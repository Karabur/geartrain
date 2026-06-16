"""Config file validator for GearTrain.

Checks config files at three levels:
1. Shape validation (Pydantic model errors from loader).
2. Reference validation (agents, workflows, paths, credentials exist).
3. Runtime readiness (paths writable, commands on PATH).

Makes no LLM or network calls.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from geartrain.engine.config import (
    AgentDefinition,
    CliAgentConfig,
    WorkspaceConfig,
)
from geartrain.engine.loader import (
    load_agent,
    load_engine,
    load_workflow,
    load_workspace,
)


@dataclass
class Diagnostic:
    """A single validation finding."""

    file: Path
    line: int | None
    sev: str  # "error" or "warning"
    fps: str  # field path, e.g. "workspace.llm.default_provider"
    message: str  # human-readable issue + fix suggestion


def _repo_root(workspace_path: Path) -> Path:
    """Determine the repo root from a workspace config path.

    Convention: workspace.yaml lives in .geartrain/ at the repo root,
    so the root is parent.parent. Falls back to parent if that fails.
    """
    candidate = workspace_path.parent.parent
    if candidate.is_dir():
        return candidate
    return workspace_path.parent


# --- Shape validation (wraps loader calls) ----------------------------------


def _shape_error(path: Path, exc: Exception) -> Diagnostic:
    """Convert a loader exception into a diagnostic."""
    return Diagnostic(
        file=path,
        line=None,
        sev="error",
        fps="(root)",
        message=f"{type(exc).__name__}: {exc}",
    )


def _load_workspace_safe(path: Path) -> tuple[WorkspaceConfig | None, list[Diagnostic]]:
    """Load workspace config. Returns (config, diagnostics)."""
    try:
        cfg = load_workspace(str(path))
        return cfg, []
    except Exception as exc:
        return None, [_shape_error(path, exc)]


def _load_engine_safe(path: Path) -> tuple[EngineConfig | None, list[Diagnostic]]:
    """Load engine config. Returns (config, diagnostics)."""
    try:
        cfg = load_engine(str(path))
        return cfg, []
    except Exception as exc:
        return None, [_shape_error(path, exc)]


def _load_agent_safe(path: Path) -> tuple[AgentDefinition | None, list[Diagnostic]]:
    """Load agent config. Returns (config, diagnostics)."""
    try:
        cfg = load_agent(str(path))
        return cfg, []
    except Exception as exc:
        return None, [_shape_error(path, exc)]


def _load_workflow_safe(path: Path) -> tuple[WorkflowDefinition | None, list[Diagnostic]]:
    """Load workflow config. Returns (config, diagnostics)."""
    try:
        cfg = load_workflow(str(path))
        return cfg, []
    except Exception as exc:
        return None, [_shape_error(path, exc)]


# --- Workspace validation ---------------------------------------------------


def validate_workspace(path: Path) -> list[Diagnostic]:
    """Validate a workspace config file.

    Checks shape (via loader) and reference validity (registry paths,
    memory paths exist on disk).
    """
    cfg, diags = _load_workspace_safe(path)
    if cfg is None:
        return diags

    root = _repo_root(path)

    # Registry paths
    for reg_field in ("agents", "workflows"):
        raw = getattr(cfg.registries, reg_field)
        p = root / raw
        if not p.is_dir():
            diags.append(Diagnostic(
                file=path, line=None, sev="error",
                fps=f"workspace.registries.{reg_field}",
                message=(
                    f"registry path {raw!r} does not exist ({p}) — "
                    f"create the directory or fix the path"
                ),
            ))

    # Memory paths
    for mem_field in ("root", "workspace", "workflows", "agent_types"):
        raw = getattr(cfg.memory, mem_field)
        p = root / raw
        if not p.exists():
            diags.append(Diagnostic(
                file=path, line=None, sev="error",
                fps=f"workspace.memory.{mem_field}",
                message=(
                    f"memory path {raw!r} does not exist ({p}) — "
                    f"create the directory"
                ),
            ))

    return diags


# --- Engine validation ------------------------------------------------------


def validate_engine(
    path: Path,
    workspace: WorkspaceConfig | None = None,
    repo_root: Path | None = None,
) -> list[Diagnostic]:
    """Validate an engine config file.

    Checks shape, workspace reference, credential consistency, and
    runtime readiness (state path writable).

    ``repo_root`` is the project root directory. If not given, it is
    inferred from the engine file path (assumes .geartrain/engines/ layout).
    """
    cfg, diags = _load_engine_safe(path)
    if cfg is None:
        return diags

    if repo_root is not None:
        engine_root = repo_root
    else:
        # Infer from engine file path. Convention: .geartrain/engines/
        # so repo root is parent.parent (engines -> .geartrain -> repo).
        # But .geartrain itself is inside the repo, so we need parent.parent.parent.
        engine_root = path.parent.parent.parent
        if not engine_root.is_dir():
            engine_root = path.parent.parent
        if not engine_root.is_dir():
            engine_root = path.parent

    # Workspace path resolves
    ws_p = engine_root / cfg.workspace.path
    if not ws_p.is_file():
        diags.append(Diagnostic(
            file=path, line=None, sev="error",
            fps="engine.workspace.path",
            message=(
                f"workspace path {cfg.workspace.path!r} does not exist ({ws_p}) — "
                f"point to a valid workspace.yaml"
            ),
        ))

    # Credential references: engine credentials should reference providers
    # that exist in engine.llm.providers or workspace integrations.
    # We only warn — missing credentials may be intentional for offline use.
    if cfg.credentials:
        for cred_name in cfg.credentials:
            if cred_name not in cfg.llm.providers:
                diags.append(Diagnostic(
                    file=path, line=None, sev="warning",
                    fps=f"engine.credentials.{cred_name}",
                    message=(
                        f"credential {cred_name!r} has no matching LLM provider — "
                        f"this is fine if used for non-LLM integrations"
                    ),
                ))

    # State path writable
    state_p = engine_root / cfg.state.path
    if state_p.exists() and not os.access(str(state_p), os.W_OK):
        diags.append(Diagnostic(
            file=path, line=None, sev="error",
            fps="engine.state.path",
            message=(
                f"state path {cfg.state.path!r} is not writable — "
                f"fix permissions"
            ),
        ))
    elif not state_p.exists():
        sp = state_p.parent
        if sp.exists() and not os.access(str(sp), os.W_OK):
            diags.append(Diagnostic(
                file=path, line=None, sev="error",
                fps="engine.state.path",
                message=(
                    f"state path parent is not writable — "
                    f"the engine cannot create {cfg.state.path!r}"
                ),
            ))

    return diags


# --- Agent validation -------------------------------------------------------


def validate_agent(
    path: Path,
    workspace: WorkspaceConfig,
    repo_root: Path | None = None,
) -> list[Diagnostic]:
    """Validate an agent config file.

    Checks shape, CLI command existence, work folder existence, and
    model hint references.
    """
    cfg, diags = _load_agent_safe(path)
    if cfg is None:
        return diags

    if repo_root is None:
        # Infer: agent files are in .geartrain/agents/, so parent.parent.parent
        # is the repo root. Fall back to parent.parent.
        repo_root = path.parent.parent.parent
        if not repo_root.is_dir():
            repo_root = path.parent.parent

    if isinstance(cfg.config, CliAgentConfig):
        # Command on PATH
        cmd = cfg.config.command.split()[0] if cfg.config.command else ""
        if cmd and shutil.which(cmd) is None:
            diags.append(Diagnostic(
                file=path, line=None, sev="warning",
                fps="agent.cli.command",
                message=(
                    f"command {cmd!r} not found on PATH — "
                    f"install it or update the command field"
                ),
            ))

        # Work folder exists
        wf = cfg.config.work_folder
        wf_p = repo_root / wf
        if not wf_p.exists():
            diags.append(Diagnostic(
                file=path, line=None, sev="warning",
                fps="agent.cli.work_folder",
                message=(
                    f"work folder {wf!r} does not exist ({wf_p}) — "
                    f"it will be created at runtime if writable"
                ),
            ))

    return diags


# --- Workflow validation ----------------------------------------------------


def validate_workflow(
    path: Path,
    workspace: WorkspaceConfig,
    agents: dict[str, AgentDefinition],
) -> list[Diagnostic]:
    """Validate a workflow config file.

    Checks shape, agent references, and graph entry/node consistency.
    """
    cfg, diags = _load_workflow_safe(path)
    if cfg is None:
        return diags

    # Agent references: values in workflow.agents should exist in agent registry
    for role, agent_name in cfg.agents.items():
        if agent_name not in agents:
            diags.append(Diagnostic(
                file=path, line=None, sev="error",
                fps=f"workflow.agents.{role}",
                message=(
                    f"agent {agent_name!r} (role {role!r}) not found in registry — "
                    f"available agents: {sorted(agents.keys())}"
                ),
            ))

    # Graph entry should exist in nodes
    if cfg.graph.entry not in cfg.graph.nodes:
        diags.append(Diagnostic(
            file=path, line=None, sev="error",
            fps="workflow.graph.entry",
            message=(
                f"entry node {cfg.graph.entry!r} not in graph.nodes — "
                f"add it or fix the entry field"
            ),
        ))

    # Graph agent references: nodes with type=agent should reference valid agents
    for node_name, node_def in cfg.graph.nodes.items():
        if isinstance(node_def, dict) and node_def.get("type") == "agent":
            node_agent = node_def.get("agent", "")
            if node_agent and node_agent not in agents:
                diags.append(Diagnostic(
                    file=path, line=None, sev="error",
                    fps=f"workflow.graph.nodes.{node_name}.agent",
                    message=(
                        f"node {node_name!r} references agent {node_agent!r} "
                        f"which is not in the registry — "
                        f"available: {sorted(agents.keys())}"
                    ),
                ))

    return diags


# --- Memory validation ------------------------------------------------------


def validate_memory(path: Path) -> list[Diagnostic]:
    """Validate a memory directory.

    Checks that markdown files have valid frontmatter (shape via loader).
    """
    diags: list[Diagnostic] = []
    if not path.is_dir():
        return [Diagnostic(
            file=path, line=None, sev="error",
            fps="memory.root",
            message=f"memory path {path} is not a directory",
        )]

    for md in sorted(path.glob("*.md")):
        try:
            from geartrain.engine.loader import load_memory_entry
            load_memory_entry(str(md))
        except Exception as exc:
            diags.append(Diagnostic(
                file=md, line=None, sev="error",
                fps="memory.entry",
                message=f"{type(exc).__name__}: {exc}",
            ))

    return diags


# --- Collect agents from registry -------------------------------------------


def _load_all_agents(
    base: Path, workspace: WorkspaceConfig
) -> tuple[dict[str, AgentDefinition], list[Diagnostic]]:
    """Load all agent definitions from the workspace registry."""
    agents_dir = base / workspace.registries.agents
    diags: list[Diagnostic] = []
    agents: dict[str, AgentDefinition] = {}

    if not agents_dir.is_dir():
        return agents, diags

    for f in sorted(agents_dir.glob("*.agent.yaml")):
        cfg, agent_diags = _load_agent_safe(f)
        if cfg is not None:
            agents[cfg.name] = cfg
        diags.extend(agent_diags)

    return agents, diags


# --- validate_all -----------------------------------------------------------


def validate_all(
    workspace_path: Path,
    engine_path: Path | None = None,
) -> list[Diagnostic]:
    """Run full validation: workspace, engine, agents, workflows, memory.

    Order: workspace -> engine -> agents -> workflows -> memory -> cross-references.
    """
    diags: list[Diagnostic] = []

    # 1. Workspace
    ws_diags = validate_workspace(workspace_path)
    diags.extend(ws_diags)

    # If workspace failed shape, stop early
    cfg, _ = _load_workspace_safe(workspace_path)
    if cfg is None:
        return diags

    root = _repo_root(workspace_path)

    # 2. Engine
    if engine_path is not None:
        diags.extend(validate_engine(engine_path, workspace=cfg, repo_root=root))

    # 3. Agents (shape only — reference checks in validate_agent)
    agents, agent_diags = _load_all_agents(root, cfg)
    diags.extend(agent_diags)

    # Agent reference checks
    agents_dir = root / cfg.registries.agents
    if agents_dir.is_dir():
        for f in sorted(agents_dir.glob("*.agent.yaml")):
            d = validate_agent(f, cfg, repo_root=root)
            # Filter out shape errors (already in agent_diags) and keep only ref checks
            for diag in d:
                if diag not in agent_diags:
                    diags.append(diag)

    # 4. Workflows
    wf_dir = root / cfg.registries.workflows
    if wf_dir.is_dir():
        for f in sorted(wf_dir.glob("*.workflow.yaml")):
            diags.extend(validate_workflow(f, cfg, agents))

    # 5. Memory
    mem_dir = root / cfg.memory.root
    if mem_dir.exists():
        diags.extend(validate_memory(mem_dir))

    # 6. Runtime readiness (already done inline above)

    return diags


# --- Formatting -------------------------------------------------------------


def format_diagnostics(diags: list[Diagnostic]) -> str:
    """Format diagnostics for terminal output.

    Format per diagnostic:
        <file>:<line>
        <severity> <field>
        <message>
    """
    if not diags:
        return "No issues found."

    lines: list[str] = []
    for d in diags:
        loc = str(d.file)
        if d.line is not None:
            loc += f":{d.line}"
        lines.append(loc)
        lines.append(f"  {d.sev} {d.fps}")
        lines.append(f"    {d.message}")
    return "\n".join(lines)
