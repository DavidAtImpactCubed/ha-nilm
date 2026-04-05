from __future__ import annotations

import asyncio
import gzip
import json
from typing import Any, Dict, Optional, Callable

import aiohttp
from training_server_url import (
    normalize_training_server_url,
    training_server_origin,
    training_server_status_base,
    uses_homeassistant_gateway,
)


class TrainingServerError(RuntimeError):
    pass


def _normalized_training_server_url(training_server_url: str) -> str:
    normalized_url = normalize_training_server_url(training_server_url)
    if not normalized_url or not training_server_origin(normalized_url):
        raise TrainingServerError(f"Invalid TRAINING_SERVER_URL: {training_server_url!r}")
    return normalized_url


def _headers(api_key: Optional[str]) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


async def start_training_job(
    training_server_url: str,
    api_key: Optional[str],
    payload: Dict[str, Any],
    timeout_s: float = 30.0,
) -> Dict[str, Any]:
    training_server_url = _normalized_training_server_url(training_server_url)
    timeout = aiohttp.ClientTimeout(total=timeout_s, connect=10, sock_read=timeout_s)
    payload_text = json.dumps(payload, separators=(",", ":"))
    payload_size_bytes = len(payload_text.encode("utf-8"))
    payload_bytes = payload_text.encode("utf-8")
    compressed_payload = gzip.compress(payload_bytes, compresslevel=6)
    compressed_size_bytes = len(compressed_payload)
    n_embeddings = len(payload.get("embeddings") or []) if isinstance(payload, dict) else 0
    embedding_dim = 0
    if isinstance(payload, dict) and isinstance(payload.get("embeddings"), list) and payload["embeddings"]:
        first_embedding = payload["embeddings"][0]
        if isinstance(first_embedding, list):
            embedding_dim = len(first_embedding)

    print(
        f"Training server POST starting url={training_server_url} "
        f"payload_bytes={payload_size_bytes} compressed_bytes={compressed_size_bytes} "
        f"n_embeddings={n_embeddings} embedding_dim={embedding_dim}",
        flush=True,
    )

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = _headers(api_key)
            headers["Content-Encoding"] = "gzip"
            async with session.post(training_server_url, headers=headers, data=compressed_payload) as resp:
                text = await resp.text()
                if resp.status not in (200, 202):
                    raise TrainingServerError(f"Training server start failed HTTP {resp.status}: {text[:800]}")

                try:
                    data = json.loads(text) if text else {}
                except Exception:
                    raise TrainingServerError(f"Training server start returned non-JSON: {text[:200]}")

                if not isinstance(data, dict) or not data.get("job_id"):
                    raise TrainingServerError(f"Training server start missing job_id. Response: {data!r}")

                print(
                    f"Training server POST accepted url={training_server_url} "
                    f"payload_bytes={payload_size_bytes} compressed_bytes={compressed_size_bytes} "
                    f"job_id={data.get('job_id')}",
                    flush=True,
                )
                return data

    except asyncio.TimeoutError as e:
        raise TrainingServerError(
            f"Training server start timed out after sending payload_bytes={payload_size_bytes} "
            f"compressed_bytes={compressed_size_bytes}"
        ) from e
    except aiohttp.ClientError as e:
        os_error = getattr(e, "os_error", None)
        os_error_text = f"{type(os_error).__name__}: {os_error}" if os_error is not None else "None"
        raise TrainingServerError(
            f"Training server start request error: {e} "
            f"(url={training_server_url}, payload_bytes={payload_size_bytes}, "
            f"compressed_bytes={compressed_size_bytes}, "
            f"n_embeddings={n_embeddings}, embedding_dim={embedding_dim}, "
            f"client_error_type={type(e).__name__}, os_error={os_error_text})"
        ) from e


async def probe_training_server_connection(
    training_server_url: str,
    api_key: Optional[str],
    timeout_s: float = 8.0,
) -> Dict[str, Any]:
    if not training_server_url:
        return {
            "ok": False,
            "state": "missing_config",
            "message": "Training server URL is not configured.",
        }

    try:
        normalized_url = _normalized_training_server_url(training_server_url)
    except TrainingServerError as e:
        return {
            "ok": False,
            "state": "invalid_config",
            "message": str(e),
        }

    timeout = aiohttp.ClientTimeout(total=timeout_s, connect=5, sock_read=5)
    origin = training_server_origin(normalized_url)
    candidates = [normalized_url]
    if origin and origin != normalized_url:
        candidates.append(origin)
    last_error = None

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for url in candidates:
                try:
                    async with session.get(url, headers=_headers(api_key)) as resp:
                        text = await resp.text()
                        if resp.status in (401, 403):
                            return {
                                "ok": False,
                                "state": "auth_error",
                                "message": f"Training server is reachable, but authorization failed (HTTP {resp.status}). Check the API key.",
                                "http_status": resp.status,
                                "checked_url": url,
                            }
                        if resp.status < 500:
                            message = "Training server connection looks ready."
                            if resp.status >= 400:
                                message = f"Training server is reachable (HTTP {resp.status})."
                            state = "ready"
                            if uses_homeassistant_gateway(normalized_url):
                                state = "proxy_route"
                                message = (
                                    "Training server is reachable through the Home Assistant gateway, "
                                    "but direct app hostnames are more reliable for training uploads. "
                                    "Open the NILM Training Server Web UI or logs and copy the displayed training_server_url."
                                )
                            return {
                                "ok": True,
                                "state": state,
                                "message": message,
                                "http_status": resp.status,
                                "configured_url": training_server_url,
                                "normalized_url": normalized_url,
                                "checked_url": url,
                                "response_excerpt": text[:200],
                            }
                        last_error = f"Training server responded with HTTP {resp.status}."
                except asyncio.TimeoutError:
                    last_error = f"Training server request to {url} timed out."
                except aiohttp.ClientError as e:
                    last_error = f"Training server request to {url} failed: {e}"

    except asyncio.TimeoutError:
        last_error = "Training server connection timed out."
    except aiohttp.ClientError as e:
        last_error = f"Training server request error: {e}"

    return {
        "ok": False,
        "state": "unreachable",
        "message": last_error or "Training server connection could not be established.",
    }


