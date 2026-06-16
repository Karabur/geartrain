# GearTrain — MVP Scope & 2-Week Implementation Plan

## Goal

Get GearTrain to a point where the GearTrain team (2-5 developers who are also product owners) can use GearTrain to develop GearTrain. This is the dogfooding milestone.

## What "Usable for Its Own Development" Means

At minimum, a developer should be able to:
1. Define agents (team lead, coder, reviewer) via YAML — no Python required
2. Define a feature development workflow via YAML
3. Run the workflow on their local machine
4. Interact with the workflow (approve plans, provide input) via a local web UI
5. Have agents read from and write to project memory (markdown-based)
6. Have agents create a GitHub PR at the end of a successful run
7. Inspect workflow state and history

The MVP ships two agent types behind one abstraction. A `cli` agent runs an external CLI tool headless and one-shot (default `codex exec`); a `langchain` agent runs inside GearTrain on LangChain/LangGraph. From the workflow's side they're identical — a node that takes a task and returns plain text — so a developer chooses the type per agent and the workflow doesn't change. The first runnable slice uses the `cli` type because a subprocess that returns text is the fastest path to a working loop; see [../work/SPEC.md](../work/SPEC.md) for that slice's task breakdown.

For MVP, GearTrain must ship with its own working workspace definition in the repo. That workspace is the first real product configuration: the local engine loads it by default and uses it to run GearTrain's own development workflow.

The MVP should not require team accounts, user management, hosted authentication, or a shared database before the product is useful. Git is the collaboration and versioning layer. A developer clones the repo, runs the local engine, and gets the same agents, workflows, and memory files as the rest of the team.

---

## MVP Scope

### In Scope

| Component | What's Included | What's Cut |
|-----------|----------------|------------|
| **Shared Workspace** | Repo-backed workspace definition stored alongside GearTrain's code, loaded by the local engine by default. Contains project config, agent registry, workflow registry, memory, and knowledge pointers. | Hosted workspace service, workspace invitation flow, cross-repo workspace discovery. |
| **Agent Layer** | Two agent types behind one abstraction, selected by a `type` field. `cli` agents run an external tool headless one-shot (default `codex exec`) with a `cli` config block. `langchain` agents run in-process with `llm` + `tools` blocks; local/open-source LLMs plug in here. Definitions stored in the workspace folder. | Interactive user-controlled CLI agents, SDK agents, cloud agents. No agent marketplace. |
| **Agent Tools** | File read/write, shell exec, git operations, project search (grep/glob), GitHub API (PR creation, issues). | Browser automation, complex API integrations, custom tool definitions via no-code. |
| **Workflow Layer** | LangGraph-based workflows defined via YAML. Sequential and branching flows, agent steps, decision nodes, human checkpoints. Workflow definitions stored in the workspace folder. | Sub-workflows, parallel execution, complex conditional logic, loop constructs. |
| **Workflow Registry** | File-system-based registry inside the workspace directory. List, validate, run. | Internal versioning service, migration engine, UI-based editing. Git history is the MVP version history. |
| **Team Layer** | Single repo workspace config via YAML. LLM provider/model defaults, GitHub integration, memory namespace. LLM provider connections and CLI agent credentials stay engine-scoped; each user sets up their own local credentials. | Multi-team, user roles, access control, UI-based team management. Team-level per-user LLM/CLI credential provisioning. |
| **Engine** | Local engine, single-workflow execution. File-backed markdown state under the workspace. | SQLite/PostgreSQL state backends, cloud engine, serverless, concurrent workflows, scheduling. |
| **Context Assembly** | A simple context builder with explicit sections for task input, agent instructions, prior outputs, selected memory, selected docs, and tool instructions. Used to build both in-process prompts and the prompt handed to `cli` agents. | Semantic RAG, prompt compression, dynamic tool schema selection, off-transcript helper calls. |
| **Channels** | Local web UI (React) for workflow monitoring, HIL checkpoints, and memory inspection. Basic CLI for starting/stopping workflows. | Slack, Telegram, email channels. |
| **Memory & Knowledge** | Git-backed markdown files with YAML frontmatter. Workspace memory, workflow memory, agent-type memory, and workflow run state are persistent files where useful. Knowledge base as project docs. Keyword-based search. Memory read/write as agent tools. | Dual-format with vector store, semantic search, memory database, automated memory promotion, memory/KB separation in storage, dreaming, guardrail LLM classification. |
| **Integrations** | GitHub (PR creation, issue read/update). | Slack, Linear, Sentry, AWS, all others. |
| **Guardrails** | Regex-based secret detection on memory writes. File path restrictions per agent for `langchain` agents; `cli` agents rely on the CLI's own sandbox/approval mode. | LLM-based classification, cost guardrails, comprehensive PII detection. |

