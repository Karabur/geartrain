"""Shared fakes for GitHub tests — an offline transport and a recording client."""

from __future__ import annotations

from typing import Any

from geartrain.integrations.github import GitHubResponse


class FakeTransport:
    """A GitHub transport that replays queued responses and records calls.

    Pass a list of :class:`GitHubResponse` (or callables taking
    ``method, url, json``); each request pops the next one. An empty queue or a
    failing callable surfaces as a test failure rather than a network call.
    """

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def request(self, method, url, *, headers, json=None) -> GitHubResponse:
        self.calls.append(
            {"method": method, "url": url, "json": json, "headers": headers}
        )
        if not self._responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        resp = self._responses.pop(0)
        if callable(resp):
            return resp(method, url, json)
        return resp

    def call_paths(self) -> list[str]:
        """Return ``METHOD /path`` for each recorded call (base URL stripped)."""
        out = []
        for call in self.calls:
            path = call["url"].split("github.com", 1)[-1]
            out.append(f"{call['method']} {path}")
        return out


def ok(data: Any, status: int = 200) -> GitHubResponse:
    """Build a successful response."""
    return GitHubResponse(status_code=status, data=data)


def err(status: int, message: str) -> GitHubResponse:
    """Build an error response with a GitHub-style body."""
    return GitHubResponse(status_code=status, data={"message": message})
