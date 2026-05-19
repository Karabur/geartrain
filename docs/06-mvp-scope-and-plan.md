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

For MVP, GearTrain must ship with its own working workspace definition in the repo. That workspace is the first real product configuration: the local engine loads it by default and uses it to run GearTrain's own development workflow.

The MVP should not require team accounts, user management, hosted authentication, or a shared database before the product is useful. Git is the collaboration and versioning layer. A developer clones the repo, runs the local engine, and gets the same agents, workflows, and memory files as the rest of the team.

---

## MVP Scope

### In Scope

| Component | What's Included | What's Cut |
|-----------|----------------|------------|
| **Shared Workspace** | Repo-backed workspace definition stored alongside GearTrain's code, loaded by the local engine by default. Contains project config, agent registry, workflow registry, memory, and knowledge pointers. | Hosted workspace service, workspace invitation flow, cross-repo workspace discovery. |
| **Agent Layer** | LangChain agents defined via YAML. Configurable system prompt, tools, LLM provider. Agent definitions stored in the workspace folder. | CLI agents, cloud agents. No agent marketplace. |
| **Agent Tools** | File read/write, shell exec, git operations, project search (grep/glob), GitHub API (PR creation, issues). | Browser automation, complex API integrations, custom tool definitions via no-code. |
| **Workflow Layer** | LangGraph-based workflows defined via YAML. Sequential and branching flows, agent steps, decision nodes, human checkpoints. Workflow definitions stored in the workspace folder. | Sub-workflows, parallel execution, complex conditional logic, loop constructs. |
| **Workflow Registry** | File-system-based registry inside the workspace directory. List, validate, run. | Internal versioning service, migration engine, UI-based editing. Git history is the MVP version history. |
| **Team Layer** | Single repo workspace config via YAML. LLM provider/model defaults, GitHub integration, memory namespace. LLM provider connections and CLI agent credentials stay engine-scoped; each user sets up their own local credentials. | Multi-team, user roles, access control, UI-based team management. Team-level per-user LLM/CLI credential provisioning. |
| **Engine** | Local engine, single-workflow execution. SQLite state persistence. | Cloud engine, serverless, concurrent workflows, scheduling. |
| **Channels** | Local web UI (React) for workflow monitoring, HIL checkpoints, and memory inspection. Basic CLI for starting/stopping workflows. | Slack, Telegram, email channels. |
| **Memory & Knowledge** | Git-backed markdown files with YAML frontmatter. Workspace memory, workflow memory, and agent-type memory as persistent files where useful. Agent-instance memory as in-process LangGraph state. Knowledge base as project docs. Keyword-based search. Memory read/write as agent tools. | Dual-format with vector store, semantic search, memory database, automated memory promotion, memory/KB separation in storage, dreaming, guardrail LLM classification. |
| **Integrations** | GitHub (PR creation, issue read/update). | Slack, Linear, Sentry, AWS, all others. |
| **Guardrails** | Regex-based secret detection on memory writes. File path restrictions per agent. | LLM-based classification, cost guardrails, comprehensive PII detection. |

### Explicitly Deferred

These are important but not required for the dogfooding milestone:

- **No-code workflow editor UI** — workflows are YAML for MVP; visual editor is a fast follow
- **Multi-team support** — one git-backed workspace is sufficient for dogfooding
- **User accounts and authentication** — local engine trusts the developer running it; GitHub handles repository access and PR identity
- **Cloud execution** — local engine only
- **Slack/Telegram/Email channels** — web UI only
- **Agent instance memory persistence** — in-process only, discarded after run
- **Memory vector store** — keyword search is sufficient for small memory sets
- **CI/CD workflow** — manual PR review on GitHub
- **Product planning workflow** — manual for now
- **User support workflow** — not needed for dogfooding

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

### 5. Single LangChain Runtime
**Decision:** All agents use LangChain. No CLI agent wrapping.
**Why:** Supporting multiple agent runtimes adds abstraction complexity. LangChain is flexible enough for all MVP agent types. CLI wrapping (Claude Code, Codex) is architecturally planned but not implemented.
**Risk:** LangChain-specific patterns may leak into the agent interface. Mitigation: clean abstract interfaces from day one.