### Explicitly Deferred

These are important but not required for the dogfooding milestone:

- **No-code workflow editor UI** — workflows are YAML for MVP; visual editor is a fast follow
- **Multi-team support** — one git-backed workspace is sufficient for dogfooding
- **User accounts and authentication** — local engine trusts the developer running it; GitHub handles repository access and PR identity
- **Cloud execution** — local engine only
- **Slack/Telegram/Email channels** — web UI only
- **Agent instance memory persistence** — in-process only, discarded after run
- **Memory vector store** — keyword search is sufficient for small memory sets
- **Advanced context optimization** — precise semantic RAG, dynamic tool discovery, prompt compression, and off-transcript helper calls are planned, but the MVP only needs context-assembly interfaces that don't block them
- **CI/CD workflow** — manual PR review on GitHub
- **Product planning workflow** — manual for now
- **User support workflow** — not needed for dogfooding
- **Interactive, user-controlled IDE/CLI agents** — the live-connection mode where the engine waits on an external session the developer drives is a fast follow. The headless one-shot `cli` agent type is in the MVP; programmatic control of stateful interactive sessions is not.
- **SDK and cloud agent types** — only `cli` and `langchain` ship in MVP

---

## Key Tradeoffs

### 1. YAML Over Visual Editor
**Decision:** Workflows and agents are configured via YAML files, not a visual UI.
**Why:** Building a visual workflow editor would consume the entire 2 weeks. The target users (developers) are comfortable with YAML. The visual editor is a fast follow once the runtime is proven.
**Risk:** YAML errors are hard to debug. Mitigation: robust validation with clear error messages.

### 2. Markdown Memory Over Vector Store
**Decision:** Workspace memory, workflow memory, and agent-type memory start as markdown files in the repo-backed workspace, searched with keyword matching. Agent-instance memory lives in LangGraph process state. Memory and knowledge base are not separated in storage (just tagged).
**Why:** A vector store adds infrastructure complexity (embedding model, vector DB). Markdown files work well enough for the small memory sets expected during early dogfooding (<100 entries). The memory interface is abstracted, so swapping the backend later doesn't affect agents.
**Risk:** Keyword search will miss semantically relevant but lexically different memories. Acceptable for MVP.

### 3. Git-Backed Workspace Over Hosted Team System
**Decision:** The default workspace is a folder inside the project repo, not a hosted team database.
**Why:** GearTrain needs agents, workflows, and memory before it needs account management. Git already gives the MVP sharing, history, review, branching, rollback, and conflict handling. This keeps the first milestone focused on running useful workflows.
**Risk:** Git conflicts can happen when multiple developers or agents edit the same memory files. Mitigation: keep entries small, write append-only files by default, and rely on PR review for curated changes.

### 4. Local Engine Only
**Decision:** No cloud execution for MVP.
**Why:** Cloud execution requires containerization, deployment infrastructure, networking, and centralized credential handling. Local execution is simpler and sufficient for the dogfooding use case. Each developer runs an engine with their own LLM provider connection and CLI agent credentials.
**Risk:** Can't run always-on workflows (CI/CD, support). Acceptable — those workflows are deferred anyway.

