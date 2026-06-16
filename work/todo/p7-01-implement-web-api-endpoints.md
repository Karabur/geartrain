---
id: GT-P7-01
phase: 7
status: todo
depends_on: 
  - GT-P3-03
  - GT-P5-02
---

# Implement Web API Endpoints

Add the FastAPI endpoints the UI needs.

## Scope

- `GET /api/workflows`, `GET /api/workflows/{id}`, `GET /api/workflows/{id}/checkpoints`, `POST /api/workflows/{id}/checkpoints/{cid}/respond`.
- `GET /api/memory`, `GET /api/memory/{scope}`.

## Requirements

- Endpoints read file-backed state and memory.
- Checkpoint respond resumes the paused workflow.

## Acceptance Criteria

- Tests cover each endpoint against a seeded run.
