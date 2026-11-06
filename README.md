# Enterprise AI Model Router

Enterprises often send every AI request to the same large model, even when a
smaller, cheaper model could complete the task. This can increase cost, latency,
and data exposure. The goal of this project is a policy-aware router that
classifies requests, selects a model, validates results, and escalates when
needed.

Phases 1–3 provide a runnable API, deterministic routing, and optional live
providers. Callers can choose a category explicitly, request a route decision,
or execute the selected model. The default configuration uses deterministic
mocks, so no credentials or model downloads are needed for local tests.

## Architecture and model categories

The intended request path is: classify the task and sensitivity, apply routing
policy, select a model, execute it, validate the response, and escalate when
quality or availability requires it. Policy controls selection, and validation
occurs before a result is returned. The current API implements deterministic
task classification, routing policy, and provider execution. Quality checks
and escalation are later stages.

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
OpenTelemetry. LiteLLM and Ollama integrations are optional in Phase 3.

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
policy file. Later phases add evaluation, governance, and deployment.

## Optional live providers

Install `requirements-providers.txt` and copy
`configs/models.hybrid.example.yaml` to a private configuration file. Set
`ROUTER_MODELS_CONFIG` to that file. Pull the configured local model with
Ollama, and set the environment variable named by each cloud entry's
`api_key_env`. Model IDs in the example are placeholders to review against
current provider availability.

`POST /v1/execute` accepts the routing fields and runs the selected provider.
For a vision request, include `image_base64` and `image_mime_type` (`image/png`,
`image/jpeg`, or `image/webp`); images are limited to 5 MB. `POST /v1/infer`
continues to allow an explicit category and accepts the same image fields.
Restricted requests cannot use a LiteLLM cloud provider. Provider failures
return HTTP 502 without exposing the upstream exception. Live provider calls
require your own credentials and were not exercised by the deterministic tests.
