"""GitHub tools — branch, commit, PR, and issue operations for agents.

Each core function wraps a :class:`~geartrain.integrations.github.GitHubClient`
call, returning a :class:`ToolResult`. A ``GitHubError`` becomes an error
result (with detail in ``metadata``) so the agent can react and a human can
finish the step by hand. The registry binds the client via ``functools.partial``
before the tools reach the model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from geartrain.agents.tools.base import ToolResult
from geartrain.integrations.github import GitHubError

if TYPE_CHECKING:
    from geartrain.integrations.github import GitHubClient


def _error(action: str, exc: GitHubError) -> ToolResult:
    """Shape a GitHubError into an error ToolResult."""
    return ToolResult(
        output=f"github {action} failed: {exc}",
        status="error",
        error=str(exc),
        metadata={"status_code": exc.status_code},
    )


# --- github_create_branch ---------------------------------------------------


class GitHubBranchArgs(BaseModel):
    name: str = Field(description="Name of the branch to create.")
    base: str = Field(default="main", description="Branch to fork from.")


def github_create_branch(
    *, name: str, base: str = "main", client: "GitHubClient"
) -> ToolResult:
    """Create a branch from a base branch."""
    try:
        result = client.create_branch(name, base=base)
    except GitHubError as exc:
        return _error("create_branch", exc)
    return ToolResult(
        output=f"created branch {name!r} from {base!r}", metadata=result
    )


# --- github_commit ----------------------------------------------------------


class GitHubCommitArgs(BaseModel):
    branch: str = Field(description="Branch to commit onto.")
    path: str = Field(description="Repository path of the file to write.")
    content: str = Field(description="Full new contents of the file.")
    message: str = Field(description="Commit message.")


def github_commit(
    *, branch: str, path: str, content: str, message: str, client: "GitHubClient"
) -> ToolResult:
    """Commit a single file onto a branch."""
    try:
        result = client.commit_files(branch, {path: content}, message)
    except GitHubError as exc:
        return _error("commit", exc)
    return ToolResult(
        output=f"committed {path!r} to {branch!r} ({result['commit'][:7]})",
        metadata=result,
    )


# --- github_create_pr -------------------------------------------------------


class GitHubPullRequestArgs(BaseModel):
    title: str = Field(description="Pull request title.")
    head: str = Field(description="Branch with the changes.")
    base: str = Field(default="main", description="Branch to merge into.")
    body: str = Field(default="", description="Pull request description.")


def github_create_pr(
    *, title: str, head: str, base: str = "main", body: str = "", client: "GitHubClient"
) -> ToolResult:
    """Open a pull request."""
    try:
        result = client.create_pull_request(
            title=title, head=head, base=base, body=body
        )
    except GitHubError as exc:
        return _error("create_pr", exc)
    return ToolResult(
        output=f"opened PR #{result['number']}: {result['url']}",
        metadata=result,
    )


# --- github_get_issue -------------------------------------------------------


class GitHubGetIssueArgs(BaseModel):
    number: int = Field(description="Issue number to read.")


def github_get_issue(*, number: int, client: "GitHubClient") -> ToolResult:
    """Read an issue's title, body, labels, assignee, and state."""
    try:
        issue = client.get_issue(number)
    except GitHubError as exc:
        return _error("get_issue", exc)
    labels = ", ".join(issue["labels"]) or "none"
    output = (
        f"#{issue['number']} [{issue['state']}] {issue['title']}\n"
        f"labels: {labels}\n"
        f"assignee: {issue['assignee'] or 'none'}\n\n"
        f"{issue['body']}"
    )
    return ToolResult(output=output, metadata=issue)


# --- github_update_issue ----------------------------------------------------


class GitHubUpdateIssueArgs(BaseModel):
    number: int = Field(description="Issue number to update.")
    state: str | None = Field(
        default=None, description="New state: 'open' or 'closed'."
    )
    labels: list[str] | None = Field(
        default=None, description="Replacement label set."
    )


def github_update_issue(
    *,
    number: int,
    state: str | None = None,
    labels: list[str] | None = None,
    client: "GitHubClient",
) -> ToolResult:
    """Update an issue's state and/or labels."""
    try:
        issue = client.update_issue(number, state=state, labels=labels)
    except GitHubError as exc:
        return _error("update_issue", exc)
    return ToolResult(
        output=f"updated issue #{issue['number']} (state: {issue['state']})",
        metadata=issue,
    )
