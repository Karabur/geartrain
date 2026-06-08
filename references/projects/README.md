# Reference Projects

Analyses of products, frameworks, libraries, and open-source projects related to agent orchestration and workflow systems. Each entry is a self-contained reference doc that covers what the project does, how it works, its tech stack, and what's relevant to GearTrain.

## Structure

One markdown file per project, named `{project-name}.md`. Each doc follows a consistent format:

- What problem it solves
- How it solves it (approach and architecture)
- Tech stack
- Comparison with GearTrain (overlaps, differences, takeaways)

## Index

| Project | Type | Key Relevance |
|---------|------|---------------|
| [npcpy](npcpy.md) | Open-source Python toolkit | File-defined agents/teams/workflows, Jinx templates, memory review, knowledge graphs, local serving |
| [OpenHuman](openhuman.md) | Open-source desktop assistant | Local memory tree, token compression, model routing, integrations, channels, trigger triage, native voice |
| [Parker](parker.md) | Commercial product | Agent orchestration for marketing, Mastra SDK, Temporal, Langfuse |
| [Temporal](temporal.md) | Open-source platform | Durable execution, event sourcing, crash-proof workflows, retry policies, saga pattern |
| [Villani Code](villani-code.md) | Open-source Python coding-agent runtime | Small-model task contracts, scope enforcement, evidence-based completion, validation and bounded repair |
