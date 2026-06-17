# Runnable Version Implementation Spec

This is the detailed contract for the first runnable version of GearTrain — phases 1-3 in [ROADMAP.md](ROADMAP.md). It builds the first executable GearTrain loop around a local engine and the `cli` agent type, with Codex as its first command.

It should prove that GearTrain can load a repo-local workspace, validate it on engine startup, run named agents through Codex CLI non-interactive execution, and run one simple workflow iteration against a task in `work/`.

The runnable version implements the `cli` agent type only — the headless, one-shot runner described in [../docs/07-design-notes.md](../docs/07-design-notes.md#agent-as-an-abstraction). `codex exec` is its default command. The `langchain` agent type is Phase 4; it implements the same `run(task, context) -> str` interface so the workflow doesn't change when it lands.

## Goals

1. Create the Python project backbone.
2. Create the root `work/` implementation driver with task-state folders.
3. Create the `.geartrain/` workspace with config, agents, workflow, and state folders.
4. Add two `cli` agents (default command `codex exec`): `coder` and `lead`.
5. Start a local engine that automatically loads `.geartrain/workspace.yaml`.
6. Validate workspace, agent, and workflow configuration on engine startup.
7. Expose a small HTTP API for direct agent calls, workflow start, run inspection, engine status, and engine shutdown.
8. Add CLI commands that call the engine API.
9. Support a minimal `geartrain-dev` workflow:
   - Pick an `in-progress` task if one exists.
   - Otherwise pick the next task from `work/todo/`.
   - Run `coder` on that task.
   - Pass coder output to `lead`.
   - `lead` writes one line to a workflow summary log.
   - The engine writes structured events for the run.
   - End the workflow.
10. Prevent parallel executions of the same workflow.
11. Treat every workflow execution as a run with nodes, attempts, checkpoints, and append-only events before the MVP dogfooding phase.

## Non-Goals

- No manual prompt-packet bootstrap (removed from the plan entirely).
- No `langchain` agent type in the runnable version — it's Phase 4, built against the same agent interface.
- No web UI or dashboard implementation.
- No memory implementation beyond a placeholder memory manager.
- No GitHub integration.
- No schema-defined workflow inputs or outputs.
- No chat mode.
- No multi-workflow concurrency.
- No cloud or hosted mode.
- No retries, replay, queues, or rich analytics. The MVP architecture stores the run data needed to add them later.

## Project Backbone

Target structure:

```text
pyproject.toml
geartrain/
├── __init__.py
├── cli.py
├── engine/
│   ├── app.py
│   ├── config.py
│   ├── service.py
│   ├── runs.py
│   └── state.py
├── agents/
│   ├── codex.py
│   └── registry.py
├── workflows/
│   ├── geartrain_dev.py
│   └── registry.py
├── work/
│   └── tasks.py
└── memory/
    └── noop.py
tests/
└── ...
```

The exact module split can change during implementation, but the boundaries should stay clear:

- CLI talks to the engine API.
- Engine owns config loading, validation, agent registry, workflow registry, run state, events, and locking.
- Codex agent runner owns `codex exec` invocation.
- Workflow runner owns task selection and handoff between `coder` and `lead`.
- Work task utilities own `todo` / `in-progress` / `done` folder operations.

## Work Folder

The root `work/` folder is not a GearTrain workspace. It is the source of truth for GearTrain implementation work.

Required layout:

```text
work/
├── SPEC.md
├── todo/
├── in-progress/
└── done/
```

Task selection:

1. If `work/in-progress/` contains task files, pick the first task by filename sort.
2. Otherwise pick the first task from `work/todo/` by filename sort.
3. When a task is picked from `todo/`, move it to `in-progress/` before running `coder`.
4. The runnable version does not automatically move tasks to `done/`. The lead or user can do that after review.

## GearTrain Workspace

Required layout:

```text
.geartrain/
├── workspace.yaml
├── engines/
│   └── local.engine.yaml
├── agents/
│   ├── coder.agent.yaml
│   └── lead.agent.yaml
├── workflows/
│   └── geartrain-dev.workflow.yaml
├── state/
│   ├── engine.md
│   ├── workflows/
│   └── runs/
└── logs/
    ├── geartrain-dev.md
    └── geartrain-dev.events.jsonl
```

`workspace.yaml` must define:

- workspace name
- project root
- default work folder path
- agents registry path
- workflows registry path
- state path
- log path

The workspace default work folder is used when a workflow does not set its own `work_folder`.

`geartrain-dev.workflow.yaml` should set:

- workflow name
- `work_folder: work`
- coder agent name
- lead agent name
- log path

## Run-Based Execution Model

A workflow definition is a reusable recipe. A run is one execution of that recipe. The engine records runs as first-class objects so CLI output, APIs, event streams, future dashboards, replay, and debugging all read the same state.

Core objects:

| Object | Purpose |
|--------|---------|
| Workflow definition | YAML recipe that declares nodes, transitions, agents, checkpoints, and integration steps |
| Run | One execution of a workflow definition against one input or task |
| Node run | One workflow node inside a run |
| Attempt | One try at executing a node or agent. Retries are deferred, but the attempt shape exists now |
| Event | Append-only timeline entry emitted by the engine |
| Checkpoint | A run-owned pause waiting for human input or approval |

The runnable version can keep one attempt per node and log-and-stop failure handling. The MVP architecture still writes attempts and events so later retries, replay, dashboards, and metrics don't require a state model rewrite.

Run statuses:

```text
created
running
waiting
completed
failed
canceled
```

Required event types:

```text
run.created
run.started
node.started
attempt.started
agent.started
agent.completed
checkpoint.created
checkpoint.resolved
node.completed
node.failed
run.completed
run.failed
lock.acquired
lock.released
```

Events are append-only. If a later state file disagrees with the event log, the event log is the debugging source of truth.

## Agent Type: cli

The first runnable agent type is `cli` — a headless external CLI agent. Codex is its first command.

When the engine runs a `cli` agent, it calls the configured command in non-interactive mode:

```text
codex exec <prompt>
```

The command is configurable per agent or engine, with `codex exec` as the default.

Agent config should include:

- `name`
- `type: cli`
- `description`
- `system_prompt`
- `cli.command` (default `codex exec`)
- optional `cli.work_folder`
- optional `cli.timeout_seconds`
- optional `cli.sandbox` (passthrough to the CLI's own sandbox/approval mode)

The engine builds the final prompt from:

- agent system prompt
- workspace name
- project root path
- workflow work folder path
- direct user/workflow prompt
- selected task file content, when running the workflow
- previous agent output, when provided

The agent response is plain text. The engine returns it as-is and may also store it in run state.

## Agents

### coder

Purpose: implement one task from the `work/` folder.

The coder prompt must include:

- project root path
- work folder path
- current task path
- current task content
- instruction to update files needed for the task
- instruction to return a concise summary of changed files, tests run, and blockers

### lead

Purpose: create tasks, review coder output, summarize task state, and start workflow iterations through the workflow tool.

The lead prompt must include:

- project root path
- work folder path
- current task folders
- direct user input
- available tool: `workflow start`

The runnable version supports one tool for the lead agent:

```text
workflow start
```

This tool starts the next `geartrain-dev` workflow iteration.

Implementation can use a simple engine-side protocol for tool calls. For example, if the lead response contains this exact line:

```text
GEARTRAIN_TOOL workflow start
```

the engine runs the workflow start action and returns the tool result with the lead response. Only one tool call needs to be supported in the runnable version.

## Engine

The engine is a local long-running process.

Commands:

```text
geartrain engine start
geartrain engine stop
geartrain engine status
```

`geartrain engine start`:

1. Starts the local engine HTTP server.
2. Loads `.geartrain/workspace.yaml` automatically from the project root.
3. Validates all config files.
4. Creates agent registry, workflow registry, noop memory manager, state manager, and workflow lock manager.
5. If validation fails, prints the error and exits non-zero.

The first implementation may run in the foreground. `status` and `stop` communicate through the HTTP API when the engine is running.

## Engine API

Minimum endpoints:

```text
GET  /health
GET  /status
POST /agents/{agent_name}/run
POST /workflows/{workflow_name}/start
GET  /workflows/{workflow_name}/status
GET  /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/events
POST /engine/stop
```

`POST /agents/{agent_name}/run` body:

```json
{
  "prompt": "show tasks"
}
```

Response:

```json
{
  "agent": "lead",
  "output": "plain text response"
}
```

## CLI Wrapper

The CLI talks to the engine API. It should not duplicate engine logic.

Commands:

```text
geartrain engine start
geartrain engine stop
geartrain engine status
geartrain agent <agent-name> "<prompt>"
geartrain workflow start
geartrain run list
geartrain run show <run-id>
geartrain run events <run-id>
```

Examples:

```text
geartrain agent lead "show tasks"
geartrain agent lead "create task for engine startup validation"
geartrain workflow start
geartrain run events 2026-06-17-geartrain-dev-001
```

`geartrain agent` is one-shot. It sends the prompt to the named agent and prints the plain text response. No chat mode.

## Workflow: geartrain-dev

The first workflow is intentionally small.

Flow:

```text
start
  -> acquire workflow lock
  -> create run
  -> append run.created and run.started events
  -> select task from work/in-progress or work/todo
  -> record task selection event
  -> run coder on selected task, with node and attempt events
  -> run lead with coder output, with node and attempt events
  -> append one line to .geartrain/logs/geartrain-dev.md
  -> append structured events to .geartrain/logs/geartrain-dev.events.jsonl
  -> release workflow lock
  -> end
```

If the workflow is already running, the engine returns current status and does not start another run.

If no task exists, the workflow returns a clear message and ends.

## State

State is run-based and file-backed for the MVP architecture.

Suggested files:

```text
.geartrain/state/engine.md
.geartrain/state/workflows/geartrain-dev.md
.geartrain/state/runs/<run-id>/
├── run.md
├── events.jsonl
├── nodes/
│   ├── 01-select-task.md
│   ├── 02-coder.md
│   └── 03-lead.md
├── attempts/
│   ├── attempt-000001.md
│   └── attempt-000002.md
└── checkpoints/
```

State files should be easy to inspect and edit manually. Keep frontmatter direct. The JSONL event file is optimized for append-only reads by the CLI, API, and future UI.

The minimal human-facing outcome log is `.geartrain/logs/geartrain-dev.md`. The minimal machine-readable observability log is `.geartrain/logs/geartrain-dev.events.jsonl`, copied or appended from run events.

## Validation

Validation runs on engine startup and through `geartrain validate`. The command validates every config file the MVP uses: workspace, engine, agent, workflow, and memory.

Validate:

- `.geartrain/workspace.yaml` exists.
- `.geartrain/engines/local.engine.yaml` loads and names credentials as env vars, not raw secrets.
- shared rules on every definition: `schema_version: 1`, `name` matches `^[a-z][a-z0-9-]*$`, `description` present, unknown top-level fields rejected.
- registry paths exist.
- workspace default `work_folder` exists when configured.
- workflow `work_folder` exists when configured.
- every agent config has `type: cli`.
- every `cli` agent has a system prompt.
- the `cli` command is configured (default `codex exec`).
- every workflow references existing agents.
- `geartrain-dev` workflow has a work folder or can use the workspace default.
- state and log directories are writable.
- run directories can be created under the configured state path.

The validator makes no LLM or network calls.

## Acceptance Criteria

The runnable version is complete when:

1. `geartrain engine start` loads and validates `.geartrain/`.
2. Invalid config causes the engine to print a clear error and quit.
3. `geartrain engine status` reports running state.
4. `geartrain agent lead "show tasks"` returns a task summary.
5. `geartrain workflow start` starts one `geartrain-dev` run.
6. A running workflow prevents another parallel run.
7. The workflow picks a task, runs `coder`, passes output to `lead`, writes a summary log line, writes structured run events, and exits.
8. Run state is written under `.geartrain/state/runs/<run-id>/` with `run.md`, `events.jsonl`, node files, and attempt files.
9. No memory implementation is required for the workflow to work.
10. `geartrain run events <run-id>` prints the event timeline for a completed or failed run.
