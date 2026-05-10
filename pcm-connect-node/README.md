# PCM/FHIR Data Source Adapter

A Node.js/TypeScript adapter that bridges between the Israel PCM (Patient Consent Management) authorization system and internal FHIR R4 data sources.

## What This Adapter Does

This adapter implements the PCM data source role in the Israeli health information exchange ecosystem:

1. **Accepts opaque access tokens** from service providers
2. **Introspects tokens** with PCM to retrieve authorization context
3. **Resolves national patient identifiers** to local patient IDs
4. **Forwards authorized FHIR queries** to internal FHIR servers
5. **Verifies responses** comply with authorization rules (e.g., V-label exclusion)
6. **Returns filtered FHIR resources** to service providers

## Architecture

```
Service Provider → [Opaque Token] → PCM Adapter → [Internal JWT] → FHIR Server
                                    ↓
                            PCM Introspection
                            ID Replacement
                            Response Verification
```

## Implementation Status

**✅ What's Currently Implemented:**
- Full mock mode for local development (no external dependencies)
- Real PCM token acquisition via mTLS (OAuth2 client credentials)
- Real PCM token introspection via mTLS
- FHIR GET proxy with parameter injection
- Response verification (V-label security filtering)
- Internal JWT minting for FHIR server auth
- Health/readiness endpoints
- Comprehensive test suite

**⏳ What's Still Mocked (Pending External Integration):**
- ID replacement service (currently returns mock patient IDs)
- Internal FHIR server (currently returns mock FHIR bundles)
- Service provider token introspection (tested with mock tokens)

**🔮 Not Yet Implemented (Future Production Features):**
- POST/PUT/DELETE FHIR operations (only GET currently supported)
- Basket-based consent filtering
- Scope-based resource access control
- Multi-patient queries

See [docs/project-status.md](docs/project-status.md) for complete implementation details.

## Prerequisites

- Node.js 20+ LTS
- Docker & Docker Compose (for containerized deployment)
- Python 3.8+ (optional, for Python PCM token tool)
- PCM certificate bundle (for Connectathon testing)

## Deployment Modes

This adapter supports three distinct deployment modes. Choose based on your environment:

### 🏠 Mode 1: Local Mock/Demo (No External Dependencies)

**Use for:** Local development, testing, demos without PCM infrastructure.

**What runs in mock mode:**
- PCM introspection returns mock authorization data
- FHIR server returns mock FHIR R4 bundles
- ID replacement returns deterministic mock patient IDs

**External services required:** None

