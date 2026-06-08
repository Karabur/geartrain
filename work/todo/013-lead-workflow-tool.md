---
id: GT-M1-013
status: todo
depends_on:
  - GT-M1-008
  - GT-M1-012
---

# Add Lead Workflow Start Tool

Expose one engine-side tool to the lead agent: `workflow start`.

## Scope

- Add tool instructions to the lead prompt.
- Detect a tool request in lead output.
- Support one exact tool call: `workflow start`.
- Invoke the same workflow start path used by `geartrain workflow start`.
- Return the tool result with the lead response.

## Requirements

- Only one tool call is required for the first milestone.
- Tool protocol can be simple and text-based.
- No general tool framework is required.

## Acceptance Criteria

- Lead can request `workflow start`.
- Engine starts workflow when lead requests the tool.
- If workflow is already running, tool returns current status.
- Unknown tool request is ignored or reported clearly.
