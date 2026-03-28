# NILM Training Server

This service receives prepared NILM training data, runs appliance-model training, and returns the trained model outputs needed by the NILM add-on.

## What The Service Does

- Accepts prepared training jobs from the NILM add-on or any compatible client.
- Runs background training jobs for a selected model bundle.
- Tracks job progress and exposes job status through a simple HTTP API.
- Returns the trained embedding, learned thresholds, and training metadata when a job finishes.

## Bundle Requirements

The service expects a training bundle that contains the Keras head model and its manifest.

- `bundles/online_v1/head.h5`
- `bundles/online_v1/bundle_manifest.json`

This training bundle should match the corresponding inference bundle used by the NILM add-on.

## API Overview

The service exposes a small HTTP API:

- `GET /version`
- `POST /train`
- `GET /train/{job_id}`
- `GET /train/{job_id}/result`

Training jobs move through the states `queued`, `running`, `done`, or `error`.

The final result includes:

- the appliance name
- the trained embedding vector
- the bundle id, mode, and version used for training
- learned appliance thresholds and related parameters
- training statistics

## Run With Docker

Build the image:

```bash
docker build -t training-server:latest .
```

Run the service:

```bash
docker run -p 8080:8080 training-server:latest
```

If you want to replace an existing local container first:

```bash
docker rm -f training-server 2>NUL
docker build -t training-server:latest .
docker run -d --name training-server -p 8080:8080 training-server:latest
```

## Persistence

The service stores job state and training outputs under its configured data directories so they remain available across restarts.
