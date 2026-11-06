from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskType(StrEnum):
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    SHORT_SUMMARY = "short_summary"
    SUMMARY = "summary"
    KNOWLEDGE = "knowledge"
    REASONING = "reasoning"
    VISION = "vision"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class RoutingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=20_000)
    task_type: TaskType | None = None
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    contains_image: bool = False

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must contain non-whitespace text")
        return value


def classify(request: RoutingRequest) -> TaskType:
    if request.contains_image:
        return TaskType.VISION
    if request.task_type is not None:
        return request.task_type
    prompt = request.prompt.lower()
    if any(term in prompt for term in ("root cause", "remediation", "migration dependencies", "analyze why")):
        return TaskType.REASONING
    if any(term in prompt for term in ("extract", "metadata", "fields")):
        return TaskType.EXTRACTION
    if any(term in prompt for term in ("knowledge base", "documentation", "explain")):
        return TaskType.KNOWLEDGE
    if "summarize" in prompt or "summary" in prompt:
        return TaskType.SHORT_SUMMARY if len(prompt) < 500 else TaskType.SUMMARY
    return TaskType.CLASSIFICATION
