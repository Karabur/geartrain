"""Tests for the LangChain agent runner and context wiring (GT-P4-01, GT-P4-05)."""

from textwrap import dedent

from langchain_core.messages import AIMessage, SystemMessage

from geartrain.agents import AgentFactory
from geartrain.agents.langchain_runner import LangchainAgentRunner
from geartrain.engine.config import (
    AgentDefinition,
    LangchainAgentConfig,
    LlmWorkspaceConfig,
    MemoryPaths,
    ProjectConfig,
    WorkspaceConfig,
    WorkspaceRegistries,
)
from geartrain.engine.loader import load_agent
from geartrain.engine.sandbox import NoopSandbox
from tests.stub_chat_model import StubChatModel


def _workspace() -> WorkspaceConfig:
    return WorkspaceConfig(
        schema_version=1,
        name="geartrain-core",
        project=ProjectConfig(name="GearTrain", repo_root="."),
        llm=LlmWorkspaceConfig(
            default_provider="anthropic", default_model="claude-sonnet-4"
        ),
        registries=WorkspaceRegistries(agents="a", workflows="w"),
        memory=MemoryPaths(
            root="m", workspace="m/w", workflows="m/wf", agent_types="m/at"
        ),
    )


def _langchain_agent(system_prompt: str = "", tools=None) -> AgentDefinition:
    return AgentDefinition(
        schema_version=1,
        name="lc-agent",
        config=LangchainAgentConfig(type="langchain", tools=tools or []),
        system_prompt=system_prompt,
    )


class TestLangchainRunnerThroughFactory:
    def test_runs_from_yaml_with_stub_llm(self, tmp_path):
        """A langchain agent loaded from YAML runs through the factory."""
        agent_dir = tmp_path / ".geartrain" / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        agent_file = agent_dir / "lc.yaml"
        agent_file.write_text(dedent("""\
            schema_version: 1
            name: lc-agent
            type: langchain
            langchain:
              llm_provider: anthropic
              llm_model: claude-sonnet-4
        """))
        agent_def = load_agent(str(agent_file))

        stub = StubChatModel(responses=[AIMessage(content="done")])
        runner = AgentFactory.create(agent_def, NoopSandbox(), llm=stub)

        output = runner.run("do the thing", {"project_name": "GearTrain"})
        assert output == "done"


class TestContextAndInterpolation:
    def test_system_prompt_interpolated_at_load(self):
        """${workspace.*} references resolve when the runner is built."""
        agent = _langchain_agent(
            system_prompt="You work on ${workspace.project.name}."
        )
        runner = LangchainAgentRunner(
            agent,
            NoopSandbox(),
            workspace=_workspace(),
            llm=StubChatModel(responses=[AIMessage(content="ok")]),
        )
        assert runner.system_prompt == "You work on GearTrain."

    def test_assembled_context_reaches_model(self):
        """Task, prior output, and memory appear in the human message."""
        stub = StubChatModel(responses=[AIMessage(content="ok")])
        runner = LangchainAgentRunner(
            _langchain_agent(system_prompt="Coder for ${workspace.project.name}."),
            NoopSandbox(),
            workspace=_workspace(),
            llm=stub,
        )

        runner.run(
            "Implement feature X",
            {
                "project_name": "GearTrain",
                "prior_outputs": [("intake", "Approved by lead")],
                "memory_entries": [("workspace", ["Use type hints"])],
            },
        )

        messages = stub.seen_messages[0]
        system = [m for m in messages if isinstance(m, SystemMessage)]
        assert system and system[0].content == "Coder for GearTrain."

        human_text = "\n".join(
            str(m.content) for m in messages if not isinstance(m, SystemMessage)
        )
        assert "Implement feature X" in human_text
        assert "Approved by lead" in human_text
        assert "Use type hints" in human_text
        assert "GearTrain" in human_text
