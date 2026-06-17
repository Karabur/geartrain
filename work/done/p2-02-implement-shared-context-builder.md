---
id: GT-P2-02
phase: 2
status: done
depends_on: 
  - GT-P2-01
---

# Implement Shared Context Builder

Build one context-assembly module shared by both agent runners.

## Scope

- Assemble explicit sections: task input, agent instructions, prior output, selected memory, selected docs, tool instructions.
- Front-load the assembled context into the `cli` prompt; expose the same builder for in-context use later.

## Requirements

- Prompts are not hardcoded in the runner; assembly lives in the builder.
- Builder leaves room for prompt budgeting and retrieval without interface changes.

## Acceptance Criteria

- Tests assert the assembled prompt contains project root, work folder, task content, and prior output.
- Builder is reused by the `cli` runner.
