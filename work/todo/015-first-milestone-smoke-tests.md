---
id: GT-M1-015
status: todo
depends_on:
  - GT-M1-006
  - GT-M1-008
  - GT-M1-011
  - GT-M1-012
  - GT-M1-013
  - GT-M1-014
---

# Add First Milestone Smoke Tests

Add end-to-end smoke tests for the first executable GearTrain loop.

## Scope

- Test engine startup with valid workspace.
- Test startup failure with invalid workspace.
- Test direct lead agent call with fake Codex runner.
- Test workflow start with fake Codex runner.
- Test workflow lock behavior.
- Test state/log files are written.

## Requirements

- Tests must not call real Codex CLI.
- Tests should use temporary project directories.
- Tests should verify files, not only return values.

## Acceptance Criteria

- Smoke tests pass without network access.
- Smoke tests pass without real Codex installed.
- Tests cover the milestone acceptance criteria in `work/SPEC.md`.
