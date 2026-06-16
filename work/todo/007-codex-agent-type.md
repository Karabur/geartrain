---
id: GT-M1-007
status: todo
depends_on:
  - GT-M1-004
---

# Implement CLI Agent Type

Implement the `cli` agent runner using headless CLI non-interactive execution. Codex (`codex exec`) is the default command.

## Scope

- Add the `cli` agent runner behind the shared `run(task, context) -> str` interface.
- Build final prompt from agent config, workspace paths, work folder path, and user/workflow input.
- Execute the configured command (default `codex exec`).
- Capture stdout/stderr and exit code.
- Return plain text output to the engine.

## Requirements

- Type is `cli`; default command is `codex exec`.
- Command should be configurable per agent or engine.
- Agent output is plain text.
- No chat mode.
- No `langchain` runtime in this slice (next slice; same interface).

## Acceptance Criteria

- Unit tests can run the agent runner with a fake Codex command.
- Prompt includes project root and work folder.
- Prompt uses the workflow work folder when one is provided.
- Non-zero Codex exit returns a clear engine error.
- Successful run returns plain text output.
