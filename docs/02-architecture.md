# GearTrain — Architecture

## System Layers

GearTrain is organized into five layers, bottom to top. Each layer has a clear responsibility and communicates with adjacent layers through defined interfaces.

```
┌─────────────────────────────────────────────────────┐
│  Layer 5: Channels                                  │
│  (Web UI, Slack, Telegram, Email, CLI)              │
├─────────────────────────────────────────────────────┤
│  Layer 4: Engine                                    │
│  (Workflow runtime, state management, scheduling)   │
├─────────────────────────────────────────────────────┤
│  Layer 3: Teams                                     │
│  (Multi-tenancy, user management, configuration)    │
├─────────────────────────────────────────────────────┤
│  Layer 2: Workflows                                 │
│  (LangGraph pipelines, decision logic, HIL gates)   │
├─────────────────────────────────────────────────────┤
│  Layer 1: Agents                                    │
│  (LangChain, CLI, SDK, and cloud agents)            │
├─────────────────────────────────────────────────────┤
│  Foundation: Memory & Integrations                  │
│  (Dual-format memory, external service connectors)  │
└─────────────────────────────────────────────────────┘
```

---

## Layer 1: Agents

### Responsibility
Individual AI units that perform specific tasks. Each agent has a defined role, set of tools, system prompt, LLM configuration, and instance memory.

### Agent Types

| Type | Runtime | LLM Provider | Configuration | MVP Status |
|------|---------|--------------|---------------|------------|
| LangChain Agent | LangChain + LangGraph | Configurable (OpenAI, Anthropic, etc.) via the user's engine-scoped provider connection | No-code (YAML definition) | **In scope** |
| CLI Agent | Local CLI tool (Claude Code, Codex) | Uses the user's engine-scoped local subscription/credentials | CLI config reference | Deferred |
| SDK Agent | Vendor-specific agentic SDK (Anthropic Agent SDK, OpenAI Agents SDK, etc.) | SDK-managed | SDK config + YAML bridge | Deferred |
| Cloud Agent | Remote API | Provider-managed | API credentials | Deferred |

Manual CLI-agent bootstrap is in scope before full CLI-agent runtime support. In that mode GearTrain does not launch or control the CLI agent. It builds a prompt packet from the workspace and stores the packet/output under `.geartrain/runs/`. A developer starts the CLI agent manually and asks it to use the packet.

**SDK Agents** are built on vendor-specific agentic SDKs — Anthropic Agent SDK, OpenAI Agents SDK, and similar frameworks that provide their own tool-use loops, context management, and orchestration primitives. Unlike LangChain agents (which GearTrain fully controls) or CLI agents (which GearTrain wraps), SDK agents bring their own execution model. GearTrain provides the environment — tools, memory, context — but the SDK handles the agent loop internally.

Open questions [to be defined]:
- How SDK-native tool registries map to GearTrain's tool system (passthrough vs. adapter layer)
- Whether SDK agents use GearTrain's memory directly or bridge through SDK-native context mechanisms
- Lifecycle management: who owns retries, checkpointing, and state persistence when the SDK has its own opinions
- How guardrails apply when the SDK manages its own execution loop

### Agent Definition Structure

```yaml
# agents/coder.agent.yaml
name: coder
type: langchain
description: "Writes code based on specifications and plans"

llm:
  provider: ${engine.llm.default}   # resolved from the user's engine config
  model: ${engine.llm.model}
  temperature: 0.2
  # Optional per-action model routing can override this default.
  routes:
    plan: ${engine.llm.strong_model}
    summarize: ${engine.llm.cheap_model}
    classify: ${engine.llm.cheap_model}

system_prompt: |
  You are a senior software engineer working on ${project.name}.
  Follow the project's coding conventions and patterns.
  ${memory.agent_type.coding_patterns}

tools:
  - file_read
  - file_write
  - shell_exec
  - git_operations
  - project_search

context:
  budget_tokens: 12000
  retrieval:
    memory_top_k: 6
    knowledge_top_k: 8
    require_source_refs: true
  tools:
    mode: dynamic
    categories: [repo, shell, git]

memory:
  agent_level: coding_patterns     # shared across all coder instances, cross-project
  instance_memory: true            # per-instance operational context

guardrails:
  max_file_changes: 20
  require_tests: true
  forbidden_paths:
    - "*.env"
    - "secrets/*"

runtime:
  tool_retries:
    max_attempts: 2
    retry_on: [timeout, transient_error]
  output:
    format: plain_text
    # Output structure is controlled by the system prompt and action instructions.
  on_failure: escalate
```

