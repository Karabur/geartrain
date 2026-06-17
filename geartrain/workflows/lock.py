"""Per-workflow file-backed locks — prevent parallel executions."""

from __future__ import annotations

import os
from pathlib import Path


class WorkflowLock:
    """File-backed lock for a single workflow.

    Acquiring writes a lock file; releasing removes it. One local engine
    process is assumed — stale-lock recovery is manual.
    """

    def __init__(self, state_path: Path, workflow_name: str) -> None:
        self._lock_file = state_path / "locks" / f"{workflow_name}.lock"

    def acquire(self, run_id: str) -> bool:
        """Try to acquire the lock for run_id.

        Returns True if acquired, False if already held.
        """
        if self.is_locked():
            return False
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file.write_text(run_id, encoding="utf-8")
        return True

    def release(self) -> None:
        """Release the lock. No-op if not held."""
        try:
            self._lock_file.unlink()
        except FileNotFoundError:
            pass

    def is_locked(self) -> bool:
        """Return True if the lock file exists."""
        return self._lock_file.exists()

    def current_run_id(self) -> str | None:
        """Return the run_id stored in the lock file, or None."""
        if not self._lock_file.exists():
            return None
        return self._lock_file.read_text(encoding="utf-8").strip() or None
