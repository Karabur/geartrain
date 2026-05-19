# GearTrain — Memory & Knowledge System Design

## Overview

Memory is what transforms GearTrain from a workflow executor into a learning system. Without memory, every workflow run starts from zero. With memory, agents build on past experience, teams accumulate project knowledge, and the system becomes more effective over time.

The system has three orthogonal dimensions:
- **Type** — memory (operational) vs. knowledge base (domain/product)
- **Scope** — who can access it (workspace, workflow, agent-instance, agent-level)
- **Format** — how it's stored and accessed (human-faced, AI-faced)

---

## Memory vs. Knowledge Base

GearTrain distinguishes between two fundamentally different kinds of persistent information. This separation is an initial direction — the boundary, storage, and interaction patterns need further refinement. [To be defined in detail]

### Memory (Operational)
**What it answers:** "How" to work and "what happened."

Memory is operational context. It records how agents should behave, what approaches work or fail, what happened recently, and what to avoid. Memory is about process, not product.

Examples:
- "When modifying the API layer, always update the OpenAPI spec first"
- "The CI pipeline caches node_modules; invalidate by changing package-lock.json"
- "Last run on this task failed because Docker wasn't running — check docker status before starting"
- "User prefers concise PR descriptions, no more than 5 bullet points"
- "Approach X was tried for the caching problem and failed because of Y — try Z instead"

Memory is consumed primarily by agents to improve their execution. It's the "muscle memory" of the system.

### Knowledge Base (Domain/Product)
**What it answers:** "What" should be done and "why."

The knowledge base contains everything that makes sense in the context of the goal or the product. It holds domain knowledge, task descriptions, implementation details, user input, analysis, specifications, reports, architecture decisions, and product context.

Examples:
- "The project uses PostgreSQL with UUID v7 primary keys and snake_case naming"
- "Sprint 4 goal: complete the workflow editor UI by June 1"
- "Authentication uses JWT tokens with 15-minute expiry — decided in RFC-012"
- "User story: As a team admin, I want to configure LLM providers per agent type"
- "Performance requirements: API responses under 200ms P95"
- "Competitive analysis: CrewAI requires Python coding for workflow definition"

The knowledge base is consumed by both agents (for task context) and humans (for project understanding). It's the "institutional knowledge" of the system.

### Why Separate Them

| Concern | Memory | Knowledge Base |
|---------|--------|---------------|
| Primary consumer | Agents (self-improvement) | Agents + Humans (context) |
| Lifecycle | Decays, gets superseded, consolidates | Versioned, curated, referenced |
| Write frequency | High (agents write constantly) | Lower (humans + agents contribute) |
| Curation model | Automated with guardrails | Human-curated with agent assistance |
| Sensitivity | Low (operational patterns) | Varies (may contain business logic, specs) |
| Cross-project value | High (agent type memory transfers) | Low (mostly project-specific) |

Keeping them separate prevents operational noise from cluttering domain knowledge, and prevents agents from accidentally modifying curated project specifications when they're just trying to record an operational pattern.

[To be defined: exact boundary rules, whether an entry can move between memory and KB, interaction patterns between the two systems, shared vs. separate storage backends, unified vs. separate search interfaces]

---

## Memory Scopes

Four scopes, from narrowest to broadest:

### 1. Agent-Instance Memory
**Scope:** A specific agent instance running on a specific engine, within a specific workflow run.
**Lifecycle:** Created when the agent is instantiated, discarded (or promoted) when the run ends.
**Purpose:** Operational context for this agent in this workflow run — the task it's working on, what it has tried, intermediate results, workflow-specific and project-specific information it needs right now.

Examples:
- "Currently working on task #42: add pagination to the /users endpoint"
- "The feature branch is `feat/user-pagination`, branched from `main` at commit abc123"
- "Already tried approach X for the query optimization, it hit the N+1 problem"
- "User clarified that 'fast' means under 200ms P95, not P50"

Agent-instance memory is the most volatile scope. It contains the working context that makes an agent effective at its current task. Most of it is irrelevant once the task is done, but valuable entries can be promoted.

### 2. Workflow Memory
**Scope:** All agents running within a specific workflow instance on a specific engine.
**Lifecycle:** Created when the workflow run starts, persists for the duration of the run. May outlive individual agent instances within the workflow.
**Purpose:** Operational context that spans multiple agents in the same workflow run — shared state, coordination notes, decisions that affect the whole workflow. Contains information that can't be scoped to a single agent because more than one agent needs it.

