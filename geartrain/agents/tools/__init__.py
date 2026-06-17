"""Tool registry — builds langchain tools from config name strings.

Agents list tools by name (``file_read``, ``shell_exec``, ``git_commit``, …).
``build_tools`` binds each to a sandbox, the tool root, the agent's forbidden
paths, and shell settings, and records every call into a shared recorder.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Sequence

from geartrain.agents.tools import files, memory as memory_tools, shell
from geartrain.agents.tools.base import (
    ToolEvent,
    ToolRecorder,
    ToolResult,
    build_tool,
)
from geartrain.memory.store import MemorySystem

if TYPE_CHECKING:
    from langchain_core.tools import StructuredTool

    from geartrain.agents.tools.memory import MemoryToolDeps
    from geartrain.engine.sandbox import Sandbox

__all__ = [
    "ToolEvent",
    "ToolRecorder",
    "ToolResult",
    "build_tools",
    "available_tools",
]

_MEMORY_TOOLS = ("memory_read", "memory_write", "kb_read", "kb_write")


def available_tools() -> list[str]:
    """Return the names of every tool the registry can build."""
    return [
        "file_read",
        "file_write",
        "project_search",
        "shell_exec",
        "git_status",
        "git_diff",
        "git_commit",
        "git_branch",
        *_MEMORY_TOOLS,
    ]


def build_tools(
    names: Sequence[str],
    *,
    sandbox: "Sandbox",
    recorder: ToolRecorder,
    root: str = ".",
    forbidden_paths: Sequence[str] = (),
    shell_cwd: str = ".",
    shell_timeout: int = 60,
    memory: "MemoryToolDeps | None" = None,
) -> list["StructuredTool"]:
    """Build the named tools, each bound to *sandbox* and recording to *recorder*.

    Pass *memory* to enable the ``memory_*`` and ``kb_*`` tools; without it,
    requesting one raises ``ValueError``. Also raises ``ValueError`` for an
    unknown tool name.
    """
    file_deps = {
        "sandbox": sandbox,
        "root": root,
        "forbidden_paths": tuple(forbidden_paths),
    }
    shell_deps = {
        "sandbox": sandbox,
        "cwd": shell_cwd,
        "timeout": shell_timeout,
    }

    specs = {
        "file_read": (
            "Read a file from the project and return its contents.",
            partial(files.file_read, **file_deps),
            files.FileReadArgs,
        ),
        "file_write": (
            "Write contents to a file in the project, creating it if needed.",
            partial(files.file_write, **file_deps),
            files.FileWriteArgs,
        ),
        "project_search": (
            "Search the project's files for a regular expression.",
            partial(files.project_search, **file_deps),
            files.ProjectSearchArgs,
        ),
        "shell_exec": (
            "Run a shell command in the project working directory.",
            partial(shell.shell_exec, **shell_deps),
            shell.ShellExecArgs,
        ),
        "git_status": (
            "Show the git working tree status.",
            partial(shell.git_status, **shell_deps),
            shell._NoArgs,
        ),
        "git_diff": (
            "Show the git diff of current changes.",
            partial(shell.git_diff, **shell_deps),
            shell._NoArgs,
        ),
        "git_commit": (
            "Stage all changes and create a git commit.",
            partial(shell.git_commit, **shell_deps),
            shell.GitCommitArgs,
        ),
        "git_branch": (
            "Create and switch to a git branch, or list branches.",
            partial(shell.git_branch, **shell_deps),
            shell.GitBranchArgs,
        ),
    }

    if memory is not None:
        specs.update(_memory_specs(memory))

    built: list["StructuredTool"] = []
    for name in names:
        if name not in specs:
            if name in _MEMORY_TOOLS:
                raise ValueError(
                    f"tool {name!r} needs memory deps; pass memory= to build it"
                )
            raise ValueError(
                f"unknown tool {name!r}; available tools: {sorted(specs)}"
            )
        description, func, args_schema = specs[name]
        built.append(build_tool(name, description, func, args_schema, recorder))
    return built


def _memory_specs(memory: "MemoryToolDeps") -> dict:
    """Tool specs for the memory and knowledge tools, bound to *memory*."""
    return {
        "memory_read": (
            "Search the agent's memory for entries matching keywords.",
            partial(
                memory_tools.memory_read,
                deps=memory,
                system=MemorySystem.MEMORY,
            ),
            memory_tools.MemoryReadArgs,
        ),
        "memory_write": (
            "Store a memory entry in one of the agent's writable scopes.",
            partial(
                memory_tools.memory_write,
                deps=memory,
                system=MemorySystem.MEMORY,
            ),
            memory_tools.MemoryWriteArgs,
        ),
        "kb_read": (
            "Search the knowledge base for entries matching keywords.",
            partial(
                memory_tools.memory_read,
                deps=memory,
                system=MemorySystem.KNOWLEDGE,
            ),
            memory_tools.MemoryReadArgs,
        ),
        "kb_write": (
            "Store a knowledge-base entry in one of the agent's writable scopes.",
            partial(
                memory_tools.memory_write,
                deps=memory,
                system=MemorySystem.KNOWLEDGE,
            ),
            memory_tools.MemoryWriteArgs,
        ),
    }
