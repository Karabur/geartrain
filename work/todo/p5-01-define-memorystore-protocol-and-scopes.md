---
id: GT-P5-01
phase: 5
status: todo
depends_on: 
  - GT-P1-08
---

# Define MemoryStore Protocol and Scopes

Define the memory interface and scopes that replace the no-op manager.

## Scope

- Define `MemoryStore` with `scope` and `system` parameters.
- Scopes: workspace, workflow, agent_level (agent_instance lives in run state).

## Requirements

- Interface is backend-agnostic so the markdown store can be swapped later.

## Acceptance Criteria

- Tests assert the protocol surface and scope enum.
