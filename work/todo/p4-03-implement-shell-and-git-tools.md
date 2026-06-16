---
id: GT-P4-03
phase: 4
status: todo
depends_on: 
  - GT-P4-02
---

# Implement Shell and Git Tools

Add `shell_exec` (via the sandbox) and git operation tools.

## Scope

- Implement `shell_exec` routed through the no-op sandbox.
- Implement git status/diff/commit/branch helpers.

## Requirements

- Shell and git run through the sandbox interface so a real sandbox can drop in later.

## Acceptance Criteria

- Tests: an agent runs a command and inspects git status against a temp repo.
