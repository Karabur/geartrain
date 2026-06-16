---
id: GT-P2-05
phase: 2
status: todo
depends_on: 
  - GT-P2-03
  - GT-P2-04
---

# Add CLI Agent Tests

Cover the cli runner and direct-agent command end to end with a fake Codex.

## Scope

- Unit-test the runner and prompt assembly.
- Integration-test `geartrain agent` against the running engine.

## Requirements

- Tests must not call the real Codex CLI or the network.

## Acceptance Criteria

- Tests pass without Codex installed.
- Tests assert plain-text output and error handling.
