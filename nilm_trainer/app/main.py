from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional
import os

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from app.model_registry import discover_server_bundles, get_bundle_by_id, get_latest_bundle_for_mode
from app.trainer import train_ref_embedding

app = FastAPI()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    content_length = request.headers.get("content-length", "unknown")
    client_host = request.client.host if request.client else "unknown"
    print(
        f"HTTP request started method={request.method} path={request.url.path} "
        f"client={client_host} content_length={content_length}",
        flush=True,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        print(
            f"HTTP request failed method={request.method} path={request.url.path} "
            f"client={client_host} content_length={content_length} error={exc}",
            flush=True,
        )
        raise

    print(
        f"HTTP request completed method={request.method} path={request.url.path} "
        f"status={response.status_code} client={client_host} content_length={content_length}",
        flush=True,
    )
    return response

# NOTE: single-worker only. For multi-worker, use Redis/DB.
JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = asyncio.Lock()
VERSION = "1.0.0"
BUNDLES_ROOT = "/app/bundles"
SERVER_BUNDLES = discover_server_bundles(BUNDLES_ROOT)
# --------------------------
# SERVER-OWNED TRAINING CONFIG (client cannot change)
# --------------------------
SERVER_TRAINING = {
    "epochs": 200,
    "lr": 0.01,
    "batch_size": 1024,
    "seed": 0,
    "patience": 5,
    "min_delta": 1e-4,
}


class TrainPayload(BaseModel):
    appliance_name: str
    appliance_type: str = ""
    embeddings: List[List[float]]
    targets_on: List[int]
    targets_power: Optional[List[float]] = None
    supervision_mode: Optional[str] = None
    appliance_sensor_id: Optional[str] = None
    bundle_id: Optional[str] = None
    bundle_mode: Optional[str] = None
    bundle_version: Optional[int] = None
    settings: Dict[str, Any]

@app.get("/version")
def version():
    return VERSION

@app.post("/train", status_code=202)
async def start_train(payload: TrainPayload, request: Request):
    request_id = uuid.uuid4().hex[:8]
    job_id = uuid.uuid4().hex

    n_emb = len(payload.embeddings)
    n_y = len(payload.targets_on)

    if n_emb == 0 or n_y == 0 or n_emb != n_y:
        raise HTTPException(status_code=400, detail="Invalid dataset sizes (embeddings/targets).")
    if payload.targets_power is not None and len(payload.targets_power) != n_emb:
        raise HTTPException(status_code=400, detail="Invalid dataset sizes (embeddings/targets_power).")

    selected_bundle = None
    if payload.bundle_id:
        selected_bundle = get_bundle_by_id(SERVER_BUNDLES, payload.bundle_id)
        if selected_bundle is None:
            raise HTTPException(status_code=400, detail=f"Unknown bundle_id: {payload.bundle_id}")
    else:
        selected_bundle = get_latest_bundle_for_mode(SERVER_BUNDLES, payload.bundle_mode or "online")
        if selected_bundle is None:
            raise HTTPException(status_code=400, detail=f"No server bundle available for mode: {payload.bundle_mode or 'online'}")

    # capture loop so thread can safely update progress
    loop = asyncio.get_running_loop()

    now = time.time()
    async with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "queued",  # queued|running|done|error
            "request_id": request_id,
            "created_at": now,
            "started_at": None,
            "updated_at": now,
            "appliance_name": payload.appliance_name,
            "appliance_type": payload.appliance_type,
            "supervision_mode": payload.supervision_mode,
            "bundle_id": selected_bundle.bundle_id,
            "bundle_mode": selected_bundle.mode,
            "bundle_version": selected_bundle.model_version,
            "n_samples": n_emb,
            "progress": {
                "phase": "queued",
                "epoch": 0,
                "total_epochs": int(SERVER_TRAINING["epochs"]),
                "loss": None,
                "min_loss": None,
            },
        }

    client_host = request.client.host if request.client else "unknown"
    print(
        f"[{request_id}] /train accepted job_id={job_id} from {client_host} "
        f"n={n_emb} bundle={selected_bundle.bundle_id} "
        f"(epochs={SERVER_TRAINING['epochs']} bs={SERVER_TRAINING['batch_size']})",
        flush=True,
    )

    asyncio.create_task(_run_training_job(job_id, payload, selected_bundle, request_id, loop))
    return {"status": "accepted", "job_id": job_id, "request_id": request_id}


