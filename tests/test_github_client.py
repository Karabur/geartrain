"""Tests for the GitHub client write and read paths (GT-P6-01, GT-P6-02).

Every test injects a fake transport, so nothing touches the network.
"""

from __future__ import annotations

import pytest

from geartrain.integrations.github import (
    GitHubClient,
    GitHubError,
    github_client_from_config,
    resolve_github_token,
)
from tests.github_fakes import FakeTransport, err, ok


def _client(responses) -> tuple[GitHubClient, FakeTransport]:
    transport = FakeTransport(responses)
    client = GitHubClient("octo", "repo", "tok", transport=transport)
    return client, transport


# --- Write path (GT-P6-01) --------------------------------------------------


class TestCreateBranch:
    def test_creates_ref_from_base_sha(self):
        client, transport = _client(
            [
                ok({"object": {"sha": "base123"}}),
                ok({"ref": "refs/heads/feature"}, status=201),
            ]
        )
        result = client.create_branch("feature", base="main")

        assert result == {"branch": "feature", "base": "main", "sha": "base123"}
        assert transport.call_paths() == [
            "GET /repos/octo/repo/git/ref/heads/main",
            "POST /repos/octo/repo/git/refs",
        ]
        assert transport.calls[1]["json"] == {
            "ref": "refs/heads/feature",
            "sha": "base123",
        }

    def test_missing_base_sha_raises(self):
        client, _ = _client([ok({"object": {}})])
        with pytest.raises(GitHubError, match="could not read sha"):
            client.create_branch("feature")

    def test_api_error_raises_with_status(self):
        client, _ = _client([err(404, "Not Found")])
        with pytest.raises(GitHubError) as exc:
            client.create_branch("feature")
        assert exc.value.status_code == 404
        assert "Not Found" in str(exc.value)


class TestCommitFiles:
    def test_creates_blob_tree_commit_and_updates_ref(self):
        client, transport = _client(
            [
                ok({"object": {"sha": "parent1"}}),       # GET head ref
                ok({"tree": {"sha": "basetree"}}),         # GET parent commit
                ok({"sha": "blob1"}, status=201),          # POST blob
                ok({"sha": "newtree"}, status=201),        # POST tree
                ok({"sha": "commit1"}, status=201),        # POST commit
                ok({"object": {"sha": "commit1"}}),        # PATCH ref
            ]
        )
        result = client.commit_files(
            "feature", {"README.md": "hello"}, "add readme"
        )

        assert result == {
            "branch": "feature",
            "commit": "commit1",
            "files": ["README.md"],
        }
        paths = transport.call_paths()
        assert paths[0] == "GET /repos/octo/repo/git/ref/heads/feature"
        assert paths[-1] == "PATCH /repos/octo/repo/git/refs/heads/feature"
        # Commit points at the new tree and the parent.
        commit_call = transport.calls[4]["json"]
        assert commit_call["tree"] == "newtree"
        assert commit_call["parents"] == ["parent1"]

    def test_empty_files_raises(self):
        client, _ = _client([])
        with pytest.raises(GitHubError, match="at least one file"):
            client.commit_files("feature", {}, "msg")


class TestCreatePullRequest:
    def test_opens_pr_and_returns_number_and_url(self):
        client, transport = _client(
            [
                ok(
                    {
                        "number": 42,
                        "html_url": "https://github.com/octo/repo/pull/42",
                        "title": "My change",
                        "state": "open",
                    },
                    status=201,
                )
            ]
        )
        result = client.create_pull_request(
            title="My change", head="feature", base="main", body="why"
        )

        assert result["number"] == 42
        assert result["url"] == "https://github.com/octo/repo/pull/42"
        assert transport.calls[0]["json"] == {
            "title": "My change",
            "head": "feature",
            "base": "main",
            "body": "why",
        }

    def test_unprocessable_raises(self):
        client, _ = _client([err(422, "Validation Failed")])
        with pytest.raises(GitHubError) as exc:
            client.create_pull_request(title="t", head="h")
        assert exc.value.status_code == 422

    def test_transport_failure_becomes_github_error(self):
        class Boom:
            def request(self, *a, **k):
                raise RuntimeError("connection reset")

        client = GitHubClient("octo", "repo", "tok", transport=Boom())
        with pytest.raises(GitHubError, match="connection reset"):
            client.create_pull_request(title="t", head="h")


