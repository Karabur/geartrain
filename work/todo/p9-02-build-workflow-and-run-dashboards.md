---
id: GT-P9-02
phase: 9
status: todo
depends_on: 
  - GT-P9-01
---

# Build Workflow and Run Dashboards

Show workflow definitions, active runs, recent runs, failures, timings, and event-backed run details.

## Scope

- Runs dashboard lists status, workflow, task, current node, duration, tool calls, memory writes, and error summary.
- Run Detail shows trace, nodes, attempts, checkpoints, outputs, events, errors, and timings.
- Workflow Detail shows definition metadata, node graph, active run, and recent runs.

## Requirements

- Reads from the run APIs and event stream.

## Acceptance Criteria

- A developer can inspect a run without opening state files manually.
