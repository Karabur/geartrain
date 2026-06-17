"""Context builder — assembles prompt context from workspace, agent, and run state."""

from __future__ import annotations


class ContextBuilder:
    """Assembles prompt context from multiple sources into a structured prompt.

    Builds the prompt that gets fed to an agent (cli or langchain).
    Uses a fluent builder pattern — with_* methods return self for chaining.
    """

    def __init__(
        self,
        project_root: str,
        project_name: str,
        work_folder: str | None = None,
    ):
        self.project_root = project_root
        self.project_name = project_name
        self.work_folder = work_folder
        self._task: str = ""
        self._agent_instructions: str = ""
        self._prior_outputs: list[tuple[str, str]] = []
        self._memory_entries: list[tuple[str, list[str]]] = []
        self._docs: list[str] = []
        self._tool_instructions: str = ""

    def with_task(self, task: str) -> ContextBuilder:
        """Set the task input (user prompt)."""
        self._task = task
        return self

    def with_agent_instructions(self, instructions: str) -> ContextBuilder:
        """Set agent system prompt / instructions."""
        self._agent_instructions = instructions
        return self

    def with_prior_output(self, node_id: str, output: str) -> ContextBuilder:
        """Add output from a prior workflow node."""
        self._prior_outputs.append((node_id, output))
        return self

    def with_memory_entries(
        self, scope: str, entries: list[str]
    ) -> ContextBuilder:
        """Add memory entries from a scope."""
        self._memory_entries.append((scope, entries))
        return self

    def with_docs(self, paths: list[str]) -> ContextBuilder:
        """Add documentation references."""
        self._docs.extend(paths)
        return self

    def with_tool_instructions(self, instructions: str) -> ContextBuilder:
        """Add tool-specific instructions."""
        self._tool_instructions = instructions
        return self

    def build(self) -> str:
        """Assemble all sections into the final prompt string.

        Only sections that were set are included. Empty sections are skipped.
        """
        sections: list[str] = []

        if self._agent_instructions:
            sections.append(
                f"# Agent Instructions\n\n{self._agent_instructions}"
            )

        if self._task:
            sections.append(f"# Task\n\n{self._task}")

        sections.append(
            "# Project Context\n\n"
            f"- **Project**: {self.project_name}\n"
            f"- **Root**: {self.project_root}"
            + (
                f"\n- **Work folder**: {self.work_folder}"
                if self.work_folder
                else ""
            )
        )

        if self._prior_outputs:
            prior = []
            for node_id, output in self._prior_outputs:
                prior.append(f"## {node_id}\n\n{output}")
            sections.append("# Prior Output\n\n" + "\n\n".join(prior))

        if self._memory_entries:
            mem_parts = []
            for scope, entries in self._memory_entries:
                mem_parts.append(f"## {scope}\n\n" + "\n\n".join(entries))
            sections.append("# Memory\n\n" + "\n\n".join(mem_parts))

        if self._docs:
            sections.append(
                "# References\n\n" + "\n".join(f"- {p}" for p in self._docs)
            )

        if self._tool_instructions:
            sections.append(
                f"# Tool Instructions\n\n{self._tool_instructions}"
            )

        return "\n\n---\n\n".join(sections)
