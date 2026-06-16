---
id: GT-P1-02
phase: 1
status: done
depends_on: 
  - GT-P1-01
---

# Create Workspace and Engine Config Scaffold

Create the `.geartrain/` workspace and the local engine config used by the MVP.

## Scope

- Add `.geartrain/workspace.yaml`, `agents/coder.agent.yaml`, `agents/lead.agent.yaml`, `workflows/geartrain-dev.workflow.yaml`.
- Add `.geartrain/engines/local.engine.yaml` with host, port, providers, credentials, state backend, resources, tool roots.
- Add `.geartrain/state/` folders and `.geartrain/logs/geartrain-dev.md`.

## Requirements

- All definition files carry `schema_version: 1`, a `name` matching `^[a-z][a-z0-9-]*$`, and a `description`.
- Both agents use `type: cli` with `cli.command` defaulting to `codex exec`.
- Workflow references only `coder` and `lead`; config paths are relative to repo root.
- Engine config names provider credentials as env vars, never raw secrets; `state.backend: files`.

## Acceptance Criteria

- Workspace, engine, agent, and workflow files are present and readable.
- Agent names match workflow references.
- Engine config resolves the workspace path.
