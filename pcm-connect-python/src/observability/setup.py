from __future__ import annotations

import structlog
from fastapi import FastAPI

from src.config.models import OTelConfig

log = structlog.get_logger()


def init_otel(app: FastAPI, config: OTelConfig) -> None:
    if not config.enabled or config.exporter == "none":
        log.info("otel_disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError as exc:
        log.warning("otel_import_failed", error=str(exc))
        return

    resource = Resource.create({"service.name": config.service_name})
    provider = TracerProvider(resource=resource, sampler=TraceIdRatioBased(config.sample_rate))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=config.endpoint)))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()

    log.info("otel_initialized", endpoint=config.endpoint, sample_rate=config.sample_rate)
