from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

import aiohttp


def _unwrap_supervisor_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


async def supervisor_get_json(base_url: str, token: Optional[str], path: str, timeout_s: float = 5.0) -> Any:
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN is not available.")

    timeout = aiohttp.ClientTimeout(total=timeout_s, connect=5, sock_read=timeout_s)
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Supervisor API {path} failed HTTP {resp.status}: {text[:300]}")
            try:
                payload = await resp.json()
            except Exception as exc:
                raise RuntimeError(f"Supervisor API {path} returned non-JSON: {text[:200]}") from exc
            return _unwrap_supervisor_payload(payload)


def _is_training_server_slug(slug: str) -> bool:
    normalized = (slug or "").strip().lower()
    return normalized == "nilm_training_server" or normalized.endswith("_nilm_training_server")


async def discover_training_server_addon(base_url: str, token: Optional[str], timeout_s: float = 5.0) -> Dict[str, Any]:
    try:
        payload = await supervisor_get_json(base_url, token, "/addons", timeout_s=timeout_s)
        addons = payload.get("addons") if isinstance(payload, dict) else None
        if not isinstance(addons, list):
            raise RuntimeError("Supervisor API /addons returned an unexpected payload.")

        candidates = [addon for addon in addons if isinstance(addon, dict) and _is_training_server_slug(str(addon.get("slug") or ""))]
        if not candidates:
            return {
                "ok": False,
                "installed": False,
                "started": False,
                "state": "not_installed",
                "message": "NILM Training Server add-on is not installed.",
            }

        candidates.sort(key=lambda addon: 0 if str(addon.get("state") or "").lower() == "started" else 1)
        selected = candidates[0]
        selected_slug = str(selected.get("slug") or "").strip()
        info = await supervisor_get_json(
            base_url,
            token,
            f"/addons/{quote(selected_slug, safe='')}/info",
            timeout_s=timeout_s,
        )
        if not isinstance(info, dict):
            raise RuntimeError("Supervisor API /addons/<addon>/info returned an unexpected payload.")

        hostname = str(info.get("hostname") or "").strip()
        state = str(info.get("state") or selected.get("state") or "").strip().lower()
        training_server_url = f"http://{hostname}:8080/train" if hostname else ""

        if state != "started":
            return {
                "ok": False,
                "installed": True,
                "started": False,
                "state": "stopped",
                "slug": selected_slug,
                "hostname": hostname,
                "training_server_url": training_server_url,
                "message": "NILM Training Server add-on is installed but not started.",
            }

        if not hostname:
            return {
                "ok": False,
                "installed": True,
                "started": True,
                "state": "missing_hostname",
                "slug": selected_slug,
                "training_server_url": "",
                "message": "NILM Training Server add-on is started, but its hostname is not available.",
            }

        return {
            "ok": True,
            "installed": True,
            "started": True,
            "state": "started",
            "slug": selected_slug,
            "hostname": hostname,
            "training_server_url": training_server_url,
            "message": "NILM Training Server add-on was detected automatically. Select it and press Save to use it.",
        }
    except Exception as exc:
        message = str(exc)
        if "HTTP 403" in message or "403: Forbidden" in message:
            message = (
                "Supervisor denied add-on discovery (HTTP 403). "
                "Rebuild the NILM add-on with hassio_role: manager, then retry autodetect."
            )
        return {
            "ok": False,
            "installed": False,
            "started": False,
            "state": "supervisor_error",
            "message": message,
        }
