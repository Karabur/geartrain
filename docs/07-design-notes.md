# GearTrain — Design Notes & Extended Concepts

This document covers concepts from the original vision that don't fit cleanly into the other documents, including future-proofing strategies, underspecified areas, and design rationale for deferred features.

---

## Self-Bootstrapping as a Design Principle

GearTrain developing GearTrain is not just a V1 validation milestone — it's a permanent design property. The system should always be capable of driving its own development. This creates a feedback loop:

1. **Using GearTrain reveals friction** → friction becomes a task → task flows through GearTrain → improvement is shipped
2. **Improving GearTrain improves the tool** → the tool develops GearTrain better → more friction is revealed → cycle continues

This means every feature decision should be evaluated through the lens: "does this make GearTrain better at developing itself?" If the answer is no and the feature doesn't serve an external use case yet, it should be deprioritized.

The self-bootstrapping property also acts as a quality gate: if the team doesn't want to use GearTrain for its own work, something is fundamentally wrong.

---

## Task Assignment, Outcomes & Agent Triggering

These are workflow-level concepts that deserve explicit definition:

### Task Assignment Rules
Within a workflow, tasks are assigned to agents based on configurable rules:

```yaml
# Example: in a workflow definition
assignment:
  strategy: round_robin | least_busy | skill_match | manual
  fallback: queue  # if no agent is available, queue the task
```

For MVP, assignment is implicit — each workflow node specifies which agent handles it. Dynamic assignment (round-robin, skill-match) is a post-MVP feature for workflows with agent pools.

### Outcome Definitions
Each agent node in a workflow produces typed outcomes that determine the next step:

```yaml
# Example: coder node outcomes
outputs:
  - name: changes
    type: code_diff
    description: "Successfully implemented changes"
    transitions_to: test
  - name: blocked
    type: blocker_report
    description: "Cannot proceed, needs human input"
    transitions_to: human_review
  - name: failed
    type: error_report
    description: "Implementation failed after retries"
    transitions_to: escalate
```

Outcomes are the contract between a workflow node and the transition logic. The workflow engine validates that every possible outcome has a defined transition.

### Agent Triggering
Agents can be triggered by:
- **Workflow transition** — the previous node completed and this agent is next (primary mechanism)
- **Event** — an external event matches the agent's trigger condition (e.g., GitHub webhook)
- **Schedule** — cron-like periodic invocation
- **Another agent** — direct invocation within the same workflow (for sub-tasks)
- **Human** — manual trigger via channel

For MVP, only workflow-transition triggering is implemented. Event and schedule triggering are post-MVP.

---

## Agent as an Abstraction

An agent is an abstraction, not a single implementation. It takes a task plus assembled context and returns a plain text result. From the workflow's point of view every agent looks the same: a node you invoke and read output from. The workflow never branches on what kind of agent it is.

Implementations differ in two ways — how they produce the result, and what configuration they need. The `type` field on an agent definition selects the implementation and decides which config block applies. MVP ships two types:

- **`langchain`** — GearTrain owns the agent loop. The definition carries an `llm` block (model hint, temperature, per-action routes), a `tools` list drawn from GearTrain's registry, and context/memory config. The model is provider-agnostic, so this is also where open-source local LLMs plug in (Ollama, or any OpenAI-compatible endpoint).
- **`cli`** — GearTrain shells out to an external CLI agent in headless one-shot mode (default `codex exec`). The CLI owns its own loop, tools, and sandbox. The definition carries a `cli` block (command, args, timeout, working folder, sandbox/approval mode, credential reference) instead of `llm`/`tools`. GearTrain front-loads everything into the prompt; it does not inject GearTrain tools mid-run.

The two share one interface: `run(task, context) -> str`. In LangGraph terms both become a node — a `cli` agent is a function wrapped as a `RunnableLambda`, a `langchain` agent is built with `create_agent` (itself a compiled graph). The workflow only ever calls `.invoke()`.

