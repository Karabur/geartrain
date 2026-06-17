---
id: GT-P8-05
phase: 8
status: todo
depends_on: 
  - GT-P8-04
  - GT-P7-06
---

# Add Critical-Path Integration Tests

Cover the dogfooding path end to end.

## Scope

- Integration tests for intake -> PR with mocked human input and GitHub.
- Assertions for run state, event logs, checkpoint records, tool call events, memory update events, and failure summaries.

## Requirements

- Deterministic and offline.

## Acceptance Criteria

- The critical path is covered and green.
