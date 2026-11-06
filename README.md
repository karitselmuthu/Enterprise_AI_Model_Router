# Enterprise AI Model Router

Enterprises often send every AI request to the same large model, even when a
smaller, cheaper model could complete the task. This can increase cost, latency,
and data exposure. The goal of this project is a policy-aware router that
classifies requests, selects a model, validates results, and escalates when
needed.

The six-phase implementation provides a runnable API, deterministic routing,
governance checks, optional live providers, evaluation, and a local Docker
stack. Callers can choose a category explicitly, request a route decision, or
execute the selected model. The default configuration uses deterministic mocks,
so no credentials or model downloads are needed for local tests.

## Architecture and model categories

The intended request path is: classify the task and sensitivity, apply routing
policy, select a model, execute it, validate the response, and escalate when
quality or availability requires it. Policy controls selection, and validation
occurs before a result is returned. The current API implements deterministic
task classification, routing policy, provider execution, basic quality checks,
and escalation. The evaluation dataset, runner, local deployment, metrics,
and tracing hooks are included.

| Category | Intended enterprise tasks | Candidate provider or model |
| --- | --- | --- |
| **SLM** — Small Language Model | Classify IT tickets, extract incident metadata, route support requests, and summarize short operational logs. | A small Qwen instruct model or SmolLM2, potentially served locally through Ollama. |
| **LLM** — Large Language Model | Generate technical documentation, answer enterprise knowledge-base questions, and summarize complex incidents. | GPT or Claude through a configured API. |
| **LRM** — Large Reasoning Model | Analyze root causes, assess infrastructure migration dependencies, and produce remediation plans. | A reasoning-capable model with configurable reasoning effort. |
| **VLM** — Vision Language Model | Interpret monitoring dashboards, architecture diagrams, scanned documents, and screenshots. | A Qwen-VL model or multimodal GPT. |

LRM describes a reasoning-oriented use of a language model, not necessarily a
separate model architecture. A VLM request can also require reasoning, so a
production route may involve more than one model stage.

The stack uses Python, FastAPI, Docker, Prometheus, Grafana, and OpenTelemetry.
LiteLLM and Ollama integrations are optional and require model setup.

For AWS and LocalStack infrastructure, see the
[separate Terraform configurations](infrastructure/terraform/README.md).

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

For a local container demonstration, run `docker compose up --build`. The API
is at `http://127.0.0.1:8000/docs`, Prometheus at `http://127.0.0.1:9090`,
and Grafana at `http://127.0.0.1:3000`. The stack binds these ports to
localhost. The [architecture notes](docs/architecture.md) describe the
request path, controls, and known limits.

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

## Local-first model options

Local-first runs all four categories through Ollama on your Mac. These are
**candidate model IDs**, not quality rankings; test them against your own tasks.
The sizes below are approximate Ollama downloads, **not RAM requirements**.
Runtime memory also depends on context length, image input, and how many models
remain loaded. Start with one model at a time when memory is tight.

