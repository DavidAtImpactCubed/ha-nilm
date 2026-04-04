import os
import time
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

import numpy as np
from aiohttp import web

import app_state
from embedding_store import bundle_models_dir, delete_embedding_files, list_saved_models, load_embedding_metadata, save_embedding_metadata
from ha_client import HistoryQuery, fetch_history_points
from model_registry import get_bundle_by_id, make_model_key, parse_model_key
from prepare_training_data import compute_on_mask
from refquery import RefQueryDisaggregator

PREVIEW_HISTORY_TIMEOUT_S = 30.0
PREVIEW_HISTORY_CHUNK_HOURS = 1.0


async def _set_preview_job(app, job_id, patch):
    async with app["preview_jobs_lock"]:
        current = app["preview_jobs"].get(job_id, {})
        current.update(patch)
        app["preview_jobs"][job_id] = current


async def _get_preview_job(app, job_id):
    async with app["preview_jobs_lock"]:
        return dict(app["preview_jobs"].get(job_id) or {})


async def _fetch_preview_history_points(fetch_start_dt, end_dt):
    entity_id = (app_state.current_config.get("main_sensor_id") or "").strip()
    if not entity_id:
        raise ValueError("No mains sensor configured. Please select and save a mains sensor first.")
    chunk_delta = timedelta(hours=PREVIEW_HISTORY_CHUNK_HOURS)
    chunk_bounds = []
    cursor = fetch_start_dt

    while cursor < end_dt:
        chunk_end = min(cursor + chunk_delta, end_dt)
        chunk_bounds.append((cursor, chunk_end))
        cursor = chunk_end

    if not chunk_bounds:
        chunk_bounds.append((fetch_start_dt, end_dt))

    all_points = []
    seen = set()
    total_chunks = len(chunk_bounds)

    for index, (chunk_start, chunk_end) in enumerate(chunk_bounds, start=1):
        chunk_points = await asyncio.wait_for(
            fetch_history_points(
                app_state.HA_REST_API_URL,
                app_state.TOKEN,
                HistoryQuery(
                    entity_id=entity_id,
                    start_dt=chunk_start,
                    end_dt=chunk_end,
                    minimal_response=True,
                    max_span_days=7,
                ),
            ),
            timeout=PREVIEW_HISTORY_TIMEOUT_S,
        )

        for ts, value in chunk_points:
            key = (float(ts), float(value))
            if key in seen:
                continue
            seen.add(key)
            all_points.append((float(ts), float(value)))

        yield {
            "phase": "history",
            "processed": index,
            "total": total_chunks,
        }

    all_points.sort(key=lambda item: item[0])
    yield {
        "phase": "history_ready",
        "processed": len(all_points),
        "total": len(all_points),
        "points": all_points,
    }


def _normalize_preview_points(raw_points):
    normalized = []
    seen = set()
    for point in raw_points or []:
        if not isinstance(point, dict):
            continue
        raw_x = point.get("x")
        raw_y = point.get("y")
        try:
            ts = float(raw_x)
            if ts > 1e12:
                ts /= 1000.0
            value = float(raw_y)
        except (TypeError, ValueError):
            continue
        key = (ts, value)
        if key in seen:
            continue
        seen.add(key)
        normalized.append((ts, value))
    normalized.sort(key=lambda item: item[0])
    return normalized


async def _fetch_preview_history_points_range(fetch_start_dt, end_dt):
    if fetch_start_dt >= end_dt:
        return []

    points = []
    async for history_update in _fetch_preview_history_points(fetch_start_dt, end_dt):
        if history_update.get("phase") == "history_ready":
            points = history_update.get("points") or []
    return points


