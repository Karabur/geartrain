---
id: GT-P7-02
phase: 7
status: todo
depends_on: 
  - GT-P7-01
---

# Implement WebSocket State Updates

Push workflow state changes to the UI in real time.

## Scope

- WebSocket channel emits state transitions and checkpoint events.

## Requirements

- Updates fire on node transitions and checkpoint creation.

## Acceptance Criteria

- Tests assert a client receives an update on a state change.
