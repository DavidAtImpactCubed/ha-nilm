from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from embedding_store import sanitize_name


REQUIRED_BUNDLE_FILES = (
    "extractor.tflite",
    "head.tflite",
    "model_settings.json",
    "bundle_manifest.json",
)


@dataclass(frozen=True)
class ModelBundle:
    bundle_id: str
    mode: str
    model_version: int
    saved_at: str
    inference_dir: str
    manifest_path: str
    is_default_for_training: bool = False
    display_name: Optional[str] = None

    @property
    def label(self) -> str:
        if self.display_name:
            return self.display_name
        return f"{self.mode.title()} v{self.model_version}"


def _parse_utc(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _bundle_sort_key(bundle: ModelBundle) -> Tuple[int, datetime, str]:
    return (
        int(bundle.model_version),
        _parse_utc(bundle.saved_at),
        bundle.bundle_id,
    )


def _load_bundle_from_manifest(manifest_path: str) -> ModelBundle:
    with open(manifest_path, "r", encoding="utf-8") as file_handle:
        raw = json.load(file_handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid bundle manifest: {manifest_path}")

    bundle_id = sanitize_name(str(raw.get("bundle_id") or "").strip())
    if not bundle_id:
        raise ValueError(f"bundle_id is required in {manifest_path}")

    mode = str(raw.get("mode") or "online").strip().lower()
    if mode not in ("online", "offline"):
        raise ValueError(f"Unsupported bundle mode '{mode}' in {manifest_path}")

    inference_dir = os.path.dirname(manifest_path)
    for required_name in REQUIRED_BUNDLE_FILES[:-1]:
        required_path = os.path.join(inference_dir, required_name)
        if not os.path.exists(required_path):
            raise FileNotFoundError(f"Missing {required_name} for bundle {bundle_id}: {required_path}")

    return ModelBundle(
        bundle_id=bundle_id,
        mode=mode,
        model_version=int(raw.get("model_version", raw.get("version", 1))),
        saved_at=str(raw.get("saved_at") or raw.get("created_at") or ""),
        inference_dir=inference_dir,
        manifest_path=manifest_path,
        is_default_for_training=bool(raw.get("is_default_for_training", False)),
        display_name=str(raw.get("display_name") or "").strip() or None,
    )


def discover_model_bundles(base_inference_dir: str) -> List[ModelBundle]:
    bundles: Dict[str, ModelBundle] = {}

    root_manifest = os.path.join(base_inference_dir, "bundle_manifest.json")
    if os.path.exists(root_manifest):
        bundle = _load_bundle_from_manifest(root_manifest)
        bundles[bundle.bundle_id] = bundle

    bundles_root = os.path.join(base_inference_dir, "bundles")
    if os.path.isdir(bundles_root):
        for entry in os.listdir(bundles_root):
            manifest_path = os.path.join(bundles_root, entry, "bundle_manifest.json")
            if not os.path.exists(manifest_path):
                continue
            bundle = _load_bundle_from_manifest(manifest_path)
            bundles[bundle.bundle_id] = bundle

    return sorted(bundles.values(), key=_bundle_sort_key, reverse=True)


def get_bundle_by_id(bundles: Iterable[ModelBundle], bundle_id: str) -> Optional[ModelBundle]:
    safe_bundle_id = sanitize_name(bundle_id)
    for bundle in bundles:
        if bundle.bundle_id == safe_bundle_id:
            return bundle
    return None


def get_latest_bundle_for_mode(bundles: Iterable[ModelBundle], mode: str) -> Optional[ModelBundle]:
    normalized_mode = str(mode or "").strip().lower()
    candidates = [bundle for bundle in bundles if bundle.mode == normalized_mode]
    if not candidates:
        return None

    explicit_defaults = [bundle for bundle in candidates if bundle.is_default_for_training]
    if explicit_defaults:
        return sorted(explicit_defaults, key=_bundle_sort_key, reverse=True)[0]

    return sorted(candidates, key=_bundle_sort_key, reverse=True)[0]


def make_model_key(bundle_id: str, appliance_name: str) -> str:
    return f"{sanitize_name(bundle_id)}:{sanitize_name(appliance_name)}"


def parse_model_key(model_key: str) -> Tuple[str, str]:
    value = str(model_key or "").strip()
    if ":" not in value:
        raise ValueError("Model key must be in the form '<bundle_id>:<appliance_name>'")
    bundle_id, appliance_name = value.split(":", 1)
    safe_bundle_id = sanitize_name(bundle_id)
    safe_appliance_name = sanitize_name(appliance_name)
    if not safe_bundle_id or not safe_appliance_name:
        raise ValueError("Model key is missing bundle_id or appliance_name")
    return safe_bundle_id, safe_appliance_name
