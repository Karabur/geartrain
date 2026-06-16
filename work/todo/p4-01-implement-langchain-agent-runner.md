---
id: GT-P4-01
phase: 4
status: todo
depends_on: 
  - GT-P2-01
---

# Implement LangChain Agent Runner

Add the `langchain` runner behind the shared interface and wire it into the factory.

## Scope

- Implement a `create_agent`-backed runnable.
- Extend `AgentFactory` to return it for `type: langchain`.

## Requirements

- Same `run(task, context) -> str` interface as `cli`; workflows don't change.
- A `langchain` agent declares `llm` and `tools`, not a `cli` block.

## Acceptance Criteria

- Tests run a langchain agent from YAML through the factory with a stub LLM.
