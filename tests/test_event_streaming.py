"""Tests for run event streaming (GT-P7-02)."""

import json
import threading
import time
from pathlib import Path

from starlette.testclient import TestClient

from geartrain.engine.app import EngineApp
from geartrain.engine.service import create_app
from geartrain.engine.state import FileStateBackend
from tests.observability_helpers import seed_success_run

ROOT = Path(__file__).parent.parent


def _app_for(tmp_path: Path) -> EngineApp:
    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    app.state_backend = FileStateBackend(tmp_path / "state")
    return app


def _parse_sse(text: str) -> list[dict]:
    """Pull the JSON ``data:`` payloads out of an SSE stream body."""
    out = []
    for line in text.splitlines():
        if line.startswith("data:"):
            out.append(json.loads(line[len("data:") :].strip()))
    return out


def test_seeded_run_streams_ordered_events(tmp_path):
    """A completed run streams all its events in order, then ends."""
    seed_success_run(tmp_path, "run-ok")
    client = TestClient(create_app(_app_for(tmp_path)))

    with client.stream("GET", "/api/runs/run-ok/events/stream") as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    payloads = _parse_sse(body)
    # Ordered by sequence, ending with the terminal marker.
    seqs = [p["seq"] for p in payloads if "seq" in p]
    assert seqs == sorted(seqs)
    assert payloads[0]["type"] == "node_start"
    assert payloads[-1] == {"run_id": "run-ok"}


def test_unknown_run_404(tmp_path):
    client = TestClient(create_app(_app_for(tmp_path)))
    assert client.get("/api/runs/ghost/events/stream").status_code == 404


def test_live_appended_events_are_delivered(tmp_path):
    """Events appended while a run is in progress reach a connected client."""
    backend = FileStateBackend(tmp_path / "state")
    backend.create_run("run-live", "obs-wf")
    backend.append_event("run-live", "node_start", {"node_id": "a"})

    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    app.state_backend = backend
    client = TestClient(create_app(app))

    def _drive():
        # Append a second event, then finish the run so the stream closes.
        time.sleep(0.2)
        backend.append_event("run-live", "tool_call", {"node_id": "a", "name": "file_read", "status": "ok"})
        time.sleep(0.2)
        backend.update_run_status("run-live", "completed")

    worker = threading.Thread(target=_drive)
    worker.start()
    with client.stream("GET", "/api/runs/run-live/events/stream") as resp:
        body = "".join(resp.iter_text())
    worker.join()

    payloads = _parse_sse(body)
    types = [p.get("type") for p in payloads if "type" in p]
    assert "node_start" in types
    assert "tool_call" in types  # delivered after the stream opened
    assert payloads[-1] == {"run_id": "run-live"}
