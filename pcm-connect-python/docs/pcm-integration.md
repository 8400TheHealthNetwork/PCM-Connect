# PCM Integration Guide for Healthcare Organizations

This guide describes how to connect an organization's `pcm-connect` adapter to
PCM, which values must be agreed with PCM, how requests are authenticated, and
how to verify the integration one stage at a time.

It complements the [operational runbook](runbook.md), which contains the full
application configuration reference.

## 1. Integration flow

With the validated `bearer` introspection method, every request to
`/fhir/{path}` follows this sequence:

1. Accept an opaque PCM bearer token from the calling organization.
2. Authenticate the adapter to PCM with mTLS and an OAuth
   `private_key_jwt` client assertion.
3. Acquire a short-lived PCM machine access token from `/token`.
4. Send the organization's opaque token to PCM `/introspect`, authenticated
   with the machine access token.
5. Read the patient, consent, scope, baskets, and organization context returned
   by PCM.
6. Resolve the PCM patient identifier to the organization's local FHIR patient
   identifier.
7. Mint an internal JWT trusted by the organization's FHIR server.
8. Forward the original FHIR request with the internal JWT.

The PCM machine access token and the organization's inbound bearer token are
different tokens and serve different purposes.

PCM can alternatively authorize introspection using mTLS alone. With
`DS_ADAPTER_PCM_INTROSPECT_AUTH_METHOD=mtls`, the adapter skips machine-token
acquisition and does not add an `Authorization` header to `/introspect`. Use
only the method PCM assigned to the organization.

## 2. Values to agree with PCM

Before deployment, the organization and PCM administrator must agree on these
exact values. URLs are compared as strings, so scheme, host, path, port, case,
and trailing slash must match PCM's registration.

| Value | Provided or registered by | Adapter setting |
|---|---|---|
| PCM client ID | MOH | `DS_ADAPTER_CLIENT_ID` — the organization's assigned organization code (`קוד ארגון`) |
| Client-assertion public key | Organization registers it with PCM | Private counterpart in `DS_ADAPTER_PCM_CLIENT_KEY` |
| Client-assertion algorithm | PCM and organization | `DS_ADAPTER_PCM_CLIENT_ASSERTION_ALGORITHM` |
| Accepted client-assertion audience | PCM | `DS_ADAPTER_PCM_CLIENT_ASSERTION_AUDIENCE` |
| PCM API base URL | MOH | `DS_ADAPTER_PCM_BASE_URL` |
| mTLS client certificate identity | Organization registers it with PCM | `DS_ADAPTER_PCM_CLIENT_CERT` and matching key |
| PCM server CA chain | PCM | `DS_ADAPTER_PCM_CA_CERT` |
| Introspection authentication method | PCM | `DS_ADAPTER_PCM_INTROSPECT_AUTH_METHOD` |
| Machine-token scope | PCM, per environment | `DS_ADAPTER_PCM_TOKEN_SCOPE`; see below |

The adapter's production default for the machine-to-machine `/token` request is:

```text
system/*.crus
```

The current MOH test environment instead requires:

```text
consent.read consent.write fhir.read
```

Set the environment-specific value with `DS_ADAPTER_PCM_TOKEN_SCOPE`. This
machine scope is not supplied by the organization making the FHIR request. The
organization/consent scope is returned dynamically by PCM introspection and is
carried into the internal FHIR JWT.

The adapter does **not** send an OAuth `resource` parameter to PCM `/token`.

## 3. Do not confuse the two JWT identities

The adapter creates two different JWTs.

### 3.1 PCM client assertion

This JWT authenticates the adapter to PCM `/token`:

```json
{
  "iss": "<DS_ADAPTER_CLIENT_ID>",
  "sub": "<DS_ADAPTER_CLIENT_ID>",
  "aud": "<DS_ADAPTER_PCM_CLIENT_ASSERTION_AUDIENCE>",
  "iat": 1700000000,
  "exp": 1700000060,
  "jti": "<unique identifier>"
}
```

Both `iss` and `sub` are controlled by `DS_ADAPTER_CLIENT_ID`. They must equal
the exact organization code (`קוד ארגון`) assigned and registered by MOH.

### 3.2 Internal FHIR JWT

After successful introspection and patient-ID resolution, the adapter creates
a separate JWT for the organization's FHIR server:

```json
{
  "iss": "<DS_ADAPTER_JWT_ISSUER>",
  "sub": "<resolved local patient ID>",
  "aud": "<DS_ADAPTER_JWT_AUDIENCE>",
  "scope": "<scope returned by PCM>",
  "consent_id": "<consent returned by PCM>"
}
```

