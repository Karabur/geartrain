---
id: GT-P6-01
phase: 6
status: todo
depends_on: 
  - GT-P4-03
---

# Implement GitHub Branch, Commit, and PR Creation

Add a GitHub client for the write path.

## Scope

- Create branch, commit changes, open a PR with description.

## Requirements

- Token comes from engine credentials (env var).
- Robust error handling; a human can finish steps manually.

## Acceptance Criteria

- Tests (mocked) cover branch/commit/PR creation and error paths.
