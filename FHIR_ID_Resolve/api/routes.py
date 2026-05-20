from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from core.auth import require_api_user
from core.config import get_settings
from services.resolver import DuplicateActivePatientError, UpstreamUnavailableError, resolve_patient


class IdentifierInput(BaseModel):
    system: str
    value: str


class ResolveRequest(BaseModel):
    identifier: IdentifierInput


class ResolveSuccessResponse(BaseModel):
    patient_id: str
    resource_reference: str


class NotFoundResponse(BaseModel):
    error: str
    message: str


class ConflictResponse(BaseModel):
    error: str
    message: str
    patient_ids: list[str]


class ServiceUnavailableResponse(BaseModel):
    error: str
    message: str


router = APIRouter(prefix="/api/v1", tags=["resolve"], dependencies=[Depends(require_api_user)])


@router.post(
    "/resolve",
    response_model=ResolveSuccessResponse,
    responses={
        404: {"model": NotFoundResponse},
        409: {"model": ConflictResponse},
        503: {"model": ServiceUnavailableResponse},
    },
    summary="Resolve identifier to local patient ID",
)
async def resolve_identifier(body: ResolveRequest) -> ResolveSuccessResponse:
    settings = get_settings()

    try:
        result = await resolve_patient(
            system=body.identifier.system,
            value=body.identifier.value,
            settings=settings,
        )
    except DuplicateActivePatientError as exc:
        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_active_patient",
                "message": "More than one active patient was found for the provided identifier",
                "patient_ids": exc.ids,
            },
        )
    except UpstreamUnavailableError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "error": "service_unavailable",
                "message": f"Unable to reach FHIR server: {exc}",
            },
        )

    if result is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": "patient_not_found",
                "message": "No patient was found for the provided identifier",
            },
        )

    return ResolveSuccessResponse(
        patient_id=result.patient_id,
        resource_reference=result.resource_reference,
    )
