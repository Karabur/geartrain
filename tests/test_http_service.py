"""Tests for the engine HTTP service (GT-P1-06)."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from geartrain.engine.app import EngineApp
from geartrain.engine.service import create_app

ROOT = Path(__file__).parent.parent


@pytest.fixture
def engine_app(tmp_path):
    """Create an EngineApp with the project scaffold configs."""
    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    return app


@pytest.fixture
def client(engine_app):
    """Create a TestClient bound to the engine app."""
    return TestClient(create_app(engine_app))


class TestHealth:
    """GET /health endpoint."""

    def test_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestStatus:
    """GET /status endpoint."""

    def test_returns_workspace_info(self, client, engine_app):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace"] == engine_app.workspace.name
        assert data["engine"] == engine_app.engine.name
        assert data["running"] is False

    def test_returns_agent_list(self, client):
        resp = client.get("/status")
        data = resp.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_returns_workflow_list(self, client):
        resp = client.get("/status")
        data = resp.json()
        assert "workflows" in data
        assert isinstance(data["workflows"], list)


class TestAgentRun:
    """POST /agents/{name}/run endpoint."""

    def test_unknown_agent_returns_404(self, client):
        resp = client.post("/agents/nonexistent/run")
        assert resp.status_code == 404
        assert "Unknown agent" in resp.json()["error"]

    def test_known_agent_run_fails_without_codex(self, client):
        resp = client.post("/agents/coder/run", json={"task": "test"})
        assert resp.status_code == 500
        assert "error" in resp.json()


class TestWorkflowStart:
    """POST /workflows/{name}/start endpoint."""

    def test_unknown_workflow_returns_404(self, client):
        resp = client.post("/workflows/nonexistent/start")
        assert resp.status_code == 404
        assert "Unknown workflow" in resp.json()["error"]

    def test_known_workflow_start_responds(self, isolated_engine):
        """Known workflow start endpoint returns a non-404 response.

        The engine resolves its state, logs, and work paths to absolute at load,
        so the start endpoint never depends on the working directory. The
        ``isolated_engine`` fixture points those paths at a temp scaffold, so the
        run writes there instead of the real repo.
        """
        client = TestClient(create_app(isolated_engine))
        resp = client.post("/workflows/sample-dev/start", json={"task": "do X"})
        assert resp.status_code != 404


class TestWorkflowStatus:
    """GET /workflows/{name}/status endpoint."""

    def test_unknown_workflow_returns_404(self, client):
        resp = client.get("/workflows/nonexistent/status")
        assert resp.status_code == 404
        assert "Unknown workflow" in resp.json()["error"]

    def test_known_workflow_returns_idle(self, client):
        resp = client.get("/workflows/geartrain-dev/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_name"] == "geartrain-dev"


class TestEngineStop:
    """POST /engine/stop endpoint."""

    def test_stops_engine(self, client, engine_app):
        engine_app.start()
        assert engine_app.running is True

        resp = client.post("/engine/stop")
        assert resp.status_code == 200
        assert resp.json() == {"status": "stopped"}
        assert engine_app.running is False
