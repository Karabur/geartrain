"""YAML loading utilities for all GearTrain config types.

Loads YAML files into validated Pydantic models. Errors are raised
immediately with field-level detail from Pydantic validation.
"""

from pathlib import Path

import yaml

from geartrain.engine.config import (
    AgentDefinition,
    EngineConfig,
    MemoryEntry,
    WorkflowDefinition,
    WorkspaceConfig,
)


def _load_yaml(path: str) -> dict:
    """Load and parse a YAML file into a plain dict.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the file is empty or the top-level value is not a mapping.
        yaml.YAMLError: if the file contains invalid YAML syntax.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    text = p.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(
            f"expected a YAML mapping at top level in {path}, "
            f"got {type(data).__name__}"
        )
    return data


def load_workspace(path: str) -> WorkspaceConfig:
    """Load a workspace.yaml file into a validated WorkspaceConfig."""
    raw = _load_yaml(path)
    return WorkspaceConfig(**raw)


def load_engine(path: str) -> EngineConfig:
    """Load an engine.yaml file into a validated EngineConfig."""
    raw = _load_yaml(path)
    return EngineConfig(**raw)


def load_agent(path: str) -> AgentDefinition:
    """Load an agent.yaml file into a validated AgentDefinition."""
    raw = _load_yaml(path)
    return AgentDefinition(**raw)


def load_workflow(path: str) -> WorkflowDefinition:
    """Load a workflow.yaml file into a validated WorkflowDefinition."""
    raw = _load_yaml(path)
    return WorkflowDefinition(**raw)


def load_memory_entry(path: str) -> MemoryEntry:
    """Load a memory entry from a markdown file with YAML frontmatter.

    Expects the file to start with ``---`` followed by YAML metadata and
    a closing ``---``. Only the frontmatter is parsed; the body is ignored.

    Raises:
        ValueError: if the file lacks valid frontmatter delimiters.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"memory entry not found: {path}")
    text = p.read_text(encoding="utf-8")

    if not text.lstrip().startswith("---"):
        raise ValueError(f"no YAML frontmatter found in {path}")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"incomplete YAML frontmatter in {path}")

    frontmatter_yaml = parts[1]
    data = yaml.safe_load(frontmatter_yaml)
    if not isinstance(data, dict):
        raise ValueError(
            f"expected a YAML mapping in frontmatter of {path}, "
            f"got {type(data).__name__ if data is not None else 'empty'}"
        )
    return MemoryEntry(**data)
