"""CLI agent runner — invokes an external command via a sandbox."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geartrain.engine.config import AgentDefinition
    from geartrain.engine.sandbox import Sandbox


class CliAgentRunner:
    """Agent runner that delegates to a CLI subprocess.

    The runner holds the agent definition and a sandbox reference so that
    later phases can wire in command execution, timeouts, and credential
    injection.
    """

    def __init__(self, agent_def: AgentDefinition, sandbox: Sandbox) -> None:
        self.agent_def = agent_def
        self.sandbox = sandbox

    def run(self, task: str, context: dict) -> str:
        """Run the CLI agent.

        Returns a placeholder string until the full subprocess integration
        is implemented in a later phase.
        """
        return "cli agent execution not yet implemented"
