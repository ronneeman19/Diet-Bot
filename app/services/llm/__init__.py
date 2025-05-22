from __future__ import annotations

from typing import Sequence, Any

from langchain.schema import ChatMessage

from .registry import get_provider

_provider = get_provider()

__all__ = [
    "chat_completion",
]


def chat_completion(
    messages: Sequence[ChatMessage],
    *,
    tools: list[Any] | None = None,
    tool_choice: str | None = None,
    response_model: type | None = None,
):
    """Facade for the configured LLM provider (synchronous).

    Returns (assistant_response, usage_dict).
    """

    return _provider.chat(
        messages, tools=tools, tool_choice=tool_choice, response_model=response_model
    ) 