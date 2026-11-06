# Enterprise AI Model Router

Enterprises often send every AI request to the same large model, even when a
smaller, cheaper model could complete the task. This can increase cost, latency,
and data exposure. The goal of this project is a policy-aware router that
classifies requests, selects a model, validates results, and escalates when
needed.

Phase 1 provides a runnable API foundation. Callers currently choose a category
explicitly, and all four providers are deterministic mocks.

## Architecture and model categories

The intended request path is: classify the task and sensitivity, apply routing
policy, select a model, execute it, validate the response, and escalate when
quality or availability requires it. Policy controls selection, and validation
occurs before a result is returned. The current Phase 1 API implements the
provider contract and mock execution; the later stages are planned work.

| Category | Intended enterprise tasks | Candidate provider or model |
| --- | --- | --- |
| **SLM** — Small Language Model | Classify IT tickets, extract incident metadata, route support requests, and summarize short operational logs. | A small Qwen instruct model or SmolLM2, potentially served locally through Ollama. |
| **LLM** — Large Language Model | Generate technical documentation, answer enterprise knowledge-base questions, and summarize complex incidents. | GPT or Claude through a configured API. |
| **LRM** — Large Reasoning Model | Analyze root causes, assess infrastructure migration dependencies, and produce remediation plans. | A reasoning-capable model with configurable reasoning effort. |
| **VLM** — Vision Language Model | Interpret monitoring dashboards, architecture diagrams, scanned documents, and screenshots. | A Qwen-VL model or multimodal GPT. |

LRM describes a reasoning-oriented use of a language model, not necessarily a
separate model architecture. A VLM request can also require reasoning, so a
production route may involve more than one model stage.

The planned stack is Python, FastAPI, LiteLLM, Ollama, Docker, and
OpenTelemetry. Phase 1 currently uses Python and FastAPI with mock providers.

## Quick start

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the API schema. Example request:

```bash
curl -X POST http://127.0.0.1:8000/v1/infer \
  -H 'Content-Type: application/json' \
  -d '{"category":"SLM","prompt":"Classify a Kubernetes pod restart alert"}'
```

Run tests with `.venv/bin/python -m pytest -q`.

`configs/models.yaml` defines the model ID for each of `SLM`, `LLM`, `LRM`,
and `VLM`. Set `ROUTER_MODELS_CONFIG` to load a different YAML file. In Phase 1,
only `provider: mock` is accepted. The VLM mock accepts text prompts but does
not ingest images. Invalid configuration prevents startup.

The [Phase 1 specification](docs/phase-1-spec.md) defines the current scope.
Later phases add policy-driven routing, live providers, evaluation, governance,
and deployment.
