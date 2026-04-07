# NILM Apps User Documentation

This folder contains end-user documentation for the `NILM` and `NILM Training Server` Home Assistant apps.

If you want to publish the documentation as a website on a PHP-capable host such as Hostinger, the entry page is:

- [index.php](/c:/Users/lgarc/Repositories/ha-nilm/docs/index.php)

It is written for Home Assistant users who want to:

- install the apps
- connect the training server
- configure a mains sensor
- train appliance models
- preview disaggregation results
- publish live NILM entities into Home Assistant

## Documentation Map

- [Installation And First Setup](./installation.md)
- [Energy Dashboard Guide](./energy-dashboard.md)
- [Appliance Training Session Guide](./training.md)
- [Troubleshooting And Practical Tips](./troubleshooting.md)

## What These Apps Do

### NILM

`NILM` is the main Home Assistant app.

It:

- reads one aggregate mains power sensor from Home Assistant
- stores trained appliance models
- shows the `Energy Dashboard` for visualization and preview
- shows the `Appliance Training Session` page for creating training jobs
- publishes live power and on/off entities back into Home Assistant

### NILM Training Server

`NILM Training Server` is the companion training app.

It:

- receives prepared training jobs from `NILM`
- runs training in the background
- returns the trained appliance model and thresholds needed for deployment

## Typical User Flow

1. Install both apps from this repository in Home Assistant.
2. Start `NILM Training Server`.
3. Open `NILM`.
4. Configure the mains sensor in `Energy Dashboard`.
5. Open `Appliance Training Session`.
6. Select the training server, appliance, supervision mode, and history range.
7. Prepare and send the training job.
8. Wait for the new appliance model to appear in `Energy Dashboard`.
9. Use `Disaggregate` or `Disaggregate All` to preview results.
10. Enable live publishing for the models you want to expose to Home Assistant.

## Important Concepts

### Mains Sensor

This is the aggregate power sensor for the whole home or monitored circuit. NILM uses this signal as the input for both:

- training preparation
- live disaggregation

### Appliance Model

A trained appliance model represents one appliance, such as:

- fridge
- oven
- dishwasher
- washing machine

Each model can be previewed in the dashboard and optionally published live.

### Training Quality

The UI shows a `Training Quality` score for each appliance model. This is a model quality indicator derived from the on/off performance of the trained appliance model.

### Live Publishing

When live publishing is enabled for a model, the app creates Home Assistant entities for that appliance and keeps updating them while the app is running.
