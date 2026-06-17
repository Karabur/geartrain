---
id: GT-P4-05
phase: 4
status: todo
depends_on: 
  - GT-P2-02
  - GT-P4-01
---

# Wire Context and Prompt Interpolation for LangChain

Use the shared context builder and resolve `${variable}` references for langchain agents.

## Scope

- Assemble in-context sections via the shared builder.
- Resolve workspace/engine/memory/workflow references in system prompts.

## Requirements

- Every static reference must resolve at load time.

## Acceptance Criteria

- Tests assert assembled context and resolved prompt variables.
