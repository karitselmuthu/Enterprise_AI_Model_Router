import json
import logging
import sys
from datetime import UTC, datetime
from uuid import uuid4

from app.models.contracts import InferenceResult

audit_logger = logging.getLogger("enterprise_router.audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False
if not audit_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)


def record_attempt(
    *, category: str, model_id: str, provider: str, sensitivity: str,
    outcome: str, result: InferenceResult | None = None, task_type: str | None = None,
    fallback_used: bool = False, request_id: str | None = None,
    entry_point: str = "unknown",
) -> str:
    """Emit metadata only; request and response bodies are deliberately excluded."""
    event_id = str(uuid4())
    audit_logger.info(
        json.dumps(
            {
                "event_id": event_id,
                "request_id": request_id,
                "entry_point": entry_point,
                "timestamp": datetime.now(UTC).isoformat(),
                "task_type": task_type,
                "sensitivity": sensitivity,
                "category": category,
                "model_id": model_id,
                "provider": provider,
                "fallback_used": fallback_used,
                "outcome": outcome,
                "prompt_tokens": result.prompt_tokens if result else None,
                "completion_tokens": result.completion_tokens if result else None,
            }
        )
    )
    return event_id
