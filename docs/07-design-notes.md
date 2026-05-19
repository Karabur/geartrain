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

**Phase 1 (MVP):** Git-backed markdown files with keyword search for persistent scopes (workspace, workflow, agent-type, KB); LangGraph state for active workflow run state and agent-instance memory. The `MemoryStore` Protocol defines the interface. Agents interact with memory/KB through `memory_read`, `memory_write`, `kb_read`, `kb_write` tools. Everything is synchronous and file-based for persistent scopes.

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

- **Stateless by definition:** Workflow state must be externalized (not in-memory). This is already the case with SQLite/LangGraph checkpointing, but serverless would need a networked state store.
- **Cold start:** Agent instantiation time matters. Pre-warming or lightweight agent definitions may be needed.
- **Cost model:** Pay-per-invocation changes the economics of always-on workflows. Need cost tracking and budgeting.
- **Event-driven:** Natural fit for webhook-triggered workflows (CI/CD, support).
- **Execution limits:** Cloud function timeouts (typically 15 minutes) may be too short for complex agent tasks. May need task decomposition or continuation patterns.

[To be defined: specific serverless platform targets, state store options, cold start mitigation]
