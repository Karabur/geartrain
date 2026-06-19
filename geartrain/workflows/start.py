"""Generic workflow start path.

Resolves a workflow by name and runs it on the generic ``WorkflowRunner`` from
its entry node. The engine names no workflow: any registered workflow starts the
same way. An optional task string from the caller seeds ``trigger.task``.

Run logging — the human ``<workflow>.md`` line and the machine-readable
``<workflow>.events.jsonl`` stream — lives here so every workflow gets it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from geartrain.engine.state import generate_run_id
from geartrain.workflows.engine import WorkflowRunError, WorkflowRunner

if TYPE_CHECKING:
    from geartrain.agents import AgentRunner
    from geartrain.engine.config import WorkflowDefinition
    from geartrain.engine.state import FileStateBackend


def _append_log_line(log_file: Path, run_id: str, task_name: str, status: str) -> None:
    """Append one line to the workflow's human-readable log."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} | run={run_id} | task={task_name} | status={status}\n"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line)


def _append_event_log(log_file: Path, run_id: str, events: list[dict]) -> None:
    """Append a run's events to the workflow's machine-readable JSONL log.

    Mirrors the per-run ``events.jsonl`` into a workflow-level log
    (``<workflow>.events.jsonl``) so dogfooding has one stream to tail across
    runs. Each line is tagged with its run id.
    """
    events_log = log_file.with_suffix(".events.jsonl")
    events_log.parent.mkdir(parents=True, exist_ok=True)
    with events_log.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps({"run_id": run_id, **ev}) + "\n")


def run_workflow(
    workflow: "WorkflowDefinition",
    agents: dict[str, "AgentRunner"],
    state_backend: "FileStateBackend",
    state_path: Path,
    log_file: Path,
    run_id: str,
    task: str = "",
    work_dir: Path | None = None,
    checkpoint_input_fn=None,
    integrations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one workflow iteration from its entry node and write run logs.

    ``task`` seeds ``trigger.task`` and defaults to empty. The workflow runs on
    the generic ``WorkflowRunner`` with no workflow-specific behavior. Pass
    ``integrations`` (e.g. ``{"github": client}``) to back any integration nodes.

    Returns the workflow result dict. Raises ``WorkflowRunError`` if the
    workflow is already running.
    """
    runner = WorkflowRunner(
        workflow=workflow,
        agents=agents,
        state_backend=state_backend,
        state_path=state_path,
        work_dir=work_dir,
        checkpoint_input_fn=checkpoint_input_fn,
        integrations=integrations,
    )

    if runner.is_locked():
        held_by = runner.current_run_id()
        raise WorkflowRunError(
            f"Workflow {workflow.name!r} is already running (run_id={held_by!r})"
        )

    try:
        result = runner.run(run_id=run_id, trigger_task=task)
    except Exception:
        # Record the failed run's log lines before propagating so a failure is
        # always inspectable in both the human and machine-readable logs.
        _append_log_line(log_file, run_id, "-", "failed")
        _append_event_log(log_file, run_id, state_backend.read_events(run_id))
        raise

    _append_log_line(log_file, run_id, "-", result.get("status", "?"))
    _append_event_log(log_file, run_id, state_backend.read_events(run_id))

    return result


def start_workflow(
    engine_app,
    name: str,
    task: str = "",
    *,
    build_runner,
    integrations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve a workflow by name and run it through the generic run path.

    ``build_runner`` builds an agent runner from an ``AgentDefinition``; it is
    injected so this module stays free of agent-factory wiring. Returns a result
    dict, or ``{"status": "already_running", ...}`` / ``{"error": ...}`` when the
    workflow cannot start.
    """
    if name not in engine_app.workflows:
        return {"error": f"Unknown workflow: {name}"}

    workflow_def = engine_app.workflows[name]
    state_path = engine_app.state_path

    runner_lock = WorkflowRunner(
        workflow=workflow_def,
        agents={},
        state_backend=engine_app.state_backend,
        state_path=state_path,
    )
    if runner_lock.is_locked():
        current = runner_lock.current_run_id()
        return {"status": "already_running", "current_run": current}

    agents = {
        role: build_runner(engine_app.agents[agent_name])
        for role, agent_name in workflow_def.agents.items()
        if agent_name in engine_app.agents
    }
    run_id = generate_run_id(name, state_path=state_path)
    log_file = engine_app.logs_dir / f"{name}.md"

    return run_workflow(
        workflow=workflow_def,
        agents=agents,
        state_backend=engine_app.state_backend,
        state_path=state_path,
        log_file=log_file,
        run_id=run_id,
        task=task,
        work_dir=engine_app.work_dir,
        integrations=integrations,
    )
