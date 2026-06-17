---
id: GT-P2-03
phase: 2
status: done
depends_on: 
  - GT-P2-02
---

# Implement CLI Agent Runner

Implement the `cli` runner using headless non-interactive execution; `codex exec` is the default command.

## Scope

- Build the final prompt via the context builder.
- Run the configured command (default `codex exec`) through the sandbox interface.
- Capture stdout/stderr and exit code; return plain text.

## Requirements

- Command is configurable per agent or engine.
- Output is plain text; no chat mode.
- No `langchain` runtime in this phase.

## Acceptance Criteria

- Tests run the runner with a fake `codex` command.
- Non-zero exit returns a clear engine error.
- Prompt uses the workflow work folder when provided.
