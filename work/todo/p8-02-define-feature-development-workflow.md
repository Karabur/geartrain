---
id: GT-P8-02
phase: 8
status: todo
depends_on: 
  - GT-P8-01
  - GT-P6-03
  - GT-P3-03
---

# Define feature-development Workflow

Build the real MVP workflow: plan, approve, implement, review, and prepare a PR.

## Scope

- Nodes: intake -> approve_plan (human) -> implement -> review -> PR integration -> end.
- Wire human checkpoints and the GitHub integration node.

## Requirements

- Routing is data-driven YAML on the generic engine.

## Acceptance Criteria

- Workflow validates and runs end to end with mocked human input and a mocked GitHub client.
