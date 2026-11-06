from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelCategory(StrEnum):
    SLM = "SLM"
    LLM = "LLM"
    LRM = "LRM"
    VLM = "VLM"


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ModelCategory
    prompt: str = Field(min_length=1, max_length=20_000)

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("prompt must contain non-whitespace text")
        return prompt


class InferenceResult(BaseModel):
    category: ModelCategory
    model_id: str
    provider: str
    output: str


class ModelProvider(Protocol):
    async def generate(self, request: InferenceRequest) -> InferenceResult: ...
