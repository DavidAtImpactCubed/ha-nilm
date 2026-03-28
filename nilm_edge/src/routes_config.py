from aiohttp import web

import app_state


async def get_config_handler(request):
    return web.json_response(app_state.current_config)


async def post_config_handler(request):
    try:
        data = await request.json()
        new_main_sensor_id = data.get("main_sensor_id")

        if new_main_sensor_id is None:
            raise ValueError("Missing 'main_sensor_id' in request body.")
        if not isinstance(new_main_sensor_id, str):
            raise ValueError("Invalid format for 'main_sensor_id' (must be string).")

        app_state.save_config(new_main_sensor_id)
        app_state.reload_algorithm_config()

        return web.json_response({"status": "success", "message": "Configuration updated successfully."})
    except ValueError as exc:
        return web.json_response({"status": "error", "message": str(exc)}, status=400)
    except Exception as exc:
        print(f"Error handling POST /config: {exc}")
        return web.json_response({"status": "error", "message": f"Internal server error: {exc}"}, status=500)


def register_config_routes(app, ingress_url_base):
    app.router.add_get(ingress_url_base + "config", get_config_handler)
    app.router.add_post(ingress_url_base + "config", post_config_handler)
