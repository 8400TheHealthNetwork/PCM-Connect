# External Development Provider Guidelines

Version: 2.2 
Last Updated: April 2026

---

## 1. Development Environment

All development and testing must be performed locally by the provider. The required architecture will be agreed upon in advance, and the provider is responsible for running all services locally according to that architecture.

### Local Services

The provider **must** run all required services locally as **Docker containers** during development. This includes databases, authentication services, message brokers, caches, and any other infrastructure component defined in the architecture.

The provider is responsible for maintaining a `docker-compose.yml` (or equivalent) that spins up the full local environment.

Examples of services that may be required (defined per project during the architecture phase):
- PostgreSQL with versioned migration scripts
- Keycloak for authentication
- LiteLLM with Amazon Bedrock integration
- Redis, RabbitMQ, etc.

---

## 2. Source Code Management

### Repository Ownership

- The source code repository **must** be hosted in our organization's GitLab instance.
- The provider will be granted write access during development. Upon handover completion, access will be revoked.
- **The organization is and remains the sole owner of the repository and all code within it.**

### Branching Strategy

The provider **must** follow the branching model specified below:

- `main` — production-ready code only. Direct pushes are **forbidden**.
- `develop` — integration branch. All feature branches are merged here.
- `feature/<ticket-id>-short-description` — one branch per feature or task.
- `fix/<ticket-id>-short-description` — for bug fixes.
- `release/<version>` — release preparation branches (if applicable).

### Commit Conventions

All commits **must** follow the **Conventional Commits** specification (`https://www.conventionalcommits.org`):

```
<type>(scope): short description

Examples:
feat(auth): add PKCE support for Keycloak login
fix(api): handle null response from user service
chore(deps): upgrade node to 22.x
```

Allowed types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`.

### Pull Requests & Code Review

- All changes **must** be submitted via Pull Requests (PRs) targeting `develop`.
- A PR **must** pass all CI checks (tests, linting, security scan) before it can be merged.
- At least **one approval** from a designated reviewer is required before merging.
- PRs must include a description of the change, linked ticket, and testing instructions.

---

## 3. Containerization & Deployment Readiness

The target deployment platform is Amazon EKS. The provider must ensure the application runs correctly as a container.

### Mandatory Requirements

- The application **must** run successfully using:
  ```bash
  docker run --env-file .env <image>
  ```
- All configuration values that change between environments (URLs, credentials, feature flags, etc.) **must** be loaded from environment variables.
- **Do NOT** hardcode configuration values or load `.env` files directly in application code (e.g., no `dotenv` in production code, no `.env` references in `npm run` / `uvicorn` start commands).
- The `.env` file is only used as a reference for required variables and for local Docker testing.

### Environment Variable Documentation

The provider must maintain an `env.example` file listing every required environment variable with:
- Variable name
- Description
- Example value (non-sensitive)
- Whether it is required or optional

### Health Checks & Graceful Shutdown

All backend services **must** implement the following HTTP endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health/live` | Liveness probe — confirms the process is alive |
| `GET /health/ready` | Readiness probe — confirms the service is ready to receive traffic |

Requirements:
- Both endpoints must return HTTP `200` when healthy, and `503` when not.
- Response body must be a JSON object: `{ "status": "ok" }` or `{ "status": "unavailable", "reason": "..." }`.
- The `readiness` endpoint must validate connectivity to dependent services (database, cache, etc.).
- The application **must** handle `SIGTERM` gracefully: stop accepting new requests, finish in-flight requests, then shut down cleanly. Maximum graceful shutdown window: **30 seconds**.

These probes will be configured in the Kubernetes deployment manifests.

---

## 4. Authentication

### Protocol

Authentication **must** use **OpenID Connect (OIDC) Authorization Code Flow with PKCE (Proof Key for Code Exchange) for Public Clients** — no client secret.

- The Keycloak client must be configured as a **public client** (`Access Type: public`).
- PKCE (`S256` challenge method) is mandatory.
- No `client_secret` should be stored or transmitted by the frontend application.

