# GearTrain - UI and Observability Spec

GearTrain's UI is a run inspector first. It should help a developer understand what happened, what is happening now, what needs human input, and what changed in the workspace.

This document defines the post-MVP UI target. The MVP does not ship dashboards. It ships the run, event, checkpoint, tool-call, memory-update, and API architecture needed for these screens to work.

## Product Intent

The primary user is a developer or product-owner developer running GearTrain on a local project. They open the UI when a workflow is running, blocked, failed, or ready for review.

The interface should feel like an operations console for agent work: dense, calm, inspectable, and fast. It should favor timelines, traces, diffs, and status over marketing-style cards.

The signature UI pattern is the run trace: a vertical execution timeline where each node opens into attempts, tool calls, memory writes, logs, output, timing, and errors. Everything else supports that inspector.

## MVP Boundary

MVP includes:

- Run-owned state files.
- Append-only run events.
- Minimal human-facing workflow log.
- Minimal machine-readable event log.
- Run query API.
- Checkpoint response API.
- Event streaming API shape.
- CLI commands for listing runs and printing event timelines.

MVP does not include:

- React dashboard.
- Visual workflow editor.
- Drag-and-drop workflow builder.
- Rich analytics dashboards.
- Hosted auth or multi-user UI.
- Replay UI.

Post-MVP includes the full UI described below.

## Information Architecture

The app has six main areas.

| Area | Purpose |
|------|---------|
| Runs | List workflow executions, status, duration, task, current node, and failure summary |
| Run Detail | Inspect one run's timeline, nodes, attempts, checkpoints, outputs, events, and errors |
| Workflows | Inspect workflow definitions, node graph, current active run, and recent run history |
| Checkpoints | Resolve pending human approvals and input requests |
| Memory | Browse memory entries, memory writes, source run, scope, and review status |
| Settings | Engine status, workspace config, integrations, provider readiness, and local paths |

The default screen is Runs, not a landing page.

## Run List

The run list is the operating surface.

Required columns:

- Status
- Workflow
- Run ID
- Task or trigger input
- Current node
- Started
- Duration
- Agent count
- Tool call count
- Memory write count
- Error summary

Required filters:

- Status: running, waiting, completed, failed, canceled
- Workflow
- Agent
- Node
- Has pending checkpoint
- Has memory writes
- Has tool failures
- Time range
- Text search across task, run ID, node ID, and error summary

Required actions:

- Open run
- Copy run ID
- Cancel running run
- Replay run after replay exists
- Open event log

## Run Detail

Run Detail explains one execution.

Header:

- Workflow name
- Run status
- Task path or trigger payload summary
- Started, finished, duration
- Current node
- Definition version or hash
- Agent/model summary when available
- Primary error when failed

Main trace:

- One row per node run.
- Rows show node status, node type, agent, duration, attempt count, output key, and error state.
- Expanding a row shows attempts, tool calls, memory updates, logs, output, and raw events for that node.

Side panel:

- Run metadata
- Input payload
- Selected task file
- Workflow definition link
- Agent definitions used by the run
- Event counts
- Timing summary

The trace should make waiting states obvious. A pending checkpoint should appear inline at the node that created it and also in the Checkpoints area.

## Node and Attempt Detail

Node detail shows how one step behaved.

Required sections:

- Node input after variable resolution
- Agent prompt sections after context assembly
- Attempt timeline
- Output text
- Tool calls
- Memory reads
- Memory writes
- Errors and stack traces
- Timing

Attempt detail shows one try at executing a node.

Required fields:

- Attempt ID
- Node ID
- Agent name
- Runner type: `cli`, `langchain`, `sdk`, or `cloud`
- Command or provider metadata when available
- Started, finished, duration
- Status
- Error summary
- Raw output

Retries are not MVP, but the UI should already render multiple attempts because the run model supports them.

## Checkpoints

Checkpoint screens handle human input.

Required views:

- Pending checkpoints
- Resolved checkpoints
- Timed-out checkpoints
- Checkpoint history by run

Checkpoint detail shows:

- Prompt
- Mode: approval or input
- Allowed responses when constrained
- Related workflow, run, and node
- Context needed to decide
- Prior agent output
- Response form

Actions:

- Approve
- Reject
- Submit input
- Open run detail

## Tool Calls

Tool calls should be visible as first-class execution records.

Required fields:

