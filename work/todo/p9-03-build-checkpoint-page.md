---
id: GT-P9-03
phase: 9
status: todo
depends_on: 
  - GT-P9-02
---

# Build Checkpoint Page

Handle human-in-the-loop input in the UI.

## Scope

- Pending and resolved checkpoint list.
- Form for approve/reject/provide-text; posts to the respond endpoint.
- Checkpoint detail links back to run, node, prior output, and event timeline.

## Requirements

- Submitting resumes the paused workflow.

## Acceptance Criteria

- A developer can approve a plan and the workflow continues.
