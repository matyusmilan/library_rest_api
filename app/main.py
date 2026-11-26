from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from sqlalchemy import Engine

from app.database import Base, engine
from app.error_handlers import register_error_handlers
from app.routers import books, borrowers


def configure_otel() -> None:
    """Configure OpenTelemetry with console exporters; use OTLP exporters in production."""
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
    Base.metadata.create_all(bind=app.state.engine)
    yield


def create_app(configure_telemetry: bool = True, db_engine: Engine | None = None) -> FastAPI:
    if configure_telemetry:
        configure_otel()

    app = FastAPI(
        title="Library Management System",
        description="A RESTful API for managing a library's books and borrowers.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.engine = db_engine or engine

    app.include_router(books.router)
    app.include_router(borrowers.router)
    register_error_handlers(app)

    FastAPIInstrumentor.instrument_app(app)

    return app
