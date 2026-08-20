from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from src.audit.formatters.cef_fmt import format_cef
from src.audit.formatters.ecs_fmt import format_ecs
from src.audit.formatters.json_fmt import format_json
from src.audit.targets.base import AuditTarget
from src.audit.targets.file import FileTarget
from src.audit.targets.kafka import KafkaTarget
from src.audit.targets.stdout import StdoutTarget
from src.audit.targets.syslog import SyslogTarget
from src.config.models import AuditConfig
from src.observability.client_certificate import ClientCertificateMetadata

log = structlog.get_logger()


@dataclass
class AuditRecord:
    timestamp: str
    correlation_id: str
    source_ip: str
    method: str
    path: str
    fhir_scope: str | None
    patient_id: str | None
    sp_organization_id: str | None
    consent_id: str | None
    response_status: int | None
    response_time_ms: float | None
    service_name: str = "ds-adapter"
    trace_id: str | None = None
    transaction_id: str | None = None
    event_outcome: str = "success"
    client_certificate: ClientCertificateMetadata | None = None
    error: str | None = None
    severity: str = "info"
    extras: dict[str, Any] = field(default_factory=dict)


def _mask_patient_id(patient_id: str | None) -> str | None:
    if not patient_id:
        return patient_id
    if len(patient_id) <= 4:
        return "*" * len(patient_id)
    return "*" * (len(patient_id) - 4) + patient_id[-4:]


class AuditService:
    def __init__(self, *, targets: list[AuditTarget], formatter: str, enabled: bool) -> None:
        self._targets = targets
        self._formatter = formatter
        self._enabled = enabled

    @classmethod
    def from_config(cls, config: AuditConfig) -> "AuditService":
        targets: list[AuditTarget] = []
        if config.enabled:
            if config.targets.stdout.enabled:
                targets.append(StdoutTarget())
            if config.targets.file.enabled:
                targets.append(FileTarget(config.targets.file))
            if config.targets.syslog.enabled:
                targets.append(SyslogTarget(config.targets.syslog))
            if config.targets.kafka.enabled:
                targets.append(KafkaTarget(config.targets.kafka))
        return cls(targets=targets, formatter=config.format, enabled=config.enabled)

    async def start(self) -> None:
        for t in self._targets:
            try:
                await t.start()
            except Exception as exc:  # noqa: BLE001
                log.warning("audit_target_start_failed", target=type(t).__name__, error=str(exc))

    async def aclose(self) -> None:
        for t in self._targets:
            try:
                await t.aclose()
            except Exception as exc:  # noqa: BLE001
                log.warning("audit_target_close_failed", target=type(t).__name__, error=str(exc))

    async def record(self, rec: AuditRecord) -> None:
        if not self._enabled or not self._targets:
            return
        rec.patient_id = _mask_patient_id(rec.patient_id)
        if self._formatter == "cef":
            payload = format_cef(rec)
        elif self._formatter == "ecs":
            payload = format_ecs(rec)
        else:
            payload = format_json(rec)
        for t in self._targets:
            try:
                await t.send(payload)
            except Exception as exc:  # noqa: BLE001
                log.warning("audit_target_send_failed", target=type(t).__name__, error=str(exc))
