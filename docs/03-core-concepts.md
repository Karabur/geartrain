# GearTrain — Core Concepts

## Glossary

### Agent
A self-contained AI unit configured to perform a specific role. An agent has a system prompt, a set of tools it can use, LLM configuration, and memory. Agents are the atomic building blocks of GearTrain — they don't know about workflows; they receive inputs, do work, and produce outputs.

**Key distinction:** An agent *definition* is a reusable template (stored in the registry). An agent *instance* is a running copy of that definition within a specific workflow execution, with its own context and instance memory.

### Agent Type
A category of agent runtime. The primary type is `langchain` (configured via YAML, runs on LangChain). Future types include `cli` (wraps a local CLI tool like Claude Code), `sdk` (built on a vendor-specific agentic SDK like Anthropic Agent SDK or OpenAI Agents SDK), and `cloud` (calls a remote agent API). Agent type determines how the agent is instantiated and what infrastructure it needs.

The `sdk` type covers agents built on vendor-managed agentic frameworks that own their own execution loop. GearTrain provides the running environment (tools, memory, context) but delegates the agent loop to the SDK. How SDK-native capabilities integrate with GearTrain's tool system and memory is [to be defined].

### Agent Registry
A team-scoped catalog of all agent definitions. The registry is the single source of truth for what agents are available. Agents are referenced by name in workflow definitions.

### Workflow (Pipeline)
A directed graph that defines how multiple agents collaborate to accomplish a goal. Built on LangGraph, a workflow specifies the sequence of agent invocations, decision points, human checkpoints, and integration steps. Workflows are the primary unit of automation in GearTrain.

"Workflow" and "pipeline" are used interchangeably. Both refer to the same concept: a reusable, configurable orchestration artifact.

### Workflow Run
A single execution of a workflow. A workflow definition can have many concurrent runs (e.g., multiple features being developed simultaneously). Each run has its own state, context, and active agent instances.

### Workflow Registry
A team-scoped catalog of workflow definitions. Similar to the agent registry but for workflows. Workflows are versioned and can be activated or deactivated.

### Team
An organizational boundary that groups users, agents, workflows, integrations, and memory into an isolated unit. Think of it as a "workspace" or "organization." Each team has its own agent/workflow registries, integration credentials, and data. The team declares which LLM providers and models to use, but LLM provider connections and CLI agent credentials are engine-scoped. Each user has their own connection and is responsible for setting it up locally so their engine can run. Future: teams can provision per-user LLM and CLI agent credentials centrally.

Teams provide multi-tenancy: one GearTrain installation can host multiple teams with no data leakage between them.

For MVP, this is implemented as a single git-backed workspace folder inside the project repo. Git repo access replaces GearTrain-specific users, roles, and authentication until the core workflow loop is useful.

### Workspace
A repo-local project configuration bundle. It contains the agent registry, workflow registry, memory folders, knowledge pointers, and integration references that the local engine should load.

The default MVP workspace lives at `.geartrain/` and is versioned with the project code. GearTrain's own repo should include a working workspace so GearTrain can develop itself from day one.

### Engine
The runtime environment that executes workflows. An engine runs on a specific host (local workstation or cloud server), manages workflow state, handles concurrency, and exposes channels for user interaction.

One engine can run multiple workflows concurrently. The engine is responsible for:
- Starting and stopping workflow runs
- Persisting workflow state (for interruption recovery)
- Managing agent concurrency limits
- Routing channel messages to the correct workflow/agent

### Channel
A communication interface between humans and running workflows. Channels are bidirectional: they deliver notifications/questions from agents to humans, and relay human responses back to the workflow.

Channels are pluggable — the same workflow can use different channels depending on team configuration. A human checkpoint might send an approval request to Slack in one team and to email in another.

### Human-in-the-Loop (HIL) Checkpoint
A workflow node that pauses execution and waits for human input. Checkpoints are typed:
- **Approval** — binary yes/no to proceed
- **Choice** — select from options presented by an agent
- **Input** — provide free-form information (requirements, context, feedback)
- **Review** — inspect agent output and approve, reject, or modify

Checkpoints have configurable timeouts and escalation paths.

### Integration
A connector to an external service (GitHub, Slack, Linear, Sentry, AWS, etc.). Integrations provide three capabilities:
1. **Actions** — things the integration can do (create PR, send message)
2. **Events** — things that can trigger workflows (PR created, issue assigned)
3. **Data** — information that can be read (repository state, issue list)