# --- Read path (GT-P6-02) ---------------------------------------------------


class TestGetIssue:
    def test_reads_and_normalizes_fields(self):
        client, _ = _client(
            [
                ok(
                    {
                        "number": 5,
                        "title": "Bug",
                        "body": "broken",
                        "labels": [{"name": "bug"}, {"name": "p1"}],
                        "assignee": {"login": "alice"},
                        "state": "open",
                    }
                )
            ]
        )
        issue = client.get_issue(5)
        assert issue == {
            "number": 5,
            "title": "Bug",
            "body": "broken",
            "labels": ["bug", "p1"],
            "assignee": "alice",
            "state": "open",
        }

    def test_handles_null_body_and_no_assignee(self):
        client, _ = _client(
            [ok({"number": 1, "title": "t", "body": None, "labels": [], "assignee": None, "state": "closed"})]
        )
        issue = client.get_issue(1)
        assert issue["body"] == ""
        assert issue["assignee"] is None
        assert issue["labels"] == []


class TestUpdateIssue:
    def test_patches_state_and_labels(self):
        client, transport = _client(
            [
                ok(
                    {
                        "number": 5,
                        "title": "Bug",
                        "body": "",
                        "labels": [{"name": "done"}],
                        "assignee": None,
                        "state": "closed",
                    }
                )
            ]
        )
        issue = client.update_issue(5, state="closed", labels=["done"])
        assert issue["state"] == "closed"
        assert issue["labels"] == ["done"]
        assert transport.calls[0]["method"] == "PATCH"
        assert transport.calls[0]["json"] == {"state": "closed", "labels": ["done"]}

    def test_no_fields_raises(self):
        client, _ = _client([])
        with pytest.raises(GitHubError, match="at least one field"):
            client.update_issue(5)


# --- Credential resolution and construction ---------------------------------


class _WS:
    """Minimal workspace stand-in carrying integrations."""

    def __init__(self, integrations):
        self.integrations = integrations


class _Integration:
    def __init__(self, owner, repo, credential):
        self.owner = owner
        self.repo = repo
        self.credential = credential


class _Engine:
    def __init__(self, credentials):
        self.credentials = credentials


class TestTokenResolution:
    def _workspace_engine(self):
        ws = _WS({"github": _Integration("octo", "repo", "github.default")})
        engine = _Engine({"github": {"default": {"token_env": "GH_TOKEN_TEST"}}})
        return ws, engine

    def test_resolves_token_from_env(self, monkeypatch):
        ws, engine = self._workspace_engine()
        monkeypatch.setenv("GH_TOKEN_TEST", "secret-tok")
        assert resolve_github_token(ws, engine) == "secret-tok"

    def test_missing_env_var_raises(self, monkeypatch):
        ws, engine = self._workspace_engine()
        monkeypatch.delenv("GH_TOKEN_TEST", raising=False)
        with pytest.raises(GitHubError, match="is not set"):
            resolve_github_token(ws, engine)

    def test_unknown_credential_path_raises(self):
        ws = _WS({"github": _Integration("o", "r", "github.missing")})
        engine = _Engine({"github": {"default": {"token_env": "X"}}})
        with pytest.raises(GitHubError, match="not found"):
            resolve_github_token(ws, engine)

    def test_no_integration_raises(self):
        ws, engine = _WS({}), _Engine({})
        with pytest.raises(GitHubError, match="no 'github' integration"):
            resolve_github_token(ws, engine)

    def test_client_from_config_uses_owner_repo_and_token(self, monkeypatch):
        ws, engine = self._workspace_engine()
        monkeypatch.setenv("GH_TOKEN_TEST", "secret-tok")
        transport = FakeTransport([ok({"number": 1, "html_url": "u", "title": "t", "state": "open"}, status=201)])
        client = github_client_from_config(ws, engine, transport=transport)
        assert client.owner == "octo"
        assert client.repo == "repo"
        client.create_pull_request(title="t", head="h")
        assert "Bearer secret-tok" == transport.calls[0]["headers"]["Authorization"]
