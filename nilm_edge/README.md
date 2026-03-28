# Home Assistant NILM Add-on

This add-on runs real-time NILM inference inside Home Assistant.

It listens to one aggregate mains power sensor, applies the available appliance models, and publishes live per-appliance power and on/off entities back into Home Assistant.

## What The Add-on Does

- Monitors one mains power sensor from Home Assistant over the supervisor WebSocket/API.
- Publishes live appliance predictions as Home Assistant entities.
- Lets you choose the mains sensor from the built-in web UI.
- Shows the trained appliance models currently available to the add-on.
- Lets you enable or disable live publishing per trained model.
- Provides prediction preview tools on historical mains data.
- Provides a training page that prepares training jobs and sends them to the separate NILM Training Server add-on or any compatible external training server.

## Installation

1. Add your add-on repository to Home Assistant.
2. Install the `NILM` add-on.
3. Start the add-on.
4. Open the web UI from the add-on page.

## Web UI

The add-on currently has two main pages.

### Main Configuration

Use this page to:

- Select the aggregate mains sensor the add-on should monitor.
- Preview recent mains history.
- Review trained appliance models stored in the add-on.
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

Training is not performed inside this add-on itself.

This add-on prepares the training payload and sends it to the configured `TRAINING_SERVER_URL`. By default that URL points to a Home Assistant-hosted training server endpoint, but it can also point to an external compatible server.

## Published Home Assistant Entities

For each trained appliance model that has live publishing enabled, the add-on creates:

- `sensor.nilm_<appliance>_power`
- `binary_sensor.nilm_<appliance>_on`

If the model belongs to a specific bundle, the bundle id is included in the generated entity suffix to keep entity ids unique.

The add-on also publishes:

- `sensor.nilm_disaggregation_duration`

This entity reports how long the latest disaggregation step took.

## Data Requirements

The add-on works best when the mains power sensor updates frequently and consistently.

- Recommended: about 1 sample per second.
- Lower update rates can still work, but prediction quality and event timing can degrade.

## Persistence

The add-on stores its configuration and trained models under the add-on data directory, so they persist across restarts.
