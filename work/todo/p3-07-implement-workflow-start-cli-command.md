---
id: GT-P3-07
phase: 3
status: todo
depends_on: 
  - GT-P1-06
  - GT-P3-06
---

# Implement Workflow Start CLI Command

Add `geartrain workflow start`.

## Scope

- Call `POST /workflows/geartrain-dev/start`; print status or final response.

## Requirements

- If already running, print current status and do nothing else.
- CLI does not run workflow logic directly.

## Acceptance Criteria

- `geartrain workflow start` starts a run.
- Re-running while locked reports status.
- No-task case returns a clear message.
