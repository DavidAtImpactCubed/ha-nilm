# NILM Training Server

![NILM for Home Assistant logo](https://github.com/lgarciamarrero92/ha-nilm/raw/main/nilm_trainer/logo.png)

This app receives prepared training jobs from `NILM`, runs appliance-model training, and returns trained outputs used by the NILM inference app.

## Main Role

- Accepts prepared training jobs from the NILM app (or compatible clients).
- Runs background training jobs for a selected model bundle.
- Tracks job progress and exposes job status through a simple HTTP API.
- Returns the trained embedding, learned thresholds, and training metadata when a job finishes.

## Documentation

This README covers the essentials.

For full user workflow and guidance:

- https://ha-nilm.bigwicho.com/
