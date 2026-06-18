"""Workflow execution engine — runs YAML-defined workflows node by node."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from geartrain.workflows.factory import WorkflowFactory
from geartrain.workflows.lock import WorkflowLock
from geartrain.workflows.nodes import (
    AgentNodeRunner,
    DecisionNodeRunner,
    HumanCheckpointRunner,
    IntegrationNodeRunner,
    NodeResult,
)

if TYPE_CHECKING:
    from geartrain.agents import AgentRunner
    from geartrain.engine.config import WorkflowDefinition
    from geartrain.engine.state import FileStateBackend


_NODE_RUNNER_MAP = {
    "agent": AgentNodeRunner,
    "decision": DecisionNodeRunner,
    "human_checkpoint": HumanCheckpointRunner,
    "integration": IntegrationNodeRunner,
}


def _resolve_variables(value: str, context: dict[str, Any]) -> str:
    """Replace ${trigger.task} and ${nodes.<id>.output} placeholders."""

    def _replace(match: re.Match) -> str:
        ref = match.group(1)

        if ref == "trigger.task":
            return str(context.get("trigger_task", ""))

        m = re.match(r"^nodes\.(\w[\w-]*)\.output$", ref)
        if m:
            node_id = m.group(1)
            outputs: dict = context.get("node_outputs", {})
            return str(outputs.get(node_id, ""))

        return match.group(0)  # leave unknown refs as-is

    return re.sub(r"\$\{([^}]+)\}", _replace, value)


def _resolve_inputs(inputs: dict[str, str], context: dict[str, Any]) -> dict[str, str]:
    return {k: _resolve_variables(v, context) for k, v in inputs.items()}


class WorkflowRunError(Exception):
    """Raised when a workflow run fails."""


class WorkflowRunner:
    """Executes a WorkflowDefinition against a set of agent runners.

    Usage::

        runner = WorkflowRunner(workflow_def, agents, state_backend, state_path, work_dir)
        result = runner.run(run_id, trigger_task="implement feature X")
    """

    def __init__(
        self,
        workflow: "WorkflowDefinition",
        agents: dict[str, "AgentRunner"],
        state_backend: "FileStateBackend",
        state_path: Path,
        work_dir: Path | None = None,
        checkpoint_input_fn=None,
        integrations: dict[str, Any] | None = None,
    ) -> None:
        self.workflow = workflow
        self.agents = agents
        self.state_backend = state_backend
        self.state_path = state_path
        self.work_dir = work_dir
        self._checkpoint_input_fn = checkpoint_input_fn
        self.integrations = integrations or {}
        self._lock = WorkflowLock(state_path, workflow.name)
        self._factory = WorkflowFactory(workflow)
        self._current_node: str | None = None

    def is_locked(self) -> bool:
        return self._lock.is_locked()

    def current_run_id(self) -> str | None:
        return self._lock.current_run_id()

    def run(self, run_id: str, trigger_task: str = "") -> dict[str, Any]:
        """Execute the workflow.

        Returns a result dict with run_id, status, and node outputs.
        Raises WorkflowRunError if the lock is already held.
        """
        self._factory.assert_valid()

        if not self._lock.acquire(run_id):
            held_by = self._lock.current_run_id()
            raise WorkflowRunError(
                f"Workflow {self.workflow.name!r} is already running "
                f"(run_id={held_by!r})"
            )

        self.state_backend.create_run(run_id, self.workflow.name)
        self.state_backend.write_workflow_state(
            self.workflow.name, "running", current_run=run_id
        )

        context: dict[str, Any] = {
            "trigger_task": trigger_task,
            "node_outputs": {},
            "project_root": str(self.work_dir.parent) if self.work_dir else ".",
            "project_name": self.workflow.name,
        }

        try:
            result = self._run_graph(run_id, context)
        except Exception as exc:
            self._handle_failure(run_id, str(exc))
            raise
        finally:
            self._lock.release()

        self.state_backend.update_run_status(run_id, "completed")
        self.state_backend.write_workflow_state(self.workflow.name, "idle")
        return result

    def _run_graph(self, run_id: str, context: dict) -> dict[str, Any]:
        nodes = self.workflow.graph.nodes
        current_node_id = self.workflow.graph.entry
        node_number = 1
        node_outputs: dict[str, str] = context["node_outputs"]

        while current_node_id and current_node_id != "end":
            if current_node_id not in nodes:
                raise WorkflowRunError(
                    f"Unknown node {current_node_id!r} during execution"
                )

            node_def = dict(nodes[current_node_id])
            node_type = node_def.get("type", "agent")
            self._current_node = current_node_id

            self.state_backend.update_run_status(run_id, "running", current_node_id)
            self._event(
                run_id,
                "node_start",
                node_id=current_node_id,
                node_type=node_type,
                node_number=node_number,
            )

            # Resolve node inputs into execution context
            raw_inputs = node_def.get("inputs", {})
            resolved_inputs = _resolve_inputs(raw_inputs, context)

            # Build per-node context
            node_context = {**context}
            node_context["task"] = resolved_inputs.get("task", context.get("trigger_task", ""))
            # Merge all resolved inputs as top-level context keys
            node_context.update(resolved_inputs)
            # Run identity so in-process tools tag memory writes and events.
            node_context["run_id"] = run_id
            node_context["node_id"] = current_node_id
            node_context["workflow"] = self.workflow.name
            # last_output for decision nodes
            node_context["last_output"] = list(node_outputs.values())[-1] if node_outputs else ""
            node_context["prior_outputs"] = list(node_outputs.items())

            result = self._run_node(run_id, current_node_id, node_type, node_def, node_context)

            self._event(
                run_id,
                "node_complete",
                node_id=current_node_id,
                node_type=node_type,
                status=result.status,
            )

            output_key = node_def.get("output_key", current_node_id)
            node_outputs[output_key] = result.output
            node_outputs[current_node_id] = result.output  # always index by node id too

            self.state_backend.write_node_output(
                run_id=run_id,
                node_id=current_node_id,
                node_type=node_type,
                agent=node_def.get("agent"),
                status="ok",
                output_text=result.output,
                output_key=output_key,
                node_number=node_number,
            )

            node_number += 1
            current_node_id = result.next_node

        return {
            "run_id": run_id,
            "workflow": self.workflow.name,
            "status": "completed",
            "node_outputs": dict(node_outputs),
        }

    def _run_node(
        self,
        run_id: str,
        node_id: str,
        node_type: str,
        node_def: dict,
        context: dict,
    ) -> NodeResult:
        attempt_id = f"{node_id}#1"
        if node_type == "agent":
            agent_runner = AgentNodeRunner(
                self.agents,
                event_sink=self._node_event_sink(run_id, node_id),
                attempt_id=attempt_id,
            )
            return agent_runner.run(node_def, context)
        elif node_type == "decision":
            return DecisionNodeRunner().run(node_def, context)
        elif node_type == "human_checkpoint":
            runner = HumanCheckpointRunner(
                input_fn=self._checkpoint_input_fn,
                event_sink=self._node_event_sink(run_id, node_id),
                checkpoint_store=self._checkpoint_recorder(run_id, node_id),
            )
            return runner.run(node_def, context)
        elif node_type == "integration":
            runner = IntegrationNodeRunner(
                self.integrations,
                event_sink=self._node_event_sink(run_id, node_id),
            )
            return runner.run(node_def, context)
        else:
            raise WorkflowRunError(f"Unknown node type {node_type!r}")

    def _event(self, run_id: str, event_type: str, **data: Any) -> None:
        """Append an event to the run store, ignoring storage failures."""
        try:
            self.state_backend.append_event(run_id, event_type, data)
        except Exception:
            pass

    def _node_event_sink(self, run_id: str, node_id: str):
        """Return an event sink bound to a run and node for a node runner."""

        def sink(event_type: str, **data: Any) -> None:
            self._event(run_id, event_type, node_id=node_id, **data)

        return sink

    def _checkpoint_recorder(self, run_id: str, node_id: str) -> "_CheckpointRecorder":
        """Return a checkpoint recorder bound to a run and node."""
        return _CheckpointRecorder(self.state_backend, run_id, node_id)

    def _handle_failure(self, run_id: str, error_msg: str) -> None:
        """Log the error, record a failure summary, and mark the run as failed."""
        self._event(
            run_id,
            "run_failed",
            node_id=self._current_node,
            error=error_msg,
        )
        try:
            self.state_backend.update_run_status(run_id, "failed")
        except Exception:
            pass
        try:
            self.state_backend.write_workflow_state(self.workflow.name, "idle")
        except Exception:
            pass
        print(
            f"[geartrain] workflow {self.workflow.name!r} run {run_id!r} failed: {error_msg}",
            file=sys.stderr,
        )


class _CheckpointRecorder:
    """Persists a checkpoint's lifecycle to the run state backend.

    ``create`` writes a ``waiting`` checkpoint and returns its id; ``respond``
    marks it ``responded``. Failures are swallowed so a state-write problem
    never aborts an otherwise-working checkpoint.
    """

    def __init__(self, backend: "FileStateBackend", run_id: str, node_id: str) -> None:
        self._backend = backend
        self._run_id = run_id
        self._node_id = node_id

    def create(self, prompt: str, mode: str) -> str:
        checkpoint_id = f"{self._node_id}-cp"
        try:
            self._backend.write_checkpoint(
                self._run_id, checkpoint_id, self._node_id, prompt, mode=mode
            )
        except Exception:
            pass
        return checkpoint_id

    def respond(self, checkpoint_id: str, response: str) -> None:
        try:
            self._backend.respond_checkpoint(self._run_id, checkpoint_id, response)
        except Exception:
            pass
