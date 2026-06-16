"""Tests for file-backed state management (GT-P1-05)."""

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from geartrain.engine.state import (
    FileStateBackend,
    create_state_backend,
    generate_run_id,
)


@pytest.fixture
def state_root(tmp_path: Path) -> Path:
    """A temporary state directory."""
    return tmp_path / "state"


@pytest.fixture
def backend(state_root: Path) -> FileStateBackend:
    """FileStateBackend pointing at a temp directory."""
    return FileStateBackend(state_path=state_root)


# --- Engine state tests -----------------------------------------------------


class TestEngineState:
    """Writing and reading engine state."""

    def test_write_engine_state_creates_file(self, backend: FileStateBackend):
        path = backend.write_engine_state(
            engine_name="local-dev",
            status="started",
            workspace_name="geartrain-core",
            pid=12345,
        )
        assert path.exists()
        assert path.name == "engine.md"

    def test_write_engine_state_frontmatter(self, backend: FileStateBackend):
        backend.write_engine_state(
            engine_name="local-dev",
            status="started",
            workspace_name="geartrain-core",
            pid=12345,
        )
        data = backend.read_engine_state()
        assert data["schema_version"] == 1
        assert data["engine_name"] == "local-dev"
        assert data["status"] == "started"
        assert data["workspace"] == "geartrain-core"
        assert data["pid"] == 12345
        assert data["started_at"] is not None

    def test_write_engine_state_no_pid(self, backend: FileStateBackend):
        backend.write_engine_state(
            engine_name="local-dev",
            status="stopped",
            workspace_name="geartrain-core",
        )
        data = backend.read_engine_state()
        assert data["pid"] is None
        assert data["started_at"] is None

    def test_read_engine_state_raises_when_missing(self, backend: FileStateBackend):
        with pytest.raises(FileNotFoundError):
            backend.read_engine_state()

    def test_engine_state_body_is_markdown(self, backend: FileStateBackend):
        backend.write_engine_state(
            engine_name="local-dev",
            status="started",
            workspace_name="geartrain-core",
            pid=12345,
        )
        text = backend.state_path.joinpath("engine.md").read_text()
        assert "# Engine State" in text
        assert "**Engine**: local-dev" in text
        assert "**PID**: 12345" in text


# --- Workflow state tests ---------------------------------------------------


class TestWorkflowState:
    """Writing and reading workflow state."""

    def test_write_workflow_state_creates_file(
        self, backend: FileStateBackend
    ):
        path = backend.write_workflow_state(
            workflow_name="geartrain-dev",
            status="idle",
        )
        assert path.exists()
        assert path.name == "geartrain-dev.md"
        assert "workflows" in str(path)

    def test_write_workflow_state_frontmatter(
        self, backend: FileStateBackend
    ):
        backend.write_workflow_state(
            workflow_name="geartrain-dev",
            status="running",
            current_run="2026-06-16-geartrain-dev-001",
        )
        data = backend.read_workflow_state("geartrain-dev")
        assert data["schema_version"] == 1
        assert data["workflow_name"] == "geartrain-dev"
        assert data["status"] == "running"
        assert data["current_run"] == "2026-06-16-geartrain-dev-001"

    def test_write_workflow_state_no_current_run(
        self, backend: FileStateBackend
    ):
        backend.write_workflow_state(
            workflow_name="geartrain-dev",
            status="idle",
        )
        data = backend.read_workflow_state("geartrain-dev")
        assert data["current_run"] is None

    def test_read_workflow_state_raises_when_missing(
        self, backend: FileStateBackend
    ):
        with pytest.raises(FileNotFoundError):
            backend.read_workflow_state("nonexistent")

    def test_workflow_state_body(self, backend: FileStateBackend):
        backend.write_workflow_state(
            workflow_name="geartrain-dev", status="idle"
        )
        text = (
            backend.state_path / "workflows" / "geartrain-dev.md"
        ).read_text()
        assert "# Workflow State: geartrain-dev" in text
        assert "**Current run**: none" in text


# --- Run state tests --------------------------------------------------------


