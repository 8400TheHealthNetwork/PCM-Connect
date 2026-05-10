from typing import TypedDict


class ErrorSpec(TypedDict):
    status: int
    issue_code: str
    display: str
    diagnostics: str


ERROR_CATALOG: dict[str, ErrorSpec] = {
    "AUTH_001": {
        "status": 401,
        "issue_code": "login",
        "display": "Missing or invalid Bearer token",
        "diagnostics": "Authorization header is missing or malformed",
    },
    "AUTH_002": {
        "status": 401,
        "issue_code": "login",
        "display": "Token introspection failed",
        "diagnostics": "The provided access token is not active",
    },
    "AUTH_003": {
        "status": 401,
        "issue_code": "login",
        "display": "Token expired",
        "diagnostics": "The provided access token has expired",
    },
    "AUTH_004": {
        "status": 403,
        "issue_code": "forbidden",
        "display": "Consent not valid",
        "diagnostics": "The consent does not authorize access to the requested resource",
    },
    "AUTH_005": {
        "status": 403,
        "issue_code": "forbidden",
        "display": "Certificate mismatch",
        "diagnostics": "Client certificate does not match token binding",
    },
    "ID_001": {
        "status": 502,
        "issue_code": "exception",
        "display": "ID service unavailable",
        "diagnostics": "Patient identity resolution service is temporarily unavailable",
    },
    "ID_002": {
        "status": 404,
        "issue_code": "not-found",
        "display": "Patient not found",
        "diagnostics": "No local patient record found for the given identifier",
    },
    "FHIR_001": {
        "status": 502,
        "issue_code": "exception",
        "display": "FHIR Server unavailable",
        "diagnostics": "The internal FHIR server is temporarily unavailable",
    },
    "FHIR_002": {
        "status": 504,
        "issue_code": "timeout",
        "display": "FHIR Server timeout",
        "diagnostics": "The internal FHIR server did not respond in time",
    },
    "PCM_001": {
        "status": 502,
        "issue_code": "exception",
        "display": "PCM unreachable",
        "diagnostics": "The consent management system is temporarily unavailable",
    },
    "PCM_002": {
        "status": 401,
        "issue_code": "login",
        "display": "PCM token acquisition failed",
        "diagnostics": "Failed to authenticate with the consent management system",
    },
    "VRF_001": {
        "status": 400,
        "issue_code": "business-rule",
        "display": "Response verification failed",
        "diagnostics": "The response was rejected by policy verification",
    },
    "CFG_001": {
        "status": 500,
        "issue_code": "exception",
        "display": "Configuration error",
        "diagnostics": "Service configuration is invalid",
    },
    "GEN_001": {
        "status": 500,
        "issue_code": "exception",
        "display": "Internal error",
        "diagnostics": "An unexpected error occurred",
    },
}


ERROR_SYSTEM = "http://ds-adapter/error-codes"
