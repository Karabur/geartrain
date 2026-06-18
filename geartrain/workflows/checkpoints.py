"""In-process coordination for human checkpoints.

A workflow that hits a ``human_checkpoint`` node pauses until a human responds.
When the run executes in a background thread, the HTTP respond endpoint and the
paused runner live in the same process, so they hand off through this
coordinator: the runner registers a waiter keyed by run id and blocks; the
endpoint resolves it with the response and the runner wakes and continues.

Only one checkpoint is active per run at a time (nodes run sequentially), so a
run id is a sufficient key.
"""

from __future__ import annotations

import threading


class CheckpointCoordinator:
    """Routes checkpoint responses from the API to a paused run thread."""

    def __init__(self) -> None:
        self._waiters: dict[str, dict] = {}
        self._lock = threading.Lock()

    def input_for(self, run_id: str, timeout: float = 600.0):
        """Return an ``input_fn`` that blocks the run until a response arrives.

        The returned callable matches the ``input(prompt) -> str`` contract the
        checkpoint runner expects. If no response arrives within ``timeout``
        seconds it returns an empty string so the run can fail cleanly rather
        than hang forever.
        """

        def _wait(_prompt: str = "") -> str:
            event = threading.Event()
            with self._lock:
                self._waiters[run_id] = {"event": event, "response": ""}
            event.wait(timeout=timeout)
            with self._lock:
                slot = self._waiters.pop(run_id, {})
            return slot.get("response", "")

        return _wait

    def resolve(self, run_id: str, response: str) -> bool:
        """Deliver ``response`` to a run waiting on a checkpoint.

        Returns ``True`` if a waiter was present and woken, ``False`` otherwise.
        """
        with self._lock:
            slot = self._waiters.get(run_id)
            if slot is None:
                return False
            slot["response"] = response
            slot["event"].set()
        return True