class TestRunState:
    """Creating and updating run state."""

    def test_create_run_makes_directory(self, backend: FileStateBackend):
        path = backend.create_run(
            run_id="2026-06-16-geartrain-dev-001",
            workflow_name="geartrain-dev",
        )
        run_dir = backend.state_path / "runs" / "2026-06-16-geartrain-dev-001"
        assert run_dir.is_dir()
        assert path == run_dir / "run.md"

    def test_create_run_frontmatter(self, backend: FileStateBackend):
        backend.create_run(
            run_id="2026-06-16-geartrain-dev-001",
            workflow_name="geartrain-dev",
        )
        data = backend.read_run_state("2026-06-16-geartrain-dev-001")
        assert data["schema_version"] == 1
        assert data["run_id"] == "2026-06-16-geartrain-dev-001"
        assert data["workflow"] == "geartrain-dev"
        assert data["status"] == "running"
        assert data["started_at"] is not None
        assert data["current_node"] is None

    def test_update_run_status(self, backend: FileStateBackend):
        backend.create_run(
            run_id="2026-06-16-geartrain-dev-001",
            workflow_name="geartrain-dev",
        )
        backend.update_run_status(
            run_id="2026-06-16-geartrain-dev-001",
            status="completed",
        )
        data = backend.read_run_state("2026-06-16-geartrain-dev-001")
        assert data["status"] == "completed"

    def test_update_run_status_with_node(self, backend: FileStateBackend):
        backend.create_run(
            run_id="2026-06-16-geartrain-dev-001",
            workflow_name="geartrain-dev",
        )
        backend.update_run_status(
            run_id="2026-06-16-geartrain-dev-001",
            status="running",
            current_node="intake",
        )
        data = backend.read_run_state("2026-06-16-geartrain-dev-001")
        assert data["status"] == "running"
        assert data["current_node"] == "intake"

    def test_read_run_state_raises_when_missing(self, backend: FileStateBackend):
        with pytest.raises(FileNotFoundError):
            backend.read_run_state("nonexistent-run")

    def test_run_state_body(self, backend: FileStateBackend):
        backend.create_run(
            run_id="2026-06-16-geartrain-dev-001",
            workflow_name="geartrain-dev",
        )
        text = (
            backend.state_path
            / "runs"
            / "2026-06-16-geartrain-dev-001"
            / "run.md"
        ).read_text()
        assert "# Run: 2026-06-16-geartrain-dev-001" in text
        assert "**Workflow**: geartrain-dev" in text
        assert "**Status**: running" in text


# --- Node output tests ------------------------------------------------------


class TestNodeOutput:
    """Writing and reading node output files."""

    def _setup_run(self, backend: FileStateBackend):
        """Create a run for node output tests."""
        backend.create_run(
            run_id="2026-06-16-geartrain-dev-001",
            workflow_name="geartrain-dev",
        )

    def test_write_node_output_creates_file(
        self, backend: FileStateBackend
    ):
        self._setup_run(backend)
        path = backend.write_node_output(
            run_id="2026-06-16-geartrain-dev-001",
            node_id="intake",
            node_type="agent",
            agent="lead",
            status="completed",
            output_text="Analysis complete.",
            output_key="plan",
            node_number=1,
        )
        assert path.exists()
        assert path.name == "01-intake.md"

    def test_write_node_output_frontmatter(
        self, backend: FileStateBackend
    ):
        self._setup_run(backend)
        backend.write_node_output(
            run_id="2026-06-16-geartrain-dev-001",
            node_id="intake",
            node_type="agent",
            agent="lead",
            status="completed",
            output_text="Analysis complete.",
            output_key="plan",
            node_number=1,
        )
        data = backend.read_node_output(
            "2026-06-16-geartrain-dev-001", "intake"
        )
        assert data["schema_version"] == 1
        assert data["node_id"] == "intake"
        assert data["node_type"] == "agent"
        assert data["agent"] == "lead"
        assert data["status"] == "completed"
        assert data["output_key"] == "plan"

    def test_write_node_output_no_agent_no_key(
        self, backend: FileStateBackend
    ):
        self._setup_run(backend)
        backend.write_node_output(
            run_id="2026-06-16-geartrain-dev-001",
            node_id="approve-plan",
            node_type="human",
            agent=None,
            status="pending",
            output_text="",
        )
        data = backend.read_node_output(
            "2026-06-16-geartrain-dev-001", "approve-plan"
        )
        assert data["agent"] is None
        assert data["output_key"] is None

    def test_write_node_output_no_number(
        self, backend: FileStateBackend
    ):
        self._setup_run(backend)
        path = backend.write_node_output(
            run_id="2026-06-16-geartrain-dev-001",
            node_id="intake",
            node_type="agent",
            agent="lead",
            status="completed",
            output_text="Done.",
        )
        assert path.name == "intake.md"

    def test_read_node_output_raises_when_missing(
        self, backend: FileStateBackend
    ):
        self._setup_run(backend)
        with pytest.raises(FileNotFoundError):
            backend.read_node_output(
                "2026-06-16-geartrain-dev-001", "nonexistent"
            )

    def test_node_output_body(self, backend: FileStateBackend):
        self._setup_run(backend)
        backend.write_node_output(
            run_id="2026-06-16-geartrain-dev-001",
            node_id="intake",
            node_type="agent",
            agent="lead",
            status="completed",
            output_text="The plan is ready.",
            node_number=1,
        )
        text = (
            backend.state_path
            / "runs"
            / "2026-06-16-geartrain-dev-001"
            / "01-intake.md"
        ).read_text()
        assert "# Node: intake" in text
        assert "**Agent**: lead" in text
        assert "## Output" in text
        assert "The plan is ready." in text


