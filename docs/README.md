# GearTrain Documentation

## Documents

| # | Document | Description |
|---|----------|-------------|
| 01 | [Vision & Overview](01-vision.md) | What GearTrain is, why it exists, core principles, target users, success criteria |
| 02 | [Architecture](02-architecture.md) | Five-layer architecture: agents, workflows, teams, engine, channels. Foundation: memory & integrations |
| 03 | [Core Concepts](03-core-concepts.md) | Glossary of all key terms and their relationships. Configuration hierarchy |
| 04 | [Memory & Knowledge System](04-memory-system.md) | Memory vs knowledge base distinction, four memory scopes (agent-instance, workflow, workspace, agent-level), dual-format storage, guardrails, MVP vs future |
| 05 | [Example: Software Development](05-example-workflow-software-dev.md) | Full software development workflow with all sub-pipelines. Dogfooding plan |
| 06 | [MVP Scope & Plan](06-mvp-scope-and-plan.md) | What's in/out of MVP, key tradeoffs, tech stack, day-by-day 2-week plan, risk register, open questions |
| 07 | [Design Notes](07-design-notes.md) | Extended concepts: self-bootstrapping, agent as an abstraction (cli + langchain), user-controlled IDE/CLI agents, task assignment, PM agent, integration patterns, non-software workflows, memory future-proofing, dreaming, git strategy, serverless |
| 08 | [MVP Definition Contracts](08-definition-contracts.md) | Validation-ready contracts for workspace, engine, agent, workflow, memory, node types, and plain text outputs |

## Reading Order

For a new team member: 01 → 03 → 02 → 04 → 05 → 06 → 08 → 07

For a quick overview: 01 → 06 → 08

## Status

These documents represent the **research and ideation stage** output. They are intended to be reviewed, debated, and refined by the team before development begins. Key areas marked `[to be defined]` need team input.

## How to Contribute

Edit the markdown files directly. Keep the YAML examples consistent with the Pydantic model definitions once implementation begins. Add new documents with the next sequential number.
