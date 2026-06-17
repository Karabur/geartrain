# GearTrain - MVP Definition Contracts

GearTrain needs stable definition contracts before validation can mean anything. This document defines the first YAML contracts the MVP should load, validate, and execute.

The goal is not to model every future feature. The goal is to make the first local engine strict enough to catch bad configuration before runtime.

## Contract Principles

Definitions are project files. They must be readable in git, reviewable in PRs, and portable between engines.

Validation should check three levels:

1. **Shape** - required fields, field types, allowed enum values.
2. **References** - agents, workflows, tools, memory paths, channels, and integrations exist.
3. **Runtime readiness** - the selected engine can actually run the referenced providers, tools, paths, and integrations.

The first validator should not call LLM providers or external services. It should validate local files and report missing runtime requirements as actionable diagnostics.

## File Types

| File | Default path | Purpose |
|------|--------------|---------|
| Workspace config | `.geartrain/workspace.yaml` | Project-local workspace, registries, memory roots, integration references |
| Engine config | `.geartrain/engines/local.engine.yaml` or user config path | Local runtime settings and per-user provider connections |
| Agent definition | `.geartrain/agents/*.agent.yaml` | Reusable agent role, model hints, tools, prompts, guardrails |
| Workflow definition | `.geartrain/workflows/*.workflow.yaml` | Directed workflow graph with agent, decision, checkpoint, integration, and memory nodes |
| Memory entry | `.geartrain/memory/**/*.md` | Human-readable memory or knowledge entry with frontmatter |
| Run state | `.geartrain/state/runs/**/*` | File-backed run metadata, node runs, attempts, checkpoints, and append-only events |

## Shared Rules

All YAML definition files use these common fields:

```yaml
schema_version: 1
name: example-name
description: "Short human-readable description"
```

Validation rules:

- `schema_version` is required and must be `1` for MVP.
- `name` is required, unique within its registry, and must match `^[a-z][a-z0-9-]*$`.
- `description` is required for workspace, agent, and workflow definitions.
- Unknown top-level fields should fail validation unless the schema explicitly allows extension fields.
- Environment references use `${env.NAME}`.
- Cross-definition references use explicit namespaces such as `${workspace.name}`, `${engine.llm.default}`, or `${nodes.intake.output}`.

## Workspace Config

The workspace config is the repo-local source of truth for the project GearTrain should load by default.

```yaml
schema_version: 1
name: geartrain-core
description: "GearTrain core development workspace"

project:
  name: GearTrain
  repo_root: "."
  knowledge_base:
    - docs/
    - references/

llm:
  default_provider: anthropic
  default_model: claude-sonnet-4
  model_hints:
    reasoning: claude-opus-4
    code: claude-sonnet-4
    fast: claude-haiku-4
    summarize: claude-haiku-4

registries:
  agents: .geartrain/agents
  workflows: .geartrain/workflows

memory:
  root: .geartrain/memory
  workspace: .geartrain/memory/workspace
  workflows: .geartrain/memory/workflows
  agent_types: .geartrain/memory/agent-types

integrations:
  github:
    owner: geartrain
    repo: geartrain
    credential: github.default
```

Validation rules:

- Registry and memory paths must be inside the repository.
- Registry paths must exist for `validate workspace`.
- Knowledge base paths may point to files or directories.
- `llm.default_provider` and every model hint are names only. Credentials stay in engine config.
- Integration credentials are references, not raw tokens.

Deferred:

- Hosted team IDs.
- Users, roles, and invitations.
- Cross-repo workspace discovery.
- Workspace inheritance.

## Engine Config

The engine config belongs to the developer or runtime host. It resolves local credentials and runtime limits.

```yaml
schema_version: 1
name: local-dev
description: "Local developer engine"
type: local

host: 127.0.0.1
port: 8420

workspace:
  path: .geartrain/workspace.yaml

llm:
  default: anthropic
  providers:
    anthropic:
      api_key_env: ANTHROPIC_API_KEY
    openai:
      api_key_env: OPENAI_API_KEY

credentials:
  github:
    default:
      token_env: GITHUB_TOKEN

state:
  backend: files
  path: .geartrain/state

resources:
  max_concurrent_workflows: 1
  max_concurrent_agents: 1

tools:
  shell:
    cwd: "."
    allow_network: true
    timeout_seconds: 120
  filesystem:
    root: "."
```

Validation rules:

- `type` must be `local` for MVP.
- `workspace.path` must resolve to a valid workspace config.
- `state.backend` must be `files` for the runnable version.
- State may live inside the workspace only when the backend is `files` or `sqlite`.
- File-backed state must be stored as markdown files under the configured state path.
- Provider credential fields must name environment variables, not contain secret values.
- Tool roots must stay inside the project repo unless the user explicitly opts into broader access.

Deferred:

