# NILM Apps For Home Assistant

This repository provides two Home Assistant apps for NILM:

- `NILM`
- `NILM Training Server`

Together, they let you train appliance models from Home Assistant history and run live appliance disaggregation from a mains power sensor.

## Available Apps

### NILM

This is the main app used inside Home Assistant.

It:

- monitors one aggregate mains power sensor
- runs live NILM inference
- publishes per-appliance power and on/off entities back into Home Assistant
- provides a web UI for configuration, model management, preview, and training preparation

### NILM Training Server

This app receives prepared training jobs and returns trained model outputs for the `NILM` app.

It:

- receives training jobs
- runs training in the background
- returns the trained embedding and learned thresholds

## Why Training Is Separate From Inference

Training and live inference are separated on purpose.

The `NILM` app needs to stay responsive and lightweight because it runs continuously inside Home Assistant and performs live predictions.

The `NILM Training Server` is heavier because training needs more CPU, memory, and machine-learning dependencies.

The dependency split reflects this:

- `NILM` uses a light inference stack based on `numpy`, `aiohttp`, `websockets`, and `tflite-runtime`
- `NILM Training Server` uses heavier training dependencies such as `tensorflow`, `fastapi`, and `uvicorn`

## How They Work Together

The normal flow is:

1. Install `NILM` and `NILM Training Server`.
2. Configure the mains sensor in `NILM`.
3. Use the training page in `NILM` to prepare appliance training data from Home Assistant history.
4. Send the prepared job to `NILM Training Server`.
5. Once training finishes, `NILM` uses the returned model outputs for live disaggregation.

## Add This Repository To Home Assistant

1. Open Home Assistant.
2. Go to `Settings` > `Apps` > `App Store`.
3. Open the top-right menu and choose `Repositories`.
4. Add this repository URL:

```text
https://github.com/lgarciamarrero92/ha-nilm
```

5. Install the apps you want from the store.

## More Information

For details about each app:

- [nilm_edge/README.md](/c:/Users/lgarc/Repositories/ha-nilm/nilm_edge/README.md)
- [nilm_trainer/README.md](/c:/Users/lgarc/Repositories/ha-nilm/nilm_trainer/README.md)
