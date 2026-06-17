"""Sandbox interface and no-op implementation for command and file operations."""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from typing import Any


class Sandbox(ABC):
    """Interface for command and file operation sandboxing."""

    @abstractmethod
    def execute_command(self, command: str, **kwargs: Any) -> tuple[str, str, int]:
        """Execute a command within the sandbox.

        Returns (stdout, stderr, return_code).
        """

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read a file within the sandbox."""

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        """Write a file within the sandbox."""

    @abstractmethod
    def list_directory(self, path: str) -> list[str]:
        """List directory contents within the sandbox."""


class NoopSandbox(Sandbox):
    """No-op sandbox that runs operations without restriction.

    Commands execute directly. File operations are unrestricted.
    This keeps the boundary ready for a real sandbox implementation.
    """

    def execute_command(self, command: str, **kwargs: Any) -> tuple[str, str, int]:
        cwd = kwargs.get("cwd")
        timeout = kwargs.get("timeout", 120)
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=cwd, timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode

    def read_file(self, path: str) -> str:
        with open(path, "r") as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        with open(path, "w") as f:
            f.write(content)

    def list_directory(self, path: str) -> list[str]:
        return os.listdir(path)
