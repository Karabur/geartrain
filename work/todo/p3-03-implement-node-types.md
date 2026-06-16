---
id: GT-P3-03
phase: 3
status: todo
depends_on: 
  - GT-P3-02
---

# Implement Node Types

Implement the four MVP node types behind the workflow engine.

## Scope

- `agent` (runs an agent), `decision` (deterministic routing), `human_checkpoint` (CLI approve/input), `integration` (stub until Phase 6).
- Each node produces a plain text output stored in run state.

## Requirements

- `human_checkpoint` pauses, emits a checkpoint, and resumes on CLI response.
- Transition targets must reference an existing node or `end`.

## Acceptance Criteria

- Tests run agent -> decision -> agent and an agent -> checkpoint -> agent flow with mocked input.
- Run state stores each node response as markdown.
