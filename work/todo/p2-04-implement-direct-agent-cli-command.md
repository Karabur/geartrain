---
id: GT-P2-04
phase: 2
status: todo
depends_on: 
  - GT-P1-06
  - GT-P2-03
---

# Implement Direct Agent CLI Command

Add `geartrain agent <name> "<prompt>"` as a one-shot wrapper over the engine API.

## Scope

- Send the prompt to `POST /agents/{name}/run`; print the plain text response.

## Requirements

- No chat mode; CLI only calls the engine API.

## Acceptance Criteria

- `geartrain agent lead "show tasks"` calls the lead agent.
- Output prints without a JSON wrapper.
- Unknown agent returns a clear error.
