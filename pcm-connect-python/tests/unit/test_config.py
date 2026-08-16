from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from src.config import load_config
from src.config.models import AppConfig
from src.errors import ConfigurationError


MINIMAL_YAML = dedent(
    """
    pcm:
      base_url: "https://pcm-core:3000"
      token_endpoint: "/token"
      introspect_endpoint: "/introspect"
      mtls_client: true

    fhir_server:
      base_url: "https://fhir-internal:8080"
      protocol: "https"
      timeout_seconds: 30

    id_replacement:
      base_url: "http://id-service:9000"
      endpoint: "/api/v1/resolve"
      timeout_seconds: 1.0
      retries: 3
      retry_backoff_seconds: 0.5
    """
).strip()


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_yaml_returns_appconfig(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, MINIMAL_YAML), env={})

    assert isinstance(cfg, AppConfig)
    assert cfg.pcm.base_url == "https://pcm-core:3000"
    assert cfg.fhir_server.timeout_seconds == 30
    assert cfg.id_replacement.retries == 3
    # Defaults populated when section omitted
    assert cfg.server.port == 8000
    assert cfg.jwt.algorithm == "ES256"
    assert cfg.audit.targets.file.enabled is True
    assert cfg.pcm.token_scope == "system/*.crus"


def test_env_override_top_level(tmp_path: Path) -> None:
    env = {"DS_ADAPTER_PCM_BASE_URL": "https://override:9999"}
    cfg = load_config(_write(tmp_path, MINIMAL_YAML), env=env)

    assert cfg.pcm.base_url == "https://override:9999"


def test_env_override_client_assertion_audience(tmp_path: Path) -> None:
    audience = "https://pcm.example:4501/token"
    env = {"DS_ADAPTER_PCM_CLIENT_ASSERTION_AUDIENCE": audience}
    cfg = load_config(_write(tmp_path, MINIMAL_YAML), env=env)

    assert cfg.pcm.client_assertion_audience == audience


def test_env_override_pcm_token_scope(tmp_path: Path) -> None:
    scope = "consent.read consent.write fhir.read"
    env = {"DS_ADAPTER_PCM_TOKEN_SCOPE": scope}
    cfg = load_config(_write(tmp_path, MINIMAL_YAML), env=env)

    assert cfg.pcm.token_scope == scope


def test_env_override_section_with_underscore(tmp_path: Path) -> None:
    env = {
        "DS_ADAPTER_FHIR_SERVER_BASE_URL": "https://other-fhir:4444",
        "DS_ADAPTER_FHIR_SERVER_TIMEOUT_SECONDS": "5",
    }
    cfg = load_config(_write(tmp_path, MINIMAL_YAML), env=env)

    assert cfg.fhir_server.base_url == "https://other-fhir:4444"
    assert cfg.fhir_server.timeout_seconds == 5


def test_env_override_nested(tmp_path: Path) -> None:
    env = {"DS_ADAPTER_AUDIT_TARGETS_FILE_PATH": "/tmp/audit.log"}
    cfg = load_config(_write(tmp_path, MINIMAL_YAML), env=env)

    assert cfg.audit.targets.file.path == "/tmp/audit.log"


def test_missing_required_field_raises(tmp_path: Path) -> None:
    bad = dedent(
        """
        pcm:
          token_endpoint: "/token"
        """
    ).strip()

    with pytest.raises(ConfigurationError):
        load_config(_write(tmp_path, bad), env={})


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_config(tmp_path / "nope.yaml", env={})


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_config(_write(tmp_path, "pcm: [unterminated"), env={})


def test_unknown_field_rejected(tmp_path: Path) -> None:
    bad = MINIMAL_YAML + "\n\nmystery: 1\n"
    with pytest.raises(ConfigurationError):
        load_config(_write(tmp_path, bad), env={})
