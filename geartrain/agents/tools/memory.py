"""Memory and knowledge tools: ``memory_read``, ``memory_write``, ``kb_read``,
``kb_write``.

These give a langchain agent live access to the markdown memory store. Reads
span the agent's allowed scopes and return ranked entries; writes go to a single
requested scope, which must be one the agent is allowed to write. Every result
carries structured ``metadata`` (scope, path, source run/node/agent, review
status, guardrail result) so Phase 7 can turn it into a memory event.

A ``cli`` agent gets memory as injected prompt text instead of these tools — it
has no live write path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from pydantic import BaseModel, Field

from geartrain.agents.tools.base import ToolResult
from geartrain.memory.store import (
    MemoryRecord,
    MemoryScope,
    MemoryStore,
    MemorySystem,
    ScopeSpec,
)

__all__ = [
    "MemoryToolDeps",
    "MemoryReadArgs",
    "MemoryWriteArgs",
    "memory_read",
    "memory_write",
]


@dataclass
class MemoryToolDeps:
    """Everything the memory tools need beyond their call arguments.

    ``read_scopes`` and ``write_scopes`` come from the agent definition;
    ``workflow`` and ``agent_type`` namespace the workflow- and agent-level
    scopes. The ``source_*`` fields tag each write for observability.
    """

    store: MemoryStore
    read_scopes: tuple[MemoryScope, ...] = ()
    write_scopes: tuple[MemoryScope, ...] = ()
    workflow: str = ""
    agent_type: str = ""
    source_run: str = ""
    source_node: str = ""
    source_agent: str = ""
    limit: int = 10


class MemoryReadArgs(BaseModel):
    query: str = Field(
        description="Keywords to search memory for. Returns the best matches."
    )


class MemoryWriteArgs(BaseModel):
    content: str = Field(description="The memory entry text to store.")
    scope: str = Field(
        description=(
            "Scope to write to: workspace, workflow, or agent_level. "
            "Must be a scope this agent is allowed to write."
        )
    )
    category: str = Field(
        default="", description="Short label for the entry (used in ranking)."
    )
    tags: list[str] = Field(
        default_factory=list, description="Optional tags for retrieval."
    )


def _namespace_for(deps: MemoryToolDeps, scope: MemoryScope) -> str:
    if scope == MemoryScope.WORKFLOW:
        return deps.workflow
    if scope == MemoryScope.AGENT_LEVEL:
        return deps.agent_type
    return ""


def _render_records(records: Sequence[MemoryRecord]) -> str:
    blocks: list[str] = []
    for rec in records:
        header = f"[{rec.scope.value}]"
        if rec.category:
            header += f" {rec.category}"
        blocks.append(f"{header}\n{rec.content}")
    return "\n\n".join(blocks)


def memory_read(
    *, query: str, deps: MemoryToolDeps, system: MemorySystem
) -> ToolResult:
    """Search the agent's readable scopes and return ranked entries."""
    specs = [
        ScopeSpec(scope, _namespace_for(deps, scope))
        for scope in deps.read_scopes
    ]
    records = deps.store.read(
        query, system=system, scopes=specs, limit=deps.limit
    )
    metadata = {
        "system": system.value,
        "query": query,
        "scopes": [s.value for s in deps.read_scopes],
        "count": len(records),
        "paths": [r.path for r in records],
        "source_run": deps.source_run,
        "source_node": deps.source_node,
        "source_agent": deps.source_agent,
    }
    if not records:
        return ToolResult(
            output=f"no {system.value} entries match {query!r}",
            metadata=metadata,
        )
    return ToolResult(output=_render_records(records), metadata=metadata)


def memory_write(
    *,
    content: str,
    scope: str,
    deps: MemoryToolDeps,
    system: MemorySystem,
    category: str = "",
    tags: list[str] | None = None,
) -> ToolResult:
    """Write an entry to one scope, enforcing the agent's allowed write scopes."""
    try:
        scope_enum = MemoryScope(scope)
    except ValueError:
        return ToolResult(
            output=f"unknown scope {scope!r}",
            status="error",
            error="unknown_scope",
            metadata={
                "system": system.value,
                "scope": scope,
                "review_status": "unreviewed",
                "guardrail": {},
                "source_run": deps.source_run,
                "source_node": deps.source_node,
                "source_agent": deps.source_agent,
            },
        )

    if scope_enum not in deps.write_scopes:
        allowed = [s.value for s in deps.write_scopes]
        return ToolResult(
            output=(
                f"write to scope {scope!r} not allowed; "
                f"this agent may write: {allowed}"
            ),
            status="error",
            error="scope_not_allowed",
            metadata={
                "system": system.value,
                "scope": scope,
                "allowed_scopes": allowed,
                "review_status": "unreviewed",
                "guardrail": {},
                "source_run": deps.source_run,
                "source_node": deps.source_node,
                "source_agent": deps.source_agent,
            },
        )

    result = deps.store.write(
        system=system,
        scope=scope_enum,
        content=content,
        namespace=_namespace_for(deps, scope_enum),
        category=category,
        tags=tags or [],
        source_run=deps.source_run,
        source_node=deps.source_node,
        source_agent=deps.source_agent,
    )
    metadata = result.to_metadata()
    if result.status == "rejected":
        return ToolResult(
            output=f"write rejected by guardrail: {result.error}",
            status="error",
            error="guardrail",
            metadata=metadata,
        )
    if result.status != "ok":
        return ToolResult(
            output=f"write failed: {result.error}",
            status="error",
            error=result.error,
            metadata=metadata,
        )
    return ToolResult(
        output=f"wrote {system.value} entry to {result.path}",
        metadata=metadata,
    )
