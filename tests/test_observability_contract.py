"""Observability contract tests (GT-P7-06).

Locks the run/event/summary contracts before dogfooding. Seeds success,
waiting, failed, and memory-write-rejected runs, then asserts the JSONL event
shape, per-event-type required fields, the summary contract, and the query and
streaming APIs. Offline and deterministic.
"""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from geartrain.engine.app import EngineApp
from geartrain.engine.service import create_app
from geartrain.engine.observability import summarize_run
from geartrain.engine.state import FileStateBackend
from tests.observability_helpers import (
    seed_failed_run,
    seed_memory_rejected_run,
    seed_success_run,
    seed_waiting_run,
)

ROOT = Path(__file__).parent.parent

# Required fields per event type. New event types must be added here, which is
# the schema-drift tripwire: an unknown type fails the contract.
_EVENT_CONTRACT = {
    "node_start": {"node_id", "node_type"},
    "node_complete": {"node_id", "status"},
    "run_failed": {"node_id", "error"},
    "tool_call": {"name", "kind", "status", "duration_ms"},
    "memory_read": {"source_run", "source_agent", "query"},
    "memory_write": {"scope", "system", "path", "source_run", "source_agent"},
    "memory_write_rejected": {"scope", "reason", "source_run"},
    "checkpoint_created": {"checkpoint_id"},
    "checkpoint_resolved": {"checkpoint_id"},
    "integration_error": {"service", "action", "error"},
}

_SUMMARY_KEYS = {
    "run_id",
    "workflow",
    "status",
    "started_at",
    "ended_at",
    "duration_ms",
    "node_count",
    "node_timings",
    "tool_calls",
    "memory",
    "event_count",
    "terminal_error",
}

_SEEDERS = {
    "success": (seed_success_run, "run-ok", "completed"),
    "waiting": (seed_waiting_run, "run-waiting", "waiting"),
    "failed": (seed_failed_run, "run-failed", "failed"),
    "rejected": (seed_memory_rejected_run, "run-rejected", "completed"),
}


def _seed(kind: str, tmp_path: Path):
    seeder, run_id, status = _SEEDERS[kind]
    backend = seeder(tmp_path, run_id)
    return backend, run_id, status


@pytest.mark.parametrize("kind", list(_SEEDERS))
def test_event_jsonl_shape(kind, tmp_path):
    """Every event line is valid JSON with seq/timestamp/type and known fields."""
    backend, run_id, _ = _seed(kind, tmp_path)
    events_file = backend.state_path / "runs" / run_id / "events.jsonl"
    if not events_file.exists():
        pytest.skip("no events for this run")

    prev_seq = 0
    for line in events_file.read_text().splitlines():
        ev = json.loads(line)  # raises on malformed JSONL
        assert {"seq", "timestamp", "type"} <= set(ev)
        assert ev["seq"] == prev_seq + 1  # monotonic, gapless
        prev_seq = ev["seq"]

        etype = ev["type"]
        assert etype in _EVENT_CONTRACT, f"undocumented event type: {etype}"
        missing = _EVENT_CONTRACT[etype] - set(ev)
        assert not missing, f"{etype} missing {missing}"


@pytest.mark.parametrize("kind", list(_SEEDERS))
def test_summary_contract(kind, tmp_path):
    """Every run kind produces the full summary contract with the right status."""
    backend, run_id, status = _seed(kind, tmp_path)
    summary = summarize_run(backend, run_id)
    assert set(summary) == _SUMMARY_KEYS
    assert summary["status"] == status
    if status == "failed":
        assert summary["terminal_error"] is not None


@pytest.mark.parametrize("kind", list(_SEEDERS))
def test_query_api_contract(kind, tmp_path):
    """The query API serves each run kind without error and with run fields."""
    backend, run_id, status = _seed(kind, tmp_path)
    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    app.state_backend = backend
    client = TestClient(create_app(app))

    assert run_id in {r["run_id"] for r in client.get("/api/runs").json()["runs"]}
    assert client.get(f"/api/runs/{run_id}").json()["status"] == status
    assert client.get(f"/api/runs/{run_id}/events").status_code == 200
    assert client.get(f"/api/runs/{run_id}/attempts").status_code == 200
    assert client.get(f"/api/runs/{run_id}/summary").json()["status"] == status


def test_waiting_run_exposes_checkpoint(tmp_path):
    backend, run_id, _ = _seed("waiting", tmp_path)
    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    app.state_backend = backend
    client = TestClient(create_app(app))
    cps = client.get("/api/checkpoints?status=waiting").json()["checkpoints"]
    assert any(c["run_id"] == run_id for c in cps)


@pytest.mark.parametrize("kind", list(_SEEDERS))
def test_stream_terminates(kind, tmp_path):
    """Streaming any seeded run yields its events and a terminal/closing frame."""
    backend, run_id, status = _seed(kind, tmp_path)
    # Mark waiting runs terminal so the stream closes deterministically.
    if status not in ("completed", "failed"):
        backend.update_run_status(run_id, "completed")
    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    app.state_backend = backend
    client = TestClient(create_app(app))
    with client.stream("GET", f"/api/runs/{run_id}/events/stream") as resp:
        body = "".join(resp.iter_text())
    assert "event: end" in body
