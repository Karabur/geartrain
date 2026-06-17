---
id: GT-P3-04
phase: 3
status: todo
depends_on: 
  - GT-P3-02
---

# Implement Workflow Error Handling

On node failure, log the error and stop the run cleanly.

## Scope

- Catch node/agent failures.
- Write the error to run state and the workflow log.
- Mark the run failed and release resources.

## Requirements

- MVP error handling is log-and-stop: no retry, skip, or escalation.
- A handled failure must not leave a stuck lock.

## Acceptance Criteria

- Tests assert a failing node stops the run, records the error, and releases the lock.
