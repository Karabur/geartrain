"""MemoryStore protocol, scopes, and the records the store moves around.

The protocol is backend-agnostic: a markdown store ships now, but anything that
satisfies this surface can drop in later. Scopes come from
:class:`~geartrain.engine.config.MemoryScope` so configs, validation, and the
store all speak the same vocabulary. ``MemorySystem`` separates working
*memory* from the curated *knowledge* base; both live behind the same store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, Sequence, runtime_checkable

from geartrain.engine.config import MemoryScope

__all__ = [
    "MemoryScope",
    "MemorySystem",
    "ScopeSpec",
    "MemoryRecord",
    "WriteResult",
    "MemoryStore",
    "WRITABLE_SCOPES",
    "DEFAULT_READ_SCOPES",
    "parse_scopes",
]


class MemorySystem(str, Enum):
    """Which body of memory an operation targets.

    ``MEMORY`` is the agents' working memory; ``KNOWLEDGE`` is the curated
    knowledge base. They are stored side by side under separate roots.
    """

    MEMORY = "memory"
    KNOWLEDGE = "knowledge"


# Scopes a store can persist. ``AGENT_INSTANCE`` is deliberately absent: an
# instance's memory lives in run state, not on disk.
WRITABLE_SCOPES: tuple[MemoryScope, ...] = (
    MemoryScope.WORKSPACE,
    MemoryScope.WORKFLOW,
    MemoryScope.AGENT_LEVEL,
)

# What an agent may read when its config says nothing: everything persisted.
DEFAULT_READ_SCOPES: tuple[MemoryScope, ...] = WRITABLE_SCOPES


def parse_scopes(names: Sequence[str | MemoryScope]) -> tuple[MemoryScope, ...]:
    """Coerce scope names (strings or enums) into a tuple of ``MemoryScope``.

    Raises ``ValueError`` for an unknown scope name.
    """
    out: list[MemoryScope] = []
    for name in names:
        out.append(name if isinstance(name, MemoryScope) else MemoryScope(name))
    return tuple(out)


@dataclass(frozen=True)
class ScopeSpec:
    """A scope plus the namespace that isolates it.

    ``namespace`` selects the workflow for ``WORKFLOW`` scope and the agent type
    for ``AGENT_LEVEL`` scope. It is ignored for ``WORKSPACE``.
    """

    scope: MemoryScope
    namespace: str = ""


@dataclass
class MemoryRecord:
    """A single memory entry, as read back from the store."""

    path: str
    system: MemorySystem
    scope: MemoryScope
    content: str
    category: str = ""
    tags: list[str] = field(default_factory=list)
    namespace: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    status: str = "active"
    review_status: str = "unreviewed"
    source_run: str = ""
    source_node: str = ""
    source_agent: str = ""
    score: float = 0.0

    def to_metadata(self) -> dict:
        """Return event-friendly metadata for a Phase 7 memory event."""
        return {
            "path": self.path,
            "system": self.system.value,
            "scope": self.scope.value,
            "namespace": self.namespace,
            "category": self.category,
            "tags": list(self.tags),
            "review_status": self.review_status,
            "source_run": self.source_run,
            "source_node": self.source_node,
            "source_agent": self.source_agent,
        }


@dataclass
class WriteResult:
    """Outcome of a write or update, carrying everything a memory event needs.

    ``status`` is ``"ok"``, ``"rejected"`` (guardrail), or ``"error"``. On a
    rejection ``path`` is empty and ``guardrail`` holds the findings.
    """

    status: str
    scope: MemoryScope | None = None
    system: MemorySystem | None = None
    path: str = ""
    namespace: str = ""
    review_status: str = "unreviewed"
    source_run: str = ""
    source_node: str = ""
    source_agent: str = ""
    guardrail: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_metadata(self) -> dict:
        """Return event-friendly metadata for a Phase 7 memory event."""
        return {
            "status": self.status,
            "scope": self.scope.value if self.scope else "",
            "system": self.system.value if self.system else "",
            "path": self.path,
            "namespace": self.namespace,
            "review_status": self.review_status,
            "source_run": self.source_run,
            "source_node": self.source_node,
            "source_agent": self.source_agent,
            "guardrail": self.guardrail,
            "error": self.error,
        }


@runtime_checkable
class MemoryStore(Protocol):
    """Backend-agnostic memory interface.

    Implementations persist entries by ``system`` and ``scope``, keyword-search
    and rank on read, and soft-delete on ``forget`` so git review curates what
    actually leaves the tree.
    """

    def write(
        self,
        *,
        system: MemorySystem,
        scope: MemoryScope,
        content: str,
        namespace: str = "",
        category: str = "",
        tags: Sequence[str] = (),
        source_run: str = "",
        source_node: str = "",
        source_agent: str = "",
    ) -> WriteResult:
        """Persist a new entry. Returns the write outcome and metadata."""
        ...

    def read(
        self,
        query: str,
        *,
        system: MemorySystem,
        scopes: Sequence[ScopeSpec],
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Keyword-search across *scopes* and return ranked records."""
        ...

    def update(
        self,
        path: str,
        *,
        content: str,
        category: str | None = None,
        tags: Sequence[str] | None = None,
    ) -> WriteResult:
        """Replace an entry's body (and optional metadata) in place."""
        ...

    def list_entries(
        self,
        *,
        system: MemorySystem,
        scope: MemoryScope,
        namespace: str = "",
        include_forgotten: bool = False,
    ) -> list[MemoryRecord]:
        """List entries in one scope, newest first."""
        ...

    def forget(self, path: str) -> bool:
        """Soft-delete an entry (mark forgotten). Returns ``True`` if found."""
        ...
