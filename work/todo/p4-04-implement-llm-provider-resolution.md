---
id: GT-P4-04
phase: 4
status: todo
depends_on: 
  - GT-P4-01
---

# Implement LLM Provider Resolution

Resolve provider/model from workspace defaults, model hints, and engine credentials.

## Scope

- Map `llm.model_hint` to a concrete model via workspace `model_hints`.
- Load per-user provider credentials from engine config env vars.

## Requirements

- Credentials come from engine config, never agent definitions.
- Unknown hints or missing credentials produce clear errors.

## Acceptance Criteria

- Tests resolve a model from a hint and surface a clear error for a missing credential.
