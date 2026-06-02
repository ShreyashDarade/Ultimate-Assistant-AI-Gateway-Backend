"""Telemetry — OpenTelemetry tracing + Prometheus metrics.

Production: exports traces to an OTLP endpoint (Jaeger, Tempo, etc.).
Development: exports traces to the console.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanExporter, ConsoleSpanExporter
from prometheus_client import Counter, Gauge, Histogram

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

ESTIMATED_COST = Counter(
    "estimated_cost_usd_total",
    "Estimated API cost in USD",
    ["provider", "model"],
)

CACHE_OPERATIONS = Counter(
    "cache_operations_total",
    "Cache hits and misses",
    ["operation"],  # hit / miss
)

ACTIVE_WEBSOCKETS = Gauge(
    "active_websocket_connections",
    "Number of active WebSocket connections",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "circuit_breaker_open",
    "Whether the circuit breaker is open (1) or closed (0) for a provider",
    ["provider"],
)


# ── OpenTelemetry tracing ────────────────────────────

def setup_telemetry() -> None:
    provider = TracerProvider()

    if settings.OTEL_EXPORTER_ENDPOINT:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            otlp_exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_ENDPOINT)
            provider.add_span_processor(BatchSpanExporter(otlp_exporter))
        except ImportError:
            # OTLP exporter not installed — fall back to console.
            provider.add_span_processor(BatchSpanExporter(ConsoleSpanExporter()))
    elif settings.DEBUG:
        provider.add_span_processor(BatchSpanExporter(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)
