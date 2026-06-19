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
workflow-agnostic: the engine provides only generic config and runtime layers,
and every workflow — including geartrain-dev — is defined entirely in
`.geartrain/`. The engine must know no workflow by name.

This restores GT-P3-06's stated requirement ("running on the generic engine, not
a hardcoded path"), which the implementation drifted from. It is a prerequisite
for the rest of Phase 8 and must land first.

## Problem

`geartrain/workflows/geartrain_dev.py` encodes one workflow's trigger and task
lifecycle (scan `work/todo`, move `todo → in-progress`, feed task content as
`trigger.task`, write logs) as a named source module. The engine's only start
path routes through it: `workflow_start` in `geartrain/engine/service.py` calls
`run_geartrain_dev` for any workflow name, so the task-folder policy is forced on
every workflow. The name `geartrain-dev` is hardcoded in `service.py` (the agent
workflow-start tool handler) and `cli.py` (`_run_workflow_start` default).

Separately, `repo_root`, state, and log paths are relative and resolve against
the process working directory at I/O time, so a start request from the wrong
directory mutates whatever repo is the cwd (the root cause behind the two
test-isolation fixes in the P7 commit).

## Trigger model (for now)

The only trigger is running the workflow. Starting a workflow instantiates it and
runs it from its entry node — there is no trigger abstraction, no `work_queue`
type, and no task-folder scanning in source. Task selection (`work/todo` →
`in-progress`) is geartrain-dev-specific workspace behavior; it does not belong in
the engine and is out of scope here. Phase 8 (`GT-P8-02`) defines how the
dogfooding workflow selects work, as config or workflow nodes, not source.

## Scope

- Add a generic start path: given a workflow name, resolve the workflow and run
  the generic `WorkflowRunner` from its entry node. Accept an optional task
  string from the caller (request body / CLI), which seeds `trigger.task`;
  default empty. No workflow is named in source.
- Update `workflow_start` and the agent workflow-start tool handler in
  `service.py` to use the generic start; drop the `run_geartrain_dev` import and
  the `"geartrain-dev"` literals.
- Update the CLI: `geartrain workflow start <name>` takes the workflow name as a
  positional argument; remove the `"geartrain-dev"` default.
- Resolve `repo_root` and the derived state/log paths to absolute paths at engine
  load, anchored to the config file location, so runtime I/O does not depend on
  cwd.
- Move run logging (the human `.md` log and the machine-readable `.events.jsonl`
  log) into the generic run path or the state backend, so any workflow gets it.
  Then delete `geartrain/workflows/geartrain_dev.py`.
- Keep the `trigger:` field in workflow YAML as declarative metadata. Config
  validation accepts known trigger types and rejects unknown ones.
- Leave `geartrain/work/tasks.py` in place for a future node-based approach, but
  the engine start path must no longer call it.

## Requirements

- The engine knows no workflow by name. geartrain-dev is purely `.geartrain/`
  config plus the generic runtime.
- Starting a workflow runs it from its entry node and is independent of the
  working directory.
- Run logging is preserved for any workflow: both the human `.md` and the
  machine-readable `.events.jsonl` logs. P7 observability outputs are unchanged.
- Follow `WRITING_STYLE.md` for all comments and docs.

## Acceptance Criteria

- No source file under `geartrain/` references `geartrain-dev` or `geartrain_dev`
  by name (grep is clean); `geartrain_dev.py` is gone. The string may remain in
  `.geartrain/` config and `work/` only.
- A second, differently named workflow with a `manual` trigger starts and runs
  from its entry node through the generic path, without touching `work/`.
- Starting a workflow no longer depends on the working directory; the
  `monkeypatch.chdir` workarounds in `test_http_service.py` and
  `test_workflow_runnable.py` are removed and those tests pass via absolute paths.
- The suite causes no repo mutation: after a full run, `.geartrain/state/runs/`
  has no new dated run dirs and `.geartrain/logs/` is git-clean.
- New tests cover the generic start path (including a second named workflow) and
  cwd-independent path resolution. The full suite is green.
