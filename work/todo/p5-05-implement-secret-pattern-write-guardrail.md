---
id: GT-P5-05
phase: 5
status: todo
depends_on: 
  - GT-P5-02
---

# Implement Secret-Pattern Write Guardrail

Reject memory writes that contain secrets or credentials.

## Scope

- Regex-based detection on write; reject and report on match.

## Requirements

- Guardrail runs before every memory write.

## Acceptance Criteria

- Tests: a write containing a token is rejected; a clean write succeeds.
