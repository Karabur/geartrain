"""End-to-end smoke tests for the first runnable GearTrain loop (GT-P3-09)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from starlette.testclient import TestClient

from geartrain.engine.app import EngineApp
from geartrain.engine.service import create_app
from geartrain.engine.state import FileStateBackend
from geartrain.work.tasks import move_to_in_progress
from geartrain.workflows.engine import WorkflowRunError, WorkflowRunner
from geartrain.workflows.factory import WorkflowFactory
from geartrain.workflows.geartrain_dev import run_geartrain_dev
from geartrain.workflows.lock import WorkflowLock

ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Fixtures: minimal project tree
# ---------------------------------------------------------------------------


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Build a minimal .geartrain/ project scaffold in tmp_path."""
    gt = tmp_path / ".geartrain"
    gt.mkdir()

    # Workspace
    (gt / "workspace.yaml").write_text(dedent(f"""\
        schema_version: 1
        name: test-ws
        description: test workspace
        project:
          name: TestProject
          repo_root: "."
        llm:
          default_provider: anthropic
          default_model: claude-sonnet-4
        registries:
          agents: .geartrain/agents
          workflows: .geartrain/workflows
        memory:
          root: .geartrain/memory
          workspace: .geartrain/memory/workspace
          workflows: .geartrain/memory/workflows
          agent_types: .geartrain/memory/agent-types
    """))

    # Engine
    (gt / "engines").mkdir()
    (gt / "engines" / "local.engine.yaml").write_text(dedent(f"""\
        schema_version: 1
        name: local-test
        description: test engine
        workspace:
          path: .geartrain/workspace.yaml
        llm:
          default: anthropic
          providers:
            anthropic:
              api_key_env: ANTHROPIC_API_KEY
        state:
          backend: files
          path: .geartrain/state
    """))

    # Agents
    (gt / "agents").mkdir()
    (gt / "agents" / "coder.agent.yaml").write_text(dedent("""\
        schema_version: 1
        name: coder
        description: coder agent
        type: cli
        cli:
          command: echo
          credential: test
        system_prompt: "You are coder."
        memory:
          read: []
    """))
    (gt / "agents" / "lead.agent.yaml").write_text(dedent("""\
        schema_version: 1
        name: lead
        description: lead agent
        type: cli
        cli:
          command: echo
          credential: test
        system_prompt: "You are lead."
        memory:
          read: []
    """))

    # Workflow
    (gt / "workflows").mkdir()
    (gt / "workflows" / "geartrain-dev.workflow.yaml").write_text(dedent("""\
        schema_version: 1
        name: geartrain-dev
        description: dev workflow
        trigger:
          type: manual
        agents:
          coder: coder
          lead: lead
        graph:
          entry: run_coder
          nodes:
            run_coder:
              type: agent
              agent: coder
              inputs:
                task: "${trigger.task}"
              output_key: coder_output
              transitions:
                default: run_lead
            run_lead:
              type: agent
              agent: lead
              inputs:
                task: "${nodes.coder_output.output}"
              output_key: lead_output
              transitions:
                default: end
    """))

    # Memory dirs (required by workspace validation)
    for mem_dir in ("memory", "memory/workspace", "memory/workflows", "memory/agent-types"):
        (gt / mem_dir).mkdir(parents=True, exist_ok=True)

    # State dirs
    (gt / "state").mkdir()
    (gt / "logs").mkdir()

    # Work dirs
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "todo").mkdir()
    (tmp_path / "work" / "in-progress").mkdir()
    (tmp_path / "work" / "done").mkdir()

    return tmp_path


class MockAgentRunner:
    def __init__(self, response: str = "mock output") -> None:
        self.response = response

    def run(self, task: str, context: dict) -> str:
        return self.response


# ---------------------------------------------------------------------------
# Engine startup smoke tests
# ---------------------------------------------------------------------------


class TestEngineStartup:
    def test_engine_loads_with_valid_config(self, project_dir: Path):
        gt = project_dir / ".geartrain"
        app = EngineApp(
            workspace_path=gt / "workspace.yaml",
            engine_path=gt / "engines" / "local.engine.yaml",
        )
        app.load_registries()
        assert "coder" in app.agents
        assert "lead" in app.agents
        assert "geartrain-dev" in app.workflows

    def test_engine_loads_real_scaffold(self):
        app = EngineApp(
            workspace_path=ROOT / ".geartrain" / "workspace.yaml",
            engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
        )
        app.load_registries()
        assert "coder" in app.agents
        assert "geartrain-dev" in app.workflows


# ---------------------------------------------------------------------------
# HTTP workflow start smoke tests
# ---------------------------------------------------------------------------


