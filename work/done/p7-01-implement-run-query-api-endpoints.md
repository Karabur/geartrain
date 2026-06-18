---
id: GT-P7-01
phase: 7
status: todo
depends_on: 
  - GT-P5-02
  - GT-P3-06
---

# Implement Run Query API Endpoints

Add the run APIs needed by CLI inspection, future UI, and dogfooding diagnostics.

## Scope

- `GET /api/runs`, `GET /api/runs/{id}`, `GET /api/runs/{id}/events`, `GET /api/runs/{id}/nodes`, `GET /api/runs/{id}/attempts`.
- `GET /api/workflows`, `GET /api/workflows/{id}`, `GET /api/checkpoints`, `POST /api/checkpoints/{cid}/respond`.
- `GET /api/memory`, `GET /api/memory/{scope}`.

## Requirements

- Endpoints read file-backed run state, event logs, and memory.
- Checkpoint respond resumes the paused workflow.

## Acceptance Criteria

- Tests cover each endpoint against a seeded run with nodes, attempts, checkpoints, and events.
