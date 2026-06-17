"""Agent runners and registry."""

from typing import Protocol

from geartrain.agents.factory import AgentFactory


class AgentRunner(Protocol):
    """Shared interface for all agent runners.

    The workflow layer only ever calls ``run(task, context)`` and receives
    plain text output. Agent-specific details are hidden behind this contract.
    """

    def run(self, task: str, context: dict) -> str:
        """Execute the agent on *task* given assembled *context*.

        Parameters
        ----------
        task:
            The user prompt or instruction text to process.
        context:
            Assembled context dictionary (project info, memory, prior output,
            etc.).

        Returns
        -------
        Plain text output from the agent execution.
        """


__all__ = ["AgentRunner", "AgentFactory"]