class TestWorkflowStartEndpoint:
    def _make_client(self, project_dir: Path) -> TestClient:
        gt = project_dir / ".geartrain"
        app = EngineApp(
            workspace_path=gt / "workspace.yaml",
            engine_path=gt / "engines" / "local.engine.yaml",
        )
        app.load_registries()
        return TestClient(create_app(app))

    def test_unknown_workflow_returns_404(self, project_dir: Path):
        client = self._make_client(project_dir)
        resp = client.post("/workflows/nonexistent/start")
        assert resp.status_code == 404

    def test_workflow_start_not_404(self, project_dir: Path):
        """Known workflow start endpoint returns a non-404 response."""
        client = self._make_client(project_dir)
        resp = client.post("/workflows/geartrain-dev/start")
        assert resp.status_code != 404


# ---------------------------------------------------------------------------
# Workflow lock: already running returns status
# ---------------------------------------------------------------------------


class TestWorkflowLockSmoke:
    def test_starting_locked_workflow_raises(self, project_dir: Path):
        from geartrain.engine.loader import load_workflow
        from geartrain.engine.state import FileStateBackend

        state_path = project_dir / ".geartrain" / "state"
        wf_path = project_dir / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml"
        wf = load_workflow(str(wf_path))
        backend = FileStateBackend(state_path)

        lock = WorkflowLock(state_path, "geartrain-dev")
        lock.acquire("existing-run")

        runner = WorkflowRunner(
            workflow=wf,
            agents={"coder": MockAgentRunner(), "lead": MockAgentRunner()},
            state_backend=backend,
            state_path=state_path,
            work_dir=project_dir / "work",
        )
        with pytest.raises(WorkflowRunError, match="already running"):
            runner.run("new-run")

        # Lock is still held by the original run
        assert lock.is_locked()
        assert lock.current_run_id() == "existing-run"


# ---------------------------------------------------------------------------
# State and log file writes
# ---------------------------------------------------------------------------


class TestStateAndLogWrites:
    def test_run_writes_state_files(self, project_dir: Path):
        from geartrain.engine.loader import load_workflow
        from geartrain.engine.state import FileStateBackend

        state_path = project_dir / ".geartrain" / "state"
        wf_path = project_dir / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml"
        wf = load_workflow(str(wf_path))
        backend = FileStateBackend(state_path)
        work_dir = project_dir / "work"
        log_file = project_dir / ".geartrain" / "logs" / "geartrain-dev.md"

        # Create a task in todo/
        task = work_dir / "todo" / "p1-01-my-task.md"
        task.write_text("---\nid: GT-TEST\n---\n# Task\n\nDo the thing.\n")

        result = run_geartrain_dev(
            workflow=wf,
            agents={"coder": MockAgentRunner("coder done"), "lead": MockAgentRunner("lead done")},
            state_backend=backend,
            state_path=state_path,
            work_dir=work_dir,
            run_id="2026-06-17-geartrain-dev-001",
            log_file=log_file,
        )

        assert result["status"] == "completed"

        # run.md written
        run_state = backend.read_run_state("2026-06-17-geartrain-dev-001")
        assert run_state["status"] == "completed"

        # Log line written
        assert log_file.exists()
        log_text = log_file.read_text()
        assert "2026-06-17-geartrain-dev-001" in log_text
        assert "p1-01-my-task.md" in log_text

        # Task moved to in-progress
        assert (work_dir / "in-progress" / "p1-01-my-task.md").exists()
        assert not task.exists()

    def test_no_task_returns_no_tasks_status(self, project_dir: Path):
        from geartrain.engine.loader import load_workflow
        from geartrain.engine.state import FileStateBackend

        state_path = project_dir / ".geartrain" / "state"
        wf_path = project_dir / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml"
        wf = load_workflow(str(wf_path))
        backend = FileStateBackend(state_path)

        result = run_geartrain_dev(
            workflow=wf,
            agents={"coder": MockAgentRunner(), "lead": MockAgentRunner()},
            state_backend=backend,
            state_path=state_path,
            work_dir=project_dir / "work",
            run_id="run-001",
            log_file=project_dir / ".geartrain" / "logs" / "geartrain-dev.md",
        )
        assert result["status"] == "no_tasks"


# ---------------------------------------------------------------------------
# Direct lead call via CLI
# ---------------------------------------------------------------------------


class TestDirectLeadCallSmoke:
    def test_geartrain_agent_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "geartrain.cli", "agent", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "agent_name" in result.stdout or "agent" in result.stdout

    def test_geartrain_workflow_start_not_running(self, tmp_path: Path, monkeypatch):
        """geartrain workflow start prints 'not running' when engine is down."""
        monkeypatch.chdir(tmp_path)
        result = subprocess.run(
            [sys.executable, "-m", "geartrain.cli", "workflow", "start"],
            capture_output=True,
            text=True,
        )
        assert "not running" in result.stdout.lower() or result.returncode != 0
