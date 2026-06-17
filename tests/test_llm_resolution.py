"""Tests for LLM provider/model resolution (GT-P4-04)."""

import pytest

from geartrain.agents.llm import LlmResolutionError, resolve_llm
from geartrain.engine.config import (
    EngineConfig,
    EngineLlmConfig,
    EngineLlmProvider,
    EngineStateConfig,
    EngineWorkspaceRef,
    LangchainAgentConfig,
    LlmWorkspaceConfig,
    MemoryPaths,
    ProjectConfig,
    WorkspaceConfig,
    WorkspaceRegistries,
)


def _workspace() -> WorkspaceConfig:
    return WorkspaceConfig(
        schema_version=1,
        name="geartrain-core",
        project=ProjectConfig(name="GearTrain", repo_root="."),
        llm=LlmWorkspaceConfig(
            default_provider="anthropic",
            default_model="claude-sonnet-4",
            model_hints={"reasoning": "claude-opus-4", "fast": "claude-haiku-4"},
        ),
        registries=WorkspaceRegistries(agents="a", workflows="w"),
        memory=MemoryPaths(
            root="m", workspace="m/w", workflows="m/wf", agent_types="m/at"
        ),
    )


def _engine() -> EngineConfig:
    return EngineConfig(
        schema_version=1,
        name="local-dev",
        workspace=EngineWorkspaceRef(path=".geartrain/workspace.yaml"),
        llm=EngineLlmConfig(
            default="anthropic",
            providers={
                "anthropic": EngineLlmProvider(api_key_env="ANTHROPIC_API_KEY"),
                "openai": EngineLlmProvider(api_key_env="OPENAI_API_KEY"),
            },
        ),
        state=EngineStateConfig(backend="files", path=".geartrain/state"),
    )


def _agent(**kwargs) -> LangchainAgentConfig:
    return LangchainAgentConfig(type="langchain", **kwargs)


def test_resolves_model_from_hint(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    resolved = resolve_llm(_agent(model_hint="reasoning"), _workspace(), _engine())
    assert resolved.model == "claude-opus-4"
    assert resolved.provider == "anthropic"
    assert resolved.api_key == "secret"
    assert resolved.api_key_env == "ANTHROPIC_API_KEY"


def test_resolves_explicit_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    resolved = resolve_llm(
        _agent(llm_provider="openai", llm_model="gpt-x"), _workspace(), _engine()
    )
    assert resolved.provider == "openai"
    assert resolved.model == "gpt-x"


def test_falls_back_to_workspace_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    resolved = resolve_llm(_agent(), _workspace(), _engine())
    assert resolved.provider == "anthropic"
    assert resolved.model == "claude-sonnet-4"


def test_unknown_hint_raises(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    with pytest.raises(LlmResolutionError, match="unknown model hint"):
        resolve_llm(_agent(model_hint="nope"), _workspace(), _engine())


def test_missing_credential_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LlmResolutionError, match="missing credential"):
        resolve_llm(_agent(), _workspace(), _engine())


def test_unconfigured_provider_raises(monkeypatch):
    with pytest.raises(LlmResolutionError, match="not configured"):
        resolve_llm(_agent(llm_provider="cohere"), _workspace(), _engine())
