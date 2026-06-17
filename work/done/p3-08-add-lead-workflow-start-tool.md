---
id: GT-P3-08
phase: 3
status: todo
depends_on: 
  - GT-P2-04
  - GT-P3-07
---

# Add Lead Workflow-Start Tool

Expose one engine-side tool to the lead agent: `workflow start`.

## Scope

- Add tool instructions to the lead prompt.
- Detect the exact tool request in lead output and invoke the workflow start path.
- Return the tool result with the lead response.

## Requirements

- Only one tool call is required; the protocol can be simple and text-based.
- No general tool framework in this phase.

## Acceptance Criteria

- Lead can request `workflow start`.
- If already running, the tool returns status.
- Unknown tool requests are reported clearly.
