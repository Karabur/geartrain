---
id: GT-M1-005
status: todo
depends_on:
  - GT-M1-004
---

# Implement Engine HTTP Service

Create the local engine HTTP service and minimal API.

## Scope

- Start a local HTTP server.
- Add health and status endpoints.
- Add direct agent run endpoint.
- Add workflow start and workflow status endpoints.
- Add engine stop endpoint.

## Required Endpoints

```text
GET  /health
GET  /status
POST /agents/{agent_name}/run
POST /workflows/{workflow_name}/start
GET  /workflows/{workflow_name}/status
POST /engine/stop
```

## Acceptance Criteria

- `GET /health` returns success.
- `GET /status` reports loaded workspace and registered agents/workflows.
- Unknown agent returns a clear error.
- Unknown workflow returns a clear error.
- Engine can shut down through the API.
