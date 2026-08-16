from __future__ import annotations

from unittest.mock import patch

import httpx
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc import trace_exporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind

from src.config import AppConfig
from src.config.models import OTelConfig
from src.observability.setup import init_otel


def _config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "pcm": {
                "base_url": "http://pcm.test",
                "token_endpoint": "/token",
                "introspect_endpoint": "/introspect",
                "mtls_client": False,
            },
            "fhir_server": {
                "base_url": "http://fhir.test",
                "protocol": "http",
            },
            "id_replacement": {
                "base_url": "http://id.test",
                "endpoint": "/api/v1/resolve",
            },
            "audit": {"enabled": False},
            "otel": {"enabled": False},
        }
    )


def test_create_app_initializes_otel_before_lifespan() -> None:
    # Importing src.main creates the module-level production app, so patch the
    # initializer before import and then verify a separately configured app.
    with patch("src.observability.setup.init_otel") as init_otel:
        from src.main import create_app

        config = _config()
        app = create_app(config)

    init_otel.assert_called_with(app, config.otel)
    assert app.state.config is config


def test_fastapi_request_is_parent_of_instrumented_httpx_call() -> None:
    exporter = InMemorySpanExporter()
    app = FastAPI()

    @app.get("/trace-test")
    async def trace_test() -> dict[str, bool]:
        async with httpx.AsyncClient() as client:
            await client.post("http://downstream.test/step")
        return {"ok": True}

    with patch.object(trace_exporter, "OTLPSpanExporter", return_value=exporter):
        init_otel(
            app,
            OTelConfig(
                enabled=True,
                endpoint="http://collector.test:4317",
                service_name="trace-parenting-test",
            ),
        )

    try:
        with respx.mock(assert_all_called=True) as router:
            router.post("http://downstream.test/step").mock(
                return_value=httpx.Response(200, json={"ok": True})
            )
            response = TestClient(app).get("/trace-test")
        assert response.status_code == 200

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        assert provider.force_flush()
        spans: tuple[ReadableSpan, ...] = exporter.get_finished_spans()
        server_span = next(span for span in spans if span.kind is SpanKind.SERVER)
        client_span = next(span for span in spans if span.kind is SpanKind.CLIENT)

        assert client_span.context is not None
        assert server_span.context is not None
        assert client_span.parent is not None
        assert client_span.context.trace_id == server_span.context.trace_id
        assert client_span.parent.span_id == server_span.context.span_id
    finally:
        HTTPXClientInstrumentor().uninstrument()
        FastAPIInstrumentor.uninstrument_app(app)
