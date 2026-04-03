from __future__ import annotations
from typing import Any, Dict


def training_server_payload_from_prepared(prepared: Dict[str, Any]) -> Dict[str, Any]:
    appliance_name = prepared.get("appliance_name") or prepared.get("_meta", {}).get("appliance_name")
    appliance_type = prepared.get("appliance_type") or prepared.get("_meta", {}).get("appliance_type")

    embeddings = prepared.get("embeddings") or prepared.get("query_embeddings")
    targets_on = prepared.get("targets_on") or prepared.get("y_on") or prepared.get("targets")
    targets_power = prepared.get("targets_power")
    supervision_mode = prepared.get("supervision_mode")
    appliance_sensor_id = prepared.get("appliance_sensor_id")
    bundle_id = prepared.get("bundle_id")
    bundle_mode = prepared.get("bundle_mode")
    bundle_version = prepared.get("bundle_version")

    settings = prepared.get("settings") or {}
    t_label = prepared.get("t_label")
    t_end = prepared.get("t_end")

    missing = []
    if not appliance_name: missing.append("appliance_name")
    if not isinstance(embeddings, list) or not embeddings: missing.append("embeddings")
    if not isinstance(targets_on, list) or not targets_on: missing.append("targets_on")
    if missing:
        raise ValueError(f"Prepared payload missing/invalid fields required by the training server: {missing}")

    return {
        "appliance_name": str(appliance_name),
        "appliance_type": str(appliance_type or ""),
        "supervision_mode": supervision_mode,
        "appliance_sensor_id": appliance_sensor_id,
        "bundle_id": bundle_id,
        "bundle_mode": bundle_mode,
        "bundle_version": bundle_version,
        "settings": settings,
        "embeddings": embeddings,
        "targets_on": targets_on,
        "targets_power": targets_power,
        "t_label": t_label,
        "t_end": t_end,
    }


def summarize_training_server_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    embeddings = payload.get("embeddings") if isinstance(payload.get("embeddings"), list) else []
    targets_on = payload.get("targets_on") if isinstance(payload.get("targets_on"), list) else []
    targets_power = payload.get("targets_power") if isinstance(payload.get("targets_power"), list) else []
    first_embedding = embeddings[0] if embeddings and isinstance(embeddings[0], list) else []

    return {
        "appliance_name": payload.get("appliance_name"),
        "bundle_id": payload.get("bundle_id"),
        "bundle_mode": payload.get("bundle_mode"),
        "supervision_mode": payload.get("supervision_mode"),
        "n_embeddings": len(embeddings),
        "embedding_dim": len(first_embedding),
        "n_targets_on": len(targets_on),
        "n_targets_power": len(targets_power),
    }
