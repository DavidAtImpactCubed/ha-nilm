from __future__ import annotations

from urllib.parse import urlparse, urlunparse


DEFAULT_TRAINING_SERVER_URL = "http://homeassistant.local:8080/train"


def normalize_training_server_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        return ""

    if "://" not in value:
        value = f"http://{value}"

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value

    path = (parsed.path or "").rstrip("/")
    if not path:
        path = "/train"

    normalized = parsed._replace(path=path, params="", query="", fragment="")
    return urlunparse(normalized)


def training_server_status_base(training_server_url: str) -> str:
    return normalize_training_server_url(training_server_url).rstrip("/")


def training_server_origin(training_server_url: str) -> str:
    parsed = urlparse(normalize_training_server_url(training_server_url))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def is_valid_training_server_url(training_server_url: str) -> bool:
    normalized = normalize_training_server_url(training_server_url)
    if not normalized:
        return False

    parsed = urlparse(normalized)
    return bool(parsed.scheme and parsed.netloc)


def uses_homeassistant_gateway(training_server_url: str) -> bool:
    hostname = (urlparse(normalize_training_server_url(training_server_url)).hostname or "").strip().lower()
    return hostname in {"homeassistant.local", "supervisor", "homeassistant"}
