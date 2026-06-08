---
id: GT-M1-010
status: todo
depends_on:
  - GT-M1-009
---

# Implement Workflow Locking

Prevent multiple parallel executions of the same workflow.

## Scope

- Add a lock for `geartrain-dev`.
- Check lock before starting a workflow.
- Release lock when workflow ends.
- Report status if workflow is already running.

## Requirements

- Lock is per workflow.
- First milestone only needs one local engine process.
- Stale lock recovery can be simple and manual.

## Acceptance Criteria

- Starting a running workflow returns status and does not start another run.
- Lock is released after successful completion.
- Lock is released after handled failure.
- State file shows running/completed status.
