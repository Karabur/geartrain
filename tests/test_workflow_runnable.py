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
from geartrain.workflows.engine import WorkflowRunError, WorkflowRunner
from geartrain.workflows.lock import WorkflowLock
from geartrain.workflows.start import run_workflow

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
        """Known workflow start endpoint returns a non-404 response.

        The engine anchors its state, logs, and work paths to the config
        location at load, so the endpoint never depends on the working
        directory and writes only inside the scaffold.
        """
        client = self._make_client(project_dir)
        resp = client.post("/workflows/geartrain-dev/start", json={"task": "do X"})
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
    """The generic run path writes run state and both log streams."""

    def test_run_writes_state_and_logs(self, project_dir: Path):
        from geartrain.engine.loader import load_workflow

        state_path = project_dir / ".geartrain" / "state"
        wf_path = project_dir / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml"
        wf = load_workflow(str(wf_path))
        backend = FileStateBackend(state_path)
        log_file = project_dir / ".geartrain" / "logs" / "geartrain-dev.md"

        result = run_workflow(
            workflow=wf,
            agents={
                "coder": MockAgentRunner("coder done"),
                "lead": MockAgentRunner("lead done"),
            },
            state_backend=backend,
            state_path=state_path,
            log_file=log_file,
            run_id="2026-06-17-geartrain-dev-001",
            task="implement feature X",
        )

        assert result["status"] == "completed"

        run_state = backend.read_run_state("2026-06-17-geartrain-dev-001")
        assert run_state["status"] == "completed"

        assert log_file.exists()
        assert "2026-06-17-geartrain-dev-001" in log_file.read_text()
        events_log = log_file.with_suffix(".events.jsonl")
        assert events_log.exists()
        assert "2026-06-17-geartrain-dev-001" in events_log.read_text()

    def test_run_does_not_touch_work_folder(self, project_dir: Path):
        """The generic run path never scans or mutates ``work/``."""
        from geartrain.engine.loader import load_workflow

        work_todo = project_dir / "work" / "todo"
        task = work_todo / "p1-01-my-task.md"
        task.write_text("---\nid: GT-TEST\n---\n# Task\n")

        state_path = project_dir / ".geartrain" / "state"
        wf_path = project_dir / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml"
        wf = load_workflow(str(wf_path))

        run_workflow(
            workflow=wf,
            agents={"coder": MockAgentRunner(), "lead": MockAgentRunner()},
            state_backend=FileStateBackend(state_path),
            state_path=state_path,
            log_file=project_dir / ".geartrain" / "logs" / "geartrain-dev.md",
            run_id="run-001",
        )

        # The task stays put; no todo -> in-progress move happens.
        assert task.exists()
        assert not (project_dir / "work" / "in-progress" / "p1-01-my-task.md").exists()


# ---------------------------------------------------------------------------
# Generic, config-driven start path
# ---------------------------------------------------------------------------


class TestGenericStart:
    """The engine starts any registered workflow by name, naming none in source."""

    def _runner_for(self, app):
        # Replace real agent runners with deterministic mocks so the start path
        # runs end to end without subprocesses.
        return lambda agent_def: MockAgentRunner(f"{agent_def.name} done")

    def test_start_runs_from_entry_node(self, isolated_engine):
        from geartrain.workflows.start import start_workflow

        result = start_workflow(
            isolated_engine,
            "sample-dev",
            task="implement feature X",
            build_runner=self._runner_for(isolated_engine),
        )
        assert result["status"] == "completed"
        # Entry node ran first; both nodes produced output.
        assert result["node_outputs"]["coder_output"] == "coder done"
        assert result["node_outputs"]["lead_output"] == "lead done"

    def test_task_seeds_trigger_task(self, isolated_engine):
        from geartrain.workflows.start import start_workflow

        seen: dict[str, str] = {}

        def build_runner(agent_def):
            def run(task, context):
                seen[agent_def.name] = task
                return f"{agent_def.name} ok"
            runner = MockAgentRunner()
            runner.run = run
            return runner

        start_workflow(
            isolated_engine,
            "sample-dev",
            task="do the thing",
            build_runner=build_runner,
        )
        # The entry node's task input resolves ${trigger.task} to the passed task.
        assert seen["coder"] == "do the thing"

    def test_second_named_workflow_runs_without_work_folder(self, isolated_engine, isolated_project):
        from geartrain.workflows.start import start_workflow

        # A pre-existing task must be left untouched by any workflow start.
        task = isolated_project / "work" / "todo" / "keepme.md"
        task.write_text("---\nid: T\n---\n# Keep\n")

        result = start_workflow(
            isolated_engine,
            "other-flow",
            build_runner=self._runner_for(isolated_engine),
        )
        assert result["status"] == "completed"
        assert result["workflow"] == "other-flow"
        assert task.exists()
        assert not (isolated_project / "work" / "in-progress" / "keepme.md").exists()

    def test_unknown_workflow_returns_error(self, isolated_engine):
        from geartrain.workflows.start import start_workflow

        result = start_workflow(
            isolated_engine,
            "no-such-flow",
            build_runner=self._runner_for(isolated_engine),
        )
        assert "error" in result

    def test_start_is_cwd_independent(self, isolated_engine, isolated_project, tmp_path, monkeypatch):
        from geartrain.workflows.start import start_workflow

        # Start from an unrelated cwd. Absolute path resolution must keep all
        # writes inside the scaffold, never the cwd.
        other = tmp_path / "elsewhere"
        other.mkdir()
        monkeypatch.chdir(other)

        result = start_workflow(
            isolated_engine,
            "sample-dev",
            build_runner=self._runner_for(isolated_engine),
        )
        assert result["status"] == "completed"

        run_id = result["run_id"]
        # State landed under the scaffold, not the cwd.
        assert (isolated_project / ".geartrain" / "state" / "runs" / run_id / "run.md").exists()
        assert not (other / ".geartrain").exists()


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
            [sys.executable, "-m", "geartrain.cli", "workflow", "start", "geartrain-dev"],
            capture_output=True,
            text=True,
        )
        assert "not running" in result.stdout.lower() or result.returncode != 0
