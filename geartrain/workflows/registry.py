"""Workflow registry — loads and indexes workflow configurations."""

from __future__ import annotations

from pathlib import Path

from geartrain.engine.loader import load_workflow
from geartrain.engine.config import WorkflowDefinition


def load_workflow_registry(workflows_dir: Path) -> dict[str, WorkflowDefinition]:
    """Load all *.workflow.yaml files from a directory into a name->def map."""
    result: dict[str, WorkflowDefinition] = {}
    if not workflows_dir.is_dir():
        return result
    for yaml_file in sorted(workflows_dir.glob("*.workflow.yaml")):
        wf = load_workflow(str(yaml_file))
        result[wf.name] = wf
    return result
