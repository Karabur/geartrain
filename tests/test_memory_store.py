"""Tests for the MemoryStore protocol, scopes, and MarkdownMemoryStore
(GT-P5-01, GT-P5-02, GT-P5-04)."""

import pytest

from geartrain.memory import (
    DEFAULT_READ_SCOPES,
    WRITABLE_SCOPES,
    MarkdownMemoryStore,
    MemoryRecord,
    MemoryScope,
    MemoryStore,
    MemorySystem,
    ScopeSpec,
    parse_scopes,
)


# --- protocol and scopes (GT-P5-01) -----------------------------------------


class TestProtocolAndScopes:
    def test_scope_enum_values(self):
        assert {s.value for s in MemoryScope} == {
            "workspace",
            "workflow",
            "agent_instance",
            "agent_level",
        }

    def test_system_enum_values(self):
        assert {s.value for s in MemorySystem} == {"memory", "knowledge"}

    def test_agent_instance_is_not_writable(self):
        # Instance memory lives in run state, not on disk.
        assert MemoryScope.AGENT_INSTANCE not in WRITABLE_SCOPES
        assert set(WRITABLE_SCOPES) == {
            MemoryScope.WORKSPACE,
            MemoryScope.WORKFLOW,
            MemoryScope.AGENT_LEVEL,
        }

    def test_markdown_store_satisfies_protocol(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        assert isinstance(store, MemoryStore)
        for method in ("write", "read", "update", "list_entries", "forget"):
            assert callable(getattr(store, method))

    def test_parse_scopes_coerces_strings(self):
        assert parse_scopes(["workspace", "workflow"]) == (
            MemoryScope.WORKSPACE,
            MemoryScope.WORKFLOW,
        )

    def test_parse_scopes_rejects_unknown(self):
        with pytest.raises(ValueError):
            parse_scopes(["nonsense"])


# --- round trip (GT-P5-02) --------------------------------------------------


class TestRoundTrip:
    def test_write_read_update_list_forget(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)

        result = store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="Always run black before committing python.",
            category="formatting",
            tags=["python", "style"],
        )
        assert result.ok
        assert result.path

        # Retrieve by keyword.
        found = store.read(
            "black python",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        )
        assert len(found) == 1
        assert "black" in found[0].content
        assert found[0].tags == ["python", "style"]
        assert found[0].score > 0

        # Update in place.
        updated = store.update(
            result.path, content="Run ruff format before committing python."
        )
        assert updated.ok
        again = store.read(
            "ruff",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        )
        assert "ruff" in again[0].content

        # List by scope.
        listed = store.list_entries(
            system=MemorySystem.MEMORY, scope=MemoryScope.WORKSPACE
        )
        assert len(listed) == 1

        # Soft-delete drops it from reads and lists by default.
        assert store.forget(result.path) is True
        assert store.read(
            "ruff",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        ) == []
        assert store.list_entries(
            system=MemorySystem.MEMORY, scope=MemoryScope.WORKSPACE
        ) == []
        # The file still exists for git review.
        assert store.list_entries(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            include_forgotten=True,
        )

    def test_ranking_orders_by_relevance(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="testing pytest fixtures and pytest markers and pytest",
        )
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="a single mention of pytest here",
        )
        ranked = store.read(
            "pytest",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        )
        assert len(ranked) == 2
        assert ranked[0].score > ranked[1].score

    def test_empty_query_returns_entries(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="anything",
        )
        results = store.read(
            "",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        )
        assert len(results) == 1

    def test_write_returns_event_metadata(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        result = store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKFLOW,
            namespace="geartrain-dev",
            content="prefer small commits",
            source_run="run-1",
            source_node="implement",
            source_agent="developer",
        )
        meta = result.to_metadata()
        assert meta["scope"] == "workflow"
        assert meta["source_run"] == "run-1"
        assert meta["source_node"] == "implement"
        assert meta["source_agent"] == "developer"
        assert meta["review_status"] == "unreviewed"
        assert meta["guardrail"] == {"ok": True, "findings": []}


# --- scope isolation and visibility (GT-P5-04) ------------------------------


class TestScopeIsolation:
    def test_scopes_stored_in_separate_directories(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="workspace note",
        )
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKFLOW,
            namespace="dev",
            content="workflow note",
        )
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.AGENT_LEVEL,
            namespace="lead",
            content="agent note",
        )
        base = tmp_path / "memory"
        assert (base / "workspace").is_dir()
        assert (base / "workflow" / "dev").is_dir()
        assert (base / "agent" / "lead").is_dir()

    def test_agent_level_isolated_by_agent_type(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.AGENT_LEVEL,
            namespace="lead",
            content="lead remembers the plan",
        )
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.AGENT_LEVEL,
            namespace="developer",
            content="developer remembers the API",
        )
        lead = store.read(
            "remembers",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.AGENT_LEVEL, "lead")],
        )
        assert len(lead) == 1
        assert "plan" in lead[0].content

    def test_memory_and_knowledge_kept_apart(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="memory entry about caching",
        )
        store.write(
            system=MemorySystem.KNOWLEDGE,
            scope=MemoryScope.WORKSPACE,
            content="knowledge entry about caching",
        )
        mem = store.read(
            "caching",
            system=MemorySystem.MEMORY,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        )
        kb = store.read(
            "caching",
            system=MemorySystem.KNOWLEDGE,
            scopes=[ScopeSpec(MemoryScope.WORKSPACE)],
        )
        assert len(mem) == 1 and "memory entry" in mem[0].content
        assert len(kb) == 1 and "knowledge entry" in kb[0].content

    def test_read_across_scopes_ranks_together(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.WORKSPACE,
            content="deploy uses docker deploy docker",
        )
        store.write(
            system=MemorySystem.MEMORY,
            scope=MemoryScope.AGENT_LEVEL,
            namespace="ops",
            content="deploy once",
        )
        results = store.read(
            "deploy docker",
            system=MemorySystem.MEMORY,
            scopes=[
                ScopeSpec(MemoryScope.WORKSPACE),
                ScopeSpec(MemoryScope.AGENT_LEVEL, "ops"),
            ],
        )
        assert len(results) == 2
        assert results[0].scope == MemoryScope.WORKSPACE

    def test_agent_instance_scope_not_persisted(self, tmp_path):
        store = MarkdownMemoryStore(tmp_path)
        with pytest.raises(ValueError, match="run state"):
            store.write(
                system=MemorySystem.MEMORY,
                scope=MemoryScope.AGENT_INSTANCE,
                content="ephemeral",
            )


def test_default_read_scopes_cover_persisted_scopes():
    assert set(DEFAULT_READ_SCOPES) == set(WRITABLE_SCOPES)


def test_record_metadata_shape(tmp_path):
    store = MarkdownMemoryStore(tmp_path)
    store.write(
        system=MemorySystem.MEMORY,
        scope=MemoryScope.WORKSPACE,
        content="note",
        category="cat",
    )
    rec = store.list_entries(
        system=MemorySystem.MEMORY, scope=MemoryScope.WORKSPACE
    )[0]
    assert isinstance(rec, MemoryRecord)
    meta = rec.to_metadata()
    assert meta["scope"] == "workspace"
    assert meta["category"] == "cat"
    assert meta["system"] == "memory"
