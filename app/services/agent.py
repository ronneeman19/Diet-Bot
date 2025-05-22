"""Agent orchestration using LangChain tools."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Any

from langchain.schema import ChatMessage

from app.services.llm import chat_completion
from app.services.agent_tools import TOOL_REGISTRY
from app.services.firebase_db import firebase_db

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are DietBot, a helpful diet coach. You must communicate exclusively "
    "through calling ONE JSON tool per turn. After thinking, decide the most "
    "appropriate tool. If you need to send a plain reply, use the Respond tool."
)


class AgentRunner:
    """Simple looped agent to process a single user message."""

    MAX_ITERS = 4

    def __init__(self, user_id: str):
        self.user_id = user_id
        profile = firebase_db.get_profile(user_id)
        if profile is None:
            raise ValueError("Unknown user")
        self.phone_number = profile.phone_number

    def build_context(self) -> List[ChatMessage]:
        """Return last N messages as ChatMessage objects."""
        recent = firebase_db.fetch_recent_messages(self.user_id, limit=10, as_dict=True)
        msgs: List[ChatMessage] = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        for m in reversed(recent):
            msgs.append(ChatMessage(role=m["role"], content=m["content"]))
        return msgs

    def run(self, incoming_text: str) -> None:
        messages = self.build_context()
        messages.append(ChatMessage(role="user", content=incoming_text))

        for _ in range(self.MAX_ITERS):
            # Call LLM with tools
            tool_classes = [cls for cls, _ in TOOL_REGISTRY.values() if cls]
            response, _ = chat_completion(messages, tools=tool_classes)

            if not isinstance(response, BaseModel):
                # Raw text – send it directly via Respond tool
                from app.services.agent_tools import respond_exec, RespondInput

                respond_exec(self.user_id, self.phone_number, RespondInput(response=response))
                break

            tool_name = response.__class__.__name__
            input_data = response
            entry = TOOL_REGISTRY.get(tool_name)
            if entry is None:
                logger.warning("Unknown tool returned: %s", tool_name)
                break
            _, executor = entry
            try:
                if tool_name == "Respond":
                    executor(self.user_id, self.phone_number, input_data)
                    break
                elif tool_name in {"FetchRecentMessages", "EstimateCalories"}:
                    executor(self.user_id, input_data)
                else:
                    executor(self.user_id)
                # Append assistant tool result to context
                messages.append(ChatMessage(role="assistant", content=input_data.model_dump_json()))
            except Exception as exc:
                logger.error("Tool execution failed: %s", exc)
                break 