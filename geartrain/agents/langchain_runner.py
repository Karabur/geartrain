"""LangChain agent runner — runs in-process with GearTrain tools and context.

Implements the same ``run(task, context) -> str`` contract as the CLI runner,
so workflows don't change when an agent switches type. The runner assembles
context with the shared :class:`ContextBuilder`, resolves ``${...}`` references
in the system prompt at load time, resolves the model and credential through
the engine config, and drives a ``create_agent`` tool-calling loop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from geartrain.agents.context_builder import ContextBuilder
from geartrain.agents.interpolation import interpolate
from geartrain.agents.llm import resolve_llm
from geartrain.agents.tools import ToolRecorder, build_tools

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

    from geartrain.engine.config import (
        AgentDefinition,
        EngineConfig,
        WorkspaceConfig,
    )
    from geartrain.engine.sandbox import Sandbox


class LangchainAgentRunner:
    """Agent runner backed by an in-process LangChain ``create_agent`` graph.

    Pass ``llm`` to inject a chat model directly (tests use a stub); otherwise
    the model is resolved from workspace defaults, the agent's model hint, and
    engine credentials. ``workspace`` and ``engine`` are required for that
    resolution and for interpolating the system prompt.
    """

    def __init__(
        self,
        agent_def: "AgentDefinition",
        sandbox: "Sandbox",
        *,
        workspace: "WorkspaceConfig | None" = None,
        engine: "EngineConfig | None" = None,
        llm: "BaseChatModel | None" = None,
        tool_root: str = ".",
        shell_cwd: str = ".",
        shell_timeout: int = 60,
        namespaces: dict[str, Any] | None = None,
    ) -> None:
        self.agent_def = agent_def
        self.sandbox = sandbox
        self.workspace = workspace
        self.engine = engine
        self._llm = llm
        self.tool_root = tool_root
        self.shell_cwd = shell_cwd
        self.shell_timeout = shell_timeout
        self.recorder = ToolRecorder()

        # Resolve ${...} references in the system prompt at load time, so a bad
        # reference fails before any model call.
        self.system_prompt = self._interpolate_system_prompt(namespaces or {})

    def _interpolate_system_prompt(self, extra: dict[str, Any]) -> str:
        """Resolve workspace/engine/memory/workflow references in the prompt."""
        prompt = self.agent_def.system_prompt
        if not prompt:
            return ""
        namespaces: dict[str, Any] = dict(extra)
        if self.workspace is not None:
            namespaces.setdefault("workspace", self.workspace)
        if self.engine is not None:
            namespaces.setdefault("engine", self.engine)
        return interpolate(prompt, namespaces)

    def _resolve_model(self) -> "BaseChatModel":
        """Return the injected model or build one from resolved config."""
        if self._llm is not None:
            return self._llm
        if self.workspace is None or self.engine is None:
            raise RuntimeError(
                "langchain runner needs a workspace and engine to resolve a "
                "model, or an explicit llm"
            )
        resolved = resolve_llm(self.agent_def.config, self.workspace, self.engine)
        # Import lazily: provider integration packages are optional and only
        # needed when no model is injected.
        from langchain.chat_models import init_chat_model

        return init_chat_model(
            resolved.model,
            model_provider=resolved.provider,
            api_key=resolved.api_key,
        )

    def _build_context_message(self, task: str, context: dict) -> str:
        """Assemble the human message via the shared context builder."""
        builder = ContextBuilder(
            project_root=context.get("project_root", "."),
            project_name=context.get("project_name", ""),
            work_folder=self.agent_def.config.work_folder,
        )
        builder.with_task(task)
        for node_id, output in context.get("prior_outputs", []):
            builder.with_prior_output(node_id, output)
        for scope, entries in context.get("memory_entries", []):
            builder.with_memory_entries(scope, entries)
        return builder.build()

    def run(self, task: str, context: dict) -> str:
        """Run the agent loop and return the final message text."""
        self.recorder = ToolRecorder()
        tools = build_tools(
            self.agent_def.config.tools,
            sandbox=self.sandbox,
            recorder=self.recorder,
            root=self.tool_root,
            forbidden_paths=self.agent_def.config.forbidden_paths,
            shell_cwd=self.shell_cwd,
            shell_timeout=self.shell_timeout,
        )

        model = self._resolve_model()
        agent = create_agent(
            model,
            tools,
            system_prompt=self.system_prompt or None,
        )

        message = self._build_context_message(task, context)
        result = agent.invoke({"messages": [HumanMessage(content=message)]})
        final = result["messages"][-1]
        content = final.content
        if isinstance(content, list):
            # Some models return content as a list of blocks; join the text.
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        return content
