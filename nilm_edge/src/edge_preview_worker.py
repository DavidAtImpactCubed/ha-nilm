from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

from prepare_training_data import (
    QueryExtractor,
    build_uniform_grid,
    load_model_settings,
    parse_mains_points,
    zoh_resample_to_grid,
)
from refquery import RefQueryDisaggregator


def emit(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def summarize_state_series(state_series):
    series = list(state_series or [])
    if not series:
        return {
            "n_points": 0,
            "max_score": None,
            "min_score": None,
            "mean_score": None,
            "threshold": None,
            "n_above_threshold": 0,
        }

    scores = []
    thresholds = []
    n_above = 0
    for point in series:
        score = point.get("score")
        threshold = point.get("threshold")
        if isinstance(score, (int, float)) and np.isfinite(score):
            scores.append(float(score))
        if isinstance(threshold, (int, float)) and np.isfinite(threshold):
            thresholds.append(float(threshold))
            if isinstance(score, (int, float)) and np.isfinite(score) and float(score) >= float(threshold):
                n_above += 1

    if not scores:
        return {
            "n_points": len(series),
            "max_score": None,
            "min_score": None,
            "mean_score": None,
            "threshold": float(thresholds[0]) if thresholds else None,
            "n_above_threshold": n_above,
        }

    return {
        "n_points": len(series),
        "max_score": float(np.max(scores)),
        "min_score": float(np.min(scores)),
        "mean_score": float(np.mean(scores)),
        "threshold": float(thresholds[0]) if thresholds else None,
        "n_above_threshold": int(n_above),
    }


def build_offline_preview_inputs(points, inference_dir: str, num_threads: int = 2, align_grid: str = "start", max_hold_factor: float = 5.0):
    parsed_points = parse_mains_points([{"x": float(ts) * 1000.0, "y": float(value)} for ts, value in (points or [])])
    if len(parsed_points) < 2:
        return {
            "windows": np.zeros((0, 0), dtype=np.float32),
            "label_times_ms": np.zeros((0,), dtype=np.int64),
            "mains_at_label": np.zeros((0,), dtype=np.float32),
            "baseload_at_label": np.zeros((0,), dtype=np.float32),
            "inference_dir": inference_dir,
            "num_threads": int(num_threads),
        }

    settings = load_model_settings(os.path.join(inference_dir, "model_settings.json"))
    T = settings.sequence_length
    dt = settings.frequency_s
    pred_idx = settings.pred_idx
    t_start = parsed_points[0][0]
    t_end = parsed_points[-1][0]
    grid_t = build_uniform_grid(t_start, t_end, dt, align=align_grid)
    if grid_t.size < T:
        return {
            "windows": np.zeros((0, 0), dtype=np.float32),
            "label_times_ms": np.zeros((0,), dtype=np.int64),
            "mains_at_label": np.zeros((0,), dtype=np.float32),
            "baseload_at_label": np.zeros((0,), dtype=np.float32),
            "inference_dir": inference_dir,
            "num_threads": int(num_threads),
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
            "windows": np.zeros((0, 0), dtype=np.float32),
            "label_times_ms": np.zeros((0,), dtype=np.int64),
            "mains_at_label": np.zeros((0,), dtype=np.float32),
            "baseload_at_label": np.zeros((0,), dtype=np.float32),
            "inference_dir": inference_dir,
            "num_threads": int(num_threads),
        }

    return {
        "windows": windows,
        "label_times_ms": np.round(grid_t_label * 1000.0).astype(np.int64),
        "mains_at_label": mains_at_label.astype(np.float32),
        "baseload_at_label": baseload_per_window.astype(np.float32),
        "inference_dir": inference_dir,
        "num_threads": int(num_threads),
    }


def extract_embeddings_with_progress(preview_inputs):
    windows = np.asarray(preview_inputs.get("windows"), dtype=np.float32)
    inference_dir = str(preview_inputs.get("inference_dir") or "")
    num_threads = int(preview_inputs.get("num_threads") or 2)
    label_times_ms = np.asarray(preview_inputs.get("label_times_ms"), dtype=np.int64)
    mains_at_label = np.asarray(preview_inputs.get("mains_at_label"), dtype=np.float32)
    baseload_at_label = np.asarray(preview_inputs.get("baseload_at_label"), dtype=np.float32)

    if not inference_dir or windows.ndim != 2 or windows.shape[0] == 0:
        return {
            "embeddings": np.zeros((0, 0), dtype=np.float32),
            "label_times_ms": np.zeros((0,), dtype=np.int64),
            "mains_at_label": np.zeros((0,), dtype=np.float32),
            "baseload_at_label": np.zeros((0,), dtype=np.float32),
        }

    extractor = QueryExtractor(os.path.join(inference_dir, "extractor.tflite"), num_threads=num_threads)
    X = extractor.build_input_batch(windows)
    out_shape = tuple(extractor.out[0]["shape"])
    D = int(np.prod(out_shape)) if len(out_shape) >= 1 else 0
    if D <= 0:
        extractor.interp.set_tensor(extractor.in_index, X[0].astype(extractor.in_dtype, copy=False))
        extractor.interp.invoke()
        D = int(np.asarray(extractor.interp.get_tensor(extractor.out_index)).size)

    N = int(X.shape[0])
    embs = np.zeros((N, D), dtype=np.float32)
    ok = np.zeros((N,), dtype=bool)
    last_emit = 0.0
    emit({"phase": "embeddings", "processed": 0, "total": N})

    for i in range(N):
        try:
            xi = X[i]
            if np.all(np.isfinite(xi)):
                extractor.interp.set_tensor(extractor.in_index, xi.astype(extractor.in_dtype, copy=False))
                extractor.interp.invoke()
                emb = np.asarray(extractor.interp.get_tensor(extractor.out_index), dtype=np.float32).reshape(-1)
                if np.linalg.norm(emb) < 1e-9:
                    emb = emb + extractor.eps
                embs[i, :] = emb
                ok[i] = True
        except Exception:
            pass

        now_mono = time.monotonic()
        if i == 0 or i == N - 1 or now_mono - last_emit >= 0.05:
            emit({"phase": "embeddings", "processed": i + 1, "total": N})
            last_emit = now_mono

    return {
        "embeddings": embs[ok],
        "label_times_ms": label_times_ms[ok],
        "mains_at_label": mains_at_label[ok],
        "baseload_at_label": baseload_at_label[ok],
    }


def score_predictions_with_progress(model_entries, preview_inputs):
    if not model_entries:
        return {}

    grouped = defaultdict(list)
    for entry in model_entries:
        grouped[entry["bundle_id"]].append(entry)

    total = 0
    if preview_inputs.get("embeddings") is not None:
        total = int(np.asarray(preview_inputs.get("embeddings"), dtype=np.float32).shape[0])
    emit({"phase": "inference", "processed": 0, "total": total})

    results = {}
    for bundle_id, entries in grouped.items():
        first = entries[0]
        disaggregator = RefQueryDisaggregator(
            inference_dir=first["inference_dir"],
            embeddings_dir=first["embeddings_dir"],
            num_threads=2,
            history_fetcher=None,
            top_k=None,
        )

        embeddings = np.asarray(preview_inputs.get("embeddings"), dtype=np.float32)
        label_times_ms = np.asarray(preview_inputs.get("label_times_ms"), dtype=np.int64)
        mains_at_label = np.asarray(preview_inputs.get("mains_at_label"), dtype=np.float32)
        baseload_at_label = np.asarray(preview_inputs.get("baseload_at_label"), dtype=np.float32)

        model_state = {}
        for entry in entries:
            ref = disaggregator._load_embedding(entry["safe_name"])
            params = disaggregator._load_appliance_params(entry["safe_name"])
            model_state[entry["safe_name"]] = (ref, float(params.get("onoff_threshold", 0.5)))
            results[entry["safe_name"]] = {
                "power_series": [],
                "baseload_series": [],
                "state_series": [],
            }

        last_emit = 0.0
        N = int(embeddings.shape[0])
        for idx in range(N):
            query_emb = np.asarray(embeddings[idx], dtype=np.float32).reshape(1, -1)
            target_ms = int(label_times_ms[idx])
            baseload_value = float(max(0.0, baseload_at_label[idx])) if idx < baseload_at_label.size else 0.0
            available_appliance_power = float(max(0.0, float(mains_at_label[idx]) - baseload_value)) if idx < mains_at_label.size else 0.0

            for safe_name, (ref, onoff_threshold) in model_state.items():
                power_w, onoff_value, _power_norm = disaggregator._run_head(ref, query_emb)
                power_w = float(max(0.0, power_w))
                power_w = float(min(power_w, available_appliance_power))
                if onoff_value < onoff_threshold:
                    power_w = 0.0

                results[safe_name]["power_series"].append({"x": target_ms, "y": power_w})
                results[safe_name]["baseload_series"].append({"x": target_ms, "y": baseload_value})
                results[safe_name]["state_series"].append({
                    "x": target_ms,
                    "y": int(onoff_value >= onoff_threshold),
                    "score": float(onoff_value),
                    "threshold": float(onoff_threshold),
                })

            now_mono = time.monotonic()
            if idx == 0 or idx == N - 1 or now_mono - last_emit >= 0.05:
                emit({"phase": "inference", "processed": idx + 1, "total": N})
                last_emit = now_mono

    return results


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: edge_preview_worker.py <payload_json>")

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        payload = json.load(f)

    result_path = str(payload.get("result_path") or "").strip()
    points = payload.get("points") or []
    model_entries = payload.get("models") or []
    if not points:
        result_payload = {"predictions": []} if payload.get("mode") == "all" else {"result": {}}
        if result_path:
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result_payload, f, ensure_ascii=False)
            emit({"done": True, "result_path": result_path})
        else:
            emit({"done": True, **result_payload})
        return 0

    preview_inputs = build_offline_preview_inputs(points, inference_dir=model_entries[0]["inference_dir"], num_threads=2, align_grid="start", max_hold_factor=5.0)
    extracted = extract_embeddings_with_progress(preview_inputs)
    embeddings = np.asarray(extracted.get("embeddings"), dtype=np.float32)
    if embeddings.ndim != 2 or embeddings.shape[0] == 0:
        result_payload = None
        if payload.get("mode") == "all":
            result_payload = {"predictions": []}
        else:
            result_payload = {"result": {"power_series": [], "baseload_series": [], "state_series": [], "state_summary": {}}}
        if result_path:
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result_payload, f, ensure_ascii=False)
            emit({"done": True, "result_path": result_path})
        else:
            emit({"done": True, **(result_payload or {})})
        return 0

    results = score_predictions_with_progress(model_entries, extracted)
    result_payload = None
    if payload.get("mode") == "all":
        predictions = []
        for entry in model_entries:
            prediction = results.get(entry["safe_name"]) or {}
            state_series = prediction.get("state_series", [])
            predictions.append({
                "model_key": entry["model_key"],
                "model_name": entry["model_name"],
                "power_series": prediction.get("power_series", []),
                "baseload_series": prediction.get("baseload_series", []),
                "state_series": state_series,
                "state_summary": summarize_state_series(state_series),
            })
        result_payload = {"predictions": predictions}
    else:
        entry = model_entries[0]
        prediction = results.get(entry["safe_name"]) or {}
        state_series = prediction.get("state_series", [])
        result_payload = {
            "result": {
                "power_series": prediction.get("power_series", []),
                "baseload_series": prediction.get("baseload_series", []),
                "state_series": state_series,
                "state_summary": summarize_state_series(state_series),
            }
        }
    if result_path:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, ensure_ascii=False)
        emit({"done": True, "result_path": result_path})
    else:
        emit({"done": True, **(result_payload or {})})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
