---
id: GT-P1-07
phase: 1
status: todo
depends_on: 
  - GT-P1-06
---

# Implement Engine CLI Lifecycle Commands

Add `geartrain engine start|stop|status`.

## Scope

- `engine start` loads and validates `.geartrain/`, may run in the foreground.
- `engine status` and `engine stop` call the engine API.

## Requirements

- Invalid config makes `start` exit non-zero.
- CLI does not duplicate engine logic.

## Acceptance Criteria

- `engine start` starts the engine.
- `engine status` reports running state.
- `engine stop` stops it via the API.
