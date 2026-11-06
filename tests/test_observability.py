import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_metrics_and_audit_share_request_id(caplog: pytest.LogCaptureFixture) -> None:
    marker = "private-marker@example.com"
    with caplog.at_level(logging.INFO, logger="enterprise_router.audit"), TestClient(create_app()) as client:
        response = client.post("/v1/execute", json={"prompt": f"Classify ticket for {marker}"})
        metrics = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert metrics.status_code == 200
    assert "router_provider_attempts_total" in metrics.text
    assert "router_routing_decisions_total" in metrics.text
    assert "router_http_requests_total" in metrics.text
    assert 'route="/v1/execute"' in metrics.text
    assert marker not in metrics.text
    events = [json.loads(record.message) for record in caplog.records if record.name == "enterprise_router.audit"]
    assert events[-1]["request_id"] == response.headers["X-Request-ID"]
    assert events[-1]["entry_point"] == "routed_execute"
