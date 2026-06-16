---
id: GT-P1-03
phase: 1
status: todo
depends_on: 
  - GT-P1-01
---

# Define Config Models and YAML Loading

Define Pydantic models for every MVP config type and load them from YAML.

## Scope

- Models: `WorkspaceConfig`, `EngineConfig`, `AgentDefinition` (cli + langchain), `WorkflowDefinition`, `MemoryEntry` frontmatter.
- Implement YAML parsing into validated models with clear field-level errors.

## Requirements

- Models follow the contracts in `docs/08-definition-contracts.md`.
- Loading is pure: no LLM or external service calls.

## Acceptance Criteria

- Tests cover loading each config type from the scaffold.
- Malformed YAML and wrong field types produce clear errors.
