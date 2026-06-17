---
id: GT-P1-06
phase: 1
status: todo
depends_on: 
  - GT-P1-04
  - GT-P1-05
---

# Implement Engine HTTP Service

Stand up the local engine HTTP service and minimal API.

## Scope

- Endpoints: `GET /health`, `GET /status`, `POST /agents/{name}/run`, `POST /workflows/{name}/start`, `GET /workflows/{name}/status`, `POST /engine/stop`.

## Requirements

- `/status` reports loaded workspace and registered agents/workflows.
- Unknown agent or workflow returns a clear error.

## Acceptance Criteria

- `/health` returns success.
- Engine shuts down through the API.
- Unknown references return clear errors.