### Agent Registry
All agents are registered in a team-scoped catalog. The registry tracks:
- Agent definitions (versioned)
- Agent type memory references
- Active instances and their state
- Performance metrics and feedback history

### Agent Instance Lifecycle
1. **Defined** — YAML definition exists in registry
2. **Instantiated** — workflow creates a running instance with context
3. **Active** — processing a task
4. **Waiting** — blocked on human input, another agent, or external event
5. **Completed** — task finished, results stored
6. **Archived** — instance memory persisted, resources released

---

## Layer 2: Workflows

### Responsibility
Orchestration layer that defines how agents collaborate. Built on LangGraph as directed graphs of steps, decisions, and checkpoints.

### Workflow Components

| Component | Description |
|-----------|-------------|
| **Agent Step** | Invokes an agent with input, collects output |
| **Decision Node** | Routes flow based on agent output or conditions |
| **Human Checkpoint** | Pauses for human approval/input via configured channel |
| **Integration Step** | Calls external service (GitHub, Slack, Linear, etc.) |
| **Sub-workflow** | Invokes another registered workflow |
| **Memory Operation** | Reads from or writes to project/workflow memory |
| **Trigger** | Defines what starts the workflow (manual, webhook, schedule, event) |

### Workflow Definition Structure

```yaml
# workflows/feature-development.workflow.yaml
name: feature-development
description: "End-to-end feature development from task to PR"
version: 1.0

trigger:
  type: manual  # or: webhook, schedule, event
  # event_source: github.issue.assigned

agents:
  - ref: team-lead
  - ref: coder
  - ref: qa
  - ref: reviewer

channels:
  - slack: ${team.integrations.slack.dev_channel}
  - web_ui: true

memory:
  project: ${team.memory.project}

graph:
  entry: intake

  nodes:
    intake:
      agent: team-lead
      action: analyze_task
      inputs:
        task: ${trigger.payload}
        project_context: ${memory.project.current_state}
      output_key: plan
      transitions:
        default: human_review

    human_review:
      type: human_checkpoint
      prompt: "Review implementation plan and approve or request changes"
      channel: slack
      timeout: 24h
      transitions:
        approved: implement
        rejected: intake
        timeout: notify_and_wait

    implement:
      agent: coder
      action: write_code
      inputs:
        plan: ${intake.output}
        codebase: ${project.repo}
      output_key: changes
      transitions:
        default: test

    test:
      agent: qa
      action: run_tests
      inputs:
        changes: ${implement.output}
      output_key: test_report
      transitions:
        default: review

    review:
      agent: reviewer
      action: review_changes
      inputs:
        changes: ${implement.output}
        standards: ${memory.project.coding_standards}
      output_key: review
      transitions:
        default: create_pr

    create_pr:
      agent: team-lead
      action: create_pull_request
      tools: [github]
      inputs:
        changes: ${implement.output}
        plan: ${intake.output}
      output_key: pr_url
      transitions:
        default: update_tracker

    update_tracker:
      type: integration
      service: issue_tracker
      action: update_status
      inputs:
        status: "in_review"
        pr_url: ${create_pr.output}
      transitions:
        done: end
```

### Workflow Registry
Team-scoped catalog of workflow definitions. Tracks:
- Workflow definitions (versioned)
- Active workflow runs and their state
- Execution history and metrics
- Template workflows (shareable across teams, future)

---

## Layer 3: Teams

### Responsibility
Multi-tenancy and organizational boundary. Each team is a self-contained environment.

For MVP, this layer is implemented as one git-backed workspace inside the project repo. The workspace carries the project configuration, agent registry, workflow registry, and markdown memory files. A hosted team service, users, roles, and authentication come later.

