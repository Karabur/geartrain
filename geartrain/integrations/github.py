"""GitHub client for the write and read paths.

The client speaks the GitHub REST API over an injectable transport. The default
transport uses ``requests``; tests inject a fake so nothing touches the network.
Every call that fails — a non-2xx response or a transport error — raises
:class:`GitHubError` with enough context that a human can finish the step by
hand.

Branch and commit creation use the Git Data API (refs, blobs, trees, commits)
so the whole flow runs with just a token, no local checkout required.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from geartrain.engine.config import EngineConfig, WorkspaceConfig

DEFAULT_BASE_URL = "https://api.github.com"
_API_VERSION = "2022-11-28"


class GitHubError(Exception):
    """A GitHub call failed. ``status_code`` is set for API errors, None otherwise."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class GitHubResponse:
    """A transport response: an HTTP status and the parsed JSON body."""

    status_code: int
    data: Any


class Transport(Protocol):
    """Sends one HTTP request and returns a :class:`GitHubResponse`."""

    def request(
        self, method: str, url: str, *, headers: dict[str, str], json: Any = None
    ) -> GitHubResponse: ...


class RequestsTransport:
    """Default transport backed by ``requests``, imported lazily on first use."""

    def request(
        self, method: str, url: str, *, headers: dict[str, str], json: Any = None
    ) -> GitHubResponse:
        import requests  # lazy: only needed for real network calls

        resp = requests.request(method, url, headers=headers, json=json, timeout=30)
        try:
            data = resp.json()
        except ValueError:
            data = None
        return GitHubResponse(status_code=resp.status_code, data=data)


