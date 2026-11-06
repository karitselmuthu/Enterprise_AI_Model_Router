"""Opt-in deployment checks against an already running LocalStack stack."""

import json
import os
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ENDPOINT = os.getenv("LOCALSTACK_LIVE_ENDPOINT")
BASE_URL = os.getenv("LOCALSTACK_LIVE_URL")

if not ENDPOINT or not BASE_URL:
    pytest.skip("Set LOCALSTACK_LIVE_ENDPOINT and LOCALSTACK_LIVE_URL for live checks", allow_module_level=True)

if not ENDPOINT.startswith(("http://localhost:", "http://127.0.0.1:")):
    raise ValueError("Live AWS CLI endpoint must be a local emulator")


def api(path: str, payload: dict | None = None) -> tuple[int, str]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{BASE_URL.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


def aws(*args: str) -> dict:
    result = subprocess.run(
        ["aws", "--endpoint-url", ENDPOINT, *args, "--output", "json"],
        env={**os.environ, "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "us-east-1"},
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    return json.loads(result.stdout)


def test_deployed_router_and_metrics() -> None:
    status, body = api("/health/ready")
    assert status == 200 and json.loads(body) == {"status": "ready"}

    status, body = api("/v1/execute", {"prompt": "Classify a test incident"})
    assert status == 200 and json.loads(body)["quality"]["accepted"]

    status, body = api("/metrics")
    assert status == 200
    assert "router_routing_decisions_total" in body
    assert "router_provider_attempts_total" in body


def test_deployment_resources() -> None:
    service = aws("ecs", "describe-services", "--cluster", "enterprise-ai-router-local", "--services", "enterprise-ai-router-local")["services"][0]
    assert service["runningCount"] == service["desiredCount"] == 1
    assert aws("logs", "describe-log-streams", "--log-group-name", "/ecs/enterprise-ai-router-local")["logStreams"]
    repositories = aws("ecr", "describe-repositories", "--repository-names", "enterprise-ai-router")["repositories"]
    assert repositories[0]["repositoryName"] == "enterprise-ai-router"
    secret = aws("secretsmanager", "get-secret-value", "--secret-id", "enterprise-ai-router/local/provider-config")
    assert json.loads(secret["SecretString"])["OPENAI_API_KEY"] == "localstack-test-only"


def test_failure_scenarios_reject_invalid_requests() -> None:
    status, _ = api("/v1/execute", {"prompt": " "})
    assert status == 422
    status, _ = api("/v1/execute", {"prompt": "Inspect image", "contains_image": True})
    assert status == 422
