import re
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUEST_LATENCY_SECONDS = Histogram(
    "app_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status_code"],
)
REQUEST_COUNT = Counter(
    "app_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
INFLIGHT_REQUESTS = Gauge("app_inflight_requests", "In-flight HTTP requests")

LLM_LATENCY_SECONDS = Histogram("app_llm_latency_seconds", "LLM call latency in seconds", ["phase"])
TOOL_LATENCY_SECONDS = Histogram("app_tool_latency_seconds", "Tool execution latency in seconds", ["tool_name"])
RETRY_COUNT = Counter("app_retry_total", "Total retry attempts", ["operation", "error_category"])
ERROR_COUNT = Counter("app_error_total", "Total errors", ["stage", "error_category"])
TOOL_CALL_COUNT = Counter("app_tool_calls_total", "Tool call totals", ["tool_name", "status"])
TOKEN_COUNT = Counter("app_llm_tokens_total", "LLM token usage totals", ["model", "token_type"])
LLM_COST_USD = Counter("app_llm_cost_usd_total", "Estimated LLM cost in USD", ["model"])
HITL_QUEUE_DEPTH = Gauge("app_hitl_queue_depth", "Pending human review items")
ESCALATION_COUNT = Counter("app_escalation_total", "Escalation trigger totals", ["trigger_class"])
QUALITY_KPI_COUNT = Counter("app_quality_kpi_total", "Quality KPI totals", ["kpi"])
CHAT_STREAM_DURATION_SECONDS = Histogram(
    "app_chat_stream_duration_seconds",
    "SSE /chat stream duration to completion in seconds",
    ["outcome"],
)
TOOL_CALLS_PER_RUN = Histogram(
    "app_tool_calls_per_run",
    "Tool calls executed in a completed /chat run",
    ["outcome"],
    buckets=(0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, float("inf")),
)

# Defensive fallback when scope["route"] is missing (e.g. unusual ASGI stacks).
_RUNS_UUID_PATH = re.compile(
    r"^/runs/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def normalized_route_path(request: Request) -> str:
    """Route template for metrics labels (low cardinality), not raw URL paths."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    raw = request.url.path
    if _RUNS_UUID_PATH.match(raw):
        return "/runs/{run_id}"
    return raw


async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    method = request.method
    start = time.perf_counter()
    INFLIGHT_REQUESTS.inc()
    try:
        response = await call_next(request)
    finally:
        INFLIGHT_REQUESTS.dec()
    elapsed = time.perf_counter() - start
    # Route matching runs inside call_next; reading path before that yields raw URLs (UUIDs).
    path = normalized_route_path(request)
    code = str(response.status_code)
    # /chat is SSE; middleware latency only captures response acceptance, not stream completion.
    # We track true /chat latency via CHAT_STREAM_DURATION_SECONDS in the route layer.
    if path != "/chat":
        REQUEST_LATENCY_SECONDS.labels(method=method, path=path, status_code=code).observe(elapsed)
    REQUEST_COUNT.labels(method=method, path=path, status_code=code).inc()
    return response


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def observe_llm_usage(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    estimated_cost_usd: float,
) -> None:
    TOKEN_COUNT.labels(model=model, token_type="input").inc(max(0, input_tokens))
    TOKEN_COUNT.labels(model=model, token_type="output").inc(max(0, output_tokens))
    TOKEN_COUNT.labels(model=model, token_type="total").inc(max(0, total_tokens))
    if estimated_cost_usd > 0:
        LLM_COST_USD.labels(model=model).inc(estimated_cost_usd)

