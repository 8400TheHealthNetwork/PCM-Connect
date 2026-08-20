from src.audit.fhir_context import classify_fhir_request


def test_classifies_standard_fhir_interactions() -> None:
    cases = [
        ("GET", "/fhir/Observation", "Observation", "search"),
        ("GET", "/fhir/Patient/123", "Patient", "read"),
        ("POST", "/fhir/Observation", "Observation", "create"),
        ("PUT", "/fhir/Patient/123", "Patient", "update"),
        ("PATCH", "/fhir/Patient/123", "Patient", "patch"),
        ("DELETE", "/fhir/Patient/123", "Patient", "delete"),
    ]

    for method, path, resource_type, interaction in cases:
        context = classify_fhir_request(method, path)
        assert context.resource_type == resource_type
        assert context.interaction == interaction
        assert context.event_action == f"fhir_{interaction}"


def test_operation_and_history_take_precedence_over_method() -> None:
    operation = classify_fhir_request("POST", "/fhir/Patient/123/$everything")
    history = classify_fhir_request("GET", "/fhir/Observation/123/_history/4")

    assert operation.resource_type == "Patient"
    assert operation.interaction == "operation"
    assert operation.audit_path == "/fhir/Patient/***/$everything"
    assert history.resource_type == "Observation"
    assert history.interaction == "history"
    assert history.audit_path == "/fhir/Observation/***/_history/*"


def test_post_search_is_not_classified_as_create() -> None:
    context = classify_fhir_request("POST", "/fhir/Observation/_search")

    assert context.resource_type == "Observation"
    assert context.interaction == "search"
    assert context.audit_path == "/fhir/Observation/_search"


def test_instance_identifiers_retain_only_the_final_four_characters() -> None:
    context = classify_fhir_request(
        "GET", "/fhir/Patient/patient-123456/_history/version-987654"
    )

    assert context.audit_path == "/fhir/Patient/**********3456/_history/**********7654"


def test_unrecognized_path_does_not_claim_a_resource_type() -> None:
    context = classify_fhir_request("GET", "/fhir/metadata")

    assert context.resource_type is None
    assert context.interaction == "access"
    assert context.event_action == "fhir_access"
    assert context.audit_path == "/fhir/metadata"
