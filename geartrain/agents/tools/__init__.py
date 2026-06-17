"""Tool registry — builds langchain tools from config name strings.

Agents list tools by name (``file_read``, ``shell_exec``, ``git_commit``, …).
``build_tools`` binds each to a sandbox, the tool root, the agent's forbidden
paths, and shell settings, and records every call into a shared recorder.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Sequence

from geartrain.agents.tools import files, shell
from geartrain.agents.tools.base import (
    ToolEvent,
    ToolRecorder,
    ToolResult,
    build_tool,
)

if TYPE_CHECKING:
    from langchain_core.tools import StructuredTool

    from geartrain.engine.sandbox import Sandbox

__all__ = [
    "ToolEvent",
    "ToolRecorder",
    "ToolResult",
    "build_tools",
    "available_tools",
]


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
) -> list["StructuredTool"]:
    """Build the named tools, each bound to *sandbox* and recording to *recorder*.

    Raises ``ValueError`` for an unknown tool name.
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

    built: list["StructuredTool"] = []
    for name in names:
        if name not in specs:
            raise ValueError(
                f"unknown tool {name!r}; available tools: {sorted(specs)}"
            )
        description, func, args_schema = specs[name]
        built.append(build_tool(name, description, func, args_schema, recorder))
    return built
