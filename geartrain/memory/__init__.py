"""Memory management — git-backed markdown memory and the knowledge base.

``MemoryStore`` is the backend-agnostic interface; ``MarkdownMemoryStore`` is
the file-backed implementation. The legacy no-op ``MemoryManager`` remains for
the engine boundary until every caller moves to the store.
"""

from geartrain.memory.guardrail import GuardrailResult, scan_for_secrets
from geartrain.memory.markdown import MarkdownMemoryStore
from geartrain.memory.noop import MemoryManager, NoopMemoryManager
from geartrain.memory.store import (
    DEFAULT_READ_SCOPES,
    WRITABLE_SCOPES,
    MemoryRecord,
    MemoryScope,
    MemoryStore,
    MemorySystem,
    ScopeSpec,
    WriteResult,
    parse_scopes,
)

__all__ = [
    "MemoryManager",
    "NoopMemoryManager",
    "MemoryStore",
    "MarkdownMemoryStore",
    "MemorySystem",
    "MemoryScope",
    "MemoryRecord",
    "ScopeSpec",
    "WriteResult",
    "WRITABLE_SCOPES",
    "DEFAULT_READ_SCOPES",
    "parse_scopes",
    "GuardrailResult",
    "scan_for_secrets",
]
