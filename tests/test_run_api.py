"""Tests for the run query API endpoints (GT-P7-01)."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from geartrain.engine.app import EngineApp
from geartrain.engine.service import create_app
from geartrain.engine.state import FileStateBackend
from geartrain.memory.markdown import MarkdownMemoryStore
from tests.observability_helpers import (
    seed_failed_run,
    seed_success_run,
    seed_waiting_run,
)

ROOT = Path(__file__).parent.parent


def _app_for(tmp_path: Path) -> EngineApp:
    """Build an EngineApp whose state and memory point at a temp dir."""
    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    app.state_backend = FileStateBackend(tmp_path / "state")
    app.memory_store = MarkdownMemoryStore(str(tmp_path / "memory"))
    return app


def _client(app: EngineApp) -> TestClient:
    return TestClient(create_app(app))


class TestRunListing:
    def test_list_runs(self, tmp_path):
        seed_success_run(tmp_path, "run-ok")
        client = _client(_app_for(tmp_path))
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        runs = resp.json()["runs"]
        assert {r["run_id"] for r in runs} == {"run-ok"}
        assert runs[0]["status"] == "completed"

    def test_get_run(self, tmp_path):
        seed_success_run(tmp_path, "run-ok")
        client = _client(_app_for(tmp_path))
        resp = client.get("/api/runs/run-ok")
        assert resp.status_code == 200
        assert resp.json()["workflow"] == "obs-wf"

    def test_unknown_run_404(self, tmp_path):
        client = _client(_app_for(tmp_path))
        assert client.get("/api/runs/nope").status_code == 404


class TestRunEventsAndNodes:
    def test_events(self, tmp_path):
        seed_success_run(tmp_path, "run-ok")
        client = _client(_app_for(tmp_path))
        events = client.get("/api/runs/run-ok/events").json()["events"]
        types = [e["type"] for e in events]
        assert types[0] == "node_start"
        assert "tool_call" in types
        assert "memory_write" in types

    def test_nodes(self, tmp_path):
        seed_success_run(tmp_path, "run-ok")
        client = _client(_app_for(tmp_path))
        nodes = client.get("/api/runs/run-ok/nodes").json()["nodes"]
        assert [n["node_id"] for n in nodes] == ["run_coder", "run_lead"]

    def test_attempts(self, tmp_path):
        seed_success_run(tmp_path, "run-ok")
        client = _client(_app_for(tmp_path))
        attempts = client.get("/api/runs/run-ok/attempts").json()["attempts"]
        ids = [a["attempt_id"] for a in attempts]
        assert ids == ["run_coder#1", "run_lead#1"]
        assert all(a["status"] == "ok" for a in attempts)


class TestWorkflowQuery:
    def test_list_workflows(self, tmp_path):
        client = _client(_app_for(tmp_path))
        names = client.get("/api/workflows").json()["workflows"]
        assert "geartrain-dev" in names

    def test_get_workflow(self, tmp_path):
        client = _client(_app_for(tmp_path))
        resp = client.get("/api/workflows/geartrain-dev")
        assert resp.status_code == 200
        assert resp.json()["name"] == "geartrain-dev"

    def test_unknown_workflow_404(self, tmp_path):
        client = _client(_app_for(tmp_path))
        assert client.get("/api/workflows/nope").status_code == 404


class TestCheckpoints:
    def test_list_waiting_checkpoints(self, tmp_path):
        seed_waiting_run(tmp_path, "run-waiting")
        client = _client(_app_for(tmp_path))
        cps = client.get("/api/checkpoints?status=waiting").json()["checkpoints"]
        assert len(cps) == 1
        assert cps[0]["checkpoint_id"] == "approve-cp"

    def test_respond_records_response(self, tmp_path):
        seed_waiting_run(tmp_path, "run-waiting")
        app = _app_for(tmp_path)
        client = _client(app)
        resp = client.post(
            "/api/checkpoints/approve-cp/respond", json={"response": "approved"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["checkpoint"]["status"] == "responded"
        assert body["checkpoint"]["response"] == "approved"
        # The persisted checkpoint reflects the response.
        cp = app.state_backend.read_checkpoint("run-waiting", "approve-cp")
        assert cp["status"] == "responded"

    def test_respond_unknown_404(self, tmp_path):
        client = _client(_app_for(tmp_path))
        resp = client.post("/api/checkpoints/ghost/respond", json={"response": "x"})
        assert resp.status_code == 404


class TestMemoryQuery:
    def test_memory_overview(self, tmp_path):
        seed_success_run(tmp_path, "run-ok")
        client = _client(_app_for(tmp_path))
        overview = client.get("/api/memory").json()["memory"]
        workspace = [o for o in overview if o["scope"] == "workspace"]
        assert workspace and workspace[0]["count"] >= 1

    def test_memory_scope_entries(self, tmp_path):
        seed_success_run(tmp_path, "run-ok")
        client = _client(_app_for(tmp_path))
        data = client.get("/api/memory/workspace").json()
        assert data["scope"] == "workspace"
        assert len(data["entries"]) >= 1
        assert data["entries"][0]["source_run"] == "run-ok"

    def test_unknown_scope_404(self, tmp_path):
        client = _client(_app_for(tmp_path))
        assert client.get("/api/memory/bogus").status_code == 404
