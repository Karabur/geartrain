"""Tests for config models and YAML loading (GT-P1-03)."""

from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from geartrain.engine.config import (
    CliAgentConfig,
    LangchainAgentConfig,
    MemoryEntry,
    MemoryScope,
)
from geartrain.engine.loader import (
    load_agent,
    load_engine,
    load_memory_entry,
    load_workflow,
    load_workspace,
)

ROOT = Path(__file__).parent.parent


# --- Scaffold loading tests -------------------------------------------------


class TestLoadWorkspace:
    """Loading workspace.yaml from the scaffold."""

    def test_loads_scaffold(self):
        cfg = load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))
        assert cfg.schema_version == 1
        assert cfg.name == "geartrain-core"
        assert cfg.description == "GearTrain core development workspace"

    def test_project_fields(self):
        cfg = load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))
        assert cfg.project.name == "GearTrain"
        assert cfg.project.repo_root == "."
        assert cfg.project.knowledge_base == ["docs/", "references/"]

    def test_llm_fields(self):
        cfg = load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))
        assert cfg.llm.default_provider == "anthropic"
        assert cfg.llm.default_model == "claude-sonnet-4"
        assert "reasoning" in cfg.llm.model_hints

    def test_registries(self):
        cfg = load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))
        assert cfg.registries.agents == ".geartrain/agents"
        assert cfg.registries.workflows == ".geartrain/workflows"

    def test_memory_paths(self):
        cfg = load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))
        assert cfg.memory.root == ".geartrain/memory"
        assert cfg.memory.workspace == ".geartrain/memory/workspace"

    def test_integrations(self):
        cfg = load_workspace(str(ROOT / ".geartrain" / "workspace.yaml"))
        gh = cfg.integrations["github"]
        assert gh.owner == "geartrain"
        assert gh.repo == "geartrain"
        assert gh.credential == "github.default"


class TestLoadEngine:
    """Loading engine.yaml from the scaffold."""

    def test_loads_scaffold(self):
        cfg = load_engine(
            str(ROOT / ".geartrain" / "engines" / "local.engine.yaml")
        )
        assert cfg.schema_version == 1
        assert cfg.name == "local-dev"
        assert cfg.type == "local"

    def test_network_fields(self):
        cfg = load_engine(
            str(ROOT / ".geartrain" / "engines" / "local.engine.yaml")
        )
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8420

    def test_workspace_ref(self):
        cfg = load_engine(
            str(ROOT / ".geartrain" / "engines" / "local.engine.yaml")
        )
        assert cfg.workspace.path == ".geartrain/workspace.yaml"

    def test_llm_providers(self):
        cfg = load_engine(
            str(ROOT / ".geartrain" / "engines" / "local.engine.yaml")
        )
        assert cfg.llm.default == "anthropic"
        assert "anthropic" in cfg.llm.providers
        assert "openai" in cfg.llm.providers

    def test_resources(self):
        cfg = load_engine(
            str(ROOT / ".geartrain" / "engines" / "local.engine.yaml")
        )
        assert cfg.resources.max_concurrent_workflows == 1
        assert cfg.resources.max_concurrent_agents == 1

    def test_tools(self):
        cfg = load_engine(
            str(ROOT / ".geartrain" / "engines" / "local.engine.yaml")
        )
        assert "shell" in cfg.tools
        assert "filesystem" in cfg.tools


class TestLoadAgent:
    """Loading agent.yaml files from the scaffold."""

    def test_loads_coder(self):
        cfg = load_agent(str(ROOT / ".geartrain" / "agents" / "coder.agent.yaml"))
        assert cfg.schema_version == 1
        assert cfg.name == "coder"
        assert isinstance(cfg.config, CliAgentConfig)
        assert cfg.config.type == "cli"
        assert cfg.config.command == "codex exec"
        assert cfg.config.timeout_seconds == 900
        assert cfg.config.credential == "codex.default"

    def test_coder_memory(self):
        cfg = load_agent(str(ROOT / ".geartrain" / "agents" / "coder.agent.yaml"))
        assert "workspace" in cfg.memory.read
        assert "workflow" in cfg.memory.read

    def test_loads_lead(self):
        cfg = load_agent(str(ROOT / ".geartrain" / "agents" / "lead.agent.yaml"))
        assert cfg.name == "lead"
        assert isinstance(cfg.config, CliAgentConfig)
        assert cfg.config.command == "codex exec"

    def test_system_prompt(self):
        cfg = load_agent(str(ROOT / ".geartrain" / "agents" / "coder.agent.yaml"))
        assert "senior software engineer" in cfg.system_prompt


