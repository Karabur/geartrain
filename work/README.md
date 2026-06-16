# GearTrain Work Folder

This folder is the implementation driver for GearTrain itself. It is separate from `.geartrain/`, which is the runtime workspace loaded by the engine.

Tasks are tracked here as markdown files, not in Linear or any external tracker. [ROADMAP.md](ROADMAP.md) defines the phases and their order; each task file carries a `phase` frontmatter field tying it to a phase.

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

## Task File Format

Each task is a markdown file with frontmatter:

```yaml
---
id: GT-P1-04
phase: 1
status: todo
depends_on:
  - GT-P1-02
  - GT-P1-03
---
```

Filenames are prefixed `p<phase>-<nn>-<slug>.md` so filename sort matches phase and task order. The body has `Scope`, `Requirements`, and `Acceptance Criteria` sections.

## Phases

The MVP (the dogfooding milestone) is delivered as eight phases, each covering one module. Phases 1-3 deliver the first runnable version; phases 1-8 deliver the MVP. See [ROADMAP.md](ROADMAP.md) for the full breakdown.

## Operating Rules

- Move one task at a time from `todo/` to `in-progress/`.
- Keep task IDs stable when moving files.
- Add notes to the task file while working.
- Move the task to `done/` only after its acceptance criteria are met.
- Use [ROADMAP.md](ROADMAP.md) for phase scope and order. `work/SPEC.md` is the detailed contract for the runnable version (phases 1-3).
