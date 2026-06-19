"""Tests for run summaries, event logs, and CLI inspection (GT-P7-05)."""

from pathlib import Path
from textwrap import dedent

import pytest

from geartrain.engine.loader import load_workflow
from geartrain.engine.observability import render_summary, summarize_run
from geartrain.engine.state import FileStateBackend
from geartrain.memory.markdown import MarkdownMemoryStore
from geartrain.workflows.start import run_workflow
from tests.observability_helpers import (
    _agent,
    _failing_workflow,
    _langchain_runner,
    seed_failed_run,
    seed_success_run,
)
from langchain_core.messages import AIMessage
from tests.stub_chat_model import StubChatModel


class TestSummary:
    def test_success_summary_shape(self, tmp_path):
        backend = seed_success_run(tmp_path, "run-ok")
        summary = summarize_run(backend, "run-ok")
        assert summary["status"] == "completed"
        assert summary["node_count"] == 2
        assert summary["tool_calls"]["total"] == 3
        assert summary["memory"]["writes"] == 1
        assert summary["terminal_error"] is None

    def test_failed_summary_points_to_failure(self, tmp_path):
        backend = seed_failed_run(tmp_path, "run-failed")
        summary = summarize_run(backend, "run-failed")
        assert summary["status"] == "failed"
        assert summary["terminal_error"]["node_id"] == "open_pr"

        rendered = render_summary(summary, events_log="path/to/events.jsonl")
        assert "FAILED at node open_pr" in rendered
        assert "path/to/events.jsonl" in rendered


def _seed_task(work_dir: Path) -> None:
    todo = work_dir / "todo"
    todo.mkdir(parents=True)
    (todo / "task.md").write_text("---\nid: T1\n---\n\n# Do a thing\n")


def _dev_workflow(tmp_path: Path):
    f = tmp_path / "dev.workflow.yaml"
    f.write_text(
        dedent(
            """\
            schema_version: 1
            name: geartrain-dev
            description: dev
            trigger:
              type: manual
            agents:
              coder: coder
              lead: lead
            graph:
              entry: run_coder
              nodes:
                run_coder:
                  type: agent
                  agent: coder
                  output_key: coder_output
                  transitions:
                    default: run_lead
                run_lead:
                  type: agent
                  agent: lead
                  output_key: lead_output
                  transitions:
                    default: end
            """
        )
    )
    return load_workflow(str(f))


class TestEventLogFiles:
    def test_success_writes_logs(self, tmp_path):
        work_dir = tmp_path / "work"
        _seed_task(work_dir)
        state_path = tmp_path / "state"
        backend = FileStateBackend(state_path)
        store = MarkdownMemoryStore(str(tmp_path / "memory"))

        agents = {
            "coder": _langchain_runner(
                _agent("coder", [], []),
                StubChatModel(responses=[AIMessage(content="c")]),
                root=tmp_path,
                memory_store=store,
            ),
            "lead": _langchain_runner(
                _agent("lead", [], []),
                StubChatModel(responses=[AIMessage(content="l")]),
                root=tmp_path,
                memory_store=store,
            ),
        }
        log_file = tmp_path / "logs" / "geartrain-dev.md"
        result = run_workflow(
            _dev_workflow(tmp_path),
            agents,
            backend,
            state_path,
            log_file,
            "run-1",
            work_dir=work_dir,
        )
        assert result["status"] == "completed"
        assert log_file.exists()
        events_log = log_file.with_suffix(".events.jsonl")
        assert events_log.exists()
        assert "run-1" in events_log.read_text()

    def test_failure_writes_logs(self, tmp_path):
        work_dir = tmp_path / "work"
        _seed_task(work_dir)
        state_path = tmp_path / "state"
        backend = FileStateBackend(state_path)
        store = MarkdownMemoryStore(str(tmp_path / "memory"))

        agents = {
            "coder": _langchain_runner(
                _agent("coder", [], []),
                StubChatModel(responses=[AIMessage(content="c")]),
                root=tmp_path,
                memory_store=store,
            ),
        }
        log_file = tmp_path / "logs" / "fail-wf.md"
        with pytest.raises(Exception):
            run_workflow(
                _failing_workflow(tmp_path),
                agents,
                backend,
                state_path,
                log_file,
                "run-2",
                work_dir=work_dir,
                integrations={},
            )
        assert log_file.exists()
        assert "status=failed" in log_file.read_text()
        events_log = log_file.with_suffix(".events.jsonl")
        assert events_log.exists()
        assert "run_failed" in events_log.read_text()


class TestCliRunCommands:
    def test_run_summary_command(self, tmp_path, monkeypatch, capsys):
        backend = seed_success_run(tmp_path, "run-ok")
        import geartrain.cli as cli

        monkeypatch.setattr(cli, "_state_backend", lambda: backend)
        cli.main(["run", "summary", "run-ok"])
        out = capsys.readouterr().out
        assert "Run run-ok [completed]" in out
        assert "tools: 3" in out

    def test_run_list_command(self, tmp_path, monkeypatch, capsys):
        backend = seed_success_run(tmp_path, "run-ok")
        import geartrain.cli as cli

        monkeypatch.setattr(cli, "_state_backend", lambda: backend)
        cli.main(["run", "list"])
        out = capsys.readouterr().out
        assert "run-ok" in out
        assert "completed" in out

    def test_run_events_command(self, tmp_path, monkeypatch, capsys):
        backend = seed_success_run(tmp_path, "run-ok")
        import geartrain.cli as cli

        monkeypatch.setattr(cli, "_state_backend", lambda: backend)
        cli.main(["run", "events", "run-ok"])
        out = capsys.readouterr().out
        assert "node_start" in out
        assert "tool_call" in out
