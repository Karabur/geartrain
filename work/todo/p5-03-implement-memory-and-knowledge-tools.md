---
id: GT-P5-03
phase: 5
status: todo
depends_on: 
  - GT-P5-02
---

# Implement Memory and Knowledge Tools

Expose memory as agent tools.

## Scope

- Add `memory_read`, `memory_write`, `kb_read`, `kb_write`.
- `cli` agents get memory injected as prompt text (no live write); `langchain` agents get live tools.

## Requirements

- Tool write scopes must be a subset of the agent's allowed scopes.

## Acceptance Criteria

- Tests: a langchain agent writes a memory; a later run retrieves it.
