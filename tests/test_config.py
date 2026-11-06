from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import load_config


def test_missing_category_fails_configuration(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text("models:\n  SLM: {id: mock-slm, provider: mock}\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Missing model categories"):
        load_config(path)


def test_non_mock_provider_fails_configuration(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        "models:\n"
        "  SLM: {id: mock-slm, provider: cloud}\n"
        "  LLM: {id: mock-llm, provider: mock}\n"
        "  LRM: {id: mock-lrm, provider: mock}\n"
        "  VLM: {id: mock-vlm, provider: mock}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="provider"):
        load_config(path)