| Category | Smaller option | Larger options | Use |
| --- | --- | --- | --- |
| SLM | [`qwen2.5:0.5b`](https://ollama.com/library/qwen2.5) (0.4 GB) or [`smollm2:360m`](https://ollama.com/library/smollm2) (0.7 GB) | `qwen3:1.7b` (1.4 GB), `smollm2:1.7b` (1.8 GB) | Ticket classification and short extraction; check accuracy on your labels. |
| LLM | [`qwen3:4b`](https://ollama.com/library/qwen3) (2.5 GB) or [`gemma3:4b`](https://ollama.com/library/gemma3) (3.4 GB) | `qwen3:8b` (5.2 GB), `gemma3:12b` (8.2 GB) | Summaries and documentation; larger choices need more memory. |
| LRM | [`deepseek-r1:1.5b`](https://ollama.com/library/deepseek-r1) (1.1 GB) | `deepseek-r1:7b` (4.7 GB), `deepseek-r1:14b` (9.0 GB), or `qwen3:8b` (5.2 GB) | Try reasoning tasks locally; verify the final answer rather than trusting the model's reasoning text. |
| VLM | [`qwen2.5vl:3b`](https://ollama.com/library/qwen2.5vl) (3.2 GB) or `gemma3:4b` (3.4 GB) | `qwen2.5vl:7b` (6.0 GB), `gemma3:12b` (8.2 GB) | Screenshots and diagrams; use a tag listed as accepting images. |

Three starting profiles are: **compact** (`qwen2.5:0.5b`, `qwen3:4b`,
`deepseek-r1:1.5b`, `qwen2.5vl:3b`); **balanced** (`qwen3:1.7b`, `qwen3:8b`,
`deepseek-r1:7b`, `qwen2.5vl:7b`); and **larger** (`smollm2:1.7b`,
`gemma3:12b`, `deepseek-r1:14b`, `gemma3:12b`). The order in each profile is
SLM, LLM, LRM, VLM. A model can serve multiple categories, but this router
currently configures one model per category. The larger profile is only a
candidate for Macs with ample available memory; download size alone cannot
establish that it will run comfortably.

To use a profile, pull its distinct model tags with `ollama pull <model-id>`.
Copy `configs/models.hybrid.example.yaml` to an ignored private file such as
`.env.local-models.yaml`, set every category's `provider: ollama`, `id` to the
chosen tag, and `base_url: http://127.0.0.1:11434`. Remove cloud-only fields
such as `api_key_env` and token prices. Set
`ROUTER_MODELS_CONFIG=.env.local-models.yaml` before starting FastAPI. Ollama
must be running, and its host must be reachable from the API process. The
current Ollama adapter does not apply `reasoning_effort`; omit that setting
for local models.

Run `.venv/bin/python -m scripts.evaluate` offline to check deterministic
**routing decisions**. It does not score generated answers. For actual local
generation, call `POST /v1/execute` or use the bounded live runner after
starting the API. Review answer quality manually; the live runner records
latency but does not judge correctness.
After the model downloads finish, local Ollama calls do not need a model API
key. Keep the configured Ollama URL local for restricted requests.

## Cloud-first setup

Cloud-first means assigning API-backed models to **all four categories**, including
SLM and VLM. The existing LiteLLM adapter supports this configuration; the
default `configs/models.yaml` remains a credential-free mock setup. Save a
private model configuration as `.env.cloud-models.yaml` (ignored by Git) and
point `ROUTER_MODELS_CONFIG` at it. For
example (replace model IDs and prices with values supported by your account and
contract):

```yaml
models:
  SLM:
    id: provider/small-model-id
    provider: litellm
    api_key_env: CLOUD_API_KEY
    input_usd_per_million_tokens: 1.0
    output_usd_per_million_tokens: 4.0
  LLM:
    id: provider/general-model-id
    provider: litellm
    api_key_env: CLOUD_API_KEY
    input_usd_per_million_tokens: 1.0
    output_usd_per_million_tokens: 4.0
  LRM:
    id: provider/reasoning-model-id
    provider: litellm
    api_key_env: CLOUD_API_KEY
    reasoning_effort: medium
    input_usd_per_million_tokens: 1.0
    output_usd_per_million_tokens: 4.0
  VLM:
    id: provider/vision-model-id
    provider: litellm
    api_key_env: CLOUD_API_KEY
    input_usd_per_million_tokens: 1.0
    output_usd_per_million_tokens: 4.0
```

Install `requirements-providers.txt`, supply the named API key through a secret
manager or environment variable, set
`ROUTER_MODELS_CONFIG=.env.cloud-models.yaml`, and start the API.
Use separate `api_key_env` values when categories use different providers.
Choose a genuinely small API model for SLM, a model that accepts the configured
`reasoning_effort` for LRM, and a model that accepts image input for VLM.
Confirm the provider-specific LiteLLM model IDs and parameters before enabling
traffic. Keep keys and the private configuration out of Git.

The existing routing policy still maps tasks and fallbacks to categories.
Review `configs/routing_policies.yaml` for the desired cloud category choices
and set `max_cloud_estimated_cost_usd` to a suitable **per-request** limit.
Configure realistic token prices and `max_output_tokens` for each model. The
current estimate uses prompt length and maximum output tokens; it does not
enforce a monthly or tenant budget, and image costs may not be represented
accurately. Add provider usage reconciliation, aggregate spend limits, and
rate limits before relying on this for enterprise cost control.

**Privacy boundary:** the current code rejects LiteLLM for `restricted`
requests regardless of `restricted_providers`. Thus an all-cloud configuration
cannot serve restricted requests; it returns a policy denial instead of sending
them to a cloud API. Keep that fail-closed behavior until you have approved
remote data handling. Supporting restricted cloud traffic requires code changes
to the guardrail, a provider and data-residency allowlist, stronger text and
image data classification, tenant access controls, and documented retention
and logging rules. Test these controls and the denial path before enabling that
traffic. The API currently has no authentication, tenant isolation, or global
rate limiting, so deploy it only behind appropriate access controls.

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
provider sample, run the following against a running API. The live runner
never stores prompt or response bodies and leaves factual quality for human
review.

```bash
.venv/bin/python -m scripts.live_validation --max-requests 10
```

## Observability and CI

`GET /metrics` exposes bounded-label request and provider metrics. Each API
response includes `X-Request-ID`, which appears in JSON audit events. The
provisioned Grafana dashboard shows provider outcomes and p95 latency. To
exercise optional OpenTelemetry export locally, set
`OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318` and run
`docker compose --profile tracing up --build`; the collector writes basic
trace summaries to its logs. The GitHub Actions workflow runs lint, tests,
the 130-scenario evaluator, and a Docker build on pushes and pull requests.
