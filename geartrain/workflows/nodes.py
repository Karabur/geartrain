"""Workflow node runners — one per node type."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, Protocol

from geartrain.agents.tools.base import summarize
from geartrain.integrations.github import GitHubError

if TYPE_CHECKING:
    from geartrain.agents import AgentRunner
    from geartrain.integrations.github import GitHubClient


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
# Integration node
# ---------------------------------------------------------------------------


class IntegrationError(Exception):
    """Raised when an integration node can't complete its action."""


class IntegrationNodeRunner:
    """Runs an external integration action (currently GitHub).

    The node names a ``service`` (e.g. ``github``) and an ``action``
    (``open_pr``, ``create_branch``, ``commit``, ``get_issue``,
    ``update_issue``). Action inputs come from the node context, which the
    workflow runner has already resolved from node ``inputs``. The action
    produces plain-text output stored in run state, and records tool/integration
    and error events through ``event_sink`` for observability.

    ``integrations`` maps a service name to its client. ``event_sink`` takes an
    event type and keyword fields; it defaults to a no-op so the runner stays
    usable without a run store.
    """

    def __init__(
        self,
        integrations: dict[str, Any] | None = None,
        event_sink: Callable[..., None] | None = None,
    ) -> None:
        self._integrations = integrations or {}
        self._event = event_sink or (lambda *a, **k: None)

    def run(self, node_def: dict, context: dict) -> NodeResult:
        service = node_def.get("service") or node_def.get("integration") or ""
        action = node_def.get("action", "")
        transitions = node_def.get("transitions", {})
        next_node = transitions.get("default")

        client = self._integrations.get(service)
        if client is None:
            msg = f"no client configured for integration service {service!r}"
            self._event("integration_error", service=service, action=action, error=msg)
            raise IntegrationError(msg)

        if service != "github":
            msg = f"unsupported integration service {service!r}"
            self._event("integration_error", service=service, action=action, error=msg)
            raise IntegrationError(msg)

        start = time.perf_counter()
        try:
            output, metadata = _run_github_action(action, client, context)
        except (GitHubError, IntegrationError) as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._event(
                "tool_call",
                kind="integration",
                name=f"{service}.{action}",
                status="error",
                duration_ms=duration_ms,
                error=str(exc),
                summary=summarize(str(exc)),
            )
            raise IntegrationError(f"{service}.{action} failed: {exc}") from exc

        duration_ms = (time.perf_counter() - start) * 1000
        self._event(
            "tool_call",
            kind="integration",
            name=f"{service}.{action}",
            status="ok",
            duration_ms=duration_ms,
            summary=summarize(output),
            metadata=metadata,
        )
        return NodeResult(output=output, next_node=next_node)


def _ctx(context: dict, *keys: str, default: Any = None, required: bool = False) -> Any:
    """Read the first present key from context."""
    for key in keys:
        value = context.get(key)
        if value not in (None, ""):
            return value
    if required:
        raise IntegrationError(f"missing required input: one of {keys}")
    return default


def _run_github_action(
    action: str, client: "GitHubClient", context: dict
) -> tuple[str, dict]:
    """Dispatch a GitHub integration action, returning (output_text, metadata)."""
    if action in ("open_pr", "create_pr"):
        result = client.create_pull_request(
            title=_ctx(context, "title", required=True),
            head=_ctx(context, "head", "branch", required=True),
            base=_ctx(context, "base", default="main"),
            body=_ctx(context, "body", default=""),
        )
        return f"Opened PR #{result['number']}: {result['url']}", result

    if action == "create_branch":
        result = client.create_branch(
            _ctx(context, "branch", "name", required=True),
            base=_ctx(context, "base", default="main"),
        )
        return f"Created branch {result['branch']} from {result['base']}", result

    if action == "commit":
        path = _ctx(context, "path", required=True)
        result = client.commit_files(
            _ctx(context, "branch", required=True),
            {path: _ctx(context, "content", default="")},
            _ctx(context, "message", required=True),
        )
        return f"Committed {path} to {result['branch']} ({result['commit'][:7]})", result

    if action == "get_issue":
        issue = client.get_issue(int(_ctx(context, "number", "issue", required=True)))
        labels = ", ".join(issue["labels"]) or "none"
        text = f"Issue #{issue['number']} [{issue['state']}] {issue['title']} (labels: {labels})"
        return text, issue

    if action == "update_issue":
        labels = _ctx(context, "labels")
        if isinstance(labels, str):
            labels = [s.strip() for s in labels.split(",") if s.strip()]
        issue = client.update_issue(
            int(_ctx(context, "number", "issue", required=True)),
            state=_ctx(context, "state"),
            labels=labels,
        )
        return f"Updated issue #{issue['number']} (state: {issue['state']})", issue

    raise IntegrationError(f"unknown github action {action!r}")
