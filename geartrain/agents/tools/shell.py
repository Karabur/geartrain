"""Shell and git tools, all routed through the sandbox.

``shell_exec`` runs an arbitrary command; the git helpers wrap common
porcelain. Every command goes through ``Sandbox.execute_command`` so a real
sandbox can enforce limits later. A non-zero exit becomes an error result with
the captured stderr, not an exception.
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from geartrain.agents.tools.base import ToolResult

if TYPE_CHECKING:
    from geartrain.engine.sandbox import Sandbox


def _run(
    command: str, sandbox: "Sandbox", cwd: str, timeout: int
) -> ToolResult:
    """Run *command* through the sandbox and shape the output into a ToolResult."""
    stdout, stderr, returncode = sandbox.execute_command(
        command, cwd=cwd, timeout=timeout
    )
    if returncode != 0:
        detail = stderr.strip() or stdout.strip() or "(no output)"
        return ToolResult(
            output=f"command failed (exit {returncode}): {detail}",
            status="error",
            error=f"exit {returncode}: {stderr.strip()}",
        )
    return ToolResult(output=stdout if stdout else "(no output)")


# --- shell_exec -------------------------------------------------------------


class ShellExecArgs(BaseModel):
    command: str = Field(description="Shell command to run in the project working directory.")


def shell_exec(
    *,
    command: str,
    sandbox: "Sandbox",
    cwd: str,
    timeout: int,
) -> ToolResult:
    """Run a shell command through the sandbox."""
    return _run(command, sandbox, cwd, timeout)


# --- git helpers ------------------------------------------------------------


class _NoArgs(BaseModel):
    pass


def git_status(*, sandbox: "Sandbox", cwd: str, timeout: int) -> ToolResult:
    """Show the working tree status in short form."""
    result = _run("git status --short --branch", sandbox, cwd, timeout)
    if result.status == "ok" and result.output == "(no output)":
        return ToolResult(output="working tree clean")
    return result


def git_diff(*, sandbox: "Sandbox", cwd: str, timeout: int) -> ToolResult:
    """Show unstaged and staged changes."""
    return _run("git diff HEAD", sandbox, cwd, timeout)


class GitCommitArgs(BaseModel):
    message: str = Field(description="Commit message.")


def git_commit(
    *, message: str, sandbox: "Sandbox", cwd: str, timeout: int
) -> ToolResult:
    """Stage all changes and create a commit."""
    staged = _run("git add -A", sandbox, cwd, timeout)
    if staged.status == "error":
        return staged
    return _run(f"git commit -m {shlex.quote(message)}", sandbox, cwd, timeout)


class GitBranchArgs(BaseModel):
    name: str | None = Field(
        default=None,
        description="Branch to create and switch to. Omit to list branches.",
    )


def git_branch(
    *,
    name: str | None = None,
    sandbox: "Sandbox",
    cwd: str,
    timeout: int,
) -> ToolResult:
    """Create and switch to a branch, or list branches when no name is given."""
    if name:
        return _run(f"git checkout -b {shlex.quote(name)}", sandbox, cwd, timeout)
    return _run("git branch", sandbox, cwd, timeout)