### 5. Two Agent Types: CLI and LangChain
**Decision:** MVP ships two agent types behind one abstraction. A `cli` agent spawns an external tool headless and one-shot (default `codex exec`) and reads plain text back. A `langchain` agent runs in-process with GearTrain tools and context assembly. The workflow treats both as the same node.
**Why:** The `cli` type is the fastest path to a running loop — no agent-runtime code, just a subprocess — and it unlocks subscription-based execution, since `codex exec` can reuse the user's CLI auth instead of per-token API billing. The `langchain` type gives GearTrain full control of the loop, tools, and context for agents that need it, and is where local/open-source LLMs plug in. Building both against one interface keeps the workflow layer agnostic and lets future types (`sdk`, `cloud`) slot in.
**Risk:** Two runners is more surface than one. Mitigation: keep the abstraction thin (`run(task, context) -> str`), ship `cli` first as the first slice, then add `langchain` against the same interface. The subscription-cost benefit is vendor-specific and shifting — OpenAI discourages subscription auth for unattended runs, and Anthropic now bills headless Claude Code at API rates — so treat it as a cost lever, not a guarantee; the agnostic interface means a `cli` node can be swapped for an API-billed `langchain` node without touching the workflow.

Fast follow: add interactive, user-controlled IDE/CLI agents for coding workflows. In that mode, the engine waits for an external IDE or CLI agent connection instead of spawning a one-shot process, exposes task context through MCP or a similar local protocol, and resumes the workflow when the external agent submits results.

### 6. Minimal Web UI
**Decision:** The web UI shows workflow state, handles HIL checkpoints, and allows memory browsing. No drag-and-drop, no visual editor, no advanced analytics.
**Why:** The UI is not the product — the workflow engine is. A functional but minimal UI is sufficient for dogfooding. Polish comes later.
**Risk:** Poor UX may discourage usage. Mitigation: make the UI functional and fast, even if not beautiful.

### 7. GitHub-Only Integration
**Decision:** GitHub is the only external integration for MVP.
**Why:** The dogfooding workflow needs PR creation and issue tracking. GitHub covers both. Adding Slack, Linear, etc. is incremental once the integration interface is defined.
**Risk:** Limits the "no-code" story to GitHub-based projects. Acceptable for V1.

### 8. Small-Model-Ready Interfaces
**Decision:** The MVP uses simple retrieval and prompt assembly, but it keeps context assembly, memory retrieval, tool exposure, and model routing behind explicit interfaces.
**Why:** GearTrain should work well with smaller models. That requires narrow steps, compact prompts, precise context, and fewer visible tools. The MVP doesn't need the final optimization stack, but it must not hardcode prompts in a way that makes those optimizations hard to add.
**Risk:** Interfaces can become abstract before they have real usage. Mitigation: start with one concrete context builder shared by both agent runners, then generalize only when the engine needs it.

---

## Technical Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Agent runtime | LangChain (Python) | Mature agent framework, good tool ecosystem |
| Workflow orchestration | LangGraph (Python) | Native LangChain integration with file-backed MVP state |
| Workflow/agent definitions | YAML | Human-readable, no-code, easy to validate |
| Configuration parsing | Pydantic | YAML → validated Python objects |
| State persistence | Markdown files | Easy to inspect, manually edit, and evolve while the state shape is still changing |
| Workspace storage | Git repo folder | Shared definitions, memory, and review through normal development flow |
| Memory (MVP) | Markdown files + file-system | Simple, human-editable, git-reviewable, swappable later |
| Context assembly | Internal builder module | One place to add prompt budgeting, precise RAG, compression, dynamic tools, and off-transcript helper calls later |
| CLI agent runner | Python `subprocess` wrapper | Runs `codex exec` headless, captures plain text; configurable command per agent/engine |
| Web UI | React + Vite | Fast development, component ecosystem |
| API layer | FastAPI | Async-native, auto-generated OpenAPI docs |
| CLI | Click (Python) | Standard Python CLI framework |
| GitHub integration | PyGithub or GitHub REST API | PR creation, issue management |
| Testing | pytest | Standard Python testing |

---

## Implementation Plan (2 Weeks)

### Phase 0: First Slice — CLI Agent Loop

