---
id: GT-M1-011
status: todo
depends_on:
  - GT-M1-002
  - GT-M1-007
  - GT-M1-009
  - GT-M1-010
---

# Implement GearTrain Dev Workflow Runner

Implement the first workflow: pick one task, run coder, pass output to lead, write a log line, and stop.

## Scope

- Select task from `work/in-progress/` or `work/todo/`.
- Move selected `todo` task to `in-progress/`.
- Run `coder` with task content.
- Run `lead` with coder output.
- Append one line to `.geartrain/logs/geartrain-dev.md`.
- Write run state.

## Requirements

- If no task exists, return a clear message and end.
- Workflow output is plain text.
- Lead output decides the log line content.
- Workflow does not move tasks to `done` automatically.

## Acceptance Criteria

- Workflow runs with fake Codex agents in tests.
- Task selection follows the required priority.
- Coder output is passed to lead.
- Log file receives one line.
- Run state includes task path, coder output, and lead output.
