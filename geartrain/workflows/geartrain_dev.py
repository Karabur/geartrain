"""geartrain-dev workflow coordinator — task selection and log writing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from geartrain.work.tasks import TaskFile, move_to_in_progress, pick_next_task
from geartrain.workflows.engine import WorkflowRunError, WorkflowRunner

if TYPE_CHECKING:
    from geartrain.agents import AgentRunner
    from geartrain.engine.config import WorkflowDefinition
    from geartrain.engine.state import FileStateBackend


def _append_log_line(log_file: Path, run_id: str, task_name: str, status: str) -> None:
    """Append one line to the workflow log."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} | run={run_id} | task={task_name} | status={status}\n"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line)


def run_geartrain_dev(
    workflow: "WorkflowDefinition",
    agents: dict[str, "AgentRunner"],
    state_backend: "FileStateBackend",
    state_path: Path,
    work_dir: Path,
    run_id: str,
    log_file: Path,
    checkpoint_input_fn=None,
    integrations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one geartrain-dev workflow iteration.

    Selects the next task, moves it to in-progress if needed, runs coder
    then lead via the generic engine, and appends one line to the log.
    Pass ``integrations`` (e.g. ``{"github": client}``) to back any
    integration nodes in the workflow.

    Returns the workflow result dict. Raises WorkflowRunError if already running.
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

    # Select next task
    task_file = pick_next_task(work_dir)
    if task_file is None:
        return {
            "run_id": None,
            "workflow": workflow.name,
            "status": "no_tasks",
            "message": "No tasks found in work/in-progress or work/todo.",
        }

    # Move todo task to in-progress
    if task_file.folder == "todo":
        new_path = move_to_in_progress(task_file.path, work_dir)
        task_file = TaskFile(new_path, "in-progress")

    task_content = task_file.path.read_text(encoding="utf-8")
    trigger_task = (
        f"Task file: {task_file.path}\n\n{task_content}"
    )

    result = runner.run(run_id=run_id, trigger_task=trigger_task)

    _append_log_line(log_file, run_id, task_file.path.name, result.get("status", "?"))

    return result
