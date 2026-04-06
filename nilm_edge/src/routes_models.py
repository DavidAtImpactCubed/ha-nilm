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
from prepare_training_data import (
    QueryExtractor,
    build_uniform_grid,
    load_model_settings,
    parse_mains_points,
    zoh_resample_to_grid,
)
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


def _filter_points_to_range(points, start_ts, end_ts):
    return [
        (float(ts), float(value))
        for ts, value in (points or [])
        if float(ts) >= start_ts and float(ts) <= end_ts
    ]


async def _load_preview_points(start_dt, end_dt, provided_points=None):
    points = _filter_points_to_range(
        _normalize_preview_points(provided_points),
        start_dt.timestamp(),
        end_dt.timestamp(),
    )
    if points:
        yield {
            "processed": len(points),
            "total": len(points),
            "phase": "history_ready",
            "points": points,
        }
        return

    try:
        async for history_update in _fetch_preview_history_points(start_dt, end_dt):
            if history_update.get("phase") == "history_ready":
                history_update = dict(history_update)
                history_update["points"] = _filter_points_to_range(
                    history_update.get("points") or [],
                    start_dt.timestamp(),
                    end_dt.timestamp(),
                )
            yield history_update
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"Loading mains history took too long ({int(PREVIEW_HISTORY_TIMEOUT_S)}s). "
            "Please reduce the selected range or check the Home Assistant connection."
        ) from exc


def _build_offline_preview_inputs(points, *, inference_dir: str, num_threads: int = 2, align_grid: str = "start", max_hold_factor: float = 5.0):
    parsed_points = parse_mains_points([{"x": float(ts) * 1000.0, "y": float(value)} for ts, value in (points or [])])
    if len(parsed_points) < 2:
        return {
            "embeddings": np.zeros((0, 0), dtype=np.float32),
            "label_times_ms": np.zeros((0,), dtype=np.int64),
            "mains_at_label": np.zeros((0,), dtype=np.float32),
            "baseload_at_label": np.zeros((0,), dtype=np.float32),
        }

    settings = load_model_settings(os.path.join(inference_dir, "model_settings.json"))
    extractor = QueryExtractor(os.path.join(inference_dir, "extractor.tflite"), num_threads=num_threads)

    T = settings.sequence_length
    dt = settings.frequency_s
    pred_idx = settings.pred_idx
    t_start = parsed_points[0][0]
    t_end = parsed_points[-1][0]
    grid_t = build_uniform_grid(t_start, t_end, dt, align=align_grid)
    if grid_t.size < T:
        return {
            "embeddings": np.zeros((0, 0), dtype=np.float32),
            "label_times_ms": np.zeros((0,), dtype=np.int64),
            "mains_at_label": np.zeros((0,), dtype=np.float32),
            "baseload_at_label": np.zeros((0,), dtype=np.float32),
        }

    max_hold_s = float(max_hold_factor) * dt if max_hold_factor and max_hold_factor > 0 else None
    fill_value_w = float(settings.query_mean)
    y_grid, mains_valid_mask = zoh_resample_to_grid(
        parsed_points,
        grid_t,
        max_hold_s=max_hold_s,
        fill_value=fill_value_w,
        return_valid_mask=True,
    )

    M = int(grid_t.size)
    N = M - (T - 1)
    windows_raw = np.lib.stride_tricks.sliding_window_view(y_grid.astype(np.float32), window_shape=T)
    baseload_per_window = np.min(windows_raw, axis=1).astype(np.float32)
    windows_shifted = windows_raw - baseload_per_window[:, None]
    query_std = settings.query_std if abs(settings.query_std) > 1e-12 else 1.0
    windows = ((windows_shifted - float(settings.query_mean)) / float(query_std)).astype(np.float32)
    valid_windows_mask = np.all(
        np.lib.stride_tricks.sliding_window_view(mains_valid_mask.astype(np.uint8), window_shape=T) == 1,
        axis=1,
    )

    grid_t_end = grid_t[(T - 1):]
    offset = (T - 1 - pred_idx) * dt
    grid_t_label = grid_t_end - offset
    mains_at_label = y_grid[pred_idx:(pred_idx + N)].astype(np.float32)

    windows = windows[valid_windows_mask]
    grid_t_label = grid_t_label[valid_windows_mask]
    mains_at_label = mains_at_label[valid_windows_mask]
    baseload_per_window = baseload_per_window[valid_windows_mask]

    if windows.shape[0] == 0:
        return {
            "embeddings": np.zeros((0, 0), dtype=np.float32),
            "label_times_ms": np.zeros((0,), dtype=np.int64),
            "mains_at_label": np.zeros((0,), dtype=np.float32),
            "baseload_at_label": np.zeros((0,), dtype=np.float32),
        }

    X = extractor.build_input_batch(windows)
    embs, mask = extractor.extract_embeddings(X, return_mask=True)
    if mask is None:
        raise RuntimeError("Internal error: preview extractor mask not returned")

    return {
        "embeddings": embs,
        "label_times_ms": np.round(grid_t_label[mask] * 1000.0).astype(np.int64),
        "mains_at_label": mains_at_label[mask].astype(np.float32),
        "baseload_at_label": baseload_per_window[mask].astype(np.float32),
    }


