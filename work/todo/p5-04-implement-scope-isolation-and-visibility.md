---
id: GT-P5-04
phase: 5
status: todo
depends_on: 
  - GT-P5-02
---

# Implement Scope Isolation and Visibility

Separate scope directories and enforce read/write visibility.

## Scope

- Store workspace, workflow, and agent-type memory in separate directories.
- An agent reads instance + workflow + workspace + agent-level; writes only allowed scopes.

## Requirements

- Agent-type memories are isolated by agent type.

## Acceptance Criteria

- Tests assert visibility rules and agent-type isolation.
