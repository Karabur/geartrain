---
id: GT-P8-01
phase: 8
status: todo
depends_on: 
  - GT-P4-06
  - GT-P5-06
---

# Define Dogfooding Agents

Define the agent set tuned for the GearTrain codebase.

## Scope

- Define `team-lead`, `coder`, `qa`, and `reviewer` agents (cli or langchain per role).

## Requirements

- Agents follow the contracts and reference workspace memory/docs.

## Acceptance Criteria

- All four agents validate and load.
