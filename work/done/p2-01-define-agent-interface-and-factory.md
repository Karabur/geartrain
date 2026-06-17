---
id: GT-P2-01
phase: 2
status: done
depends_on: 
  - GT-P1-06
---

# Define Agent Interface and Factory

Add the shared `run(task, context) -> str` interface and an `AgentFactory` that dispatches on `type`.

## Scope

- Define the agent interface.
- Implement `AgentFactory`; `cli` returns the subprocess runner.
- Reserve the `langchain` branch for the next phase behind the same interface.

## Requirements

- The workflow layer only ever sees `run(task, context) -> str`.
- Factory dispatch is the single place agent types are selected.

## Acceptance Criteria

- Tests build a `cli` agent from YAML through the factory.
- Unknown type returns a clear error.
