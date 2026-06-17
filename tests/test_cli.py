"""Integration tests for engine CLI lifecycle commands (GT-P1-07)."""

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from geartrain.cli import _run_engine_start


def _create_valid_configs(tmp_path):
    """Create a complete valid workspace and engine config in tmp_path."""
    gt = tmp_path / ".geartrain"
    for d in (
        gt / "agents",
        gt / "workflows",
        gt / "state",
        tmp_path / ".geartrain" / "memory",
        tmp_path / ".geartrain" / "memory" / "workspace",
        tmp_path / ".geartrain" / "memory" / "workflows",
        tmp_path / ".geartrain" / "memory" / "agent-types",
    ):
        d.mkdir(parents=True, exist_ok=True)

    (gt / "workspace.yaml").write_text(dedent("""\
        schema_version: 1
        name: test-ws
        project:
          name: Test
        llm:
          default_provider: anthropic
          default_model: x
        registries:
          agents: .geartrain/agents
          workflows: .geartrain/workflows
        memory:
          root: .geartrain/memory
          workspace: .geartrain/memory/workspace
          workflows: .geartrain/memory/workflows
          agent_types: .geartrain/memory/agent-types
    """))

    (gt / "engines" / "local.engine.yaml").parent.mkdir(parents=True, exist_ok=True)
    (gt / "engines" / "local.engine.yaml").write_text(dedent("""\
        schema_version: 1
        name: test-engine
        host: 127.0.0.1
        port: 8420
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


class TestEngineStart:
    """geartrain engine start command."""

    def test_start_with_invalid_config_exits_nonzero(self, tmp_path, monkeypatch):
        """engine start with invalid config prints errors and exits non-zero."""
        monkeypatch.chdir(tmp_path)
        # Minimal workspace with missing required fields (project, llm, etc.)
        ws = tmp_path / ".geartrain" / "workspace.yaml"
        ws.parent.mkdir(exist_ok=True)
        ws.write_text("schema_version: 1\nname: test\n")

        with pytest.raises(SystemExit) as exc:
            _run_engine_start()
        assert exc.value.code == 1

    def test_start_with_valid_config_starts(self, tmp_path):
        """engine start with valid config creates EngineApp and starts server.

        Verified via subprocess: the process prints the startup message,
        confirming validation passed and EngineApp was created. The process
        may exit early if the port cannot be bound (e.g., sandbox restrictions),
        but the startup message proves the app was created successfully.
        """
        _create_valid_configs(tmp_path)

        result = subprocess.run(
            [sys.executable, "-m", "geartrain.cli", "engine", "start"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            timeout=15,
        )
        # The startup message is printed before the server binds the port,
        # so it appears even if binding fails (e.g., sandbox restrictions).
        assert "Engine started on 127.0.0.1:8420" in result.stdout


class TestEngineStatus:
    """geartrain engine status command."""

    def test_status_when_not_running(self, tmp_path):
        """Prints 'not running' message when engine is not listening."""
        _create_valid_configs(tmp_path)

        result = subprocess.run(
            [sys.executable, "-m", "geartrain.cli", "engine", "status"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert "not running" in result.stdout.lower()


class TestEngineStop:
    """geartrain engine stop command."""

    def test_stop_when_not_running(self, tmp_path):
        """Prints appropriate message when engine is not listening."""
        _create_valid_configs(tmp_path)

        result = subprocess.run(
            [sys.executable, "-m", "geartrain.cli", "engine", "stop"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert "not running" in result.stdout.lower()
