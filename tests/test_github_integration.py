"""End-to-end GitHub integration tests through the workflow engine.

Covers the integration node, recorded events, and failure summaries
(GT-P6-03, GT-P6-04). A fake client stands in for GitHub, so the whole flow
runs offline.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from geartrain.engine.loader import load_workflow
from geartrain.engine.state import FileStateBackend
from geartrain.integrations.github import GitHubError
from geartrain.workflows.engine import WorkflowRunner
from geartrain.workflows.nodes import IntegrationError


class FakeGitHub:
    """A GitHub client double recording calls and optionally failing."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.calls: list[str] = []

    def create_pull_request(self, *, title, head, base="main", body=""):
        self.calls.append("create_pull_request")
        if self.fail_on == "create_pull_request":
            raise GitHubError("Validation Failed", status_code=422)
        return {
            "number": 17,
            "url": "https://github.com/octo/repo/pull/17",
            "title": title,
            "state": "open",
        }

    def update_issue(self, number, *, state=None, labels=None):
        self.calls.append("update_issue")
        if self.fail_on == "update_issue":
            raise GitHubError("Not Found", status_code=404)
        return {
            "number": number,
            "title": "task",
            "body": "",
            "labels": labels or [],
            "assignee": None,
            "state": state or "open",
        }


def _workflow(tmp_path: Path) -> "object":
    f = tmp_path / "ship.workflow.yaml"
    f.write_text(
        dedent(
            """\
            schema_version: 1
            name: ship
            description: open a PR and close the issue
            trigger:
              type: manual
            graph:
              entry: open_pr
              nodes:
                open_pr:
                  type: integration
                  service: github
                  action: open_pr
                  output_key: pr
                  inputs:
                    title: "Implement feature"
                    head: "feature/x"
                    body: "done"
                  transitions:
                    default: close_issue
                close_issue:
                  type: integration
                  service: github
                  action: update_issue
                  inputs:
                    number: "12"
                    state: "closed"
                    labels: "done"
                  transitions:
                    default: end
            """
        )
    )
    return load_workflow(str(f))


def _runner(tmp_path, workflow, github) -> WorkflowRunner:
    return WorkflowRunner(
        workflow=workflow,
        agents={},
        state_backend=FileStateBackend(tmp_path / "state"),
        state_path=tmp_path / "state",
        integrations={"github": github},
    )


class TestSuccessfulRun:
    def test_opens_pr_and_updates_issue(self, tmp_path):
        github = FakeGitHub()
        runner = _runner(tmp_path, _workflow(tmp_path), github)

        result = runner.run("run-1")

        assert result["status"] == "completed"
        assert "PR #17" in result["node_outputs"]["pr"]
        assert "#12" in result["node_outputs"]["close_issue"]
        assert github.calls == ["create_pull_request", "update_issue"]

    def test_records_node_and_integration_events(self, tmp_path):
        backend = FileStateBackend(tmp_path / "state")
        runner = WorkflowRunner(
            workflow=_workflow(tmp_path),
            agents={},
            state_backend=backend,
            state_path=tmp_path / "state",
            integrations={"github": FakeGitHub()},
        )
        runner.run("run-1")

        events = backend.read_events("run-1")
        types = [e["type"] for e in events]
        assert types.count("node_start") == 2
        assert types.count("node_complete") == 2

        tool_calls = [e for e in events if e["type"] == "tool_call"]
        assert [e["name"] for e in tool_calls] == ["github.open_pr", "github.update_issue"]
        assert all(e["kind"] == "integration" for e in tool_calls)
        assert all(e["status"] == "ok" for e in tool_calls)
        # Events carry a sequence number and node id for observability.
        assert tool_calls[0]["node_id"] == "open_pr"
        assert [e["seq"] for e in events] == list(range(1, len(events) + 1))


class TestFailureHandling:
    def test_failed_integration_stops_run_and_records_summary(self, tmp_path):
        backend = FileStateBackend(tmp_path / "state")
        github = FakeGitHub(fail_on="create_pull_request")
        runner = WorkflowRunner(
            workflow=_workflow(tmp_path),
            agents={},
            state_backend=backend,
            state_path=tmp_path / "state",
            integrations={"github": github},
        )

        with pytest.raises(IntegrationError):
            runner.run("run-1")

        # Run is marked failed and the second node never ran (log-and-stop).
        assert backend.read_run_state("run-1")["status"] == "failed"
        assert github.calls == ["create_pull_request"]

        events = backend.read_events("run-1")
        types = [e["type"] for e in events]
        assert "run_failed" in types

        failed_tool = [
            e for e in events if e["type"] == "tool_call" and e["status"] == "error"
        ]
        assert failed_tool and "Validation Failed" in failed_tool[0]["error"]

        summary = [e for e in events if e["type"] == "run_failed"][0]
        assert summary["node_id"] == "open_pr"
        assert "open_pr" in summary["error"]

    def test_lock_released_after_failure(self, tmp_path):
        github = FakeGitHub(fail_on="create_pull_request")
        runner = _runner(tmp_path, _workflow(tmp_path), github)
        with pytest.raises(IntegrationError):
            runner.run("run-1")
        assert not runner.is_locked()