**Objective:** Get one real GearTrain loop running end to end with the `cli` agent type before the fuller runtime exists. This slice is specified in detail in [../work/SPEC.md](../work/SPEC.md); the summary here keeps the plan aligned with it.

Tasks:
- Stand up the local engine: load and validate `.geartrain/workspace.yaml` on startup, expose a small HTTP API.
- Implement the `cli` agent runner: build the prompt from agent config, workspace paths, work folder, task content, and prior output, then run `codex exec` and capture plain text.
- Define two `cli` agents (`coder`, `lead`) and one small workflow (`geartrain-dev`): pick a task from `work/`, run `coder`, pass output to `lead`, write a log line.
- File-back run state under `.geartrain/state/`. Prevent parallel runs of the same workflow.

Deliverable: `geartrain workflow start` runs one `geartrain-dev` iteration through real `codex` agents and writes run state.

### Week 1: Foundation

#### Days 1-2: Project Skeleton & Core Models

**Objective:** Runnable project with core data models and configuration loading.

Tasks:
- Initialize Python project structure (monorepo: `geartrain/` package)
- Set up development tooling: pyproject.toml, ruff, mypy, pytest
- Define the default workspace folder structure:
  - `.geartrain/workspace.yaml` — project/workspace config
  - `.geartrain/agents/` — agent definitions
  - `.geartrain/workflows/` — workflow definitions
  - `.geartrain/memory/workspace/` — project/workspace operational memory
  - `.geartrain/memory/agent-types/` — agent-type memory
  - `.geartrain/memory/workflows/` — reusable workflow memory and run summaries
  - `.geartrain/state/` — file-backed workflow state and per-run outputs (`state/runs/<run-id>/`)
- Define Pydantic models for all YAML schemas:
  - `AgentDefinition` — name, type, LLM config, system prompt, tools, memory config
  - `WorkflowDefinition` — name, nodes, transitions, triggers, channels
  - `WorkspaceConfig` — project name, LLM defaults, integrations, registry paths, memory paths
  - `EngineConfig` — host, port, resources, state backend
- Implement YAML loading and validation with clear error messages
- Write a sample agent definition and workflow definition
- Write tests for configuration loading

Deliverable: `geartrain validate .geartrain/agents/coder.agent.yaml` works and reports errors.

#### Days 3-4: Agent Runtime

**Objective:** Both agent types instantiable from YAML behind one interface. The `cli` runner already exists from Phase 0; this adds the `langchain` runner and the shared abstraction.

Tasks:
- Define the agent interface: `run(task, context) -> str`. Both runners implement it; the workflow only sees this.
- Implement `AgentFactory` — dispatch on `type`: `cli` returns the subprocess runner, `langchain` returns a `create_agent`-backed runnable.
- Implement core LangChain tools (for `langchain` agents): `file_read`, `file_write`, `shell_exec` (sandboxed to project dir), `git_operations`, `project_search`.
- Implement system prompt template resolution (`${variable}` interpolation).
- Implement a shared context builder used by both runners — assembled in-context for `langchain`, front-loaded into the prompt for `cli`.
- Implement LLM provider resolution for `langchain` agents: team provider/model defaults, engine loads each user's local OpenAI/Anthropic/local connection. (`cli` agents resolve credentials through the CLI's own auth.)
- Write tests: a `langchain` coder reads a file, makes a change, runs tests; a `cli` coder runs against a fake `codex` command.
- Implement basic agent execution logging for both runners.

Deliverable: A coder agent defined in YAML runs under either `type`, selected by the definition, with no change to the workflow.

#### Day 5: Memory & Knowledge System (MVP)

**Objective:** Git-backed markdown memory/knowledge store that agents can read from and write to.

Tasks:
- Implement `MemoryStore` interface (Protocol class) with `scope` and `system` parameters
- Implement `MarkdownMemoryStore` for persistent scopes (workspace memory, workflow memory, agent-type memory, knowledge base):
  - `write()` — creates a markdown file with YAML frontmatter (scope, system, category, tags)
  - `read()` — keyword search across files, returns ranked results, respects scope visibility
  - `update()` — modifies an existing entry
  - `list()` — lists entries by scope, system, category, tags
  - `forget()` — soft-deletes an entry
