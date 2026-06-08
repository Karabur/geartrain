---
id: GT-M1-001
status: todo
depends_on: []
---

# Create Project Backbone

Create the Python package, CLI entrypoint, and test skeleton needed for the first milestone.

## Scope

- Add `pyproject.toml`.
- Add `geartrain/` package.
- Add `geartrain/cli.py`.
- Add empty engine, agents, workflows, work, and memory modules.
- Add `tests/` with a basic import/CLI smoke test.

## Requirements

- Package exposes a `geartrain` CLI command.
- CLI can print help.
- Tests can import the package.
- No engine behavior is required in this task.

## Acceptance Criteria

- `geartrain --help` works in the development environment.
- `pytest` runs at least one smoke test.
- Project structure matches the boundaries in `work/SPEC.md`.
