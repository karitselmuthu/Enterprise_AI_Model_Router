from pydantic import BaseModel

from app.models.contracts import InferenceResult


class QualityResult(BaseModel):
    accepted: bool
    reason: str


def assess_quality(result: InferenceResult) -> QualityResult:
    output = result.output.strip().lower()
    if not output:
        return QualityResult(accepted=False, reason="empty output")
    if any(output.startswith(phrase) for phrase in ("i don't know", "i cannot answer", "unable to answer")):
        return QualityResult(accepted=False, reason="provider abstained")
    return QualityResult(accepted=True, reason="basic output checks passed")