async def fetch_training_status(
    training_server_url: str,
    api_key: Optional[str],
    job_id: str,
    timeout_s: float = 15.0,
) -> Dict[str, Any]:
    status_base = training_server_status_base(_normalized_training_server_url(training_server_url))
    status_url = f"{status_base}/{job_id}"
    timeout = aiohttp.ClientTimeout(total=timeout_s, connect=10, sock_read=10)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(status_url, headers=_headers(api_key)) as resp:
                text = await resp.text()
                if resp.status == 404:
                    raise TrainingServerError(f"Training server job_id not found: {job_id}")
                if resp.status >= 400:
                    raise TrainingServerError(f"Training server status HTTP {resp.status}: {text[:500]}")

                try:
                    st = json.loads(text) if text else {}
                except Exception:
                    raise TrainingServerError(f"Training server status non-JSON: {text[:200]}")

                if not isinstance(st, dict):
                    raise TrainingServerError(f"Training server status invalid JSON shape: {type(st)}")

                return st

    except asyncio.TimeoutError as e:
        raise TrainingServerError("Training server status timed out") from e
    except aiohttp.ClientError as e:
        raise TrainingServerError(f"Training server status request error: {e}") from e


async def poll_training_result(
    training_server_url: str,
    api_key: Optional[str],
    job_id: str,
    poll_every_s: float = 2.0,
    max_wait_s: float = 1800.0,
    on_status: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    Polls /train/{job_id} until status is 'done', then fetches /train/{job_id}/result.
    
    IMPROVEMENTS:
    1. Transient Error Tolerance: Does not crash if a single status check fails.
    2. Propagation Delay Handling: Retries the /result fetch if the training server reports 
       'done' but the file isn't immediately accessible (e.g., 404/500 errors).
    3. Small Payload Optimization: Ideal for 128-dim vectors.
    """
    status_base = training_server_status_base(_normalized_training_server_url(training_server_url))
    result_url = f"{status_base}/{job_id}/result"
    deadline = asyncio.get_running_loop().time() + max_wait_s

    while asyncio.get_running_loop().time() < deadline:
        try:
            # 1. Fetch current status from the training server
            st = await fetch_training_status(training_server_url, api_key, job_id)
            
            # Bubble up the status to the UI (via the service/database)
            if on_status:
                try:
                    on_status(st)
                except Exception:
                    pass # Don't let a logging error kill the polling loop

            status = (st.get("status") or "").lower()

            # 2. SUCCESS CASE: Training server is finished
            if status == "done":
                # The training server finished fast, but the result file might need a moment 
                # to propagate. We try up to 5 times (10 seconds total).
                for attempt in range(5):
                    try:
                        # Use a generous timeout for the download, even for small vectors
                        timeout = aiohttp.ClientTimeout(total=60, connect=10)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            async with session.get(result_url, headers=_headers(api_key)) as resp:
                                if resp.status == 200:
                                    # SUCCESS! We got our 128-number vector.
                                    return await resp.json()
                                
                                # If 404 or 5xx, the training server is still finalizing
                                # the result file even though the job state is 'done'.
                                print(f"Result URL returned {resp.status}, retrying in 2s...")
                    except Exception as e:
                        print(f"Attempt {attempt+1} to fetch result failed: {e}")
                    
                    await asyncio.sleep(2)
                
                raise TrainingServerError("Training server reported 'done' but result was unreachable after retries.")

            # 3. ERROR CASE: Training server failed the training task
            if status == "error":
                err_msg = st.get('message') or st.get('error') or 'unknown training server error'
                raise TrainingServerError(f"Training server training failed: {err_msg}")

        except TrainingServerError as ce:
            # If fetch_training_status raises an error (e.g., temporary 502),
            # we don't kill the whole loop. We wait and try again.
            if "not found" in str(ce).lower():
                raise ce # If the job is truly gone (404), stop polling.
            print(f"Transient polling error: {ce}. Retrying...")

        # Wait before the next poll interval
        await asyncio.sleep(poll_every_s)

    # 4. TIMEOUT CASE: Deadline reached
    raise TrainingServerError(f"Job {job_id} timed out after {max_wait_s}s without reaching 'done' state.")