`DS_ADAPTER_JWT_ISSUER` does not affect the PCM client assertion. It identifies
the adapter to the downstream FHIR server and is also advertised by the
adapter's discovery endpoints.

## 4. Tested PCM test-environment configuration

The following endpoint configuration was validated against the Ministry of
Health PCM test environment. Each organization must replace the client ID and
key material with its own PCM registration.

```text
DS_ADAPTER_PCM_BASE_URL=https://pcm2mtest.health.gov.il/api/fhir-service/r4
DS_ADAPTER_PCM_CLIENT_ASSERTION_AUDIENCE=https://pcm2mtest.health.gov.il/api/fhir-service/r4/token
DS_ADAPTER_PCM_CLIENT_ASSERTION_ALGORITHM=RS256
DS_ADAPTER_PCM_INTROSPECT_AUTH_METHOD=bearer
DS_ADAPTER_PCM_MTLS_CLIENT=true
DS_ADAPTER_PCM_TOKEN_SCOPE="consent.read consent.write fhir.read"
DS_ADAPTER_CLIENT_ID=<organization code assigned by MOH>
```

The adapter appends its built-in `/token` and `/introspect` endpoint defaults
to this base URL. Organizations therefore do not need to set
`DS_ADAPTER_PCM_TOKEN_ENDPOINT` or `DS_ADAPTER_PCM_INTROSPECT_ENDPOINT` for the
MOH test environment.

Do not use the adapter's public URL as the client ID. The client ID is the
organization code assigned by MOH.

Keep `DS_ADAPTER_PCM_VERIFY_HOSTNAME=true` in production. If a non-production
PCM test endpoint intentionally presents a certificate whose SAN does not match
the endpoint hostname, prefer a corrected endpoint or a TLS proxy that verifies
the expected server identity. Set hostname verification to `false` only for an
isolated test environment after explicit risk acceptance; CA-chain validation
alone does not authenticate the requested hostname.

### Required credential material

Store private keys and authorization values using the organization's approved
secret mechanism, never in Git or a plain-text configuration file. Client and
CA certificates are public material, but their integrity and distribution must
still be controlled as trusted configuration.

| Variable | Content |
|---|---|
| `DS_ADAPTER_PCM_CLIENT_KEY` | PEM private key used to sign the client assertion and as the matching mTLS private key |
| `DS_ADAPTER_PCM_CLIENT_CERT` | PEM mTLS client certificate registered with PCM |
| `DS_ADAPTER_PCM_CA_CERT` | PEM CA certificate used to verify PCM |
| `DS_ADAPTER_JWT_SIGNING_KEY` | Separate PEM private key used to sign internal FHIR JWTs |
| `DS_ADAPTER_ID_REPLACEMENT_AUTH` | Optional authorization header value for the local ID resolver |

## 5. PCM request shapes

### 5.1 Machine token request

```http
POST /api/fhir-service/r4/token HTTP/1.1
Host: pcm2mtest.health.gov.il
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&
client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer&
client_assertion=<signed-JWT>&
scope=consent.read+consent.write+fhir.read
```

The signed JWT contains the claims shown in section 3.1. The request is sent
over mTLS. The adapter caches a successful PCM machine token until shortly
before its `expires_in` time. The body shown above reflects Python
`application/x-www-form-urlencoded` encoding, where spaces are encoded as `+`.

### 5.2 Organization-token introspection

With `DS_ADAPTER_PCM_INTROSPECT_AUTH_METHOD=bearer`:

```http
POST /api/fhir-service/r4/introspect HTTP/1.1
Host: pcm2mtest.health.gov.il
Authorization: Bearer <PCM machine access token>
Content-Type: application/x-www-form-urlencoded

token=<opaque token received from the calling organization>
```

A usable response must contain `active: true` and a patient identifier. The
adapter also consumes these optional fields when PCM returns them:

```json
{
  "active": true,
  "patient": "<PCM patient identifier>",
  "scope": "<organization/consent scope>",
  "consent_id": "<consent identifier>",
  "baskets": [],
  "access_type": "<access type>",
  "sp_organization_id": "<calling organization>",
  "cnf": {},
  "exp": 0
}
```

## 6. Calling the adapter

An organization sends its opaque PCM token to the adapter, not the PCM machine
token:

```bash
curl --request GET \
  --header "Authorization: Bearer <organization PCM token>" \
  --header "Accept: application/fhir+json" \
  --header "X-Correlation-ID: integration-test-001" \
  "https://<adapter-host>/fhir/Observation?patient=<patient-identifier>"
```

