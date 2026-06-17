---
id: GT-P3-02
phase: 3
status: todo
depends_on: 
  - GT-P1-03
  - GT-P2-01
---

# Implement Workflow Factory

Build a LangGraph graph from a `WorkflowDefinition` instead of hardcoding the flow.

## Scope

- Implement `WorkflowFactory` that compiles nodes and transitions into a runnable graph.
- Resolve variables across workflow context (`${nodes.<id>.output}`, `${trigger.task}`).

## Requirements

- Workflow routing is data-driven from YAML; agents perform work inside nodes.
- Detect orphan and unreachable nodes during build.

## Acceptance Criteria

- Tests build and run a small graph with mock nodes.
- Variable references resolve to upstream node output.
