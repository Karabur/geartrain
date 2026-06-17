"""Tests for workflow factory, node types, engine, and locking (GT-P3-02 to P3-05)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from geartrain.engine.config import WorkflowDefinition
from geartrain.engine.loader import load_workflow
from geartrain.engine.state import FileStateBackend
from geartrain.workflows.engine import WorkflowRunError, WorkflowRunner
from geartrain.workflows.factory import WorkflowFactory, WorkflowValidationError
from geartrain.workflows.lock import WorkflowLock
from geartrain.workflows.nodes import (
    AgentNodeRunner,
    DecisionNodeRunner,
    HumanCheckpointRunner,
    IntegrationNodeRunner,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_workflow(tmp_path: Path, yaml_text: str) -> WorkflowDefinition:
    f = tmp_path / "test.workflow.yaml"
    f.write_text(dedent(yaml_text))
    return load_workflow(str(f))


def _simple_workflow(tmp_path: Path) -> WorkflowDefinition:
    return _write_workflow(
        tmp_path,
        """\
        schema_version: 1
        name: test-wf
        description: test
        trigger:
          type: manual
        agents:
          worker: worker
        graph:
          entry: step_a
          nodes:
            step_a:
              type: agent
              agent: worker
              output_key: a_output
              transitions:
                default: step_b
            step_b:
              type: agent
              agent: worker
              output_key: b_output
              transitions:
                default: end
        """,
    )


class MockAgentRunner:
    def __init__(self, response: str = "mock output") -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def run(self, task: str, context: dict) -> str:
        self.calls.append((task, context))
        return self.response


@pytest.fixture
def state_backend(tmp_path: Path) -> FileStateBackend:
    return FileStateBackend(tmp_path / "state")


# ---------------------------------------------------------------------------
# WorkflowFactory tests (P3-02)
# ---------------------------------------------------------------------------


class TestWorkflowFactory:
    def test_valid_graph(self, tmp_path: Path):
        wf = _simple_workflow(tmp_path)
        factory = WorkflowFactory(wf)
        assert factory.is_valid
        assert factory.errors == []

    def test_missing_entry_node(self, tmp_path: Path):
        wf = _write_workflow(
            tmp_path,
            """\
            schema_version: 1
            name: test-wf
            description: test
            trigger:
              type: manual
            graph:
              entry: nonexistent
              nodes:
                step_a:
                  type: agent
                  transitions:
                    default: end
            """,
        )
        factory = WorkflowFactory(wf)
        assert not factory.is_valid
        assert any("entry" in e for e in factory.errors)

    def test_unknown_transition_target(self, tmp_path: Path):
        wf = _write_workflow(
            tmp_path,
            """\
            schema_version: 1
            name: test-wf
            description: test
            trigger:
              type: manual
            graph:
              entry: step_a
              nodes:
                step_a:
                  type: agent
                  transitions:
                    default: ghost_node
            """,
        )
        factory = WorkflowFactory(wf)
        assert not factory.is_valid
        assert any("ghost_node" in e for e in factory.errors)

    def test_unreachable_node(self, tmp_path: Path):
        wf = _write_workflow(
            tmp_path,
            """\
            schema_version: 1
            name: test-wf
            description: test
            trigger:
              type: manual
            graph:
              entry: step_a
              nodes:
                step_a:
                  type: agent
                  transitions:
                    default: end
                orphan:
                  type: agent
                  transitions:
                    default: end
            """,
        )
        factory = WorkflowFactory(wf)
        assert not factory.is_valid
        assert any("orphan" in e for e in factory.errors)

    def test_assert_valid_raises(self, tmp_path: Path):
        wf = _write_workflow(
            tmp_path,
            """\
            schema_version: 1
            name: test-wf
            description: test
            trigger:
              type: manual
            graph:
              entry: missing
              nodes: {}
            """,
        )
        factory = WorkflowFactory(wf)
        with pytest.raises(WorkflowValidationError):
            factory.assert_valid()

    def test_node_ids_in_order(self, tmp_path: Path):
        wf = _simple_workflow(tmp_path)
        factory = WorkflowFactory(wf)
        ids = factory.node_ids_in_order()
        assert ids == ["step_a", "step_b"]

    def test_variable_resolution(self, tmp_path: Path, state_backend: FileStateBackend):
        """Variable ${nodes.a_output.output} resolves to upstream output."""
        wf = _write_workflow(
            tmp_path,
            """\
            schema_version: 1
            name: test-wf
            description: test
            trigger:
              type: manual
            agents:
              worker: worker
            graph:
              entry: step_a
              nodes:
                step_a:
                  type: agent
                  agent: worker
                  output_key: a_output
                  transitions:
                    default: step_b
                step_b:
                  type: agent
                  agent: worker
                  inputs:
                    task: "${nodes.a_output.output}"
                  output_key: b_output
                  transitions:
                    default: end
            """,
        )
        mock = MockAgentRunner("from_a")
        step_b_mock = MockAgentRunner("from_b")
        call_order = []

        class SequentialMock:
            def __init__(self):
                self._calls = 0

            def run(self, task: str, context: dict) -> str:
                self._calls += 1
                if self._calls == 1:
                    return "from_a"
                return task  # returns whatever task was passed

        seq = SequentialMock()
        runner = WorkflowRunner(
            workflow=wf,
            agents={"worker": seq},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        result = runner.run("run-001", trigger_task="start")
        assert result["node_outputs"].get("b_output") == "from_a"


# ---------------------------------------------------------------------------
# Node type tests (P3-03)
# ---------------------------------------------------------------------------


class TestAgentNodeRunner:
    def test_runs_agent_and_follows_default_transition(self):
        mock = MockAgentRunner("agent output")
        runner = AgentNodeRunner({"myagent": mock})
        result = runner.run(
            {"type": "agent", "agent": "myagent", "transitions": {"default": "next"}},
            {"task": "do thing"},
        )
        assert result.output == "agent output"
        assert result.next_node == "next"

    def test_missing_agent_raises(self):
        runner = AgentNodeRunner({})
        with pytest.raises(RuntimeError, match="No agent registered"):
            runner.run({"agent": "missing", "transitions": {}}, {})

    def test_end_transition(self):
        mock = MockAgentRunner("ok")
        runner = AgentNodeRunner({"a": mock})
        result = runner.run({"agent": "a", "transitions": {"default": "end"}}, {"task": ""})
        assert result.next_node == "end"


class TestDecisionNodeRunner:
    def test_matches_keyword_in_output(self):
        runner = DecisionNodeRunner()
        result = runner.run(
            {"transitions": {"approved": "yes_branch", "rejected": "no_branch"}},
            {"last_output": "The plan is approved."},
        )
        assert result.next_node == "yes_branch"

    def test_falls_back_to_default(self):
        runner = DecisionNodeRunner()
        result = runner.run(
            {"transitions": {"approved": "yes", "default": "fallback"}},
            {"last_output": "no keyword here"},
        )
        assert result.next_node == "fallback"


class TestHumanCheckpointRunner:
    def test_approved_follows_approved_transition(self):
        runner = HumanCheckpointRunner(input_fn=lambda _: "y")
        result = runner.run(
            {
                "prompt": "Approve?",
                "mode": "approval",
                "transitions": {"approved": "proceed", "rejected": "stop"},
            },
            {},
        )
        assert result.next_node == "proceed"

    def test_rejected_follows_rejected_transition(self):
        runner = HumanCheckpointRunner(input_fn=lambda _: "n")
        result = runner.run(
            {
                "prompt": "Approve?",
                "mode": "approval",
                "transitions": {"approved": "proceed", "rejected": "stop"},
            },
            {},
        )
        assert result.next_node == "stop"

    def test_input_mode_captures_text(self):
        runner = HumanCheckpointRunner(input_fn=lambda _: "my free text")
        result = runner.run(
            {"mode": "input", "transitions": {"default": "next"}},
            {},
        )
        assert result.output == "my free text"
        assert result.next_node == "next"


class TestIntegrationNodeRunner:
    def test_runs_github_action_and_follows_default_transition(self):
        class FakeGitHub:
            def create_pull_request(self, *, title, head, base="main", body=""):
                return {"number": 7, "url": "https://gh/pr/7", "title": title, "state": "open"}

        runner = IntegrationNodeRunner({"github": FakeGitHub()})
        result = runner.run(
            {
                "service": "github",
                "action": "open_pr",
                "transitions": {"default": "done"},
            },
            {"title": "My PR", "head": "feature/x"},
        )
        assert "PR #7" in result.output
        assert result.next_node == "done"

    def test_missing_client_raises(self):
        from geartrain.workflows.nodes import IntegrationError

        runner = IntegrationNodeRunner()
        with pytest.raises(IntegrationError):
            runner.run(
                {"service": "github", "action": "open_pr", "transitions": {}},
                {"title": "x", "head": "y"},
            )


# ---------------------------------------------------------------------------
# WorkflowRunner tests (P3-02, P3-03, P3-04)
# ---------------------------------------------------------------------------


class TestWorkflowRunner:
    def test_runs_agent_nodes(self, tmp_path: Path, state_backend: FileStateBackend):
        wf = _simple_workflow(tmp_path)
        mock = MockAgentRunner("step output")
        runner = WorkflowRunner(
            wf,
            agents={"worker": mock},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        result = runner.run("run-001", trigger_task="do work")
        assert result["status"] == "completed"
        assert len(mock.calls) == 2  # step_a and step_b

    def test_writes_run_state_files(self, tmp_path: Path, state_backend: FileStateBackend):
        wf = _simple_workflow(tmp_path)
        runner = WorkflowRunner(
            wf,
            agents={"worker": MockAgentRunner("ok")},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        runner.run("run-001", trigger_task="work")
        run_state = state_backend.read_run_state("run-001")
        assert run_state["status"] == "completed"

    def test_agent_decision_agent_flow(self, tmp_path: Path, state_backend: FileStateBackend):
        wf = _write_workflow(
            tmp_path,
            """\
            schema_version: 1
            name: test-wf
            description: test
            trigger:
              type: manual
            agents:
              worker: worker
            graph:
              entry: first
              nodes:
                first:
                  type: agent
                  agent: worker
                  output_key: first_out
                  transitions:
                    default: decide
                decide:
                  type: decision
                  transitions:
                    approved: final
                    default: final
                final:
                  type: agent
                  agent: worker
                  output_key: final_out
                  transitions:
                    default: end
            """,
        )

        class SequenceMock:
            def __init__(self):
                self._n = 0
            def run(self, task, context):
                self._n += 1
                return "approved" if self._n == 1 else "done"

        runner = WorkflowRunner(
            wf,
            agents={"worker": SequenceMock()},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        result = runner.run("run-001")
        assert result["status"] == "completed"

    def test_agent_checkpoint_agent_flow(self, tmp_path: Path, state_backend: FileStateBackend):
        wf = _write_workflow(
            tmp_path,
            """\
            schema_version: 1
            name: test-wf
            description: test
            trigger:
              type: manual
            agents:
              worker: worker
            graph:
              entry: first
              nodes:
                first:
                  type: agent
                  agent: worker
                  output_key: first_out
                  transitions:
                    default: checkpoint
                checkpoint:
                  type: human_checkpoint
                  prompt: "Approve?"
                  mode: approval
                  transitions:
                    approved: final
                    rejected: end
                final:
                  type: agent
                  agent: worker
                  output_key: final_out
                  transitions:
                    default: end
            """,
        )
        runner = WorkflowRunner(
            wf,
            agents={"worker": MockAgentRunner("output")},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
            checkpoint_input_fn=lambda _: "y",
        )
        result = runner.run("run-001")
        assert result["status"] == "completed"

    def test_failing_node_stops_run_and_records_error(
        self, tmp_path: Path, state_backend: FileStateBackend
    ):
        wf = _simple_workflow(tmp_path)

        class FailingAgent:
            def run(self, task, context):
                raise RuntimeError("agent exploded")

        runner = WorkflowRunner(
            wf,
            agents={"worker": FailingAgent()},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        with pytest.raises(RuntimeError, match="agent exploded"):
            runner.run("run-001")

        run_state = state_backend.read_run_state("run-001")
        assert run_state["status"] == "failed"

    def test_lock_releases_after_failure(self, tmp_path: Path, state_backend: FileStateBackend):
        wf = _simple_workflow(tmp_path)

        class FailingAgent:
            def run(self, task, context):
                raise RuntimeError("boom")

        runner = WorkflowRunner(
            wf,
            agents={"worker": FailingAgent()},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        with pytest.raises(RuntimeError):
            runner.run("run-001")

        assert not runner.is_locked()

    def test_run_state_stored_per_node(self, tmp_path: Path, state_backend: FileStateBackend):
        wf = _simple_workflow(tmp_path)
        runner = WorkflowRunner(
            wf,
            agents={"worker": MockAgentRunner("node output")},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        runner.run("run-001")
        node_data = state_backend.read_node_output("run-001", "step_a")
        assert node_data["node_id"] == "step_a"


# ---------------------------------------------------------------------------
# Workflow locking tests (P3-05)
# ---------------------------------------------------------------------------


class TestWorkflowLock:
    def test_acquire_and_release(self, tmp_path: Path):
        lock = WorkflowLock(tmp_path, "my-wf")
        assert not lock.is_locked()
        assert lock.acquire("run-001")
        assert lock.is_locked()
        assert lock.current_run_id() == "run-001"
        lock.release()
        assert not lock.is_locked()

    def test_second_acquire_fails(self, tmp_path: Path):
        lock = WorkflowLock(tmp_path, "my-wf")
        assert lock.acquire("run-001")
        assert not lock.acquire("run-002")

    def test_release_when_not_locked_is_noop(self, tmp_path: Path):
        lock = WorkflowLock(tmp_path, "my-wf")
        lock.release()  # should not raise

    def test_already_running_raises_on_runner(self, tmp_path: Path, state_backend: FileStateBackend):
        wf = _simple_workflow(tmp_path)
        lock = WorkflowLock(tmp_path / "state", wf.name)
        lock.acquire("existing-run")

        runner = WorkflowRunner(
            wf,
            agents={"worker": MockAgentRunner("ok")},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        with pytest.raises(WorkflowRunError, match="already running"):
            runner.run("new-run")

    def test_lock_releases_after_successful_run(
        self, tmp_path: Path, state_backend: FileStateBackend
    ):
        wf = _simple_workflow(tmp_path)
        runner = WorkflowRunner(
            wf,
            agents={"worker": MockAgentRunner("ok")},
            state_backend=state_backend,
            state_path=tmp_path / "state",
            work_dir=tmp_path,
        )
        runner.run("run-001")
        assert not runner.is_locked()
