from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import router
from src.auth.pcm_client import PCMClient
from src.config import load_config
from src.errors.handlers import register_exception_handlers
from src.fhir.client import FHIRClient
from src.identity.id_replacement import IDReplacementClient
from src.middleware.audit_middleware import AuditMiddleware
from src.middleware.correlation import CorrelationMiddleware
from src.middleware.timing import TimingMiddleware


CONFIG_YAML = dedent(
    """
    pcm:
      base_url: "http://pcm.test"
      token_endpoint: "/token"
      introspect_endpoint: "/introspect"
      mtls_client: false

    fhir_server:
      base_url: "http://fhir.test"
      protocol: "http"
      timeout_seconds: 5

    id_replacement:
      base_url: "http://id.test"
      endpoint: "/api/v1/resolve"
      timeout_seconds: 1.0
      retries: 2
      retry_backoff_seconds: 0.0

    audit:
      enabled: false
      targets:
        file:
          enabled: false
        syslog:
          enabled: false
        kafka:
          enabled: false

    otel:
      enabled: false

    verification:
      enabled: true
      forbidden_labels:
        - "http://fhir.health.gov.il/cs/il-core-main-security-label|V"
    """
).strip()


@pytest.fixture
def app(es256_keypair, tmp_path: Path, monkeypatch) -> FastAPI:
    private_pem, _ = es256_keypair
    monkeypatch.setenv("DS_ADAPTER_JWT_SIGNING_KEY", private_pem)
    monkeypatch.setenv("DS_ADAPTER_PCM_CLIENT_KEY", private_pem)

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(CONFIG_YAML, encoding="utf-8")
    config = load_config(cfg_path)

    app = FastAPI()
    app.add_middleware(AuditMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(CorrelationMiddleware)
    register_exception_handlers(app)
    app.include_router(router)

    pcm_http = httpx.AsyncClient()
    id_http = httpx.AsyncClient()
    fhir_http = httpx.AsyncClient()

    app.state.config = config
    app.state.pcm_client = PCMClient(
        http=pcm_http,
        base_url=config.pcm.base_url,
        token_endpoint=config.pcm.token_endpoint,
        introspect_endpoint=config.pcm.introspect_endpoint,
        client_id="adapter-test",
        client_signing_key=private_pem,
    )
    app.state.id_replacement_client = IDReplacementClient(http=id_http, config=config.id_replacement)
    app.state.fhir_client = FHIRClient(http=fhir_http, config=config.fhir_server)

    from src.fhir.verification import ResponseVerifier

    app.state.verifier = ResponseVerifier(config.verification)

    from src.audit.service import AuditService

    app.state.audit_service = AuditService.from_config(config.audit)

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_introspection_response() -> dict:
    return {
        "active": True,
        "patient": "000000018",
        "scope": "patient/Observation.rs",
        "consent_id": "consent-12345",
        "baskets": ["basket-a"],
        "access_type": "treatment",
        "sp_organization_id": "org-hospital-a",
    }


@pytest.fixture
def sample_fhir_bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-1",
                    "status": "final",
                    "meta": {
                        "security": [
                            {
                                "system": "http://fhir.health.gov.il/cs/il-core-main-security-label",
                                "code": "N",
                            }
                        ]
                    },
                }
            }
        ],
    }


@pytest.fixture
def sample_fhir_bundle_with_v_label() -> dict:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-1",
                    "meta": {
                        "security": [
                            {
                                "system": "http://fhir.health.gov.il/cs/il-core-main-security-label",
                                "code": "V",
                            }
                        ]
                    },
                }
            }
        ],
    }
