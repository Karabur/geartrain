"""Shared fixtures.

``isolated_project`` builds a minimal ``.geartrain/`` scaffold under ``tmp_path``
with absolute, cwd-independent config paths. ``isolated_engine`` loads an
``EngineApp`` from it. Both let workflow-start tests run without touching the
real repo and without ``monkeypatch.chdir``.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from geartrain.engine.app import EngineApp


def _write_scaffold(root: Path) -> None:
    """Write a minimal .geartrain/ project tree rooted at ``root``.

    All registry, state, memory, and work paths are absolute so the engine reads
    and writes only inside ``root`` regardless of the process cwd.
    """
    gt = root / ".geartrain"
    gt.mkdir(parents=True, exist_ok=True)

    (gt / "workspace.yaml").write_text(dedent(f"""\
        schema_version: 1
        name: test-ws
        description: test workspace
        project:
          name: TestProject
          repo_root: "{root}"
        llm:
          default_provider: anthropic
          default_model: claude-sonnet-4
        registries:
          agents: {gt / "agents"}
          workflows: {gt / "workflows"}
        memory:
          root: {gt / "memory"}
          workspace: {gt / "memory" / "workspace"}
          workflows: {gt / "memory" / "workflows"}
          agent_types: {gt / "memory" / "agent-types"}
    """))

    (gt / "engines").mkdir(exist_ok=True)
    (gt / "engines" / "local.engine.yaml").write_text(dedent(f"""\
        schema_version: 1
        name: local-test
        description: test engine
        workspace:
          path: .geartrain/workspace.yaml
        llm:
          default: anthropic
          providers:
            anthropic:
              api_key_env: ANTHROPIC_API_KEY
        state:
          backend: files
          path: {gt / "state"}
    """))

    (gt / "agents").mkdir(exist_ok=True)
    (gt / "agents" / "coder.agent.yaml").write_text(dedent("""\
        schema_version: 1
        name: coder
        description: coder agent
        type: cli
        cli:
          command: echo
          credential: test
        system_prompt: "You are coder."
        memory:
          read: []
    """))
    (gt / "agents" / "lead.agent.yaml").write_text(dedent("""\
        schema_version: 1
        name: lead
        description: lead agent
        type: cli
        cli:
          command: echo
          credential: test
        system_prompt: "You are lead."
        memory:
          read: []
    """))

    (gt / "workflows").mkdir(exist_ok=True)
    _two_node_workflow(gt / "workflows" / "sample-dev.workflow.yaml", "sample-dev")
    _two_node_workflow(gt / "workflows" / "other-flow.workflow.yaml", "other-flow")

    for mem in ("memory", "memory/workspace", "memory/workflows", "memory/agent-types"):
        (gt / mem).mkdir(parents=True, exist_ok=True)
    (gt / "state").mkdir(exist_ok=True)
    (gt / "logs").mkdir(exist_ok=True)

    for wd in ("work", "work/todo", "work/in-progress", "work/done"):
        (root / wd).mkdir(parents=True, exist_ok=True)


def _two_node_workflow(path: Path, name: str) -> None:
    """Write a coder->lead manual-trigger workflow named ``name``."""
    path.write_text(dedent(f"""\
        schema_version: 1
        name: {name}
        description: dev workflow
        trigger:
          type: manual
        agents:
          coder: coder
          lead: lead
        graph:
          entry: run_coder
          nodes:
            run_coder:
              type: agent
              agent: coder
              inputs:
                task: "${{trigger.task}}"
              output_key: coder_output
              transitions:
                default: run_lead
            run_lead:
              type: agent
              agent: lead
              inputs:
                task: "${{nodes.coder_output.output}}"
              output_key: lead_output
              transitions:
                default: end
    """))


@pytest.fixture
def isolated_project(tmp_path: Path) -> Path:
    """Return the root of a self-contained .geartrain/ scaffold under tmp_path."""
    _write_scaffold(tmp_path)
    return tmp_path


@pytest.fixture
def isolated_engine(isolated_project: Path) -> EngineApp:
    """Load an EngineApp from the isolated scaffold with registries loaded."""
    gt = isolated_project / ".geartrain"
    app = EngineApp(
        workspace_path=gt / "workspace.yaml",
        engine_path=gt / "engines" / "local.engine.yaml",
    )
    app.load_registries()
    return app