Anchor the GearTrain agent interface at the node/Runnable level, not the model level. LangChain's own agnosticism lives at the model layer (`BaseChatModel`, swap one LLM for another), but that abstraction assumes a chat-completion model and can't hold a CLI agent or a future non-LLM agent. The node level is the altitude that absorbs all of them — `langchain`, `cli`, and later `sdk` or `cloud` — without the workflow definition changing.

Config divergence between types is expected and fine. Validation dispatches on `type`: a `langchain` agent requires `llm` and `tools`; a `cli` agent requires `cli`. A shared core (`name`, `description`, `system_prompt`, memory scopes consumed as prompt context) stays common across both.

### Why `cli` is in the MVP

The `cli` type is the fastest path to a running loop — no agent-runtime code, just a subprocess that returns text. It also unlocks subscription-based execution: `codex exec` reuses the user's saved CLI auth, so headless runs draw on a ChatGPT subscription instead of per-token API billing. That's a real cost lever for heavy dogfooding, with two caveats worth recording. OpenAI recommends an API key (not subscription auth) for unattended/CI runs, so the subscription path is available but against their guidance. And on the Anthropic side, headless `claude -p`/Agent SDK usage now bills at API rates from a separate credit pool rather than the interactive subscription, and keeping subscription auth alive headless violates the ToS — so the subscription arbitrage currently applies to Codex, not Claude Code. Treat it as a near-term cost lever, not an architectural assumption; the agnostic interface means a `cli` node can be swapped for an API-billed `langchain` node without touching the workflow.

---

## User-Controlled IDE/CLI Agents

GearTrain should support coding workflows where the implementation step happens inside the user's preferred IDE or CLI agent instead of a GearTrain-started process. This is different from wrapping a CLI agent as an autonomous runtime. The user remains in the loop, drives the IDE or CLI session, and sends completed work back to the engine when ready.

This is distinct from the MVP `cli` agent type. The MVP `cli` agent is headless and one-shot: GearTrain spawns `codex exec`, waits, and reads the result. The user-controlled mode below is interactive and long-lived: the engine doesn't spawn anything, it waits on an external IDE or CLI session the developer drives, then resumes when results come back. It adds a runtime connection, an engine-owned wait state, validation, and resume behavior on top of the one-shot model.

The workflow can model this as an `ide` or `external` agent type (separate from the headless `cli` type). When execution reaches that node, the engine doesn't spawn an agent process. It marks the workflow as waiting on an external agent connection, exposes the task context, and waits for a completion signal.

The external agent should get context through a standard connection, most likely an MCP server exposed by the engine. A typical flow:

1. A workflow reaches the `coder` node.
2. The engine sees that the assigned agent is user-controlled.
3. The engine publishes the current task, relevant memory, constraints, and expected plain text response format through MCP or an equivalent local protocol.
4. The user opens an IDE or CLI agent and asks it to pull the current task.
5. The IDE or CLI agent works with the user in a normal interactive coding session.
6. When the work is complete, the agent sends results back to the engine.
7. The engine validates the result and continues the workflow.

This enables high-involvement coding workflows: exploratory implementation, architecture-heavy changes, debugging sessions, and work that requires ongoing user guidance. GearTrain still owns run state, memory, transitions, and validation, but the coding session can stay in the tool where the developer is most productive.

The integration should be CLI-agent agnostic. GearTrain may detect installed agents and configure a local MCP or skill bridge automatically. If detection fails, it should provide manual setup instructions. After connection setup, the workflow contract should be the same for Claude Code, Codex, Cursor, other AI IDEs, or future local agent tools.

The same agent should be switchable to autonomous mode. At any point, the user can tell the external agent to finish without further involvement. From the engine's perspective, the node is still waiting on the same external connection; only the interaction style changes from user-guided to autonomous.

This is probably too large for the MVP runtime, but it may be the right fast follow after the first minimal dogfooding loop works. It could help GearTrain reach the "GearTrain builds GearTrain" milestone faster because the first coding workflow can coordinate real work without replacing the developer's existing IDE or CLI agent.

