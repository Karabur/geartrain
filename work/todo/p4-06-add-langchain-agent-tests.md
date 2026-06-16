---
id: GT-P4-06
phase: 4
status: todo
depends_on: 
  - GT-P4-02
  - GT-P4-03
  - GT-P4-04
  - GT-P4-05
---

# Add LangChain Agent Tests

Cover a langchain coder end to end with a stub LLM.

## Scope

- A langchain coder reads a file, makes a change, and runs tests.
- The same workflow runs a coder under either `type` with no change.

## Requirements

- No real LLM calls; use a stub or recorded responses.

## Acceptance Criteria

- Tests pass offline and prove type-swappability.
