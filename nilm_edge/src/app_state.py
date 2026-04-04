import inspect
import json
import os
from typing import Any, Dict, Optional

from embedding_store import migrate_legacy_models, rename_bundle_models_dir
from ha_client import HistoryQuery, fetch_history_points
from model_registry import discover_model_bundles, get_latest_bundle_for_mode
from online_runtime import MultiBundleOnlineRuntime


TRAINING_SERVER_URL = (
    os.getenv("TRAINING_SERVER_URL", "").strip()
    or os.getenv("CLOUD_TRAIN_URL", "").strip()
)
TRAINING_SERVER_API_KEY = (
    os.getenv("TRAINING_SERVER_API_KEY", "").strip()
    or None
)
MODELS_ROOT = "/data/models"
LEGACY_EMBEDDINGS_DIR = "/data/embeddings"
INFERENCE_ROOT = "/app/inference"
CONFIG_FILE_PATH = "/data/config.json"
ADDON_OPTIONS_PATH = "/data/options.json"

HA_WS_URL = os.getenv("HA_WS_URL", "ws://supervisor/core/websocket")
HA_REST_API_URL = os.getenv("HA_REST_API_URL", "http://supervisor/core/api")
TOKEN = os.getenv("SUPERVISOR_TOKEN")

INGRESS_URL_BASE = os.getenv("SUPERVISOR_INGRESS_URL", "/")
if not INGRESS_URL_BASE.endswith("/"):
    INGRESS_URL_BASE += "/"

current_config = {
    "main_sensor_id": (os.getenv("MAIN_SENSOR", "").strip() or None),
}

refquery_instance = None
model_bundles = []


async def maybe_await(value):
    return await value if inspect.isawaitable(value) else value


def _load_addon_options() -> Dict[str, Any]:
    if not os.path.exists(ADDON_OPTIONS_PATH):
        return {}

    try:
        with open(ADDON_OPTIONS_PATH, "r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        print(f"Error reading add-on options from {ADDON_OPTIONS_PATH}: {exc}")
        return {}


def get_training_server_url() -> str:
    options = _load_addon_options()
    option_url = str(options.get("training_server_url") or "").strip()
    if option_url:
        return option_url
    return TRAINING_SERVER_URL


def get_training_server_api_key() -> Optional[str]:
    options = _load_addon_options()
    option_api_key = str(options.get("training_server_api_key") or "").strip()
    if option_api_key:
        return option_api_key
    return TRAINING_SERVER_API_KEY


async def history_fetcher(start_dt, end_dt):
    sensor_id = current_config.get("main_sensor_id")
    if not sensor_id:
        return []

    query = HistoryQuery(
        entity_id=sensor_id,
        start_dt=start_dt,
        end_dt=end_dt,
        minimal_response=True,
        max_span_days=7,
    )
    return await fetch_history_points(HA_REST_API_URL, TOKEN, query)


def load_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        print(f"No config file found at {CONFIG_FILE_PATH}. Using default values.")
        return

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as file_handle:
            loaded_config = json.load(file_handle)
        loaded_sensor_id = loaded_config.get("main_sensor_id", current_config["main_sensor_id"])
        current_config["main_sensor_id"] = (str(loaded_sensor_id).strip() if loaded_sensor_id is not None else None) or None
        print(f"Configuration loaded from {CONFIG_FILE_PATH}")
    except json.JSONDecodeError as exc:
        print(f"Error decoding config.json: {exc}. Using current in-memory values.")
    except Exception as exc:
        print(f"Error reading config.json: {exc}. Using current in-memory values.")


def save_config(main_sensor_id):
    current_config["main_sensor_id"] = (str(main_sensor_id).strip() if main_sensor_id is not None else None) or None
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as file_handle:
            json.dump(current_config, file_handle, indent=2)
        print(f"Configuration saved to {CONFIG_FILE_PATH}")
    except Exception as exc:
        print(f"Error saving configuration to {CONFIG_FILE_PATH}: {exc}")


def reload_algorithm_config():
    global refquery_instance
    global model_bundles

    try:
        renamed = rename_bundle_models_dir(MODELS_ROOT, "nilm_online_v1", "online_v1")
        if renamed:
            print("Renamed saved models bundle 'nilm_online_v1' to 'online_v1'.")

        model_bundles = discover_model_bundles(INFERENCE_ROOT)
        default_online_bundle = get_latest_bundle_for_mode(model_bundles, "online")
        migrated = migrate_legacy_models(
            legacy_embeddings_dir=LEGACY_EMBEDDINGS_DIR,
            models_root=MODELS_ROOT,
            default_bundle_id=default_online_bundle.bundle_id if default_online_bundle else None,
        )
        if migrated:
            print(f"Migrated {migrated} legacy model files into bundle-aware storage.")

        refquery_instance = MultiBundleOnlineRuntime(
            bundles=model_bundles,
            models_root=MODELS_ROOT,
            num_threads=2,
            history_fetcher=history_fetcher,
            top_k=None,
        )
        print("Algorithm configuration reloaded successfully.")
    except Exception as exc:
        print(f"ERROR: Failed to initialize RefQuery disaggregator: {exc}")
        refquery_instance = None
