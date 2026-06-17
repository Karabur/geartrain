"""Tests for config validation (GT-P1-04)."""

from pathlib import Path
from textwrap import dedent

import pytest

from geartrain.engine.validator import (
    Diagnostic,
    format_diagnostics,
    validate_all,
    validate_agent,
    validate_engine,
    validate_workflow,
    validate_workspace,
)

ROOT = Path(__file__).parent.parent


# --- Shape validation (errors from Pydantic) --------------------------------


class TestShapeValidation:
    """Loader errors surface as shape diagnostics."""

    def test_missing_workspace_file(self, tmp_path):
        diags = validate_workspace(tmp_path / "nonexistent.yaml")
        assert len(diags) == 1
        assert diags[0].sev == "error"
        assert "FileNotFoundError" in diags[0].message

    def test_bad_schema_version(self, tmp_path):
        f = tmp_path / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 99
            name: test-ws
            project:
              name: Test
            llm:
              default_provider: anthropic
              default_model: x
            registries:
              agents: .
              workflows: .
            memory:
              root: .
              workspace: .
              workflows: .
              agent_types: .
        """))
        diags = validate_workspace(f)
        assert len(diags) == 1
        assert diags[0].sev == "error"
        assert "schema_version" in diags[0].message

    def test_bad_name(self, tmp_path):
        f = tmp_path / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: Invalid_Name
            project:
              name: Test
            llm:
              default_provider: anthropic
              default_model: x
            registries:
              agents: .
              workflows: .
            memory:
              root: .
              workspace: .
              workflows: .
              agent_types: .
        """))
        diags = validate_workspace(f)
        assert len(diags) == 1
        assert diags[0].sev == "error"

    def test_unknown_field(self, tmp_path):
        f = tmp_path / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-ws
            unknown_field: true
            project:
              name: Test
            llm:
              default_provider: anthropic
              default_model: x
            registries:
              agents: .
              workflows: .
            memory:
              root: .
              workspace: .
              workflows: .
              agent_types: .
        """))
        diags = validate_workspace(f)
        assert len(diags) == 1
        assert diags[0].sev == "error"
        assert "unknown_field" in diags[0].message


# --- Reference validation ---------------------------------------------------


class TestWorkspaceReferences:
    """Workspace registry and memory paths must exist."""

    def test_missing_registry_path(self, tmp_path):
        """Workspace with a missing workflows registry directory."""
        gt = tmp_path / ".geartrain"
        gt.mkdir()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        f = gt / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-ws
            project:
              name: Test
            llm:
              default_provider: anthropic
              default_model: x
            registries:
              agents: agents
              workflows: nonexistent_workflows
            memory:
              root: mem
              workspace: mem/ws
              workflows: mem/wf
              agent_types: mem/at
        """))
        # Create memory dirs so only workflows registry is missing
        for d in ("mem", "mem/ws", "mem/wf", "mem/at"):
            (tmp_path / d).mkdir()
        diags = validate_workspace(f)
        errors = [d for d in diags if d.sev == "error"]
        assert any("workflows" in d.fps for d in errors)

    def test_missing_memory_path(self, tmp_path):
        """Workspace with missing memory subdirectories."""
        gt = tmp_path / ".geartrain"
        gt.mkdir()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        workflows_dir = tmp_path / "workflows"
        workflows_dir.mkdir()
        f = gt / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-ws
            project:
              name: Test
            llm:
              default_provider: anthropic
              default_model: x
            registries:
              agents: agents
              workflows: workflows
            memory:
              root: mem
              workspace: mem/ws
              workflows: mem/wf
              agent_types: mem/at
        """))
        # Create only root memory dir
        (tmp_path / "mem").mkdir()
        diags = validate_workspace(f)
        errors = [d for d in diags if d.sev == "error"]
        missing_fields = [d.fps for d in errors]
        assert any("memory.workspace" in f_ for f_ in missing_fields)


class TestEngineReferences:
    """Engine workspace path and state path checks."""

    def test_missing_workspace_path(self, tmp_path):
        engine_f = tmp_path / "engine.yaml"
        engine_f.write_text(dedent("""\
            schema_version: 1
            name: test-engine
            workspace:
              path: nonexistent/workspace.yaml
            llm:
              default: anthropic
            state:
              backend: files
              path: state
        """))
        from geartrain.engine.config import WorkspaceConfig
        # Pass a dummy workspace — the engine check is about its own refs
        dummy_ws = WorkspaceConfig(
            name="dummy",
            project={"name": "X"},
            llm={"default_provider": "a", "default_model": "x"},
            registries={"agents": ".", "workflows": "."},
            memory={"root": ".", "workspace": ".", "workflows": ".", "agent_types": "."},
        )
        diags = validate_engine(engine_f, workspace=dummy_ws, repo_root=tmp_path)
        assert any("workspace.path" in d.fps for d in diags)

    def test_state_path_not_writable(self, tmp_path):
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state_dir.chmod(0o000)
        try:
            engine_f = tmp_path / "engine.yaml"
            engine_f.write_text(dedent("""\
                schema_version: 1
                name: test-engine
                workspace:
                  path: ws.yaml
                llm:
                  default: anthropic
                state:
                  backend: files
                  path: state
            """))
            ws_f = tmp_path / "ws.yaml"
            ws_f.write_text(dedent("""\
                schema_version: 1
                name: dummy
                project:
                  name: X
                llm:
                  default_provider: a
                  default_model: x
                registries:
                  agents: .
                  workflows: .
                memory:
                  root: .
                  workspace: .
                  workflows: .
                  agent_types: .
            """))
            from geartrain.engine.loader import load_workspace
            ws = load_workspace(str(ws_f))
            diags = validate_engine(engine_f, workspace=ws, repo_root=tmp_path)
            assert any("state.path" in d.fps for d in diags)
        finally:
            state_dir.chmod(0o755)


class TestWorkflowReferences:
    """Workflow agent references must exist in registry."""

    def _make_workspace(self, tmp_path) -> "WorkspaceConfig":
        """Create a minimal workspace with agents/workflows dirs."""
        from geartrain.engine.loader import load_workspace
        gt = tmp_path / ".geartrain"
        gt.mkdir()
        (tmp_path / "agents").mkdir()
        (tmp_path / "workflows").mkdir()
        f = gt / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-ws
            project:
              name: Test
            llm:
              default_provider: anthropic
              default_model: x
            registries:
              agents: agents
              workflows: workflows
            memory:
              root: mem
              workspace: mem/ws
              workflows: mem/wf
              agent_types: mem/at
        """))
        return load_workspace(str(f))

    def test_missing_agent_reference(self, tmp_path):
        ws = self._make_workspace(tmp_path)
        wf = tmp_path / "workflows" / "test.workflow.yaml"
        wf.write_text(dedent("""\
            schema_version: 1
            name: test-wf
            trigger:
              type: manual
            agents:
              lead: nonexistent_agent
            graph:
              entry: start
              nodes:
                start:
                  type: agent
                  agent: nonexistent_agent
        """))
        diags = validate_workflow(wf, ws, agents={})
        errors = [d for d in diags if d.sev == "error"]
        assert any("nonexistent_agent" in d.message for d in errors)

    def test_graph_entry_not_in_nodes(self, tmp_path):
        ws = self._make_workspace(tmp_path)
        wf = tmp_path / "workflows" / "test.workflow.yaml"
        wf.write_text(dedent("""\
            schema_version: 1
            name: test-wf
            trigger:
              type: manual
            agents: {}
            graph:
              entry: nonexistent_entry
              nodes:
                start:
                  type: agent
                  agent: coder
        """))
        diags = validate_workflow(wf, ws, agents={"coder": None})  # type: ignore
        assert any("graph.entry" in d.fps for d in diags)


