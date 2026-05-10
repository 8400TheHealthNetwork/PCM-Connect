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


def _read_config_file() -> dict[str, Any]:
    config_path = Path(os.getenv("FHIR_RESOLVE_CONFIG", "config.json"))
    if not config_path.is_file():
        raise RuntimeError(
            f"Configuration file not found: {config_path}. Set FHIR_RESOLVE_CONFIG or create config.json"
        )

    try:
        raw = config_path.read_text(encoding="utf-8")
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in configuration file {config_path}: {exc}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_data = _resolve_env_placeholders(_read_config_file())
    try:
        settings = Settings.model_validate(config_data)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid configuration payload: {exc}") from exc

    if not settings.auth.username or not settings.auth.password:
        raise RuntimeError("auth.username and auth.password must be configured")

    if settings.resolver.patient_id_strategy == "identifier" and not settings.resolver.patient_id_identifier_system:
        raise RuntimeError(
            "resolver.patient_id_identifier_system is required when patient_id_strategy=identifier"
        )

    return settings