def _score_preview_embeddings(preview_disaggregator, safe_names, preview_inputs):
    embeddings = np.asarray(preview_inputs.get("embeddings"), dtype=np.float32)
    label_times_ms = np.asarray(preview_inputs.get("label_times_ms"), dtype=np.int64)
    mains_at_label = np.asarray(preview_inputs.get("mains_at_label"), dtype=np.float32)
    baseload_at_label = np.asarray(preview_inputs.get("baseload_at_label"), dtype=np.float32)

    prediction_map = {
        safe_name: {
            "power_series": [],
            "baseload_series": [],
            "state_series": [],
        }
        for safe_name in safe_names
    }

    if embeddings.ndim != 2 or embeddings.shape[0] == 0:
        return prediction_map

    model_state = {}
    for safe_name in safe_names:
        ref = preview_disaggregator._load_embedding(safe_name)
        params = preview_disaggregator._load_appliance_params(safe_name)
        model_state[safe_name] = (ref, float(params.get("onoff_threshold", 0.5)))

    for idx in range(embeddings.shape[0]):
        query_emb = np.asarray(embeddings[idx], dtype=np.float32).reshape(1, -1)
        target_ms = int(label_times_ms[idx])
        baseload_value = float(max(0.0, baseload_at_label[idx])) if idx < baseload_at_label.size else 0.0
        available_appliance_power = float(max(0.0, float(mains_at_label[idx]) - baseload_value)) if idx < mains_at_label.size else 0.0

        for safe_name in safe_names:
            ref, onoff_threshold = model_state[safe_name]
            power_w, onoff_value, _power_norm = preview_disaggregator._run_head(ref, query_emb)
            power_w = float(max(0.0, power_w))
            power_w = float(min(power_w, available_appliance_power))
            if onoff_value < onoff_threshold:
                power_w = 0.0

            prediction_map[safe_name]["power_series"].append({"x": target_ms, "y": power_w})
            prediction_map[safe_name]["baseload_series"].append({"x": target_ms, "y": baseload_value})
            prediction_map[safe_name]["state_series"].append({
                "x": target_ms,
                "y": int(onoff_value >= onoff_threshold),
                "score": float(onoff_value),
                "threshold": float(onoff_threshold),
            })

    return prediction_map


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

    points = []
    async for history_update in _load_preview_points(start_dt, end_dt, provided_points=provided_points):
        if history_update.get("phase") == "history_ready":
            points = history_update.get("points") or []
            yield {
                "processed": int(history_update.get("processed", 0)),
                "total": int(history_update.get("total", 0)),
                "phase": "history_ready",
            }
        else:
            yield history_update

    if not points:
        yield {
            "done": True,
            "power_series": [],
            "state_series": [],
            "processed": 0,
            "total": 0,
        }
        return

    yield {"processed": 0, "total": len(points), "phase": "embeddings"}
    preview_inputs = _build_offline_preview_inputs(points, inference_dir=bundle.inference_dir, num_threads=2, align_grid="start", max_hold_factor=5.0)
    embeddings = np.asarray(preview_inputs.get("embeddings"), dtype=np.float32)
    total = int(embeddings.shape[0])
    if total <= 0:
        yield {
            "done": True,
            "power_series": [],
            "baseload_series": [],
            "state_series": [],
            "processed": 0,
            "total": 0,
        }
        return

    yield {"processed": total, "total": total, "phase": "inference"}
    prediction_map = _score_preview_embeddings(preview_disaggregator, [safe_name], preview_inputs)
    prediction = prediction_map.get(safe_name) or {}

    yield {
        "done": True,
        "power_series": prediction.get("power_series", []),
        "baseload_series": prediction.get("baseload_series", []),
        "state_series": prediction.get("state_series", []),
        "processed": total,
        "total": total,
    }


