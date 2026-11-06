# Enterprise AI Model Router

Enterprises often send every AI request to the same large model, even when a
smaller, cheaper model could complete the task. This can increase cost, latency,
and data exposure. The goal of this project is a policy-aware router that
classifies requests, selects a model, validates results, and escalates when
needed.

Phases 1–5 provide a runnable API, deterministic routing, governance checks,
and optional live providers. Callers can choose a category explicitly, request a route decision,
or execute the selected model. The default configuration uses deterministic
mocks, so no credentials or model downloads are needed for local tests.

## Architecture and model categories

The intended request path is: classify the task and sensitivity, apply routing
policy, select a model, execute it, validate the response, and escalate when
quality or availability requires it. Policy controls selection, and validation
occurs before a result is returned. The current API implements deterministic
task classification, routing policy, provider execution, basic quality checks,
and escalation. The evaluation dataset and runner are included; deployment is
the remaining phase.

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
and `VLM`. Set `ROUTER_MODELS_CONFIG` to load a different YAML file. The
default uses mock providers. The VLM mock accepts image input without analyzing
it. Invalid configuration prevents startup.

The [Phase 1 specification](docs/phase-1-spec.md) defines the foundation.
`configs/routing_policies.yaml` defines task mappings, fallbacks, and providers
allowed for restricted requests. Set `ROUTER_POLICIES_CONFIG` to use another
policy file. Later phases add a larger evaluation suite and deployment.

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

## Governance limits

An email address or US Social Security number in a text prompt upgrades the
request to `restricted`. Restricted text stays on a mock or local Ollama model;
remote Ollama hosts and LiteLLM cloud models are blocked. This regex check is
incomplete: callers must still label sensitive text and image content correctly.
The API has no authentication yet, so do not expose it to untrusted networks.

Cloud model configuration requires operator supplied input and output token
prices. The router estimates a worst-case cost from prompt length and the
configured maximum output tokens, then compares it with
`max_cloud_estimated_cost_usd` in `configs/routing_policies.yaml`. These are
estimates, not billing records; update prices when contracts change. Output
tokens are capped at the model's `max_output_tokens` setting.

Execution checks for empty or abstaining responses and tries a permitted
fallback from the policy file. The checks do not prove factual correctness.
Each provider attempt emits a JSON audit event with routing metadata and token
counts, excluding prompt, image, and response bodies.

## Evaluation

Run `.venv/bin/python -m scripts.evaluate` for the 130-case deterministic
routing suite. The committed [validation notes](docs/validation.md) and
`reports/phase5_mock.json` describe results and limits. For a bounded live
provider sample, run `.venv/bin/python -m scripts.live_validation
--max-requests 10` against a running API. The live runner never stores prompt
or response bodies and leaves factual quality for human review.
