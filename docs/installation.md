# Installation And First Setup

This guide covers the first-time setup of both apps inside Home Assistant.

## 1. Add The Repository To Home Assistant

1. Open Home Assistant.
2. Go to `Settings`.
3. Open `Apps`.
4. Open the `App Store`.
5. Open the top-right menu and choose `Repositories`.
6. Add this repository:

```text
https://github.com/lgarciamarrero92/ha-nilm
```

7. Refresh the App Store if needed.

## 2. Install The Apps

Install these two apps:

- `NILM`
- `NILM Training Server`

`NILM` is the main app.

`NILM Training Server` is the background trainer used when you create appliance models from history.

## 3. Start NILM Training Server First

The training app should be started before you begin training appliances.

After starting `NILM Training Server`:

- check that the app is running
- optionally open its Web UI
- optionally check its logs

The training server app exposes an HTTP API on port `8080`.

## 4. Start NILM

Start the `NILM` app and open its web UI from Home Assistant.

The UI currently includes two main pages:

- `Energy Dashboard`
- `Appliance Training Session`

## 5. Configure The Training Server In NILM

The training connection is configured from the `Appliance Training Session` page.

Open `Appliance Training Session` and look for the `Training Server Connection` card.

Current behavior:

- if the internal training app is detected, it appears as a selectable option
- you still need to select it and press `Save`
- once saved, the card should show the training server as ready

If the internal training app is installed and running, the expected option is typically shown as:

- `Internal App`

This selection is important because `NILM` uses it when sending prepared training jobs.

## 6. Configure The Mains Sensor

Open `Energy Dashboard`.

In the mains sensor selector:

1. choose the aggregate mains power sensor you want NILM to monitor
2. wait for the dashboard to save the selection automatically
3. confirm that the mains chart loads successfully

The mains sensor is the most important configuration in the app.

It is used for:

- live disaggregation
- dashboard previews
- training preparation

## 7. Verify The Initial Setup

Before training anything, make sure all of these are true:

- the `NILM` app is running
- the `NILM Training Server` app is running
- the training server is selected and saved in `Appliance Training Session`
- the mains sensor is selected in `Energy Dashboard`
- the mains chart loads correctly

When those items are working, the system is ready for appliance training and disaggregation preview.

## Home Assistant Entities Created By NILM

After you train models and enable live publishing, `NILM` creates entities such as:

- `sensor.nilm_<appliance>_power`
- `binary_sensor.nilm_<appliance>_on`

These entities include useful attributes such as:

- the on/off probability
- the on/off threshold used by the deployed model

`NILM` also publishes:

- `sensor.nilm_disaggregation_duration`

This reports the runtime of the full disaggregation pass.

## Recommended Input Signal Quality

The apps work best when the mains power sensor:

- is a power sensor in watts
- updates regularly
- has enough history available in Home Assistant

Low-frequency or inconsistent mains signals can still work, but they usually reduce disaggregation quality and make event timing less precise.

