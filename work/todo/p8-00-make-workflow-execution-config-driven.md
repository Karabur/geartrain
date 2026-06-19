---
id: GT-P8-00
phase: 8
status: todo
depends_on:
  - GT-P3-06
  - GT-P7-06
---

# Make Workflow Execution Config-Driven

Remove the hardcoded geartrain-dev workflow path from source. GearTrain must be
workflow-agnostic: the engine provides the config and runtime layers, and every
workflow — including geartrain-dev — is defined entirely in `.geartrain/`.

This restores GT-P3-06's stated requirement ("running on the generic engine, not
a hardcoded path"), which the implementation drifted from. It is a prerequisite
for the rest of Phase 8 and must land first.

## Problem

`geartrain/workflows/geartrain_dev.py` encodes one workflow's trigger and task
lifecycle (scan `work/todo`, move `todo → in-progress`, feed task content as
`trigger.task`, write logs) as a named source module. The engine's only start
path routes through it: `workflow_start` in `geartrain/engine/service.py:185`
calls `run_geartrain_dev` for any workflow name, so the task-folder policy is
forced on every workflow. The name `geartrain-dev` is hardcoded in
`service.py:110`, `cli.py:199`, and the agent workflow-start tool handler.

Separately, `repo_root`, state, and log paths are relative and resolve against
the process working directory at I/O time, so a start request from the wrong
directory mutates whatever repo is the cwd (the root cause behind the two
test-isolation fixes in the P7 commit).

## Scope

- Add a generic trigger abstraction. A workflow declares where its trigger input
  comes from in its YAML. Introduce a `work_queue` trigger type alongside
  `manual`:

  ```yaml
  trigger:
    type: work_queue
    path: work
  ```

  A generic resolver builds the trigger payload: `manual` takes the task from the
  request/CLI; `work_queue` scans `<path>/in-progress` then `<path>/todo`, moves
  the chosen `todo` task to `in-progress`, and sets `trigger.task` to its
  content. No task → `no_tasks` status and a clear message; tasks are never
  auto-moved to `done`.
- Add a generic engine entry point that, given a workflow name, resolves the
  workflow, resolves its trigger, builds the payload, and runs `WorkflowRunner`.
  No workflow is named in source.
- Update `workflow_start` and the agent workflow-start tool handler in
  `service.py` to use the generic entry; drop the `run_geartrain_dev` import and
  the `"geartrain-dev"` literals.
- Update the CLI: `geartrain workflow start <name>` takes the workflow name as a
  positional argument; remove the `"geartrain-dev"` default.
- Resolve `repo_root` and the derived state/log paths to absolute paths at engine
  load, anchored to the config file location, so runtime I/O does not depend on
  cwd.
- Move the human and JSONL log writing into the generic run path (or the state
  backend) and delete `geartrain/workflows/geartrain_dev.py`.
- Declare the `work_queue` trigger in
  `.geartrain/workflows/geartrain-dev.workflow.yaml`.
- Extend config validation to accept known trigger types and reject unknown ones.

## Requirements

- The engine knows no workflow by name. geartrain-dev is purely `.geartrain/`
  config plus the generic runtime.
- Behavior is preserved: task-selection priority (in-progress before todo), the
  `todo → in-progress` move, no auto-move to `done`, the no-task message, and
  both the human (`.md`) and machine-readable (`.events.jsonl`) logs.
- Path resolution is independent of the working directory.
- Follow `WRITING_STYLE.md` for all comments and docs.

## Acceptance Criteria

- No source file under `geartrain/` references `geartrain-dev` or `geartrain_dev`
  by name (grep is clean); `geartrain_dev.py` is gone.
- A second, differently named workflow with a `manual` trigger starts and runs
  through the generic path without touching `work/`.
- The `work_queue` trigger drives geartrain-dev exactly as before; observability
  and log outputs are unchanged.
- Starting a workflow no longer depends on the working directory; once paths are
  absolute, the `monkeypatch.chdir` workarounds in `test_http_service.py` and
  `test_workflow_runnable.py` can be removed.
- New tests cover trigger resolution (`manual` and `work_queue`), the generic
  start path, and cwd-independent path resolution. The full suite is green.
