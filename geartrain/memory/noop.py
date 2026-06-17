"""Memory manager interface and no-op implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryManager(ABC):
    """Interface for agent memory operations."""

    @abstractmethod
    def read(self, scope: str, **kwargs: Any) -> list[str]:
        """Read memory entries from a scope. Returns list of text entries."""

    @abstractmethod
    def write(self, scope: str, content: str, **kwargs: Any) -> None:
        """Write a memory entry to a scope."""

    @abstractmethod
    def search(self, query: str, scopes: list[str] | None = None) -> list[str]:
        """Search memory across scopes. Returns matching entries."""


class NoopMemoryManager(MemoryManager):
    """No-op memory manager that returns empty results.

    Read returns empty lists. Write is a no-op. Search returns nothing.
    This keeps the boundary ready for a real memory implementation.
    """

    def read(self, scope: str, **kwargs: Any) -> list[str]:
        return []

    def write(self, scope: str, content: str, **kwargs: Any) -> None:
        pass

    def search(self, query: str, scopes: list[str] | None = None) -> list[str]:
        return []
