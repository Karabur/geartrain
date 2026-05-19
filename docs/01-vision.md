# GearTrain — Vision & Overview

## What Is GearTrain

GearTrain is a framework for building AI-driven workflows that act as a drivetrain for any project. It treats AI agents not as isolated chat interfaces but as coordinated team members that execute structured workflows — with memory, tool access, human checkpoints, and external integrations.

The first milestone targets software development, but the architecture is domain-agnostic by design: marketing, content creation, user support, operations — any domain where structured work can be decomposed into agent-driven steps.

## Why GearTrain Exists

The current landscape (mid-2026) has two extremes:

1. **Single-agent tools** (Claude Code, Cursor, Copilot) — powerful but isolated. Each session starts mostly from scratch. No persistent team structure, no cross-agent coordination, no workflow memory.
2. **Hardcoded agent frameworks** (CrewAI, AutoGen) — flexible but require engineering effort to configure. Changing a workflow means changing code.

GearTrain fills the gap: **coordinated multi-agent workflows, configured without code, with persistent memory and human-in-the-loop control.**

By 2027, we expect AI work to look less like "chat with a bot" and more like "manage a team of specialists." GearTrain is built for that future.

## What GearTrain Gives Agents

The architecture isn't just an organizational choice — it produces concrete advantages for the agents running inside it.

**Focused environments.** Each agent gets only the tools it needs, only the context relevant to its task, and a system prompt scoped to its role. No kitchen-sink toolbars, no irrelevant project history dumped into the prompt. This reduces token usage, makes tool selection more effective (fewer tools = fewer wrong picks), and cuts the number of roundtrips an agent needs to reach a result.

**Extensible, vendor-agnostic tooling.** Tools are defined once in GearTrain's registry and available to any agent regardless of the underlying LLM or agent framework. Teams build and share tool sets without coupling them to a specific provider. When a new model or SDK shows up, existing tools work without rewriting.

**Rich automatic context.** Agents receive structured context about their running environment (engine, team, integrations), the project they're working in (memory, knowledge base, conventions), and the specific task at hand (workflow state, upstream outputs, relevant history). This context is assembled automatically from GearTrain's layered configuration — agents don't hunt for it, and humans don't hand-assemble it.

## Core Principles

### 1. No-Code Configuration, Full Customization
Every aspect of the system — agents, workflows, memory, integrations — is configurable through structured definitions (YAML/JSON/UI), not application code. Power users can extend with code, but it's never required.

### 2. Agents Are Composable Building Blocks
An agent is a reusable, self-contained unit with a defined role, tools, and memory. Agents are registered in a catalog and can be assembled into any workflow without modification.

### 3. Workflows Are Reusable Artifacts
A workflow (pipeline) is a directed graph of agent steps, decision points, human checkpoints, and integration hooks. Workflows are versioned, shareable, and composable — one workflow can invoke another.

### 4. Memory & Knowledge Are First-Class Systems
Memory (operational — "how" to work) and knowledge base (domain — "what" and "why") are distinct systems. Four memory scopes — agent-instance, workflow, workspace, and agent-level — ensure context is preserved at the right granularity. Both systems use dual-format storage: human-readable for inspection and AI-optimized for retrieval and reasoning.

### 5. Humans Stay in the Loop
Human interaction is not an afterthought. Workflows define explicit checkpoints where human approval, input, or feedback is required. Agents can also communicate with humans asynchronously through configured channels.

### 6. Teams as Isolation Boundaries
A "team" is an organizational unit with its own agents, workflows, integrations, memory, and users. Teams provide multi-tenancy, access control, and configuration isolation.

### 7. Engine-Agnostic Execution
Workflows run on "engines" — local workstations, cloud servers, or (eventually) serverless runtimes. The workflow definition is decoupled from where it runs.

### 8. Agent-Framework Agnostic
The bottom layer supports multiple agent runtimes: LangChain-based agents (primary), CLI agents (Claude Code, Codex), SDK-based agents (Anthropic Agent SDK, OpenAI Agents SDK), and eventually cloud-hosted agents. The framework doesn't lock you into one provider.

### 9. Channel-Agnostic Interaction
Users interact with running workflows through pluggable channels: local web UI, Slack, Telegram, email, or any custom integration. The workflow defines which channels are active.

### 10. Self-Improving Agents
Agents learn from experience. Each agent instance accumulates operational memory — patterns that worked, mistakes to avoid, environment-specific knowledge — within guardrails that prevent storing sensitive data.

## Target Users

**First milestone:** Small development teams (2-5 people) who are also the product owners. They want to use GearTrain to accelerate their own development workflow and are comfortable setting up a local development environment.

**Future:** Any team that wants to automate structured workflows with AI — product managers, marketing teams, support operations, DevOps teams.

## Success Criteria for V1

GearTrain is successful when the GearTrain development team itself uses GearTrain to manage its own development workflow. This means:

- A working software development pipeline (task intake → coding → review → PR → deployment)
- A repo-backed GearTrain workspace that defines the shared agents, workflows, and memory used to develop GearTrain itself
- Persistent project memory that accumulates knowledge across sessions
- Human-in-the-loop checkpoints that feel natural, not obstructive
- At least one external integration (GitHub) working end-to-end
- A developer can configure a new workflow without writing Python code
