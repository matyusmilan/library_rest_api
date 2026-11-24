from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.database import Base, engine
from app.routers import books, borrowers


def configure_otel() -> None:
    """
    Set up OpenTelemetry tracing and metrics with console exporters.

    In production this would be replaced with an OTLP exporter pointing at
    a collector (e.g. Jaeger, Grafana Tempo, Datadog), but console exporters
    are sufficient to demonstrate that spans and metrics are emitted correctly
    without requiring external infrastructure for local development.
    """
    # Tracing
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=15_000)
    meter_provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create all database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


def create_app(configure_telemetry: bool = True) -> FastAPI:
    if configure_telemetry:
        configure_otel()

    app = FastAPI(
        title="Library Management System",
        description="A RESTful API for managing a library's books and borrowers.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(books.router)
    app.include_router(borrowers.router)

    FastAPIInstrumentor.instrument_app(app)

    return app
