---
id: GT-P6-03
phase: 6
status: todo
depends_on: 
  - GT-P6-01
  - GT-P6-02
  - GT-P3-03
---

# Expose GitHub as Tools and Integration Node

Wrap GitHub as agent tools and back the `integration` node type.

## Scope

- Wrap client calls as LangChain tools.
- Implement the `integration` node (`service: github`).

## Requirements

- Integration node produces plain text output stored in run state.

## Acceptance Criteria

- Tests run an integration node that opens a PR via the mocked client.