class TestLoadWorkflow:
    """Loading workflow.yaml from the scaffold."""

    def test_loads_scaffold(self):
        cfg = load_workflow(
            str(ROOT / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml")
        )
        assert cfg.schema_version == 1
        assert cfg.name == "geartrain-dev"
        assert cfg.version == "0.1.0"

    def test_trigger(self):
        cfg = load_workflow(
            str(ROOT / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml")
        )
        assert cfg.trigger.type == "manual"

    def test_channels(self):
        cfg = load_workflow(
            str(ROOT / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml")
        )
        assert cfg.channels["human"] == "cli"

    def test_agents(self):
        cfg = load_workflow(
            str(ROOT / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml")
        )
        assert cfg.agents["lead"] == "lead"
        assert cfg.agents["coder"] == "coder"

    def test_graph(self):
        cfg = load_workflow(
            str(ROOT / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml")
        )
        assert cfg.graph.entry == "run_coder"
        assert len(cfg.graph.nodes) == 2
        assert "run_coder" in cfg.graph.nodes
        assert "run_lead" in cfg.graph.nodes

    def test_node_types(self):
        cfg = load_workflow(
            str(ROOT / ".geartrain" / "workflows" / "geartrain-dev.workflow.yaml")
        )
        assert cfg.graph.nodes["run_coder"]["type"] == "agent"
        assert cfg.graph.nodes["run_lead"]["type"] == "agent"


# --- Memory entry tests ----------------------------------------------------


class TestLoadMemoryEntry:
    """Loading memory entries from markdown with frontmatter."""

    def test_loads_frontmatter(self, tmp_path):
        f = tmp_path / "entry.md"
        f.write_text(
            "---\nscope: workspace\nsource: manual\ntags:\n  - important\n---\n\nBody text.\n"
        )
        entry = load_memory_entry(str(f))
        assert entry.scope == MemoryScope.WORKSPACE
        assert entry.source == "manual"
        assert entry.tags == ["important"]

    def test_missing_frontmatter(self, tmp_path):
        f = tmp_path / "entry.md"
        f.write_text("Just plain text, no frontmatter.")
        with pytest.raises(ValueError, match="no YAML frontmatter"):
            load_memory_entry(str(f))

    def test_incomplete_frontmatter(self, tmp_path):
        f = tmp_path / "entry.md"
        f.write_text("---\nscope: workspace\n")
        with pytest.raises(ValueError, match="incomplete YAML frontmatter"):
            load_memory_entry(str(f))


# --- Error handling tests --------------------------------------------------


class TestMalformedYaml:
    """Malformed YAML produces clear errors."""

    def test_invalid_yaml_syntax(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("{invalid: yaml: [}")
        with pytest.raises(Exception):
            load_workspace(str(f))

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        with pytest.raises(ValueError, match="expected a YAML mapping"):
            load_workspace(str(f))

    def test_yaml_list_at_top_level(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="expected a YAML mapping"):
            load_workspace(str(f))


class TestWrongFieldType:
    """Wrong field types produce clear Pydantic validation errors."""

    def test_port_must_be_int(self, tmp_path):
        """Engine port field must be an integer."""
        f = tmp_path / "engine.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-engine
            type: local
            workspace:
              path: .
            llm:
              default: anthropic
            state:
              backend: files
              path: .
            port: not_a_number
        """))
        with pytest.raises(ValidationError):
            load_engine(str(f))

    def test_knowledge_base_must_be_list(self, tmp_path):
        """Workspace knowledge_base must be a list."""
        f = tmp_path / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-ws
            project:
              name: Test
              knowledge_base: "not_a_list"
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
        with pytest.raises(ValidationError):
            load_workspace(str(f))

    def test_trigger_type_must_be_str(self, tmp_path):
        """Workflow trigger type must be a string."""
        f = tmp_path / "workflow.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-wf
            trigger:
              type: 123
            graph:
              entry: start
              nodes: {}
        """))
        with pytest.raises(ValidationError):
            load_workflow(str(f))

    def test_unknown_trigger_type_rejected(self, tmp_path):
        """An unknown trigger type fails validation."""
        f = tmp_path / "workflow.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-wf
            trigger:
              type: work_queue
            graph:
              entry: start
              nodes: {}
        """))
        with pytest.raises(ValidationError):
            load_workflow(str(f))



class TestInvalidSchemaVersion:
    """Invalid schema_version produces a clear error."""

    def test_bad_schema_version_workspace(self, tmp_path):
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
        with pytest.raises(ValidationError, match="schema_version"):
            load_workspace(str(f))

    def test_bad_schema_version_engine(self, tmp_path):
        f = tmp_path / "engine.yaml"
        f.write_text(dedent("""\
            schema_version: 2
            name: test-engine
            workspace:
              path: .
            llm:
              default: anthropic
            state:
              backend: files
              path: .
        """))
        with pytest.raises(ValidationError, match="schema_version"):
            load_engine(str(f))


class TestInvalidName:
    """Invalid name format produces a clear error."""

    def test_uppercase_name(self, tmp_path):
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
        with pytest.raises(ValidationError, match="name"):
            load_workspace(str(f))

    def test_name_starts_with_digit(self, tmp_path):
        f = tmp_path / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: 123abc
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
        with pytest.raises(ValidationError, match="name"):
            load_workspace(str(f))

    def test_empty_name(self, tmp_path):
        f = tmp_path / "workspace.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: ""
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
        with pytest.raises(ValidationError, match="name"):
            load_workspace(str(f))


class TestExtraFieldsForbidden:
    """Unknown fields are rejected by extra='forbid'."""

    def test_unknown_workspace_field(self, tmp_path):
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
        with pytest.raises(ValidationError, match="unknown_field"):
            load_workspace(str(f))

    def test_unknown_cli_agent_field(self, tmp_path):
        """Unknown fields inside the cli config block are rejected."""
        f = tmp_path / "agent.yaml"
        f.write_text(dedent("""\
            schema_version: 1
            name: test-agent
            type: cli
            cli:
              command: test
              credential: x
              unknown_cli_field: true
        """))
        with pytest.raises(ValidationError, match="unknown_cli_field"):
            load_agent(str(f))
