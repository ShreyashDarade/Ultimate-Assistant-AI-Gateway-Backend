from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanExporter, ConsoleSpanExporter
from prometheus_client import Counter, Histogram

from app.core.config import settings

# ── Prometheus metrics ───────────────────────────────

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
)

PROVIDER_REQUEST_COUNT = Counter(
    "provider_requests_total",
    "Total provider API calls",
    ["provider", "model", "modality", "status"],
)

PROVIDER_LATENCY = Histogram(
    "provider_request_duration_seconds",
    "Provider API call latency",
    ["provider", "model"],
)

TOKENS_USED = Counter(
    "tokens_used_total",
    "Total tokens consumed",
    ["provider", "model", "direction"],  # direction: input/output
)


# ── OpenTelemetry tracing ────────────────────────────

def setup_telemetry() -> None:
    provider = TracerProvider()
    if settings.DEBUG:
        provider.add_span_processor(BatchSpanExporter(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
