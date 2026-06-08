---
id: GT-M1-002
status: todo
depends_on:
  - GT-M1-001
---

# Implement Work Folder Task Helpers

Implement helpers for reading and moving implementation task files in the root `work/` folder.

## Scope

- Add utilities for locating `work/todo/`, `work/in-progress/`, and `work/done/`.
- Add deterministic task selection.
- Add move helper from `todo` to `in-progress`.
- Add task listing helper for the lead agent.

## Requirements

- `in-progress` tasks have priority over `todo` tasks.
- Task selection is sorted by filename.
- Helpers must not inspect `.geartrain/` workspace task state.

## Acceptance Criteria

- Tests cover empty task folders.
- Tests cover selecting an existing `in-progress` task.
- Tests cover selecting and moving the first `todo` task.
- Tests cover task list output for lead prompts.
