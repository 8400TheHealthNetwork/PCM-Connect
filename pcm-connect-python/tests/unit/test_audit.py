from __future__ import annotations

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from uuid import UUID

import pytest

from src.audit.formatters.cef_fmt import format_cef
from src.audit.formatters.ecs_fmt import format_ecs
from src.audit.formatters.json_fmt import format_json
from src.audit.service import AuditRecord, AuditService, _mask_patient_id
from src.audit.targets.file import FileTarget
from src.config.models import (
    AuditConfig,
    AuditTargetsConfig,
    FileTargetConfig,
    KafkaTargetConfig,
    StdoutTargetConfig,
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
        fhir_resource_type="Observation",
        fhir_interaction="search",
        baskets=("basket-a", "basket-b"),
        access_type="treatment",
        authorization_decision="allowed",
        authorization_stage="authorized",
        processing_stage="completed",
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
        "event_id",
        "audit_schema_version",
        "fhir_resource_type",
        "fhir_interaction",
        "baskets",
        "access_type",
        "authorization_decision",
        "authorization_stage",
        "processing_stage",
    ):
        assert key in payload
    assert UUID(payload["event_id"])
    assert payload["audit_schema_version"] == "1.0.0"


def test_format_ecs_includes_required_fields() -> None:
    rec = _record(patient_id="****0018")
    payload = json.loads(format_ecs(rec))
    assert payload["@timestamp"] == rec.timestamp
    assert payload["service"]["name"] == "ds-adapter"
    assert payload["log"]["logger"] == "audit"
    assert UUID(payload["event"]["id"])
    assert payload["event"]["action"] == "fhir_search"
    assert payload["event"]["dataset"] == "pcm-connect.audit"
    assert payload["event"]["outcome"] == "success"
    assert payload["event"]["duration"] == 12_340_000
    assert payload["ecs"]["version"] == "8.0.0"
    assert payload["labels"]["correlation_id"] == "cid-1"
    assert payload["source"]["ip"] == "10.0.0.1"
    assert payload["http"]["request"]["method"] == "GET"
    assert payload["http"]["response"]["status_code"] == 200
    assert payload["url"]["path"] == "/fhir/Observation"
    assert payload["pcm"]["fhir"]["resource_type"] == "Observation"
    assert payload["pcm"]["fhir"]["interaction"] == "search"
    assert payload["pcm"]["audit"]["schema_version"] == "1.0.0"
    assert payload["pcm"]["audit"]["processing_stage"] == "completed"
    assert payload["pcm"]["authorization"] == {
        "decision": "allowed",
        "stage": "authorized",
    }
    assert payload["pcm"]["patient_id"] == "****0018"
    assert payload["pcm"]["consent_id"] == "consent-1"
    assert payload["pcm"]["baskets"] == ["basket-a", "basket-b"]
    assert payload["pcm"]["access_type"] == "treatment"


def test_audit_records_receive_unique_event_ids() -> None:
    first = _record()
    second = _record()

    assert first.event_id != second.event_id
    assert UUID(first.event_id)
    assert UUID(second.event_id)


def test_format_cef_starts_with_header() -> None:
    rec = _record()
    out = format_cef(rec)
    assert out.startswith("CEF:0|ds-adapter|DSAdapter|1.0.0|")
    assert f"externalId={rec.event_id}" in out
    assert "act=fhir_search" in out
    assert "flexString1=allowed" in out
    assert "cat=completed" in out
    assert "cs1Label=correlation_id" in out


async def test_file_target_writes_record(tmp_path: Path) -> None:
    target_path = tmp_path / "audit.log"
    target = FileTarget(FileTargetConfig(enabled=True, path=str(target_path), rotation="daily", max_files=5))
    await target.start()
    await target.send('{"hello": "world"}')
    await target.aclose()
    contents = target_path.read_text()
    assert '"hello": "world"' in contents


async def test_file_target_rotation_none_uses_plain_file_handler(tmp_path: Path) -> None:
    target = FileTarget(
        FileTargetConfig(enabled=True, path=str(tmp_path / "audit.log"), rotation="none")
    )
    await target.start()
    assert isinstance(target._handler, logging.FileHandler)  # type: ignore[attr-defined]
    assert not isinstance(target._handler, TimedRotatingFileHandler)  # type: ignore[attr-defined]
    await target.aclose()


async def test_stdout_target_emits_one_json_message(caplog) -> None:
    config = AuditConfig(
        enabled=True,
        format="ecs",
        targets=AuditTargetsConfig(
            stdout=StdoutTargetConfig(enabled=True),
            file=FileTargetConfig(enabled=False),
        ),
    )
    service = AuditService.from_config(config)
    with caplog.at_level(logging.INFO, logger="audit"):
        await service.record(_record())

    messages = [record.message for record in caplog.records if record.name == "audit"]
    assert len(messages) == 1
    assert json.loads(messages[0])["event"]["action"] == "fhir_search"


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
