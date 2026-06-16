---
id: GT-P1-08
phase: 1
status: todo
depends_on: 
  - GT-P1-06
---

# Add No-op Sandbox and Memory Managers

Add architecture seams for sandboxing and memory so later phases plug in without refactoring.

## Scope

- Add a `Sandbox` interface and a `NoopSandbox` that runs commands/file ops without restriction.
- Add a `MemoryManager` interface and a `NoopMemoryManager`.
- Engine creates both on startup.

## Requirements

- Sandboxing is out of MVP scope; the no-op layer keeps the boundary ready for a real sandbox later.
- No workflow path requires memory or sandbox behavior in this phase.

## Acceptance Criteria

- Engine startup creates both managers.
- Tests confirm they are present but inert.
- Agent/tool execution routes through the sandbox interface even though it is no-op.
