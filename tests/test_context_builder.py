"""Tests for the shared context builder (GT-P2-02)."""

from geartrain.agents.context_builder import ContextBuilder


class TestContextBuilderBasic:
    def test_build_with_only_task(self):
        builder = ContextBuilder(
            project_root="/app",
            project_name="MyProject",
        )
        prompt = builder.with_task("Fix the login bug").build()

        assert "# Task" in prompt
        assert "Fix the login bug" in prompt
        assert "# Project Context" in prompt
        assert "**Project**: MyProject" in prompt
        assert "**Root**: /app" in prompt
        assert "# Prior Output" not in prompt
        assert "# Memory" not in prompt

    def test_build_with_all_sections(self):
        builder = ContextBuilder(
            project_root="/app",
            project_name="MyProject",
            work_folder="work",
        )
        builder.with_task("Implement feature X")
        builder.with_agent_instructions("You are a coder.")
        builder.with_prior_output("intake", "Approved: implement feature X")
        builder.with_memory_entries(
            "workspace", ["Memory entry 1", "Memory entry 2"]
        )
        builder.with_docs(["docs/api.md", "docs/arch.md"])
        builder.with_tool_instructions("Use git for version control.")

        prompt = builder.build()

        assert "# Agent Instructions" in prompt
        assert "You are a coder." in prompt
        assert "# Task" in prompt
        assert "Implement feature X" in prompt
        assert "**Work folder**: work" in prompt
        assert "## intake" in prompt
        assert "Approved: implement feature X" in prompt
        assert "## workspace" in prompt
        assert "Memory entry 1" in prompt
        assert "Memory entry 2" in prompt
        assert "docs/api.md" in prompt
        assert "Use git for version control" in prompt

    def test_empty_build_has_project_context(self):
        builder = ContextBuilder(
            project_root="/app",
            project_name="MyProject",
        )
        prompt = builder.build()

        assert "# Project Context" in prompt
        assert "**Project**: MyProject" in prompt

    def test_multiple_prior_outputs(self):
        builder = ContextBuilder(project_root="/app", project_name="X")
        builder.with_prior_output("node-1", "Output one")
        builder.with_prior_output("node-2", "Output two")

        prompt = builder.build()

        assert "## node-1" in prompt
        assert "Output one" in prompt
        assert "## node-2" in prompt
        assert "Output two" in prompt

    def test_multiple_memory_scopes(self):
        builder = ContextBuilder(project_root="/app", project_name="X")
        builder.with_memory_entries("workspace", ["ws-entry"])
        builder.with_memory_entries("workflow", ["wf-entry"])

        prompt = builder.build()

        assert "## workspace" in prompt
        assert "## workflow" in prompt
        assert "ws-entry" in prompt
        assert "wf-entry" in prompt

    def test_unset_sections_omitted(self):
        builder = ContextBuilder(project_root="/app", project_name="X")
        builder.with_task("do something")

        prompt = builder.build()

        assert "# Agent Instructions" not in prompt
        assert "# Prior Output" not in prompt
        assert "# Memory" not in prompt
        assert "# References" not in prompt
        assert "# Tool Instructions" not in prompt

    def test_work_folder_none_omitted(self):
        builder = ContextBuilder(
            project_root="/app",
            project_name="X",
            work_folder=None,
        )
        prompt = builder.build()

        assert "Work folder" not in prompt
