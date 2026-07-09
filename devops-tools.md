# DevOps Tools Summary

## Configuration
- **Layout**: One repo, two services (FHIR_ID_Resolve, pcm-connect-python)
- **Language**: Python (FastAPI, both services)
- **Architecture**: ARM (arm64)
- **Port**: 8000 (both services)
- **CMD**:
  - fhir-id-resolve: `python -m uvicorn app:app --host 0.0.0.0 --port 8000`
  - pcm-connect-python: `uvicorn src.main:app --host 0.0.0.0 --port 8000`
- **Namespace**: pcm-connect (shared by both services)
- **Environment Secrets**: Yes — `fhir-id-resolve-env-secret`, `pcm-connect-python-env-secret`
- **VirtualService**: Public with mTLS (`istio-ingress/mtls-public-gateway`)
  - Hosts: `fhir-id-resolve.{PUBLIC_DOMAIN}`, `pcm-connect-python.{PUBLIC_DOMAIN}`
  - Test domain: `dev.idgmc.org` | Prod domain: `idgmc.org`

## Files Generated
- [x] FHIR_ID_Resolve/Dockerfile (overwritten)
- [x] pcm-connect-python/Dockerfile (overwritten)
- [x] FHIR_ID_Resolve/deployment.yaml
- [x] pcm-connect-python/deployment.yaml
- [x] .gitlab-ci.yml (repo root, per-service build/deploy/logs jobs)

## Notes
- Dockerfiles hardened: Alpine base, non-root `appuser`, tini for signal handling.
- pcm-connect-python uses a multi-stage build (build-base/libffi-dev/openssl-dev in builder for cryptography/aiokafka).
- VirtualService hosts use `${APP}.${PUBLIC_DOMAIN}` (not namespace) since both services share the `pcm-connect` namespace.
- pcm-connect-python requires DS_ADAPTER_* secrets — populate `pcm-connect-python-env-secret` before deploying (see its CLAUDE.md for the full list).
- FHIR_ID_Resolve config defaults to `config.json`; override with `FHIR_RESOLVE_CONFIG` or `FHIR_RESOLVE_*` env vars via the secret.
