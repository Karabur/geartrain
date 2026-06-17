---
id: GT-P3-05
phase: 3
status: todo
depends_on: 
  - GT-P1-05
  - GT-P3-04
---

# Implement Workflow Locking

Prevent parallel executions of the same workflow.

## Scope

- Per-workflow lock; check before start, release on end.
- Report status if already running.

## Requirements

- One local engine process for MVP; stale-lock recovery can be manual.

## Acceptance Criteria

- Starting a running workflow returns status without a second run.
- Lock releases after success and after a handled failure.
