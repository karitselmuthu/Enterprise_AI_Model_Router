"""Run deterministic routing and policy validation against versioned scenarios."""

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

from app.config import load_config
from app.governance.guardrails import estimated_max_cost_usd, model_allowed
from app.router.classifier import RoutingRequest
from app.router.policy_engine import load_policies
from app.router.routing_engine import PolicyDenied, RouteUnavailable, RoutingEngine

DATASET = Path(__file__).resolve().parent.parent / "datasets" / "routing_scenarios.jsonl"


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def load_scenarios(path: Path = DATASET) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def evaluate_scenarios(scenarios: list[dict]) -> dict:
    base_config = load_config()
    policies = load_policies()
    failures: list[dict] = []
    timings: list[float] = []
    policy_violations = 0
    estimated_upper_cost = 0.0
    groups = Counter(scenario["group"] for scenario in scenarios)
    for scenario in scenarios:
        config = base_config.model_copy(deep=True)
        for category in scenario.get("disabled_categories", []):
            config.models[category].enabled = False
        engine = RoutingEngine(config, policies)
        request = RoutingRequest(
            prompt=scenario["prompt"],
            task_type=scenario["task_type"],
            sensitivity=scenario.get("sensitivity", "internal"),
            contains_image=scenario.get("contains_image", False),
        )
        start = time.perf_counter()
        try:
            decision = engine.route(request)
            status = 200
        except PolicyDenied:
            decision = None
            status = 403
        except RouteUnavailable:
            decision = None
            status = 503
        timings.append((time.perf_counter() - start) * 1000)
        actual_category = decision.category.value if decision else None
        actual_sensitivity = decision.sensitivity.value if decision else None
        correct = (
            status == scenario["expected_status"]
            and actual_category == scenario["expected_category"]
            and (decision is None or actual_sensitivity == scenario["expected_sensitivity"])
        )
        if decision:
            model = config.models[decision.category]
            estimated_upper_cost += estimated_max_cost_usd(request.prompt, model)
            if not model_allowed(request.prompt, decision.sensitivity, model, policies):
                policy_violations += 1
            if scenario.get("disabled_categories") and not decision.fallback_used:
                correct = False
        if not correct:
            failures.append({
                "id": scenario["id"], "expected_category": scenario["expected_category"],
                "actual_category": actual_category, "expected_status": scenario["expected_status"],
                "actual_status": status,
            })
    total = len(scenarios)
    return {
        "mode": "deterministic-routing",
        "scenario_count": total,
        "groups": dict(groups),
        "routing_accuracy": round((total - len(failures)) / total, 4) if total else 0,
        "policy_violations": policy_violations,
        "p50_route_latency_ms": round(percentile(timings, 0.50), 3),
        "p95_route_latency_ms": round(percentile(timings, 0.95), 3),
        "estimated_max_cost_usd": round(estimated_upper_cost, 6),
        "token_usage": None,
        "task_quality": None,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate_scenarios(load_scenarios(args.dataset))
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if not report["failures"] and not report["policy_violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
