# Branching Guide

This repository is intended to use two long-lived branches:

- `main`: release-ready Home Assistant apps only
- `dev`: everything in `main`, plus local development helpers such as mock services, local compose files, datasets, and workflow notes

## Files Intended For `main`

Keep the production app code and documentation:

- `nilm_edge/config.yaml`
- `nilm_edge/Dockerfile`
- `nilm_edge/requirements.txt`
- `nilm_edge/README.md`
- `nilm_edge/src/`
- `nilm_edge/www/`
- `nilm_edge/inference/`
- `nilm_trainer/config.yaml`
- `nilm_trainer/Dockerfile`
- `nilm_trainer/requirements.txt`
- `nilm_trainer/README.md`
- `nilm_trainer/app/`
- `nilm_trainer/bundles/`

## Files Intended Only For `dev`

Keep development-only helpers on `dev`:

- `nilm_edge/docker-compose.dev.yml`
- `nilm_edge/Dockerfile.mock`
- `nilm_edge/requirements.mock.txt`
- `nilm_edge/Dev Workflow.md`
- `nilm_edge/tests/mock_ha.py`
- `nilm_edge/tests/wait_for_ha.py`
- `nilm_edge/tests/ukdale_5_1_week.h5`

## Recommended Workflow

1. Make the first commit on `dev`.
2. Create `main` from `dev`.
3. On `main`, remove the files listed in the dev-only section.
4. Keep day-to-day development on `dev`.
5. Merge `dev` into `main` when features are ready for release.