### Team Structure

```yaml
# .geartrain/workspace.yaml
name: geartrain-core
description: "GearTrain core development team"

# MVP has no users, roles, or authentication layer.
# Git repo access controls who can edit and run the shared workspace.
# Future: users, roles, invitations, and hosted team management.

# LLM provider connections and CLI agent credentials are engine-scoped
# (see Engine definition below). Each user provides their own API
# keys/accounts locally so their engine can run.
# Future: team-level provisioning can supply per-user LLM and CLI credentials.

llm:
  default_provider: anthropic        # declares which provider agents should use
  model: claude-sonnet-4-20250514    # default model; connection resolved from engine config
  # per-agent overrides allowed

integrations:
  github:
    org: geartrain
    repo: geartrain
    token: ${env.GITHUB_TOKEN}
  slack:
    workspace: geartrain
    dev_channel: "#dev"
    bot_token: ${env.SLACK_BOT_TOKEN}
  # linear, sentry, aws, etc.

memory:
  root: ./.geartrain/memory
  workspace: ./.geartrain/memory/workspace
  agent_types: ./.geartrain/memory/agent-types
  workflows: ./.geartrain/memory/workflows

agents:
  registry: ./.geartrain/agents/
workflows:
  registry: ./.geartrain/workflows/
runs:
  root: ./.geartrain/runs/
```

### Team Isolation
- MVP: the current git repo contains one workspace; isolation comes from repo boundaries and local engine configuration
- Future: each hosted team has its own agent registry, workflow registry, memory namespace, and integration credentials
- Future: no cross-team data access unless explicit sharing mechanisms are added
- Team defines which LLM providers and models agents should use; actual provider connections and CLI agent credentials are engine-scoped, and each user provides their own locally

---

## Layer 4: Engine

### Responsibility
Runtime environment that executes workflows. Manages state, scheduling, concurrency, and resource allocation.

### Engine Types

| Type | Runs On | Use Case | MVP Status |
|------|---------|----------|------------|
| Local Engine | Developer workstation | Interactive development workflows | **In scope** |
| Server Engine | Cloud VM / container | CI/CD, always-on pipelines | Deferred |
| Serverless Engine | Cloud functions | Event-driven, stateless workflows | Deferred |

### Engine Capabilities
- **State Management:** Persists workflow state across interruptions. MVP state is file-backed markdown under the workspace; SQLite and stronger checkpointing can come later.
- **Concurrency:** Runs multiple workflow instances; manages agent resource contention
- **Scheduling:** Cron-like triggers for periodic workflows
- **Deterministic Tool Control:** Applies configured tool retries, timeouts, fallback paths, and escalation rules outside the LLM loop
- **Failure Handling:** Routes bad outputs, agent mistakes, external API failures, repeated LLM call failures, and invalid tool results through configured repair, retry, fallback, or human-escalation paths
- **Model Routing:** Resolves per-agent and per-action model choices so workflows can spend stronger models where they matter and cheaper models where they are enough
- **Context Assembly:** Builds compact per-call prompts from workflow state, selected memory, selected knowledge, prior outputs, and agent instructions
- **Dynamic Tool Exposure:** Exposes only the tool schemas relevant to the current step, while keeping larger tool catalogs available through registry lookup
- **Health Monitoring:** Tracks active workflows, agent utilization, error rates
- **Observability:** Captures token usage, cost, latency, tool usage, repeated invocations, retries, failed LLM calls, failed tool calls, and workflow outcomes
- **Evals:** Runs workflow and agent behavior checks to detect drift, compare models, validate prompt changes, and support controlled model upgrades
- **Hot Reload:** Picks up agent/workflow definition changes without restart
- **Workspace Loading:** Loads the repo's default `.geartrain/workspace.yaml` unless a different workspace path is provided

### Engine Definition