async def _build_preview_all_results(model_entries, start_dt, end_dt, provided_points=None):
    if not model_entries:
        yield {"done": True, "predictions": [], "processed": 0, "total": 0}
        return

    grouped_models = {}
    for model_entry in model_entries:
        bundle_id = str(model_entry.get("bundle_id") or "").strip()
        safe_name = str(model_entry.get("appliance_name") or "").strip()
        if not bundle_id or not safe_name:
            continue
        grouped_models.setdefault(bundle_id, []).append({
            "model_key": make_model_key(bundle_id, safe_name),
            "model_name": safe_name,
            "safe_name": safe_name,
        })

    if not grouped_models:
        yield {"done": True, "predictions": [], "processed": 0, "total": 0}
        return

    all_predictions = []

    for bundle_id, bundle_models in grouped_models.items():
        bundle = get_bundle_by_id(app_state.model_bundles, bundle_id)
        if bundle is None:
            continue

        preview_disaggregator = RefQueryDisaggregator(
            inference_dir=bundle.inference_dir,
            embeddings_dir=bundle_models_dir(app_state.MODELS_ROOT, bundle_id),
            num_threads=2,
            history_fetcher=None,
            top_k=None,
        )

        points = []
        async for history_update in _load_preview_points(start_dt, end_dt, provided_points=provided_points):
            if history_update.get("phase") == "history_ready":
                points = history_update.get("points") or []
                yield {
                    "processed": int(history_update.get("processed", 0)),
                    "total": int(history_update.get("total", 0)),
                    "phase": "history_ready",
                }
            else:
                yield history_update

        if not points:
            continue

        model_names = [item["safe_name"] for item in bundle_models]
        yield {"processed": 0, "total": len(points), "phase": "embeddings"}
        preview_inputs = _build_offline_preview_inputs(points, inference_dir=bundle.inference_dir, num_threads=2, align_grid="start", max_hold_factor=5.0)
        embeddings = np.asarray(preview_inputs.get("embeddings"), dtype=np.float32)
        total = int(embeddings.shape[0])
        if total <= 0:
            continue
        yield {"processed": total, "total": total, "phase": "inference"}

        scored_predictions = _score_preview_embeddings(preview_disaggregator, model_names, preview_inputs)

        for item in bundle_models:
            prediction = scored_predictions.get(item["safe_name"]) or {}
            power_series = prediction.get("power_series", [])
            state_series = prediction.get("state_series", [])

            all_predictions.append({
                "model_key": item["model_key"],
                "model_name": item["model_name"],
                "power_series": power_series,
                "baseload_series": prediction.get("baseload_series", []),
                "state_series": state_series,
            })

    yield {
        "done": True,
        "predictions": all_predictions,
        "processed": len(all_predictions),
        "total": len(all_predictions),
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
                        "baseload_series": update.get("baseload_series", []),
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


async def _run_preview_all_job(app, job_id, model_entries, start_dt, end_dt, provided_points=None):
    try:
        await _set_preview_job(app, job_id, {
            "status": "running",
            "phase": "history",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "processed": 0,
            "total": 0,
            "percent": 5,
        })

        async for update in _build_preview_all_results(model_entries, start_dt, end_dt, provided_points=provided_points):
            if update.get("done"):
                await _set_preview_job(app, job_id, {
                    "status": "done",
                    "phase": "done",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "processed": int(update.get("processed", 0)),
                    "total": int(update.get("total", 0)),
                    "percent": 100,
                    "result": {
                        "predictions": update.get("predictions", []),
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


async def start_preview_all_embeddings_handler(request):
    try:
        data = await request.json()
        if not isinstance(data, dict):
            return web.json_response({"status": "error", "message": "Invalid JSON body"}, status=400)

        start_raw = str(data.get("start") or "").strip()
        end_raw = str(data.get("end") or "").strip()
        provided_points = data.get("mains_points")
        if not start_raw or not end_raw:
            return web.json_response({"status": "error", "message": "Missing start/end query parameters"}, status=400)

        start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        if start_dt >= end_dt:
            return web.json_response({"status": "error", "message": "start must be before end"}, status=400)

        model_entries = []
        for model_entry in list_saved_models(app_state.MODELS_ROOT):
            bundle_id = model_entry["bundle_id"]
            safe_name = model_entry["appliance_name"]
            bundle = get_bundle_by_id(app_state.model_bundles, bundle_id)
            if bundle is None:
                continue
            model_entries.append({
                "bundle_id": bundle_id,
                "appliance_name": safe_name,
            })

        if not model_entries:
            return web.json_response({"status": "error", "message": "No appliance models found yet."}, status=400)

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
        asyncio.create_task(_run_preview_all_job(request.app, job_id, model_entries, start_dt, end_dt, provided_points=provided_points))
        return web.json_response({"status": "accepted", "job_id": job_id})
    except ValueError as exc:
        return web.json_response({"status": "error", "message": str(exc)}, status=400)
    except Exception as exc:
        print(f"Error handling POST /embeddings/preview-all: {exc}")
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
    app.router.add_post(ingress_url_base + "embeddings/preview-all", start_preview_all_embeddings_handler)
    app.router.add_get(ingress_url_base + "preview-jobs/{job_id}", preview_embedding_status_handler)
    app.router.add_patch(ingress_url_base + "embeddings/{name}", update_embedding_handler)
    app.router.add_post(ingress_url_base + "embeddings/{name}", update_embedding_handler)
    app.router.add_delete(ingress_url_base + "embeddings/{name}", delete_embedding_handler)
