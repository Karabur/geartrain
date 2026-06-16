---
id: GT-P4-02
phase: 4
status: todo
depends_on: 
  - GT-P4-01
---

# Implement Core File and Search Tools

Add `file_read`, `file_write`, and `project_search` (grep/glob) tools.

## Scope

- Implement the three tools as LangChain tools.
- Route file access through the sandbox interface.

## Requirements

- Tools respect per-agent `forbidden_paths` and stay within tool roots.

## Acceptance Criteria

- Tests: an agent reads a file, writes a change, and searches the project.
