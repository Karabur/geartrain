"""Tests for prompt variable interpolation (GT-P4-05)."""

import pytest

from geartrain.agents.interpolation import InterpolationError, interpolate
from geartrain.engine.config import (
    LlmWorkspaceConfig,
    ProjectConfig,
    WorkspaceConfig,
    WorkspaceRegistries,
    MemoryPaths,
)


def _workspace() -> WorkspaceConfig:
    return WorkspaceConfig(
        schema_version=1,
        name="geartrain-core",
        project=ProjectConfig(name="GearTrain", repo_root="."),
        llm=LlmWorkspaceConfig(
            default_provider="anthropic", default_model="claude-sonnet-4"
        ),
        registries=WorkspaceRegistries(agents="a", workflows="w"),
        memory=MemoryPaths(
            root="m", workspace="m/w", workflows="m/wf", agent_types="m/at"
        ),
    )


def test_resolves_workspace_reference():
    ws = _workspace()
    result = interpolate(
        "You work on ${workspace.project.name}.", {"workspace": ws}
    )
    assert result == "You work on GearTrain."


def test_resolves_multiple_references():
    ws = _workspace()
    out = interpolate(
        "${workspace.project.name} uses ${workspace.llm.default_model}.",
        {"workspace": ws},
    )
    assert out == "GearTrain uses claude-sonnet-4."


def test_resolves_dict_namespace():
    out = interpolate(
        "Ticket ${workflow.ticket}", {"workflow": {"ticket": "GT-P4-05"}}
    )
    assert out == "Ticket GT-P4-05"


def test_unresolved_reference_raises():
    ws = _workspace()
    with pytest.raises(InterpolationError, match="unresolved reference"):
        interpolate("${workspace.project.missing}", {"workspace": ws})


def test_unknown_namespace_raises():
    with pytest.raises(InterpolationError):
        interpolate("${memory.note}", {})


def test_template_without_references_passes_through():
    assert interpolate("plain text", {}) == "plain text"
