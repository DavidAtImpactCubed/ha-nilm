from __future__ import annotations

import os
import json
import uuid
import asyncio
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import inspect

import app_state
from training_server_client import (
    TrainingServerError,
    probe_training_server_connection,
    start_training_job,
    poll_training_result,
    fetch_training_status,
)
from embedding_store import bundle_models_dir, load_embedding_metadata
from training_payload import training_server_payload_from_prepared, summarize_training_server_payload
from embedding_store import save_embedding_metadata


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def _percent_from_progress(p: Optional[Dict[str, Any]]) -> Optional[int]:
    if not isinstance(p, dict):
        return None
    e = p.get("epoch")
    t = p.get("total_epochs")
    try:
        e = int(e) if e is not None else None
        t = int(t) if t is not None else None
        if not e or not t or t <= 0:
            return None
        return max(0, min(100, int(round((e / t) * 100))))
    except Exception:
        return None


class TrainingServerServiceManager:
    def __init__(
        self,
        *,
        jobs_dir: str,
        models_root: str,
        training_server_url: str,
        training_server_api_key: Optional[str],
        save_embedding_npy_fn,
        reload_algorithm_fn=None,
    ):
        self.jobs_dir = jobs_dir
        self.models_root = models_root
        self.training_server_url = training_server_url
        self.training_server_api_key = training_server_api_key
        self.save_embedding_npy = save_embedding_npy_fn
        self.reload_algorithm = reload_algorithm_fn

        os.makedirs(self.jobs_dir, exist_ok=True)

        # Prevent concurrent read/write races between UI status calls and poller tasks
        self._io_lock = asyncio.Lock()

    async def _maybe_reload_algorithm(self) -> None:
        if self.reload_algorithm is None:
            return
        result = self.reload_algorithm()
        if inspect.isawaitable(result):
            await result

    def _job_path(self, job_id: str) -> str:
        return os.path.join(self.jobs_dir, f"{job_id}.json")

    def _read_unlocked(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    async def _read(self, job_id: str) -> Dict[str, Any]:
        path = self._job_path(job_id)
        async with self._io_lock:
            return self._read_unlocked(path)

    async def _write(self, job_id: str, data: Dict[str, Any]) -> None:
        path = self._job_path(job_id)
        async with self._io_lock:
            _atomic_write_json(path, data)

    async def _patch_job(self, job_id: str, patch: Dict[str, Any]) -> None:
        path = self._job_path(job_id)
        async with self._io_lock:
            data = self._read_unlocked(path)
            data.setdefault("_job", {})
            data["_job"] = {**data["_job"], **patch}
            _atomic_write_json(path, data)

    async def create_job(self, prepared: Dict[str, Any]) -> str:
        job_id = uuid.uuid4().hex
        prepared["_job"] = {
            "job_id": job_id,
            "state": "prepared",
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "training_server_job_id": None,
            "saved_path": None,
            "embedding_dim": None,
            "error": None,
            # progress fields your UI can show
            "progress": {
                "phase": "prepared",
                "epoch": 0,
                "total_epochs": None,
                "loss": None,
                "min_loss": None,
            },
            "percent": None,
        }
        await self._write(job_id, prepared)
        print(
            f"Created local training job local_job_id={job_id} "
            f"appliance={prepared.get('appliance_name')} bundle_id={prepared.get('bundle_id')} "
            f"n_embeddings={len(prepared.get('embeddings') or [])}",
            flush=True,
        )
        return job_id

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        data = await self._read(job_id)
        j = data.get("_job", {}) or {}
        return {
            "status": "success",
            "job_id": job_id,
            "state": j.get("state", "unknown"),
            "training_server_job_id": j.get("training_server_job_id"),
            "saved_path": j.get("saved_path"),
            "embedding_dim": j.get("embedding_dim"),
            "error": j.get("error"),
            "progress": j.get("progress"),
            "percent": j.get("percent"),
            "training_metrics": j.get("training_metrics"),
            "updated_at": j.get("updated_at"),
        }

    async def get_training_server_connection_status(self) -> Dict[str, Any]:
        url_state = await app_state.resolve_training_server_url_state()
        training_server_url = url_state["effective_training_server_url"]
        if not training_server_url:
            autodetect = url_state.get("autodetect") or {}
            message = "Training server URL is not configured."
            if autodetect.get("ok") and autodetect.get("training_server_url"):
                message = (
                    "Training server URL is not saved yet. "
                    "Press Auto-detect, review the detected URL, then press Save."
                )
            elif autodetect.get("message"):
                message = f"{message} {autodetect.get('message')}"
            return {
                "status": "success",
                "ok": False,
                "state": "missing_config",
                "message": message,
                "training_server_url": "",
                **url_state,
            }
        training_server_api_key = app_state.get_training_server_api_key()
        result = await probe_training_server_connection(
            training_server_url=training_server_url,
            api_key=training_server_api_key,
            timeout_s=8.0,
        )
        return {
            "status": "success",
            "training_server_url": training_server_url,
            **url_state,
            **result,
        }

    async def detect_training_server(self) -> Dict[str, Any]:
        url_state = await app_state.resolve_training_server_url_state()
        autodetect = url_state.get("autodetect") or {}
        return {
            "status": "success",
            **autodetect,
            "configured_training_server_url": url_state.get("configured_training_server_url", ""),
            "effective_training_server_url": url_state.get("effective_training_server_url", ""),
            "training_server_url_source": url_state.get("training_server_url_source"),
        }

    async def start_send(self, job_id: str) -> Dict[str, Any]:
        prepared = await self._read(job_id)
        training_server_payload = training_server_payload_from_prepared(prepared)
        payload_summary = summarize_training_server_payload(training_server_payload)
        url_state = await app_state.resolve_training_server_url_state()
        training_server_url = url_state["effective_training_server_url"]
        training_server_api_key = app_state.get_training_server_api_key()
        print(
            f"Starting training server send for local_job_id={job_id} "
            f"url={training_server_url}: {json.dumps(payload_summary, sort_keys=True)}",
            flush=True,
        )

        start = await start_training_job(
            training_server_url=training_server_url,
            api_key=training_server_api_key,
            payload=training_server_payload,
            timeout_s=1120.0,
        )

        training_server_job_id = start["job_id"]
        print(
            f"Training server accepted local_job_id={job_id} training_server_job_id={training_server_job_id}",
            flush=True,
        )

        await self._patch_job(job_id, {
            "training_server_job_id": training_server_job_id,
            "training_server_url": training_server_url,
            "training_server_url_source": url_state.get("training_server_url_source"),
            "state": "training_server_queued",
            "updated_at": _utc_now_iso(),
            "error": None,
            "progress": {
                "phase": "queued",
                "epoch": 0,
                "total_epochs": None,
                "loss": None,
                "min_loss": None,
            },
            "percent": None,
        })

        # background poller updates progress + finalizes
        asyncio.create_task(self._poll_and_finalize(job_id, training_server_job_id, training_server_url, training_server_api_key))

        return {"status": "success", "job_id": job_id, "training_server_job_id": training_server_job_id}

    async def _merge_training_server_status(self, job_id: str, st: Dict[str, Any]) -> None:
        """
        st is the raw JSON from the training server GET /train/{job_id}
        """
        training_server_status = (st.get("status") or "").lower()  # queued|running|done|error
        progress = st.get("progress")
        percent = _percent_from_progress(progress)

        # Map training server status -> addon state
        if training_server_status == "queued":
            state = "training_server_queued"
        elif training_server_status == "running":
            state = "training_server_running"
        elif training_server_status == "done":
            state = "training_server_done"
        elif training_server_status == "error":
            state = "error"
        else:
            state = "training_server_running"  # fallback

        patch: Dict[str, Any] = {
            "state": state,
            "updated_at": _utc_now_iso(),
        }

        if isinstance(progress, dict):
            patch["progress"] = progress
            patch["percent"] = percent

        if training_server_status == "error":
            patch["error"] = st.get("message") or st.get("error") or "Training server error"

        await self._patch_job(job_id, patch)

    async def _poll_and_finalize(
        self,
        job_id: str,
        training_server_job_id: str,
        training_server_url: str,
        training_server_api_key: Optional[str],
    ) -> None:
        try:
            # 1) Kick off a lightweight status loop to keep progress fresh
            #    (even if poll_training_result sleeps / waits long)
            async def progress_loop():
                while True:
                    st = await fetch_training_status(
                        training_server_url=training_server_url,
                        api_key=training_server_api_key,
                        job_id=training_server_job_id,
                        timeout_s=240.0,
                    )
                    await self._merge_training_server_status(job_id, st)

                    s = (st.get("status") or "").lower()
                    if s in ("done", "error"):
                        return
                    await asyncio.sleep(2.0)

            progress_task = asyncio.create_task(progress_loop())

            # 2) Wait for final result (this returns only when DONE)
            result = await poll_training_result(
                training_server_url=training_server_url,
                api_key=training_server_api_key,
                job_id=training_server_job_id,
                poll_every_s=2.0,
                max_wait_s=1800.0,
            )

            # ensure progress loop stops
            try:
                await progress_task
            except Exception:
                pass

            embedding = result.get("embedding")
            appliance_name = (
                result.get("appliance_name")
                or (await self._read(job_id)).get("appliance_name")
                or (await self._read(job_id)).get("_meta", {}).get("appliance_name")
            )

            if not appliance_name or not isinstance(embedding, list) or not embedding:
                raise RuntimeError("Training server result missing appliance_name/embedding")

            prepared_job = await self._read(job_id)
            bundle_id = str(
                result.get("bundle_id")
                or prepared_job.get("bundle_id")
                or prepared_job.get("_meta", {}).get("bundle_id")
                or ""
            ).strip()
            if not bundle_id:
                raise RuntimeError("Training server result missing bundle_id")

            bundle_dir = bundle_models_dir(self.models_root, bundle_id)
            existing_metadata = load_embedding_metadata(bundle_dir, str(appliance_name)) or {}
            saved_path = self.save_embedding_npy(bundle_dir, str(appliance_name), embedding)
            save_embedding_metadata(
                bundle_dir,
                str(appliance_name),
                {
                    **existing_metadata,
                    "appliance_name": str(appliance_name),
                    "bundle_id": bundle_id,
                    "bundle_mode": prepared_job.get("bundle_mode") or result.get("bundle_mode"),
                    "bundle_version": prepared_job.get("bundle_version"),
                    "saved_path": saved_path,
                    "saved_at": _utc_now_iso(),
                    "stats": prepared_job.get("stats", {}) or {},
                    "supervision_mode": prepared_job.get("supervision_mode"),
                    "appliance_sensor_id": prepared_job.get("appliance_sensor_id"),
                    "job_id": job_id,
                    "training_server_job_id": training_server_job_id,
                    "onoff_threshold": float(result.get("appliance_params", {}).get("onoff_threshold", 0.5)),
                    "power_threshold": float(result.get("appliance_params", {}).get("power_threshold", 0.0)),
                    "onoff_f1": result.get("stats", {}).get("onoff_f1"),
                    "power_f1": result.get("stats", {}).get("power_f1"),
                    "fine_tune_target": result.get("stats", {}).get("fine_tune_target"),
                },
            )
            await self._maybe_reload_algorithm()

            await self._patch_job(job_id, {
                "state": "done",
                "updated_at": _utc_now_iso(),
                "saved_path": saved_path,
                "embedding_dim": len(embedding),
                "error": None,
                "training_metrics": {
                    "onoff_f1": result.get("stats", {}).get("onoff_f1"),
                    "onoff_threshold": result.get("appliance_params", {}).get("onoff_threshold"),
                    "power_f1": result.get("stats", {}).get("power_f1"),
                    "power_threshold": result.get("appliance_params", {}).get("power_threshold"),
                    "fine_tune_target": result.get("stats", {}).get("fine_tune_target"),
                },
                "progress": {
                    "phase": "done",
                    "epoch": len(embedding) and prepared_job.get("_job", {}).get("progress", {}).get("epoch"),
                    "total_epochs": prepared_job.get("_job", {}).get("progress", {}).get("total_epochs"),
                    "loss": prepared_job.get("_job", {}).get("progress", {}).get("loss"),
                    "min_loss": prepared_job.get("_job", {}).get("progress", {}).get("min_loss"),
                },
                "percent": 100,
            })
            print(
                f"Training finalize done local_job_id={job_id} training_server_job_id={training_server_job_id} "
                f"saved_path={saved_path}",
                flush=True,
            )

        except Exception as e:
            print(
                f"Training finalize failed local_job_id={job_id} training_server_job_id={training_server_job_id}: {e}",
                flush=True,
            )
            print(traceback.format_exc(), flush=True)
            await self._patch_job(job_id, {
                "state": "error",
                "updated_at": _utc_now_iso(),
                "error": str(e),
                "progress": {"phase": "error"},
            })
