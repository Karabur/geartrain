"""Engine application — bootstrap and startup logic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from geartrain.engine.config import AgentDefinition, WorkflowDefinition
from geartrain.engine.loader import load_agent, load_engine, load_workflow, load_workspace
from geartrain.engine.sandbox import NoopSandbox
from geartrain.engine.state import FileStateBackend, create_state_backend
from geartrain.memory.markdown import MarkdownMemoryStore
from geartrain.memory.noop import NoopMemoryManager


class EngineApp:
    """Central engine application object.

    Loads workspace and engine configs, registers agents and workflows
    from their registry directories, and manages runtime state.
    """

    def __init__(self, workspace_path: Path, engine_path: Path):
        self.workspace_path = workspace_path
        self.engine_path = engine_path
        self.workspace = load_workspace(str(workspace_path))
        self.engine = load_engine(str(engine_path))
        self.state_backend = create_state_backend(self.engine)
        self.sandbox = NoopSandbox()
        # Legacy no-op boundary, kept until every caller uses the store.
        self.memory_manager = NoopMemoryManager()
        # Real markdown-backed store for memory and the knowledge base.
        self.memory_store = MarkdownMemoryStore(self.workspace.memory.root)
        self.agents: dict[str, AgentDefinition] = {}
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.running = False
        self.pid: int | None = None

    def load_registries(self) -> None:
        """Load agents and workflows from registry directories."""
        agent_dir = Path(self.workspace.registries.agents)
        if agent_dir.is_dir():
            for yaml_file in sorted(agent_dir.glob("*.agent.yaml")):
                agent = load_agent(str(yaml_file))
                self.agents[agent.name] = agent

        workflow_dir = Path(self.workspace.registries.workflows)
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
