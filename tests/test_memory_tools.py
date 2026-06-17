"""Tests for memory and knowledge tools and their wiring (GT-P5-03, GT-P5-06)."""

import pytest
from langchain_core.messages import AIMessage

from geartrain.agents.langchain_runner import LangchainAgentRunner
from geartrain.agents.tools import ToolRecorder, build_tools
from geartrain.agents.tools.memory import (
    MemoryToolDeps,
    memory_read,
    memory_write,
)
from geartrain.engine.config import (
    AgentDefinition,
    AgentMemoryScopes,
    LangchainAgentConfig,
)
from geartrain.engine.sandbox import NoopSandbox
from geartrain.memory import (
    MarkdownMemoryStore,
    MemoryScope,
    MemorySystem,
    ScopeSpec,
)
from tests.stub_chat_model import StubChatModel, tool_call_message


def _deps(store, *, read=(), write=(), **kw):
    return MemoryToolDeps(
        store=store,
        read_scopes=read,
        write_scopes=write,
        **kw,
    )


# --- core tool functions (GT-P5-03) -----------------------------------------


class TestMemoryToolFunctions:
    def test_write_then_read_round_trips(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        deps = _deps(
            store,
            read=(MemoryScope.WORKSPACE,),
            write=(MemoryScope.WORKSPACE,),
            source_run="run-1",
            source_node="implement",
            source_agent="developer",
        )

        write = memory_write(
            content="prefer dependency injection",
            scope="workspace",
            category="design",
            deps=deps,
            system=MemorySystem.MEMORY,
        )
        assert write.status == "ok"
        # Write result exposes event-friendly metadata.
        assert write.metadata["scope"] == "workspace"
        assert write.metadata["path"]
        assert write.metadata["source_run"] == "run-1"
        assert write.metadata["source_node"] == "implement"
        assert write.metadata["source_agent"] == "developer"
        assert write.metadata["review_status"] == "unreviewed"
        assert write.metadata["guardrail"]["ok"] is True

        read = memory_read(
            query="dependency injection",
            deps=deps,
            system=MemorySystem.MEMORY,
        )
        assert read.status == "ok"
        assert "dependency injection" in read.output
        assert read.metadata["count"] == 1
        assert read.metadata["scopes"] == ["workspace"]
        assert read.metadata["paths"]

    def test_write_to_disallowed_scope_rejected(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        deps = _deps(store, write=(MemoryScope.AGENT_LEVEL,), agent_type="dev")

        result = memory_write(
            content="should not land",
            scope="workspace",
            deps=deps,
            system=MemorySystem.MEMORY,
        )
        assert result.status == "error"
        assert result.error == "scope_not_allowed"
        # Rejected write still exposes event-friendly metadata.
        assert result.metadata["scope"] == "workspace"
        assert result.metadata["allowed_scopes"] == ["agent_level"]
        assert "agent_level" in result.output
        # Nothing was written anywhere.
        assert store.list_entries(
            system=MemorySystem.MEMORY, scope=MemoryScope.WORKSPACE
        ) == []

    def test_write_with_secret_reports_guardrail(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        deps = _deps(store, write=(MemoryScope.WORKSPACE,))
        result = memory_write(
            content="key is AKIAIOSFODNN7EXAMPLE",
            scope="workspace",
            deps=deps,
            system=MemorySystem.MEMORY,
        )
        assert result.status == "error"
        assert result.error == "guardrail"
        assert result.metadata["guardrail"]["ok"] is False

    def test_unknown_scope_rejected(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        deps = _deps(store, write=(MemoryScope.WORKSPACE,))
        result = memory_write(
            content="x", scope="nonsense", deps=deps, system=MemorySystem.MEMORY
        )
        assert result.status == "error"
        assert result.error == "unknown_scope"

    def test_kb_and_memory_are_separate_systems(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        deps = _deps(
            store,
            read=(MemoryScope.WORKSPACE,),
            write=(MemoryScope.WORKSPACE,),
        )
        memory_write(
            content="memory fact about retries",
            scope="workspace",
            deps=deps,
            system=MemorySystem.MEMORY,
        )
        kb = memory_read(
            query="retries", deps=deps, system=MemorySystem.KNOWLEDGE
        )
        assert kb.metadata["count"] == 0
        assert "no knowledge entries" in kb.output


# --- registry wiring --------------------------------------------------------


class TestRegistryWiring:
    def test_memory_tool_needs_deps(self, tmp_path):
        with pytest.raises(ValueError, match="needs memory deps"):
            build_tools(
                ["memory_write"],
                sandbox=NoopSandbox(),
                recorder=ToolRecorder(),
                root=str(tmp_path),
            )

    def test_builds_memory_tools_with_deps(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        deps = _deps(store, write=(MemoryScope.WORKSPACE,))
        tools = build_tools(
            ["memory_read", "memory_write", "kb_read", "kb_write"],
            sandbox=NoopSandbox(),
            recorder=ToolRecorder(),
            root=str(tmp_path),
            memory=deps,
        )
        assert {t.name for t in tools} == {
            "memory_read",
            "memory_write",
            "kb_read",
            "kb_write",
        }


# --- end to end through the agent (GT-P5-06) --------------------------------


class TestLangchainAgentMemory:
    def test_agent_writes_memory_a_later_run_retrieves(self, tmp_path):
        """A langchain agent writes a memory; reading the store later finds it."""
        store = MarkdownMemoryStore(tmp_path)
        agent_def = AgentDefinition(
            schema_version=1,
            name="developer",
            config=LangchainAgentConfig(
                type="langchain", tools=["memory_write"]
            ),
            memory=AgentMemoryScopes(
                read=["workspace"], write=["workspace"]
            ),
        )
        stub = StubChatModel(
            responses=[
                tool_call_message(
                    "memory_write",
                    {
                        "content": "the build cache lives in .geartrain/cache",
                        "scope": "workspace",
                        "category": "build",
                        "tags": ["cache"],
                    },
                ),
                AIMessage(content="noted"),
            ]
        )
        runner = LangchainAgentRunner(
            agent_def,
            NoopSandbox(),
            llm=stub,
            memory_store=store,
        )

        output = runner.run("remember where the cache lives", {"run_id": "r1"})
        assert output == "noted"

        # A later run (fresh read) retrieves what the agent wrote.
        found = store.read(
            "build cache",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        )
        assert len(found) == 1
        assert ".geartrain/cache" in found[0].content
        assert found[0].source_run == "r1"
        assert found[0].source_agent == "developer"

    def test_no_store_means_no_memory_tools(self, tmp_path):
        """Without a store, requesting a memory tool fails at build time."""
        agent_def = AgentDefinition(
            schema_version=1,
            name="developer",
            config=LangchainAgentConfig(
                type="langchain", tools=["memory_write"]
            ),
            memory=AgentMemoryScopes(write=["workspace"]),
        )
        runner = LangchainAgentRunner(
            agent_def,
            NoopSandbox(),
            llm=StubChatModel(responses=[AIMessage(content="x")]),
        )
        with pytest.raises(ValueError, match="needs memory deps"):
            runner.run("do it", {})
