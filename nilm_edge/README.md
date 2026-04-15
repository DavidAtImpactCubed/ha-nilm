# Home Assistant NILM App

This app runs real-time NILM inference inside Home Assistant.

It monitors one mains power sensor, applies trained appliance models, and publishes live appliance power and on/off entities back to Home Assistant.

NILM provides estimation from aggregate mains data, not direct per-appliance measurement.

## Main Features

- Live disaggregation from one aggregate mains sensor.
- Built-in UI for setup, model management, and preview.
- Training job preparation and handoff to the separate `NILM Training Server` app (or compatible external training server).
- Per-model live publish toggle.

## Quick Start

1. Install both apps: `NILM` and `NILM Training Server`.
2. Start `NILM Training Server` first, then start `NILM`.
3. Open the `NILM` UI and save your mains power sensor.
4. Open the Training page and confirm the training server is ready.

## Core Workflow

1. Select and save the mains sensor in `NILM`.
2. In Training, choose manual interval labeling or sensor-based labeling.
3. Prepare training data from Home Assistant history.
4. Send the job to the training server.
5. When training finishes, validate predictions in the Energy Dashboard.
6. Enable live publishing for selected models.
7. Use generated entities in dashboards and automations.

Notes:
- Training range is limited to the previous 7 days.
- Better training quality comes from complete labeling of the chosen interval.
- Live entities are updated approximately every 8 seconds.

## Published Entities

For each model enabled for live publishing:

- `sensor.nilm_<appliance>_power`
- `binary_sensor.nilm_<appliance>_on`

## Requirements

- Home Assistant app environment.
- A mains power sensor already available in Home Assistant.
- Recorder history for the selected training period.
- Both NILM apps installed (`NILM` and `NILM Training Server`).
- Around 4 GB RAM available for Home Assistant + NILM apps.
- Mains updates in the order of seconds (1s, 3s, 5s, 10s typically work well).

## Full Documentation

This README only covers the essentials.

For complete setup, training, troubleshooting, and advanced guidance, visit:

- https://ha-nilm.bigwicho.com/
