from __future__ import annotations

import json
import sys
from typing import Any, Dict

import numpy as np

from embedding_store import sanitize_name
from refquery import RefQueryDisaggregator


def _binary_f1_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=np.int32).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=np.int32).reshape(-1)
    if y_true.size == 0 or y_pred.size == 0 or y_true.size != y_pred.size:
        return 0.0
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    if tp == 0:
        return 0.0
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    denom = precision + recall
    return float(0.0 if denom <= 0 else (2.0 * precision * recall) / denom)


def _best_prob_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> tuple[float, float]:
    y_true = np.asarray(y_true, dtype=np.int32).reshape(-1)
    y_prob = np.asarray(y_prob, dtype=np.float32).reshape(-1)

    if y_true.size == 0 or y_prob.size == 0 or y_true.size != y_prob.size or np.unique(y_true).size < 2:
        return 0.5, 0.0

    best_thr = 0.5
    best_f1 = -1.0
    for thr in np.linspace(0.05, 0.95, 19):
        y_pred = (y_prob >= float(thr)).astype(np.int32)
        f1 = _binary_f1_score(y_true, y_pred)
        if f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)
    return float(best_thr), float(best_f1)


def _summarize_scores(scores: np.ndarray, threshold: float, y_true: np.ndarray) -> Dict[str, Any]:
    scores = np.asarray(scores, dtype=np.float32).reshape(-1)
    y_true = np.asarray(y_true, dtype=np.int32).reshape(-1)
    if scores.size == 0:
        return {
            "n_points": 0,
            "max_score": None,
            "min_score": None,
            "mean_score": None,
            "threshold": float(threshold),
            "n_above_threshold": 0,
            "f1_at_threshold": 0.0,
        }
    y_pred = (scores >= float(threshold)).astype(np.int32)
    return {
        "n_points": int(scores.size),
        "max_score": float(np.max(scores)),
        "min_score": float(np.min(scores)),
        "mean_score": float(np.mean(scores)),
        "threshold": float(threshold),
        "n_above_threshold": int(np.sum(y_pred)),
        "f1_at_threshold": _binary_f1_score(y_true, y_pred),
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: edge_replay_worker.py <replay_input_json>")

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        payload = json.load(f)

    inference_dir = str(payload.get("inference_dir") or "")
    embeddings_dir = str(payload.get("embeddings_dir") or "")
    appliance_name = str(payload.get("appliance_name") or "")
    embeddings = np.asarray(payload.get("embeddings") or [], dtype=np.float32)
    targets_on = np.asarray(payload.get("targets_on") or [], dtype=np.int32)

    if not inference_dir or not embeddings_dir or not appliance_name:
        raise RuntimeError("Replay payload missing inference_dir, embeddings_dir, or appliance_name")

    if embeddings.ndim != 2 or embeddings.shape[0] == 0 or embeddings.shape[0] != targets_on.size:
        print(json.dumps(_summarize_scores(np.zeros((0,), dtype=np.float32), 0.5, np.zeros((0,), dtype=np.int32))))
        return 0

    replay_disaggregator = RefQueryDisaggregator(
        inference_dir=inference_dir,
        embeddings_dir=embeddings_dir,
        num_threads=2,
        history_fetcher=None,
        top_k=None,
    )
    ref = replay_disaggregator._load_embedding(sanitize_name(appliance_name))
    scores = np.zeros((embeddings.shape[0],), dtype=np.float32)
    for idx in range(embeddings.shape[0]):
        query_emb = np.asarray(embeddings[idx], dtype=np.float32).reshape(1, -1)
        _power_w, onoff_value, _power_norm = replay_disaggregator._run_head(ref, query_emb)
        scores[idx] = float(onoff_value)

    threshold, _best_f1 = _best_prob_threshold(targets_on, scores)
    summary = _summarize_scores(scores, threshold, targets_on)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
