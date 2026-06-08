---
id: GT-M1-014
status: todo
depends_on:
  - GT-M1-005
---

# Add Noop Memory Manager

Create the memory manager placeholder required by the engine without implementing memory behavior.

## Scope

- Add `NoopMemoryManager`.
- Engine creates it on startup.
- Agents do not depend on memory for first milestone.

## Requirements

- No memory read/write tools are required.
- No memory files are required for workflow execution.
- The placeholder keeps the engine boundary ready for later memory implementation.

## Acceptance Criteria

- Engine startup creates the memory manager.
- No workflow path requires memory to be present.
- Tests confirm the manager is available but inert.
