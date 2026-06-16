---
id: GT-P1-05
phase: 1
status: todo
depends_on: 
  - GT-P1-03
---

# Implement File-Backed Engine and Run State

Persist engine, workflow, and run state as markdown files under `.geartrain/state/`.

## Scope

- Write `state/engine.md`, `state/workflows/geartrain-dev.md`, `state/runs/<run-id>/run.md`.
- Write per-node/agent outputs as markdown into run folders.

## Requirements

- State files are human-readable with minimal frontmatter.
- Writes are simple and robust.

## Acceptance Criteria

- Startup writes engine state.
- Workflow start writes a run folder.
- Tests read state back from files.