@app.get("/train/{job_id}", status_code=200)
async def train_status(job_id: str):
    async with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job_id not found")

    return {
        "job_id": job_id,
        "status": job["status"],
        "request_id": job.get("request_id"),
        "message": job.get("message"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "updated_at": job.get("updated_at"),
        "n_samples": job.get("n_samples"),
        "progress": job.get("progress"),
    }


@app.get("/train/{job_id}/result", status_code=200)
async def train_result(job_id: str):
    async with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "job_id not found")

    if job["status"] == "error":
        raise HTTPException(500, job.get("message", "training failed"))
    if job["status"] != "done":
        raise HTTPException(409, f"not ready ({job['status']})")

    return {
        "status": "success",
        "job_id": job_id,
        "appliance_name": job["result"]["appliance_name"],
        "embedding": job["result"]["embedding"],
        "embedding_dim": job["result"]["embedding_dim"],
        "bundle_id": job["result"].get("bundle_id"),
        "bundle_mode": job["result"].get("bundle_mode"),
        "bundle_version": job["result"].get("bundle_version"),
        "appliance_params": job["result"].get("appliance_params", {}),
        "stats": job["result"]["stats"],
    }


async def _run_training_job(job_id: str, payload: TrainPayload, selected_bundle, request_id: str, loop: asyncio.AbstractEventLoop):
    async with JOBS_LOCK:
        j = JOBS.get(job_id)
        if not j:
            return
        j["status"] = "running"
        j["started_at"] = time.time()
        j["updated_at"] = time.time()
        j["progress"]["phase"] = "running"

    def push_progress(p: Dict[str, Any]) -> None:
        """Called from training thread; schedules an async merge into JOBS."""
        async def _merge():
            async with JOBS_LOCK:
                jj = JOBS.get(job_id)
                if not jj:
                    return
                jj["updated_at"] = time.time()
                jj["progress"] = {**jj.get("progress", {}), **p}

        loop.call_soon_threadsafe(lambda: asyncio.create_task(_merge()))

    try:
        embedding, stats, appliance_params = await asyncio.to_thread(
            train_ref_embedding,
            query_embeddings=payload.embeddings,
            targets_on=payload.targets_on,
            targets_power=payload.targets_power,
            settings=payload.settings,
            head_model_path=selected_bundle.head_model_path,
            epochs=int(SERVER_TRAINING["epochs"]),
            lr=float(SERVER_TRAINING["lr"]),
            batch_size=int(SERVER_TRAINING["batch_size"]),
            seed=int(SERVER_TRAINING["seed"]),
            patience=int(SERVER_TRAINING["patience"]),
            min_delta=float(SERVER_TRAINING["min_delta"]),
            on_progress=push_progress,
        )

        async with JOBS_LOCK:
            jj = JOBS.get(job_id)
            if not jj:
                return
            jj["status"] = "done"
            jj["updated_at"] = time.time()
            jj["progress"] = {
                **jj.get("progress", {}),
                "phase": "done",
                "epoch": stats.get("epochs_ran"),
                "total_epochs": stats.get("epochs_requested"),
                "loss": stats.get("final_loss"),
                "min_loss": stats.get("min_loss"),
                "cls_loss": stats.get("final_cls_loss"),
                "reg_loss": stats.get("final_reg_loss"),
                "fine_tune_target": stats.get("fine_tune_target"),
            }
            jj["result"] = {
                "appliance_name": payload.appliance_name,
                "bundle_id": selected_bundle.bundle_id,
                "bundle_mode": selected_bundle.mode,
                "bundle_version": selected_bundle.model_version,
                "embedding": embedding,
                "embedding_dim": len(embedding),
                "appliance_params": appliance_params,
                "stats": stats,
            }

        print(f"[{request_id}] job_id={job_id} DONE embedding_dim={len(embedding)}", flush=True)

    except Exception as e:
        async with JOBS_LOCK:
            jj = JOBS.get(job_id)
            if not jj:
                return
            jj["status"] = "error"
            jj["updated_at"] = time.time()
            jj["message"] = str(e)
            jj["progress"] = {**jj.get("progress", {}), "phase": "error"}

        print(f"[{request_id}] job_id={job_id} ERROR: {e}", flush=True)
