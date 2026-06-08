---
id: GT-M1-012
status: todo
depends_on:
  - GT-M1-005
  - GT-M1-011
---

# Implement Workflow Start CLI Command

Add the user-facing workflow command for starting the first workflow.

## Scope

- Add `geartrain workflow start`.
- Call `POST /workflows/geartrain-dev/start`.
- Print status or final workflow response.

## Requirements

- Command starts `geartrain-dev`.
- If workflow is already running, print current status and do nothing else.
- CLI does not run workflow logic directly.

## Acceptance Criteria

- `geartrain workflow start` starts a run.
- Running it again while locked reports current status.
- No task case returns a clear message.
