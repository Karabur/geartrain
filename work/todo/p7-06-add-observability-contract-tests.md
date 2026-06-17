---
id: GT-P7-06
phase: 7
status: todo
depends_on:
  - GT-P7-05
---

# Add Observability Contract Tests

Lock down the run/event contracts before dogfooding.

## Scope

- Seed runs with nodes, attempts, checkpoints, tool calls, memory events, errors, and timings.
- Test query APIs, streaming APIs, CLI summaries, and JSONL event shape.

## Requirements

- Tests are offline and deterministic.
- Tests should catch event schema drift.

## Acceptance Criteria

- Contract tests cover success, waiting, failed, and memory-write-rejected runs.