class GitHubClient:
    """Talks to one repository's GitHub REST API.

    Pass ``transport`` to swap the HTTP layer; the default uses ``requests``.
    Methods return plain dicts with the few fields callers need, and raise
    :class:`GitHubError` on any failure.
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        token: str,
        *,
        transport: Transport | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self._token = token
        self._transport = transport or RequestsTransport()
        self._base_url = base_url.rstrip("/")

    # -- HTTP plumbing -------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        ok: tuple[int, ...] = (200,),
    ) -> Any:
        """Send a request and return the JSON body, or raise on a bad status."""
        url = f"{self._base_url}{path}"
        try:
            resp = self._transport.request(
                method, url, headers=self._headers(), json=json
            )
        except GitHubError:
            raise
        except Exception as exc:  # network or transport failure
            raise GitHubError(f"{method} {path} failed: {exc}") from exc

        if resp.status_code not in ok:
            detail = _error_detail(resp.data)
            raise GitHubError(
                f"{method} {path} returned {resp.status_code}: {detail}",
                status_code=resp.status_code,
            )
        return resp.data

    # -- Write path (GT-P6-01) ----------------------------------------------

    def create_branch(self, branch: str, *, base: str = "main") -> dict[str, Any]:
        """Create ``branch`` pointing at the tip of ``base``."""
        base_ref = self._request(
            "GET", f"/repos/{self.owner}/{self.repo}/git/ref/heads/{base}"
        )
        base_sha = _dig(base_ref, "object", "sha")
        if not base_sha:
            raise GitHubError(f"could not read sha for base branch {base!r}")

        self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
            ok=(201,),
        )
        return {"branch": branch, "base": base, "sha": base_sha}

    def commit_files(
        self, branch: str, files: dict[str, str], message: str
    ) -> dict[str, Any]:
        """Commit ``files`` (path -> contents) onto ``branch`` as one commit."""
        if not files:
            raise GitHubError("commit_files needs at least one file")

        head_ref = self._request(
            "GET", f"/repos/{self.owner}/{self.repo}/git/ref/heads/{branch}"
        )
        parent_sha = _dig(head_ref, "object", "sha")
        if not parent_sha:
            raise GitHubError(f"could not read sha for branch {branch!r}")

        parent_commit = self._request(
            "GET",
            f"/repos/{self.owner}/{self.repo}/git/commits/{parent_sha}",
        )
        base_tree_sha = _dig(parent_commit, "tree", "sha")

        tree = []
        for path, content in files.items():
            blob = self._request(
                "POST",
                f"/repos/{self.owner}/{self.repo}/git/blobs",
                json={"content": content, "encoding": "utf-8"},
                ok=(201,),
            )
            tree.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob["sha"],
                }
            )

        new_tree = self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/git/trees",
            json={"base_tree": base_tree_sha, "tree": tree},
            ok=(201,),
        )
        new_commit = self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/git/commits",
            json={
                "message": message,
                "tree": new_tree["sha"],
                "parents": [parent_sha],
            },
            ok=(201,),
        )
        self._request(
            "PATCH",
            f"/repos/{self.owner}/{self.repo}/git/refs/heads/{branch}",
            json={"sha": new_commit["sha"]},
        )
        return {
            "branch": branch,
            "commit": new_commit["sha"],
            "files": sorted(files),
        }

    def create_pull_request(
        self, *, title: str, head: str, base: str = "main", body: str = ""
    ) -> dict[str, Any]:
        """Open a PR from ``head`` into ``base``."""
        pr = self._request(
            "POST",
            f"/repos/{self.owner}/{self.repo}/pulls",
            json={"title": title, "head": head, "base": base, "body": body},
            ok=(201,),
        )
        return {
            "number": pr.get("number"),
            "url": pr.get("html_url", ""),
            "title": pr.get("title", title),
            "state": pr.get("state", "open"),
        }

    # -- Read path (GT-P6-02) -----------------------------------------------

    def get_issue(self, number: int) -> dict[str, Any]:
        """Read an issue's title, body, labels, assignee, and state."""
        issue = self._request(
            "GET", f"/repos/{self.owner}/{self.repo}/issues/{number}"
        )
        return _normalize_issue(issue)

    def update_issue(
        self,
        number: int,
        *,
        state: str | None = None,
        labels: list[str] | None = None,
        title: str | None = None,
        body: str | None = None,
        assignees: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an issue's status, labels, or other fields.

        Only the arguments you pass are changed; ``labels`` replaces the full
        set. Raises ``GitHubError`` if nothing was given to update.
        """
        payload: dict[str, Any] = {}
        if state is not None:
            payload["state"] = state
        if labels is not None:
            payload["labels"] = labels
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if assignees is not None:
            payload["assignees"] = assignees
        if not payload:
            raise GitHubError("update_issue needs at least one field to change")

        issue = self._request(
            "PATCH",
            f"/repos/{self.owner}/{self.repo}/issues/{number}",
            json=payload,
        )
        return _normalize_issue(issue)


# --- Helpers ----------------------------------------------------------------


def _dig(data: Any, *keys: str) -> Any:
    """Walk nested dict ``keys``, returning None if any step is missing."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _error_detail(data: Any) -> str:
    """Pull a human-readable message out of an error response body."""
    if isinstance(data, dict):
        message = data.get("message")
        if message:
            errors = data.get("errors")
            if errors:
                return f"{message} ({errors})"
            return str(message)
    return str(data) if data else "(no body)"


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Shape a raw issue payload into the fields callers use."""
    labels = [
        label["name"] if isinstance(label, dict) else label
        for label in issue.get("labels", [])
    ]
    assignee = issue.get("assignee")
    if isinstance(assignee, dict):
        assignee = assignee.get("login")
    return {
        "number": issue.get("number"),
        "title": issue.get("title", ""),
        "body": issue.get("body") or "",
        "labels": labels,
        "assignee": assignee,
        "state": issue.get("state", ""),
    }


# --- Credential resolution and construction --------------------------------


def resolve_github_token(
    workspace: "WorkspaceConfig",
    engine: "EngineConfig",
    *,
    name: str = "github",
) -> str:
    """Resolve the GitHub token from the engine credentials and environment.

    The workspace integration names a dotted credential path (e.g.
    ``github.default``) into ``engine.credentials``; the leaf holds the
    environment variable name under ``token_env`` (or is the name itself).
    Raises :class:`GitHubError` if the path or environment variable is missing.
    """
    integration = workspace.integrations.get(name)
    if integration is None:
        raise GitHubError(f"no {name!r} integration in workspace config")

    node: Any = engine.credentials
    for part in integration.credential.split("."):
        if not isinstance(node, dict) or part not in node:
            raise GitHubError(
                f"credential path {integration.credential!r} not found in "
                f"engine.credentials"
            )
        node = node[part]

    env_var = node.get("token_env") if isinstance(node, dict) else node
    if not env_var:
        raise GitHubError(
            f"credential {integration.credential!r} has no token_env"
        )

    token = os.environ.get(env_var)
    if not token:
        raise GitHubError(
            f"missing GitHub credential: environment variable {env_var!r} is not set"
        )
    return token


def github_client_from_config(
    workspace: "WorkspaceConfig",
    engine: "EngineConfig",
    *,
    name: str = "github",
    transport: Transport | None = None,
) -> GitHubClient:
    """Build a :class:`GitHubClient` from workspace and engine config."""
    integration = workspace.integrations.get(name)
    if integration is None:
        raise GitHubError(f"no {name!r} integration in workspace config")
    token = resolve_github_token(workspace, engine, name=name)
    return GitHubClient(
        integration.owner,
        integration.repo,
        token,
        transport=transport,
    )
