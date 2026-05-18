from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerConfig(_Strict):
    host: str = "0.0.0.0"
    port: int = 8000
    shutdown_timeout_seconds: int = 30


class PCMConfig(_Strict):
    base_url: str
    token_endpoint: str = "/token"
    introspect_endpoint: str = "/introspect"
    mtls_client: bool = True
    client_assertion_algorithm: Literal["ES256", "RS256"] = "ES256"
    verify_hostname: bool = True
    introspect_auth_method: Literal["bearer", "mtls"] = "bearer"
    # RFC 8707 resource indicator. Required by some PCMs on /token. Leave None to omit.
    token_resource: str | None = None


class FHIRServerConfig(_Strict):
    base_url: str
    protocol: Literal["http", "https"] = "https"
    timeout_seconds: int = 30


class IDReplacementConfig(_Strict):
    base_url: str
    endpoint: str = "/api/v1/resolve"
    timeout_seconds: float = 1.0
    retries: int = 3
    retry_backoff_seconds: float = 0.5


class JWTConfig(_Strict):
    algorithm: Literal["ES256", "RS256"] = "ES256"
    # Public URL of this adapter. Used as JWT `iss` claim AND as the OAuth
    # `issuer` advertised by the discovery endpoints. Must match exactly the
    # value the FHIR server (e.g. IRIS) is configured to trust.
    issuer: str = "ds-adapter"
    # JWT `aud` claim. Accepts a string or a list of strings. If null, falls
    # back to fhir_server.base_url. Per RFC 7519, multiple audiences are
    # encoded as a JSON array — useful when the FHIR server (e.g. IRIS)
    # accepts more than one valid audience value (with/without explicit port,
    # public vs. internal URL, etc.).
    # Override with DS_ADAPTER_JWT_AUDIENCE — comma-separated for a list.
    audience: str | list[str] | None = None
    expiry_seconds: int = 300

    @field_validator("audience", mode="before")
    @classmethod
    def _split_csv_audience(cls, value: object) -> object:
        # Allow env-var overrides like "https://a,https://b" to become a list.
        if isinstance(value, str) and "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return value


# SMART on FHIR scopes that the adapter advertises by default. Baskets in
# PCM can grant access to many different FHIR resources, so the adapter
# advertises a wide list. Operators can replace it via `metadata.scopes_supported`
# in YAML if they want a tighter advertisement.
_DEFAULT_FHIR_RESOURCES = (
    "AllergyIntolerance",
    "Appointment",
    "CarePlan",
    "CareTeam",
    "Claim",
    "Composition",
    "Condition",
    "Consent",
    "Coverage",
    "DiagnosticReport",
    "DocumentReference",
    "Encounter",
    "EpisodeOfCare",
    "FamilyMemberHistory",
    "Goal",
    "Immunization",
    "Location",
    "Medication",
    "MedicationAdministration",
    "MedicationDispense",
    "MedicationRequest",
    "MedicationStatement",
    "Observation",
    "Organization",
    "Patient",
    "Practitioner",
    "PractitionerRole",
    "Procedure",
    "Provenance",
    "Questionnaire",
    "QuestionnaireResponse",
    "RelatedPerson",
    "ServiceRequest",
    "Specimen",
)


def _default_scopes_supported() -> list[str]:
    scopes: list[str] = [
        "openid",
        "fhirUser",
        "profile",
        "offline_access",
        "launch",
        "launch/patient",
        "patient/*.rs",
        "patient/*.read",
        "patient/*.search",
        "user/*.rs",
        "user/*.read",
        "system/*.rs",
        "system/*.read",
    ]
    for resource in _DEFAULT_FHIR_RESOURCES:
        scopes.append(f"patient/{resource}.rs")
        scopes.append(f"patient/{resource}.read")
        scopes.append(f"user/{resource}.rs")
    return scopes


class MetadataConfig(_Strict):
    """Fields advertised at /.well-known/openid-configuration,
    /.well-known/oauth-authorization-server and /.well-known/smart-configuration.

    `issuer` and signing alg come from JWTConfig — kept in one place so the
    JWT `iss` claim and the discovery `issuer` URL never drift.
    """
    enabled: bool = True
    # Override for the published JWKS URL. If null, defaults to
    # f"{jwt.issuer}/.well-known/jwks.json".
    jwks_uri: str | None = None
    # Optional pass-throughs for clients that want them. Usually point at PCM.
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    introspection_endpoint: str | None = None
    # SMART on FHIR / OAuth2 capabilities.
    response_types_supported: list[str] = Field(default_factory=lambda: ["code"])
    grant_types_supported: list[str] = Field(
        default_factory=lambda: ["authorization_code", "client_credentials"]
    )
    scopes_supported: list[str] = Field(default_factory=_default_scopes_supported)
    token_endpoint_auth_methods_supported: list[str] = Field(
        default_factory=lambda: ["private_key_jwt"]
    )
    code_challenge_methods_supported: list[str] = Field(default_factory=lambda: ["S256"])
    capabilities: list[str] = Field(
        default_factory=lambda: ["launch-standalone", "client-public"]
    )


class SyslogTargetConfig(_Strict):
    enabled: bool = False
    host: str = "localhost"
    port: int = 514
    protocol: Literal["udp", "tcp"] = "udp"


class FileTargetConfig(_Strict):
    enabled: bool = True
    path: str = "/var/log/adapter/audit.log"
    rotation: Literal["daily", "hourly", "none"] = "daily"
    max_files: int = 30


class KafkaTargetConfig(_Strict):
    enabled: bool = False
    brokers: str = "kafka:9092"
    topic: str = "ds-adapter-audit"


class AuditTargetsConfig(_Strict):
    syslog: SyslogTargetConfig = Field(default_factory=SyslogTargetConfig)
    file: FileTargetConfig = Field(default_factory=FileTargetConfig)
    kafka: KafkaTargetConfig = Field(default_factory=KafkaTargetConfig)


class AuditConfig(_Strict):
    enabled: bool = True
    format: Literal["json", "cef"] = "json"
    include_response: bool = False
    targets: AuditTargetsConfig = Field(default_factory=AuditTargetsConfig)


class LoggingConfig(_Strict):
    level: Literal["debug", "info", "warning", "error"] = "info"
    format: Literal["json", "text"] = "json"


class OTelConfig(_Strict):
    enabled: bool = True
    exporter: Literal["otlp", "none"] = "otlp"
    endpoint: str = "http://otel-collector:4317"
    service_name: str = "ds-adapter"
    sample_rate: float = 1.0


class VerificationConfig(_Strict):
    enabled: bool = True
    forbidden_labels: list[str] = Field(default_factory=list)


class AppConfig(_Strict):
    server: ServerConfig = Field(default_factory=ServerConfig)
    pcm: PCMConfig
    fhir_server: FHIRServerConfig
    id_replacement: IDReplacementConfig
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    otel: OTelConfig = Field(default_factory=OTelConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
