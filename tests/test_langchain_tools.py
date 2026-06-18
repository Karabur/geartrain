"""Tests for langchain file, search, shell, and git tools (GT-P4-02, GT-P4-03)."""

import subprocess

import pytest

from geartrain.agents.tools import ToolRecorder, build_tools
from geartrain.agents.tools.files import (
    PathNotAllowedError,
    file_read,
    file_write,
    project_search,
    resolve_within_root,
)
from geartrain.engine.sandbox import NoopSandbox


# --- path safety ------------------------------------------------------------


class TestPathSafety:
    def test_relative_path_resolves_under_root(self, tmp_path):
        resolved = resolve_within_root("sub/file.txt", str(tmp_path), [])
        assert str(resolved).startswith(str(tmp_path.resolve()))

    def test_escape_outside_root_rejected(self, tmp_path):
        with pytest.raises(PathNotAllowedError, match="outside"):
            resolve_within_root("../secrets.txt", str(tmp_path), [])

    def test_forbidden_path_rejected(self, tmp_path):
        with pytest.raises(PathNotAllowedError, match="forbidden"):
            resolve_within_root(".env", str(tmp_path), [".env"])

    def test_forbidden_directory_rejected(self, tmp_path):
        with pytest.raises(PathNotAllowedError, match="forbidden"):
            resolve_within_root("secrets/key.pem", str(tmp_path), ["secrets"])


# --- core file tools --------------------------------------------------------


class TestFileTools:
    def test_read_write_search(self, tmp_path):
        sandbox = NoopSandbox()
        root = str(tmp_path)
        deps = {"sandbox": sandbox, "root": root, "forbidden_paths": ()}

        write = file_write(path="app.py", content="print('hi')\n", **deps)
        assert write.status == "ok"
        assert (tmp_path / "app.py").read_text() == "print('hi')\n"

        read = file_read(path="app.py", **deps)
        assert read.output == "print('hi')\n"

        found = project_search(pattern=r"print", glob="*.py", **deps)
        assert "app.py:1:" in found.output
        assert found.status == "ok"

    def test_search_no_match(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        result = project_search(
            pattern="nonexistent",
            sandbox=NoopSandbox(),
            root=str(tmp_path),
            forbidden_paths=(),
        )
        assert "no matches" in result.output


# --- recorded tool events ---------------------------------------------------


class TestToolEvents:
    def test_file_tools_record_event_metadata(self, tmp_path):
        recorder = ToolRecorder()
        tools = build_tools(
            ["file_write", "file_read"],
            sandbox=NoopSandbox(),
            recorder=recorder,
            root=str(tmp_path),
        )
        by_name = {t.name: t for t in tools}

        by_name["file_write"].invoke({"path": "x.txt", "content": "hello"})
        by_name["file_read"].invoke({"path": "x.txt"})

        assert len(recorder.events) == 2
        write_event = recorder.events[0]
        assert write_event.name == "file_write"
        assert write_event.status == "ok"
        assert write_event.duration_ms >= 0
        assert "path=" in write_event.input_summary
        assert write_event.output_summary
        assert write_event.error == ""
        # Event is serializable for a Phase 7 tool-call event.
        assert set(write_event.to_dict()) == {
            "name",
            "category",
            "input_summary",
            "output_summary",
            "status",
            "duration_ms",
            "error",
        }
        assert write_event.to_dict()["category"] == "file"

    def test_failure_records_error_event(self, tmp_path):
        recorder = ToolRecorder()
        tools = build_tools(
            ["file_read"],
            sandbox=NoopSandbox(),
            recorder=recorder,
            root=str(tmp_path),
        )
        # Reading a missing file fails; the wrapper records an error event.
        out = tools[0].invoke({"path": "missing.txt"})
        assert "failed" in out
        event = recorder.events[0]
        assert event.status == "error"
        assert event.error

    def test_unknown_tool_name_raises(self, tmp_path):
        with pytest.raises(ValueError, match="unknown tool"):
            build_tools(
                ["does_not_exist"],
                sandbox=NoopSandbox(),
                recorder=ToolRecorder(),
                root=str(tmp_path),
            )


# --- shell and git tools ----------------------------------------------------


@pytest.fixture
def temp_repo(tmp_path):
    """A temp git repo with one committed file."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.io"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# repo\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    return tmp_path


class TestShellAndGitTools:
    def test_shell_exec_runs_command(self, tmp_path):
        recorder = ToolRecorder()
        tools = build_tools(
            ["shell_exec"],
            sandbox=NoopSandbox(),
            recorder=recorder,
            shell_cwd=str(tmp_path),
        )
        out = tools[0].invoke({"command": "echo hello"})
        assert "hello" in out
        assert recorder.events[0].status == "ok"

    def test_shell_exec_failure_metadata(self, tmp_path):
        recorder = ToolRecorder()
        tools = build_tools(
            ["shell_exec"],
            sandbox=NoopSandbox(),
            recorder=recorder,
            shell_cwd=str(tmp_path),
        )
        out = tools[0].invoke({"command": "exit 3"})
        assert "exit 3" in out
        event = recorder.events[0]
        assert event.status == "error"
        assert "exit 3" in event.error

    def test_git_status_against_temp_repo(self, temp_repo):
        recorder = ToolRecorder()
        tools = build_tools(
            ["git_status"],
            sandbox=NoopSandbox(),
            recorder=recorder,
            shell_cwd=str(temp_repo),
        )
        (temp_repo / "new.txt").write_text("change\n")
        out = tools[0].invoke({})
        assert "new.txt" in out
        assert recorder.events[0].status == "ok"

    def test_git_commit_and_branch(self, temp_repo):
        recorder = ToolRecorder()
        tools = {
            t.name: t
            for t in build_tools(
                ["git_branch", "git_commit", "git_diff"],
                sandbox=NoopSandbox(),
                recorder=recorder,
                shell_cwd=str(temp_repo),
            )
        }

        branch_out = tools["git_branch"].invoke({"name": "feature/x"})
        assert "feature/x" in branch_out or branch_out == "(no output)"

        (temp_repo / "feature.txt").write_text("work\n")
        commit_out = tools["git_commit"].invoke({"message": "add feature"})
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=temp_repo,
            capture_output=True,
            text=True,
        )
        assert "add feature" in log.stdout
