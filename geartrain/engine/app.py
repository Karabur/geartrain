"""Engine application — bootstrap and startup logic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from geartrain.engine.config import AgentDefinition, WorkflowDefinition
from geartrain.engine.loader import load_agent, load_engine, load_workflow, load_workspace
from geartrain.engine.sandbox import NoopSandbox
from geartrain.engine.state import FileStateBackend
from geartrain.memory.markdown import MarkdownMemoryStore
from geartrain.memory.noop import NoopMemoryManager
from geartrain.workflows.checkpoints import CheckpointCoordinator


class EngineApp:
    """Central engine application object.

    Loads workspace and engine configs, registers agents and workflows
    from their registry directories, and manages runtime state.
    """

    def __init__(self, workspace_path: Path, engine_path: Path):
        self.workspace_path = Path(workspace_path).resolve()
        self.engine_path = Path(engine_path).resolve()
        self.workspace = load_workspace(str(self.workspace_path))
        self.engine = load_engine(str(self.engine_path))
        # Anchor all runtime paths to the config location, not the process cwd.
        # workspace.yaml lives in .geartrain/ at the repo root, so the root is
        # its grandparent. A start request from any directory then reads and
        # writes the same repo.
        self.repo_root = self._resolve_repo_root()
        self.state_path = self._anchor(self.engine.state.path)
        self.logs_dir = self.repo_root / ".geartrain" / "logs"
        self.work_dir = self._anchor(self.workspace.project.repo_root) / "work"
        self.state_backend = FileStateBackend(self.state_path)
        self.sandbox = NoopSandbox()
        # Legacy no-op boundary, kept until every caller uses the store.
        self.memory_manager = NoopMemoryManager()
        # Real markdown-backed store for memory and the knowledge base.
        self.memory_store = MarkdownMemoryStore(self.workspace.memory.root)
        # Coordinates human-checkpoint pause/resume between the run thread and
        # the HTTP respond endpoint (Phase 7 observability).
        self.checkpoint_coordinator = CheckpointCoordinator()
        self.agents: dict[str, AgentDefinition] = {}
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.running = False
        self.pid: int | None = None

    def _resolve_repo_root(self) -> Path:
        """Return the repo root, anchored to the workspace config location.

        Convention: workspace.yaml lives in .geartrain/ at the repo root, so the
        root is its grandparent.
        """
        return self.workspace_path.parent.parent

    def _anchor(self, raw: str) -> Path:
        """Resolve a config path against the repo root unless already absolute."""
        p = Path(raw)
        return p if p.is_absolute() else (self.repo_root / p)

    def load_registries(self) -> None:
        """Load agents and workflows from registry directories."""
        agent_dir = self._anchor(self.workspace.registries.agents)
        if agent_dir.is_dir():
            for yaml_file in sorted(agent_dir.glob("*.agent.yaml")):
                agent = load_agent(str(yaml_file))
                self.agents[agent.name] = agent

        workflow_dir = self._anchor(self.workspace.registries.workflows)
        if workflow_dir.is_dir():
            for yaml_file in sorted(workflow_dir.glob("*.workflow.yaml")):
                workflow = load_workflow(str(yaml_file))
                self.workflows[workflow.name] = workflow

    def start(self) -> None:
        """Mark as running and persist engine state."""
        self.running = True
        self.pid = os.getpid()
        self.state_backend.write_engine_state(
            engine_name=self.engine.name,
            status="started",
            workspace_name=self.workspace.name,
            pid=self.pid,
        )

    def stop(self) -> None:
        """Mark as stopped and persist engine state."""
        self.running = False
        self.pid = None
        self.state_backend.write_engine_state(
            engine_name=self.engine.name,
            status="stopped",
            workspace_name=self.workspace.name,
        )

    def get_status(self) -> dict[str, Any]:
        """Return a status dict with workspace, agents, and workflows info."""
        return {
            "workspace": self.workspace.name,
            "engine": self.engine.name,
            "running": self.running,
            "agents": sorted(self.agents.keys()),
            "workflows": sorted(self.workflows.keys()),
        }
