"""Agent factory — creates runner instances from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from geartrain.agents.cli_runner import CliAgentRunner

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from geartrain.agents import AgentRunner
    from geartrain.engine.config import (
        AgentDefinition,
        EngineConfig,
        WorkspaceConfig,
    )
    from geartrain.engine.sandbox import Sandbox


class AgentFactory:
    """Creates ``AgentRunner`` instances by dispatching on agent config type.

    This is the single place where agent type selection happens. The workflow
    layer never inspects config types directly.
    """

    @staticmethod
    def create(
        agent_def: AgentDefinition,
        sandbox: Sandbox,
        *,
        workspace: "WorkspaceConfig | None" = None,
        engine: "EngineConfig | None" = None,
        llm: "BaseChatModel | None" = None,
        **kwargs: Any,
    ) -> AgentRunner:
        """Build an agent runner from a definition and sandbox.

        Parameters
        ----------
        agent_def:
            Parsed agent configuration (from YAML).
        sandbox:
            Sandbox instance for command execution.
        workspace, engine:
            Configs the ``langchain`` runner needs to resolve a model and
            interpolate the system prompt. Ignored by the ``cli`` runner.
        llm:
            Optional chat model injected directly (tests use a stub). When set,
            model resolution is skipped.
        kwargs:
            Extra keyword arguments forwarded to the langchain runner (e.g.
            ``tool_root``, ``shell_cwd``).

        Returns
        -------
        An ``AgentRunner`` implementation matching the config type.

        Raises
        ------
        ValueError:
            When the agent type is unknown.
        """
        agent_type = agent_def.config.type

        if agent_type == "cli":
            return CliAgentRunner(agent_def, sandbox)
        elif agent_type == "langchain":
            from geartrain.agents.langchain_runner import LangchainAgentRunner

            return LangchainAgentRunner(
                agent_def,
                sandbox,
                workspace=workspace,
                engine=engine,
                llm=llm,
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
