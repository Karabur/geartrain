---
id: GT-P3-01
phase: 3
status: todo
depends_on: 
  - GT-P1-01
---

# Implement Work Folder Task Helpers

Read and move implementation task files in the root `work/` folder.

## Scope

- Locate `work/todo|in-progress|done/`.
- Deterministic task selection sorted by filename.
- Move helper from `todo` to `in-progress`; task-list helper for the lead prompt.

## Requirements

- `in-progress` has priority over `todo`.
- Helpers must not inspect `.geartrain/` task state.

## Acceptance Criteria

- Tests cover empty folders, selecting an in-progress task, selecting+moving the first todo, and list output.
