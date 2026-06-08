# Temporal (temporal.io)

**Type:** Open-source durable execution platform (also offered as managed cloud)
**Domain:** Reliable distributed application development — workflow orchestration with crash-proof guarantees
**License:** MIT (core server and SDKs)
**Maturity:** Production-proven at massive scale (Stripe, Coinbase, Netflix, Datadog, Airbnb, Box, Snap)
**SDKs:** Go, Java, Python, TypeScript, PHP, Ruby, .NET, Rust

**Source:** [Docs](https://docs.temporal.io/) | [GitHub](https://github.com/temporalio) | [Use cases](https://docs.temporal.io/evaluate/use-cases-design-patterns)

---

## Problem

Distributed applications fail. Servers crash, networks partition, services go down, deployments happen mid-execution. Traditional approaches force developers to write extensive error handling, recovery code, retry logic, state checkpointing, and dead-letter queue management — all of which is tedious, error-prone, and hard to test.

The core problem: **when a process crashes, the state of execution is lost.** The application has no memory of what happened before the failure. Restoring that state requires complex recovery code that's itself a source of bugs.

## Solution

Temporal provides **Durable Execution** — a guarantee that once a workflow starts, it runs to completion regardless of crashes, network failures, or infrastructure outages, whether that takes minutes, hours, days, or years. The platform shifts failure handling from the application to the infrastructure, so developers write business logic and Temporal handles the rest.

The key insight: Temporal doesn't snapshot state. It records an **Event History** of every decision and result, then **replays** the workflow code against that history to reconstruct state after a failure. The workflow code re-executes deterministically, but side effects (API calls, DB writes, etc.) are skipped during replay because their results are already in the history.

## Architecture

### Core Components

**Temporal Service** — the central orchestrator. Persists Event Histories to a database, schedules tasks, manages timers, and coordinates workers. Doesn't execute user code — just tracks what needs to happen and what already happened. Can be self-hosted or used as Temporal Cloud (managed).

**Workers** — part of the user's application. Poll the Temporal Service for tasks, execute Workflow and Activity code, and report results back. Workers run in the user's infrastructure, meaning user data never leaves their environment. You can run hundreds or thousands of workers for horizontal scaling.

**Workflows** — the orchestration logic. Defined as code (not YAML, not drag-and-drop). A Workflow is a deterministic function that coordinates Activities, handles signals, manages timers, and makes decisions. Workflows can run for years.

**Activities** — the units of work that interact with the outside world (API calls, DB queries, LLM invocations, file I/O). Activities are non-deterministic and failure-prone by design. When an Activity fails, Temporal retries it automatically. Activity results are recorded in the Event History so they're never re-executed during replay.

### Data Flow

1. Client starts a Workflow Execution with input parameters
2. Temporal Service creates the execution and schedules a Workflow Task
3. A Worker picks up the task, runs the Workflow code
4. Workflow code issues Commands (schedule Activity, start Timer, etc.)
5. Worker sends Commands to Temporal Service
6. Temporal Service maps Commands to Events, persists them
7. When an Activity is scheduled, it goes into a Task Queue
8. An Activity Worker picks it up, executes it, returns the result
9. Result is persisted as an Event in the history
10. Workflow Task is scheduled again, Worker replays history + continues from where it left off

---

## Deep Dive: Crash-Proof Execution

This is the core of what makes Temporal interesting for GearTrain. Here's exactly how they guarantee execution survives every category of failure.

### The Event Sourcing Model

Temporal's durability model is **event sourcing applied to workflow execution.** Every meaningful thing that happens in a workflow's lifetime is recorded as an Event in an append-only, ordered log (the Event History). This history is the single source of truth.

Events include things like:
- WorkflowExecutionStarted
- ActivityTaskScheduled
- ActivityTaskCompleted (with result payload)
- TimerStarted / TimerFired
- SignalReceived
- ChildWorkflowExecutionStarted

The Event History is durably persisted to a database before the Temporal Service acknowledges any state transition. This means even if the Temporal Service itself crashes, the history is safe.

### Deterministic Replay

When a workflow needs to resume (after crash, after waiting for a timer, after an activity completes), the Worker doesn't restore from a memory snapshot. It **re-executes the Workflow code from the beginning**, feeding it the Event History. The code runs the same way it did before because:

- Activity calls don't re-execute — their recorded results are returned from history
- Timers don't wait again — recorded timer-fired events are replayed instantly
- Time is read from the Workflow context (recorded value), not `Date.now()`
- Random values are captured once and replayed
- Signals and queries are replayed in recorded order

This is why **Workflow code must be deterministic.** Given the same Event History, it must make the same decisions. Non-deterministic operations (network calls, file I/O, random numbers, clock reads) must happen inside Activities, not directly in Workflow code.

**Deterministic constraint in practice:** You can't call external APIs from Workflow code. You can't use wall-clock time. You can't generate random numbers with `Math.random()`. Temporal provides replay-safe alternatives for all of these. Activities handle everything that touches the outside world.

### Failure Scenarios and How Temporal Handles Each

#### Worker crashes mid-Activity

The Activity was executing on a Worker process that died (OOM, hardware failure, deployment). Temporal detects this through timeouts:

- **Start-To-Close Timeout** — maximum time for a single Activity Task Execution. If the worker dies and can't report back, this timeout fires and the Activity is retried on another worker.
- **Heartbeat Timeout** — for long-running activities. The worker periodically sends heartbeats to prove it's alive. If heartbeats stop, Temporal knows the worker is dead within the heartbeat interval (could be seconds) rather than waiting for the full Start-To-Close Timeout.

When a retry happens, the new Activity Task is placed back in the Task Queue. Any available Worker picks it up. If the Activity was using **Heartbeat progress** (saving intermediate state in heartbeat payloads), the retried Activity receives that progress and can continue from where it left off instead of starting over.

#### Worker crashes mid-Workflow

The Workflow Task was being processed when the Worker died. The Temporal Service notices the Workflow Task wasn't completed within its timeout and reschedules it. A new Worker picks it up, replays the Event History, reconstructs the Workflow's state, and continues.

No work is lost because all completed Activity results are in the Event History. The Workflow code replays deterministically to the exact state before the crash, then continues executing the next step.

#### Temporal Service crashes

The Event History is persisted to a durable database (Cassandra, MySQL, or PostgreSQL). Even if the entire Temporal Service goes down, the state is safe. When the service recovers, it reads the persisted state and resumes scheduling. In Temporal Cloud and recommended self-hosted setups, the service runs as a multi-node cluster with leader election, so individual node failures don't cause downtime.

#### Network partition between Worker and Service

The Worker can't communicate with the Temporal Service. From Temporal's perspective, this looks like the Worker crashed — activity timeouts fire and the work is retried. From the Worker's perspective, it might complete the Activity but fail to report the result. This is why **Activities should be idempotent** — they might execute more than once (at-least-once delivery).

#### Database failure

If the persistence layer goes down, the Temporal Service can't accept new events. Workflows pause. When the database recovers, everything resumes. No data loss because the Event History is the source of truth and it's already persisted.

#### Deployment during execution

A new version of the Worker code is deployed while workflows are running. Temporal handles this through **Worker Versioning** and **Patching**. Running workflows continue on their original code path, while new workflows use the new code. The Event History's deterministic replay ensures old workflows don't break when replayed on new code (as long as the developer handles versioning correctly).

### Timeout Hierarchy

Temporal uses a layered timeout system — this is a key design pattern:

| Timeout | Scope | Default | Purpose |
|---------|-------|---------|---------|
| Workflow Execution Timeout | Entire workflow lifecycle | Unlimited | Absolute deadline for the whole workflow |
| Workflow Run Timeout | Single workflow run | Same as Execution Timeout | Limits a single run (before continue-as-new) |
| Schedule-To-Close Timeout | Activity Execution (all retries) | Unlimited | Total time budget for an activity including retries |
| Start-To-Close Timeout | Single Activity Task | Same as Schedule-To-Close | Detect individual worker crashes |
| Schedule-To-Start Timeout | Queue wait time | Unlimited | Detect task queue starvation |
| Heartbeat Timeout | Between heartbeats | None | Fast detection of long-running activity failure |

The key insight: **Start-To-Close Timeout is the primary mechanism for detecting Worker crashes.** The Temporal Service can't detect a crashed Worker directly — it relies on the timeout firing. Heartbeat Timeout provides faster detection for long-running activities.

### Retry Policies

Retry configuration is declarative — you specify the behavior, Temporal implements it:

- **Initial Interval:** time before first retry (default: 1 second)
- **Backoff Coefficient:** multiplier for each subsequent retry (default: 2.0)
- **Maximum Interval:** cap on retry interval (default: 100x Initial Interval)
- **Maximum Attempts:** total retry limit (default: unlimited)
- **Non-Retryable Errors:** error types that should fail immediately, not retry

Activities retry by default with exponential backoff. Workflows don't retry by default — the philosophy is that workflow failures indicate design problems, while activity failures indicate transient infrastructure problems.

**Per-error retry delays:** Activities can throw errors with a custom next-retry delay, overriding the Retry Policy for that specific failure. Useful when an API returns a Retry-After header.

### Activity Heartbeats and Progress

For long-running Activities (ML training, large file processing, data migration), heartbeats serve two purposes:

1. **Liveness detection** — proves the Worker is still alive
2. **Progress checkpointing** — heartbeat payload carries progress data

If the Worker dies mid-Activity, the retried Activity receives the last heartbeat payload. This lets it resume from the last checkpoint rather than starting over. For an LLM agent context: if an agent is processing a multi-step research task and crashes after step 3 of 5, the heartbeat can carry enough state to resume from step 3.

Heartbeats are throttled by the SDK to avoid overwhelming the Temporal Service — the Worker batches them and sends at most one per throttle interval (typically 80% of the Heartbeat Timeout).

### Saga Pattern for Compensations

When a multi-step workflow partially fails and needs to undo completed steps, Temporal supports the **Saga pattern.** Each step registers a compensation function. If a later step fails, the compensations run in reverse order. This is built on top of the workflow primitives — not a separate feature — but it's a first-class design pattern in the Temporal ecosystem.

Relevant to GearTrain: if an agent workflow makes changes across multiple systems and a later step fails, the saga pattern provides a clean way to roll back.

### Signals and Queries

**Signals** — async messages sent to a running Workflow from the outside. The Workflow can react to signals at any point. Useful for human-in-the-loop, external events, cancellation requests.

**Queries** — synchronous read-only requests to inspect Workflow state without affecting execution. Useful for status dashboards, progress monitoring.

**Updates** — newer mechanism combining signal + query: send data to a Workflow and get a response back.

These message passing primitives are event-sourced too — signals become Events in the history, so they survive crashes.

---

## API and Definition Style

Temporal's approach is **"Workflows as Code"** — not YAML, not visual builders, not config files. You define workflows and activities as regular functions/methods in your programming language.

Key design choices:

- **Workflow = function.** A workflow is a regular function with a specific decorator/annotation. No DSL, no special syntax.
- **Activities = functions.** Each activity is a function that does one thing. Non-deterministic by nature.
- **Configuration is declarative.** Retry policies, timeouts, and task queues are set when calling activities or starting workflows — not embedded in the workflow logic.
- **Polyglot.** Workflows in one language can call activities or child workflows in another language via Task Queues.
- **Child Workflows** — workflows can spawn sub-workflows for composability and isolation.
- **Continue-As-New** — long-running workflows can periodically reset their Event History to avoid unbounded growth, carrying forward only the current state.
- **Schedules and Cron** — built-in support for recurring workflows.

---

## Comparison with GearTrain

### What's similar

**Workflow orchestration as the core problem.** Both Temporal and GearTrain orchestrate multi-step processes. Temporal does it for general distributed applications; GearTrain does it for AI agent workflows. The fundamental challenge — coordinating steps, handling failures, persisting state — is identical.

**Workflows-as-code philosophy.** Temporal rejected visual/no-code workflow builders in favor of real code. GearTrain targets no-code YAML configuration but with LangGraph (code) underneath. There's a tension here worth understanding: Temporal argues that code gives full control and visual tools hit limitations.

**State persistence and recovery.** Both need workflows to survive crashes. Temporal uses event sourcing + deterministic replay. LangGraph uses checkpointing. Different mechanisms, same goal.

**Activity/task separation.** Temporal separates orchestration logic (Workflows) from side-effecting work (Activities). LangGraph separates graph structure (nodes and edges) from the functions nodes execute. Same architectural boundary.

### What's different

| Dimension | Temporal | GearTrain |
|-----------|----------|-----------|
| Primary use case | General distributed systems | AI agent orchestration |
| Definition style | Code (functions + decorators) | YAML config + LangGraph |
| Durability model | Event sourcing + deterministic replay | LangGraph checkpointing |
| Determinism requirement | Strict — workflow code must be deterministic | Not enforced — LLM calls are inherently non-deterministic |
| Retry scope | Activities retry; workflows don't by default | TBD |
| Heartbeats | Built-in progress checkpointing for long activities | Not built-in |
| Saga pattern | First-class design pattern | Not addressed yet |
| Multi-language | 8 SDKs, polyglot workflows | Python-first |
| Scale | Millions of concurrent workflows | Early stage |
| Managed service | Temporal Cloud | Self-hosted only |

**The determinism constraint is the biggest philosophical difference.** Temporal demands workflow code be deterministic so replay works. LLM-based agent workflows are fundamentally non-deterministic — the same prompt can produce different outputs. GearTrain can't adopt Temporal's replay model directly for the agent decision layer. But it could use it for the orchestration layer around agent decisions.

### Takeaways for GearTrain

**Event sourcing for the orchestration layer.** GearTrain doesn't need to make LLM calls deterministic. But the *orchestration* around those calls (which agent runs next, what results were returned, what state transitions happened) can be event-sourced. Record every agent invocation and its result. On crash, replay the history to reconstruct which step the workflow was on, and re-execute from that point. The LLM calls don't replay — their recorded results are used.

This is exactly Temporal's Workflow/Activity split applied to agents: the Workflow (orchestration) is deterministic; the Activities (LLM calls, tool use) are not and their results are recorded.

**Timeout hierarchy for agent workflows.** Temporal's layered timeout model (execution timeout > schedule-to-close > start-to-close > heartbeat) is directly applicable:
- Workflow-level timeout: how long can the entire agent pipeline run?
- Step-level timeout: how long can a single agent step take?
- Heartbeat for long agent tasks: is the agent still making progress or stuck in a loop?

**Heartbeats for LLM progress.** Long-running agent tasks (multi-step research, code generation with iteration) should send heartbeats with progress data. If the process crashes, the retried task can resume from the last checkpoint rather than starting over. Think: an agent that's 80% through a complex research task crashes — with heartbeat progress, it picks up from step 8/10 instead of step 1.

**Retry policies as configuration, not code.** Temporal's declarative retry policies (initial interval, backoff coefficient, max attempts, non-retryable errors) are a clean API pattern. GearTrain should let users configure retry behavior per-step in YAML without writing retry logic.

**Saga pattern for agent rollback.** When an agent workflow partially completes and fails, what happens to the side effects? If the agent created files, sent messages, or modified data in early steps, a saga-style compensation mechanism lets later steps undo those changes. GearTrain should consider this for workflows with real-world side effects.

**Signals for human-in-the-loop.** Temporal's Signal mechanism (send async messages to a running workflow) maps directly to human-in-the-loop agent workflows. An agent can pause, wait for human approval via a Signal, then continue. The signal is event-sourced so it survives crashes.

**Continue-As-New for long agent sessions.** Agent workflows that run indefinitely (monitoring, continuous improvement loops) accumulate state. Temporal's Continue-As-New pattern — periodically resetting history while carrying forward current state — prevents unbounded memory/storage growth. GearTrain should design for this from the start.

**The "no-code" tension.** Temporal explicitly chose code over visual tools, arguing that no-code hits limits. GearTrain targets no-code YAML config. The resolution: YAML config for the 80% case (declaring agent steps, retry policies, routing), with code escape hatches for the 20% that needs full control. Temporal's experience validates that the escape hatch matters.

**Consider Temporal as an optional backend.** Rather than reimplementing durable execution, GearTrain could optionally run on Temporal. Agent workflows defined in YAML would compile to Temporal Workflows. Activities would wrap agent/LLM calls. This gives GearTrain Temporal's battle-tested durability for free, while keeping the no-code configuration layer as GearTrain's value-add. LangGraph checkpointing for the simple case, Temporal for production-grade durability.
