from __future__ import annotations

import logging
from typing import Any, Sequence, List
import time
from functools import wraps

from langchain_openai import ChatOpenAI
from langchain.schema import ChatMessage
from pydantic import BaseModel, ValidationError
from langchain_core.output_parsers.openai_tools import PydanticToolsParser
from langchain.output_parsers import PydanticOutputParser

from app.config import get_settings

from .base import LLMProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model_name=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=settings.openai_temperature,
            top_p=settings.openai_top_p,
            max_tokens=settings.openai_max_tokens,
        )

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: list[Any] | None = None,
        tool_choice: str | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> tuple[Any, dict]:
        """Execute a chat completion with optional tools / response schema.

        Returned first element is either raw assistant text or a validated
        Pydantic model instance if *response_model* was supplied.
        """

        chain = self._llm

        # Tool binding
        if tools:
            chain = chain.bind_tools(tools=tools, tool_choice=tool_choice or tools[0].__name__)
            parser = PydanticToolsParser(tools=tools)
            chain = chain | parser
        elif response_model is not None:
            parser = PydanticOutputParser(pydantic_object=response_model)
            chain = chain | parser

        # Add retry capability
        chain = chain.with_retry(max_retries=3)

        # Invoke synchronously
        output = chain.invoke(messages)

        # Attempt to extract usage if ChatOpenAI provides metadata
        usage: dict[str, Any] = {}
        if hasattr(self._llm, "client") and hasattr(self._llm.client, "last_response"):
            meta_raw = getattr(self._llm.client, "last_response", None)
            if meta_raw and isinstance(meta_raw, dict):
                usage = meta_raw.get("usage", {})

        meta = {
            "model": settings.openai_model,
            "temperature": settings.openai_temperature,
            "top_p": settings.openai_top_p,
            "max_tokens": settings.openai_max_tokens,
            **usage,
        }
        return output, meta 