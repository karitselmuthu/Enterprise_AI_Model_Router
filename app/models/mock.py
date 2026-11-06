from app.models.contracts import InferenceRequest, InferenceResult, ModelCategory


class MockProvider:
    """Deterministic stand-in for a configured model; performs no inference."""

    def __init__(self, category: ModelCategory, model_id: str) -> None:
        self.category = category
        self.model_id = model_id

    async def generate(self, request: InferenceRequest) -> InferenceResult:
        return InferenceResult(
            category=self.category,
            model_id=self.model_id,
            provider="mock",
            output=f"Mock {self.category} response for: {request.prompt.strip()}",
        )
