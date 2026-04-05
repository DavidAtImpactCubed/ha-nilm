# Home Assistant NILM App

This app runs real-time NILM inference inside Home Assistant.

It listens to one aggregate mains power sensor, applies the available appliance models, and publishes live per-appliance power and on/off entities back into Home Assistant.

## What The App Does

- Monitors one mains power sensor from Home Assistant over the supervisor WebSocket/API.
- Publishes live appliance predictions as Home Assistant entities.
- Lets you choose the mains sensor from the built-in web UI.
- Shows the trained appliance models currently available to the app.
- Lets you enable or disable live publishing per trained model.
- Provides prediction preview tools on historical mains data.
- Provides a training page that prepares training jobs and sends them to the separate NILM Training Server app or any compatible external training server.

## Installation

1. Add your app repository to Home Assistant.
2. Install the `NILM` app.
3. Open the `NILM Training Server` app Web UI or logs and copy the displayed `training_server_url`.
4. In the `NILM` app Configuration tab, set `training_server_url` to that value.
5. Start the app.
6. Open the web UI from the app page.

## Web UI

The app currently has two main pages.

### Main Configuration

Use this page to:

- Select the aggregate mains sensor the app should monitor.
- Preview recent mains history.
- Review trained appliance models stored in the app.
- Enable or disable live publishing for each model.
- Launch prediction previews for a model on historical data.
- Delete trained models you no longer want to keep.

### Training Interface

Use this page to prepare appliance training data from Home Assistant history and send it to the training server.

The page supports two supervision modes:

- Interval supervision: you mark windows where the appliance is active in the mains signal.
- Sensor supervision: you provide a ground-truth appliance power sensor from Home Assistant.

The training page:

- Checks whether the training server is reachable.
- Builds embeddings from the selected history range.
- Creates local training jobs.
- Sends prepared jobs to the training server.
- Tracks job progress until the trained appliance model is returned.

## Training Server

Training is not performed inside this app itself.

This app prepares the training payload and sends it to the configured `TRAINING_SERVER_URL`. By default that URL points to a Home Assistant-hosted training server endpoint, but it can also point to an external compatible server.

You can enter the training server as either:

- `hostname:8080`
- `http://hostname:8080`
- `http://hostname:8080/train`

The app normalizes those forms to the actual training endpoint automatically.

## Published Home Assistant Entities

For each trained appliance model that has live publishing enabled, the app creates:

- `sensor.nilm_<appliance>_power`
- `binary_sensor.nilm_<appliance>_on`

If the model belongs to a specific bundle, the bundle id is included in the generated entity suffix to keep entity ids unique.

The app also publishes:

- `sensor.nilm_disaggregation_duration`

This entity reports how long the latest disaggregation step took.

## Data Requirements

The app works best when the mains power sensor updates frequently and consistently.

- Recommended: about 1 sample per second.
- Lower update rates can still work, but prediction quality and event timing can degrade.

## Persistence

The app stores its configuration and trained models under the app data directory, so they persist across restarts.