- Workflow run state and agent-instance context: stored as markdown files under `.geartrain/state/` where useful
- Implement memory as LangChain tools (`memory_read`, `memory_write`, `kb_read`, `kb_write`)
- Implement regex-based guardrail for memory writes (reject secrets, credentials)
- Scope isolation: workspace memory, workflow memory, agent-type memory, and knowledge base in separate directories
- Implement scope visibility rules: agent reads instance + workflow + workspace + agent-level
- Write tests for memory operations

Deliverable: An agent can write a workspace, workflow, agent-type, or KB entry in `.geartrain/memory/`, and a subsequent agent run can retrieve it. Agent-type memories are isolated by agent type.

### Week 2: Workflow Engine & UI

#### Days 6-7: Workflow Engine

**Objective:** LangGraph-based workflow runtime that executes YAML-defined workflows.

Tasks:
- Implement `WorkflowFactory` — takes a `WorkflowDefinition`, builds a LangGraph graph
- Implement node types:
  - `AgentNode` — instantiates and runs an agent, captures output
  - `DecisionNode` — evaluates conditions, routes to next node
  - `HumanCheckpointNode` — pauses workflow, emits a checkpoint event, waits for response
  - `IntegrationNode` — calls an external service (GitHub for MVP)
- Implement state management:
  - Workflow state stored as markdown files under `.geartrain/state/`
  - State includes: current node, plain text agent outputs, human responses, memory references
- Implement variable resolution across workflow context
- Implement transition logic (output-based routing)
- Write tests: run a simple 3-node workflow (agent → decision → agent)

Deliverable: A feature-development workflow can run end-to-end in tests (with mocked human input).

#### Day 8: GitHub Integration & CLI

**Objective:** Working GitHub integration and CLI to start/manage workflows.

Tasks:
- Implement GitHub integration:
  - Create branch, commit changes, create PR with description
  - Read issues (title, body, labels, assignee)
  - Update issue status/labels
- Wrap as LangChain tools available to agents
- Implement CLI:
  - `geartrain init` — scaffold `.geartrain/` in the current repo
  - `geartrain validate <file>` — validate any YAML definition
  - `geartrain agent <agent> "<prompt>"` — run a single named agent (either type) one-shot
  - `geartrain run <workflow> [--task <description>]` — start a workflow run from the default workspace
  - `geartrain status` — show running workflows and their state
  - `geartrain stop <run-id>` — stop a workflow run
- Implement engine startup (loads workspace config, registers agents/workflows, starts API server)

Deliverable: `geartrain run feature-development --task "add unit tests for memory store"` starts a real workflow.

#### Days 9-10: Web UI

**Objective:** Minimal web UI for workflow monitoring and human-in-the-loop interaction.

Tasks:
- Set up React + Vite project in `web/` directory
- Implement FastAPI backend endpoints:
  - `GET /api/workflows` — list active workflow runs
  - `GET /api/workflows/{id}` — workflow run state and history
  - `GET /api/workflows/{id}/checkpoints` — pending human checkpoints
  - `POST /api/workflows/{id}/checkpoints/{id}/respond` — submit human response
  - `GET /api/memory` — browse memory entries
  - `GET /api/memory/{scope}` — list memories by scope
  - WebSocket: real-time workflow state updates
- Implement UI pages:
  - **Dashboard** — list of active workflows, their status, current node
  - **Workflow Detail** — step-by-step view of a running workflow, agent outputs, transition history
  - **Checkpoint** — form for human input (approve/reject/provide text)
  - **Memory Browser** — list/search/view memory entries by scope
- Implement real-time updates via WebSocket (workflow state changes push to UI)

Deliverable: Developer can watch a workflow run in the browser and respond to checkpoints.

#### Days 11-12: Integration Testing & Dogfooding Prep

**Objective:** End-to-end testing with the actual GearTrain codebase as the target project.