# --- Run ID generation tests ------------------------------------------------


class TestGenerateRunId:
    """Incremental run ID generation."""

    def test_generates_base_id(self, tmp_path: Path):
        rid = generate_run_id("geartrain-dev", state_path=tmp_path)
        assert rid.endswith("-geartrain-dev-001")
        parts = rid.split("-")
        assert len(parts) >= 4  # date parts + workflow + seq

    def test_increments_sequence(self, tmp_path: Path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        (runs_dir / "2026-06-16-geartrain-dev-001").mkdir()
        (runs_dir / "2026-06-16-geartrain-dev-002").mkdir()

        rid = generate_run_id("geartrain-dev", state_path=tmp_path)
        assert rid.endswith("-geartrain-dev-003")

    def test_ignores_other_workflows(self, tmp_path: Path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        (runs_dir / "2026-06-16-other-flow-005").mkdir()

        rid = generate_run_id("geartrain-dev", state_path=tmp_path)
        assert rid.endswith("-geartrain-dev-001")

    def test_no_state_path_returns_001(self):
        rid = generate_run_id("geartrain-dev")
        assert rid.endswith("-geartrain-dev-001")


# --- Factory function tests -------------------------------------------------


class TestCreateStateBackend:
    """Factory function from EngineConfig."""

    def test_creates_backend_from_config(self, tmp_path: Path):
        """create_state_backend reads state.path from EngineConfig."""
        from geartrain.engine.config import EngineConfig

        config = EngineConfig(
            name="test-engine",
            workspace={"path": "workspace.yaml"},
            llm={"default": "anthropic"},
            state={"backend": "files", "path": str(tmp_path / "state")},
        )
        be = create_state_backend(config)
        assert isinstance(be, FileStateBackend)
        assert be.state_path == tmp_path / "state"


# --- State directory creation -----------------------------------------------


class TestStateDirectoryCreation:
    """State directories are created automatically."""

    def test_engine_state_creates_parent_dirs(self, tmp_path: Path):
        """write_engine_state creates the state directory if missing."""
        deep = tmp_path / "a" / "b" / "c"
        be = FileStateBackend(state_path=deep)
        be.write_engine_state(
            engine_name="test", status="started", workspace_name="w"
        )
        assert (deep / "engine.md").exists()

    def test_create_run_creates_nested_dirs(self, tmp_path: Path):
        """create_run creates runs/ and the run subdirectory."""
        be = FileStateBackend(state_path=tmp_path)
        be.create_run(run_id="test-run", workflow_name="wf")
        assert (tmp_path / "runs" / "test-run" / "run.md").exists()
