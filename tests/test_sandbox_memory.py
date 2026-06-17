"""Tests for sandbox and memory manager interfaces (GT-P1-08)."""

from pathlib import Path

from geartrain.engine.app import EngineApp
from geartrain.engine.sandbox import NoopSandbox
from geartrain.memory.noop import NoopMemoryManager


ROOT = Path(__file__).parent.parent


class TestNoopSandbox:
    """NoopSandbox runs commands and file operations directly."""

    def test_execute_command(self):
        sb = NoopSandbox()
        stdout, stderr, rc = sb.execute_command("echo hello")
        assert rc == 0
        assert "hello" in stdout

    def test_read_file(self, tmp_path):
        sb = NoopSandbox()
        f = tmp_path / "test.txt"
        f.write_text("content here")
        assert sb.read_file(str(f)) == "content here"

    def test_write_file(self, tmp_path):
        sb = NoopSandbox()
        f = tmp_path / "out.txt"
        sb.write_file(str(f), "written content")
        assert f.read_text() == "written content"

    def test_list_directory(self, tmp_path):
        sb = NoopSandbox()
        (tmp_path / "a.txt").touch()
        (tmp_path / "b.txt").touch()
        names = sb.list_directory(str(tmp_path))
        assert set(names) == {"a.txt", "b.txt"}


class TestNoopMemoryManager:
    """NoopMemoryManager returns empty results and ignores writes."""

    def test_read_returns_empty(self):
        mgr = NoopMemoryManager()
        assert mgr.read("workspace") == []

    def test_write_no_error(self):
        mgr = NoopMemoryManager()
        mgr.write("workspace", "some content")

    def test_search_returns_empty(self):
        mgr = NoopMemoryManager()
        assert mgr.search("query") == []
        assert mgr.search("query", scopes=["workspace"]) == []


class TestEngineAppIntegration:
    """EngineApp creates sandbox and memory manager on init."""

    def test_creates_sandbox_and_memory_manager(self):
        app = EngineApp(
            workspace_path=ROOT / ".geartrain" / "workspace.yaml",
            engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
        )
        assert isinstance(app.sandbox, NoopSandbox)
        assert isinstance(app.memory_manager, NoopMemoryManager)