Tasks:
- Create the repo-backed `.geartrain/` workspace for self-development
- Define agents: team-lead, coder, qa, reviewer (tuned for GearTrain codebase)
- Define the feature-development workflow for GearTrain
- Seed project memory with GearTrain architecture knowledge
- Run end-to-end: pick a real task, run the workflow, produce a PR
- Fix bugs and rough edges discovered during dogfooding
- Write integration tests for the critical path
- Document setup instructions for team members

Deliverable: A developer can clone the repo, run `geartrain init && geartrain run feature-development`, and get a working PR out.

#### Days 13-14: Polish & Documentation

**Objective:** Stable enough for team members to use. Documentation complete.

Tasks:
- Fix critical bugs from dogfooding
- Improve error messages and validation
- Write setup guide (README.md)
- Write user guide: how to define agents, workflows, run the system
- Write contributor guide: how to add new tools, integrations, agent types
- Create example configurations for common scenarios
- Performance testing: can a workflow complete a simple task in under 10 minutes?
- Tag v0.1.0

Deliverable: Team members can set up and use GearTrain independently.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| File-backed workflow state doesn't support the workflow patterns needed | Medium | High | Prototype the workflow engine first (day 6); fall back to a small custom state index or SQLite if markdown files become limiting |
| Agent quality is too low to produce usable code | High | Medium | Start with small, well-scoped tasks; focus on the coordination value, not agent autonomy |
| YAML schema becomes unwieldy | Medium | Low | Keep schemas flat and well-documented; visual editor is the real solution |
| GitHub integration is flaky | Low | Medium | Robust error handling and retry logic; human can always complete GitHub steps manually |
| Two agent runners diverge or the abstraction leaks | Medium | Medium | Keep the interface to `run(task, context) -> str`; ship `cli` first, add `langchain` against the same interface; cover both with the same workflow tests |
| Subscription-auth cost benefit disappears (vendor policy) | Medium | Low | Don't assume it; `cli` nodes are swappable for API-billed `langchain` nodes without workflow changes |
| 2 weeks is not enough | High | High | Cut UI polish, cut reviewer agent, cut QA agent. Minimum viable: team-lead + coder + human checkpoints + GitHub PR |

---

## Absolute Minimum (If Time Runs Out)

If the 2-week timeline is too aggressive, this is the bare minimum to demonstrate the concept:

1. **Repo workspace** (`.geartrain/agents`, `.geartrain/workflows`, `.geartrain/memory`, `.geartrain/state`)
2. **One `cli` agent** (coder, default `codex exec`) configurable via YAML — the cheapest runner to stand up
3. **One workflow** (plan → code → human review → PR) in LangGraph
4. **Memory** (markdown files, read-only by agents — human writes memory manually)
5. **CLI only** (no web UI — human checkpoints via terminal prompts)
6. **GitHub PR creation** (the one integration)

This could be achieved in ~5 days and would prove the architecture works, even if it's not comfortable to use. The `langchain` agent type can follow once the loop holds.

---

## Open Questions [To Be Defined]

1. **Agent tool sandboxing** — how to prevent agents from accessing files outside the project? Containerization? chroot? Honor system with guardrails?
2. **Cost tracking** — how to measure and limit LLM API costs per workflow run? Per agent? Per team?
3. **Concurrent workflow runs** — what happens when two developers run the same workflow on the same repo? Branch isolation? Locking?
4. **Memory conflict resolution** — when two agents write contradictory git-backed memories, which wins? Timestamp? Confidence? Human review?
5. **Agent-to-agent communication** — can agents talk to each other directly within a workflow, or only through the graph? Direct messaging adds flexibility but complexity.
6. **Workflow error handling** — what happens when an agent fails? Retry? Skip? Human escalation? Configurable per node?
7. **LLM provider failover** — if the primary LLM provider is down, can agents fail over to an alternative? How is this configured?
8. **Workflow composability** — how do sub-workflows share state with parent workflows? What's the data contract?
9. **Observability** — what telemetry does the engine emit? OpenTelemetry? Custom format?
10. **Upgrade path** — when a workflow definition changes, what happens to in-flight runs? Complete with old definition? Migrate?