```yaml
# engines/local-dev.engine.yaml
name: local-dev
type: local
host: localhost
port: 8420

# LLM provider connections and CLI agent credentials live here.
# Each user configures their own API keys/accounts locally so this engine can run.
# The engine resolves these at runtime; agents and workflows reference
# provider/model names, not credentials directly.
# Future: team-level provisioning can supply per-user LLM and CLI credentials centrally.
llm:
  default: anthropic
  strong_model: ${env.GEARTRAIN_STRONG_MODEL}
  cheap_model: ${env.GEARTRAIN_CHEAP_MODEL}

  anthropic:
    api_key: ${env.ANTHROPIC_API_KEY}
  openai:
    api_key: ${env.OPENAI_API_KEY}

mcp_servers:
  filesystem:
    command: ${env.GEARTRAIN_MCP_FILESYSTEM_COMMAND}
    args: ["${project.repo}"]
  github:
    command: ${env.GEARTRAIN_MCP_GITHUB_COMMAND}

acp:
  enabled: false
  # Future: expose the running engine to ACP-capable IDEs.

cli_agents:
  claude_code:
    # Uses the user's local Claude subscription
    config_path: ~/.claude
  codex:
    config_path: ~/.codex

workflows:
  - ref: feature-development
  - ref: ci-review

workspace:
  path: ./.geartrain/workspace.yaml

resources:
  max_concurrent_workflows: 3
  max_concurrent_agents: 5

state:
  backend: files            # MVP: markdown files; future: SQLite/PostgreSQL
  path: ./.geartrain/state

logging:
  level: info
  output: ./logs/

observability:
  traces: true
  metrics:
    - token_usage
    - cost
    - latency
    - tool_usage
    - retries
    - failed_llm_calls
    - failed_tool_calls
    - workflow_outcomes

evals:
  enabled: false
  suites:
    - workflow_regression
    - model_upgrade
```

---

## Context Assembly & Smaller-Model Readiness

GearTrain should not assume every workflow step runs on a frontier model with a huge context window. The architecture should make smaller models effective by giving them less irrelevant work to do.

The engine owns context assembly. Agents and workflows declare what they need; the engine builds the smallest useful prompt for each call. That keeps context policy outside one-off agent prompts and lets teams improve retrieval, compression, routing, and tool selection without rewriting every agent.

Core requirements:
- **Prompt budgets:** Agents, workflow nodes, and model routes can define target context budgets.
- **Scoped prompt sections:** System instructions, task input, workflow state, prior outputs, memory, knowledge, and tool instructions remain separate until final prompt assembly.
- **Precise retrieval:** Memory and knowledge retrieval use metadata filters, scope rules, query rewriting where useful, top-k limits, source references, and relevance thresholds.
- **Dynamic tools:** Agents can declare tool categories or capabilities. The engine resolves the concrete schemas at call time and avoids injecting every available tool.
- **Off-transcript calls:** Planning, classification, retrieval query generation, tool selection, and output repair can run as helper calls whose intermediate transcripts don't enter the main agent context.
- **Output contracts:** Workflow steps define expected output shape, validation, repair, and fallback behavior so smaller models get explicit targets.
- **Evals by route:** Evals compare prompts, retrieval rules, tool-selection rules, and model routes so teams can decide where smaller models are safe.

MVP can keep the implementation simple: hand-assembled prompt packets, keyword search, explicit tool lists, and plain text outputs. The important constraint is that these are behind interfaces that can grow into precise RAG, dynamic tool discovery, prompt compression, and off-transcript helper calls later.

---

## Layer 5: Channels

### Responsibility
User-facing interaction points for running workflows. Each channel is a bidirectional communication bridge between humans and the engine.

### Channel Types

| Channel | Direction | Use Case | MVP Status |
|---------|-----------|----------|------------|
| Web UI | Bidirectional | Dashboard, workflow monitoring, HIL interaction | **In scope** (minimal) |
| Slack | Bidirectional | Team notifications, approvals, async communication | Deferred |
| CLI | Input only | Developer command-line interaction | **In scope** (basic) |
| Telegram | Bidirectional | Mobile-friendly interaction | Deferred |
| Email | Bidirectional | Async approvals, reports | Deferred |
| Webhook | Input only | External event triggers | **In scope** (basic) |

### Channel Configuration in Workflows
Channels are defined per-workflow. A workflow specifies which channels it uses for:
- **Human checkpoints** — where approval requests are sent
- **Notifications** — where status updates go
- **Agent-to-human communication** — where agents can ask questions
- **Reports** — where summaries and results are delivered