# --- Valid scaffold passes validation ---------------------------------------


class TestValidScaffold:
    """The scaffold config files should pass validation."""

    def test_workspace_loads(self):
        diags = validate_workspace(ROOT / ".geartrain" / "workspace.yaml")
        errors = [d for d in diags if d.sev == "error"]
        assert errors == [], f"unexpected errors: {errors}"

    def test_engine_loads(self):
        from geartrain.engine.loader import load_workspace
        ws = load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))
        diags = validate_engine(
            ROOT / ".geartrain" / "engines" / "local.engine.yaml",
            workspace=ws,
            repo_root=ROOT,
        )
        errors = [d for d in diags if d.sev == "error"]
        assert errors == [], f"unexpected errors: {errors}"

    def test_all_validation(self):
        diags = validate_all(
            ROOT / ".geartrain" / "workspace.yaml",
            ROOT / ".geartrain" / "engines" / "local.engine.yaml",
        )
        errors = [d for d in diags if d.sev == "error"]
        assert errors == [], f"unexpected errors: {errors}"


# --- Langchain agent validation ---------------------------------------------


class TestLangchainAgentValidation:
    """validate_agent checks model hints and tool names for langchain agents."""

    def _workspace(self):
        from geartrain.engine.loader import load_workspace

        return load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))

    def _write_agent(self, tmp_path, block: str) -> Path:
        agent_dir = tmp_path / ".geartrain" / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        f = agent_dir / "lc.agent.yaml"
        f.write_text(dedent(block))
        return f

    def test_valid_langchain_agent(self, tmp_path):
        f = self._write_agent(tmp_path, """\
            schema_version: 1
            name: lc-coder
            type: langchain
            langchain:
              model_hint: code
              tools:
                - file_read
                - shell_exec
        """)
        diags = validate_agent(f, self._workspace(), repo_root=tmp_path)
        assert [d for d in diags if d.sev == "error"] == []

    def test_unknown_model_hint(self, tmp_path):
        f = self._write_agent(tmp_path, """\
            schema_version: 1
            name: lc-coder
            type: langchain
            langchain:
              model_hint: bogus
        """)
        diags = validate_agent(f, self._workspace(), repo_root=tmp_path)
        errors = [d for d in diags if d.sev == "error"]
        assert any("model hint" in d.message for d in errors)

    def test_unknown_tool(self, tmp_path):
        f = self._write_agent(tmp_path, """\
            schema_version: 1
            name: lc-coder
            type: langchain
            langchain:
              tools:
                - file_read
                - teleport
        """)
        diags = validate_agent(f, self._workspace(), repo_root=tmp_path)
        errors = [d for d in diags if d.sev == "error"]
        assert any("unknown tool" in d.message for d in errors)

    def test_valid_memory_scopes(self, tmp_path):
        f = self._write_agent(tmp_path, """\
            schema_version: 1
            name: lc-coder
            type: langchain
            langchain: {}
            memory:
              read:
                - workspace
                - agent_instance
              write:
                - workspace
                - agent_level
        """)
        diags = validate_agent(f, self._workspace(), repo_root=tmp_path)
        assert [d for d in diags if d.sev == "error"] == []

    def test_unknown_memory_scope(self, tmp_path):
        f = self._write_agent(tmp_path, """\
            schema_version: 1
            name: lc-coder
            type: langchain
            langchain: {}
            memory:
              read:
                - galaxy
        """)
        diags = validate_agent(f, self._workspace(), repo_root=tmp_path)
        errors = [d for d in diags if d.sev == "error"]
        assert any("unknown memory scope" in d.message for d in errors)

    def test_non_writable_memory_scope(self, tmp_path):
        f = self._write_agent(tmp_path, """\
            schema_version: 1
            name: lc-coder
            type: langchain
            langchain: {}
            memory:
              write:
                - agent_instance
        """)
        diags = validate_agent(f, self._workspace(), repo_root=tmp_path)
        errors = [d for d in diags if d.sev == "error"]
        assert any("not writable" in d.message for d in errors)