The public gateway may require an additional client certificate. That is a
gateway requirement and is separate from the adapter-to-PCM mTLS connection.

The patient returned by PCM introspection must exist in the organization's ID
replacement service. A valid PCM token can therefore pass authentication but
still return `ID_002 Patient not found` until the local mapping is populated.

## 7. Verification sequence

Test the integration in stages. A later-stage error is useful evidence that
the earlier stages succeeded.

| Result | Meaning | Action |
|---|---|---|
| TLS handshake error | PCM mTLS did not complete | Check client certificate/key, CA chain, hostname verification, and network path |
| `PCM_002` with missing-scope message | PCM rejected the machine token request scope | Confirm `DS_ADAPTER_PCM_TOKEN_SCOPE` matches the target PCM environment |
| `invalid_client`: JWT `iss` not registered | `DS_ADAPTER_CLIENT_ID` does not match PCM registration, or PCM's organization service is unavailable | Confirm the exact registered client ID |
| `invalid_client`: audience invalid | Client-assertion `aud` is not in PCM's configured audience list | Use the exact audience supplied by PCM; in the validated test environment it is the full token URL |
| PCM `/token` returns `200` JSON with a non-empty `access_token` | mTLS, client ID, signature, audience, and machine scope were accepted | Continue to introspection |
| PCM `/token` returns `200` without a JSON access token | A gateway or upstream error was returned with a misleading success status | Use the correlation and gateway request IDs to investigate the protected server logs |
| `AUTH_002`: token inactive | The caller's opaque PCM token is invalid, expired, revoked, or otherwise inactive | Obtain a new active organization token |
| Introspection returns active but `ID_002` | PCM integration succeeded, but no local patient mapping exists | Populate the ID replacement service or test with a mapped patient |
| `FHIR_001` or `FHIR_002` | Authentication and ID mapping passed, but the FHIR server is unreachable or timed out | Check FHIR transport configuration |
| Upstream FHIR response | End-to-end integration succeeded | Validate returned data and audit records |

Always send an `X-Correlation-ID` and search the adapter logs for the same
value. PCM gateway request IDs such as `X-Amzn-RequestId` are also valuable
when escalating a rejected request to the PCM administrator.

## 8. Organization onboarding checklist

- [ ] MOH assigned the organization an organization code (`קוד ארגון`) for
      `DS_ADAPTER_CLIENT_ID`.
- [ ] PCM registered the client-assertion public key and algorithm.
- [ ] PCM registered/trusted the organization's mTLS certificate.
- [ ] PCM supplied the exact accepted client-assertion audience.
- [ ] `DS_ADAPTER_PCM_TOKEN_SCOPE` matches the scope enabled for the target PCM environment (`system/*.crus` in production; `consent.read consent.write fhir.read` in the current MOH test environment).
- [ ] The PCM API base URL was confirmed; the default `/token` and
      `/introspect` paths produce the expected endpoint URLs.
- [ ] All PCM keys and certificates were stored and injected using the
      organization's approved secure secret mechanism.
- [ ] `DS_ADAPTER_CLIENT_ID` is used for PCM assertion `iss` and `sub`.
- [ ] `DS_ADAPTER_JWT_ISSUER` and `DS_ADAPTER_JWT_AUDIENCE` were separately
      agreed with the downstream FHIR server.
- [ ] The FHIR server trusts the adapter's internal JWT public key/JWKS.
- [ ] The local ID replacement service contains a mapping for the test patient.
- [ ] A fresh organization PCM token passed introspection.
- [ ] A correlated FHIR request completed end to end.

## 9. Security notes

- Treat organization bearer tokens, private keys, and access tokens as
  secrets. Do not place them in documentation, shell history, CI logs, or
  tickets.
- Use short-lived test tokens and rotate any token exposed during manual
  troubleshooting.
- Keep the PCM client key separate from the internal FHIR JWT signing key
  unless an approved deployment profile explicitly requires reuse.
- Validate certificate expiration and key/certificate pairing before deployment.
- Preserve generic client-facing errors; use correlation IDs and protected
  server logs for detailed diagnostics.

## References

- [RFC 7523: JWT Profile for OAuth 2.0 Client Authentication](https://www.rfc-editor.org/rfc/rfc7523.html)
- [RFC 7662: OAuth 2.0 Token Introspection](https://www.rfc-editor.org/rfc/rfc7662.html)
- [Operational runbook](runbook.md)
- [API reference](api.md)