- SQLite state backend.
- Cloud engines.
- Serverless engines.
- Shared credential provisioning.
- Multiple concurrent workflow runs.

## Agent Definition

An agent definition describes a reusable role. It does not define workflow routing.

The `type` field selects the implementation and decides which config block is required. MVP supports two types, `langchain` and `cli`. They share a core (`schema_version`, `name`, `description`, `system_prompt`, `memory`) and diverge on the rest: a `langchain` agent carries `llm` and `tools`; a `cli` agent carries a `cli` block and no `tools` (the external CLI brings its own).

### `langchain` agent

```yaml
schema_version: 1
name: coder
description: "Implements approved code changes"
type: langchain

llm:
  model_hint: code
  temperature: 0.2
  routes:
    plan: reasoning
    summarize: summarize

system_prompt: |
  You are a senior software engineer working on ${workspace.project.name}.
  Follow the workspace memory and project documentation.

tools:
  - file_read
  - file_write
  - project_search
  - shell_exec
  - git_status
  - memory_read
  - memory_write

context:
  budget_tokens: 12000
  retrieval:
    memory_top_k: 6
    knowledge_top_k: 8
    require_source_refs: true
  tools:
    mode: static
    categories: []

memory:
  read:
    - workspace
    - workflow
    - agent_level
  write:
    - workflow
  agent_type: coder

guardrails:
  forbidden_paths:
    - ".env"
    - ".env.*"
    - "secrets/**"
  max_files_changed: 20
  require_tests: true

runtime:
  timeout_seconds: 900
  retries:
    max_attempts: 1
```

Validation rules:

- `type` must be `langchain` or `cli`. The rules below apply when `type: langchain`.
- `llm.model_hint` must exist in workspace `llm.model_hints` or be a concrete model name.
- Every tool must exist in the engine tool registry.
- `context.budget_tokens`, when set, must be a positive integer.
- Retrieval limits must be positive integers and should be low enough to fit the context budget.
- `context.tools.mode` must be `static` for the runnable version. `dynamic` is reserved for later runtime tool selection.
- Tool categories are advisory until dynamic tool exposure is implemented.
- Write scopes must be a subset of allowed scopes for the agent type.
- `system_prompt` may reference workspace, engine, memory, and workflow context variables, but every static reference must resolve.
- Guardrail path patterns are relative to the workspace repo root.

### `cli` agent

A `cli` agent delegates the loop to an external CLI tool run headless and one-shot. GearTrain assembles the prompt and reads plain text back; it does not expose GearTrain tools to the CLI.

```yaml
schema_version: 1
name: coder
description: "Implements approved code changes via a headless CLI agent"
type: cli

cli:
  command: codex exec          # default; configurable per agent or engine
  # extra_args: ["--model", "gpt-5.5"]
  timeout_seconds: 900
  work_folder: work            # optional; falls back to workflow/workspace default
  sandbox: workspace-write     # passthrough to the CLI's own sandbox/approval mode
  credential: codex.default    # optional engine-scoped CLI credential reference

system_prompt: |
  You are a senior software engineer working on ${workspace.project.name}.
  Follow the workspace memory and project documentation provided in the prompt.

memory:
  read:                        # injected into the prompt as text, not as live tools
    - workspace
    - workflow
```

Validation rules:

- `cli.command` is required and must be a non-empty string. Default is `codex exec`.
- `cli.timeout_seconds`, when set, must be a positive integer.
- `cli.work_folder`, when set, must resolve inside the repo; otherwise the workflow or workspace default applies.
- `cli.credential`, when set, must name a credential declared in engine config, not a raw secret.
- A `cli` agent must not declare `llm` or `tools`. The external CLI owns the model and tools.
- `memory.read` scopes are allowed (injected as prompt context). `memory.write` is not supported for `cli` agents in MVP — the CLI can't call GearTrain memory tools mid-run.
- `system_prompt` may reference workspace, engine, memory, and workflow context variables, but every static reference must resolve.

Deferred:

- SDK agents.
- Cloud agents.
- User-controlled interactive IDE/CLI agents (the headless `cli` type is in MVP).
- Agent marketplaces.
- Agent inheritance and composition.
- Dynamic tool schema selection.
- Semantic retrieval and prompt compression.
- `memory.write` from `cli` agents.

## Workflow Definition

A workflow definition owns routing. Agents perform work inside nodes; they don't decide the main graph path.