async def _build_preview_result(bundle_id, safe_name, start_dt, end_dt, provided_points=None):
    bundle = get_bundle_by_id(app_state.model_bundles, bundle_id)
    if bundle is None:
        raise ValueError(f"Unknown bundle_id: {bundle_id}")

    preview_disaggregator = RefQueryDisaggregator(
        inference_dir=bundle.inference_dir,
        embeddings_dir=bundle_models_dir(app_state.MODELS_ROOT, bundle_id),
        num_threads=2,
        history_fetcher=None,
        top_k=None,
    )

    lookback_s = preview_disaggregator.settings.sequence_length * preview_disaggregator.settings.frequency_s
    fetch_start_dt = start_dt - timedelta(seconds=lookback_s)
    if (end_dt.date() - fetch_start_dt.date()).days + 1 > 7:
        fetch_start_dt = start_dt

    points = _normalize_preview_points(provided_points)
    if points:
        earliest_ts = points[0][0]
        required_start_ts = fetch_start_dt.timestamp()
        if earliest_ts > required_start_ts + 1e-6:
            missing_end_dt = datetime.fromtimestamp(earliest_ts, tz=timezone.utc)
            try:
                missing_points = await _fetch_preview_history_points_range(fetch_start_dt, missing_end_dt)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"Loading mains history took too long ({int(PREVIEW_HISTORY_TIMEOUT_S)}s). "
                    "Please reduce the selected range or check the Home Assistant connection."
                ) from exc
            points = _normalize_preview_points(
                [{"x": ts, "y": value} for ts, value in missing_points] +
                [{"x": ts, "y": value} for ts, value in points]
            )
        yield {
            "processed": len(points),
            "total": len(points),
            "phase": "history_ready",
        }
    else:
        try:
            async for history_update in _fetch_preview_history_points(fetch_start_dt, end_dt):
                if history_update.get("phase") == "history_ready":
                    points = history_update.get("points") or []
                    yield {
                        "processed": int(history_update.get("processed", 0)),
                        "total": int(history_update.get("total", 0)),
                        "phase": "history_ready",
                    }
                else:
                    yield history_update
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"Loading mains history took too long ({int(PREVIEW_HISTORY_TIMEOUT_S)}s). "
                "Please reduce the selected range or check the Home Assistant connection."
            ) from exc

    if not points:
        yield {
            "done": True,
            "power_series": [],
            "state_series": [],
            "processed": 0,
            "total": 0,
        }
        return

    power_series = []
    preview_times_ms = []
    processed = 0
    total = len(points)
    last_progress_emit = 0.0

    yield {"processed": 0, "total": total, "phase": "inference"}

    for ts, mains_power in points:
        result = await preview_disaggregator.disaggregate_next(float(mains_power), float(ts), appliances=[safe_name])
        processed += 1
        now_mono = time.monotonic()
        if processed == 1 or processed == total or now_mono - last_progress_emit >= 0.05:
            yield {"processed": processed, "total": total, "phase": "inference"}
            last_progress_emit = now_mono
        if processed % 32 == 0:
            await asyncio.sleep(0)
        if not result:
            continue

        target_ts = float(result.get("timestamp", ts))
        if target_ts < start_dt.timestamp() or target_ts > end_dt.timestamp():
            continue

        appliance_result = (result.get("appliances") or {}).get(safe_name)
        if not appliance_result:
            continue

        power_value = float(appliance_result.get("power", 0.0) or 0.0)
        target_ms = int(round(target_ts * 1000.0))

        power_series.append({"x": target_ms, "y": power_value})
        preview_times_ms.append(target_ms)

    state_series = []
    if power_series:
        yield {"processed": total, "total": total, "phase": "postprocess"}
        power_values = np.asarray([float(point["y"]) for point in power_series], dtype=np.float32)
        on_mask = compute_on_mask(
            power_values,
            sample_period_s=float(preview_disaggregator.settings.frequency_s),
            threshold_watts=20.0,
            window_hours=24.0,
            min_on_s=60.0,
            min_off_s=300.0,
        )
        state_series = [
            {"x": int(preview_times_ms[i]), "y": int(on_mask[i] >= 1)}
            for i in range(min(len(preview_times_ms), len(on_mask)))
        ]

    yield {
        "done": True,
        "power_series": power_series,
        "state_series": state_series,
        "processed": total,
        "total": total,
    }


