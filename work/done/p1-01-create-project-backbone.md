---
id: GT-P1-01
phase: 1
status: todo
depends_on: []
---

# Create Project Backbone

Create the Python package, CLI entrypoint, and test skeleton.

## Scope

- Add `pyproject.toml` exposing a `geartrain` CLI command.
- Add `geartrain/` package with empty engine, agents, workflows, work, and memory modules.
- Add `tests/` with an import/CLI smoke test.

## Requirements

- CLI uses the `geartrain <module> <command>` / `geartrain <global-command>` shape from the start.
- No engine behavior required in this task.

## Acceptance Criteria

- `geartrain --help` works.
- `pytest` runs at least one smoke test.
- Structure matches the boundaries in `work/SPEC.md`.
