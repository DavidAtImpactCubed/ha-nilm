import asyncio
import json
import websockets
from aiohttp import web
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import tables

MOCK_UPDATE_FREQUENCY_SECONDS = float(os.getenv("MOCK_UPDATE_FREQUENCY_SECONDS", "8.0"))
MOCK_H5_PATH = os.getenv("MOCK_H5_PATH", "/app/tests/ukdale_5_1_week.h5")


DATASET_DAY_FRAMES: Dict[str, Dict[int, object]] = {}
DATASET_ENTITY_METADATA: Dict[str, Dict[str, str]] = {}
DATASET_INTERVAL_SECONDS = 6.0


def _make_power_state(entity_id: str, friendly_name: str, initial_state: float = 0.0):
    return {
        "entity_id": entity_id,
        "state": str(initial_state),
        "attributes": {
            "unit_of_measurement": "W",
            "device_class": "power",
            "friendly_name": friendly_name,
            "state_class": "measurement",
        },
    }


# Mock data for HA states
mock_states = {
    "sensor.mock_mains": _make_power_state("sensor.mock_mains", "Mains", 0.0),
}

INGRESS_URL_BASE = "/api" 

# Define distinct ports for WebSocket and REST API
MOCK_WS_PORT = 8123
MOCK_REST_API_PORT = 8124

def _seconds_since_midnight(ts: datetime) -> int:
    dt = ts.astimezone(timezone.utc)
    return dt.hour * 3600 + dt.minute * 60 + dt.second


def _as_utc_timestamp_series(timestamps: np.ndarray) -> "pd.DatetimeIndex":
    return pd.to_datetime(timestamps, unit="s", utc=True)


def _prepare_dataset_day_frames(df: "pd.DataFrame") -> Dict[int, "pd.DataFrame"]:
    frames: Dict[int, "pd.DataFrame"] = {}
    work = df.copy()
    work["seconds"] = (
        work.index.hour * 3600
        + work.index.minute * 60
        + work.index.second
    )
    for day in range(7):
        day_frame = work[work.index.dayofweek == day][["power", "seconds"]].copy()
        if day_frame.empty:
            continue
        day_frame = day_frame.drop_duplicates(subset="seconds", keep="first").sort_values("seconds")
        frames[day] = day_frame
    return frames


def _slugify_sensor_name(name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in name.strip())
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _pretty_appliance_name(name: str) -> str:
    words = [word for word in name.replace("_", " ").split() if word]
    return " ".join(word.capitalize() for word in words)


def _load_ukdale_dataset():
    if not os.path.exists(MOCK_H5_PATH):
        raise FileNotFoundError(f"Mock HA: required dataset not found at {MOCK_H5_PATH}")

    print(f"Mock HA: Loading UK-DALE dataset from {MOCK_H5_PATH}...")
    with tables.open_file(MOCK_H5_PATH, mode="r") as h5file:
        mains_values = np.asarray(h5file.root.mains_data.read(), dtype=float).reshape(-1)
        mains_timestamps = np.asarray(h5file.root.mains_timestamps.read(), dtype=float).reshape(-1)
        mains_index = _as_utc_timestamp_series(mains_timestamps)
        mains_df = pd.DataFrame({"power": mains_values}, index=mains_index)
        DATASET_DAY_FRAMES["sensor.mock_mains"] = _prepare_dataset_day_frames(mains_df)
        DATASET_ENTITY_METADATA["sensor.mock_mains"] = {
            "friendly_name": "Mains",
            "source": "ukdale",
        }

        appliances_group = h5file.root.appliances
        appliance_nodes = {
            node._v_name[:-5]
            for node in appliances_group._f_iter_nodes()
            if node._v_name.endswith("_data")
        }

        for appliance_key in sorted(appliance_nodes):
            data_attr = f"{appliance_key}_data"
            ts_attr = f"{appliance_key}_timestamps"
            if not hasattr(appliances_group, ts_attr):
                print(f"Mock HA: Dataset missing timestamps for appliance '{appliance_key}', skipping.")
                continue
            entity_id = f"sensor.{_slugify_sensor_name(appliance_key)}_power"
            friendly_name = f"{_pretty_appliance_name(appliance_key)} Power"
            appliance_values = np.asarray(getattr(appliances_group, data_attr).read(), dtype=float).reshape(-1)
            appliance_timestamps = np.asarray(getattr(appliances_group, ts_attr).read(), dtype=float).reshape(-1)
            appliance_index = _as_utc_timestamp_series(appliance_timestamps)
            appliance_df = pd.DataFrame({"power": appliance_values}, index=appliance_index)
            DATASET_DAY_FRAMES[entity_id] = _prepare_dataset_day_frames(appliance_df)
            DATASET_ENTITY_METADATA[entity_id] = {
                "friendly_name": friendly_name,
                "source": "ukdale",
            }

    if not DATASET_DAY_FRAMES.get("sensor.mock_mains"):
        raise RuntimeError("Mock HA: UK-DALE dataset did not yield mains day frames.")

    dataset_states = {}
    for entity_id, meta in DATASET_ENTITY_METADATA.items():
        dataset_states[entity_id] = _make_power_state(entity_id, meta["friendly_name"], 0.0)
        dataset_states[entity_id]["attributes"]["mock_source"] = meta["source"]
    mock_states.clear()
    mock_states.update(dataset_states)
    print(f"Mock HA: UK-DALE mode enabled with {len(mock_states)} sensors.")


