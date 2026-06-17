"""Workflow node runners — one per node type."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from geartrain.agents import AgentRunner


class NodeResult:
    """Output from a node execution."""

    def __init__(self, output: str, next_node: str | None, status: str = "ok") -> None:
        self.output = output
        self.next_node = next_node  # None means end
        self.status = status  # "ok" or "error"


class NodeRunner(Protocol):
    """Shared interface for all node runners."""

    def run(self, node_def: dict, context: dict) -> NodeResult: ...


# ---------------------------------------------------------------------------
# Agent node
# ---------------------------------------------------------------------------


class AgentNodeRunner:
    """Runs an agent and follows the default transition."""

    def __init__(self, agents: dict[str, "AgentRunner"]) -> None:
        self._agents = agents

    def run(self, node_def: dict, context: dict) -> NodeResult:
        agent_key = node_def.get("agent", "")
        runner = self._agents.get(agent_key)
        if runner is None:
            raise RuntimeError(f"No agent registered for key {agent_key!r}")

        task = context.get("task", "")
        output = runner.run(task, context)

        transitions = node_def.get("transitions", {})
        next_node = transitions.get("default")
        return NodeResult(output=output, next_node=next_node)


# ---------------------------------------------------------------------------
# Decision node
# ---------------------------------------------------------------------------


class DecisionNodeRunner:
    """Routes to a transition based on a keyword match in the last output."""

    def run(self, node_def: dict, context: dict) -> NodeResult:
        last_output = context.get("last_output", "").lower()
        transitions = node_def.get("transitions", {})

        for key, target in transitions.items():
            if key == "default":
                continue
            if key.lower() in last_output:
                return NodeResult(output=f"Decision: {key}", next_node=target)

        default = transitions.get("default")
        return NodeResult(output="Decision: default", next_node=default)


# ---------------------------------------------------------------------------
# Human checkpoint node
# ---------------------------------------------------------------------------


class HumanCheckpointRunner:
    """Pauses for CLI input and routes based on the response.

    Emits the checkpoint prompt to stdout, reads a response from stdin,
    then follows the approved/rejected transition.
    """

    def __init__(self, input_fn=None) -> None:
        # Allows tests to inject a fake input function
        self._input = input_fn or input

    def run(self, node_def: dict, context: dict) -> NodeResult:
        prompt = node_def.get("prompt", "Approve? [y/n]")
        mode = node_def.get("mode", "approval")
        transitions = node_def.get("transitions", {})

        print(f"\n[checkpoint] {prompt}")

        if mode == "approval":
            response = self._input("  Enter 'y' to approve, anything else to reject: ").strip().lower()
            approved = response in ("y", "yes", "approve", "approved")
            key = "approved" if approved else "rejected"
            next_node = transitions.get(key, transitions.get("default"))
            return NodeResult(output=f"Checkpoint response: {key}", next_node=next_node)
        else:
            # input mode — capture free text
            response = self._input("  Response: ").strip()
            next_node = transitions.get("default")
            return NodeResult(output=response, next_node=next_node)


# ---------------------------------------------------------------------------
# Integration node (stub)
# ---------------------------------------------------------------------------


class IntegrationNodeRunner:
    """Stub integration node — logs a note and follows the default transition."""

    def run(self, node_def: dict, context: dict) -> NodeResult:
        name = node_def.get("integration", "unknown")
        action = node_def.get("action", "unknown")
        note = f"[integration stub] {name}.{action} — not yet implemented"
        print(note, file=sys.stderr)
        transitions = node_def.get("transitions", {})
        next_node = transitions.get("default")
        return NodeResult(output=note, next_node=next_node)
