---
id: GT-P3-06
phase: 3
status: todo
depends_on: 
  - GT-P3-01
  - GT-P2-03
  - GT-P3-03
  - GT-P3-05
---

# Implement geartrain-dev Workflow

Define and run the first workflow on the engine: pick a task, run coder, pass to lead, log a line, stop.

## Scope

- Select a task from `in-progress` or `todo`; move a chosen `todo` task to `in-progress`.
- Run `coder`, pass output to `lead`, append one line to `.geartrain/logs/geartrain-dev.md`.
- Write run state.

## Requirements

- Defined as a `geartrain-dev.workflow.yaml` running on the generic engine, not a hardcoded path.
- No task -> clear message and end; tasks are not auto-moved to `done`.

## Acceptance Criteria

- Workflow runs with fake Codex agents.
- Task selection follows priority order.
- Run state includes task path, coder output, and lead output.