def _nearest_dataset_value(entity_id: str, ts: datetime) -> float:
    day_frames = DATASET_DAY_FRAMES.get(entity_id)
    if not day_frames:
        return 0.0
    day = ts.astimezone(timezone.utc).weekday()
    frame = day_frames.get(day)
    if frame is None or frame.empty:
        available_days = sorted(day_frames.keys())
        if not available_days:
            return 0.0
        frame = day_frames[available_days[day % len(available_days)]]
    sec = _seconds_since_midnight(ts)
    seconds = frame["seconds"].to_numpy()
    idx = int(np.abs(seconds - sec).argmin())
    return float(frame.iloc[idx]["power"])


def _dataset_history(entity_id: str, start_date_dt: datetime, end_date_dt: datetime) -> List[dict]:
    history_data = []
    current_time = start_date_dt
    interval = timedelta(seconds=DATASET_INTERVAL_SECONDS)
    while current_time <= end_date_dt:
        power = _nearest_dataset_value(entity_id, current_time)
        timestamp = current_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        history_data.append({
            "state": str(round(power, 1)),
            "last_changed": timestamp,
            "last_updated": timestamp,
        })
        current_time += interval
    return history_data
def generate_mock_power(entity_id: str, ts: datetime) -> float:
    return _nearest_dataset_value(entity_id, ts)


def refresh_mock_states(now: Optional[datetime] = None):
    ts = now or datetime.now(timezone.utc)
    for entity_id in list(mock_states.keys()):
        power = round(generate_mock_power(entity_id, ts), 1)
        mock_states[entity_id]["state"] = str(power)
        mock_states[entity_id]["attributes"]["last_updated"] = ts.isoformat()


async def websocket_handler(websocket, path):
    """
    Handles WebSocket communication, simulating Home Assistant's behavior.
    It performs authentication and then sends mock state_changed events.
    """
    print(f"Mock HA: New WebSocket client connected on path: {path}")
    
    await websocket.send(json.dumps({"type": "auth_required", "ha_version": "2025.1.0"}))
    
    try:
        # 2. Wait for auth request from the client
        auth_request = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
        
        # Validate the access token
        expected_token = os.getenv("SUPERVISOR_TOKEN", "dev_token")
        if auth_request.get("access_token") == expected_token:
            await websocket.send(json.dumps({"type": "auth_ok", "ha_version": "2025.1.0"}))
            print("Mock HA: WebSocket authentication successful.")
        else:
            await websocket.send(json.dumps({"type": "auth_invalid", "message": "Invalid token provided."}))
            print(f"Mock HA: WebSocket authentication failed. Expected '{expected_token}', got '{auth_request.get('access_token')}'")
            return # Exit handler on invalid auth

        # 3. Wait for subscribe_events request
        subscribe_request = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))

        if subscribe_request.get("type") == "subscribe_events" and subscribe_request.get("event_type") == "state_changed":
            print(f"Mock HA: Received subscribe_events request (id: {subscribe_request['id']}). Starting to send dummy data.")
            event_counter = 0
            sensor_to_monitor = os.getenv("MAIN_SENSOR", "sensor.mock_mains")
            
            while True: # Keep sending data until connection closes
                event_counter += 1

                if sensor_to_monitor in mock_states:
                    now = datetime.now(timezone.utc)
                    refresh_mock_states(now)
                    
                    event_data = {
                        "id": subscribe_request["id"],
                        "type": "event",
                        "event": {
                            "event_type": "state_changed",
                            "data": {
                                "entity_id": sensor_to_monitor,
                                "old_state": {}, 
                                "new_state": mock_states[sensor_to_monitor]
                            },
                            "origin": "LOCAL",
                            "time_fired": now.isoformat()
                        }
                    }
                    await websocket.send(json.dumps(event_data))
                    
                await asyncio.sleep(MOCK_UPDATE_FREQUENCY_SECONDS) # Use configurable frequency
        else:
            print(f"Mock HA: Unexpected WebSocket request received after auth: {subscribe_request}")

    except asyncio.TimeoutError:
        print("Mock HA: WebSocket client did not send expected message in time. Connection might be short-lived.")
    except websockets.exceptions.ConnectionClosedOK:
        print("Mock HA: WebSocket connection closed gracefully by client during handshake/subscription. This is expected for readiness probes.")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Mock HA: WebSocket connection closed with error: {e}")
    except json.JSONDecodeError as e:
        print(f"Mock HA: Error decoding JSON from WebSocket message: {e}")
    except Exception as e:
        print(f"Mock HA: Unexpected error in websocket_handler: {e}")