- Tool name
- Tool category
- Node ID
- Attempt ID
- Input summary
- Output summary
- Started, finished, duration
- Status
- Error summary
- Retry count when available

The first UI version can show tool calls inside Run Detail. A dedicated Tool Calls view can follow once there is enough volume.

## Memory Updates

Memory updates need reviewable provenance.

Required fields:

- Memory entry path
- Scope
- Source run
- Source node
- Source agent
- Created or updated time
- Review status
- Diff or content preview
- Secret guardrail result

Required actions:

- Open memory entry
- Open source run
- Mark reviewed
- Mark rejected

The UI must distinguish durable memory from run-local state. Run-local outputs are evidence. Memory entries are reusable project knowledge.

## Errors and Timing

Errors should be grouped by the thing that failed:

- Workflow failure
- Node failure
- Agent failure
- Tool failure
- Memory write failure
- Integration failure
- Checkpoint timeout
- Engine/system failure

Timing should show:

- Run duration
- Queue/wait time when available
- Node duration
- Attempt duration
- Tool duration
- Time waiting for human input
- Slowest nodes

The first dashboard should answer: which runs failed, where they failed, how long they took, and what changed.

## Event Stream Contract

The UI reads the same event stream as the CLI.

Minimum event fields:

- `schema_version`
- `event_id`
- `run_id`
- `type`
- `created_at`
- `workflow`
- `node_id`
- `attempt_id`
- `checkpoint_id`
- `tool_call_id`
- `memory_entry`
- `level`
- `message`
- `data`

Required event groups:

- Run lifecycle
- Lock lifecycle
- Node lifecycle
- Attempt lifecycle
- Agent lifecycle
- Checkpoint lifecycle
- Tool lifecycle
- Memory lifecycle
- Error lifecycle

Events are append-only. State summaries can be rebuilt from events if needed.

## API Surface

The UI needs these API groups.

Runs:

```text
GET /api/runs
GET /api/runs/{run_id}
GET /api/runs/{run_id}/events
GET /api/runs/{run_id}/nodes
GET /api/runs/{run_id}/attempts
POST /api/runs/{run_id}/cancel
POST /api/runs/{run_id}/replay
```

Workflows:

```text
GET /api/workflows
GET /api/workflows/{workflow_id}
POST /api/workflows/{workflow_id}/start
```

Checkpoints:

```text
GET /api/checkpoints
GET /api/checkpoints/{checkpoint_id}
POST /api/checkpoints/{checkpoint_id}/respond
```

Memory:

```text
GET /api/memory
GET /api/memory/{scope}
GET /api/memory-updates
POST /api/memory/{entry_id}/review
```

Engine:

```text
GET /api/engine/status
GET /api/engine/readiness
```

Streaming:

```text
GET /api/runs/{run_id}/stream
GET /api/events/stream
```

SSE is enough for the first implementation. WebSockets are useful once the UI needs bidirectional runtime interaction beyond checkpoint responses.

## Visual Direction

The UI should be compact and work-focused.

Layout:

- Left navigation with Runs, Workflows, Checkpoints, Memory, Settings.
- Main content uses tables, traces, split panes, and inspectors.
- Run Detail uses a trace column plus a right inspector panel.
- Cards are only for repeated run summaries, modal content, and bounded inspectors.

Controls:

- Status filters use segmented controls.
- Time range uses a compact menu.
- Search is prominent on run and memory lists.
- Icon buttons should use familiar symbols for copy, replay, cancel, open, filter, and refresh.
- Checkpoint actions are explicit text buttons because they are decisions.

Visual tone:

- Muted technical palette.
- Semantic colors only for status.
- Clear typography hierarchy.
- Small, dense tables with readable row heights.
- Subtle borders instead of heavy shadows.

Accessibility:

- Keyboard navigation for lists, filters, trace expansion, and checkpoint actions.
- Visible focus states.
- Status never relies on color alone.
- Error summaries are text-first.

## Build Order

1. Run list and run detail from seeded file-backed run state.
2. Event streaming into Run Detail.
3. Checkpoint list and response flow.
4. Memory browser and memory update review.
5. Tool call and timing inspectors.
6. Replay and cancellation controls.
7. Cross-run observability dashboards.

The UI should never invent state. If the run store doesn't expose a fact, the UI should show it as unavailable and drive a backend task to add it.