async def _run_preview_job(app, job_id, bundle_id, safe_name, start_dt, end_dt, provided_points=None):
    try:
        await _set_preview_job(app, job_id, {
            "status": "running",
            "phase": "history",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "processed": 0,
            "total": 0,
            "percent": 5,
        })

        async for update in _build_preview_result(bundle_id, safe_name, start_dt, end_dt, provided_points=provided_points):
            if update.get("done"):
                await _set_preview_job(app, job_id, {
                    "status": "done",
                    "phase": "done",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "processed": int(update.get("processed", 0)),
                    "total": int(update.get("total", 0)),
                    "percent": 100,
                    "result": {
                        "power_series": update.get("power_series", []),
                        "state_series": update.get("state_series", []),
                    },
                })
                return

            processed = int(update.get("processed", 0))
            total = int(update.get("total", 0))
            phase = str(update.get("phase") or "inference")
            if total > 0:
                if phase == "history":
                    percent = max(5, min(24, int(round((processed / total) * 24))))
                elif phase == "history_ready":
                    percent = 25
                elif phase == "postprocess":
                    percent = 95
                else:
                    percent = max(26, min(92, 25 + int(round((processed / total) * 67))))
            else:
                percent = 5 if phase == "history" else 8
            await _set_preview_job(app, job_id, {
                "status": "running",
                "phase": phase,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "processed": processed,
                "total": total,
                "percent": percent,
            })
            await asyncio.sleep(0)
    except Exception as exc:
        await _set_preview_job(app, job_id, {
            "status": "error",
            "phase": "error",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message": str(exc),
        })


async def get_embeddings_handler(request):
    try:
        embeddings = []
        for model_entry in list_saved_models(app_state.MODELS_ROOT):
            bundle_id = model_entry["bundle_id"]
            name = model_entry["appliance_name"]
            path = model_entry["embedding_path"]
            bundle = get_bundle_by_id(app_state.model_bundles, bundle_id)
            if bundle is None:
                continue
            stat = os.stat(path)
            metadata = load_embedding_metadata(bundle_models_dir(app_state.MODELS_ROOT, bundle_id), name) or {}
            embeddings.append({
                "model_key": make_model_key(bundle_id, name),
                "name": name,
                "bundle_id": bundle_id,
                "bundle_mode": bundle.mode,
                "bundle_version": bundle.model_version,
                "bundle_label": bundle.label,
                "file_name": os.path.basename(path),
                "path": path,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "source": "trained",
                "metadata": metadata,
                "deletable": True,
            })

        return web.json_response({"status": "success", "embeddings": embeddings})
    except Exception as exc:
        print(f"Error handling GET /embeddings: {exc}")
        return web.json_response({"status": "error", "message": f"Internal server error: {exc}"}, status=500)


async def get_model_bundles_handler(request):
    try:
        bundles = [
            {
                "bundle_id": bundle.bundle_id,
                "mode": bundle.mode,
                "version": bundle.model_version,
                "label": bundle.label,
                "is_default_for_training": bundle.is_default_for_training,
            }
            for bundle in app_state.model_bundles
        ]
        return web.json_response({"status": "success", "bundles": bundles})
    except Exception as exc:
        print(f"Error handling GET /model-bundles: {exc}")
        return web.json_response({"status": "error", "message": f"Internal server error: {exc}"}, status=500)


async def delete_embedding_handler(request):
    try:
        model_key = str(request.match_info.get("name") or "").strip()
        if not model_key:
            return web.json_response({"status": "error", "message": "Missing embedding name"}, status=400)

        bundle_id, safe_name = parse_model_key(model_key)
        bundle_dir = bundle_models_dir(app_state.MODELS_ROOT, bundle_id)
        deleted = delete_embedding_files(bundle_dir, safe_name)
        if not deleted["embedding"] and not deleted["metadata"]:
            return web.json_response({"status": "error", "message": "Embedding not found"}, status=404)

        app_state.reload_algorithm_config()
        return web.json_response({"status": "success", "message": f"Appliance model '{safe_name}' deleted"})
    except ValueError as exc:
        return web.json_response({"status": "error", "message": str(exc)}, status=400)
    except Exception as exc:
        print(f"Error handling DELETE /embeddings/{{name}}: {exc}")
        return web.json_response({"status": "error", "message": f"Internal server error: {exc}"}, status=500)