Examples:
- "QA agent found a regression in the auth module; coder agent should fix before proceeding"
- "Human approved the implementation plan with a modification: skip the caching layer for V1"
- "The deployment target for this run is staging, not production"
- "Review agent flagged 3 issues; 2 were addressed by coder, 1 is deferred per human decision"

Workflow memory is the communication medium between agents within a single run. It replaces the need for direct agent-to-agent messaging for most coordination needs.

### 3. Agent-Level Memory (Agent Type Memory)
**Scope:** Shared between all instances of a specific agent type, across all workflows and all engines.
**Lifecycle:** Persistent. Grows over time as agent instances contribute learnings. Subject to consolidation and decay.
**Purpose:** Accumulated experience of a role — how to do the job well. This is the self-improvement memory. Sensitive information is stripped; only operational patterns and learnings are kept.

Examples (for a "coder" agent type):
- "Always run `npm install` after pulling changes if package-lock.json was modified"
- "When writing tests for async handlers, use `jest.useFakeTimers()` to avoid flaky tests"
- "Prefer small, focused commits over large monolithic ones — reviewers consistently request splits"
- "When the linter reports unused imports after refactoring, check for re-exports before deleting"

Agent-level memory is how GearTrain agents improve over time. A new coder agent instance on a fresh project benefits from everything previous coder instances learned across all projects. This is the highest cross-project value scope.

**Guardrails:** Agent-level memory must not contain project-specific details, credentials, PII, or business logic. Only transferable operational knowledge is stored. Content is filtered before promotion from agent-instance memory.

### 4. Workspace Memory
**Scope:** Shared between all workflows and all agents within a team/workspace/project.
**Lifecycle:** Persistent. Curated by humans and agents. The most stable scope.
**Purpose:** Global operational context for the workspace — conventions, tool configuration, environment setup, team preferences, cross-workflow coordination.

Examples:
- "All PRs require at least one human approval before merge"
- "The staging environment is at staging.geartrain.dev, deployed via GitHub Actions"
- "Team convention: use conventional commit messages"
- "Slack notifications go to #dev-notifications, not #general"
- "The Docker setup requires at least 8GB RAM allocated to Docker Desktop"

Workspace memory is the operational counterpart to the workspace-level knowledge base. Where the KB stores "what the project is and what should be built," workspace memory stores "how the team works and how the environment is set up."

### Scope Hierarchy and Access

An agent can read from all scopes it's contained within, but writes are scoped:

```
┌─────────────────────────────────────────────────┐
│  Workspace Memory (team-wide operational)       │  ← all agents read
│  ┌─────────────────────────────────────────────┐│
│  │  Workflow Memory (per-run, multi-agent)     ││  ← agents in this run read/write
│  │  ┌─────────────────────────────────────────┐││
│  │  │  Agent-Instance Memory (per-agent run)  │││  ← this agent reads/writes
│  │  └─────────────────────────────────────────┘││
│  └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Agent-Level Memory (per agent type, global)    │  ← all instances of this type read
└─────────────────────────────────────────────────┘    writes via promotion only
```

Agent-level memory sits outside the workspace hierarchy because it's cross-project. A coder agent's operational learnings apply regardless of which workspace or workflow it's running in.

---

## Knowledge Base Scopes

The knowledge base follows a simpler two-level model. [To be defined in more detail]

### Workspace Knowledge Base
Project-wide domain knowledge: architecture, specifications, design decisions, requirements, reports, analysis.

### Workflow Knowledge Base
Workflow-specific reference material: task descriptions, acceptance criteria, relevant documentation for the current workflow's domain.

[To be defined: whether agent-level or agent-instance KB scopes are needed, or whether agents always pull from workspace/workflow KB]

---

## Memory Promotion

When an agent instance or workflow run completes, the system evaluates whether operational memories should be promoted to a broader scope:

```
Agent-Instance Memory → Workflow Memory      (multi-agent coordination patterns)
Agent-Instance Memory → Agent-Level Memory   (transferable operational patterns)
Agent-Instance Memory → Workspace Memory     (environment/team-specific operations)
Workflow Memory       → Workspace Memory     (cross-workflow operational knowledge)
```

Promotion criteria:
- **Generalizability** — is this useful beyond this one run / this one workflow?
- **Novelty** — is this already known at the target scope?
- **Safety** — does it pass guardrail checks? (especially important for agent-level, which is cross-project)
- **Sensitivity stripping** — for agent-level promotion, project-specific details must be abstracted away

Promotion can be automatic (with guardrails) or require human approval (configurable per team).

