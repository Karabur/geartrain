"""Workflow factory — validates and prepares a WorkflowDefinition for execution."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geartrain.engine.config import WorkflowDefinition


class WorkflowValidationError(Exception):
    """Raised when a workflow graph has structural problems."""


def _all_reachable(graph: dict, entry: str) -> set[str]:
    """Return all node IDs reachable from entry by following transitions."""
    reachable: set[str] = set()
    queue = [entry]
    while queue:
        node_id = queue.pop()
        if node_id in reachable or node_id == "end":
            continue
        reachable.add(node_id)
        node_def = graph.get(node_id, {})
        for target in node_def.get("transitions", {}).values():
            if target and target != "end" and target not in reachable:
                queue.append(target)
    return reachable


def validate_graph(workflow: "WorkflowDefinition") -> list[str]:
    """Return a list of error strings for graph structural problems.

    Checks:
    - Entry node exists in nodes.
    - All transition targets exist (or are "end").
    - No orphan (unreachable) nodes.
    """
    errors: list[str] = []
    nodes = workflow.graph.nodes
    entry = workflow.graph.entry

    if entry not in nodes:
        errors.append(f"entry node {entry!r} not in graph.nodes")
        return errors  # can't analyse further

    for node_id, node_def in nodes.items():
        transitions = node_def.get("transitions", {})
        for key, target in transitions.items():
            if target and target != "end" and target not in nodes:
                errors.append(
                    f"node {node_id!r}: transition {key!r} targets unknown node {target!r}"
                )

    reachable = _all_reachable(nodes, entry)
    orphans = set(nodes.keys()) - reachable
    for orphan in sorted(orphans):
        errors.append(f"node {orphan!r} is unreachable from entry {entry!r}")

    return errors


class WorkflowFactory:
    """Validates and describes a WorkflowDefinition for the runner.

    The factory does not hold execution state. The runner uses it to verify
    the workflow before starting.
    """

    def __init__(self, workflow: "WorkflowDefinition") -> None:
        self.workflow = workflow
        self._errors = validate_graph(workflow)

    @property
    def is_valid(self) -> bool:
        return not self._errors

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    def assert_valid(self) -> None:
        """Raise WorkflowValidationError if the graph has problems."""
        if self._errors:
            msg = "; ".join(self._errors)
            raise WorkflowValidationError(
                f"workflow {self.workflow.name!r} has graph errors: {msg}"
            )

    def node_ids_in_order(self) -> list[str]:
        """Return node IDs in BFS order starting from entry."""
        self.assert_valid()
        seen: list[str] = []
        queue = [self.workflow.graph.entry]
        visited: set[str] = set()
        while queue:
            node_id = queue.pop(0)
            if node_id in visited or node_id == "end":
                continue
            visited.add(node_id)
            seen.append(node_id)
            node_def = self.workflow.graph.nodes.get(node_id, {})
            for target in node_def.get("transitions", {}).values():
                if target and target not in visited:
                    queue.append(target)
        return seen
