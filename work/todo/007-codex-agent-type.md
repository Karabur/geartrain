---
id: GT-M1-007
status: todo
depends_on:
  - GT-M1-004
---

# Implement Codex Agent Type

Implement the `codex` agent runner using Codex CLI non-interactive execution.

## Scope

- Add `codex` agent runner.
- Build final prompt from agent config, workspace paths, work folder path, and user/workflow input.
- Execute `codex exec`.
- Capture stdout/stderr and exit code.
- Return plain text output to the engine.

## Requirements

- Default command is `codex exec`.
- Command should be configurable.
- Agent output is plain text.
- No chat mode.
- No LangChain runtime.

## Acceptance Criteria

- Unit tests can run the agent runner with a fake Codex command.
- Prompt includes project root and work folder.
- Prompt uses the workflow work folder when one is provided.
- Non-zero Codex exit returns a clear engine error.
- Successful run returns plain text output.
