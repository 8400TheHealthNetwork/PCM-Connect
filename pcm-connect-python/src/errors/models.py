from src.errors.catalog import ERROR_CATALOG, ERROR_SYSTEM


def build_operation_outcome(code: str) -> dict:
    spec = ERROR_CATALOG.get(code) or ERROR_CATALOG["GEN_001"]
    resolved_code = code if code in ERROR_CATALOG else "GEN_001"
    return {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": "error",
                "code": spec["issue_code"],
                "details": {
                    "coding": [
                        {
                            "system": ERROR_SYSTEM,
                            "code": resolved_code,
                            "display": spec["display"],
                        }
                    ]
                },
                "diagnostics": spec["diagnostics"],
            }
        ],
    }
