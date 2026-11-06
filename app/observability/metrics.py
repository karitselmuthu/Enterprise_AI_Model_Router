from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "router_http_requests_total", "HTTP requests by route and status class",
    ["method", "route", "status_class"],
)
HTTP_DURATION = Histogram(
    "router_http_duration_seconds", "HTTP request duration by route",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
PROVIDER_ATTEMPTS = Counter(
    "router_provider_attempts_total", "Provider attempt outcomes",
    ["category", "provider", "outcome"],
)
PROVIDER_DURATION = Histogram(
    "router_provider_duration_seconds", "Provider attempt duration",
    ["category", "provider"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)


def observe_provider(category: str, provider: str, outcome: str, duration_seconds: float) -> None:
    PROVIDER_ATTEMPTS.labels(category, provider, outcome).inc()
    PROVIDER_DURATION.labels(category, provider).observe(duration_seconds)