async def get_states_handler(request):
    """
    Handles GET /api/states, returning all current mock entity states.
    """
    print("Mock HA: Received GET /api/states request.")
    refresh_mock_states()
    return web.json_response(list(mock_states.values()))

async def post_state_handler(request):
    """
    Handles POST /api/states/{entity_id}, simulating state updates to HA.
    """
    entity_id = request.match_info['entity_id']
    data = await request.json()
    print(f"Mock HA: Received state update for {entity_id}: {data}")
    
    mock_states[entity_id] = {
        "entity_id": entity_id,
        "state": str(data.get("state")),
        "attributes": data.get("attributes", {})
    }
    
    return web.json_response(mock_states[entity_id], status=201)

# Handler for mock historical data
async def get_mock_history_handler(request):
    """
    Generates mock historical data for the main sensor, mimicking Home Assistant's history/period API.
    The start_time is provided as a path parameter.
    The end_time and filter_entity_id are provided via query parameters.
    Defaults to the last 7 days if no specific period or end_time is provided.
    The range is limited to a maximum of 7 days.
    """
    print("Mock HA: Received GET /api/history/period/{start_time_str} request for history.")
    
    # Get start date from path parameter
    start_time_str_path = request.match_info.get("start_time_str")
    
    # Get end_time and filter_entity_id from query parameters
    end_time_str_query = request.query.get("end_time")
    filter_entity_id = request.query.get("filter_entity_id")
    minimal_response = request.query.get("minimal_response") # HA sometimes sends this

    # Default end date is now
    end_date_dt = datetime.now(timezone.utc)
    if end_time_str_query:
        try:
            end_date_dt = datetime.fromisoformat(end_time_str_query.replace('Z', '+00:00')).astimezone(timezone.utc)
        except ValueError as e:
            print(f"Mock HA: Invalid 'end_time' query param: {end_time_str_query}. Error: {e}. Using current time as end.")
            # If parsing fails, use default end_date_dt
    
    # Default start date is 7 days before end_date_dt
    start_date_dt = end_date_dt - timedelta(days=7)
    if start_time_str_path:
        try:
            if "T" in start_time_str_path:
                start_date_dt = datetime.fromisoformat(start_time_str_path.replace('Z', '+00:00')).astimezone(timezone.utc)
            else:
                start_date_dt = datetime.strptime(start_time_str_path, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError as e:
            print(f"Mock HA: Invalid 'start_time_str' path param: {start_time_str_path}. Error: {e}. Using default 7 days ago as start.")
            # If parsing fails, use default start_date_dt

    # Validate date range: must be no more than 7 days
    time_difference = end_date_dt - start_date_dt
    if time_difference > timedelta(days=7) + timedelta(seconds=1): # Allow for slight drift due to minute/second parsing
        print(f"Mock HA: Requested range ({start_date_dt} to {end_date_dt}) exceeds 7 days. Denying.")
        return web.json_response({"status": "error", "message": "Date range cannot exceed 7 days."}, status=400)

    sensor_to_mock = filter_entity_id or os.getenv("MAIN_SENSOR", "sensor.mock_mains")
    if sensor_to_mock not in mock_states:
        print(f"Mock HA: No history for requested entity_id: {filter_entity_id}. Returning empty.")
        return web.json_response([[]]) # HA API returns list of lists, so empty list of history for entity

    history_data = _dataset_history(sensor_to_mock, start_date_dt, end_date_dt)
    
    # HA history API returns a list of lists, one inner list per entity requested
    print(f"Mock HA: Generated {len(history_data)} history points for {sensor_to_mock} from {start_date_dt.isoformat()} to {end_date_dt.isoformat()}.")
    return web.json_response([history_data])


async def start_mock_servers():
    """
    Starts both the WebSocket and REST API mock servers.
    """
    # WebSocket Server
    websocket_server = await websockets.serve(websocket_handler, "0.0.0.0", MOCK_WS_PORT, subprotocols=["homeassistant"])
    websocket_task = asyncio.create_task(websocket_server.wait_closed())
    print(f"Mock HA WebSocket server started on ws://0.0.0.0:{MOCK_WS_PORT}/") 
    
    # REST API Server setup
    app = web.Application()
    app.router.add_get(f'{INGRESS_URL_BASE}/states', get_states_handler)
    app.router.add_post(f'{INGRESS_URL_BASE}/states/{{entity_id}}', post_state_handler)
    # Re-added the /period/ route to match HA's expected history API structure
    app.router.add_get(f'{INGRESS_URL_BASE}/history/period/{{start_time_str}}', get_mock_history_handler) 
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', MOCK_REST_API_PORT)
    rest_api_task = asyncio.create_task(site.start())

    print(f"Mock HA REST API server started on http://0.0.0.0:{MOCK_REST_API_PORT}{INGRESS_URL_BASE}")
    
    await asyncio.gather(websocket_task, rest_api_task)

if __name__ == "__main__":
    _load_ukdale_dataset()
    asyncio.run(start_mock_servers())
