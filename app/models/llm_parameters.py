from __future__ import annotations

from pydantic import BaseModel, Field


class LLMParameters(BaseModel):
    model: str = Field(..., description="LLM model name, e.g., gpt-4o")
    temperature: float
    top_p: float
    max_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    response: str 