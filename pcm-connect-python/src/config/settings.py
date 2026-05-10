from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from src.config.models import AppConfig
from src.errors import ConfigurationError

ENV_PREFIX = "DS_ADAPTER_"


def load_config(
    config_path: str | Path = "config.yaml",
    env: dict[str, str] | None = None,
) -> AppConfig:
    """Load AppConfig from YAML, apply DS_ADAPTER_* env overrides, validate.

    Raises ConfigurationError (CFG_001) on missing file, malformed YAML,
    or schema validation failure.
    """
    env = env if env is not None else dict(os.environ)
    raw = _load_yaml(config_path)
    overridden = _apply_env_overrides(raw, AppConfig, env, prefix=ENV_PREFIX)
    try:
        return AppConfig.model_validate(overridden)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid configuration: {exc}") from exc


def _load_yaml(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Config root must be a mapping, got {type(data).__name__}")
    return data


def _apply_env_overrides(
    config: dict[str, Any],
    model_cls: type[BaseModel],
    env: dict[str, str],
    prefix: str,
) -> dict[str, Any]:
    """Walk the model schema; for every leaf field, look for an env var
    named PREFIX + UPPER_SNAKE_PATH and override it if present.

    Underscores inside field names are preserved (e.g. fhir_server.base_url
    maps to DS_ADAPTER_FHIR_SERVER_BASE_URL). The walk is schema-driven, so
    there is no parsing ambiguity from underscores in identifiers.
    """
    for field_name, field_info in model_cls.model_fields.items():
        annotation = field_info.annotation
        env_segment = field_name.upper()
        next_prefix = f"{prefix}{env_segment}_"

        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            sub = config.get(field_name)
            if not isinstance(sub, dict):
                sub = {}
            config[field_name] = _apply_env_overrides(sub, annotation, env, next_prefix)
            continue

        env_key = f"{prefix}{env_segment}"
        if env_key in env:
            config[field_name] = env[env_key]

    return config
