---
id: GT-P7-03
phase: 7
status: todo
depends_on:
  - GT-P4-03
  - GT-P7-02
---

# Record Tool Call Events

Emit structured events for tool usage across in-process agents and integration nodes.

## Scope

- Record tool started, completed, and failed events.
- Include tool name, category, node ID, attempt ID, duration, input summary, output summary, and error summary.
- Keep raw sensitive inputs out of event payloads.

## Requirements

- Events must be useful for debugging without leaking secrets.
- Tool events should work for shell, file/search, git, and integration tools.

## Acceptance Criteria

- Tests assert successful and failed tool calls append the expected events.
