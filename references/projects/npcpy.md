# npcpy

**Type:** Open-source Python library and CLI toolkit
**Domain:** Multimodal LLM application primitives, local/cloud agents, team orchestration, workflows, memory, knowledge graphs
**License:** MIT
**Language:** Python
**Version inspected:** `1.4.26` package metadata, GitHub commit `4445221740b9ccfca18da28cdca8e3ad691b1aed`

**Source:** [GitHub](https://github.com/NPC-Worldwide/npcpy) | [Docs](https://npcpy.readthedocs.io/) | [Architecture](https://npcpy.readthedocs.io/en/latest/npc_data_layer/) | [Core concepts](https://npcpy.readthedocs.io/en/latest/concepts/)

---

## Problem

`npcpy` packages the building blocks needed to create local-first and cloud-backed AI applications: agent personas, tool calling, multi-agent teams, reusable prompt/code workflows, persistence, knowledge graphs, and serving endpoints.

Its central idea is the **NPC Context-Agent-Tool data layer**. An application defines agents as NPCs, groups them into teams, gives them tools and Jinx workflows, then persists conversations, tool calls, memories, and knowledge graph facts.

This is close to GearTrain's problem space, but at a lower product layer. `npcpy` is a Python toolkit for building agent systems. GearTrain is a repo-backed workflow product that should let a team define and run agent workflows without writing Python.

---

## Solution

`npcpy` provides these primitives:

| Primitive | What it does | GearTrain relevance |
|-----------|--------------|---------------------|
| `NPC` | Agent with a name, primary directive, model/provider, tools, jinxes, and shared context | Similar to GearTrain agent definitions |
| `Team` | Group of NPCs with a coordinator called `forenpc` | Similar to GearTrain team/workspace agent registry, but less workflow-explicit |
| `Jinx` | YAML workflow template with natural-language and Python steps | Similar to GearTrain YAML workflow nodes, but sequential and template-driven |
| `Skill` | Knowledge-content Jinx loaded from `SKILL.md` sections | Related to GearTrain memory/knowledge and agent operating instructions |
| `NPCArray` | Lazy, vectorized execution over many models or agents | Useful for evals, model routing experiments, and consensus patterns |
| `CommandHistory` | SQLAlchemy-backed persistence for conversations, tool calls, cost, and execution logs | Relevant to GearTrain's engine state, observability, and run history |
| Knowledge graph | LLM-extracted facts/concepts with keyword, embedding, graph, and hybrid search | Relevant to GearTrain's future AI-faced memory layer |
| Flask server | REST/SSE API exposing NPCs, teams, Jinx execution, models, and OpenAI-compatible chat | Relevant to GearTrain's local engine API and UI backend |

---

## Architecture

### NPC Data Layer

The docs describe four major data structures:

**NPC** is the agent unit. It can be initialized directly or from a `.npc` YAML file. It carries model/provider config, tools, Jinx workflows, a database connection, a team reference, and a Jinja templating environment. Each NPC also has a shared context dictionary that works as per-agent working memory during execution.

**Jinx** is the reusable workflow/tool unit. Jinxes are Jinja-templated execution templates. They can run `natural` steps through an LLM or `python` steps through code execution. This makes them usable even with models that don't support native tool calling.

**Team** groups NPCs and provides a shared context, a `forenpc` coordinator, team-wide Jinx availability, and loading from `team.ctx` files. The coordinator receives the request and routes work to other NPCs.

**Pipeline** represents a sequence of NPC interactions, Jinja references between steps, database access, batch vs. row-wise processing, and mixture/consensus processing.

### File-Based Team Structure

`npcpy` supports a team directory that looks like this:

```text
npc_team/
├── team.ctx
├── analyst.npc
├── writer.npc
├── jinxes/
│   ├── summarize.jinx
│   └── analyze.jinx
├── assembly_lines/
├── sql_models/
├── jobs/
└── triggers/
```

This strongly overlaps with GearTrain's repo-backed `.geartrain/` workspace idea:

```text
.geartrain/
├── workspace.yaml
├── agents/
├── workflows/
└── memory/
```

The useful pattern is not the exact folder names. The useful pattern is that the runtime can load a complete team from a project-local directory containing agent definitions, shared team context, workflows, data models, jobs, and triggers.

### `.npc` Agent Definitions

NPCs can be defined with YAML:

```yaml
name: data_analyst
primary_directive: >
  You are a meticulous data analyst who provides insights from structured
  and unstructured data.
model: llama3.2
provider: ollama
jinxes:
  - "*"
tools:
  - statistical_analysis
  - data_visualization
```

Fields relevant to GearTrain:

- `name`
- `primary_directive`
- `model`
- `provider`
- `jinxes`
- `tools`
- `api_url`
- `api_key`

GearTrain should avoid copying `api_key` into workspace-level agent files. GearTrain's current direction is better: workspace/team config can name providers and models, while provider connections and CLI agent credentials stay engine-scoped and per-user.

### `team.ctx`

Team configuration can set defaults and shared context:

```yaml
name: Data Science Team
context: >
  We are a data-driven team focused on extracting actionable insights.
model: llama3.2
provider: ollama
forenpc: data_analyst
databases:
  - customer_insights
preferences:
  - detail-oriented analysis
file_patterns:
  - pattern: "*.md"
    recursive: true
    base_path: "./docs"
mcp_servers:
  - name: sqlite
    command: python -m mcp.server.sqlite
    args: []
```

Reserved keys are handled specially. Other keys are merged into team `shared_context`.

GearTrain can use the same distinction:

- Reserved config keys define runtime behavior.
- Unreserved keys become workspace context available to agents and workflows.
- MCP server declarations belong in workspace or engine config depending on whether they are portable project tools or local user tools.

---

## Workflows

### Jinx

Jinx workflows are YAML files with named steps:

```yaml
jinx_name: "data_analyzer"
description: "Analyze CSV data and generate insights"
inputs:
  - "file_path"
  - "analysis_type"
steps:
  - name: "load_data"
    engine: "python"
    code: |
      df = pd.read_csv('{{ file_path }}')
      context['row_count'] = len(df)
      output = f"Loaded {len(df)} rows"

  - name: "generate_report"
    engine: "natural"
    code: |
      The dataset has {{ row_count }} rows.
      Generate a report.
```

Key details:

- Steps are ordered.
- Step outputs are stored under the step name.
- Later steps reference earlier outputs through Jinja variables.
- Python steps can write additional state into `context`.
- Natural steps use the NPC's LLM.
- The final result returns the full context, including step outputs.

### Comparison With GearTrain Workflows

Jinx is simpler than GearTrain's planned LangGraph workflows.

| Dimension | Jinx | GearTrain |
|-----------|------|-----------|
| Definition style | YAML template | YAML graph compiled to LangGraph |
| Control flow | Mostly sequential | Directed graph with decisions, HIL gates, sub-workflows |
| Execution engines | `natural`, `python`, `skill` | Agent, decision, integration, memory, human checkpoint |
| State | Shared context dict | File-backed workflow state plus engine-managed context |
| Durability | Basic persistence through DB/logs | MVP markdown state; stronger durable backends later |
| Human-in-loop | Not central | Core workflow node type |

The important idea for GearTrain is the **step-output namespace**. GearTrain workflow YAML should make outputs addressable by node name, with a clear interpolation model:

```yaml
inputs:
  plan: ${intake.output}
  test_report: ${test.output}
```

GearTrain should also keep Jinx's useful split between LLM steps and deterministic code/tool steps, but express it through explicit node types rather than a generic `python` engine in product-level workflow YAML.

---

## Multi-Agent Teams

`npcpy` teams use a coordinator called `forenpc`. The forenpc receives a request first and decides whether to answer directly, delegate to another NPC, or pass work between agents.

Delegation can happen when the coordinator mentions another NPC by name or uses an explicit `pass_to_npc` action. Team-level Jinxes are distributed to NPCs, so shared workflows and skills become available across the team.

This maps to two GearTrain design options:

1. **Coordinator-as-agent:** a workflow can have a lead agent that decides who handles a task.
2. **Workflow-as-coordinator:** the LangGraph workflow owns routing through explicit transitions.

GearTrain should prefer workflow-as-coordinator for MVP because it gives inspectable state, deterministic routing, and better human review. Coordinator agents can still be used inside specific nodes when flexible delegation is useful.

---

## Tools and Skills

NPC tools are Python callables. `npcpy` can generate tool schemas from function type hints and docstrings. Agents can also use default tools such as shell, Python, file editing, and web search.

Skills are knowledge-content Jinxes. A skill is a `SKILL.md` file with YAML frontmatter and markdown sections:

```text
npc_team/
└── jinxes/
    └── skills/
        └── code-review/
            ├── SKILL.md
            ├── scripts/
            └── references/
```

Each `##` section becomes requestable content. The agent can call a skill like a tool and ask for a specific section.

GearTrain relevance:

- Skills are a clean model for agent-specific operating knowledge.
- Scripts and references colocated with skill docs are useful.
- The "skill as callable knowledge" pattern could map to GearTrain memory/knowledge tools.
- GearTrain should still distinguish project memory from stable reusable skills. Skills are curated capability packages. Memory is accumulated operational context.

---

## Memory and Persistence

`npcpy` uses SQLAlchemy for persistence. SQLite is the default; PostgreSQL is supported through a SQLAlchemy engine.

The `conversation_history` table stores:

- message ID
- timestamp
- role and content
- conversation ID
- directory path
- model and provider
- NPC and team
- reasoning content
- tool calls and tool results
- parent message ID
- device metadata
- generation params
- input/output tokens
- cost

It also has execution tables for Jinx and NPC runs:

- `jinx_executions`
- `npc_executions`

These tables track execution input, output, status, error message, duration, NPC, team, and conversation.

GearTrain should treat this as a useful minimum for engine observability. The MVP should record workflow run ID, node ID, agent ID, model/provider, tool calls, retries, status, latency, token usage, and cost in a queryable SQLite schema.

### Human-In-The-Loop Memory Lifecycle

`npcpy` includes a memory review pipeline:

1. `pending_approval`
2. `human-approved`
3. `human-rejected`
4. `human-edited`

Memories are scoped by `(npc, team, directory_path)`. Approved memories can be injected into an NPC system message.

GearTrain's planned memory promotion model is broader and more explicit, but `npcpy` provides a concrete pattern worth copying: do not silently promote every generated memory. Put proposed memories through a review lifecycle with status, source message, final edited content, model/provider, and timestamps.

---

## Knowledge Graphs

`npcpy` can build and evolve a knowledge graph from text. The graph stores:

- facts
- concepts
- fact-to-concept links
- fact-to-fact links
- concept-to-concept links
- generation numbers
- origin labels such as `organic`, `dream`, `deepen`, and `manual_add`

The graph supports:

- initial fact/concept extraction from text
- incremental evolution from new content
- sleep process for pruning, deepening, and linking
- dream process for speculative connections
- keyword search
- embedding search
- graph traversal search
- hybrid search
- visualization

Stored KGs are scoped by:

- `team_name`
- `npc_name`
- `directory_path`

GearTrain relevance:

- The `generation` field is useful for tracking memory/knowledge evolution over time.
- `origin` is useful for separating human-authored, agent-inferred, and speculative content.
- Hybrid search is a strong candidate for GearTrain's AI-facing memory layer after MVP.
- The sleep/dream language is less useful for GearTrain docs. GearTrain should describe this as consolidation, pruning, inference, and hypothesis generation.

For MVP, GearTrain should not implement this whole KG system. Markdown plus keyword search is enough for dogfooding. But the metadata model is worth reserving for future AI-facing memory.

---

## NPCSQL

`npcpy` includes an AI-powered SQL layer. SQL model files can use Jinja functions and `nql.*` calls:

```sql
{{ config(materialized='table') }}

SELECT
    b.customer_id,
    nql.generate_text(b.customer_id, 'analyst') as customer_segment
FROM {{ ref('base_stats') }} b
```

The model compiler discovers models, parses dependencies, topologically sorts them, executes SQL, applies AI functions, and materializes results.

GearTrain relevance is limited but useful:

- The `ref()` DAG model is a good example of file-defined dependency graphs.
- AI calls embedded in SQL are interesting for data workflows, not core MVP.
- GearTrain should not add SQL-model functionality until the workflow engine is stable.

---

## Serving

`npcpy` ships a Flask server that can expose NPCs and teams over HTTP. It includes:

- streaming responses through `/api/stream`
- Jinx execution through `/api/jinx/execute`
- model listing
- global NPC and Jinx listing
- conversation APIs
- health check
- OpenAI-compatible `/v1/chat/completions`
- model management endpoints
- fine-tuning and ML endpoints

The server resolves NPCs in this order:

1. Registered team NPCs
2. Globally registered NPCs
3. Database/file fallback from global or project directories

GearTrain should use a similar priority rule for the local engine:

1. Loaded workspace definitions
2. Explicit runtime overrides
3. Engine/global defaults

For GearTrain, FastAPI still fits better than Flask because the current MVP plan needs async workflows, WebSockets, and OpenAPI generation.

---

## Provider Model

`npcpy` supports local and cloud providers through LiteLLM and direct integrations:

- Ollama
- OpenAI
- Anthropic
- Gemini
- DeepSeek
- AirLLM
- OpenAI-compatible endpoints
- local model tooling such as llama.cpp, LM Studio, and related backends

The package dependencies include `litellm`, `ollama`, `anthropic`, `openai`, Google GenAI packages, `chromadb`, `sentence_transformers`, Flask, Redis, SQLAlchemy, and MCP support.

GearTrain takeaway: LiteLLM is worth evaluating as a provider abstraction, but GearTrain should keep provider credentials engine-scoped and per-user. The workspace should name provider/model preferences, not hold shared API keys.

---

## Comparison With GearTrain

### What's Similar

**Repo-local definitions.** `npcpy` can load `.npc`, `.jinx`, `team.ctx`, skills, jobs, triggers, and SQL models from a directory. GearTrain's `.geartrain/` workspace is a stronger, product-specific version of the same idea.

**Agent/team/workflow primitives.** Both systems need agents, teams/workspaces, tools, workflows, memory, and persistent run history.

**YAML as the no-code boundary.** `npcpy` uses YAML for NPCs, team context, and Jinx workflows. GearTrain's MVP also uses YAML because developers can review it in git and edit it without a visual builder.

**Local-first runtime.** `npcpy` works well with local models and local files. GearTrain's MVP also starts as a local engine with git-backed project state.

**Memory as a first-class system.** `npcpy` already tracks conversations, tool calls, reviewed memories, and knowledge graphs. GearTrain has a clearer memory-vs-knowledge architecture, but `npcpy` gives concrete implementation details.

### What's Different

| Dimension | npcpy | GearTrain |
|-----------|-------|-----------|
| Product level | Python toolkit and CLI | Workflow product/platform |
| Primary user | Python developer building AI apps | Developer/team configuring agent workflows |
| Agent runtime | Custom NPC abstraction | LangChain/DeepAgents initially, LangGraph orchestration |
| Workflow runtime | Jinx templates and pipelines | LangGraph state graphs |
| Workflow shape | Sequential templates, team delegation | Explicit graph with decisions and HIL checkpoints |
| Workspace model | `npc_team/` and global/project directories | Repo-backed `.geartrain/` workspace |
| Memory storage | SQL DB plus KG/vector pieces | MVP markdown, future AI-facing store |
| Server | Flask | Planned FastAPI |
| Credential model | Agent/team configs can include provider fields and API fields | Provider connections and CLI credentials are engine-scoped and per-user |

---

## Takeaways for GearTrain

**Keep the repo-local workspace direction.** `npcpy` confirms that file-defined agents, team context, tools, skills, workflows, jobs, and triggers are practical. GearTrain should make `.geartrain/` the opinionated version with validation, clear schemas, and git review.

**Separate routing policy from agent discretion.** `npcpy` lets the coordinator agent route by mentioning teammates. GearTrain should use explicit LangGraph transitions for core workflow routing, then allow coordinator agents inside nodes where open-ended delegation is valuable.

**Use addressable node outputs.** Jinx step outputs become variables available to later steps. GearTrain workflow outputs should be equally easy to reference, while staying plain text for MVP.

**Adopt memory review states.** The pending/approved/rejected/edited lifecycle maps cleanly to GearTrain memory promotion. Agents can propose memory, but humans or policy gates should decide what becomes workspace or agent-level memory.

**Reserve metadata now.** Even if MVP memory is markdown-only, frontmatter should reserve fields like `origin`, `source`, `confidence`, `generation`, `scope`, `agent_type`, `workflow_id`, and `review_status`. This makes future vector/KG sync easier.

**Treat skills as curated knowledge packages.** `npcpy` skills are a useful pattern for reusable agent methodology. GearTrain can support a similar structure later, but should keep it separate from accumulated memory.

**Design observability tables early.** `npcpy` conversation and execution tables show the minimum useful log shape: message content, tool calls, tool results, model/provider, NPC/team, token usage, cost, status, error, and duration.

**Do not copy the full scope.** `npcpy` includes image/audio/video generation, fine-tuning, ML models, desktop automation, SQL AI functions, jobs, triggers, and model management. These are useful reference points, not MVP requirements for GearTrain.

**Evaluate LiteLLM, but don't bind the product to it yet.** LiteLLM may simplify provider support. GearTrain's durable abstraction should remain provider/model routing resolved by the engine, not direct provider config embedded in every workflow.

---

## What To Ignore For MVP

- Fine-tuning and genetic evolution
- Image/audio/video generation
- Desktop automation
- AI SQL model compiler
- Knowledge graph sleep/dream processes
- Full model management UI/API
- Global NPC directories outside the repo workspace
- Agent configs that store API keys directly

These are either product-scope distractions or better suited to future plugins/integrations.