Open questions [to be defined]:
- Agent type vocabulary: `ide`, `cli`, `user`, or a more general `external`
- Protocol: MCP only, ACP where available, or a small GearTrain local API with MCP as the first adapter
- Result contract: diff, branch name, commit, PR, structured task report, or all of these
- Ownership model: whether the external agent can write memory directly or only return proposed memory updates
- Timeout and cancellation behavior while the workflow waits for an external connection
- How autonomous-mode switching is represented in run state and audit history

---

## Product Manager Agent & Proactive Human Communication

The vision describes a PM agent that proactively communicates with humans — not just at HIL checkpoints, but as an ongoing dialogue partner. This is distinct from the "Team Lead" agent in the MVP.

### PM Agent Responsibilities (Post-MVP)
- **Requirements gathering:** Reaches out to stakeholders on configured channels (Slack, email) to collect business requirements, acceptance criteria, and priorities
- **Status updates:** Proactively sends progress reports to stakeholders on a schedule or when milestones are reached
- **Feedback collection:** After deployment, solicits feedback from users and stakeholders
- **Context bridging:** Translates between business language (stakeholder input) and technical language (agent workflows)

### Communication Model
Unlike HIL checkpoints (which are pull-based — the workflow pauses and waits), PM communication is push-based: the agent initiates contact and handles async responses.

```yaml
# Future: PM agent communication config
communication:
  channels:
    - type: slack
      target: "#product-planning"
      purpose: status_updates
    - type: slack
      target: "@product_owner"
      purpose: requirements_gathering
  schedule:
    status_update: "0 9 * * 1"   # Weekly Monday 9am
    feedback_collection: "0 10 * * 5"  # Weekly Friday 10am
  async_response:
    timeout: 48h
    reminder: 24h
```

For MVP, the team lead agent handles basic planning in the feature development workflow. The full PM agent concept is deferred.

---

## External Service Integration Patterns

### Sentry Integration Example
The original vision describes a feedback agent that connects to Sentry, analyzes traces, and creates tasks or reports. This illustrates a general pattern:

```
External Service (Sentry) → Event/Poll → Integration Adapter → Agent → Action (create issue, update memory)
```

Concrete flow:
1. Integration polls Sentry API for new errors/performance issues (or receives webhook)
2. Feedback agent receives the trace data
3. Agent analyzes: is this a known issue? A regression? A new bug?
4. Agent cross-references with project memory (known issues, recent changes)
5. Agent decides: create a new issue in the tracker, update an existing issue, or add to project memory as a known pattern
6. Agent can also generate a report for human review

This pattern generalizes to any monitoring/observability tool (Datadog, PagerDuty, CloudWatch). The integration provides the data; the agent provides the intelligence.

### Integration Architecture
Each integration follows a standard adapter pattern:

```python
class Integration(Protocol):
    """Base integration interface."""
    
    def authenticate(self, credentials: dict) -> None: ...
    def get_actions(self) -> list[Action]: ...      # what can this do
    def get_events(self) -> list[EventType]: ...    # what can trigger workflows
    def get_data_sources(self) -> list[DataSource]: ... # what data can be read
    
    # Exposed as LangChain tools to agents
    def as_tools(self) -> list[BaseTool]: ...
```

New integrations are added by implementing this interface and registering them in the integration registry. No changes to the core engine required.

---

## Non-Software Workflow Examples

The architecture is domain-agnostic. Here are sketches for non-software workflows to validate that the architecture supports them:

### Content Creation Workflow
```
Trigger: Content calendar event or manual request
Agents: Researcher, Writer, Editor, Publisher
Flow:
  1. Researcher gathers sources and key points on the topic
  2. Writer produces a draft based on research + brand guidelines (project memory)
  3. Editor reviews for quality, tone, accuracy
  4. Human checkpoint: final approval
  5. Publisher formats and posts to configured channel (blog, social media)
Memory: Brand voice guidelines, past content performance, audience insights
```