async def update_embedding_handler(request):
    try:
        model_key = str(request.match_info.get("name") or "").strip()
        if not model_key:
            return web.json_response({"status": "error", "message": "Missing embedding name"}, status=400)

        bundle_id, safe_name = parse_model_key(model_key)
        bundle = get_bundle_by_id(app_state.model_bundles, bundle_id)
        if bundle is None:
            return web.json_response({"status": "error", "message": f"Unknown bundle_id: {bundle_id}"}, status=404)

        if request.method == "POST":
            action = str(request.query.get("action") or "").strip().lower()
            if action != "update":
                return web.json_response({"status": "error", "message": "Missing/invalid action. Use ?action=update"}, status=400)

        data = await request.json()
        if not isinstance(data, dict):
            return web.json_response({"status": "error", "message": "Invalid JSON body"}, status=400)

        bundle_dir = bundle_models_dir(app_state.MODELS_ROOT, bundle_id)
        metadata = load_embedding_metadata(bundle_dir, safe_name) or {}

        if "publish_online" in data:
            if bundle.mode != "online":
                return web.json_response({"status": "error", "message": "Only online bundles can publish live to Home Assistant"}, status=400)
            metadata["publish_online"] = bool(data.get("publish_online"))

        save_embedding_metadata(bundle_dir, safe_name, metadata)
        app_state.reload_algorithm_config()
        return web.json_response({"status": "success", "metadata": metadata})
    except ValueError as exc:
        return web.json_response({"status": "error", "message": str(exc)}, status=400)
    except Exception as exc:
        print(f"Error handling PATCH /embeddings/{{name}}: {exc}")
        return web.json_response({"status": "error", "message": f"Internal server error: {exc}"}, status=500)


async def start_preview_embedding_handler(request):
    try:
        model_key = str(request.match_info.get("name") or "").strip()
        if not model_key:
            return web.json_response({"status": "error", "message": "Missing embedding name"}, status=400)

        bundle_id, safe_name = parse_model_key(model_key)
        bundle = get_bundle_by_id(app_state.model_bundles, bundle_id)
        if bundle is None:
            return web.json_response({"status": "error", "message": f"Unknown bundle_id: {bundle_id}"}, status=404)

        if request.method == "POST":
            data = await request.json()
            if not isinstance(data, dict):
                return web.json_response({"status": "error", "message": "Invalid JSON body"}, status=400)
            start_raw = str(data.get("start") or "").strip()
            end_raw = str(data.get("end") or "").strip()
            provided_points = data.get("mains_points")
        else:
            start_raw = str(request.query.get("start") or "").strip()
            end_raw = str(request.query.get("end") or "").strip()
            provided_points = None
        if not start_raw or not end_raw:
            return web.json_response({"status": "error", "message": "Missing start/end query parameters"}, status=400)

        start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        if start_dt >= end_dt:
            return web.json_response({"status": "error", "message": "start must be before end"}, status=400)

        job_id = uuid.uuid4().hex
        await _set_preview_job(request.app, job_id, {
            "status": "queued",
            "phase": "queued",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "processed": 0,
            "total": 0,
            "percent": 0,
            "message": None,
        })
        asyncio.create_task(_run_preview_job(request.app, job_id, bundle_id, safe_name, start_dt, end_dt, provided_points=provided_points))
        return web.json_response({"status": "accepted", "job_id": job_id})
    except ValueError as exc:
        return web.json_response({"status": "error", "message": str(exc)}, status=400)
    except Exception as exc:
        print(f"Error handling POST /embeddings/{{name}}/preview: {exc}")
        return web.json_response({"status": "error", "message": f"Internal server error: {exc}"}, status=500)


async def preview_embedding_status_handler(request):
    try:
        job_id = str(request.match_info.get("job_id") or "").strip()
        if not job_id:
            return web.json_response({"status": "error", "message": "Missing job_id"}, status=400)

        job = await _get_preview_job(request.app, job_id)
        if not job:
            return web.json_response({"status": "error", "message": "Preview job not found"}, status=404)

        return web.json_response({
            "status": "success",
            "job_id": job_id,
            **job,
        })
    except Exception as exc:
        print(f"Error handling GET /preview-jobs/{{job_id}}: {exc}")
        return web.json_response({"status": "error", "message": f"Internal server error: {exc}"}, status=500)


def register_model_routes(app, ingress_url_base):
    if "preview_jobs" not in app:
        app["preview_jobs"] = {}
    if "preview_jobs_lock" not in app:
        app["preview_jobs_lock"] = asyncio.Lock()

    app.router.add_get(ingress_url_base + "model-bundles", get_model_bundles_handler)
    app.router.add_get(ingress_url_base + "embeddings", get_embeddings_handler)
    app.router.add_post(ingress_url_base + "embeddings/{name}/preview", start_preview_embedding_handler)
    app.router.add_get(ingress_url_base + "preview-jobs/{job_id}", preview_embedding_status_handler)
    app.router.add_patch(ingress_url_base + "embeddings/{name}", update_embedding_handler)
    app.router.add_post(ingress_url_base + "embeddings/{name}", update_embedding_handler)
    app.router.add_delete(ingress_url_base + "embeddings/{name}", delete_embedding_handler)