---

## Foundation: Memory & Integrations

### Memory & Knowledge System
See [04-memory-system.md](04-memory-system.md) for full design.

Two systems:
- **Memory** (operational) — "how" to work and "what happened"
- **Knowledge Base** (domain/product) — "what" should be done and "why"

Four memory scopes:
1. **Agent-Instance Memory** — operational context for a specific agent in a specific workflow run
2. **Workflow Memory** — shared operational context across agents within a single workflow run
3. **Workspace Memory** — shared operational context across all workflows in a team
4. **Agent-Level Memory** — cross-project operational learnings for an agent type (self-improvement)

Two storage formats:
1. **Human-Faced** — readable, inspectable, editable by humans (Markdown/HTML for MVP)
2. **AI-Faced** — optimized for retrieval, ranking, and contextual search (vector store + structured metadata)

MVP storage is simpler: the human-faced markdown files in `.geartrain/memory/` are the source of truth, and git provides sharing, history, review, branching, rollback, and conflict handling. The AI-facing store is deferred until semantic search is needed.

### Integration System
Pluggable connectors to external services. Each integration provides:
- **Authentication** — credential management (engine-scoped for LLM provider connections and CLI agent credentials; team-scoped for integrations)
- **Actions** — what the integration can do (create issue, send message, deploy)
- **Events** — what the integration can trigger on (PR created, message received)
- **Data** — what information can be read (issues, messages, metrics)

MCP servers are engine-scoped tool providers. GearTrain should include a sane default set for common development workflows, then let teams add or remove servers per workspace. ACP is a future channel/runtime bridge that should let an ACP-capable IDE talk to the running GearTrain engine directly.

Integration registry (extensible):

| Category | Services | MVP Status |
|----------|----------|------------|
| Agent Tools | MCP servers | Basic curated set: **In scope** |
| Version Control | GitHub, GitLab | GitHub: **In scope** |
| Issue Tracking | Linear, Jira, GitHub Issues | GitHub Issues: **In scope** |
| Communication | Slack, Telegram, Email | Deferred |
| Monitoring | Sentry, Datadog | Deferred |
| Cloud | AWS, GCP, Azure | Deferred |
| CI/CD | GitHub Actions, CircleCI | Deferred |
| Documentation | Notion, Confluence | Deferred |
| IDE Runtime Bridge | ACP | Deferred |

---

## Cross-Cutting Concerns

### Configuration Resolution
Configurations use variable interpolation with scoped resolution:
1. Agent definition → 2. Workflow context → 3. Team config → 4. Engine config → 5. Environment variables

### Security & Guardrails
- Agent memory guardrails prevent storing secrets, credentials, PII
- Tool access is scoped per agent definition
- LLM provider connections are engine-scoped (per-user), never exposed to agents directly
- CLI agent credentials are engine-scoped (per-user), never exposed to agents directly
- Integration credentials are team-scoped, never exposed to agents directly
- Human checkpoints enforce approval gates for sensitive operations
- [To be defined] Audit logging for all agent actions

### Versioning
- MVP: agent definitions, workflow definitions, and persistent memory files are versioned through git
- Future: GearTrain adds internal definition versioning and memory snapshots
- Breaking changes to definitions require explicit migration
- [To be defined] Rollback mechanisms for workflow definitions

### Observability
Observability is required for long-running agent workflows because failures can come from the model, the prompt, the tool, the external API, the workflow definition, or the surrounding runtime. GearTrain should emit structured traces and metrics for each workflow run, agent invocation, LLM call, and tool call.

Minimum telemetry:
- Token usage and estimated cost by workflow, agent, model, and step
- LLM call count, failed LLM calls, retries, latency, and response validation failures
- Tool usage, failed tool calls, retries, timeouts, and fallback paths
- Repeated invocations and repair loops
- Workflow outcomes, human escalations, and failed terminal states

Evals build on this telemetry. They compare prompts, models, routing rules, and workflow definitions against known tasks so teams can control behavior drift, optimize cost, and upgrade models without relying on anecdotes.
