import asyncio
import json
import os
import signal
import time
from datetime import datetime, timezone

import aiohttp
from aiohttp import web
import websockets

import app_state
from embedding_store import save_embedding_npy
from routes_config import register_config_routes
from routes_ha import register_ha_routes
from routes_models import register_model_routes
from routes_training import register_training_routes
from training_server_service import TrainingServerServiceManager


running = True


def shutdown_handler(sig, frame):
    global running
    print("Received shutdown signal")
    running = False


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


def _slug(value: str) -> str:
    return value.replace(" ", "_").replace("-", "_").lower()


async def publish_disaggregation_dl(
    total_power: float,
    dl_result,
    timestamp: datetime,
    duration=None,
):
    if not dl_result or not isinstance(dl_result, dict):
        return

    appliances = dl_result.get("appliances") or {}
    if not isinstance(appliances, dict):
        return

    prediction_target_dt = datetime.fromtimestamp(
        float(dl_result.get("timestamp", timestamp.timestamp())),
        tz=timezone.utc,
    )
    window_end_dt = datetime.fromtimestamp(
        float(dl_result.get("window_end_timestamp", timestamp.timestamp())),
        tz=timezone.utc,
    )
    raw_sample_dt = datetime.fromtimestamp(
        float(dl_result.get("raw_timestamp", timestamp.timestamp())),
        tz=timezone.utc,
    )
    prediction_delay_s = float(dl_result.get("prediction_delay_s", 0.0) or 0.0)
    pred_idx = dl_result.get("pred_idx")

    headers = {
        "Authorization": f"Bearer {app_state.TOKEN}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        for appliance_name, values in appliances.items():
            try:
                power = float(values.get("power"))
                onoff = float(values.get("onoff"))
            except Exception:
                continue

            display_name = str(values.get("appliance_name") or appliance_name)
            bundle_id = str(values.get("bundle_id") or "").strip()
            bundle_label = f" [{bundle_id}]" if bundle_id else ""
            slug = _slug(f"{display_name}_{bundle_id}" if bundle_id else display_name)
            appliance_prediction_target_dt = datetime.fromtimestamp(
                float(values.get("timestamp", prediction_target_dt.timestamp())),
                tz=timezone.utc,
            )
            appliance_window_end_dt = datetime.fromtimestamp(
                float(values.get("window_end_timestamp", window_end_dt.timestamp())),
                tz=timezone.utc,
            )
            appliance_raw_sample_dt = datetime.fromtimestamp(
                float(values.get("raw_timestamp", raw_sample_dt.timestamp())),
                tz=timezone.utc,
            )
            appliance_prediction_delay_s = float(values.get("prediction_delay_s", prediction_delay_s) or 0.0)
            appliance_pred_idx = values.get("pred_idx", pred_idx)
            power_entity_id = f"sensor.nilm_{slug}_power"
            power_data = {
                "state": round(power, 1),
                "attributes": {
                    "unit_of_measurement": "W",
                    "device_class": "power",
                    "state_class": "measurement",
                    "friendly_name": f"NILM {display_name.replace('_', ' ').title()} Power{bundle_label}",
                    "last_updated": timestamp.isoformat(),
                    "prediction_target_time": appliance_prediction_target_dt.isoformat(),
                    "window_end_time": appliance_window_end_dt.isoformat(),
                    "raw_sample_time": appliance_raw_sample_dt.isoformat(),
                    "prediction_delay_s": round(appliance_prediction_delay_s, 3),
                    "pred_idx": appliance_pred_idx,
                    "bundle_id": bundle_id or None,
                    "icon": "mdi:power-socket-eu",
                    "source": "dl",
                },
            }
            try:
                async with session.post(f"{app_state.HA_REST_API_URL}/states/{power_entity_id}", headers=headers, json=power_data) as response:
                    if response.status not in [200, 201]:
                        response_text = await response.text()
                        print(f"Error updating {power_entity_id} via REST API: {response.status} - {response_text}")
            except Exception as exc:
                print(f"Exception during REST API call for {power_entity_id}: {exc}")

            is_on = onoff >= 0.5
            on_entity_id = f"binary_sensor.nilm_{slug}_on"
            on_data = {
                "state": "on" if is_on else "off",
                "attributes": {
                    "friendly_name": f"NILM {display_name.replace('_', ' ').title()} On/Off{bundle_label}",
                    "last_updated": timestamp.isoformat(),
                    "prediction_target_time": appliance_prediction_target_dt.isoformat(),
                    "window_end_time": appliance_window_end_dt.isoformat(),
                    "raw_sample_time": appliance_raw_sample_dt.isoformat(),
                    "prediction_delay_s": round(appliance_prediction_delay_s, 3),
                    "pred_idx": appliance_pred_idx,
                    "bundle_id": bundle_id or None,
                    "icon": "mdi:toggle-switch" if is_on else "mdi:toggle-switch-off",
                    "source": "dl",
                    "onoff_score": round(onoff, 4),
                },
            }
            try:
                async with session.post(f"{app_state.HA_REST_API_URL}/states/{on_entity_id}", headers=headers, json=on_data) as response:
                    if response.status not in [200, 201]:
                        response_text = await response.text()
                        print(f"Error updating {on_entity_id} via REST API: {response.status} - {response_text}")
            except Exception as exc:
                print(f"Exception during REST API call for {on_entity_id}: {exc}")

        if duration is not None:
            duration_entity_id = "sensor.nilm_disaggregation_duration"
            duration_data = {
                "state": round(float(duration), 3),
                "attributes": {
                    "unit_of_measurement": "s",
                    "device_class": "duration",
                    "state_class": "measurement",
                    "friendly_name": "NILM Disaggregation Duration",
                    "last_updated": timestamp.isoformat(),
                    "prediction_target_time": prediction_target_dt.isoformat(),
                    "window_end_time": window_end_dt.isoformat(),
                    "raw_sample_time": raw_sample_dt.isoformat(),
                    "prediction_delay_s": round(prediction_delay_s, 3),
                    "pred_idx": pred_idx,
                    "icon": "mdi:timer-outline",
                    "source": "dl",
                },
            }
            try:
                async with session.post(f"{app_state.HA_REST_API_URL}/states/{duration_entity_id}", headers=headers, json=duration_data) as response:
                    if response.status not in [200, 201]:
                        response_text = await response.text()
                        print(f"Error updating {duration_entity_id} via REST API: {response.status} - {response_text}")
            except Exception as exc:
                print(f"Exception during REST API call for {duration_entity_id}: {exc}")


async def retry_websocket_connection(url, max_retries=10, initial_delay=1):
    for attempt in range(max_retries):
        try:
            print(f"Attempting WebSocket connection to {url} (attempt {attempt + 1}/{max_retries})...")
            websocket = await websockets.connect(url)
            print("WebSocket connection established.")
            return websocket
        except Exception as exc:
            delay = initial_delay * (2 ** attempt)
            print(f"WebSocket connection failed: {exc}. Retrying in {delay:.1f} seconds...")
            await asyncio.sleep(delay)
    raise ConnectionRefusedError(f"Failed to establish WebSocket connection to {url} after {max_retries} attempts.")


def build_web_app():
    app = web.Application(client_max_size=50 * 1024**2)
    app["training_server_manager"] = TrainingServerServiceManager(
        jobs_dir="/data/training_jobs",
        models_root=app_state.MODELS_ROOT,
        training_server_url=app_state.TRAINING_SERVER_URL,
        training_server_api_key=app_state.TRAINING_SERVER_API_KEY,
        save_embedding_npy_fn=save_embedding_npy,
        reload_algorithm_fn=app_state.reload_algorithm_config,
    )

    app.router.add_get(
        app_state.INGRESS_URL_BASE,
        lambda request: web.FileResponse(os.path.join("/app/www", "index.html")),
    )
    if app_state.INGRESS_URL_BASE != "/":
        app.router.add_get(
            app_state.INGRESS_URL_BASE.rstrip("/"),
            lambda request: web.FileResponse(os.path.join("/app/www", "index.html")),
        )

    app.router.add_static(app_state.INGRESS_URL_BASE + "components/", path="/app/www/components")
    app.router.add_static(app_state.INGRESS_URL_BASE + "js/", path="/app/www/js")
    app.router.add_static(app_state.INGRESS_URL_BASE + "vendor/", path="/app/www/vendor")

    register_config_routes(app, app_state.INGRESS_URL_BASE)
    register_model_routes(app, app_state.INGRESS_URL_BASE)
    register_ha_routes(app, app_state.INGRESS_URL_BASE)
    register_training_routes(app, app_state.INGRESS_URL_BASE)
    return app


async def run_live_loop():
    sensor_to_monitor = app_state.current_config["main_sensor_id"]
    websocket = None
    backoff = 1

    while running:
        try:
            websocket = await retry_websocket_connection(app_state.HA_WS_URL)

            initial_auth_reply = json.loads(await websocket.recv())
            print(f"Received initial server message: {initial_auth_reply}")
            if initial_auth_reply.get("type") != "auth_required":
                raise RuntimeError(
                    f"Expected 'auth_required' from HA, but got: {initial_auth_reply.get('type')}. Full reply: {initial_auth_reply}"
                )

            await websocket.send(json.dumps({"type": "auth", "access_token": app_state.TOKEN}))
            auth_result = json.loads(await websocket.recv())
            print(f"Received authentication result: {auth_result}")

            if auth_result.get("type") == "auth_ok":
                print("Home Assistant WebSocket authentication successful!")
            elif auth_result.get("type") == "auth_invalid":
                raise RuntimeError(f"HA WebSocket authentication failed: {auth_result.get('message', 'Invalid token provided.')}")
            else:
                raise RuntimeError(
                    f"Unexpected WebSocket authentication response type: {auth_result.get('type')}. Full reply: {auth_result}"
                )

            await websocket.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
            print(f"Listening to {sensor_to_monitor} via HA WebSocket...")
            backoff = 1

            while running:
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=60)
                except asyncio.TimeoutError:
                    print("No data received in 60s.")
                    if app_state.refquery_instance:
                        now = datetime.now(timezone.utc)
                        start_time = time.perf_counter()
                        dl_disagg = await app_state.refquery_instance.disaggregate_next(0.0, now)
                        dl_dur = time.perf_counter() - start_time
                        try:
                            await publish_disaggregation_dl(0.0, dl_disagg, now, dl_dur)
                        except Exception as pub_err:
                            print(f"Publish error during idle tick: {pub_err}")
                    else:
                        print("NILM instance not available, skipping idle tick.")
                    continue
                except websockets.exceptions.ConnectionClosedOK:
                    print("WebSocket connection closed gracefully.")
                    break

                try:
                    event = json.loads(msg)
                    new_state = event.get("event", {}).get("data", {}).get("new_state")
                    if not new_state or new_state.get("entity_id") != sensor_to_monitor:
                        continue

                    total_power = float(new_state["state"])
                    now = datetime.now(timezone.utc)

                    if app_state.refquery_instance:
                        start_time = time.perf_counter()
                        dl_disagg = await app_state.refquery_instance.disaggregate_next(total_power, now)
                        dl_dur = time.perf_counter() - start_time
                        await publish_disaggregation_dl(total_power, dl_disagg, now, dl_dur)
                        print("NILM duration:", dl_dur)
                    else:
                        print("NILM instance not available, skipping disaggregation.")
                except Exception as exc:
                    print(f"Error during loop: {exc}")

        except Exception as err:
            print(f"WebSocket connection error: {err}")
            sleep_s = backoff
            backoff = min(backoff * 2, 60)
            print(f"Reconnecting in {sleep_s}s...")
            await asyncio.sleep(sleep_s)
            continue
        finally:
            if websocket is not None and not websocket.closed:
                print("Closing WebSocket connection gracefully...")
                try:
                    await websocket.close()
                except Exception:
                    pass


async def main():
    print("Main application starting...")
    print(f"DEBUG: SUPERVISOR_TOKEN length: {len(app_state.TOKEN) if app_state.TOKEN else 'None'}")
    if not app_state.TOKEN:
        print("ERROR: SUPERVISOR_TOKEN environment variable is not set!")
        return

    app_state.load_config()
    app_state.reload_algorithm_config()

    app = build_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8099)
    await site.start()
    print("Web server started on port 8099 for Ingress.")

    try:
        await run_live_loop()
    finally:
        print("Shutting down NILM service.")
        await runner.cleanup()
        print("Web server stopped.")


if __name__ == "__main__":
    os.makedirs("/data", exist_ok=True)
    asyncio.run(main())
