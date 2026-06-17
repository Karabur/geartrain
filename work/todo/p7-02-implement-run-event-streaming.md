---
id: GT-P7-02
phase: 7
status: todo
depends_on: 
  - GT-P7-01
---

# Implement Run Event Streaming

Stream run events for future UI and live CLI/API consumers.

## Scope

- Streaming endpoint emits run events, node events, checkpoint events, tool events, memory events, and error events as they are appended.
- Server-sent events are acceptable for the first version; WebSockets can replace them later.

## Requirements

- Updates fire on node transitions, attempt changes, checkpoint creation/resolution, tool calls, memory writes, and run completion/failure.

## Acceptance Criteria

- Tests assert a client receives ordered updates on seeded and live state changes.