---

## Memory Formats

### The Problem with Current Approaches
Plain markdown files are the current mainstream approach for AI memory (as used in CLAUDE.md, AGENTS.md, etc.). They work but have significant limitations:
- No structured metadata for filtering or ranking
- Linear search only — no semantic retrieval
- No distinction between "meant for humans to read" and "meant for AI to process"
- Difficult to manage at scale (hundreds of memory entries)
- No support for temporal reasoning ("what did we know at time X?")

### Dual-Format Architecture

GearTrain uses two parallel storage formats, kept in sync, each optimized for its consumer:

#### Human-Faced Storage
**Consumer:** Humans inspecting, editing, curating memory and knowledge base entries.
**Format (MVP):** Markdown files with YAML frontmatter.
**Future:** HTML/rich-text editor, wiki-style interface, or whatever best serves human readability.

For MVP, persistent memory lives inside the project repo under `.geartrain/memory/`. Git is the sharing and versioning system: memory changes can be reviewed in PRs, reverted with normal git tools, and carried across machines through clone/pull.

```markdown
---
system: memory          # or: knowledge_base
scope: workspace
category: convention
created: 2026-05-18
updated: 2026-05-18
source: agent:coder/run-42
confidence: 0.9
tags: [git, conventions]
---

# Commit Message Convention

Team uses conventional commits format. All commits must have a type prefix
(feat, fix, chore, docs, refactor, test). Scope is optional but encouraged.
Breaking changes must use the `!` suffix.
```

Human-faced storage is the "source of truth" for content. Humans can edit these files directly, and changes propagate to the AI-faced store.

#### AI-Faced Storage
**Consumer:** Agents retrieving relevant context for their current task.
**Format (MVP):** Vector store (ChromaDB or similar) with structured metadata.
**Future:** Purpose-built memory database with support for temporal queries, causal graphs, confidence scoring, and dreaming (background consolidation and inference).

Each entry in the AI-faced store contains:
- **Embedding** — vector representation for semantic search
- **Content** — the actual text
- **Metadata** — structured fields for filtering:
  - `system` (memory | knowledge_base)
  - `scope` (workspace | workflow | agent_instance | agent_level)
  - `category` (convention | pattern | decision | issue | learning | architecture | spec | ...)
  - `agent_type` (for agent-level-scoped entries)
  - `workflow_id` (for workflow-scoped entries)
  - `agent_instance_id` (for instance-scoped entries)
  - `confidence` (0.0-1.0, how reliable this entry is)
  - `access_count` (how often retrieved)
  - `last_accessed` (for recency ranking)
  - `source` (what created this: agent run, human edit, promotion)
  - `supersedes` (link to an entry this one replaces)
  - `tags` (free-form labels)
  - `created_at`, `updated_at`

### Sync Between Formats
```
Human edits markdown → sync engine → update vector store
Agent writes entry   → sync engine → generate/update markdown file
```

The sync engine runs bidirectionally:
- **Human → AI:** When a markdown file is created/edited, the sync engine re-embeds it and updates the vector store entry.
- **AI → Human:** When an agent creates an entry, the sync engine generates a markdown file with appropriate frontmatter.

Conflict resolution: human edits always win. If a human modifies a markdown file that an agent also modified, the human version is kept.

---

## Memory Operations

### Write
An agent writes an entry. The system:
1. Checks guardrails (no secrets, PII, credentials)
2. Classifies as memory vs. knowledge base
3. Determines scope (instance, workflow, workspace, or agent-level)
4. Checks for duplicates/supersession
5. Stores in AI-faced format
6. Generates/updates human-faced file
7. Logs the write for audit

### Read (Retrieval)
An agent requests relevant entries for its current context. The system:
1. Determines the agent's accessible scopes (instance + workflow + workspace + agent-level)
2. Determines which system(s) to query (memory, knowledge base, or both)
3. Performs semantic search with the query
4. Applies metadata filters (system, scope, category, tags)
5. Ranks results by relevance, recency, confidence, and access patterns
6. Returns top-K results with metadata

### Forget
An entry is marked as deprecated or removed. The system:
1. Marks the AI-faced entry as inactive (soft delete)
2. Moves or annotates the human-faced file
3. Logs the deletion for audit
4. Related entries are not automatically removed (but may lose confidence over time)

### Dream (Future)
A background process that consolidates and improves memory:
- Merges near-duplicate entries
- Infers new connections between memories
- Decays confidence on stale, unaccessed memories
- Generates summary memories from clusters of related entries
- Identifies contradictions and flags them for human review

