# tests/wait_for_ha.py
import time
import os
import sys
import asyncio
import websockets
import json
import aiohttp # Imported for aiohttp.ClientConnectorError, which websockets can raise
import socket # Import socket for DNS lookup

# Get mock HA details from environment variables (set in docker-compose.dev.yml)
MOCK_HA_HOST = os.getenv("MOCK_HA_HOST", "mock-ha")
MOCK_WS_PORT = int(os.getenv("MOCK_WS_PORT", "8123")) # WebSocket port
MOCK_REST_API_PORT = int(os.getenv("MOCK_REST_API_PORT", "8124")) # REST API port
MAIN_APP_COMMAND = os.getenv("MAIN_APP_COMMAND", "python main.py").split()
SUPERVISOR_TOKEN_FOR_PROBE = os.getenv("SUPERVISOR_TOKEN", "dev_token")


# Construct the full URL for the mock WebSocket
MOCK_WS_URL = f"ws://{MOCK_HA_HOST}:{MOCK_WS_PORT}/api/websocket"

print(f"Waiting for mock Home Assistant WebSocket at {MOCK_WS_URL} to be fully ready (checking handshake & DNS)...")

retries = 30  # Increased retries for robustness
initial_delay = 1

async def perform_full_mock_websocket_handshake():
    """
    Attempts to establish a WebSocket connection and perform a full mock handshake
    (auth, subscribe events) to ensure the server is fully ready.
    """
    for i in range(retries):
        delay = initial_delay * (2 ** i) # Exponential backoff
        try:
            resolved_ip = check_dns_resolution(MOCK_HA_HOST)
            if not resolved_ip:
                print(f"WebSocket handshake skipped because {MOCK_HA_HOST} is not resolvable yet. Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
                continue

            probe_ws_url = f"ws://{resolved_ip}:{MOCK_WS_PORT}/api/websocket"
            print(f"Attempting full WebSocket handshake to {probe_ws_url} (attempt {i+1}/{retries})...")
            
            # Use short timeouts for connection and message reception to avoid hanging
            async with websockets.connect(probe_ws_url, open_timeout=5, read_limit=8192, write_limit=8192) as ws:
                # 1. Wait for auth_required
                initial_msg = await asyncio.wait_for(ws.recv(), timeout=5)
                msg_json = json.loads(initial_msg)

                if msg_json.get("type") != "auth_required":
                    print(f"Mock HA WebSocket: Expected 'auth_required', got '{msg_json.get('type')}'. Retrying...")
                    # Close the connection and allow retry
                    await ws.close()
                    continue # Try again
                
                # 2. Send dummy auth message with the correct token
                await ws.send(json.dumps({
                    "type": "auth",
                    "access_token": SUPERVISOR_TOKEN_FOR_PROBE # Use the correct token
                }))
                auth_result = await asyncio.wait_for(ws.recv(), timeout=5)
                auth_result_json = json.loads(auth_result)

                if auth_result_json.get("type") != "auth_ok":
                    print(f"Mock HA WebSocket: Auth failed during readiness check: {auth_result_json.get('message')}. Retrying...")
                    # Close the connection and allow retry
                    await ws.close()
                    continue # Try again

                # 3. Send dummy subscribe_events message
                await ws.send(json.dumps({
                    "id": 9999, # Dummy ID
                    "type": "subscribe_events",
                    "event_type": "state_changed"
                }))
                
                # Be flexible here. Accept either 'result' or 'event' as success.
                subscribe_response = await asyncio.wait_for(ws.recv(), timeout=5)
                subscribe_response_json = json.loads(subscribe_response)

                if (subscribe_response_json.get("type") == "result" and subscribe_response_json.get("success")) or \
                   (subscribe_response_json.get("type") == "event" and subscribe_response_json.get("event", {}).get("event_type") == "state_changed"):
                     print(f"Mock Home Assistant WebSocket at {probe_ws_url} is fully ready (full handshake successful and events flowing).")
                     return True
                else:
                    print(f"Mock HA WebSocket: Subscribe failed or unexpected response: {subscribe_response_json}. Retrying...")
                    # Close the connection and allow retry
                    await ws.close()


        except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError,
                ConnectionRefusedError, asyncio.TimeoutError, aiohttp.ClientConnectorError, json.JSONDecodeError) as e:
            print(f"WebSocket handshake failed: {e}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay) # Use time.sleep here, as this is a synchronous wait loop
        except Exception as e:
            # Catch any other unexpected errors during connection attempt
            print(f"An unexpected error occurred during WebSocket handshake health check: {e}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
    return False

# Function to check DNS resolution
def check_dns_resolution(host):
    try:
        ip_address = socket.gethostbyname(host)
        print(f"DNS resolved {host} to {ip_address}.")
        return ip_address
    except socket.gaierror as e:
        print(f"DNS resolution failed for {host}: {e}")
        return None

# Run the asynchronous WebSocket check
if not asyncio.run(perform_full_mock_websocket_handshake()):
    print(f"Failed to establish full WebSocket readiness to {MOCK_WS_URL} after {retries} attempts. Exiting.")
    sys.exit(1) # Exit with an error code if connection fails

# Perform DNS resolution and override HA_WS_URL if successful
print(f"Performing final DNS resolution check for {MOCK_HA_HOST}...")
resolved_ip = None
dns_retries = 10
dns_delay = 0.5
for i in range(dns_retries):
    resolved_ip = check_dns_resolution(MOCK_HA_HOST)
    if resolved_ip:
        print(f"DNS resolution for {MOCK_HA_HOST} successful. Resolved IP: {resolved_ip}")
        break
    else:
        print(f"DNS resolution failed (attempt {i+1}/{dns_retries}). Retrying in {dns_delay:.1f} seconds...")
        time.sleep(dns_delay)
else:
    print(f"Failed to resolve DNS for {MOCK_HA_HOST} after {dns_retries} attempts. Exiting.")
    sys.exit(1)

# Construct the HA_WS_URL using the resolved IP address
# and prepare the environment for the executed main.py process.
if resolved_ip:
    ip_based_ha_ws_url = f"ws://{resolved_ip}:{MOCK_WS_PORT}/api/websocket"
    ip_based_ha_rest_url = f"http://{resolved_ip}:{MOCK_REST_API_PORT}/api"
    # FIX: Create a copy of the current environment and update HA_WS_URL in it.
    # Then pass this updated environment explicitly to os.execvpe.
    new_env = os.environ.copy()
    new_env["HA_WS_URL"] = ip_based_ha_ws_url
    new_env["HA_REST_API_URL"] = ip_based_ha_rest_url
    print(f"Overriding HA_WS_URL for main.py to: {ip_based_ha_ws_url} in the new environment.")
    print(f"Overriding HA_REST_API_URL for main.py to: {ip_based_ha_rest_url} in the new environment.")
else:
    # If for some reason IP wasn't resolved, use the original environment
    # main.py will likely fail, but we've logged warnings.
    new_env = os.environ.copy() 
    print("WARNING: Could not resolve IP for mock-ha. main.py will use original HA_WS_URL. This might lead to connection errors.")


print("Mock Home Assistant is ready. Adding a small final delay before starting main.py...")
time.sleep(2) # Wait for 2 seconds

# Once mock HA is confirmed available, execute the original main.py
print(f"Starting main application: {' '.join(MAIN_APP_COMMAND)}")
# FIX: Use os.execvpe to pass the updated environment explicitly
os.execvpe(MAIN_APP_COMMAND[0], MAIN_APP_COMMAND, new_env)
