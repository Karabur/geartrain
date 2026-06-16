---
id: GT-P6-04
phase: 6
status: todo
depends_on: 
  - GT-P6-03
---

# Add GitHub Integration Tests

Cover the integration path without hitting GitHub.

## Scope

- Mocked end-to-end: a workflow node opens a PR and updates an issue.

## Requirements

- No live GitHub calls.

## Acceptance Criteria

- Tests pass offline and cover error handling.
