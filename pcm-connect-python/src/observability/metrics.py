from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter(
    "ds_adapter_requests_total",
    "Total HTTP requests handled by the DS Adapter.",
    labelnames=("method", "status", "path"),
)

REQUEST_DURATION = Histogram(
    "ds_adapter_request_duration_seconds",
    "End-to-end HTTP request duration.",
    labelnames=("method", "path"),
)

PCM_INTROSPECT_DURATION = Histogram(
    "ds_adapter_pcm_introspection_duration_seconds",
    "PCM introspection latency.",
)

ID_REPLACEMENT_DURATION = Histogram(
    "ds_adapter_id_replacement_duration_seconds",
    "ID resolution latency.",
)

FHIR_FORWARD_DURATION = Histogram(
    "ds_adapter_fhir_forward_duration_seconds",
    "FHIR upstream forward latency.",
)

ERRORS_TOTAL = Counter(
    "ds_adapter_errors_total",
    "Total error responses by error code.",
    labelnames=("error_code",),
)

TOKEN_CACHE_HITS = Counter(
    "ds_adapter_token_cache_hits_total",
    "PCM access-token cache hits.",
)

TOKEN_CACHE_MISSES = Counter(
    "ds_adapter_token_cache_misses_total",
    "PCM access-token cache misses (fresh fetch).",
)
