"""Task file helpers — pick, move, and list work/ folder tasks."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class TaskFile(NamedTuple):
    """A task file with its current folder state."""

    path: Path
    folder: str  # "todo", "in-progress", or "done"


def _md_files(directory: Path) -> list[Path]:
    """Return sorted .md files in a directory, excluding .gitkeep."""
    if not directory.is_dir():
        return []
    return sorted(
        f for f in directory.iterdir()
        if f.suffix == ".md" and f.name != ".gitkeep"
    )


def pick_next_task(work_dir: Path) -> TaskFile | None:
    """Return the next task to work on.

    Checks in-progress/ first, then todo/. Returns None if both are empty.
    """
    in_progress = work_dir / "in-progress"
    files = _md_files(in_progress)
    if files:
        return TaskFile(files[0], "in-progress")

    todo = work_dir / "todo"
    files = _md_files(todo)
    if files:
        return TaskFile(files[0], "todo")

    return None


def move_to_in_progress(task_path: Path, work_dir: Path) -> Path:
    """Move a task file from todo/ to in-progress/.

    Returns the new path. Creates in-progress/ if it does not exist.
    """
    dest_dir = work_dir / "in-progress"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / task_path.name
    task_path.rename(dest)
    return dest


def list_tasks(work_dir: Path) -> list[TaskFile]:
    """Return all task files across todo/, in-progress/, and done/."""
    result: list[TaskFile] = []
    for folder in ("todo", "in-progress", "done"):
        for path in _md_files(work_dir / folder):
            result.append(TaskFile(path, folder))
    return result


def format_task_list(work_dir: Path) -> str:
    """Return a human-readable summary of all tasks."""
    tasks = list_tasks(work_dir)
    if not tasks:
        return "No tasks found."

    lines: list[str] = []
    current_folder = None
    for task in tasks:
        if task.folder != current_folder:
            current_folder = task.folder
            lines.append(f"\n{current_folder}/")
        lines.append(f"  {task.path.name}")
    return "\n".join(lines).strip()
