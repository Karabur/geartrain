# OpenHuman

**Type:** Open-source desktop personal AI assistant
**Domain:** Single-user AI agent, local memory, desktop automation, integrations, messaging channels, voice
**License:** GPL-3.0
**Language:** Rust core, React/Vite/Tauri desktop app, managed Node.js runtime for skills
**Version inspected:** `0.54.2` package metadata, GitHub commit `6a83409a4cc2f9382a56158943772346bb431fe0`

**Source:** [GitHub](https://github.com/tinyhumansai/openhuman) | [Docs](https://tinyhumans.gitbook.io/openhuman/) | [Architecture](https://tinyhumans.gitbook.io/openhuman/developing/architecture) | [Memory Tree](https://tinyhumans.gitbook.io/openhuman/features/obsidian-wiki/memory-tree) | [Token Compression](https://tinyhumans.gitbook.io/openhuman/features/token-compression) | [Model Routing](https://tinyhumans.gitbook.io/openhuman/features/model-routing)

---

## Problem

OpenHuman is a personal AI assistant that tries to avoid the usual cold-start problem. Instead of waiting for the user to manually paste context into each conversation, it continuously pulls from connected services, compresses the results, stores them locally, and routes tasks through a single agent surface with native tools, channels, and voice.

It is not a workflow platform like GearTrain. It is mostly a single-user, single-agent product with subagents and background loops. The useful ideas for GearTrain are in the supporting systems: local memory architecture, token compression, model routing, integration ingestion, messaging channels, trigger triage, and native voice.

---

## Solution

OpenHuman combines a desktop app with a local Rust core:

| Area | What OpenHuman does | GearTrain relevance |
|------|---------------------|---------------------|
| Memory Tree | Local SQLite store plus Markdown/Obsidian vault, built from integrations and activity | Strong reference for human-readable plus machine-indexed memory |
| TokenJuice | Compresses tool results before they enter LLM context | Strong reference for GearTrain tool output budgets |
| Model routing | Uses `hint:*` model strings and routing policy to choose local vs remote / fast vs reasoning | Strong reference for GearTrain model routing |
| Integrations | Uses Composio-backed OAuth connections as tools, memory sources, profile signals, and triggers | Reference for future integration layer, not MVP |
| Channels | Defines provider contracts for Telegram, Discord, Slack, web, email, etc. | Reference for GearTrain channels after local web UI |
| Trigger triage | Classifies external events into drop / acknowledge / react / escalate | Strong pattern for event-driven workflows |
| Native voice | STT, TTS, dictation, live Google Meet agent | Future channel/tool reference |
| Security | Local memory, backend-held OAuth tokens, keychain, scoped tools, prompt-injection guard | Useful boundary model |

---

## Architecture

OpenHuman is a monorepo with a Rust core and a React/Tauri desktop UI.

| Layer | Implementation | Notes |
|-------|----------------|-------|
| Desktop app | Tauri v2 + React 19 + Vite + Redux Toolkit | Ships Windows, macOS, Linux desktop builds |
| Core runtime | Rust `openhuman_core` and `openhuman-core` binary | Owns RPC, tools, channels, memory, routing, security |
| UI/core bridge | Tauri IPC and HTTP JSON-RPC | UI calls core business logic over RPC |
| Skills runtime | Managed Node.js runtime | Skills use metadata, instructions, and JS helpers |
| Storage | SQLite via `rusqlite`, Markdown vault | Local-first memory and app state |
| Networking | `reqwest`, Socket.IO/WebSocket, rustls | Backend broker for OAuth, LLMs, search, TTS |
| Observability | tracing, OpenTelemetry, Sentry, Prometheus dependencies | Also has E2E artifact capture docs |

OpenHuman's docs describe a dual-socket setup where the Rust core keeps persistent backend connectivity independent of the WebView. It also broadcasts a `tool:sync` event containing available tools and connection status so the backend AI system knows the current tool surface.

For GearTrain, the useful principle is: the engine should be the source of truth for runtime state and tool availability. The UI should observe and control it, not own it.

---

## Agent Harness

OpenHuman's public agent surface owns the LLM tool loop, subagent dispatch, transcripts, trigger triage, and bundled prompts. Provider HTTP transport, tool implementations, prompt assembly, and memory storage live in separate modules.

Its subagent definitions are data-driven TOML files. Built-ins live under `src/openhuman/agent/agents/<agent>/agent.toml` plus `prompt.md`. Users can add custom definitions under `$OPENHUMAN_WORKSPACE/agents/*.toml` or `~/.openhuman/agents/*.toml`.

An agent definition includes:

- identity: `id`, `display_name`, `when_to_use`
- prompt source and prompt-section omissions
- model selection strategy
- allowed tool scope, disallowed tools, skill filters, extra tools
- runtime limits: max iterations, output cap, timeout, sandbox mode
- subagents it may delegate to
- tier: `chat`, `reasoning`, or `worker`

OpenHuman enforces a spawn hierarchy:

```text
Chat
  -> Reasoning
    -> Worker
  -> Worker
```

`Chat` agents can't spawn other `Chat` agents. `Reasoning` agents can't spawn other `Reasoning` agents. `Worker` agents can't spawn anything. The harness also caps depth.

GearTrain relevance:

- This tiering maps well to GearTrain's planned workflow/agent split.
- GearTrain should keep primary workflow routing explicit in LangGraph, but subagent tier rules are useful inside agent steps.
- Tool scope, disallowed tools, timeouts, output caps, and sandbox mode belong in GearTrain agent definitions from the start.

---

## Memory Tree

OpenHuman's Memory Tree is its strongest reference point for GearTrain.

The pipeline:

```text
source adapters
  -> canonicalize to Markdown + provenance
  -> chunk into <=3k-token deterministic segments
  -> content store writes atomic Markdown files
  -> SQLite store tracks chunks, scores, summaries, jobs
  -> score with signals, embeddings, entity extraction
  -> source / topic / global summary trees
  -> retrieval: search, drill-down, topic, global, fetch
```

The design has two local storage surfaces:

| Path | Purpose |
|------|---------|
| `<workspace>/memory_tree/chunks.db` | Chunks, scores, summaries, entity index, jobs, hotness |
| `<workspace>/wiki/` | Markdown vault readable in Obsidian |

The Memory Tree builds three scopes:

- **Source trees**: per-source rolling buffers that seal into higher-level summaries.
- **Topic trees**: per-entity summaries built when an entity becomes hot enough.
- **Global tree**: daily global digest across all ingested sources.

Chunk lifecycle:

```text
pending_extraction -> admitted -> buffered -> sealed
        \
         -> dropped
```

The ingest hot path avoids LLM calls. It canonicalizes, chunks, fast-scores, persists, and enqueues follow-up work. Heavy work runs in background workers: embeddings, entity extraction, sealing summaries, daily digests, stale flushes.

GearTrain relevance:

- GearTrain's MVP markdown memory can stay simple, but this validates the dual-format direction: human-readable files plus machine-indexed local state.
- Deterministic chunk IDs and one-transaction ingest are good defaults.
- Memory entries should preserve provenance so agents can trace claims back to source files or workflow runs.
- Background summarization should not block the main workflow path.
- GearTrain should reserve frontmatter fields for lifecycle state, source, confidence/score, generation, scope, and provenance.

---

## Obsidian-Style Vault

OpenHuman writes agent memory into a user-owned Markdown vault:

```text
<workspace>/
└── wiki/
    ├── summaries/
    ├── notes/
    └── one folder per connected source
```

The user can open, edit, link, and export the vault. Manual notes under `wiki/notes/` are ingested like any other source.

This lines up with GearTrain's repo-backed `.geartrain/memory/` plan. GearTrain should keep the stronger repo/project framing:

- Memory files live with the code and are reviewed through git.
- The engine syncs markdown into the AI-facing index.
- Human edits win over generated memory.

OpenHuman's Obsidian compatibility is useful but personal-knowledge oriented. GearTrain's equivalent should optimize for project memory, workflow records, and team review.

---

## Auto-Fetch and Integration Ingest

OpenHuman runs a global sync tick every 20 minutes. On each tick it walks active connections and calls the matching native provider if that connection's interval has elapsed.

State is per `(toolkit, connection_id)`:

- last sync timestamp
- daily budget
- dedupe set
- cursor

Native providers fetch new items, canonicalize them, and feed the same Memory Tree ingest path. Webhook/event-driven sync shares the same state so periodic sync doesn't duplicate work.

GearTrain relevance:

- One global scheduler is simpler than one scheduler per connection.
- Integration sync state should be per connection, not global.
- Daily budgets and per-provider intervals are practical guardrails.
- Errors in background sync should be logged and isolated; the scheduler loop must keep running.

For MVP, GearTrain only needs GitHub integration. The architecture should still leave room for this pattern.

---

## Token Compression

OpenHuman's TokenJuice layer runs before tool results enter model context:

```text
tool call result
  -> TokenJuice classify / match rule / reduce
  -> LLM context
```

Rules are JSON and merge in three layers:

| Layer | Path | Purpose |
|-------|------|---------|
| Builtin | shipped with binary | Defaults for git, npm, cargo, docker, kubectl, ls |
| User | `~/.config/tokenjuice/rules/` | Personal overrides |
| Project | `.tokenjuice/rules/` | Repo-specific overrides checked into git |

Reduction strategies include truncation, line dedupe, whitespace folding, regex drops, and section summarization. OpenHuman also has a context pipeline that microcompacts older tool-result envelopes by replacing old payload bodies with a stable placeholder while preserving the tool-call/result pairing required by provider APIs.

GearTrain relevance:

- Add a tool-result budget before outputs enter agent history.
- Make compression rule-based first, with project overrides in the repo.
- Preserve provider invariants when compacting history. Don't delete tool-result envelopes if the API expects them.
- Keep recent tool results hot and compact older ones.
- Log bytes/tokens saved for observability.

For GearTrain, this belongs in the engine/tool runtime policy layer, not in agent prompts.

---

## Model Routing

OpenHuman uses `hint:*` model strings to route requests. A call can specify either a concrete model or a hint such as:

- `hint:reasoning`
- `hint:fast`
- `hint:vision`
- `hint:summarize`
- `hint:code`

The router resolves the hint to a provider/model pair. Its routing policy also classifies tasks:

| Category | Examples | Default routing |
|----------|----------|-----------------|
| Lightweight | `hint:reaction`, `hint:classify`, `hint:format`, `hint:sentiment` | Local-first when available |
| Medium | `hint:summarize`, `hint:medium`, `hint:tool_lite` | Local when latency/cost hints ask for it |
| Heavy | `hint:chat`, `hint:reasoning`, `hint:agentic`, `hint:coding`, exact model names | Remote by default |

Per-call hints include:

- `privacy_required`: local only, no fallback
- `latency_budget`: prefer low latency
- `cost_sensitivity`: prefer low cost

OpenHuman's docs emphasize one subscription where the backend brokers access to multiple model providers. That is a consumer-product choice, not a fit for GearTrain MVP.

GearTrain relevance:

- The `hint:*` abstraction is worth copying.
- Agent definitions should use task-level hints instead of hard-coding every model.
- The engine should resolve hints using local per-user provider connections.
- Routing should be observable: record hint, resolved provider/model, fallback, cost, latency, and quality signals.
- Privacy/local-only requirements should be explicit routing constraints, not best-effort preferences.

GearTrain should keep its current contract: workspace config names providers/models and hints, while actual provider connections remain engine-scoped and per-user.

---

## Local AI

OpenHuman's local AI is opt-in and feature-scoped. It uses Ollama or LM Studio for workloads where local execution matters most:

- memory embeddings
- summary-tree building
- heartbeat/background loops
- learning/reflection
- subconscious loop

Default chat, heavy reasoning, vision, STT, TTS, and web search stay cloud-backed. Lightweight chat hints can prefer local when local AI is enabled and healthy.

Important design details:

- `local_ai.runtime_enabled` is the master switch.
- `local_ai.opt_in_confirmed` prevents accidental enablement.
- Local usage flags are per subsystem.
- The local provider is health-gated and can fall back to remote unless privacy requires local-only.

GearTrain relevance:

- Local AI should be a per-workload choice, not an all-or-nothing mode.
- Health gates and graceful fallback matter.
- Memory embedding and summarization are the best first local workloads.
- Heavy workflow planning should stay on stronger configured models unless explicitly overridden.

---

## Third-Party Integrations

OpenHuman uses Composio for 118+ integrations. A connection appears in four places:

1. Agent tool
2. Memory source for auto-fetch
3. Profile/personalization signal
4. Trigger source

The catalog includes Gmail, Outlook, Google Calendar, Google Drive, Notion, Dropbox, GitHub, Linear, Jira, Figma, Slack, Discord, Teams, Telegram, WhatsApp, Salesforce, HubSpot, Stripe, Shopify, Asana, Trello, X, YouTube, and more.

The docs distinguish:

- **Native providers**: Rust modules that ingest data directly into Memory Tree.
- **Proxied tools**: agent-callable tools without automatic ingest.

GearTrain relevance:

- The same integration can have multiple roles: action, data source, trigger source, memory source.
- GearTrain's integration model should represent those capabilities separately.
- OAuth/token storage should not be exposed to agents. Agents see typed tool results, not credentials.
- GitHub is enough for MVP, but the data model should not assume every integration is only a tool.

---

## Trigger Triage

OpenHuman turns connected-service events into trigger envelopes. The pipeline:

```text
third-party API webhook
  -> OpenHuman backend verifies and normalizes
  -> Rust core receives authenticated socket event
  -> DomainEvent::ComposioTriggerReceived
  -> trigger_triage agent
  -> one of: drop / acknowledge / react / escalate
```

Triage choices:

| Action | Meaning |
|--------|---------|
| `drop` | Log and discard |
| `acknowledge` | Persist a short memory note, no agent run |
| `react` | Run a narrow trigger reactor with one or two tool calls |
| `escalate` | Hand off to the orchestrator for multi-step work |

GearTrain relevance:

- This is directly useful for future event-triggered workflows.
- Not every external event should start a full workflow.
- The cheap classifier/triage step saves cost and reduces noise.
- Every trigger and decision should be audit-logged.
- Event settings should be configurable per integration and event type.

For GearTrain, `escalate` should start a named workflow or open a human checkpoint, not hand off to a general personal assistant.

---

## Messaging Channels

OpenHuman has a `Channel` trait and provider implementations for many platforms:

- CLI
- Web
- Telegram
- Discord
- Slack
- WhatsApp
- Email
- iMessage
- IRC
- Matrix
- Signal
- Lark
- Mattermost
- DingTalk
- QQ
- Linq

The channel domain owns inbound/outbound messages, provider connectors, runtime supervision, proactive outbound delivery, status/test/connect/disconnect RPCs, and per-platform threads/reactions where supported.

GearTrain relevance:

- Channels should be bidirectional capabilities, not just notification sinks.
- Channel auth should be separate from channel runtime.
- Channel providers need status and doctor/test commands.
- Inbound channel messages should become workflow or agent inputs through a dispatcher.
- Outbound messages should carry run/thread context so human replies route back to the right workflow.

GearTrain MVP only needs web UI and CLI. This is a future reference for Slack/Telegram/email.

---

## Native Voice

OpenHuman treats voice as a native tool family:

- push-to-talk and toggle dictation
- cross-platform mic capture and VAD
- streaming transcription
- hallucination filtering for common silence artifacts
- dictation cleanup
- hosted TTS
- avatar lip-sync
- live Google Meet agent that joins a meeting, transcribes, writes notes to Memory Tree, and can speak back into the call

GearTrain relevance:

- Voice can be modeled as a channel plus tools: STT input, TTS output, meeting transcript ingest.
- Meeting transcripts are a useful future knowledge source.
- Low-latency voice turns need a fast model route separate from deep planning.

Voice is not relevant to GearTrain MVP unless the product direction shifts toward real-time collaboration.

---

## Security and Privacy Boundary

OpenHuman's user-facing privacy model:

- Memory Tree SQLite database and Markdown vault live locally.
- Audio buffers stay local and are discarded after STT.
- OAuth tokens are held by backend services, not plaintext on the laptop.
- Sensitive local credentials use OS keychain.
- Filesystem tools are workspace-scoped.
- Skills are sandboxed with resource limits.
- Prompt-injection guard can `allow`, `review`, or `block` before model/tool execution.

GearTrain relevance:

- GearTrain should make workspace scoping explicit for filesystem and shell tools.
- Secret detection and prompt-injection checks belong before tool execution, not only after memory writes.
- Credential storage must remain engine-scoped and local for MVP.
- Audit logs should record blocked/reviewed actions.

OpenHuman's backend-held OAuth model is a hosted product choice. GearTrain's MVP should use local developer credentials and GitHub access through the user's local engine.

---

## Comparison With GearTrain

### What's Similar

**Local-first memory.** Both products value human-readable local memory. OpenHuman uses `wiki/` plus SQLite. GearTrain plans `.geartrain/memory/` plus future AI-facing indexes.

**Agent runtime with tools.** Both need file, shell, git, search, memory, and integration tools with scoped permissions.

**Model routing.** OpenHuman's hint-based routing maps well to GearTrain's planned per-action model routing.

**Channels and triggers.** OpenHuman already models inbound/outbound channels and event triage. GearTrain will need the same patterns for workflow starts and HIL checkpoints.

**Token control.** OpenHuman treats tool output compression as infrastructure. GearTrain should do the same.

### What's Different

| Dimension | OpenHuman | GearTrain |
|-----------|-----------|-----------|
| Product type | Personal desktop assistant | Team/workflow orchestration platform |
| Primary unit | User-facing agent session | Workflow run |
| Memory target | Personal life/work context | Project/workspace/workflow memory |
| Workspace | `~/.openhuman` or user workspace | Repo-backed `.geartrain/` folder |
| Routing | One subscription plus local AI options | Engine-scoped per-user provider connections |
| Integrations | Broad OAuth catalog via backend | GitHub-first MVP, other integrations later |
| Channels | Many personal messaging channels | Web UI/CLI MVP, Slack/email later |
| Voice | Core product feature | Future optional channel |
| License | GPL-3.0 | License compatibility must be considered before copying code |

---

## Takeaways for GearTrain

**Add tool-result compression early.** GearTrain agents will run shell, tests, git, grep, and API calls. Tool output needs a budget and reduction rules before it reaches the LLM.

**Use model hints in YAML.** Agent/workflow definitions should say `reasoning`, `fast`, `summarize`, `code`, or `vision`, and the engine should resolve those hints per user.

**Keep memory local and inspectable.** OpenHuman validates the idea that users trust memory more when they can read and edit it as Markdown.

**Use a background memory pipeline later.** The MVP can use markdown plus keyword search. After that, GearTrain can add deterministic chunking, scoring, embedding, and summarization workers.

**Represent integrations by capability.** A service can be an action surface, data source, memory source, trigger source, and channel. Don't flatten integrations into only "tools."

**Put triage before workflows.** Event-driven GearTrain should classify external events before starting expensive workflows. Many events should only log memory or ask a human.

**Design channel replies around workflow runs.** Every outbound HIL prompt needs enough metadata for an inbound reply to resume the correct workflow.

**Make local AI per workload.** Local embeddings and summarization are good candidates. Heavy planning and code work should stay on configured strong models unless a workspace explicitly opts into local-only.

**Keep credential ownership aligned with GearTrain's model.** OpenHuman centralizes OAuth and model brokerage in its backend. GearTrain MVP should keep LLM provider connections, CLI agent credentials, and GitHub credentials engine-scoped and per-user.

---

## What To Ignore For MVP

- Broad Composio integration catalog
- Native voice and meeting agents
- Mascot/avatar UI
- Consumer subscription model
- Backend-brokered OAuth/model access
- Multi-channel messaging beyond web UI and CLI
- Full Memory Tree summary hierarchy
- Agent "subconscious" background loop
- Crypto/wallet-specific tooling
- GPL-licensed code reuse

These are useful references, but they would distract from GearTrain's dogfooding milestone.
