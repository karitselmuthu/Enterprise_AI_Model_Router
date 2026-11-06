# Phase 5 validation

The deterministic dataset contains 130 distinct IT operations scenarios:
30 SLM, 25 LLM, 25 LRM, 20 VLM, and 30 privacy, fallback, failure, or
adversarial cases. The last 30 are split into 10 privacy, 10 availability
fallback/failure, and 10 prompt-injection-style routing cases. They are fictional
fixtures, not enterprise production data.

Run the reproducible routing evaluator:

```bash
.venv/bin/python -m scripts.evaluate --output reports/phase5_mock.json
.venv/bin/python -m pytest -q
```

The committed baseline report records 130/130 expected decisions and zero
policy violations under the default mock configuration. It measures only
in-process routing latency. Token usage and task quality are `null` because
mock outputs are not meaningful model answers. Cost is zero because the default
configuration has no paid provider. Treat the latency numbers as local samples,
not service-level objectives.

For an explicitly bounded sample against a running API and configured providers:

```bash
.venv/bin/python -m scripts.live_validation --max-requests 10 --output live-report.json
```

The live script records status, selected category, provider, latency, token
counts where available, and estimated cost from operator configured prices.
It stores neither prompts nor responses. It does not score factual quality;
reviewers must assess answer correctness, usefulness, and safety separately.
Vision samples need real image fixtures and are excluded from this text-only
live runner. No live provider benchmark has been run for the committed report.

The current suite simulates disabled-model failures and validates fallback
behavior. Separate deployment testing should exercise connection failures,
provider timeouts, invalid credentials, and actual cost reconciliation.
