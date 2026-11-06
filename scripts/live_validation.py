"""Sample live API execution; stores metadata only and leaves quality for review."""

import argparse
import json
import time
from pathlib import Path

import httpx

from app.config import load_config
from scripts.evaluate import load_scenarios, percentile


def run_live(base_url: str, max_requests: int, groups: set[str]) -> dict:
    config = load_config()
    scenarios = [
        scenario for scenario in load_scenarios()
        if scenario["group"] in groups and scenario["expected_status"] == 200
        and not scenario.get("contains_image") and not scenario.get("disabled_categories")
    ][:max_requests]
    samples: list[dict] = []
    with httpx.Client(base_url=base_url, timeout=90.0) as client:
        for scenario in scenarios:
            payload = {
                "prompt": scenario["prompt"],
                "task_type": scenario["task_type"],
                "sensitivity": scenario.get("sensitivity", "internal"),
            }
            start = time.perf_counter()
            try:
                response = client.post("/v1/execute", json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000
                body = response.json()
                if response.status_code == 200:
                    decision = body["decision"]
                    result = body["result"]
                    model = config.models[decision["category"]]
                    prompt_tokens = result.get("prompt_tokens")
                    completion_tokens = result.get("completion_tokens")
                    cost = None
                    if prompt_tokens is not None and completion_tokens is not None:
                        cost = (
                            prompt_tokens * (model.input_usd_per_million_tokens or 0)
                            + completion_tokens * (model.output_usd_per_million_tokens or 0)
                        ) / 1_000_000
                    samples.append({
                        "id": scenario["id"], "status": 200, "category": decision["category"],
                        "provider": decision["provider"], "latency_ms": round(elapsed_ms, 2),
                        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                        "estimated_cost_usd": cost, "quality_review_required": True,
                    })
                else:
                    samples.append({"id": scenario["id"], "status": response.status_code, "latency_ms": round(elapsed_ms, 2)})
            except httpx.HTTPError:
                samples.append({"id": scenario["id"], "status": "transport_error"})
    latencies = [sample["latency_ms"] for sample in samples if "latency_ms" in sample]
    known_costs = [sample["estimated_cost_usd"] for sample in samples if sample.get("estimated_cost_usd") is not None]
    return {
        "mode": "live-provider-sample", "request_count": len(samples),
        "p50_latency_ms": round(percentile(latencies, 0.5), 2),
        "p95_latency_ms": round(percentile(latencies, 0.95), 2),
        "estimated_cost_usd": round(sum(known_costs), 6),
        "cost_samples": len(known_costs), "task_quality": None,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--groups", default="slm,llm,lrm")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.max_requests < 1 or args.max_requests > 130:
        parser.error("--max-requests must be between 1 and 130")
    report = run_live(args.api_url, args.max_requests, set(args.groups.split(",")))
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