### Token Storage

- Access tokens and refresh tokens **must NOT** be stored in `localStorage` or `sessionStorage`. These are vulnerable to XSS attacks.
- Tokens must be stored either:
  - In **memory only** (JavaScript variable / React state), OR
  - In **`httpOnly`, `Secure`, `SameSite=Strict` cookies** (server-side session pattern).
- The chosen strategy must be documented and approved before implementation begins.

### Token Lifecycle

- The application must implement **silent token refresh** using the refresh token before the access token expires.
- On logout, the provider must call the Keycloak **revocation endpoint** to invalidate the session server-side. Clearing local state alone is insufficient.
- Session timeout behavior must be defined and implemented (idle timeout, absolute timeout).

---

## 5. Logging

All application logs **must** follow the **Elastic Common Schema (ECS)** format (structured JSON).

### Implementation References

| Language | Library / Reference |
|---|---|
| Node.js | [ECS Logging for Node.js](https://www.elastic.co/docs/reference/ecs/logging/nodejs) — use `@elastic/ecs-winston-format` or `@elastic/ecs-pino-format` |
| Python | [ECS Logging for Python](https://www.elastic.co/docs/reference/ecs/logging/python) — use `ecs-logging-python` |

### Requirements

- Logs must be written to `stdout` (not to files inside the container).
- Log level must be configurable via environment variable (e.g., `LOG_LEVEL=info`).
- Include correlation/request IDs in every log entry where applicable (propagate `X-Request-ID` or `X-Correlation-ID` headers).
- **PII and secrets must never appear in logs** — mask or omit fields such as passwords, tokens, email addresses, and ID numbers. This is a security requirement, not a recommendation.

### Log Levels

| Level | When to use |
|---|---|
| `error` | Unhandled exceptions, service failures |
| `warn` | Recoverable issues, retries, deprecated usage |
| `info` | Significant business events, startup/shutdown |
| `debug` | Detailed flow for troubleshooting (disabled in production) |

---

Logging alone is insufficient for operating a service in production. The provider must implement all three pillars of observability.

### Metrics

- All backend services must expose a **`GET /metrics`** endpoint in **Prometheus text format**.
- At minimum, the following metrics must be exposed:
  - HTTP request count (by method, path, status code)
  - HTTP request latency (histogram, p50 / p95 / p99)
  - Active database connection pool size
  - Application-specific business metrics (to be agreed per project)

### Distributed Tracing

- All services must instrument requests using **OpenTelemetry**.
- Trace context must be propagated via standard HTTP headers (`traceparent`, `tracestate`).
- The OTLP exporter endpoint must be configurable via environment variable (`OTEL_EXPORTER_OTLP_ENDPOINT`).

### Reference

- OpenTelemetry Node.js: https://opentelemetry.io/docs/languages/js/
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/

---

## 8. Docker Images

### Base Images

- Use **Alpine-based** images (e.g., `node:22-alpine`, `python:3.12-alpine`) unless a specific dependency requires otherwise. Any exception must be documented and justified.

### Architecture

- All images **must** be built for **ARM64** (`linux/arm64`), unless a specific dependency requires otherwise. Any exception must be documented and justified.
- Use Docker Buildx for multi-platform builds:
  ```bash
  docker buildx build --platform linux/arm64 -t <image> .
  ```
- Before committing to ARM64, the provider must verify that **all third-party dependencies** (native modules, binary tools) have ARM64-compatible releases. Incompatibilities must be reported to our DevOps team before development begins.

### Non-Root User

- Containers **must not run as root**.
- The Dockerfile must create and switch to a dedicated non-root user:
  ```dockerfile
  RUN addgroup -S appgroup && adduser -S appuser -G appgroup
  USER appuser
  ```

### Frontend Build

Frontend applications **must** use a **multi-stage build**:

1. **Build stage** — install dependencies, compile/bundle the application.
2. **Production stage** — copy the build artifacts into an `nginx:alpine` image and serve with Nginx.

Example structure:
```dockerfile
# Stage 1: Build
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
USER appuser
CMD ["nginx", "-g", "daemon off;"]
```

---

## 9. Backend Access — Reverse Proxy

The backend API **must NOT** be accessed directly from the user's browser.

- All backend requests must be **proxied through Nginx** (the same Nginx serving the frontend).
- The Nginx configuration must include a `location` block that proxies API requests to the backend service.
- The backend container should not expose ports to end users — only to the internal network (other containers / Kubernetes services).

### Nginx Proxy Configuration

```nginx
location /api/ {
    proxy_pass http://backend:3000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_connect_timeout 10s;
    proxy_send_timeout    60s;
    proxy_read_timeout    60s;
}
```

### Security Headers

The Nginx configuration **must** include the following security headers on all responses:

```nginx
add_header Strict-Transport-Security  "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options            "DENY" always;
add_header X-Content-Type-Options     "nosniff" always;
add_header Referrer-Policy            "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy    "default-src 'self'; script-src 'self'; object-src 'none';" always;
```

> Note: The `Content-Security-Policy` value above is a baseline. The provider must adjust it to match the actual resources used by the frontend (fonts, CDNs, etc.) and submit it for review.

### CORS

- CORS policy must be defined and enforced at the **backend application layer**, not solely at the Nginx level.
- Allowed origins must be loaded from an environment variable (`CORS_ALLOWED_ORIGINS`).
- `Access-Control-Allow-Origin: *` is **forbidden** in any environment.

---

## 10. Databases

- All databases **must** use authentication — no anonymous or passwordless access.
- A **dedicated database user** must be created for the application (do not use the root/admin user).
- Database credentials must be loaded from environment variables.
- Migration scripts must be versioned and idempotent (e.g., using tools like Flyway, Alembic, Knex, Prisma Migrate).
- Every migration **must** include a corresponding **rollback/down script**.
- Connection pooling must be configured appropriately for the expected load. For PostgreSQL, use `PgBouncer` or the application-level pool settings — the maximum pool size must be defined and documented.

---

## 11. Security Standards — Application Layer

### Dependency Vulnerability Scanning

The CI pipeline must include automated scanning at every build:

| Language | Tool | Command |
|---|---|---|
| Node.js | `npm audit` | `npm audit --audit-level=high` |
| Python | `pip-audit` | `pip-audit` |
| All | Snyk (optional, recommended) | `snyk test` |

Builds with **high** or **critical** severity vulnerabilities must fail the pipeline. The provider must resolve or formally accept (with written justification) any such finding before delivery.

### Docker Image Scanning

All images must be scanned with **Trivy** before being pushed to ECR:

```bash
trivy image --exit-code 1 --severity HIGH,CRITICAL <image>
```

Images with unresolved HIGH or CRITICAL CVEs will not be accepted in our environments.

### SAST (Static Analysis)

- The CI pipeline must include a static analysis stage using **Semgrep** or an equivalent tool.
- The ruleset must be agreed upon per project (e.g., `semgrep --config=p/owasp-top-ten`).

### Secrets Detection

- A secrets scanner (e.g., `gitleaks`, `trufflehog`) must be configured as a pre-commit hook and as a CI stage.
- No credentials, tokens, or private keys may be committed to the repository at any point — even in history.

---

## 12. API Standards

### Specification

- All backend APIs must be documented using **OpenAPI 3.x** specification.
- The `openapi.yaml` / `openapi.json` file must be maintained in the repository and kept in sync with the implementation.
- A Swagger UI endpoint must be available in development environments (`/docs` or `/api-docs`), and disabled in production via environment variable.

### Versioning

- All API routes must be prefixed with a version: `/api/v1/...`
- Breaking changes require a new version prefix.

### Error Response Format

All error responses must follow **RFC 7807 — Problem Details for HTTP APIs**:

```json
{
  "type": "https://errors.example.com/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "The field 'email' must be a valid email address.",
  "instance": "/api/v1/users"
}
```

---

## 13. Testing Requirements

The provider is responsible for delivering a tested codebase. The following requirements are mandatory:

### Unit Tests

- All business logic must be covered by unit tests.
- Minimum coverage threshold: **70%** (lines). This is a floor, not a target.
- Coverage reports must be generated in the CI pipeline and attached to each PR.

### Integration Tests

- Critical integration points (database queries, external API calls, authentication flows) must have integration tests.
- Integration tests must run against real services using Docker Compose (not mocks for external services where avoidable).

### End-to-End Tests (if applicable)

- For projects with a frontend, at least the critical user journeys must be covered by E2E tests (e.g., using Playwright or Cypress).

### Test Execution

All tests must be executable with a single command from the repository root, for example:
```bash
docker compose -f docker-compose.test.yml run --rm tests
```

---

## 14. Documentation

### Required Documentation

The provider must deliver the following documents as part of the project:

| Document | Description |
|---|---|
| `README.md` | Project overview, local setup instructions, and how to run tests |
| `docs/architecture.md` | Architecture overview with component diagram |
| `docs/api.md` or `openapi.yaml` | Full API reference |
| `docs/database.md` | Schema overview and migration instructions |
| `docs/runbook.md` | Operational runbook: how to deploy, roll back, monitor, and troubleshoot |
| `env.example` | All environment variables with descriptions and example values |
| `CHANGELOG.md` | Version history following Keep a Changelog format |

### Architecture Decision Records (ADRs)

Significant technical decisions (choice of framework, data model design, external integrations) must be documented as **Architecture Decision Records** in `docs/adr/`. Each ADR must include: context, decision, and consequences.

> **Note on AI-assisted documentation:** AI coding tools may be used to assist in drafting documentation, but the provider is fully responsible for the accuracy and completeness of all delivered documentation. AI-generated content must be reviewed and validated by the development team before submission.

---

## 15. Our DevOps Responsibilities During Development

Our DevOps team is available for **consultation and access provisioning only**. We will not modify provider code or environments.

We will provide:
- AWS account creation (if needed)
- Network connectivity via **AWS Transit Gateway** — we handle cross-account networking only. We will **not** create or modify VPCs, subnets, route tables, or any network resources inside the provider's AWS account.
- Database snapshots / RDS Snapshots / Exports (if needed)
- Consultation on architecture and infrastructure questions

---

## 16. Security Standards in Our AWS Accounts

When the provider operates within our AWS accounts, the following security standards are **mandatory** and non-negotiable:

- **No public IP addresses** on EC2 instances, ECS tasks, or any compute resources. Use **Application Load Balancers (ALB)** for any public-facing access.
- **Least privilege IAM roles** — every IAM role and policy must grant only the minimum permissions required. No wildcard (`*`) actions or resources unless absolutely justified and approved.
- **Security Groups** — must follow least privilege. Only open the specific ports and source CIDRs required.
- **No `0.0.0.0/0` inbound rules for SSH (port 22) or RDP (port 3389)** — this is strictly forbidden. Use SSM Session Manager or a bastion host with restricted source IPs if remote access is needed.
- **No publicly accessible RDS instances** — all databases must be in private subnets with no public endpoint enabled.
- Any deviation from these standards must be requested and approved by our DevOps team in advance.

---

## 17. Handover Process

### Pre-Handover Checklist

Before scheduling the handover demo, the provider must confirm in writing that all of the following are complete:

- [ ] All CI/CD pipeline stages pass on `main`
- [ ] Docker image scan shows no HIGH/CRITICAL CVEs
- [ ] Test coverage meets the minimum threshold
- [ ] All required documentation is delivered and reviewed
- [ ] `env.example` is complete and up to date
- [ ] Health check endpoints are implemented and tested
- [ ] Security headers are configured in Nginx
- [ ] No secrets or credentials exist in Git history

### Pre-Handover Demo

Before handover, the provider must conduct a **live demo** for the DevOps team showing:
- The complete solution running via **Docker / Docker Compose / Kubernetes**
- **Not** via `npm run`, `uvicorn`, `python manage.py`, or any direct runtime command
- All services starting and communicating correctly
- Health check endpoints responding correctly
- Log output in ECS format visible on `stdout`

### Required Deliverables

1. Complete source code (in our repository)
2. `docker-compose.yml` (or Kubernetes manifests) that runs the full stack
3. `env.example` with all required environment variables documented
4. All database migration and rollback scripts with instructions
5. Step-by-step description of all "migration" steps (data seeding, schema changes, external service setup)
6. Full project documentation (as described in Section 14)
7. OpenAPI specification
8. Test suite with passing results and coverage report

### Handover Completion Criteria

The handover process is considered **complete** only when the software is running successfully in our **Test Environment** and all automated tests pass. Until that point, the provider remains responsible for resolving any issues related to deployment, configuration, or missing documentation.

### Warranty Period

Following handover completion, the provider is obligated to a **30-day warranty period** during which:
- Bugs classified as **Critical** or **High** must be resolved within **2 business days**.
- Bugs classified as **Medium** must be resolved within **5 business days**.
- The scope of warranty covers defects in delivered functionality, not new feature requests.

---

## Quick Reference — Do's and Don'ts

| ✅ Do | ❌ Don't |
|---|---|
| Host the repo in our organization account | Use a provider-owned repository as the primary |
| Follow Conventional Commits | Write vague or empty commit messages |
| Submit changes via Pull Requests with CI passing | Push directly to `main` or `develop` |
| Tag images with `semver` or `branch-sha` | Use `latest` as the sole image tag |
| Push images to our designated ECR | Use public or provider-owned registries |
| Load config from environment variables | Hardcode URLs, secrets, or config values |
| Use `docker run --env-file .env` for local testing | Use `dotenv` or `.env` in application startup |
| Use Alpine base images | Use full Debian/Ubuntu images without justification |
| Build for ARM64 | Build only for AMD64 without justification |
| Run containers as a non-root user | Run containers as `root` |
| Proxy backend through Nginx | Expose backend directly to the browser |
| Include security headers in Nginx | Serve responses without security headers |
| Define CORS origins via environment variable | Use `Access-Control-Allow-Origin: *` |
| Use dedicated DB users with auth | Use root DB user or no authentication |
| Include rollback scripts for all migrations | Deliver forward-only migration scripts |
| Use OIDC Authorization Code + PKCE | Use client secrets in frontend apps |
| Store tokens in memory or `httpOnly` cookies | Store tokens in `localStorage` |
| Call the Keycloak revocation endpoint on logout | Clear only local state on logout |
| Write ECS-formatted JSON logs to stdout | Write unstructured logs or log to files |
| Never log PII or secrets | Include emails, tokens, or passwords in logs |
| Implement `/health/live` and `/health/ready` | Omit health check endpoints |
| Handle `SIGTERM` for graceful shutdown | Let the process terminate abruptly |
| Expose Prometheus metrics at `/metrics` | Provide no operational visibility |
| Deliver an OpenAPI spec for all APIs | Leave APIs undocumented |
| Scan images with Trivy before delivery | Deliver images with known CVEs |
| Run `npm audit` / `pip-audit` in CI | Ship with unreviewed vulnerable dependencies |
| Write unit + integration tests (≥70% coverage) | Deliver untested code |
| Demo with Docker/Compose/K8s | Demo with `npm run dev` or `uvicorn` |
| Run all local services as Docker containers | Run services directly on host machine |
| Use ALB for public-facing access | Assign public IPs to instances |
| Use least privilege IAM and Security Groups | Use wildcard IAM policies or open Security Groups |
| Keep RDS in private subnets | Make RDS publicly accessible |
| Use SSM / restricted bastion for access | Open SSH/RDP to `0.0.0.0/0` |
