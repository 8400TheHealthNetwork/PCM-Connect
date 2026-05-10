from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    algorithm: Literal["ES256"] = "ES256"
    issuer: str = "ds-adapter"
    expiry_seconds: int = 300


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
    audit: AuditConfig = Field(default_factory=AuditConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    otel: OTelConfig = Field(default_factory=OTelConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
