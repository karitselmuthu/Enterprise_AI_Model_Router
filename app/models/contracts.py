from enum import StrEnum
from typing import Literal, Protocol
import base64
import binascii

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ModelCategory(StrEnum):
    SLM = "SLM"
    LLM = "LLM"
    LRM = "LRM"
    VLM = "VLM"


class InferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ModelCategory
    prompt: str = Field(min_length=1, max_length=20_000)
    sensitivity: Literal["public", "internal", "restricted"] = "internal"
    image_base64: str | None = Field(default=None, max_length=7_000_000)
    image_mime_type: str | None = None

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("prompt must contain non-whitespace text")
        return prompt

    @model_validator(mode="after")
    def validate_image(self) -> "InferenceRequest":
        if (self.image_base64 is None) != (self.image_mime_type is None):
            raise ValueError("image_base64 and image_mime_type must be provided together")
        if self.image_base64 is not None:
            if self.category != ModelCategory.VLM:
                raise ValueError("image input requires VLM category")
            if self.image_mime_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise ValueError("unsupported image MIME type")
            try:
                image_bytes = base64.b64decode(self.image_base64, validate=True)
            except binascii.Error as exc:
                raise ValueError("invalid base64 image") from exc
            if len(image_bytes) > 5_000_000:
                raise ValueError("image exceeds 5 MB limit")
        return self


class InferenceResult(BaseModel):
    category: ModelCategory
    model_id: str
    provider: str
    output: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ModelProvider(Protocol):
    async def generate(self, request: InferenceRequest) -> InferenceResult: ...
