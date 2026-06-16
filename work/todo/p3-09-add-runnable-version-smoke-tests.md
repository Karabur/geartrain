---
id: GT-P3-09
phase: 3
status: todo
depends_on: 
  - GT-P3-06
  - GT-P3-07
  - GT-P3-08
---

# Add Runnable-Version Smoke Tests

End-to-end smoke tests for the first runnable GearTrain loop.

## Scope

- Test engine startup (valid + invalid), direct lead call, workflow start, lock behavior, and state/log writes.

## Requirements

- Tests use temporary project dirs, no real Codex, no network.
- Tests verify files, not only return values.

## Acceptance Criteria

- Smoke tests pass offline and cover the acceptance criteria in `work/SPEC.md`.