**See:** [Local Mock Setup](#local-mock-mode) below

---

### 🔬 Mode 2: Connectathon PCM + Mock Services

**Use for:** Testing real PCM integration with Connectathon certificate bundle.

**What's real:**
- PCM token acquisition (mTLS, OAuth2 client credentials)
- PCM token introspection (mTLS)

**What's still mocked:**
- FHIR server (returns mock bundles)
- ID replacement (returns mock patient IDs)

**External services required:** PCM Connectathon environment + certificate bundle

**See:** [Connectathon Setup](#connectathon-mode) below

---

### 🏭 Mode 3: Production (Future - Not Yet Ready)

**Use for:** Production deployment with all real services.

**What's real:**
- PCM token acquisition and introspection (mTLS)
- Internal FHIR server (real FHIR R4 data)
- ID replacement service (real patient ID resolution)

**External services required:** All production services configured

**Status:** ⏳ Pending production service integration (see [docs/project-status.md](docs/project-status.md))

---

## Quick Start

### Local Mock Mode (No External Dependencies) {#local-mock-mode}

```bash
# 1. Install dependencies
npm install

# 2. Configure for mock mode
cp .env.example .env
# Edit .env to ensure these lines:
#   PCM_INTROSPECTION_MODE=mock
#   FHIR_FORWARDING_MODE=mock
#   ID_REPLACEMENT_MODE=mock

# 3. Run verification
npm run verify:local

# 4. Start server
npm start

# 5. Test endpoints
curl http://localhost:3009/health
curl http://localhost:3009/ready
curl -H "Authorization: Bearer test" "http://localhost:3009/fhir/Observation?code=test"
```

**Expected behavior:** Mock FHIR bundle returned, no external calls made.

---

### Connectathon Mode {#connectathon-mode}

```bash
# 1. Extract certificate bundle
# Download org-connecthon-python-XXXXXX.zip from PCM admin
# Extract to: ./secrets/connectathon/
# Expected structure:
#   ./secrets/connectathon/rootCA.crt
#   ./secrets/connectathon/custom/org-connecthon-python-XXXXXX.crt
#   ./secrets/connectathon/custom/org-connecthon-python-XXXXXX.key
#   ./secrets/connectathon/bundle.json

# 2. Configure for Connectathon
cp .env.connectathon.example .env
# Edit .env to match your bundle:
#   Update DATA_SOURCE_ID (from bundle.json)
#   Update PCM_CLIENT_ID (from bundle.json)
#   Update certificate paths (from bundle.json)
#   Update PCM_CLIENT_CERT_THUMBPRINT (from bundle.json)
#   Verify PCM_INTROSPECTION_MODE=pcm (NOT mock)
#   Keep FHIR_FORWARDING_MODE=mock and ID_REPLACEMENT_MODE=mock

# 3. Verify certificates and PCM connectivity
npm run verify:connectathon

# 4. Start server
npm start

# 5. Test mock flow end-to-end
npm run verify:mock-flow
```

**Expected behavior:** Real PCM calls succeed, mock FHIR responses returned.

---

### Docker Compose

```bash
# Ensure .env is configured (see above modes)
# Ensure secrets/ directory exists with certificates

# Build and start
docker compose up -d

# View logs
docker compose logs -f pcm-adapter

# Test
curl http://localhost:3009/health
curl http://localhost:3009/ready

# Stop
docker compose down
```

---

## Full Documentation

Jump to:
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [Testing & Verification](#testing)
- [API Endpoints](#api-endpoints)
- [Security](#security-notes)
- [Troubleshooting](#troubleshooting)

---

## Configuration

### Step-by-Step: Configuring `.env`

#### For Local Mock Mode:

1. **Copy the template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and verify these critical settings:**
   ```bash
   # Server
   PORT=3009
   NODE_ENV=development

   # Data Source Identity (placeholder for mock mode)
   DATA_SOURCE_ID=data-source-org-id
   DATA_SOURCE_ENDPOINT=https://data-source.example.com

   # PCM Configuration - MOCK MODE
   PCM_INTROSPECTION_MODE=mock

   # Internal FHIR Server - MOCK MODE
   FHIR_FORWARDING_MODE=mock
   FHIR_BASE_URL=http://mock-fhir.local

   # ID Replacement Service - MOCK MODE
   ID_REPLACEMENT_MODE=mock
   ID_REPLACEMENT_BASE_URL=http://mock-id-replacement.local

   # Internal JWT - Use placeholder paths for mock mode
   JWT_ISSUER=data-source-org-id
   JWT_AUDIENCE=http://mock-fhir.local
   JWT_ALGORITHM=RS256
   JWT_SIGNING_KEY_PATH=/path/to/internal-jwt-private.pem
   ```

3. **What you DON'T need for mock mode:**
   - Real PCM certificates (PCM_MTLS_CERT_PATH, PCM_MTLS_KEY_PATH, PCM_CA_CERT_PATH)
   - Real PCM URLs
   - Real FHIR server URLs
   - Real ID replacement endpoints

---

#### For Connectathon Mode:

1. **Copy the Connectathon template:**
   ```bash
   cp .env.connectathon.example .env
   ```

2. **Extract certificate bundle:**
   ```bash
   # Unzip your bundle: org-connecthon-python-XXXXXX.zip
   # Expected directory structure after extraction:
   ./secrets/connectathon/
   ├── rootCA.crt
   ├── bundle.json
   └── custom/
       ├── org-connecthon-python-XXXXXX.crt
       └── org-connecthon-python-XXXXXX.key
   ```

3. **Edit `.env` with values from `bundle.json`:**
   ```bash
   # Data Source Identity (from bundle.json)
   DATA_SOURCE_ID=org-connecthon-python-298c5466  # Example - use YOUR bundle ID
   DATA_SOURCE_ENDPOINT=https://connecthon-python.demo  # Example - use YOUR endpoint

   # PCM Configuration - REAL PCM MODE
   PCM_INTROSPECTION_MODE=pcm  # ← Must be "pcm", NOT "mock"
   PCM_BASE_URL=https://pcm-connectathon-mtls-XXXXXX.elb.il-central-1.amazonaws.com:4501  # From bundle
   PCM_CLIENT_ID=https://connecthon-python.demo  # Same as DATA_SOURCE_ENDPOINT
   PCM_CLIENT_CERT_THUMBPRINT=2-mGHGuZkYLdh6YgnoP3-trBcBJbqOGXjobtjI_sRxM  # From bundle

   # Certificate paths - MATCH YOUR EXTRACTED FILES
   PCM_MTLS_CERT_PATH=./secrets/connectathon/custom/org-connecthon-python-298c5466.crt
   PCM_MTLS_KEY_PATH=./secrets/connectathon/custom/org-connecthon-python-298c5466.key
   PCM_CA_CERT_PATH=./secrets/connectathon/rootCA.crt
   PCM_TLS_SERVERNAME=pcm-core  # Required for Connectathon

   # Client Assertion - USUALLY SAME KEY AS MTLS
   PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH=./secrets/connectathon/custom/org-connecthon-python-298c5466.key
   PCM_CLIENT_ASSERTION_ALGORITHM=RS256  # Run `npm run cert:check` to verify

   # FHIR and ID still mocked
   FHIR_FORWARDING_MODE=mock
   ID_REPLACEMENT_MODE=mock
   ```

4. **Verify configuration:**
   ```bash
   npm run cert:check           # Validates certificates and key compatibility
   npm run pcm:token:check      # Tests PCM token acquisition
   ```

---

### Configuration Reference

All available settings are documented in `.env.example`. Key categories:

| Category | Example Variables | Description |
|----------|------------------|-------------|
| **Server** | `PORT`, `NODE_ENV` | Basic server configuration |
| **Data Source Identity** | `DATA_SOURCE_ID`, `DATA_SOURCE_ENDPOINT` | Your organization's PCM registration |
| **PCM Integration** | `PCM_BASE_URL`, `PCM_INTROSPECTION_MODE` | PCM connection and mode selection |
| **PCM Certificates** | `PCM_MTLS_CERT_PATH`, `PCM_CA_CERT_PATH` | mTLS certificate paths |
| **FHIR Server** | `FHIR_BASE_URL`, `FHIR_FORWARDING_MODE` | Internal FHIR server configuration |
| **ID Replacement** | `ID_REPLACEMENT_BASE_URL`, `ID_REPLACEMENT_MODE` | Patient ID resolution service |
| **Internal JWT** | `JWT_SIGNING_KEY_PATH`, `JWT_ALGORITHM` | JWT for FHIR server auth |
| **Security** | `RESPONSE_VERIFICATION_ENABLED` | Response filtering configuration |

**Key mode settings:**
- `PCM_INTROSPECTION_MODE`: `mock` (local dev) or `pcm` (real PCM)
- `FHIR_FORWARDING_MODE`: `mock` (local dev) or `http` (real FHIR)
- `ID_REPLACEMENT_MODE`: `mock` (local dev) or `http` (real ID service)

See `.env.example` for inline documentation of every variable.

## Running Locally (Without Docker)

### Prerequisites
- Node.js 20+ LTS installed
- `.env` file configured (see [Configuration](#configuration))
- For Connectathon mode: certificate bundle extracted to `secrets/connectathon/`

### Development Mode (Auto-reload)
```bash
npm install
npm run start:dev
```

The server will restart automatically when you edit TypeScript files.

### Production Build
```bash
npm install
npm run build    # Compiles TypeScript to dist/
npm start        # Runs compiled JavaScript from dist/
```

**Server details:**
- Default port: `3009` (override with `PORT` env var)
- Logs to: stdout (JSON format)
- Process will exit on fatal config errors (missing certs, invalid URLs)

**Testing the running server:**
```bash
# Health check
curl http://localhost:3009/health
# Expected: {"status":"ok"}

# Readiness check (validates config and certificates)
curl http://localhost:3009/ready
# Expected: {"status":"ready","config":"ok","pcmCerts":"ok"} (Connectathon mode)
# Expected: {"status":"ready","config":"ok","pcmCerts":"N/A (mock mode)"} (Mock mode)

# FHIR proxy (requires Authorization header)
curl -H "Authorization: Bearer mock-token-123" \
  "http://localhost:3009/fhir/Observation?code=15074-8"
# Expected: FHIR R4 Bundle (mock or real depending on mode)
```

---

## Running with Docker Compose

### Prerequisites
- Docker and Docker Compose installed
- `.env` file configured (see [Configuration](#configuration))
- For Connectathon mode: `secrets/` directory with certificates

### Build and Run
```bash
# Build image
docker compose build

# Start service (detached)
docker compose up -d

# View logs (follow mode)
docker compose logs -f pcm-adapter

# Check status
docker compose ps

# Stop service
docker compose down
```

### Troubleshooting Docker
```bash
# Rebuild without cache
docker compose build --no-cache

# Start in foreground (see logs immediately)
docker compose up

# Execute commands inside container
docker compose exec pcm-adapter sh

# Check container health
docker compose exec pcm-adapter curl http://localhost:3009/health
```

**Important for Connectathon mode:**
- The `secrets/` directory must exist before running `docker compose up`
- Docker Compose mounts `./secrets:/app/secrets` as read-only
- Certificate paths in `.env` must be relative to `/app/` inside container

## Testing & Verification

### Unit Tests

```bash
# Run all unit tests
npm test

# Run with coverage report
npm run test:cov

# Run specific test file
npm test -- src/pcm/pcm-introspection.service.spec.ts

# Watch mode (auto-rerun on changes)
npm test -- --watch
```

**Test coverage:** 66 unit tests covering PCM integration, JWT, FHIR proxy, response verification.

---

### Verification Scripts

Use these scripts to validate configuration and connectivity:

#### `npm run verify:local`
**What it does:** Builds project and runs unit tests  
**Use when:** Validating local development setup  
**Requires:** None (works with mock mode)  
**Expected output:**
```
✓ Build successful
✓ 66 tests passed
```

---

#### `npm run verify:connectathon`
**What it does:** Validates certificates and tests PCM token acquisition  
**Use when:** Setting up Connectathon environment  
**Requires:** 
- Connectathon certificate bundle extracted to `secrets/connectathon/`
- `.env` configured with `PCM_INTROSPECTION_MODE=pcm`
- Network access to PCM Connectathon endpoint

**Expected output:**
```
✓ Certificates found and valid
✓ Key type matches algorithm (RS256/ES256)
✓ PCM token acquired successfully
✓ Token contains expected claims
```

**What it tests:**
- Certificate file existence and format
- Private key compatibility with configured algorithm
- mTLS connection to PCM
- OAuth2 client credentials flow
- Client assertion JWT generation

**Run components separately:**
```bash
npm run cert:check         # Just certificate validation
npm run pcm:token:check    # Just PCM token acquisition
```

---

#### `npm run verify:mock-flow`
**What it does:** Simulates full adapter flow end-to-end  
**Use when:** Testing complete request flow  
**Requires:** Server running (`npm start` in another terminal)  
**Expected output:**
```
✓ Health endpoint responding
✓ FHIR proxy accepts bearer token
✓ Mock introspection successful
✓ Mock ID replacement successful
✓ FHIR bundle returned
```

**Alias:** `npm run adapter:e2e:check`

---

#### `npm run pcm:token:check`
**What it does:** Tests PCM token acquisition via mTLS  
**Use when:** Debugging PCM connectivity issues  
**Requires:** Connectathon setup (see `verify:connectathon`)  
**Expected output:**
```
🔐 Acquiring PCM token...
✓ Token acquired: eyJhbGciOiJSUzI1Ni...
✓ Expires in: 30 seconds
✓ Token type: Bearer
```

**What can go wrong:**
- `ENOTFOUND`: Check `PCM_BASE_URL` in `.env`
- `UNABLE_TO_VERIFY_LEAF_SIGNATURE`: Check `PCM_CA_CERT_PATH`
- `wrong signature type`: Check `PCM_CLIENT_ASSERTION_ALGORITHM` matches key type
- `invalid_client`: Check `PCM_CLIENT_ID` and certificate thumbprint

---

#### `npm run adapter:e2e:check`
**What it does:** Same as `verify:mock-flow` (alias)  
**Use when:** Verifying end-to-end adapter flow  
**Requires:** Server running

---

### Additional Verification Commands

```bash
# Certificate inspection
npm run cert:check

# ID replacement service test (mock or real)
npm run id:resolve:check

# Manual endpoint testing
curl http://localhost:3009/health
curl http://localhost:3009/ready
curl -H "Authorization: Bearer test" "http://localhost:3009/fhir/Patient"
```

---

### Testing Checklist for New Developers

**Before first commit:**
```bash
✓ npm run verify:local          # Unit tests pass
✓ npm start                     # Server starts without errors
✓ curl http://localhost:3009/health  # Returns {"status":"ok"}
```

**Before testing with Connectathon:**
```bash
✓ Certificate bundle extracted to secrets/connectathon/
✓ .env copied from .env.connectathon.example
✓ Bundle values (ID, thumbprint) updated in .env
✓ npm run verify:connectathon   # Certificates valid, PCM token acquired
✓ npm start                     # Server starts without certificate errors
✓ curl http://localhost:3009/ready  # Returns ready status
```

## API Endpoints

### GET /health

**Purpose:** Basic liveness check (no dependencies validated)

**Authentication:** None

**Response:**
```json
{"status": "ok"}
```

**Use cases:**
- Kubernetes liveness probe
- Load balancer health check
- Quick connectivity test

**Example:**
```bash
curl http://localhost:3009/health
```

---

### GET /ready

**Purpose:** Readiness check with full config and certificate validation

**Authentication:** None

**Response (Connectathon mode):**
```json
{
  "status": "ready",
  "config": "ok",
  "pcmCerts": "ok"
}
```

**Response (Mock mode):**
```json
{
  "status": "ready",
  "config": "ok",
  "pcmCerts": "N/A (mock mode)"
}
```

**Use cases:**
- Kubernetes readiness probe
- Pre-deployment validation
- Certificate expiry monitoring

**What it validates:**
- Environment variables loaded
- PCM certificate files exist (Connectathon mode)
- Certificate format valid (Connectathon mode)
- Key type matches configured algorithm

**Example:**
```bash
curl http://localhost:3009/ready
```

**Possible errors:**
- `503 Service Unavailable`: Missing certificates or invalid configuration

---

### GET /fhir/*

**Purpose:** FHIR R4 resource proxy with PCM authorization

**Authentication:** Required  
`Authorization: Bearer <opaque-pcm-token>`

**Supported FHIR Resources:**
- `/fhir/Patient?...`
- `/fhir/Observation?...`
- `/fhir/Condition?...`
- All FHIR R4 search endpoints

**Request Flow:**
1. **Extract token** from Authorization header
2. **Introspect token** with PCM (or mock)
3. **Extract patient ID** from introspection response
4. **Resolve patient ID** to local ID (or mock)
5. **Mint internal JWT** for FHIR server auth
6. **Forward request** to FHIR server with:
   - `patient=<local-id>` injected into query
   - `_security:not=V` injected (V-label exclusion)
   - Internal JWT in Authorization header
7. **Verify response** (check for forbidden security labels)
8. **Return** filtered FHIR Bundle or OperationOutcome

**Example (Mock Mode):**
```bash
curl -H "Authorization: Bearer test-token-123" \
  "http://localhost:3009/fhir/Observation?code=15074-8"
```

**Example (Connectathon Mode):**
```bash
# First acquire a service provider token (not shown - external to adapter)
# Then introspect it via adapter:
curl -H "Authorization: Bearer <real-opaque-token>" \
  "http://localhost:3009/fhir/Observation?code=15074-8"
```

**Success Response (200 OK):**
```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "entry": [
    {
      "resource": {
        "resourceType": "Observation",
        "id": "obs-123",
        ...
      }
    }
  ]
}
```

**Error Responses:**

| Status | Scenario | OperationOutcome |
|--------|----------|------------------|
| `401` | Missing/invalid Authorization header | `security` / `Unauthorized` |
| `401` | PCM introspection failed | `security` / `Invalid token` |
| `403` | Response contains forbidden label | `security` / `Forbidden resource` |
| `500` | ID replacement failed | `transient` / `ID resolution error` |
| `502` | FHIR server error | `transient` / `FHIR server error` |

**Limitations (Current Implementation):**
- ❌ **POST/PUT/DELETE not supported** (only GET)
- ❌ **No batch/transaction operations**
- ❌ **Single patient context** (multi-patient queries rejected)
- ✅ **V-label exclusion** implemented
- ⏳ **Basket-based filtering** not yet implemented

## Security Notes

🔒 **CRITICAL SECURITY RULES**

### ❌ NEVER Commit These Files

**Environment files:**
- ❌ `.env` (contains secrets)
- ✅ `.env.example` (safe template - commit this)
- ✅ `.env.connectathon.example` (safe template - commit this)

**Certificate and key files:**
- ❌ `secrets/` directory (entire directory gitignored)
- ❌ `*.key` (private keys)
- ❌ `*.pem` (may contain private keys)
- ❌ `*.crt` (certificates may contain sensitive org info)
- ❌ `*.p12`, `*.pfx` (PKCS#12 bundles)
- ❌ `bundle.json` (contains certificate thumbprints and URLs)

**Token and credential files:**
- ❌ Any file containing `token`, `password`, `secret` in content
- ❌ Temporary token files from scripts

### ❌ NEVER Print to Logs

**Forbidden in logs (current implementation prevents this):**
- ❌ Access tokens (opaque or JWT)
- ❌ Private keys
- ❌ Patient identifiers (national ID, local ID)
- ❌ Authorization headers
- ❌ Internal JWTs

**Safe to log:**
- ✅ Token expiry times
- ✅ Token types (Bearer)
- ✅ Masked patient IDs (`123***789`)
- ✅ Configuration mode (`mock`, `pcm`, `http`)
- ✅ Request correlation IDs

**Debugging tokens (local only):**
```bash
# If you MUST debug a token locally:
# 1. Use environment variable (never log to file):
export DEBUG_TOKEN=eyJhbGc...

# 2. NEVER commit debug code that prints tokens

# 3. Remove debug env var after session:
unset DEBUG_TOKEN
```

---

### Pre-Push Security Checklist

**Run before every `git push`:**

```bash
# 1. Check no secrets tracked
git status --short
git ls-files | grep -E '\.(env|key|pem|crt|p12|pfx)$'
git ls-files | grep secrets/

# ✅ Should return EMPTY or ONLY:
#    .env.example
#    .env.connectathon.example

# 2. Check no tokens in code
git grep -i "Bearer ey" -- '*.ts' '*.js'
git grep -i "password.*=.*['\"]" -- '*.ts' '*.js'

# ✅ Should return EMPTY (or only test mocks)

# 3. Build and test
npm run verify:local

# ✅ Should pass all tests
```

---

### If You Accidentally Committed Secrets

**Option 1: Secret not yet pushed (safe - local only)**
```bash
# Remove from staging
git restore --staged .env secrets/

# OR remove from last commit
git reset --soft HEAD~1
git restore --staged .env secrets/
git commit -m "Your commit message (without secrets)"
```

**Option 2: Secret already pushed (DANGEROUS - requires force push)**
```bash
# 1. Remove from Git history
git rm --cached .env
git rm --cached -r secrets/
git commit -m "Remove accidentally tracked secrets"

# 2. Force push (ONLY if you're alone on the branch)
git push --force

# 3. ROTATE THE COMPROMISED SECRETS IMMEDIATELY
# - Request new certificate bundle from PCM admin
# - Regenerate any exposed keys
# - Update .env with new values
```

**⚠️ Important:** If secrets were pushed to a shared branch:
1. **Assume secrets are compromised**
2. **Rotate all certificates and keys immediately**
3. **Contact security team if PHI or production credentials exposed**

---

### .gitignore Protection

The repository `.gitignore` already protects:
```gitignore
# Environment files
.env
.env.local
*.env

# Secrets directory
secrets/

# Keys and certificates
*.key
*.pem
*.p12
*.pfx
*.crt
*.cer
```

**Never edit `.gitignore` to remove these protections.**

---

### Security Logging (Production)

When deploying to production:
- ✅ **Audit logs enabled** (`AUDIT_ENABLED=true`)
- ✅ **Logs sent to secure aggregator** (e.g., Splunk, ELK)
- ✅ **No PII/PHI in logs** (patient IDs masked)
- ✅ **Log retention policy** (90 days recommended)
- ✅ **Log access control** (authorized personnel only)

Current implementation logs:
- Request correlation IDs
- PCM introspection status (success/failure)
- FHIR forwarding status
- Response verification results
- Error types (no sensitive details)

---

### Security Hardening Checklist (Production)

Before production deployment:
- [ ] Secrets stored in secret management system (Vault, AWS Secrets Manager)
- [ ] Certificates auto-rotated before expiry
- [ ] mTLS enforced for all PCM communication
- [ ] Internal FHIR auth uses short-lived JWTs (60s)
- [ ] Response verification enabled (`RESPONSE_VERIFICATION_ENABLED=true`)
- [ ] Audit logging enabled (`AUDIT_ENABLED=true`)
- [ ] No mock modes in production config
- [ ] Docker image scanned for vulnerabilities
- [ ] Network policies restrict egress to known endpoints
- [ ] Rate limiting configured
- [ ] Security monitoring alerts configured

## Project Structure

```
pcm-project/
├── src/
│   ├── audit/          # Audit logging
│   ├── config/         # Configuration & validation
│   ├── fhir/           # FHIR proxy & forwarding
│   ├── identity/       # ID replacement
│   ├── jwt/            # Internal JWT
│   ├── pcm/            # PCM integration
│   └── scripts/        # Verification scripts
├── tools/python-pcm-token/  # Python PCM tool
├── secrets/            # Certificates (gitignored)
├── docs/               # Documentation
└── docker-compose.yml
```

## Troubleshooting

### Server Won't Start

**Symptom:** Process exits immediately after `npm start`

**Common causes:**

1. **Missing or invalid `.env` file:**
   ```bash
   # Check if .env exists
   ls -la .env
   
   # Verify it's not empty
   cat .env | head -5
   
   # Solution: Copy from template
   cp .env.example .env
   ```

2. **Invalid configuration values:**
   ```bash
   # Check for common issues:
   grep -E "^[A-Z_]+=\s*$" .env  # Empty required values
   grep "#" .env | grep -v "^#"   # Inline comments (not allowed)
   
   # Solution: Remove inline comments, fill required values
   ```

3. **Certificate file not found (Connectathon mode):**
   ```bash
   # Verify certificate paths
   npm run cert:check
   
   # Check files exist
   ls -l secrets/connectathon/custom/
   ls -l secrets/connectathon/rootCA.crt
   
   # Solution: Extract certificate bundle or switch to mock mode
   ```

---

### Certificate Errors

**Symptom:** `npm run cert:check` fails

**Error: "Certificate file not found"**
```bash
# Check path in .env
grep PCM_MTLS_CERT_PATH .env
grep PCM_MTLS_KEY_PATH .env

# Verify files exist at those paths
ls -l $(grep PCM_MTLS_CERT_PATH .env | cut -d= -f2)

# Solution: Fix paths in .env or extract certificate bundle
```

**Error: "Key type mismatch" or "wrong signature type"**
```bash
# Check key type
openssl rsa -in secrets/connectathon/custom/*.key -text -noout 2>/dev/null && echo "RSA key"
openssl ec -in secrets/connectathon/custom/*.key -text -noout 2>/dev/null && echo "EC key"

# Update algorithm in .env:
# RSA key → PCM_CLIENT_ASSERTION_ALGORITHM=RS256
# EC key  → PCM_CLIENT_ASSERTION_ALGORITHM=ES256
```

**Error: "Certificate expired"**
```bash
# Check certificate expiry
openssl x509 -in secrets/connectathon/custom/*.crt -noout -dates

# Solution: Request new certificate bundle from PCM admin
```

---

### PCM Connection Issues

**Symptom:** `npm run pcm:token:check` fails

**Error: "ENOTFOUND" or "ECONNREFUSED"**
```bash
# Check PCM URL is reachable
curl -v https://pcm-connectathon-mtls-XXXXXX.elb.il-central-1.amazonaws.com:4501/

# Common issues:
# - Wrong URL in .env (check PCM_BASE_URL)
# - Firewall blocking port 4501
# - VPN required (check with PCM admin)

# Solution: Verify PCM_BASE_URL in .env matches bundle.json
grep PCM_BASE_URL .env
cat secrets/connectathon/bundle.json | grep -i url
```

**Error: "UNABLE_TO_VERIFY_LEAF_SIGNATURE"**
```bash
# CA certificate issue
# Check CA path in .env
grep PCM_CA_CERT_PATH .env

# Verify CA file exists and is valid
openssl x509 -in $(grep PCM_CA_CERT_PATH .env | cut -d= -f2) -noout -subject

# Solution: Ensure PCM_CA_CERT_PATH points to rootCA.crt from bundle
```

**Error: "invalid_client"**
```bash
# Client ID or certificate mismatch
# Verify values match bundle.json:
grep PCM_CLIENT_ID .env
grep PCM_CLIENT_CERT_THUMBPRINT .env
cat secrets/connectathon/bundle.json

# Calculate thumbprint from your certificate
openssl x509 -in secrets/connectathon/custom/*.crt -noout -fingerprint -sha256 | \
  sed 's/://g' | cut -d= -f2 | xxd -r -p | base64 | tr '+/' '-_' | tr -d '='

# Solution: Update .env with exact values from bundle.json
```

**Error: "Certificate has expired"**
```bash
# Certificate validity
openssl x509 -in secrets/connectathon/custom/*.crt -noout -checkend 0

# Solution: Request new bundle from PCM admin
```

---

### Mock Mode Not Working

**Symptom:** Server starts but doesn't use mock responses

**Check configuration:**
```bash
# Verify all three mode settings
grep MODE .env

# Should see:
# PCM_INTROSPECTION_MODE=mock
# FHIR_FORWARDING_MODE=mock
# ID_REPLACEMENT_MODE=mock

# Check server logs for mode confirmation
npm start | grep -i mock

# Expected log output:
# [ConfigService] PCM introspection mode: mock
# [ConfigService] FHIR forwarding mode: mock
# [ConfigService] ID replacement mode: mock
```

**Solution:**
```bash
# Reset to full mock mode
sed -i '' 's/PCM_INTROSPECTION_MODE=.*/PCM_INTROSPECTION_MODE=mock/' .env
sed -i '' 's/FHIR_FORWARDING_MODE=.*/FHIR_FORWARDING_MODE=mock/' .env
sed -i '' 's/ID_REPLACEMENT_MODE=.*/ID_REPLACEMENT_MODE=mock/' .env
```

---

### FHIR Proxy Returns 401

**Symptom:** `curl -H "Authorization: Bearer test" http://localhost:3009/fhir/Patient` returns 401

**Check logs:**
```bash
# Start server with debug output
npm start

# In another terminal, make request
curl -v -H "Authorization: Bearer test" "http://localhost:3009/fhir/Patient"

# Look for errors in server logs
```

**Common causes:**
1. Missing Authorization header (check curl command)
2. PCM introspection failed (check `PCM_INTROSPECTION_MODE` in .env)
3. Token format invalid (mock mode accepts any token)

---

### Docker Issues

**Symptom:** `docker compose up` fails

**Error: "secrets directory not found"**
```bash
# Check secrets directory exists
ls -ld secrets/

# Solution: Create directory (even if using mock mode)
mkdir -p secrets/connectathon
```

**Error: "Build failed"**
```bash
# Clean rebuild
docker compose down
docker compose build --no-cache
docker compose up
```

**Container starts but health check fails:**
```bash
# Check container logs
docker compose logs pcm-adapter

# Execute commands inside container
docker compose exec pcm-adapter sh
# Then inside container:
curl http://localhost:3009/health
cat /app/.env | head -10
```

---

### Testing Scripts Fail

**`npm run verify:connectathon` fails:**
```bash
# Run components individually to isolate issue
npm run cert:check          # Certificate validation
npm run pcm:token:check     # PCM connectivity

# Check which fails and see relevant section above
```

**`npm run verify:mock-flow` fails:**
```bash
# Ensure server is running
npm start &
sleep 5

# Then run verification
npm run verify:mock-flow

# Kill background server after
killall node
```

---

### Need More Help?

1. **Check detailed status:** See [docs/project-status.md](docs/project-status.md)
2. **Enable debug logging:** Set `NODE_ENV=development` in `.env`
3. **Run full verification:**
   ```bash
   npm run verify:local          # Basic checks
   npm run verify:connectathon   # Connectathon checks
   ```
4. **Review logs carefully:** Most errors include actionable error messages

---

## Quick Reference for New Developers

### I just cloned the repo. What now?

```bash
# 1. Install dependencies
npm install

# 2. Set up mock mode (fastest way to explore)
cp .env.example .env

# 3. Verify everything works
npm run verify:local

# 4. Start server
npm start

# 5. Test it
curl http://localhost:3009/health
curl -H "Authorization: Bearer test" "http://localhost:3009/fhir/Observation?code=test"
```

### What are the main directories?

```
pcm-project/
├── src/
│   ├── pcm/            ← PCM integration (token, introspection)
│   ├── fhir/           ← FHIR proxy (main endpoint)
│   ├── jwt/            ← Internal JWT for FHIR auth
│   ├── identity/       ← Patient ID resolution
│   ├── config/         ← Configuration service
│   └── audit/          ← Audit logging
├── secrets/            ← Certificates (create this, never commit)
├── docs/               ← Project documentation
└── tools/              ← Python PCM token tool
```

### What can I test right now (mock mode)?

✅ **Working in mock mode:**
- `/health` and `/ready` endpoints
- Full FHIR proxy flow (`/fhir/*`)
- Internal JWT minting
- Response verification (V-label filtering)
- All unit tests

⏳ **Requires Connectathon setup:**
- Real PCM token acquisition
- Real PCM introspection
- mTLS certificate validation

⏳ **Not yet integrated:**
- Real internal FHIR server
- Real ID replacement service
- Production deployment

### How do I test with real PCM (Connectathon)?

1. **Get certificate bundle** from PCM admin (org-connecthon-python-XXXXXX.zip)
2. **Extract to** `./secrets/connectathon/`
3. **Configure:** `cp .env.connectathon.example .env`
4. **Update `.env`** with values from `bundle.json`
5. **Verify:** `npm run verify:connectathon`
6. **Run:** `npm start`

### What are the most important config settings?

| Setting | Values | Impact |
|---------|--------|--------|
| `PCM_INTROSPECTION_MODE` | `mock` or `pcm` | Use real PCM or mock responses |
| `FHIR_FORWARDING_MODE` | `mock` or `http` | Use real FHIR or mock responses |
| `ID_REPLACEMENT_MODE` | `mock` or `http` | Use real ID service or mock |
| `PCM_MTLS_CERT_PATH` | Path to .crt file | Required for Connectathon mode |
| `PCM_CLIENT_ASSERTION_ALGORITHM` | `RS256` or `ES256` | Must match key type |

### What should I never do?

❌ **Never commit:**
- `.env` file
- `secrets/` directory
- Any `*.key` or `*.pem` files
- Tokens or passwords

❌ **Never print to logs:**
- Access tokens
- Private keys
- Patient identifiers (unless masked)

### Where can I learn more?

- **Project status:** [docs/project-status.md](docs/project-status.md) (what's done, what's pending)
- **Full config reference:** `.env.example` (inline comments for every variable)
- **Connectathon config:** `.env.connectathon.example` (real PCM example)
- **Architecture:** See [Purpose](#what-this-adapter-does) and [docs/project-status.md](docs/project-status.md)

---

## License

UNLICENSED - Internal use only
