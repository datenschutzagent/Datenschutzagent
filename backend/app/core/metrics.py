"""Prometheus metrics for the Datenschutzagent API.

Usage in FastAPI:
    from app.core.metrics import http_request_duration_seconds
    http_request_duration_seconds.labels(method="GET", path="/health", status_code="200").observe(0.01)

Usage in Celery workers:
    Connect Celery signals (see celery_app.py).
    Note: for multi-process deployments (Celery workers + FastAPI) a Prometheus
    Pushgateway is required so worker metrics are visible from the /metrics endpoint.
"""
import logging

from prometheus_client import Histogram, Gauge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTTP metrics
# ---------------------------------------------------------------------------

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path", "status_code"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ---------------------------------------------------------------------------
# LLM metrics
# ---------------------------------------------------------------------------

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "LLM provider call duration in seconds",
    ["provider", "status"],  # status: success | error | circuit_open
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)

# ---------------------------------------------------------------------------
# Celery metrics
# ---------------------------------------------------------------------------

celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration in seconds",
    ["task_name", "status"],  # status: success | failure | timeout
    buckets=[0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# ---------------------------------------------------------------------------
# Database pool metrics (updated on each /metrics scrape)
# ---------------------------------------------------------------------------

db_pool_checkedout = Gauge(
    "db_pool_checkedout_connections",
    "Connections currently checked out from the async SQLAlchemy pool",
)

db_pool_total = Gauge(
    "db_pool_total_connections",
    "Total size of the async SQLAlchemy connection pool",
)


# ---------------------------------------------------------------------------
# OpenTelemetry setup (optional — activated when OTEL_EXPORTER_OTLP_ENDPOINT is set)
# ---------------------------------------------------------------------------

def configure_opentelemetry(service_name: str, otlp_endpoint: str) -> bool:
    """Set up an OTLP-HTTP span exporter and instrument FastAPI + SQLAlchemy.

    Returns True if setup succeeded, False if packages are missing.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME as _SVC
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        resource = Resource(attributes={_SVC: service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        )
        trace.set_tracer_provider(provider)
        logger.info(
            "OpenTelemetry configured",
            extra={"service_name": service_name, "otlp_endpoint": otlp_endpoint},
        )
        return True
    except ImportError:
        logger.warning(
            "opentelemetry-exporter-otlp-proto-http not installed; tracing disabled. "
            "Install with: pip install opentelemetry-exporter-otlp-proto-http"
        )
        return False


def instrument_fastapi(app) -> None:
    """Auto-instrument a FastAPI app with OpenTelemetry spans (no-op if not installed)."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OpenTelemetry instrumentation enabled")
    except ImportError:
        pass


def instrument_sqlalchemy(engine) -> None:
    """Auto-instrument a SQLAlchemy engine with OpenTelemetry spans (no-op if not installed)."""
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy OpenTelemetry instrumentation enabled")
    except ImportError:
        pass
