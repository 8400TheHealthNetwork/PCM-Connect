from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.audit.formatters.cef_fmt import format_cef
from src.audit.formatters.json_fmt import format_json
from src.audit.service import AuditRecord, AuditService, _mask_patient_id
from src.audit.targets.file import FileTarget
from src.config.models import (
    AuditConfig,
    AuditTargetsConfig,
    FileTargetConfig,
    KafkaTargetConfig,
    SyslogTargetConfig,
)


def _record(**overrides) -> AuditRecord:
    base = dict(
        timestamp="2026-05-10T10:00:00Z",
        correlation_id="cid-1",
        source_ip="10.0.0.1",
        method="GET",
        path="/fhir/Observation",
        fhir_scope="patient/Observation.rs",
        patient_id="000000018",
        sp_organization_id="org-a",
        consent_id="consent-1",
        response_status=200,
        response_time_ms=12.34,
    )
    base.update(overrides)
    return AuditRecord(**base)


def test_mask_patient_id_keeps_last_four() -> None:
    assert _mask_patient_id("000000018") == "*****0018"
    assert _mask_patient_id("ABC") == "***"
    assert _mask_patient_id(None) is None
    assert _mask_patient_id("") == ""


def test_format_json_includes_required_fields() -> None:
    rec = _record(patient_id="****0018")
    payload = json.loads(format_json(rec))
    for key in (
        "timestamp",
        "correlation_id",
        "source_ip",
        "method",
        "path",
        "fhir_scope",
        "patient_id",
        "sp_organization_id",
        "consent_id",
        "response_status",
        "response_time_ms",
    ):
        assert key in payload


def test_format_cef_starts_with_header() -> None:
    rec = _record()
    out = format_cef(rec)
    assert out.startswith("CEF:0|ds-adapter|DSAdapter|")
    assert "cs1Label=correlation_id" in out


async def test_file_target_writes_record(tmp_path: Path) -> None:
    target_path = tmp_path / "audit.log"
    target = FileTarget(FileTargetConfig(enabled=True, path=str(target_path), rotation="daily", max_files=5))
    await target.start()
    await target.send('{"hello": "world"}')
    await target.aclose()
    contents = target_path.read_text()
    assert '"hello": "world"' in contents


async def test_audit_service_masks_and_writes(tmp_path: Path) -> None:
    target_path = tmp_path / "audit.log"
    config = AuditConfig(
        enabled=True,
        format="json",
        include_response=False,
        targets=AuditTargetsConfig(
            file=FileTargetConfig(enabled=True, path=str(target_path), rotation="daily", max_files=5),
            syslog=SyslogTargetConfig(enabled=False),
            kafka=KafkaTargetConfig(enabled=False),
        ),
    )
    service = AuditService.from_config(config)
    await service.start()
    await service.record(_record(patient_id="000000018"))
    await service.aclose()

    line = target_path.read_text().strip()
    payload = json.loads(line)
    assert payload["patient_id"] == "*****0018"
    assert payload["response_status"] == 200


async def test_audit_disabled_writes_nothing(tmp_path: Path) -> None:
    target_path = tmp_path / "audit.log"
    config = AuditConfig(
        enabled=False,
        targets=AuditTargetsConfig(
            file=FileTargetConfig(enabled=True, path=str(target_path), rotation="daily", max_files=5),
        ),
    )
    service = AuditService.from_config(config)
    await service.start()
    await service.record(_record())
    await service.aclose()
    assert not target_path.exists() or target_path.read_text() == ""


async def test_audit_target_failure_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    config = AuditConfig(
        enabled=True,
        targets=AuditTargetsConfig(
            file=FileTargetConfig(enabled=True, path=str(tmp_path / "a.log"), rotation="daily", max_files=5),
        ),
    )
    service = AuditService.from_config(config)
    await service.start()

    # Force every target's send to raise; service must swallow.
    async def _boom(_: str) -> None:
        raise RuntimeError("disk full")

    for target in service._targets:  # type: ignore[attr-defined]
        target.send = _boom  # type: ignore[method-assign]

    await service.record(_record())  # no exception
    await service.aclose()