```yaml
schema_version: 1
name: feature-development
description: "Plan, implement, test, review, and prepare a PR"
version: 0.1.0

trigger:
  type: manual

channels:
  human: cli

agents:
  team_lead: team-lead
  coder: coder
  reviewer: reviewer

graph:
  entry: intake
  nodes:
    intake:
      type: agent
      agent: team_lead
      action: analyze_task
      inputs:
        task: ${trigger.task}
      output_key: plan
      transitions:
        default: approve_plan

    approve_plan:
      type: human_checkpoint
      mode: approval
      prompt: "Approve the implementation plan?"
      transitions:
        approved: implement
        rejected: intake

    implement:
      type: agent
      agent: coder
      action: implement
      inputs:
        plan: ${nodes.intake.output}
      output_key: changes
      transitions:
        default: review

    review:
      type: agent
      agent: reviewer
      action: review_diff
      inputs:
        changes: ${nodes.implement.output}
      output_key: review
      transitions:
        default: end

    human_input:
      type: human_checkpoint
      mode: input
      prompt: "Provide the missing context."
      transitions:
        submitted: intake
```

Validation rules:

- `trigger.type` must be `manual` for the runnable version.
- `graph.entry` must reference an existing node.
- Every node must have a supported `type`.
- Every agent node must reference an agent declared in `agents`.
- Every transition target must reference an existing node or `end`.
- Agent, human checkpoint, and integration nodes produce a plain text output response.
- `output_key` is optional. It gives the node output a human-readable label in run state, but it does not define a schema.
- Variable references to node output text must point to upstream nodes unless the workflow explicitly supports loops for that edge.
- Loops are allowed only when the graph declares them through transitions. The validator should detect accidental orphan nodes and unreachable nodes.

Deferred:

- Parallel branches.
- Sub-workflows.
- Scheduled triggers.
- Webhook triggers.
- Dynamic agent assignment.
- Visual workflow editing.

## Node Types

MVP supports four node types.

| Type | Purpose | Required fields |
|------|---------|-----------------|
| `agent` | Run an agent action | `agent`, `action`, `inputs`, `transitions` |
| `decision` | Route on deterministic conditions | `conditions`, `transitions` |
| `human_checkpoint` | Wait for human approval or input | `mode`, `prompt`, `transitions` |
| `integration` | Call a configured integration | `service`, `action`, `inputs`, `transitions` |

The runnable version (phases 1-3) can implement only `agent` with a mock runner and `human_checkpoint` through CLI. The contract should still reserve the other node types so workflow files don't churn as later phases land.

## Node Inputs And Outputs

Node inputs and outputs are plain text for MVP.

People should be able to create workflows by writing YAML and prompts. They should not need to write Pydantic models or define detailed output schemas in a UI. The output shape is controlled by the agent's system prompt and action instructions.

The engine stores each node response as markdown in run-owned state:

```text
.geartrain/state/
└── runs/
    └── 2026-05-28-feature-development-001/
        ├── run.md
        ├── events.jsonl
        ├── nodes/
        │   ├── 01-intake.md
        │   ├── 02-approve-plan.md
        │   ├── 03-implement.md
        │   └── 04-review.md
        ├── attempts/
        │   ├── attempt-000001.md
        │   └── attempt-000002.md
        └── checkpoints/
            └── checkpoint-000001.md
```

Validation rules:

- `inputs` values may be literal text or variable references.
- `${nodes.<node-id>.output}` resolves to the full plain text response from that node.
- `${nodes.<node-id>.outputs.<key>}` is not part of the MVP contract.
- The validator checks that referenced nodes exist. It does not validate the semantic structure of their text.
- Future validators may check text against natural-language rules, but schema-based output validation is deferred.

Deferred:

- Pydantic-defined workflow input and output schemas.
- UI-defined output fields.
- Strict structured output validation.
- Natural-language output validators.

## Run State Contract

Workflow definitions are recipes. Runs are executions. The engine stores every execution as a run directory.

### `run.md`

`run.md` is the human-readable summary and current state for one run.

Required frontmatter:

```yaml
schema_version: 1
run_id: 2026-06-17-feature-development-001
workflow: feature-development
workflow_version: 0.1.0
workflow_hash: sha256-placeholder
status: running
created_at: 2026-06-17T18:20:00Z
started_at: 2026-06-17T18:20:01Z
finished_at:
current_node: implement
task_path: work/in-progress/p4-01-implement-langchain-agent-runner.md
error:
```

Validation rules:

- `status` must be `created`, `running`, `waiting`, `completed`, `failed`, or `canceled`.
- `run_id` must be unique under `.geartrain/state/runs/`.
- `workflow` must reference a known workflow definition.
- `current_node`, when set, must reference a node in the workflow definition.
- `task_path`, when set, must stay inside the repo.

### Node Run Files

Node run files live under `nodes/`.

Required frontmatter:

```yaml
schema_version: 1
node_id: implement
node_type: agent
status: completed
agent: coder
attempts:
  - attempt-000002
started_at: 2026-06-17T18:21:00Z
finished_at: 2026-06-17T18:24:00Z
duration_ms: 180000
output_key: changes
error:
```

Validation rules:

