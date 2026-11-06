from collections import Counter

from scripts.evaluate import evaluate_scenarios, load_scenarios


def test_dataset_has_target_distribution_and_unique_ids() -> None:
    scenarios = load_scenarios()
    counts = Counter(scenario["group"] for scenario in scenarios)
    assert counts == {
        "slm": 30, "llm": 25, "lrm": 25, "vlm": 20,
        "privacy": 10, "fallback": 10, "adversarial": 10,
    }
    assert len({scenario["id"] for scenario in scenarios}) == 130
    assert len({scenario["prompt"] for scenario in scenarios}) == 130


def test_all_deterministic_scenarios_pass() -> None:
    report = evaluate_scenarios(load_scenarios())
    assert report["scenario_count"] == 130
    assert report["routing_accuracy"] == 1.0
    assert report["policy_violations"] == 0
    assert report["failures"] == []
    assert report["task_quality"] is None
