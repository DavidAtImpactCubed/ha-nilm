from __future__ import annotations

import json
import os
import shutil
from typing import Any, Dict, Iterable, List, Optional

import numpy as np


def sanitize_name(name: str) -> str:
    return "".join(c.lower() if c.isalnum() or c in ("_", "-") else "_" for c in name.strip())


def bundle_models_dir(models_root: str, bundle_id: str) -> str:
    return os.path.join(models_root, sanitize_name(bundle_id))


def deleted_marker_path(embeddings_dir: str, appliance_name: str) -> str:
    safe = sanitize_name(appliance_name)
    return os.path.join(embeddings_dir, ".deleted", f"{safe}.marker")


def mark_embedding_deleted(embeddings_dir: str, appliance_name: str) -> str:
    path = deleted_marker_path(embeddings_dir, appliance_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("deleted\n")
    return path


def clear_deleted_marker(embeddings_dir: str, appliance_name: str) -> None:
    path = deleted_marker_path(embeddings_dir, appliance_name)
    if os.path.exists(path):
        os.remove(path)


def is_embedding_marked_deleted(embeddings_dir: str, appliance_name: str) -> bool:
    return os.path.exists(deleted_marker_path(embeddings_dir, appliance_name))


def save_embedding_npy(embeddings_dir: str, appliance_name: str, emb: List[float]) -> str:
    """
    Saves embedding to /data/embeddings/<appliance>.npy
    Returns saved path.
    """
    os.makedirs(embeddings_dir, exist_ok=True)
    safe = sanitize_name(appliance_name)
    path = os.path.join(embeddings_dir, f"{safe}.npy")
    arr = np.asarray(emb, dtype=np.float32).reshape(1, -1)
    np.save(path, arr)
    clear_deleted_marker(embeddings_dir, safe)
    return path


def metadata_path_for_embedding(embeddings_dir: str, appliance_name: str) -> str:
    safe = sanitize_name(appliance_name)
    return os.path.join(embeddings_dir, f"{safe}.json")


def save_embedding_metadata(embeddings_dir: str, appliance_name: str, metadata: Dict[str, Any]) -> str:
    os.makedirs(embeddings_dir, exist_ok=True)
    path = metadata_path_for_embedding(embeddings_dir, appliance_name)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)
    return path


def load_embedding_metadata(embeddings_dir: str, appliance_name: str) -> Optional[Dict[str, Any]]:
    path = metadata_path_for_embedding(embeddings_dir, appliance_name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def delete_embedding_files(embeddings_dir: str, appliance_name: str) -> Dict[str, bool]:
    safe = sanitize_name(appliance_name)
    npy_path = os.path.join(embeddings_dir, f"{safe}.npy")
    json_path = os.path.join(embeddings_dir, f"{safe}.json")

    deleted_npy = False
    deleted_json = False
    if os.path.exists(npy_path):
        os.remove(npy_path)
        deleted_npy = True
    if os.path.exists(json_path):
        os.remove(json_path)
        deleted_json = True

    mark_embedding_deleted(embeddings_dir, safe)

    return {"embedding": deleted_npy, "metadata": deleted_json}


def list_saved_models(models_root: str) -> List[Dict[str, str]]:
    if not os.path.isdir(models_root):
        return []

    out: List[Dict[str, str]] = []
    for bundle_entry in sorted(os.listdir(models_root)):
        bundle_dir = os.path.join(models_root, bundle_entry)
        if not os.path.isdir(bundle_dir):
            continue
        for filename in sorted(os.listdir(bundle_dir)):
            if not filename.endswith(".npy"):
                continue
            appliance_name = filename[:-4]
            out.append({
                "bundle_id": sanitize_name(bundle_entry),
                "appliance_name": appliance_name,
                "embedding_path": os.path.join(bundle_dir, filename),
                "metadata_path": metadata_path_for_embedding(bundle_dir, appliance_name),
            })
    return out


def rename_bundle_models_dir(models_root: str, old_bundle_id: str, new_bundle_id: str) -> bool:
    old_dir = bundle_models_dir(models_root, old_bundle_id)
    new_dir = bundle_models_dir(models_root, new_bundle_id)

    if not os.path.isdir(old_dir):
        return False
    if old_dir == new_dir:
        return False

    if os.path.exists(new_dir):
        return False

    os.makedirs(os.path.dirname(new_dir), exist_ok=True)
    os.replace(old_dir, new_dir)
    return True


def migrate_legacy_models(
    *,
    legacy_embeddings_dir: str,
    models_root: str,
    default_bundle_id: Optional[str],
) -> int:
    if not default_bundle_id or not os.path.isdir(legacy_embeddings_dir):
        return 0

    target_dir = bundle_models_dir(models_root, default_bundle_id)
    os.makedirs(target_dir, exist_ok=True)

    migrated = 0
    for filename in os.listdir(legacy_embeddings_dir):
        if not (filename.endswith(".npy") or filename.endswith(".json")):
            continue
        src_path = os.path.join(legacy_embeddings_dir, filename)
        if not os.path.isfile(src_path):
            continue
        dst_path = os.path.join(target_dir, filename)
        if os.path.exists(dst_path):
            continue
        shutil.move(src_path, dst_path)
        migrated += 1

    deleted_dir = os.path.join(legacy_embeddings_dir, ".deleted")
    if os.path.isdir(deleted_dir):
        target_deleted_dir = os.path.join(target_dir, ".deleted")
        os.makedirs(target_deleted_dir, exist_ok=True)
        for filename in os.listdir(deleted_dir):
            src_path = os.path.join(deleted_dir, filename)
            dst_path = os.path.join(target_deleted_dir, filename)
            if os.path.isfile(src_path) and not os.path.exists(dst_path):
                shutil.move(src_path, dst_path)
                migrated += 1

    return migrated
