# Enterprise AI Model Router

Enterprises often send every AI request to the same large model, even when a
smaller, cheaper model could complete the task. This can increase cost, latency,
and data exposure. The goal of this project is a policy-aware router that
classifies requests, selects a model, validates results, and escalates when
needed.

Phases 1 and 2 provide a runnable API foundation and deterministic routing.
Callers can choose a category explicitly or request a route decision; all four
providers are currently deterministic mocks.

## Architecture and model categories

The intended request path is: classify the task and sensitivity, apply routing
policy, select a model, execute it, validate the response, and escalate when
quality or availability requires it. Policy controls selection, and validation
occurs before a result is returned. The current API implements deterministic
task classification, routing policy, and mock providers. Live execution,
quality checks, and escalation are later stages.

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
OpenTelemetry. The current API uses Python and FastAPI with mock providers.

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

For a policy decision, call `POST /v1/route` with a `prompt`, optional
`task_type`, `sensitivity` (`public`, `internal`, or `restricted`), and
`contains_image`. Classification uses deterministic rules; an explicit image
signal takes precedence. The endpoint returns the selected category, model,
reason, and whether a fallback was used. It does not invoke the provider.

`configs/models.yaml` defines the model ID for each of `SLM`, `LLM`, `LRM`,
and `VLM`. Set `ROUTER_MODELS_CONFIG` to load a different YAML file. In Phase 1,
only `provider: mock` is accepted. The VLM mock accepts text prompts but does
not ingest images. Invalid configuration prevents startup.

The [Phase 1 specification](docs/phase-1-spec.md) defines the foundation.
`configs/routing_policies.yaml` defines task mappings, fallbacks, and providers
allowed for restricted requests. Set `ROUTER_POLICIES_CONFIG` to use another
policy file. Later phases add live providers, evaluation, governance, and
deployment.
