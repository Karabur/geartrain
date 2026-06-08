---
id: GT-M1-006
status: todo
depends_on:
  - GT-M1-005
---

# Implement Engine CLI Lifecycle Commands

Add user-facing CLI commands for starting, stopping, and checking the engine.

## Scope

- `geartrain engine start`
- `geartrain engine stop`
- `geartrain engine status`

## Requirements

- `start` loads and validates `.geartrain/`.
- First implementation may run in the foreground.
- `status` calls the engine API.
- `stop` calls the engine API.

## Acceptance Criteria

- `geartrain engine start` starts the local engine.
- Invalid config makes `start` exit non-zero.
- `geartrain engine status` reports running state when engine is up.
- `geartrain engine stop` stops the engine through the API.
