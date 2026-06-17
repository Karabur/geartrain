---
id: GT-P7-04
phase: 7
status: todo
depends_on:
  - GT-P5-03
  - GT-P7-02
---

# Record Memory Update Events

Emit structured events when agents read, write, or are blocked from writing memory.

## Scope

- Record memory read, memory write, and memory write rejected events.
- Include scope, entry path, source run, source node, source agent, review status, and guardrail result.
- Link memory updates back to the run that produced them.

## Requirements

- Event payloads must not duplicate full memory content when a path and summary are enough.
- Rejected writes must include a safe reason.

## Acceptance Criteria

- Tests assert memory reads, writes, and rejected writes append events with source metadata.
