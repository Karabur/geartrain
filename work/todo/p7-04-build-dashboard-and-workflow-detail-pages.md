---
id: GT-P7-04
phase: 7
status: todo
depends_on: 
  - GT-P7-02
  - GT-P7-03
---

# Build Dashboard and Workflow Detail Pages

Show active workflows and a step-by-step run view.

## Scope

- Dashboard lists runs with status and current node.
- Detail shows agent outputs and transition history, updating over WebSocket.

## Requirements

- Reads from the API and live updates.

## Acceptance Criteria

- A developer can watch a run progress in the browser.
