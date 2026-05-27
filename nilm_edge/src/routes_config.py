from aiohttp import web

import app_state
from training_server_url import is_valid_training_server_url, normalize_training_server_url


async def get_config_handler(request):
    training_server_state = await app_state.resolve_training_server_url_state()
    return web.json_response({
        **app_state.current_config,
        **training_server_state,
    })


async def post_config_handler(request):
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")

        update_main_sensor_id = "main_sensor_id" in data
        update_main_sensor_unit = "main_sensor_unit" in data
        update_training_server_url = "training_server_url" in data
        if not update_main_sensor_id and not update_main_sensor_unit and not update_training_server_url:
            raise ValueError("Nothing to update. Provide 'main_sensor_id', 'main_sensor_unit' and/or 'training_server_url'.")

        new_main_sensor_id = data.get("main_sensor_id")
        new_main_sensor_unit = data.get("main_sensor_unit")
        new_training_server_url = data.get("training_server_url")

        if update_main_sensor_id and new_main_sensor_id is not None and not isinstance(new_main_sensor_id, str):
            raise ValueError("Invalid format for 'main_sensor_id' (must be string).")
        if update_main_sensor_unit and new_main_sensor_unit is not None and not isinstance(new_main_sensor_unit, str):
            raise ValueError("Invalid format for 'main_sensor_unit' (must be string).")
        if update_training_server_url and new_training_server_url is not None and not isinstance(new_training_server_url, str):
            raise ValueError("Invalid format for 'training_server_url' (must be string).")
        if update_training_server_url and isinstance(new_training_server_url, str) and new_training_server_url.strip():
            normalized_training_server_url = normalize_training_server_url(new_training_server_url)
            if not is_valid_training_server_url(normalized_training_server_url):
                raise ValueError("Invalid 'training_server_url'. Use a full host or URL such as http://trainer.local:8080/train.")

        app_state.save_config(
            main_sensor_id=new_main_sensor_id,
            main_sensor_unit=new_main_sensor_unit,
            training_server_url=new_training_server_url,
            update_main_sensor_id=update_main_sensor_id,
            update_main_sensor_unit=update_main_sensor_unit,
            update_training_server_url=update_training_server_url,
        )
        if update_main_sensor_id:
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
