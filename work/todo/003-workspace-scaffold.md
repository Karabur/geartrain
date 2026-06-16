---
id: GT-M1-003
status: todo
depends_on:
  - GT-M1-001
---

# Create GearTrain Workspace Scaffold

Create the `.geartrain/` workspace required by the first milestone.

## Scope

- Add `.geartrain/workspace.yaml`.
- Add `.geartrain/agents/coder.agent.yaml`.
- Add `.geartrain/agents/lead.agent.yaml`.
- Add `.geartrain/workflows/geartrain-dev.workflow.yaml`.
- Add `.geartrain/state/` folders.
- Add `.geartrain/logs/geartrain-dev.md`.

## Requirements

- Workspace is separate from the root `work/` folder.
- Workspace config includes the default local `work_folder` path.
- `geartrain-dev.workflow.yaml` includes `work_folder: work`.
- Both agents use `type: cli` with `cli.command` defaulting to `codex exec`.
- Workflow references only `coder` and `lead`.

## Acceptance Criteria

- Workspace files are present and readable.
- Agent names match workflow references.
- Config paths are relative to project root.
