---
id: GT-P1-04
phase: 1
status: todo
depends_on: 
  - GT-P1-02
  - GT-P1-03
---

# Implement Config Validation and `geartrain validate`

Validate all MVP config files on startup and via a `geartrain validate` command.

## Scope

- Validate shape (required fields, types, enums, `schema_version: 1`, `name` regex, reject unknown top-level fields).
- Validate references (agents/workflows/paths/credentials exist) and runtime readiness (paths writable, command present).
- Add `geartrain validate [workspace|engine|agent|workflow|memory|all]` with file/field/severity/fix diagnostics.

## Requirements

- Validation covers every config file used in the MVP: workspace, engine, agent, workflow, memory.
- Startup runs `validate all`; invalid config prints a clear error and exits non-zero.
- Validator makes no LLM or network calls.

## Acceptance Criteria

- Tests cover: missing workspace, missing referenced agent, invalid agent type, missing work folder, bad `schema_version`/`name`, unknown field, valid scaffold passing.
- `geartrain validate all` reports actionable diagnostics with file paths.
