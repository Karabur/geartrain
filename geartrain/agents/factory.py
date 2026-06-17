"""Agent factory — creates runner instances from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geartrain.agents.cli_runner import CliAgentRunner

if TYPE_CHECKING:
    from geartrain.agents import AgentRunner
    from geartrain.engine.config import AgentDefinition
    from geartrain.engine.sandbox import Sandbox


class AgentFactory:
    """Creates ``AgentRunner`` instances by dispatching on agent config type.

    This is the single place where agent type selection happens. The workflow
    layer never inspects config types directly.
    """

    @staticmethod
    def create(agent_def: AgentDefinition, sandbox: Sandbox) -> AgentRunner:
        """Build an agent runner from a definition and sandbox.

        Parameters
        ----------
        agent_def:
            Parsed agent configuration (from YAML).
        sandbox:
            Sandbox instance for command execution.

        Returns
        -------
        An ``AgentRunner`` implementation matching the config type.

        Raises
        ------
        NotImplementedError:
            When the agent type is recognized but not yet implemented.
        ValueError:
            When the agent type is unknown.
        """
        agent_type = agent_def.config.type

        if agent_type == "cli":
            return CliAgentRunner(agent_def, sandbox)
        elif agent_type == "langchain":
            raise NotImplementedError("langchain agent type not yet implemented")
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")
