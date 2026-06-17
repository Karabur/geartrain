---
id: GT-P3-10
phase: 3
status: todo
depends_on: 
  - GT-P3-09
---

# Write Runnable-Version Documentation

Document running the first runnable version locally.

## Scope

- Document setup, `engine start|status|stop`, `geartrain agent`, `geartrain workflow start`, and where state/logs live.
- Document how task files move between `work/` folders.

## Requirements

- Follows `WRITING_STYLE.md`.

## Acceptance Criteria

- A developer can follow it from a fresh checkout.
- It states that memory, web UI, GitHub, and LangChain arrive in later phases.
- It includes troubleshooting for missing Codex and invalid config.
