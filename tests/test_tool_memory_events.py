"""Tests for tool-call and memory-update events (GT-P7-03, GT-P7-04)."""

from pathlib import Path

from tests.observability_helpers import (
    seed_memory_rejected_run,
    seed_success_run,
)


def _events_of_type(backend, run_id, etype):
    return [e for e in backend.read_events(run_id) if e["type"] == etype]


class TestToolCallEvents:
    def test_successful_tool_calls_recorded(self, tmp_path):
        backend = seed_success_run(tmp_path, "run-ok")
        calls = _events_of_type(backend, "run-ok", "tool_call")
        names = [c["name"] for c in calls]
        assert names == ["file_write", "memory_write", "file_read"]
        # Each carries category, node, attempt, duration, and a summary.
        write = calls[0]
        assert write["kind"] == "file"
        assert write["node_id"] == "run_coder"
        assert write["attempt_id"] == "run_coder#1"
        assert write["status"] == "ok"
        assert "duration_ms" in write
        assert write["summary"]

    def test_failed_tool_call_recorded(self, tmp_path):
        backend = seed_memory_rejected_run(tmp_path, "run-rej")
        calls = _events_of_type(backend, "run-rej", "tool_call")
        assert len(calls) == 1
        assert calls[0]["name"] == "memory_write"
        assert calls[0]["status"] == "error"

    def test_tool_events_do_not_leak_full_content(self, tmp_path):
        """The file_write input summary names the arg but not via a secret dump."""
        backend = seed_success_run(tmp_path, "run-ok")
        calls = _events_of_type(backend, "run-ok", "tool_call")
        write = calls[0]
        # Summaries are present and bounded; no raw payload key leaks.
        assert "content" in write["input_summary"]  # arg name shown
        assert len(write["summary"]) <= 201


class TestMemoryEvents:
    def test_memory_write_event_has_source_metadata(self, tmp_path):
        backend = seed_success_run(tmp_path, "run-ok")
        writes = _events_of_type(backend, "run-ok", "memory_write")
        assert len(writes) == 1
        ev = writes[0]
        assert ev["scope"] == "workspace"
        assert ev["system"] == "memory"
        assert ev["source_run"] == "run-ok"
        assert ev["source_node"] == "run_coder"
        assert ev["source_agent"] == "coder"
        assert ev["path"]  # links to the written entry

    def test_rejected_write_event_has_safe_reason(self, tmp_path):
        backend = seed_memory_rejected_run(tmp_path, "run-rej")
        rejected = _events_of_type(backend, "run-rej", "memory_write_rejected")
        assert len(rejected) == 1
        ev = rejected[0]
        assert ev["scope"] == "workflow"
        assert ev["reason"]  # e.g. scope_not_allowed
        assert ev["source_run"] == "run-rej"
        # A rejection carries no written path and no entry content.
        assert ev.get("path", "") == ""

    def test_memory_read_event_recorded(self, tmp_path):
        """A read tool call appends a memory_read event with the query."""
        from langchain_core.messages import AIMessage

        from geartrain.engine.config import (
            AgentDefinition,
            AgentMemoryScopes,
            LangchainAgentConfig,
        )
        from geartrain.engine.sandbox import NoopSandbox
        from geartrain.memory.markdown import MarkdownMemoryStore
        from geartrain.workflows.nodes import AgentNodeRunner
        from geartrain.agents.langchain_runner import LangchainAgentRunner
        from tests.stub_chat_model import StubChatModel, tool_call_message

        store = MarkdownMemoryStore(str(tmp_path / "memory"))
        stub = StubChatModel(
            responses=[
                tool_call_message("memory_read", {"query": "anything"}, "r1"),
                AIMessage(content="done"),
            ]
        )
        agent = AgentDefinition(
            schema_version=1,
            name="reader",
            config=LangchainAgentConfig(type="langchain", tools=["memory_read"]),
            memory=AgentMemoryScopes(read=["workspace"], write=[]),
        )
        runner = LangchainAgentRunner(
            agent, NoopSandbox(), llm=stub, memory_store=store
        )

        seen = []
        node = AgentNodeRunner(
            {"reader": runner},
            event_sink=lambda etype, **d: seen.append((etype, d)),
            attempt_id="n#1",
        )
        node.run(
            {"agent": "reader", "transitions": {}},
            {"task": "go", "run_id": "r", "node_id": "n"},
        )

        reads = [d for etype, d in seen if etype == "memory_read"]
        assert len(reads) == 1
        assert reads[0]["query"] == "anything"
        assert reads[0]["attempt_id"] == "n#1"
