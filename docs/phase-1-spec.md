# Phase 1: project foundation

## Objective

Create a runnable API foundation for an enterprise model router. This phase proves
configuration loading, a common provider contract, four mock model categories,
and HTTP health and inference behavior. It does not make routing decisions or call
live models.

## Contract

- `GET /health/live` returns process liveness.
- `GET /health/ready` confirms validated model configuration was loaded.
- `GET /v1/models` lists configured category, model ID, and provider.
- `POST /v1/infer` accepts a nonempty prompt and an explicit category (`SLM`,
  `LLM`, `LRM`, `VLM`); it returns the configured model ID and a deterministic
  mock response. Invalid input returns HTTP 422.
- Configuration errors fail startup with a readable exception.

## Stack and commands

Python 3.11+, FastAPI, Pydantic 2, PyYAML, pytest, HTTPX.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
.venv/bin/python -m pytest -q
```

## Structure and style

`app/api` owns HTTP schemas and routes; `app/models` owns category and provider
contracts; `app/config.py` validates configuration. `configs/models.yaml` selects
the mock model for each category. `tests/` verifies behavior. Python modules use
type hints and explicit names; configuration and request schemas forbid unknown
fields.

## Testing and boundaries

Integration tests cover all endpoints, all four categories, invalid requests,
and configuration failure. Always validate configuration before serving requests.
Do not commit secrets or log prompt bodies. Live provider calls, privacy controls,
automatic routing, and evaluation datasets belong to later phases.

## Success criteria

The API starts from a clean install; health endpoints respond; four mock categories
can be invoked; invalid configuration prevents startup; tests pass.