- `status` must be `pending`, `running`, `waiting`, `completed`, `failed`, or `skipped`.
- `node_id` must reference a node in the workflow definition.
- `agent`, when set, must reference a known agent.

### Attempt Files

Attempt files live under `attempts/`.

Required frontmatter:

```yaml
schema_version: 1
attempt_id: attempt-000002
node_id: implement
status: completed
agent: coder
runner_type: cli
started_at: 2026-06-17T18:21:00Z
finished_at: 2026-06-17T18:24:00Z
duration_ms: 180000
error:
```

The runnable version creates one attempt per executable node. Retries are deferred, but future retries add more attempt files without changing the node contract.

### Checkpoint Files

Checkpoint files live under `checkpoints/`.

Required frontmatter:

```yaml
schema_version: 1
checkpoint_id: checkpoint-000001
node_id: approve-plan
mode: approval
status: pending
created_at: 2026-06-17T18:20:30Z
resolved_at:
response:
```

Validation rules:

- `mode` must be `approval` or `input`.
- `status` must be `pending`, `resolved`, `rejected`, or `timed_out`.
- Resolved checkpoints must include `resolved_at` and response text.

## Event Log Contract

Each run has an append-only `events.jsonl` file. Each line is one JSON object.

Required fields:

```json
{
  "schema_version": 1,
  "event_id": "evt-000001",
  "run_id": "2026-06-17-feature-development-001",
  "type": "node.started",
  "created_at": "2026-06-17T18:21:00Z",
  "workflow": "feature-development",
  "node_id": "implement",
  "attempt_id": "attempt-000002",
  "checkpoint_id": null,
  "tool_call_id": null,
  "memory_entry": null,
  "level": "info",
  "message": "Started implement node",
  "data": {}
}
```

Required event types for MVP architecture:

- `run.created`
- `run.started`
- `run.completed`
- `run.failed`
- `lock.acquired`
- `lock.released`
- `node.started`
- `node.completed`
- `node.failed`
- `attempt.started`
- `attempt.completed`
- `attempt.failed`
- `agent.started`
- `agent.completed`
- `agent.failed`
- `checkpoint.created`
- `checkpoint.resolved`
- `tool.started`
- `tool.completed`
- `tool.failed`
- `memory.read`
- `memory.write`
- `memory.write_rejected`

The runnable version must emit the lifecycle, lock, node, attempt, agent, checkpoint, and error events it uses. Tool and memory events become active when those systems land.

Validation rules:

- Events are append-only.
- `event_id` is unique within a run.
- `run_id` must match the containing run directory.
- `type` must be from the known event registry.
- Timestamps must be ISO 8601 strings.
- `level` must be `debug`, `info`, `warning`, or `error`.

## Memory Entry Frontmatter

MVP memory entries are markdown files with YAML frontmatter.

```markdown
---
schema_version: 1
system: memory
scope: workspace
category: convention
source: human
confidence: 1.0
review_status: approved
tags: [git, workflow]
created_at: 2026-05-28T00:00:00Z
updated_at: 2026-05-28T00:00:00Z
---

# Commit Convention

Use conventional commits for generated commits.
```

Validation rules:

- `system` must be `memory` or `knowledge_base`.
- `scope` must be `workspace`, `workflow`, `agent_instance`, or `agent_level`.
- Persistent MVP files may not use `agent_instance`; that scope lives in run state.
- `review_status` must be `pending`, `approved`, `rejected`, or `edited`.
- Agent-level memory must include `agent_type`.
- Content must pass the secret-pattern guard before write.

## Validator Commands

The first CLI should expose these commands:

```text
geartrain validate workspace [path]
geartrain validate engine [path]
geartrain validate agent <path>
geartrain validate workflow <path>
geartrain validate memory <path>
geartrain validate all
```

`validate all` should run in this order:

1. Workspace config.
2. Engine config if provided.
3. Agent registry.
4. Workflow registry.
5. Memory files.
6. Cross-reference checks.
7. Runtime readiness checks.

Diagnostics should include file path, line number when available, field path, severity, and a direct fix suggestion.

Example:

```text
.geartrain/workflows/feature-development.workflow.yaml:42
error workflow.graph.nodes.implement.agent
Unknown agent reference "coder". Add it to workflow agents or create .geartrain/agents/coder.agent.yaml.
```

## First Implementation Target

The first implementation should prove this contract with no LLM calls:

1. Load `.geartrain/workspace.yaml`.
2. Validate all agent and workflow YAML files.
3. Run `feature-development` with mock agent outputs.
4. Pause at a CLI human checkpoint.
5. Persist run state as markdown files under `.geartrain/state/runs/`.
6. Persist run events as `events.jsonl`.
7. Print the final run summary and the run event log path.

After that works, replace mock agent nodes with real execution — the `cli` runner first (default `codex exec`), then `langchain`.
