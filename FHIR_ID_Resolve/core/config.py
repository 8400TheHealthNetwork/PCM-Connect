from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class AuthConfig(BaseModel):
    username: str
    password: str


class FhirConfig(BaseModel):
    base_url: str
    timeout_seconds: float = 10.0
    verify_ssl: bool = True
    default_headers: dict[str, str] = Field(default_factory=dict)


class ResolverConfig(BaseModel):
    patient_id_strategy: Literal["resource_id", "identifier"] = "resource_id"
    patient_id_identifier_system: str | None = None


class Settings(BaseModel):
    api: ApiConfig
    auth: AuthConfig
    fhir: FhirConfig
    resolver: ResolverConfig


# ---------------------------------------------------------------------------
# Environment variable prefix for direct config overrides.
# When set, these take precedence over values from the config file.
#
# Supported env vars:
#   FHIR_RESOLVE_API_HOST
#   FHIR_RESOLVE_API_PORT
#   FHIR_RESOLVE_AUTH_USERNAME
#   FHIR_RESOLVE_AUTH_PASSWORD
#   FHIR_RESOLVE_FHIR_BASE_URL
#   FHIR_RESOLVE_FHIR_TIMEOUT_SECONDS
#   FHIR_RESOLVE_FHIR_VERIFY_SSL
#   FHIR_RESOLVE_FHIR_DEFAULT_HEADERS  (JSON object string)
#   FHIR_RESOLVE_PATIENT_ID_STRATEGY
#   FHIR_RESOLVE_PATIENT_ID_IDENTIFIER_SYSTEM
# ---------------------------------------------------------------------------

_ENV_PREFIX = "FHIR_RESOLVE_"


def _build_config_from_env() -> dict[str, Any]:
    """Build a configuration dict purely from environment variables.

    Returns a (possibly partial) nested dict matching the Settings schema.
    Only keys whose corresponding env var is set will be included.
    """
    config: dict[str, Any] = {}

    # --- api ---
    api: dict[str, Any] = {}
    if v := os.environ.get(f"{_ENV_PREFIX}API_HOST"):
        api["host"] = v
    if v := os.environ.get(f"{_ENV_PREFIX}API_PORT"):
        api["port"] = int(v)
    if api:
        config["api"] = api

    # --- auth ---
    auth: dict[str, Any] = {}
    if v := os.environ.get(f"{_ENV_PREFIX}AUTH_USERNAME"):
        auth["username"] = v
    if v := os.environ.get(f"{_ENV_PREFIX}AUTH_PASSWORD"):
        auth["password"] = v
    if auth:
        config["auth"] = auth

    # --- fhir ---
    fhir: dict[str, Any] = {}
    if v := os.environ.get(f"{_ENV_PREFIX}FHIR_BASE_URL"):
        fhir["base_url"] = v
    if v := os.environ.get(f"{_ENV_PREFIX}FHIR_TIMEOUT_SECONDS"):
        fhir["timeout_seconds"] = float(v)
    if v := os.environ.get(f"{_ENV_PREFIX}FHIR_VERIFY_SSL"):
        fhir["verify_ssl"] = v.lower() in ("true", "1", "yes")
    if v := os.environ.get(f"{_ENV_PREFIX}FHIR_DEFAULT_HEADERS"):
        try:
            fhir["default_headers"] = json.loads(v)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"{_ENV_PREFIX}FHIR_DEFAULT_HEADERS must be a valid JSON object"
            )
    if fhir:
        config["fhir"] = fhir

    # --- resolver ---
    resolver: dict[str, Any] = {}
    if v := os.environ.get(f"{_ENV_PREFIX}PATIENT_ID_STRATEGY"):
        resolver["patient_id_strategy"] = v
    if v := os.environ.get(f"{_ENV_PREFIX}PATIENT_ID_IDENTIFIER_SYSTEM"):
        resolver["patient_id_identifier_system"] = v
    if resolver:
        config["resolver"] = resolver

    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base. Override values win."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


ENV_PLACEHOLDER_RE = re.compile(r"\$\{ENV:([A-Za-z_][A-Za-z0-9_]*)\}")


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        matches = ENV_PLACEHOLDER_RE.findall(value)
        if not matches:
            return value

        def _replace(match: re.Match[str]) -> str:
            env_name = match.group(1)
            env_value = os.getenv(env_name)
            if env_value is None:
                raise RuntimeError(f"Environment variable {env_name} is required by configuration")
            return env_value

        return ENV_PLACEHOLDER_RE.sub(_replace, value)

    if isinstance(value, list):
        return [_resolve_env_placeholders(item) for item in value]

    if isinstance(value, dict):
        return {key: _resolve_env_placeholders(item) for key, item in value.items()}

    return value


def _read_config_file() -> dict[str, Any] | None:
    """Read the config file if it exists. Returns None if no file is found."""
    config_path = Path(os.getenv("FHIR_RESOLVE_CONFIG", "config.json"))
    if not config_path.is_file():
        return None

    try:
        raw = config_path.read_text(encoding="utf-8")
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in configuration file {config_path}: {exc}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # 1. Try to load from config file (may be None if file doesn't exist)
    file_config = _read_config_file()
    if file_config is not None:
        file_config = _resolve_env_placeholders(file_config)
    else:
        file_config = {}

    # 2. Build config from environment variables
    env_config = _build_config_from_env()

    # 3. Merge: env vars take precedence over file values
    merged = _deep_merge(file_config, env_config)

    if not merged:
        raise RuntimeError(
            "No configuration found. Provide a config file (FHIR_RESOLVE_CONFIG) "
            "or set FHIR_RESOLVE_* environment variables."
        )

    # Ensure sections with defaults exist so Pydantic can apply them
    merged.setdefault("api", {})
    merged.setdefault("resolver", {})

    try:
        settings = Settings.model_validate(merged)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid configuration payload: {exc}") from exc

    if not settings.auth.username or not settings.auth.password:
        raise RuntimeError("auth.username and auth.password must be configured")

    if settings.resolver.patient_id_strategy == "identifier" and not settings.resolver.patient_id_identifier_system:
        raise RuntimeError(
            "resolver.patient_id_identifier_system is required when patient_id_strategy=identifier"
        )

    return settings
