"""File-backed engine and workflow state management.

Persists engine, workflow, run, and node state as markdown files with YAML
frontmatter under a configurable state directory.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from geartrain.engine.config import EngineConfig


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_md(path: Path, frontmatter: dict, body: str) -> Path:
    """Write a markdown file with YAML frontmatter and a text body."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    path.write_text(f"---\n{fm}---\n\n{body}\n", encoding="utf-8")
    return path


def _read_md(path: Path) -> dict:
    """Read a markdown file and return its frontmatter as a dict."""
    if not path.exists():
        raise FileNotFoundError(f"state file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.lstrip().startswith("---"):
        raise ValueError(f"no YAML frontmatter in {path}")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"incomplete frontmatter in {path}")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter in {path} is not a YAML mapping")
    return data


# --- Helpers ----------------------------------------------------------------


def generate_run_id(workflow_name: str, state_path: Path | None = None) -> str:
    """Generate an incremental run ID: ``<date>-<workflow>-<seq>``.

    Scans the state ``runs/`` directory for existing IDs matching the
    workflow name and date, then increments the sequence.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prefix = f"{today}-{workflow_name}-"

    if state_path is not None:
        runs_dir = state_path / "runs"
        if runs_dir.is_dir():
            existing = [
                d.name for d in runs_dir.iterdir() if d.is_dir()
            ]
            seq = 1
            for name in existing:
                if name.startswith(prefix):
                    m = re.match(rf"^{re.escape(prefix)}(\d{{3,}})$", name)
                    if m:
                        seq = max(seq, int(m.group(1)) + 1)
            return f"{prefix}{seq:03d}"

    return f"{prefix}001"


def create_state_backend(engine_config: EngineConfig) -> FileStateBackend:
    """Factory: create a FileStateBackend from an EngineConfig."""
    return FileStateBackend(state_path=Path(engine_config.state.path))


# --- State backend ----------------------------------------------------------


class FileStateBackend:
    """File-backed state backend for engine, workflow, and run state."""

    def __init__(self, state_path: Path | str):
        self.state_path = Path(state_path)

    # -- Engine state --------------------------------------------------------

    def write_engine_state(
        self,
        engine_name: str,
        status: str,
        workspace_name: str,
        pid: int | None = None,
    ) -> Path:
        """Write the engine state file."""
        started_at = _now_iso() if status == "started" else None
        fm = {
            "schema_version": 1,
            "engine_name": engine_name,
            "status": status,
            "started_at": started_at,
            "workspace": workspace_name,
            "pid": pid,
        }
        body = (
            f"# Engine State\n\n"
            f"**Engine**: {engine_name}\n"
            f"**Status**: {status}\n"
            f"**Workspace**: {workspace_name}"
            + (f"\n**PID**: {pid}" if pid is not None else "")
            + (f"\n**Started at**: {started_at}" if started_at else "")
        )
        return _write_md(self.state_path / "engine.md", fm, body)

    def read_engine_state(self) -> dict:
        """Read the engine state file and return its frontmatter."""
        return _read_md(self.state_path / "engine.md")

    # -- Workflow state ------------------------------------------------------

    def write_workflow_state(
        self,
        workflow_name: str,
        status: str,
        current_run: str | None = None,
    ) -> Path:
        """Write the workflow state file."""
        fm = {
            "schema_version": 1,
            "workflow_name": workflow_name,
            "status": status,
            "current_run": current_run,
        }
        body = (
            f"# Workflow State: {workflow_name}\n\n"
            f"**Status**: {status}\n"
            f"**Current run**: {current_run if current_run else 'none'}"
        )
        wf_dir = self.state_path / "workflows"
        return _write_md(wf_dir / f"{workflow_name}.md", fm, body)

    def read_workflow_state(self, workflow_name: str) -> dict:
        """Read a workflow state file and return its frontmatter."""
        wf_dir = self.state_path / "workflows"
        return _read_md(wf_dir / f"{workflow_name}.md")

    # -- Run state -----------------------------------------------------------

    def create_run(self, run_id: str, workflow_name: str) -> Path:
        """Create a run directory and its ``run.md`` state file."""
        run_dir = self.state_path / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        started_at = _now_iso()
        fm = {
            "schema_version": 1,
            "run_id": run_id,
            "workflow": workflow_name,
            "status": "running",
            "started_at": started_at,
            "current_node": None,
        }
        body = (
            f"# Run: {run_id}\n\n"
            f"**Workflow**: {workflow_name}\n"
            f"**Status**: running\n"
            f"**Started**: {started_at}"
        )
        return _write_md(run_dir / "run.md", fm, body)

    def update_run_status(
        self,
        run_id: str,
        status: str,
        current_node: str | None = None,
    ) -> None:
        """Update the status and current_node fields in a run state file."""
        run_file = self.state_path / "runs" / run_id / "run.md"
        state = _read_md(run_file)
        state["status"] = status
        state["current_node"] = current_node
        body = (
            f"# Run: {run_id}\n\n"
            f"**Workflow**: {state.get('workflow', '?')}\n"
            f"**Status**: {status}\n"
            f"**Started**: {state.get('started_at', 'unknown')}"
            + (f"\n**Current node**: {current_node}" if current_node else "")
        )
        _write_md(run_file, state, body)

    def read_run_state(self, run_id: str) -> dict:
        """Read a run state file and return its frontmatter."""
        run_file = self.state_path / "runs" / run_id / "run.md"
        return _read_md(run_file)

    # -- Node output ---------------------------------------------------------

    def write_node_output(
        self,
        run_id: str,
        node_id: str,
        node_type: str,
        agent: str | None,
        status: str,
        output_text: str,
        output_key: str | None = None,
        node_number: int | None = None,
    ) -> Path:
        """Write a node output file inside a run directory."""
        run_dir = self.state_path / "runs" / run_id

        if node_number is not None:
            filename = f"{node_number:02d}-{node_id}.md"
        else:
            filename = f"{node_id}.md"

        fm = {
            "schema_version": 1,
            "node_id": node_id,
            "node_type": node_type,
            "agent": agent,
            "status": status,
            "output_key": output_key,
        }
        body = (
            f"# Node: {node_id}\n\n"
            + (f"**Agent**: {agent}\n" if agent else "")
            + f"**Status**: {status}\n"
            + (f"**Output key**: {output_key}\n" if output_key else "")
            + f"\n## Output\n\n{output_text}"
        )
        return _write_md(run_dir / filename, fm, body)

    def read_node_output(self, run_id: str, node_id: str) -> dict:
        """Read a node output file and return its frontmatter.

        Searches for files matching ``*-{node_id}.md`` in the run directory
        to handle numbered node files.
        """
        run_dir = self.state_path / "runs" / run_id
        # Try numbered files first (e.g. 01-intake.md)
        for f in sorted(run_dir.glob(f"*-{node_id}.md")):
            return _read_md(f)
        # Fall back to unnumbered name
        direct = run_dir / f"{node_id}.md"
        if direct.exists():
            return _read_md(direct)
        raise FileNotFoundError(
            f"node output file for {node_id!r} not found in {run_dir}"
        )
