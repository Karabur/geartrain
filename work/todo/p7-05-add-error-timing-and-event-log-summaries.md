---
id: GT-P7-05
phase: 7
status: todo
depends_on:
  - GT-P7-01
  - GT-P7-02
  - GT-P7-03
  - GT-P7-04
---

# Add Error, Timing, and Event Log Summaries

Make run observability usable without a dashboard.

## Scope

- Summarize run status, node timings, attempt timings, tool counts, memory update counts, and terminal errors.
- Add CLI/API output for run summaries and event timelines.
- Ensure `.geartrain/logs/geartrain-dev.md` and `.geartrain/logs/geartrain-dev.events.jsonl` are written for dogfooding runs.

## Requirements

- The summary is compact and readable in a terminal.
- The structured event log remains machine-readable JSONL.

## Acceptance Criteria

- A failed run prints where it failed, why, and which event log to inspect.
- Tests assert summary output and event log files are written for success and failure.
