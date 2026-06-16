---
id: GT-P5-02
phase: 5
status: todo
depends_on: 
  - GT-P5-01
---

# Implement MarkdownMemoryStore

Implement the markdown-file memory store with keyword search.

## Scope

- `write` creates a markdown file with frontmatter (system, scope, category, tags, timestamps).
- `read` keyword-searches and ranks; `update`, `list`, `forget` (soft delete).

## Requirements

- Markdown files are the single source of truth, editable by humans and agents.
- Conflict handling is not needed for MVP: last write to a file wins, git review curates changes.

## Acceptance Criteria

- Tests: write an entry, retrieve it by keyword, update it, list by scope, soft-delete it.
