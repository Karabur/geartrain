"""A scripted chat model for offline langchain agent tests.

Returns a fixed list of ``AIMessage`` responses in order, one per model turn.
Implements ``bind_tools`` as a no-op so ``create_agent`` can run a tool loop
without any real provider or network call.
"""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class StubChatModel(BaseChatModel):
    """Emits pre-scripted AI messages, ignoring the input messages.

    Records every batch of input messages in ``seen_messages`` so tests can
    assert what context the agent assembled.
    """

    responses: list[AIMessage]
    index: int = 0
    seen_messages: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "stub"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "StubChatModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen_messages.append(list(messages))
        message = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call_message(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    """Build an AI message that requests a single tool call."""
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id}],
    )
