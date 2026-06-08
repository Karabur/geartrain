---
id: GT-M1-004
status: todo
depends_on:
  - GT-M1-001
  - GT-M1-003
---

# Implement Config Loading And Startup Validation

Load `.geartrain/workspace.yaml` on engine startup and validate all first-milestone config files.

## Scope

- Parse workspace YAML.
- Parse agent YAML files.
- Parse workflow YAML files.
- Validate required paths and references.
- Return clear startup errors.

## Requirements

- No separate `geartrain validate` CLI command is required.
- Validation runs when `geartrain engine start` starts.
- Invalid config prints a clear error and exits non-zero.
- Validation does not call Codex or external services.

## Acceptance Criteria

- Tests cover missing workspace file.
- Tests cover missing agent referenced by workflow.
- Tests cover invalid agent type.
- Tests cover missing work folder.
- Tests cover workflow `work_folder` overriding the workspace default.
- Tests cover valid scaffold loading successfully.