---

## Guardrails

### What Must Not Be Stored in Memory
- Credentials (API keys, tokens, passwords)
- PII (names, emails, phone numbers of end users)
- Secrets (encryption keys, certificates)
- Raw sensitive data (customer data, financial records)
- Project-specific details in agent-level memory (must be abstracted for cross-project use)

### How Guardrails Work
1. **Pattern matching** — regex-based detection of common secret formats (API keys, JWTs, etc.)
2. **LLM classification** — the content is classified by a lightweight LLM check before storage
3. **Allowlists/blocklists** — team-configurable lists of terms that are always/never allowed
4. **Human review queue** — optionally, new entries above a sensitivity threshold are queued for human approval
5. **Promotion filters** — additional checks when promoting from instance to broader scopes, especially to agent-level

### What Should Be Stored

**In Memory:**
- How to operate effectively in this environment
- Patterns that worked or failed
- Tool-specific tips and gotchas
- Feedback received and lessons learned
- Coordination notes between agents

**In Knowledge Base:**
- Architecture decisions and rationale
- Specifications and requirements
- Domain knowledge and business context
- Analysis results and reports
- User input and clarifications

---

## MVP Implementation

For the 2-week MVP, the system is simplified:

| Feature | MVP | Future |
|---------|-----|--------|
| Memory/KB separation | Single git-backed markdown store with `system` tag | Separate storage and interfaces |
| Workspace memory | Markdown files with YAML frontmatter in `.geartrain/memory/workspace/` | Dual-format with vector store |
| Workflow memory | Markdown files for reusable workflow memory and run summaries; LangGraph state for active run state | Persistent, queryable workflow state and dual-format memory |
| Agent-instance memory | In-process state (LangGraph state) | Persistent with promotion |
| Agent-level memory | Markdown files scoped by agent type in `.geartrain/memory/agent-types/` | Dual-format with cross-project sync |
| Knowledge base | Markdown files in project docs | Structured KB with versioning |
| Semantic search | Keyword-based (grep + metadata) | Vector embeddings + ranking |
| Format sync | Manual (human edits markdown) | Bidirectional auto-sync |
| Guardrails | Pattern matching only | Pattern + LLM classification |
| Dreaming | Not implemented | Background consolidation |
| Promotion | Manual | Automated with guardrails |
| Temporal queries | Not implemented | Time-scoped retrieval |

The MVP system is intentionally built as a module with a clean interface, so the backend can be swapped without changing how agents interact with memory.

The default repo layout is:

```text
.geartrain/
├── workspace.yaml
├── agents/
├── workflows/
└── memory/
    ├── workspace/
    ├── workflows/
    └── agent-types/
```

This layout makes the first usable GearTrain workspace part of GearTrain's own codebase. It also defers team, user, and authentication complexity until the core workflow loop is useful.

### MVP Interface

```python
class MemoryStore(Protocol):
    def write(self, entry: MemoryEntry, scope: MemoryScope, system: System) -> str: ...
    def read(self, query: str, scopes: list[MemoryScope], filters: dict) -> list[MemoryEntry]: ...
    def update(self, entry_id: str, content: str, metadata: dict) -> None: ...
    def forget(self, entry_id: str) -> None: ...
    def list(self, scope: MemoryScope, system: System, filters: dict) -> list[MemoryEntry]: ...
```

Where:
- `MemoryScope` = `workspace | workflow | agent_instance | agent_level`
- `System` = `memory | knowledge_base`

This interface remains stable as the backend evolves from markdown files to vector stores to purpose-built databases.

---

## Open Questions [To Be Defined]

1. **Memory vs. KB boundary rules** — how does an agent decide whether something is operational (memory) or domain knowledge (KB)? Automated classification? Agent decision? Human curation?
2. **Unified vs. separate search** — should agents query memory and KB with one call, or explicitly choose which system to query?
3. **Knowledge base versioning** — KB entries (specs, decisions) should be versioned. What's the versioning model? Git-backed? Internal?
4. **KB editing workflow** — who can edit the KB? Agents with approval? Humans only? Mixed?
5. **Agent-level memory portability** — how are agent-level memories transferred when a team switches to a different LLM provider?
6. **Cross-team KB sharing** — can teams share KB entries (e.g., common domain knowledge)? Access control model?
7. **Dreaming triggers** — what triggers the dreaming process? Schedule? Memory count threshold? Workflow completion?
8. **Cost of memory** — with dual-format and sync, memory has real storage and compute costs. How to budget and limit?