Integrations are configured at the team level and made available to agents and workflows by reference.

### Memory
Operational knowledge — "how" to work and "what happened." Persists across workflow runs and agent instances. See [04-memory-system.md](04-memory-system.md) for full design.

**Scopes (narrow to broad):**
- **Agent-Instance Memory** — operational context for this agent in this workflow run (task state, what's been tried)
- **Workflow Memory** — shared context across agents within a single workflow run (coordination, shared decisions)
- **Workspace Memory** — team-wide operational context (conventions, environment setup, tool configuration)
- **Agent-Level Memory** — cross-project learnings for an agent type (self-improvement, transferable patterns)

### Knowledge Base
Domain and product knowledge — "what" should be done and "why." Contains architecture decisions, specifications, requirements, analysis, reports, and domain context. Consumed by both agents (for task context) and humans (for project understanding). See [04-memory-system.md](04-memory-system.md).

### Storage Formats
Both memory and knowledge base use dual-format storage:
- **Human-Faced** — readable and editable by humans (Markdown for MVP)
- **AI-Faced** — optimized for machine retrieval and reasoning (vector store, future: purpose-built DB)

### Tool
A capability available to an agent — file operations, shell commands, API calls, search, etc. Tools are defined in the system and assigned to agents via their definitions. An agent can only use tools explicitly granted to it.

### Trigger
What starts a workflow run. Types include:
- **Manual** — user explicitly starts a run
- **Event** — external event (webhook, integration event) starts a run
- **Schedule** — cron-like periodic execution
- **Agent** — another agent or workflow requests a sub-workflow

### Decision Node
A workflow node that routes execution based on conditions. Conditions can be based on agent output, memory state, integration data, or static rules. Decision nodes are how workflows handle branching logic (e.g., "if tests pass, go to review; if they fail, go back to coding").

### Guardrail
A constraint applied to an agent or workflow that limits what it can do. Examples:
- Maximum number of files an agent can modify
- Forbidden file paths (secrets, config)
- Required steps (must run tests before creating PR)
- Memory guardrails (don't store credentials or PII)
- Cost guardrails (maximum LLM tokens per agent invocation) [to be defined]

### Sub-workflow
A workflow that is invoked as a step within another workflow. This enables composition: a "CI/CD" workflow might invoke a "deploy" sub-workflow and a "smoke-test" sub-workflow. Sub-workflows are registered in the same registry and can be used independently or as components.

---

## Relationship Map

```
Team
├── Users
├── LLM Defaults (provider, model — no provider connection)
├── Integrations (GitHub, Slack, ...)
├── Memory (Project scope)
├── Agent Registry
│   └── Agent Definitions
│       ├── Tools
│       ├── System Prompt
│       ├── LLM Config (provider/model from team; connection from engine)
│       └── Agent Type Memory
└── Workflow Registry
    └── Workflow Definitions
        ├── Agent Steps (reference agents from registry)
        ├── Decision Nodes
        ├── HIL Checkpoints
        ├── Integration Steps
        ├── Triggers
        └── Channels

Workspace (MVP)
├── .geartrain/workspace.yaml
├── .geartrain/agents/
├── .geartrain/workflows/
└── .geartrain/memory/
    ├── workspace/
    ├── workflows/
    └── agent-types/

Engine
├── LLM Provider Connections (per-user API keys/accounts)
├── CLI Agent Credentials (per-user subscriptions)
├── Runs Workflows (from one or more teams)
├── Manages State
├── Exposes Channels (Web UI, CLI, Slack, ...)
└── Workflow Runs
    └── Agent Instances
        └── Agent Instance Memory
```

---

## Configuration Hierarchy

Configuration values resolve through a chain, with more specific values overriding more general ones:

1. **Agent definition** — most specific, wins if set
2. **Workflow context** — per-run overrides
3. **Team configuration** — team-wide defaults
4. **Engine configuration** — engine-level defaults
5. **Environment variables** — system-level fallback

Variable interpolation syntax: `${scope.key}` (e.g., `${team.llm.model}`, `${engine.llm.anthropic.api_key}`, `${env.GITHUB_TOKEN}`)

Engine-scoped connection values are local to the user running the engine. Team configuration can reference provider and model names, but it must not require a shared LLM API key or shared CLI agent account for MVP.
