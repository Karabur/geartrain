"""File and search tools: ``file_read``, ``file_write``, ``project_search``.

File access routes through the sandbox so a real sandbox can drop in later.
Every path is checked against the tool root and the agent's ``forbidden_paths``
before any read or write happens.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from pydantic import BaseModel, Field

from geartrain.agents.tools.base import ToolResult

if TYPE_CHECKING:
    from geartrain.engine.sandbox import Sandbox


class PathNotAllowedError(Exception):
    """Raised when a path escapes the tool root or hits a forbidden path."""


def resolve_within_root(
    path: str, root: str, forbidden_paths: Sequence[str]
) -> Path:
    """Resolve *path* under *root* and reject escapes and forbidden paths.

    Relative paths resolve against *root*. The result must stay inside *root*
    and must not sit under any entry in *forbidden_paths*.
    """
    root_p = Path(root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root_p / candidate
    resolved = candidate.resolve()

    if resolved != root_p and root_p not in resolved.parents:
        raise PathNotAllowedError(
            f"path {path!r} resolves outside the tool root {root!r}"
        )

    for forbidden in forbidden_paths:
        fb = Path(forbidden)
        if not fb.is_absolute():
            fb = root_p / fb
        fb = fb.resolve()
        if resolved == fb or fb in resolved.parents:
            raise PathNotAllowedError(
                f"path {path!r} is under forbidden path {forbidden!r}"
            )

    return resolved


# --- file_read --------------------------------------------------------------


class FileReadArgs(BaseModel):
    path: str = Field(description="Path to the file to read, relative to the project root.")


def file_read(
    *,
    path: str,
    sandbox: "Sandbox",
    root: str,
    forbidden_paths: Sequence[str],
) -> ToolResult:
    """Read a file through the sandbox and return its contents."""
    resolved = resolve_within_root(path, root, forbidden_paths)
    content = sandbox.read_file(str(resolved))
    return ToolResult(output=content)


# --- file_write -------------------------------------------------------------


class FileWriteArgs(BaseModel):
    path: str = Field(description="Path to the file to write, relative to the project root.")
    content: str = Field(description="Full contents to write to the file.")


def file_write(
    *,
    path: str,
    content: str,
    sandbox: "Sandbox",
    root: str,
    forbidden_paths: Sequence[str],
) -> ToolResult:
    """Write *content* to a file through the sandbox, creating parent dirs."""
    resolved = resolve_within_root(path, root, forbidden_paths)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    sandbox.write_file(str(resolved), content)
    return ToolResult(output=f"wrote {len(content)} bytes to {path}")


# --- project_search ---------------------------------------------------------


class ProjectSearchArgs(BaseModel):
    pattern: str = Field(description="Regular expression to search for in file contents.")
    glob: str | None = Field(
        default=None,
        description="Optional glob (e.g. '*.py') limiting which files are searched.",
    )


def project_search(
    *,
    pattern: str,
    glob: str | None = None,
    sandbox: "Sandbox",
    root: str,
    forbidden_paths: Sequence[str],
    max_matches: int = 100,
) -> ToolResult:
    """Search file contents under the tool root for *pattern* (grep + glob).

    Returns ``path:lineno:line`` matches. Files read through the sandbox; the
    root and forbidden paths are honored, and common noise dirs are skipped.
    """
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return ToolResult(
            output=f"invalid pattern: {exc}", status="error", error=str(exc)
        )

    root_p = Path(root).resolve()
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", ".geartrain"}
    matches: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root_p):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if glob and not fnmatch.fnmatch(filename, glob):
                continue
            file_path = Path(dirpath) / filename
            rel = file_path.relative_to(root_p)
            try:
                resolved = resolve_within_root(str(rel), root, forbidden_paths)
            except PathNotAllowedError:
                continue
            try:
                content = sandbox.read_file(str(resolved))
            except (OSError, UnicodeDecodeError):
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if regex.search(line):
                    matches.append(f"{rel}:{lineno}:{line.strip()}")
                    if len(matches) >= max_matches:
                        break
            if len(matches) >= max_matches:
                break
        if len(matches) >= max_matches:
            break

    if not matches:
        return ToolResult(output=f"no matches for pattern {pattern!r}")
    return ToolResult(output="\n".join(matches))
