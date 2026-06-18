"""Seeding helpers for Phase 7 observability tests.

Builds real runs through the workflow engine with scripted stub LLMs, so the
run state, node files, and ``events.jsonl`` the query/stream/summary code reads
are produced exactly as production would write them. No network, no real LLM.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from langchain_core.messages import AIMessage

from geartrain.agents.langchain_runner import LangchainAgentRunner
from geartrain.engine.config import (
    AgentDefinition,
    AgentMemoryScopes,
    LangchainAgentConfig,
    WorkflowDefinition,
)
from geartrain.engine.loader import load_workflow
from geartrain.engine.sandbox import NoopSandbox
from geartrain.engine.state import FileStateBackend
from geartrain.memory.markdown import MarkdownMemoryStore
from geartrain.workflows.engine import WorkflowRunner
from tests.stub_chat_model import StubChatModel, tool_call_message


def _agent(name: str, tools: list[str], write_scopes: list[str]) -> AgentDefinition:
    return AgentDefinition(
        schema_version=1,
        name=name,
        config=LangchainAgentConfig(type="langchain", tools=tools),
        system_prompt="do work",
        memory=AgentMemoryScopes(read=["workspace"], write=write_scopes),
    )


def _langchain_runner(agent_def, stub, *, root, memory_store):
    return LangchainAgentRunner(
        agent_def,
        NoopSandbox(),
        llm=stub,
        tool_root=str(root),
        shell_cwd=str(root),
        memory_store=memory_store,
    )


def _two_node_workflow(tmp_path: Path) -> WorkflowDefinition:
    f = tmp_path / "obs.workflow.yaml"
    f.write_text(
        dedent(
            """\
            schema_version: 1
            name: obs-wf
            description: observability test workflow
            trigger:
              type: manual
            agents:
              coder: coder
              lead: lead
            graph:
              entry: run_coder
              nodes:
                run_coder:
                  type: agent
                  agent: coder
                  output_key: coder_output
                  transitions:
                    default: run_lead
                run_lead:
                  type: agent
                  agent: lead
                  output_key: lead_output
                  transitions:
                    default: end
            """
        )
    )
    return load_workflow(str(f))


def _failing_workflow(tmp_path: Path) -> WorkflowDefinition:
    """A workflow whose second node is an integration with no client."""
    f = tmp_path / "fail.workflow.yaml"
    f.write_text(
        dedent(
            """\
            schema_version: 1
            name: fail-wf
            description: failing workflow
            trigger:
              type: manual
            agents:
              coder: coder
            graph:
              entry: run_coder
              nodes:
                run_coder:
                  type: agent
                  agent: coder
                  output_key: coder_output
                  transitions:
                    default: open_pr
                open_pr:
                  type: integration
                  service: github
                  action: open_pr
                  transitions:
                    default: end
            """
        )
    )
    return load_workflow(str(f))


def seed_success_run(tmp_path: Path, run_id: str = "run-ok") -> FileStateBackend:
    """Run a coder→lead workflow that writes a file and a memory entry.

    The coder writes a file and a workspace memory entry; the lead reads the
    file. Returns the state backend holding the completed run.
    """
    state_path = tmp_path / "state"
    backend = FileStateBackend(state_path)
    memory_store = MarkdownMemoryStore(str(tmp_path / "memory"))

    coder_stub = StubChatModel(
        responses=[
            tool_call_message("file_write", {"path": "out.txt", "content": "hi"}, "c1"),
            tool_call_message(
                "memory_write",
                {"content": "remember this", "scope": "workspace"},
                "c2",
            ),
            AIMessage(content="coder done"),
        ]
    )
    lead_stub = StubChatModel(
        responses=[
            tool_call_message("file_read", {"path": "out.txt"}, "l1"),
            AIMessage(content="lead done"),
        ]
    )

    coder = _agent("coder", ["file_write", "memory_write"], ["workspace"])
    lead = _agent("lead", ["file_read"], [])
    agents = {
        "coder": _langchain_runner(coder, coder_stub, root=tmp_path, memory_store=memory_store),
        "lead": _langchain_runner(lead, lead_stub, root=tmp_path, memory_store=memory_store),
    }

    workflow = _two_node_workflow(tmp_path)
    runner = WorkflowRunner(workflow, agents, backend, state_path, work_dir=tmp_path / "work")
    runner.run(run_id, trigger_task="do the thing")
    return backend


def seed_memory_rejected_run(tmp_path: Path, run_id: str = "run-rejected") -> FileStateBackend:
    """Run a workflow whose coder attempts a write to a disallowed scope."""
    state_path = tmp_path / "state"
    backend = FileStateBackend(state_path)
    memory_store = MarkdownMemoryStore(str(tmp_path / "memory"))

    coder_stub = StubChatModel(
        responses=[
            tool_call_message(
                "memory_write",
                {"content": "secret plan", "scope": "workflow"},  # not allowed
                "c1",
            ),
            AIMessage(content="coder done"),
        ]
    )
    lead_stub = StubChatModel(responses=[AIMessage(content="lead done")])

    # Coder may write only workspace; it tries to write workflow → rejected.
    coder = _agent("coder", ["memory_write"], ["workspace"])
    lead = _agent("lead", [], [])
    agents = {
        "coder": _langchain_runner(coder, coder_stub, root=tmp_path, memory_store=memory_store),
        "lead": _langchain_runner(lead, lead_stub, root=tmp_path, memory_store=memory_store),
    }

    workflow = _two_node_workflow(tmp_path)
    runner = WorkflowRunner(workflow, agents, backend, state_path, work_dir=tmp_path / "work")
    runner.run(run_id, trigger_task="write memory")
    return backend


def seed_failed_run(tmp_path: Path, run_id: str = "run-failed") -> FileStateBackend:
    """Run a workflow that fails on an integration node with no client."""
    state_path = tmp_path / "state"
    backend = FileStateBackend(state_path)
    memory_store = MarkdownMemoryStore(str(tmp_path / "memory"))

    coder_stub = StubChatModel(responses=[AIMessage(content="coder done")])
    coder = _agent("coder", [], [])
    agents = {
        "coder": _langchain_runner(coder, coder_stub, root=tmp_path, memory_store=memory_store),
    }

    workflow = _failing_workflow(tmp_path)
    runner = WorkflowRunner(
        workflow, agents, backend, state_path, work_dir=tmp_path / "work", integrations={}
    )
    try:
        runner.run(run_id, trigger_task="fail please")
    except Exception:
        pass
    return backend


def seed_waiting_run(tmp_path: Path, run_id: str = "run-waiting") -> FileStateBackend:
    """Seed a running run with a waiting checkpoint (no execution needed)."""
    state_path = tmp_path / "state"
    backend = FileStateBackend(state_path)
    backend.create_run(run_id, "obs-wf")
    backend.update_run_status(run_id, "waiting", current_node="approve")
    backend.append_event(run_id, "node_start", {"node_id": "approve", "node_type": "human_checkpoint"})
    backend.write_checkpoint(
        run_id, "approve-cp", "approve", "Approve the change?", mode="approval"
    )
    backend.append_event(
        run_id, "checkpoint_created", {"node_id": "approve", "checkpoint_id": "approve-cp"}
    )
    return backend
