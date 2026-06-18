"""Run observability — attempts, summaries, and human-facing log rendering.

Phase 7 keeps run state file-backed and the event log append-only JSONL. This
module reads those records and turns them into the derived views observability
needs without a dashboard: per-node attempts, a compact run summary, and a
terminal-friendly timeline. Everything here is pure: it reads a
:class:`FileStateBackend` and returns plain dicts and strings.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geartrain.engine.state import FileStateBackend


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _duration_ms(start: str | None, end: str | None) -> float | None:
    a, b = _parse_ts(start), _parse_ts(end)
    if a is None or b is None:
        return None
    return (b - a).total_seconds() * 1000.0


def derive_attempts(events: list[dict]) -> list[dict]:
    """Reconstruct per-node attempts from a run's event stream.

    Each ``node_start`` opens an attempt; the next ``node_complete`` or
    ``run_failed`` for that node closes it. Error handling is log-and-stop, so a
    node normally has a single attempt, but the model carries an ``attempt``
    counter to stay correct if retries are added later.
    """
    attempts: list[dict] = []
    open_by_node: dict[str, dict] = {}
    counts: dict[str, int] = {}

    for ev in events:
        etype = ev.get("type")
        node_id = ev.get("node_id")
        if etype == "node_start" and node_id:
            counts[node_id] = counts.get(node_id, 0) + 1
            attempt = {
                "node_id": node_id,
                "attempt": counts[node_id],
                "attempt_id": f"{node_id}#{counts[node_id]}",
                "node_type": ev.get("node_type"),
                "started_at": ev.get("timestamp"),
                "ended_at": None,
                "status": "running",
                "error": None,
            }
            attempts.append(attempt)
            open_by_node[node_id] = attempt
        elif etype == "node_complete" and node_id in open_by_node:
            attempt = open_by_node.pop(node_id)
            attempt["ended_at"] = ev.get("timestamp")
            attempt["status"] = ev.get("status", "ok")
            attempt["duration_ms"] = _duration_ms(
                attempt["started_at"], attempt["ended_at"]
            )
        elif etype == "run_failed" and node_id in open_by_node:
            attempt = open_by_node.pop(node_id)
            attempt["ended_at"] = ev.get("timestamp")
            attempt["status"] = "failed"
            attempt["error"] = ev.get("error")
            attempt["duration_ms"] = _duration_ms(
                attempt["started_at"], attempt["ended_at"]
            )

    for attempt in attempts:
        attempt.setdefault("duration_ms", None)
    return attempts


def attempts_for_run(backend: "FileStateBackend", run_id: str) -> list[dict]:
    """Read a run's events and return its derived attempts."""
    return derive_attempts(backend.read_events(run_id))


def summarize_run(backend: "FileStateBackend", run_id: str) -> dict[str, Any]:
    """Compute a compact, machine-readable summary of a run.

    Reports run status and duration, per-node attempt timings, tool-call counts
    by status, memory read/write/rejected counts, and the terminal error (if
    any) with the node it failed on. This is the source both the API summary
    endpoint and the CLI summary command render.
    """
    state = backend.read_run_state(run_id)
    events = backend.read_events(run_id)
    attempts = derive_attempts(events)

    tool_calls = {"total": 0, "ok": 0, "error": 0}
    memory = {"reads": 0, "writes": 0, "rejected": 0}
    terminal_error: dict[str, Any] | None = None

    for ev in events:
        etype = ev.get("type")
        if etype == "tool_call":
            tool_calls["total"] += 1
            bucket = "error" if ev.get("status") == "error" else "ok"
            tool_calls[bucket] += 1
        elif etype == "memory_read":
            memory["reads"] += 1
        elif etype == "memory_write":
            memory["writes"] += 1
        elif etype == "memory_write_rejected":
            memory["rejected"] += 1
        elif etype in ("run_failed", "integration_error"):
            terminal_error = {
                "node_id": ev.get("node_id"),
                "error": ev.get("error"),
                "at": ev.get("timestamp"),
            }

    node_timings = [
        {
            "node_id": a["node_id"],
            "attempt_id": a["attempt_id"],
            "status": a["status"],
            "duration_ms": a.get("duration_ms"),
        }
        for a in attempts
    ]

    return {
        "run_id": run_id,
        "workflow": state.get("workflow"),
        "status": state.get("status"),
        "started_at": state.get("started_at"),
        "ended_at": state.get("ended_at"),
        "duration_ms": _duration_ms(state.get("started_at"), state.get("ended_at")),
        "node_count": len(attempts),
        "node_timings": node_timings,
        "tool_calls": tool_calls,
        "memory": memory,
        "event_count": len(events),
        "terminal_error": terminal_error,
    }


def _fmt_ms(ms: float | None) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.1f}s"


def render_summary(summary: dict[str, Any], events_log: str | None = None) -> str:
    """Render a run summary as a compact, terminal-friendly block.

    A failed run shows where it failed, why, and which event log to inspect.
    """
    lines: list[str] = []
    status = summary.get("status", "?")
    lines.append(f"Run {summary['run_id']} [{status}]")
    lines.append(
        f"  workflow: {summary.get('workflow', '?')}  "
        f"duration: {_fmt_ms(summary.get('duration_ms'))}  "
        f"nodes: {summary.get('node_count', 0)}"
    )

    for nt in summary.get("node_timings", []):
        lines.append(
            f"  - {nt['node_id']} [{nt['status']}] "
            f"{_fmt_ms(nt.get('duration_ms'))}"
        )

    tc = summary.get("tool_calls", {})
    mem = summary.get("memory", {})
    lines.append(
        f"  tools: {tc.get('total', 0)} "
        f"(ok={tc.get('ok', 0)}, error={tc.get('error', 0)})  "
        f"memory: reads={mem.get('reads', 0)} "
        f"writes={mem.get('writes', 0)} rejected={mem.get('rejected', 0)}"
    )

    err = summary.get("terminal_error")
    if err:
        lines.append(
            f"  FAILED at node {err.get('node_id', '?')}: {err.get('error', '')}"
        )
    if events_log:
        lines.append(f"  events: {events_log}")
    return "\n".join(lines)


def render_timeline(events: list[dict]) -> str:
    """Render an ordered event timeline for terminal inspection."""
    lines: list[str] = []
    for ev in events:
        seq = ev.get("seq", "?")
        ts = ev.get("timestamp", "")
        etype = ev.get("type", "?")
        node = ev.get("node_id")
        detail = ""
        if etype == "tool_call":
            detail = f" {ev.get('name', '')} [{ev.get('status', '')}]"
        elif etype in ("memory_write", "memory_read", "memory_write_rejected"):
            detail = f" {ev.get('scope', '')} {ev.get('path', '')}".rstrip()
        elif etype == "run_failed":
            detail = f" {ev.get('error', '')}"
        node_part = f" ({node})" if node else ""
        lines.append(f"{seq:>3} {ts} {etype}{node_part}{detail}")
    return "\n".join(lines)
