"""LLM provider and model resolution for langchain agents.

Resolves the concrete provider and model from three sources, in order:
a model hint mapped through workspace ``model_hints``, an explicit
provider/model on the agent, or the workspace defaults. Credentials always
come from the engine config — never from agent definitions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geartrain.engine.config import (
        EngineConfig,
        LangchainAgentConfig,
        WorkspaceConfig,
    )


class LlmResolutionError(Exception):
    """Raised when a provider/model can't be resolved or a credential is missing."""


@dataclass
class ResolvedLlm:
    """A fully resolved provider, model, and credential.

    ``api_key`` holds the secret value read from the environment; ``api_key_env``
    names the variable it came from so callers can log the source without the
    secret.
    """

    provider: str
    model: str
    api_key_env: str
    api_key: str


def resolve_llm(
    agent_cfg: "LangchainAgentConfig",
    workspace: "WorkspaceConfig",
    engine: "EngineConfig",
) -> ResolvedLlm:
    """Resolve the model and credential for a langchain agent.

    Raises ``LlmResolutionError`` for an unknown model hint, an unconfigured
    provider, or a missing credential.
    """
    model = _resolve_model(agent_cfg, workspace)
    provider = agent_cfg.llm_provider or workspace.llm.default_provider

    providers = engine.llm.providers
    if provider not in providers:
        raise LlmResolutionError(
            f"provider {provider!r} is not configured in engine.llm.providers; "
            f"available providers: {sorted(providers)}"
        )

    api_key_env = providers[provider].api_key_env
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise LlmResolutionError(
            f"missing credential for provider {provider!r}: environment variable "
            f"{api_key_env!r} is not set"
        )

    return ResolvedLlm(
        provider=provider,
        model=model,
        api_key_env=api_key_env,
        api_key=api_key,
    )


def _resolve_model(
    agent_cfg: "LangchainAgentConfig", workspace: "WorkspaceConfig"
) -> str:
    """Pick the concrete model name from hint, explicit field, or default."""
    if agent_cfg.model_hint:
        hints = workspace.llm.model_hints
        if agent_cfg.model_hint not in hints:
            raise LlmResolutionError(
                f"unknown model hint {agent_cfg.model_hint!r}; "
                f"workspace defines: {sorted(hints)}"
            )
        return hints[agent_cfg.model_hint]
    if agent_cfg.llm_model:
        return agent_cfg.llm_model
    return workspace.llm.default_model
