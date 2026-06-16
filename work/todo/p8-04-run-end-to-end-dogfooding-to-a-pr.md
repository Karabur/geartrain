---
id: GT-P8-04
phase: 8
status: todo
depends_on: 
  - GT-P8-02
  - GT-P8-03
  - GT-P7-05
---

# Run End-to-End Dogfooding to a PR

Pick a real task, run feature-development, and produce a PR; fix rough edges.

## Scope

- Run the workflow against a real `work/` task with real agents.
- Fix bugs and rough edges found during the run.

## Requirements

- The run produces a reviewable PR.

## Acceptance Criteria

- A real task goes from `work/todo` to an open PR via the workflow.