# --- Diagnostic formatting --------------------------------------------------


class TestFormatDiagnostics:
    """Diagnostic output formatting."""

    def test_empty_list(self):
        assert format_diagnostics([]) == "No issues found."

    def test_single_error(self):
        diags = [Diagnostic(
            file=Path("test.yaml"),
            line=5,
            sev="error",
            fps="workspace.name",
            message="name is invalid",
        )]
        out = format_diagnostics(diags)
        assert "test.yaml:5" in out
        assert "error" in out
        assert "workspace.name" in out
        assert "name is invalid" in out

    def test_no_line_number(self):
        diags = [Diagnostic(
            file=Path("test.yaml"),
            line=None,
            sev="warning",
            fps="agent.cli.command",
            message="cmd not found",
        )]
        out = format_diagnostics(diags)
        assert "test.yaml" in out
        assert ":None" not in out


# --- CLI integration --------------------------------------------------------


class TestCLIIntegration:
    """geartrain validate command integration."""

    def test_valid_config_exits_zero(self):
        """Valid scaffold exits 0."""
        from geartrain.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["validate"])
        assert exc.value.code == 0

    def test_invalid_config_exits_nonzero(self, tmp_path, monkeypatch):
        """Invalid config exits non-zero."""
        monkeypatch.chdir(tmp_path)
        # Create a workspace with missing paths
        ws = tmp_path / ".geartrain" / "workspace.yaml"
        ws.parent.mkdir()
        ws.write_text(dedent("""\
            schema_version: 1
            name: test-ws
            project:
              name: Test
            llm:
              default_provider: anthropic
              default_model: x
            registries:
              agents: nonexistent_agents
              workflows: nonexistent_workflows
            memory:
              root: nonexistent_mem
              workspace: nonexistent_mem/ws
              workflows: nonexistent_mem/wf
              agent_types: nonexistent_mem/at
        """))
        from geartrain.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["validate"])
        assert exc.value.code == 1
