---
id: GT-P9-05
phase: 9
status: todo
depends_on:
  - GT-P9-02
  - GT-P9-04
---

# Build Tool Call and Memory Update Inspectors

Add detailed post-MVP inspectors for tool usage and memory changes.

## Scope

- Tool call inspector with input summary, output summary, duration, status, and error summary.
- Memory update inspector with source run, scope, review status, diff preview, and guardrail result.

## Requirements

- Inspectors must read event-backed API data, not parse raw files directly.

## Acceptance Criteria

- A developer can trace a tool failure or memory write back to the source run and node.