### 6. Minimal Web UI
**Decision:** The web UI shows workflow state, handles HIL checkpoints, and allows memory browsing. No drag-and-drop, no visual editor, no advanced analytics.
**Why:** The UI is not the product — the workflow engine is. A functional but minimal UI is sufficient for dogfooding. Polish comes later.
**Risk:** Poor UX may discourage usage. Mitigation: make the UI functional and fast, even if not beautiful.

### 7. GitHub-Only Integration
**Decision:** GitHub is the only external integration for MVP.
**Why:** The dogfooding workflow needs PR creation and issue tracking. GitHub covers both. Adding Slack, Linear, etc. is incremental once the integration interface is defined.
**Risk:** Limits the "no-code" story to GitHub-based projects. Acceptable for V1.

---

## Technical Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Agent runtime | LangChain (Python) | Mature agent framework, good tool ecosystem |
| Workflow orchestration | LangGraph (Python) | Native LangChain integration, state management, checkpointing |
| Workflow/agent definitions | YAML | Human-readable, no-code, easy to validate |
| Configuration parsing | Pydantic | YAML → validated Python objects |
| State persistence | SQLite | Zero-config, sufficient for local engine |
| Workspace storage | Git repo folder | Shared definitions, memory, and review through normal development flow |
| Memory (MVP) | Markdown files + file-system | Simple, human-editable, git-reviewable, swappable later |
| Web UI | React + Vite | Fast development, component ecosystem |
| API layer | FastAPI | Async-native, auto-generated OpenAPI docs |
| CLI | Click (Python) | Standard Python CLI framework |
| GitHub integration | PyGithub or GitHub REST API | PR creation, issue management |
| Testing | pytest | Standard Python testing |

---

## Implementation Plan (2 Weeks)

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

**Objective:** LangChain agents that can be instantiated from YAML definitions and executed.

Tasks:
- Implement `AgentFactory` — takes an `AgentDefinition`, returns a runnable LangChain agent
- Implement core tools as LangChain tools:
  - `file_read`, `file_write` — read/write project files
  - `shell_exec` — run shell commands (sandboxed to project directory)
  - `git_operations` — git status, diff, commit, branch, push
  - `project_search` — grep/glob across project files
- Implement system prompt template resolution (`${variable}` interpolation)
- Implement LLM provider resolution: agents use team provider/model defaults, while the engine loads each user's local OpenAI/Anthropic connection
- Write a test: define a coder agent in YAML, instantiate it, run a simple coding task
- Implement basic agent execution logging

Deliverable: A coder agent defined in YAML can read a file, make a change, and run tests.

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
- Workflow run state and agent-instance memory: handled by LangGraph state (in-process, no persistence yet)
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
  - Workflow state stored in SQLite via LangGraph checkpointing
  - State includes: current node, agent outputs, human responses, memory references
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
| LangGraph checkpointing doesn't support the workflow patterns needed | Medium | High | Prototype the workflow engine first (day 6); fall back to custom state machine if needed |
| Agent quality is too low to produce usable code | High | Medium | Start with small, well-scoped tasks; focus on the coordination value, not agent autonomy |
| YAML schema becomes unwieldy | Medium | Low | Keep schemas flat and well-documented; visual editor is the real solution |
| GitHub integration is flaky | Low | Medium | Robust error handling and retry logic; human can always complete GitHub steps manually |
| 2 weeks is not enough | High | High | Cut UI polish, cut reviewer agent, cut QA agent. Minimum viable: team-lead + coder + human checkpoints + GitHub PR |

---

## Absolute Minimum (If Time Runs Out)

If the 2-week timeline is too aggressive, this is the bare minimum to demonstrate the concept:

1. **One agent** (coder) configurable via YAML
2. **One workflow** (plan → code → human review → PR) in LangGraph
3. **Repo workspace** (`.geartrain/agents`, `.geartrain/workflows`, `.geartrain/memory`)
4. **Memory** (markdown files, read-only by agents — human writes memory manually)
5. **CLI only** (no web UI — human checkpoints via terminal prompts)
6. **GitHub PR creation** (the one integration)

This could be achieved in ~5 days and would prove the architecture works, even if it's not comfortable to use.

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
