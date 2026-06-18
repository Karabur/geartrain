"""Shared plumbing for langchain tools: results, events, and the tool builder.

Core tool functions return a :class:`ToolResult` — a string for the model plus
a status and error. The builder wraps a core function into a LangChain
``StructuredTool`` that times the call, records a :class:`ToolEvent` for
observability (Phase 7), and hands the plain string back to the model.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

_SUMMARY_LIMIT = 200


def summarize(text: str, limit: int = _SUMMARY_LIMIT) -> str:
    """Collapse *text* to a single-line summary no longer than *limit*."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


@dataclass
class ToolResult:
    """What a core tool function returns.

    ``output`` is the text handed to the model. On failure, set ``status`` to
    ``"error"`` and put a short reason in ``error`` — the output still flows to
    the model so the agent can react. ``metadata`` carries structured detail
    (e.g. a memory write's scope, path, and guardrail result) for Phase 7
    events; it never reaches the model.
    """

    output: str
    status: str = "ok"
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


_TOOL_CATEGORIES = {
    "file_read": "file",
    "file_write": "file",
    "project_search": "file",
    "shell_exec": "shell",
    "git_status": "git",
    "git_diff": "git",
    "git_commit": "git",
    "git_branch": "git",
    "memory_read": "memory",
    "memory_write": "memory",
    "kb_read": "memory",
    "kb_write": "memory",
    "github_create_branch": "github",
    "github_commit": "github",
    "github_create_pr": "github",
    "github_get_issue": "github",
    "github_update_issue": "github",
}


def tool_category(name: str) -> str:
    """Classify a tool by name so events can be grouped without leaking inputs."""
    return _TOOL_CATEGORIES.get(name, "other")


@dataclass
class ToolEvent:
    """A recorded tool call, carrying everything a Phase 7 event needs.

    ``metadata`` holds the originating :class:`ToolResult` metadata — for memory
    tools this is the scope/path/source detail a memory event needs. It is never
    handed to the model and never carries raw sensitive inputs.
    """

    name: str
    input_summary: str
    output_summary: str
    status: str
    duration_ms: float
    error: str = ""
    category: str = "other"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the event as a plain dict for serialization."""
        return {
            "name": self.name,
            "category": self.category,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class ToolRecorder:
    """Collects tool events in call order for an agent run."""

    events: list[ToolEvent] = field(default_factory=list)

    def record(self, event: ToolEvent) -> None:
        self.events.append(event)


def build_tool(
    name: str,
    description: str,
    func: Callable[..., ToolResult],
    args_schema: type[BaseModel],
    recorder: ToolRecorder,
) -> StructuredTool:
    """Wrap a core function into a recording ``StructuredTool``.

    *func* takes the validated tool arguments as keyword arguments and returns a
    :class:`ToolResult`. The wrapper times the call, records a
    :class:`ToolEvent`, and returns the result's ``output`` to the model. An
    exception raised by *func* becomes an error result rather than crashing the
    agent loop.
    """

    def _invoke(**kwargs: Any) -> str:
        start = time.perf_counter()
        try:
            result = func(**kwargs)
        except Exception as exc:  # surface as an error result, not a crash
            result = ToolResult(
                output=f"{name} failed: {exc}", status="error", error=str(exc)
            )
        duration_ms = (time.perf_counter() - start) * 1000
        recorder.record(
            ToolEvent(
                name=name,
                input_summary=summarize(_format_args(kwargs)),
                output_summary=summarize(result.output),
                status=result.status,
                duration_ms=duration_ms,
                error=result.error,
                category=tool_category(name),
                metadata=result.metadata,
            )
        )
        return result.output

    return StructuredTool.from_function(
        func=_invoke,
        name=name,
        description=description,
        args_schema=args_schema,
    )


def _format_args(kwargs: dict[str, Any]) -> str:
    """Render call arguments for an input summary."""
    return ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
