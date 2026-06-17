# Running GearTrain Locally

This covers setup and operation for the first runnable version (phases 1-3). It runs a local engine, calls agents directly, and runs the `geartrain-dev` workflow against tasks in `work/`.

Memory, web UI, GitHub integration, and the LangChain agent type are not yet implemented — they arrive in later phases.

## Prerequisites

- Python 3.11+
- `codex` CLI installed and on `PATH` ([OpenAI Codex CLI](https://github.com/openai/codex))
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` environment variable set (used by Codex)

## Setup

Clone the repo and install the package:

```bash
git clone <repo>
cd geartrain
pip install -e .
```

The `.geartrain/` directory is already scaffolded in the repo. It contains the workspace config, agents, workflow definition, and state directories.

## Engine commands

Start the local engine in the foreground:

```bash
geartrain engine start
```

The engine validates all config files on startup and exits with an error if anything is wrong. It serves the HTTP API at `http://127.0.0.1:8420` by default.

Check engine status (in a second terminal while the engine is running):

```bash
geartrain engine status
```

Stop the engine:

```bash
geartrain engine stop
```

## Calling agents directly

Send a one-shot prompt to a named agent:

```bash
geartrain agent lead "show tasks"
geartrain agent lead "what is the next task?"
```

The agent command calls the engine API and prints the plain text response. It's not a chat session — each call is independent.

The lead agent has access to one tool: `workflow start`. If its response contains the line `GEARTRAIN_TOOL workflow start`, the engine starts the next `geartrain-dev` workflow iteration.

## Running the workflow

Start one `geartrain-dev` workflow iteration:

```bash
geartrain workflow start
```

The workflow:

1. Picks the first task from `work/in-progress/`, or the first task from `work/todo/` if in-progress is empty.
2. Moves the chosen `todo/` task to `in-progress/`.
3. Runs `coder` on the task.
4. Passes coder output to `lead`.
5. Appends one line to `.geartrain/logs/geartrain-dev.md`.
6. Ends.

If no tasks exist in either folder, the workflow exits with a clear message and does nothing.

If the workflow is already running, the command prints the current run status instead of starting another.

Tasks are **not** automatically moved to `done/`. Move them manually after reviewing the coder and lead output.

## Where state and logs live

```text
.geartrain/
├── state/
│   ├── engine.md              # engine status
│   ├── workflows/
│   │   └── geartrain-dev.md   # workflow status
│   └── runs/
│       └── <run-id>/
│           ├── run.md         # run status
│           ├── 01-run_coder.md
│           └── 02-run_lead.md
└── logs/
    └── geartrain-dev.md       # one line per run
```

All state files are plain markdown with YAML frontmatter — human-readable and editable.

## How task files move

```text
work/
├── todo/        ← ready to start
├── in-progress/ ← an agent is working on it
└── done/        ← completed (moved manually)
```

When `geartrain workflow start` runs, it picks the first task from `in-progress/` (if any), or moves the first task from `todo/` to `in-progress/`. After reviewing the output, move the task to `done/` yourself.

## Validating configuration

```bash
geartrain validate
```

Checks all config files — workspace, engine, agents, workflow, memory — and prints any errors or warnings. The engine also runs validation on startup.

## Troubleshooting

**"Engine is not running"**

Start the engine with `geartrain engine start` in a separate terminal.

**"command 'codex' not found on PATH"**

Install the Codex CLI and make sure it's on your PATH. The validator will warn about this on startup. Agent calls will fail until Codex is available.

**"Invalid config"**

Run `geartrain validate` for field-level diagnostics. The most common issues are missing registry directories and invalid YAML structure. Fix the reported fields and restart the engine.

**"Workflow is already running"**

A previous run may have crashed without releasing its lock. The lock file is at `.geartrain/state/locks/geartrain-dev.lock`. Delete it to reset, then start the workflow again.
