from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from langchain.schema import ChatMessage
from pydantic import BaseModel


class LLMProvider(ABC):
    """Abstract interface for a language-model provider."""

    name: str = "abstract"

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[Any] | None = None,
        tool_choice: str | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> tuple[Any, dict]:
        """Run a chat completion.

        Returns
        -------
        tuple[Any, dict]
            assistant response (str or validated model), usage_metadata
        """
 