"""Tests for work/ folder task helpers (GT-P3-01)."""

from pathlib import Path

import pytest

from geartrain.work.tasks import (
    TaskFile,
    format_task_list,
    list_tasks,
    move_to_in_progress,
    pick_next_task,
)


def _write_task(directory: Path, name: str, content: str = "# Task") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    f = directory / name
    f.write_text(content)
    return f


@pytest.fixture
def work_dir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    (d / "todo").mkdir(parents=True)
    (d / "in-progress").mkdir(parents=True)
    (d / "done").mkdir(parents=True)
    return d


class TestPickNextTask:
    def test_empty_returns_none(self, work_dir: Path):
        assert pick_next_task(work_dir) is None

    def test_picks_in_progress_over_todo(self, work_dir: Path):
        _write_task(work_dir / "todo", "a-task.md")
        _write_task(work_dir / "in-progress", "b-task.md")
        result = pick_next_task(work_dir)
        assert result is not None
        assert result.folder == "in-progress"
        assert result.path.name == "b-task.md"

    def test_picks_first_in_progress_by_name(self, work_dir: Path):
        _write_task(work_dir / "in-progress", "z-task.md")
        _write_task(work_dir / "in-progress", "a-task.md")
        result = pick_next_task(work_dir)
        assert result is not None
        assert result.path.name == "a-task.md"

    def test_picks_first_todo_when_no_in_progress(self, work_dir: Path):
        _write_task(work_dir / "todo", "b-task.md")
        _write_task(work_dir / "todo", "a-task.md")
        result = pick_next_task(work_dir)
        assert result is not None
        assert result.folder == "todo"
        assert result.path.name == "a-task.md"

    def test_ignores_gitkeep(self, work_dir: Path):
        (work_dir / "in-progress" / ".gitkeep").write_text("")
        assert pick_next_task(work_dir) is None

    def test_missing_subdirs_does_not_error(self, tmp_path: Path):
        d = tmp_path / "empty_work"
        d.mkdir()
        assert pick_next_task(d) is None


class TestMoveToInProgress:
    def test_moves_file(self, work_dir: Path):
        src = _write_task(work_dir / "todo", "my-task.md", "content")
        dest = move_to_in_progress(src, work_dir)
        assert dest.exists()
        assert dest.parent.name == "in-progress"
        assert not src.exists()
        assert dest.read_text() == "content"

    def test_creates_in_progress_dir_if_missing(self, tmp_path: Path):
        d = tmp_path / "work"
        (d / "todo").mkdir(parents=True)
        src = _write_task(d / "todo", "task.md")
        dest = move_to_in_progress(src, d)
        assert dest.exists()
        assert dest.parent.name == "in-progress"


class TestListTasks:
    def test_empty_returns_empty(self, work_dir: Path):
        assert list_tasks(work_dir) == []

    def test_lists_across_folders(self, work_dir: Path):
        _write_task(work_dir / "todo", "todo-task.md")
        _write_task(work_dir / "in-progress", "wip-task.md")
        _write_task(work_dir / "done", "done-task.md")
        tasks = list_tasks(work_dir)
        assert len(tasks) == 3
        folders = [t.folder for t in tasks]
        assert "todo" in folders
        assert "in-progress" in folders
        assert "done" in folders

    def test_sorted_within_folder(self, work_dir: Path):
        _write_task(work_dir / "todo", "z.md")
        _write_task(work_dir / "todo", "a.md")
        tasks = [t for t in list_tasks(work_dir) if t.folder == "todo"]
        assert tasks[0].path.name == "a.md"
        assert tasks[1].path.name == "z.md"


class TestFormatTaskList:
    def test_no_tasks(self, work_dir: Path):
        result = format_task_list(work_dir)
        assert "No tasks" in result

    def test_shows_task_names(self, work_dir: Path):
        _write_task(work_dir / "todo", "my-task.md")
        result = format_task_list(work_dir)
        assert "my-task.md" in result
        assert "todo" in result
