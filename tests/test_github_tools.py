"""Tests for the GitHub agent tools and registry wiring (GT-P6-03)."""

from __future__ import annotations

import pytest

from geartrain.agents.tools import (
    ToolRecorder,
    available_tools,
    build_tools,
)
from geartrain.integrations.github import GitHubClient, GitHubError
from tests.github_fakes import FakeTransport, err, ok


class StubSandbox:
    """Sandbox stand-in; the github tools never touch it."""


def _client(responses) -> GitHubClient:
    return GitHubClient("octo", "repo", "tok", transport=FakeTransport(responses))


def _build(names, client, recorder=None):
    return build_tools(
        names,
        sandbox=StubSandbox(),
        recorder=recorder or ToolRecorder(),
        github=client,
    )


class TestRegistry:
    def test_github_tools_listed_as_available(self):
        names = available_tools()
        for tool in (
            "github_create_branch",
            "github_commit",
            "github_create_pr",
            "github_get_issue",
            "github_update_issue",
        ):
            assert tool in names

    def test_requesting_github_tool_without_client_raises(self):
        with pytest.raises(ValueError, match="needs a github client"):
            build_tools(
                ["github_create_pr"],
                sandbox=StubSandbox(),
                recorder=ToolRecorder(),
            )


class TestPullRequestTool:
    def test_opens_pr_and_records_event(self):
        client = _client(
            [ok({"number": 9, "html_url": "https://gh/pr/9", "title": "t", "state": "open"}, status=201)]
        )
        recorder = ToolRecorder()
        (tool,) = _build(["github_create_pr"], client, recorder)

        out = tool.invoke({"title": "t", "head": "feature"})

        assert "PR #9" in out
        assert "https://gh/pr/9" in out
        assert recorder.events[0].name == "github_create_pr"
        assert recorder.events[0].status == "ok"

    def test_api_error_is_error_result_not_exception(self):
        client = _client([err(422, "Validation Failed")])
        recorder = ToolRecorder()
        (tool,) = _build(["github_create_pr"], client, recorder)

        out = tool.invoke({"title": "t", "head": "feature"})

        assert "failed" in out.lower()
        assert recorder.events[0].status == "error"


class TestIssueTools:
    def test_get_issue_renders_fields(self):
        client = _client(
            [
                ok(
                    {
                        "number": 3,
                        "title": "Bug",
                        "body": "details",
                        "labels": [{"name": "bug"}],
                        "assignee": {"login": "bob"},
                        "state": "open",
                    }
                )
            ]
        )
        (tool,) = _build(["github_get_issue"], client)
        out = tool.invoke({"number": 3})
        assert "#3" in out
        assert "bug" in out
        assert "bob" in out
        assert "details" in out

    def test_update_issue_closes_and_sets_labels(self):
        client = _client(
            [
                ok(
                    {
                        "number": 3,
                        "title": "Bug",
                        "body": "",
                        "labels": [{"name": "done"}],
                        "assignee": None,
                        "state": "closed",
                    }
                )
            ]
        )
        (tool,) = _build(["github_update_issue"], client)
        out = tool.invoke({"number": 3, "state": "closed", "labels": ["done"]})
        assert "#3" in out
        assert "closed" in out


class TestBranchAndCommitTools:
    def test_create_branch(self):
        client = _client(
            [ok({"object": {"sha": "s1"}}), ok({"ref": "refs/heads/f"}, status=201)]
        )
        (tool,) = _build(["github_create_branch"], client)
        out = tool.invoke({"name": "feature", "base": "main"})
        assert "feature" in out

    def test_commit_single_file(self):
        client = _client(
            [
                ok({"object": {"sha": "parent"}}),
                ok({"tree": {"sha": "bt"}}),
                ok({"sha": "blob"}, status=201),
                ok({"sha": "tree"}, status=201),
                ok({"sha": "abc1234def"}, status=201),
                ok({"object": {"sha": "abc1234def"}}),
            ]
        )
        (tool,) = _build(["github_commit"], client)
        out = tool.invoke(
            {"branch": "feature", "path": "f.txt", "content": "x", "message": "m"}
        )
        assert "f.txt" in out
        assert "abc1234" in out
