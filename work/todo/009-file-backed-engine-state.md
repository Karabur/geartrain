---
id: GT-M1-009
status: todo
depends_on:
  - GT-M1-004
---

# Implement File-Backed Engine State

Persist engine, workflow, and run state as markdown files under `.geartrain/state/`.

## Scope

- Write `.geartrain/state/engine.md`.
- Write `.geartrain/state/workflows/geartrain-dev.md`.
- Write `.geartrain/state/runs/<run-id>/run.md`.
- Write agent outputs into run folders.

## Requirements

- State files should be human-readable.
- Frontmatter should be minimal.
- State writes should be simple and robust.

## Acceptance Criteria

- Engine startup writes current engine state.
- Workflow start writes a run folder.
- Agent outputs are saved as markdown files.
- Tests can read state back from files.