### Marketing Campaign Workflow
```
Trigger: Campaign brief (manual) or schedule
Agents: Strategist, Content Creator, Analyst
Flow:
  1. Strategist analyzes campaign brief, target audience, past performance
  2. Content Creator produces campaign assets (copy, outlines)
  3. Human checkpoint: review and approve
  4. After launch: Analyst monitors performance metrics
  5. Analyst generates reports and optimization recommendations
Memory: Brand guidelines, audience profiles, past campaign results
Integrations: Analytics API, social media APIs, email marketing API
```

### User Support Workflow (Expanded)
```
Trigger: User message (Slack, email, in-app chat, feedback form)
Agents: Classifier, Responder, Escalation Handler
Flow:
  1. Classifier categorizes the request (bug, feature request, question, complaint)
  2. Responder searches knowledge base + product docs for relevant answer
  3. If confident: auto-respond with approval gate (or directly, configurable)
  4. If not confident: escalate to human support agent
  5. Log the interaction: category, resolution, satisfaction
  6. If bug: create issue in tracker with reproduction details
  7. If endorsement: log for product team reporting
Memory: Product FAQ, troubleshooting guides, known issues, user sentiment trends
```

These workflows use the same building blocks as software development: agents, memory, integrations, HIL checkpoints, channels. The architecture doesn't need to change.

---

## Memory Future-Proofing Strategy

### The Strategy
The memory system is explicitly designed to evolve through three phases without breaking the agent-facing interface:

**Phase 1 (MVP):** Git-backed markdown files with keyword search for persistent scopes (workspace, workflow, agent-type, KB) plus file-backed run state and append-only run events. The `MemoryStore` Protocol defines the memory interface. Agents interact with memory/KB through `memory_read`, `memory_write`, `kb_read`, `kb_write` tools. State shape stays easy to inspect and manually edit while the workflow model is still changing.

**Phase 2 (Post-MVP):** Vector store backend (ChromaDB or Qdrant). The `MemoryStore` implementation changes but the Protocol stays the same. Agents don't know or care that search is now semantic. Human-faced markdown files are still generated and kept in sync.

**Phase 3 (Future):** Purpose-built memory database with:
- Temporal queries ("what did we know about X as of date Y?")
- Causal graphs (memory A led to decision B which caused outcome C)
- Confidence decay (unaccessed memories lose confidence over time)
- Dreaming (background process that consolidates, infers, and prunes)
- Cross-team memory sharing (opt-in, with access control)

The Protocol may grow new optional methods (e.g., `dream()`, `temporal_read()`), but the core `read/write/update/forget` interface remains stable.

### Why This Works
The key insight is that agents don't need to understand memory internals. An agent says "find memories about database schema conventions" and gets results. Whether those results came from grep, vector similarity, or a causal graph is an implementation detail. By locking the interface early and keeping it simple, the backend can evolve independently.

### Dreaming: Design Intent
"Dreaming" is a background process that runs between workflow executions:
- **Consolidation:** Merges near-duplicate memories into canonical entries
- **Inference:** Identifies patterns across memories and creates new synthetic memories (e.g., "agent X consistently struggles with task Y" → create a guidance memory)
- **Decay:** Reduces confidence on memories that haven't been accessed in N days/runs
- **Contradiction detection:** Flags pairs of memories that assert incompatible facts
- **Summarization:** Creates higher-level summary memories from clusters of detailed ones

Dreaming is triggered on a schedule (e.g., nightly) or after a configurable number of workflow runs. Results are written back through the standard `MemoryStore` interface and are visible in human-faced format for review.

[To be defined: dreaming triggers, LLM cost implications, human approval for synthetic memories]

---

## Git Workflow Integration

The vision mentions git workflow rules (git flow, worktrees). This is how it maps to GearTrain:

### Configurable Git Strategy
Each workflow can specify its git strategy:

```yaml
git:
  strategy: feature_branch | trunk_based | gitflow
  branch_prefix: "feat/"           # for feature_branch strategy
  base_branch: main
  worktree: true                    # use git worktrees for isolation
  auto_commit: true                 # agent commits as it works
  commit_convention: conventional   # conventional commits format
```

### MVP Git Support
For MVP, git has two jobs. It is the code collaboration layer, and it is the sharing/versioning layer for `.geartrain/` workspace definitions and persistent memory files.

The coder agent has git tools (branch, commit, push, create PR) and follows a simple feature-branch model. Git strategy configuration is hardcoded to feature-branch. Worktree support, alternative strategies, hosted team workspaces, and GearTrain-specific authentication are post-MVP.

---

## Serverless Workflows (Future)

Serverless execution is listed as a distant future goal. Design considerations to capture now:

- **Stateless by definition:** Workflow state must be externalized, not in-memory. MVP state is file-backed markdown; serverless would need a networked state store.
- **Cold start:** Agent instantiation time matters. Pre-warming or lightweight agent definitions may be needed.
- **Cost model:** Pay-per-invocation changes the economics of always-on workflows. Need cost tracking and budgeting.
- **Event-driven:** Natural fit for webhook-triggered workflows (CI/CD, support).
- **Execution limits:** Cloud function timeouts (typically 15 minutes) may be too short for complex agent tasks. May need task decomposition or continuation patterns.

[To be defined: specific serverless platform targets, state store options, cold start mitigation]

---

## Smaller-Model Optimization Roadmap

GearTrain should be able to get useful work from smaller models by shaping the work before the model sees it. The product should treat model quality as partly an architecture problem: narrow workflow nodes, explicit contracts, precise retrieval, smaller tool surfaces, and helper calls that keep the main transcript clean.

The first version can be simple. The architecture should still leave room for:
- Workflow decomposition into smaller model-sized steps
- Prompt and context budgets per agent, node, and model route
- Precise RAG with metadata filters, source references, top-k limits, and relevance thresholds
- Dynamic tool discovery and tool-schema injection
- Off-transcript planning, routing, critique, summarization, and repair calls
- Prompt compression and context distillation before long-running workflows exceed budget
- Evals that prove where smaller models are good enough and where stronger models are required

This should land as runtime policy, not agent-specific prompt folklore. Agents declare what kind of context and tools they need; the engine decides how to assemble the smallest useful call.

---

## Context Management: Off-Transcript LLM Calls

Two related techniques worth using in GearTrain's agent runtime. Both treat some model calls as **off-transcript** — their output feeds the next prompt, but their input/output pair is dropped from history. Saves tokens and keeps the main context focused on user-visible reasoning.

### Tool selection (tool RAG)

When an agent has many tools, full JSONSchema for every tool bloats the prompt. Instead:

1. First call sees only tool names, short descriptions, or category labels and picks what it needs.
2. Second call is constructed fresh with just the selected tools' full schemas. The selection step is rewritten out of history.

Variants:

- *Embedding-based retrieval* — skip the LLM for selection. Embed the user message, nearest-neighbor against tool description embeddings, inject top-k schemas. Cheaper, no rollback.
- *Lazy/deferred schemas* — tool names always visible, full schema fetched on demand. MCP supports this natively via dynamic tool discovery. Claude Code's `ToolSearch` works this way.
- *Hierarchical routing* — first pick a category, then pick a tool within it. Useful when tool count is in the hundreds.

In GearTrain, this maps to agent definitions that declare tool *categories* rather than enumerating every tool. The engine resolves categories to schemas at call time based on the task.

### Look-ahead with rollback

The general pattern: run an LLM call to get preliminary context (a route, a plan, a summary), then continue the conversation as if that call never happened — only its result enters the next prompt.

Names this goes by:

- *Sub-agent / orchestrator pattern* — spawn a child with its own context, return only a summary. Parent never sees the child's transcript. Claude Code's Task tool and Anthropic's research agent work this way.
- *Context distillation* — run a reasoning pass, then replace it in history with a condensed result.
- *Speculative / out-of-band calls* — probe the model for routing or planning, then rewrite history to hide the probe.
- *Reflexion / self-refine* — discard intermediate critiques after using them.

The unifying rule: an LLM call is off-transcript when its result is small and self-contained (a tool name, a category, a JSON object, a short summary). Don't use this pattern when the model needs to reference its own prior reasoning — that requires the work to stay in context.

### How this lands in GearTrain

The engine should treat LLM calls as a first-class primitive with two modes: *in-transcript* (default, full history retained) and *off-transcript* (result captured, call discarded). Agent definitions can declare pre-call hooks — tool selection, plan drafting, memory retrieval — that run off-transcript by default.

Memory retrieval is already off-transcript in spirit: the relevance query and ranking happen outside the main agent loop, only the retrieved memories enter the prompt. Generalize this into a named pattern the framework supports directly.

[To be defined: API shape for off-transcript calls, caching policy, cost accounting when one user turn fires multiple LLM calls]

---

## Pluggable Memory Composition

Today's memory model in [04-memory-system.md](04-memory-system.md) treats scopes (workspace, workflow, agent-instance, agent-type) as a fixed hierarchy. A more flexible framing: an agent has a **set of memory stores plugged in at config time**. The set always includes its own memory, and can include workspace, workflow, and arbitrary user-defined stores — including a store shared between two agents in a workflow as an explicit collaboration channel.

This makes cross-agent memory sharing first-class instead of a side effect of scope inclusion. Two coder agents in a multi-service workflow can be wired to a shared store named `shared:auth-redesign` without that store being visible to anything else in the workflow.

### Integration patterns

Two ways to expose a composed set of stores to the agent:

**Single memory manager (aggregator).** A facade aggregates all attached stores and presents one memory interface. The agent calls `read` / `write` and the manager decides which store to pull from and which to write to.

- Pros: simple from the agent side; scales to many stores; adding or removing a store doesn't change the agent definition.
- Cons: routing is the hard problem. Heuristics, metadata tags, or an LLM-based dispatch step are all options, and all have failure modes.

**Multi-memory in context.** Each store is listed explicitly in the agent's context with its purpose, scope, and read/write conventions. The agent picks the right store per operation.

- Pros: precise — the agent can reason about provenance and target the correct store.
- Cons: context bloat. Each store costs tokens and prompt complexity.

A hybrid is probably correct. The manager handles unambiguous routing (own vs workspace) automatically; explicit context is reserved for stores where the agent's judgment matters (shared, user-defined).

### Three-tier classification

Orthogonal to where stores live, every memory item fits one of three tiers with distinct lifecycles:

**Knowledge base.** External information — docs, references, ingested files. Largely read-only from the agent's perspective. Benefits from chunking and retrieval (RAG). Maps to the KB system already described in [04-memory-system.md](04-memory-system.md).

**Long-term memory.** Anything the agent must keep across runs. Benefits from time-aware structure, semantic search, periodic consolidation, and pruning of stale entries. This is where dreaming runs.

**Operational memory.** Simple structure, scoped to the current workflow or agent run. Wiped at run end, with an optional consolidation step that promotes important items into long-term before teardown.

Any pluggable store can carry one or more tiers — a workspace store typically holds KB plus long-term, a workflow store is purely operational, a shared store between two agents might mix operational with selective long-term promotion.

### Why this matters

Cross-agent collaboration needs explicit memory boundaries, not implicit scope inclusion. The aggregator vs explicit-context tradeoff also informs how much prompt budget memory should cost — pick per agent type rather than globally. And the operational tier matches how the workflow engine already thinks about run state, so the consolidation step becomes the natural bridge from run state into persistent memory.

[To be defined: store identity and naming, ACL between agents on a shared store, default tier assignment per store type, consolidation policy when a run ends]
