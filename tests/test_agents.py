"""Tests for agent interface and factory (GT-P2-01)."""

from textwrap import dedent

import pytest

from geartrain.agents import AgentFactory
from geartrain.engine.loader import load_agent
from geartrain.engine.sandbox import NoopSandbox


def _write_cli_agent(tmp_path, filename="test-agent.yaml") -> str:
    """Write a minimal CLI agent YAML and return its path."""
    agent_dir = tmp_path / ".geartrain" / "agents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agent_dir / filename
    agent_file.write_text(dedent("""\
        schema_version: 1
        name: test-cli-agent
        type: cli
        cli:
          command: echo
          credential: test-cred
    """))
    return str(agent_file)


class TestAgentFactory:
    """AgentFactory dispatch and error handling."""

    def test_create_cli_agent(self, tmp_path):
        """Factory creates a CliAgentRunner for a cli-type agent."""
        path = _write_cli_agent(tmp_path)
        agent_def = load_agent(path)
        assert agent_def.config.type == "cli"

        runner = AgentFactory.create(agent_def, NoopSandbox())
        assert runner is not None
        # Verify the run contract returns str.
        result = runner.run("do something", {})
        assert isinstance(result, str)

    def test_create_langchain_returns_runner(self, tmp_path):
        """Factory builds a LangchainAgentRunner for a langchain-type agent."""
        agent_dir = tmp_path / ".geartrain" / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        agent_file = agent_dir / "lc-agent.yaml"
        agent_file.write_text(dedent("""\
            schema_version: 1
            name: test-lc-agent
            type: langchain
            langchain:
              llm_provider: anthropic
              llm_model: claude-sonnet-4
        """))

        agent_def = load_agent(str(agent_file))
        runner = AgentFactory.create(agent_def, NoopSandbox())

        from geartrain.agents.langchain_runner import LangchainAgentRunner

        assert isinstance(runner, LangchainAgentRunner)

    def test_create_unknown_type_raises_value_error(self, tmp_path):
        """Factory raises ValueError for an unrecognized agent type."""
        agent_dir = tmp_path / ".geartrain" / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        agent_file = agent_dir / "unknown-agent.yaml"
        agent_file.write_text(dedent("""\
            schema_version: 1
            name: test-unknown-agent
            type: custom
            custom:
              foo: bar
        """))

        # Pydantic will parse the config block as a dict with type=custom,
        # but the discriminated union won't match any tag. We bypass that
        # by constructing the definition with a mock config whose type is
        # something the factory doesn't recognize.
        from unittest.mock import MagicMock

        agent_def = MagicMock()
        agent_def.config.type = "custom"

        with pytest.raises(ValueError, match="Unknown agent type"):
            AgentFactory.create(agent_def, NoopSandbox())
