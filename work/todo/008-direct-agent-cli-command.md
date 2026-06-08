---
id: GT-M1-008
status: todo
depends_on:
  - GT-M1-005
  - GT-M1-007
---

# Implement Direct Agent CLI Command

Add a one-shot CLI wrapper for running a named agent through the engine.

## Scope

- Add `geartrain agent <agent-name> "<prompt>"`.
- Send prompt to `POST /agents/{agent_name}/run`.
- Print the plain text response.

## Requirements

- No chat mode.
- No local agent execution in the CLI.
- CLI should only call the engine API.

## Acceptance Criteria

- `geartrain agent lead "show tasks"` calls the lead agent.
- Agent output prints without JSON wrapper by default.
- Unknown agent returns a clear error.
