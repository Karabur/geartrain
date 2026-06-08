# GearTrain Work Folder

This folder is the implementation driver for GearTrain itself. It is separate from `.geartrain/`, which is the runtime workspace loaded by the engine.

## State Model

Tasks move between folders:

```text
work/
├── SPEC.md
├── todo/
├── in-progress/
└── done/
```

The folder location is the source of truth for task state:

- `todo/` means the task is ready or waiting.
- `in-progress/` means an agent or human is working on it.
- `done/` means the task is complete.

Task files should stay small enough for an agent to complete in one focused run. If a task grows, split it before starting.

## Operating Rules

- Move one task at a time from `todo/` to `in-progress/`.
- Keep task IDs stable when moving files.
- Add notes to the task file while working.
- Move the task to `done/` only after its acceptance criteria are met.
- Use `work/SPEC.md` as the first milestone contract.
