# Development Workflow

This document outlines the core steps for the development workflow. The environment is designed to use Docker volumes for live updates, which means you can see your changes instantly without a full container rebuild.

---

## Step 1: Start the Development Environment

To begin, open your terminal in the project's root directory and run the following command. This will build all containers and start the main application and the mock server. You only need to run this command once to start your session.

```
docker compose -f docker-compose.dev.yml up --build --force-recreate
```

Once all services are running, your web UI will be accessible at `http://localhost:8099`. Keep this terminal window open, as it will display real-time logs from your application.

---

## Step 2: Make Your Changes

### For the Web UI

* Make changes to the UI files (HTML, CSS, or JavaScript) using your code editor on your local machine.

* Save the file.

* Go to your web browser and perform a hard refresh (`Ctrl+Shift+R` or `Cmd+Shift+R`).

Your changes will appear instantly, as Docker automatically syncs the files from your local machine to the running container.

### For the Python Backend (Core Logic)

* Make your changes to the Python backend files.

* Since these are backend files, you must restart the service for your changes to take effect.

* In the terminal where you started the services, press `Ctrl+C` to stop everything.

* Run the `docker compose -f docker-compose.dev.yml up` command from Step 1 again.

This workflow minimizes the time spent on rebuilding containers and allows you to quickly iterate on both the frontend and backend of your application.

## Branches

This repo is intended to use:

- `dev` for local development, mock services, datasets, and workflow helpers
- `main` for release-ready add-on contents only

See [BRANCHING.md](/c:/Users/lgarc/Repositories/ha-nilm/BRANCHING.md) for the exact split.
