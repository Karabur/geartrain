"""Tests for P2-04/P2-05: direct agent CLI command and agent runner coverage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from geartrain.agents.cli_runner import CliAgentRunner
from geartrain.agents.factory import AgentFactory
from geartrain.cli import main
from geartrain.engine.app import EngineApp
from geartrain.engine.config import AgentDefinition, CliAgentConfig, LangchainAgentConfig
from geartrain.engine.service import create_app

ROOT = Path(__file__).parent.parent


def _make_agent(name: str = "echo-agent", command: str = "cat") -> AgentDefinition:
    return AgentDefinition(
        schema_version=1,
        name=name,
        config=CliAgentConfig(
            type="cli",
            command=command,
            timeout_seconds=10,
            work_folder="work",
            sandbox="workspace-write",
            credential="none",
        ),
        system_prompt="Test agent.",
    )


@pytest.fixture
def engine_app():
    app = EngineApp(
        workspace_path=ROOT / ".geartrain" / "workspace.yaml",
        engine_path=ROOT / ".geartrain" / "engines" / "local.engine.yaml",
    )
    app.agents["echo-agent"] = _make_agent()
    return app


@pytest.fixture
def client(engine_app):
    return TestClient(create_app(engine_app))


class TestAgentRunEndpoint:
    def test_known_agent_returns_output(self, client):
        resp = client.post("/agents/echo-agent/run", json={"task": "do something"})
        assert resp.status_code == 200
        data = resp.json()
        assert "output" in data
        assert "do something" in data["output"]

    def test_output_contains_prompt_sections(self, client):
        resp = client.post("/agents/echo-agent/run", json={"task": "my unique task"})
        assert resp.status_code == 200
        assert "my unique task" in resp.json()["output"]

    def test_unknown_agent_returns_404(self, client):
        resp = client.post("/agents/nope/run", json={"task": "hi"})
        assert resp.status_code == 404
        assert "Unknown agent" in resp.json()["error"]

    def test_failed_agent_returns_500(self, engine_app):
        engine_app.agents["fail-agent"] = _make_agent(name="fail-agent", command="false")
        c = TestClient(create_app(engine_app))
        resp = c.post("/agents/fail-agent/run", json={"task": "fail"})
        assert resp.status_code == 500
        assert "error" in resp.json()

    def test_missing_body_uses_empty_task(self, client):
        resp = client.post("/agents/echo-agent/run")
        assert resp.status_code == 200

    def test_error_message_contains_exit_code(self, engine_app):
        engine_app.agents["fail-agent"] = _make_agent(name="fail-agent", command="false")
        c = TestClient(create_app(engine_app))
        resp = c.post("/agents/fail-agent/run", json={"task": "fail"})
        assert "exit 1" in resp.json()["error"]


class TestAgentFactory:
    def test_creates_cli_runner(self):
        runner = AgentFactory.create(_make_agent(), sandbox=None)
        assert isinstance(runner, CliAgentRunner)

    def test_creates_langchain_runner(self):
        from geartrain.agents.langchain_runner import LangchainAgentRunner

        agent = AgentDefinition(
            schema_version=1,
            name="lc-agent",
            config=LangchainAgentConfig(
                type="langchain",
                llm_provider="openai",
                llm_model="gpt-4",
            ),
            system_prompt="",
        )
        runner = AgentFactory.create(agent, sandbox=None)
        assert isinstance(runner, LangchainAgentRunner)

    def test_raises_value_error_for_unknown_type(self, monkeypatch):
        agent = _make_agent()
        monkeypatch.setattr(agent.config, "type", "unknown-type")
        with pytest.raises(ValueError, match="Unknown agent type"):
            AgentFactory.create(agent, sandbox=None)


class TestAgentCliCommand:
    def _mock_conn(self, status: int, body: dict) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status = status
        mock_resp.read.return_value = json.dumps(body).encode()
        conn = MagicMock()
        conn.getresponse.return_value = mock_resp
        return conn

    def test_prints_plain_text_on_success(self, capsys, monkeypatch):
        conn = self._mock_conn(200, {"output": "task done\n"})
        monkeypatch.setattr("http.client.HTTPConnection", lambda *a, **kw: conn)

        main(["agent", "lead", "show tasks"])

        assert "task done" in capsys.readouterr().out

    def test_no_json_wrapper_in_output(self, capsys, monkeypatch):
        conn = self._mock_conn(200, {"output": "plain result"})
        monkeypatch.setattr("http.client.HTTPConnection", lambda *a, **kw: conn)

        main(["agent", "lead", "show tasks"])

        out = capsys.readouterr().out
        assert "plain result" in out
        assert '"output"' not in out

    def test_unknown_agent_prints_error_and_exits(self, capsys, monkeypatch):
        conn = self._mock_conn(404, {"error": "Unknown agent: bad-agent"})
        monkeypatch.setattr("http.client.HTTPConnection", lambda *a, **kw: conn)

        with pytest.raises(SystemExit) as exc:
            main(["agent", "bad-agent", "do stuff"])

        assert exc.value.code == 1
        assert "Unknown agent" in capsys.readouterr().out

    def test_agent_error_prints_error_and_exits(self, capsys, monkeypatch):
        conn = self._mock_conn(500, {"error": "Agent command failed (exit 1): oops"})
        monkeypatch.setattr("http.client.HTTPConnection", lambda *a, **kw: conn)

        with pytest.raises(SystemExit) as exc:
            main(["agent", "lead", "do stuff"])

        assert exc.value.code == 1
        assert "Error" in capsys.readouterr().out

    def test_engine_not_running_exits_with_message(self, capsys, monkeypatch):
        conn = MagicMock()
        conn.request.side_effect = ConnectionRefusedError("refused")
        monkeypatch.setattr("http.client.HTTPConnection", lambda *a, **kw: conn)

        with pytest.raises(SystemExit) as exc:
            main(["agent", "lead", "hi"])

        assert exc.value.code == 1
        assert "not running" in capsys.readouterr().out
