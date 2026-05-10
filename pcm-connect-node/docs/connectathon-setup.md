# Local Connectathon Certificate Bundle Setup

This guide explains how to set up the PCM Connectathon certificate bundle for local development and testing.

## Overview

The PCM Connectathon environment provides a certificate bundle for each registered data source. This bundle contains:

- **Client certificate** - for mutual TLS (mTLS) authentication with PCM
- **Client private key** - corresponding private key for the certificate
- **Root CA certificate** - for verifying PCM server certificates
- **Configuration metadata** - PCM endpoint URLs and data source identifiers

## Certificate Bundle Structure

The Connectathon certificate bundle is provided as a ZIP file containing:

```
bundle.zip
├── bundle.json                              # Configuration metadata
├── rootCA.crt                               # PCM root CA certificate
└── custom/
    ├── org-connecthon-python-298c5466.crt  # Client certificate
    └── org-connecthon-python-298c5466.key  # Client private key
```

**Important:** The exact filenames in `custom/` will vary based on your data source ID.

## Setup Steps

### 1. Extract the Certificate Bundle

Extract the ZIP file to the `secrets/connectathon/` directory (create if it doesn't exist):

```bash
# From the project root
mkdir -p secrets/connectathon
unzip /path/to/your-bundle.zip -d secrets/connectathon/
```

**Expected directory structure after extraction:**

```
pcm-project/
├── secrets/
│   └── connectathon/
│       ├── bundle.json
│       ├── rootCA.crt
│       └── custom/
│           ├── org-connecthon-python-298c5466.crt
│           └── org-connecthon-python-298c5466.key
├── src/
├── .env.example
├── .env.connectathon.example
└── ...
```

### 2. Review bundle.json

The `bundle.json` file contains all configuration values needed for PCM integration:

```json
{
  "dataSource": {
    "id": "org-connecthon-python-298c5466",
    "parentId": "org-connecthon-python-298c5466-parent",
    "name": "connecthon-python",
    "endpoint": "https://connecthon-python.demo",
    "clientId": "https://connecthon-python.demo",
    "certThumbprint": "2-mGHGuZkYLdh6YgnoP3-trBcBJbqOGXjobtjI_sRxM"
  },
  "pcm": {
    "issuer": "https://pcm-connectathon-mtls-...:4501",
    "tokenEndpoint": "https://pcm-connectathon-mtls-...:4501/token",
    "introspectionEndpoint": "https://pcm-connectathon-mtls-...:4501/introspect",
    "metadataEndpoint": "https://pcm-connectathon-mtls-...:4502/.well-known/oauth-authorization-server"
  }
}
```

**Note:** URLs have been abbreviated. Your `bundle.json` will contain full URLs.

### 3. Create Local .env File

Copy the Connectathon example to create your local `.env`:

```bash
cp .env.connectathon.example .env
```

**OR** manually update the certificate paths in your `.env` file:

```bash
# Data Source Identity
DATA_SOURCE_ID=org-connecthon-python-298c5466
DATA_SOURCE_ENDPOINT=https://connecthon-python.demo

# PCM Configuration
PCM_BASE_URL=https://pcm-connectathon-mtls-4c336523aef82051.elb.il-central-1.amazonaws.com:4501
PCM_TOKEN_ENDPOINT=/token
PCM_INTROSPECTION_ENDPOINT=/introspect
PCM_METADATA_ENDPOINT=https://pcm-connectathon-mtls-4c336523aef82051.elb.il-central-1.amazonaws.com:4502/.well-known/oauth-authorization-server
PCM_CLIENT_ID=https://connecthon-python.demo
PCM_CLIENT_CERT_THUMBPRINT=2-mGHGuZkYLdh6YgnoP3-trBcBJbqOGXjobtjI_sRxM
PCM_CLIENT_ASSERTION_AUDIENCE=https://pcm-connectathon-mtls-4c336523aef82051.elb.il-central-1.amazonaws.com:4501/token

# Certificate Paths (update with your actual data source ID)
PCM_MTLS_CERT_PATH=./secrets/connectathon/custom/org-connecthon-python-298c5466.crt
PCM_MTLS_KEY_PATH=./secrets/connectathon/custom/org-connecthon-python-298c5466.key
PCM_CA_CERT_PATH=./secrets/connectathon/rootCA.crt
PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH=./secrets/connectathon/custom/org-connecthon-python-298c5466.key
```

### 4. Verify Certificate Files

Check that the certificate files are readable and in the correct location:

```bash
# List certificate files (do NOT cat/print them)
ls -la secrets/connectathon/
ls -la secrets/connectathon/custom/

# Expected output:
# secrets/connectathon/bundle.json
# secrets/connectathon/rootCA.crt
# secrets/connectathon/custom/org-connecthon-python-298c5466.crt
# secrets/connectathon/custom/org-connecthon-python-298c5466.key
```

**Security reminder:**
- ✅ List file names and paths
- ❌ Do NOT print certificate or key contents
- ❌ Do NOT commit certificates or keys to version control
- ✅ The `secrets/` directory is gitignored

## Configuration Fields Explained

### Data Source Identity

| Field | Description | Example |
|-------|-------------|---------|
| `DATA_SOURCE_ID` | Unique identifier assigned by PCM | `org-connecthon-python-298c5466` |
| `DATA_SOURCE_ENDPOINT` | Public endpoint URL for this data source | `https://connecthon-python.demo` |

**Note:** In Connectathon, `DATA_SOURCE_ENDPOINT` is also used as the OAuth2 `client_id`.

### PCM Endpoints

| Field | Description | Example |
|-------|-------------|---------|
| `PCM_BASE_URL` | PCM Core API base URL | `https://pcm-...amazonaws.com:4501` |
| `PCM_TOKEN_ENDPOINT` | Path to token endpoint | `/token` |
| `PCM_INTROSPECTION_ENDPOINT` | Path to introspection endpoint | `/introspect` |
| `PCM_METADATA_ENDPOINT` | OAuth2 metadata/discovery endpoint | `https://pcm-...amazonaws.com:4502/.well-known/...` |

**Note:** Token and introspection use port 4501, metadata uses port 4502 in Connectathon.

### PCM Authentication

| Field | Description | Example |
|-------|-------------|---------|
| `PCM_CLIENT_ID` | OAuth2 client ID (same as endpoint) | `https://connecthon-python.demo` |
| `PCM_CLIENT_CERT_THUMBPRINT` | x5t#S256 thumbprint for CNF validation | `2-mGHGuZkYLdh6YgnoP3-trBcBJbqOGXjobtjI_sRxM` |
| `PCM_CLIENT_ASSERTION_AUDIENCE` | Audience claim for client assertion JWT | `https://pcm-.../token` |

### Certificate Paths

| Field | Description | Local Path |
|-------|-------------|------------|
| `PCM_MTLS_CERT_PATH` | Client certificate for mTLS | `./secrets/connectathon/custom/*.crt` |
| `PCM_MTLS_KEY_PATH` | Private key for mTLS | `./secrets/connectathon/custom/*.key` |
| `PCM_CA_CERT_PATH` | Root CA for verifying PCM | `./secrets/connectathon/rootCA.crt` |
| `PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH` | Key for signing client assertion | `./secrets/connectathon/custom/*.key` |

**Note:** In Connectathon, the same private key is used for both mTLS and client assertion signing.

## Verification

After setup, verify the configuration is loaded correctly:

```bash
# Build the project
npm run build

# Run tests
npm test

# Start the server
PORT=3009 npm start

# In another terminal, check health endpoint
curl http://localhost:3009/health
# Expected: {"status":"ok"}
```

**Note:** The adapter is now configured to use the Connectathon certificates, but PCM HTTP calls are not yet implemented. The configuration is prepared for future integration.

## What's Next

The certificate bundle setup prepares the project for PCM integration:

- ✅ Configuration fields defined and loaded
- ✅ Certificate paths configured
- ✅ Endpoint URLs set from bundle
- ⏸️ PCM token acquisition (not yet implemented)
- ⏸️ PCM introspection calls (not yet implemented)
- ⏸️ mTLS HTTP client (not yet implemented)

The next implementation step will add PCM token service with OAuth2 client credentials flow using these certificates.

## Security Notes

### What is Gitignored

The following are automatically excluded from version control:

- `secrets/` directory (entire directory)
- `.env` file (local environment variables)
- `.env.local` and `.env.*.local` files
- `*.key` files (private keys)
- `*.pem` files (PEM-encoded keys/certs)
- `*.crt` files (certificates)
- `*.p12` and `*.pfx` files (PKCS#12 bundles)

### What Can Be Committed

- ✅ `.env.example` - generic placeholders, no secrets
- ✅ `.env.connectathon.example` - public demo URLs, no secrets
- ✅ Documentation and setup guides
- ❌ Real `.env` files
- ❌ Certificate files
- ❌ Private keys
- ❌ `bundle.json` (contains thumbprint which may be considered sensitive)

### Certificate Handling Best Practices

1. **Never print or log certificate/key contents**
   - Use file paths only
   - List filenames, not contents

2. **Verify file permissions**
   ```bash
   chmod 600 secrets/connectathon/custom/*.key  # Private keys: owner read/write only
   chmod 644 secrets/connectathon/custom/*.crt  # Certificates: owner read/write, others read
   ```

3. **Rotate certificates when**
   - Certificate approaches expiry
   - Private key may have been compromised
   - Leaving/changing teams
   - Moving from Connectathon to production

4. **Production certificates**
   - Will use a different acquisition process (not ZIP download)
   - May use secret managers (AWS Secrets Manager, K8s secrets)
   - Will have different endpoint URLs
   - Should follow stricter rotation policies

## Troubleshooting

### Certificate File Not Found

**Error:** `ENOENT: no such file or directory, open './secrets/connectathon/...`

**Solution:**
1. Verify the ZIP was extracted to the correct location
2. Check the data source ID in your `.env` matches the actual filename
3. Use absolute paths if relative paths don't work

### Certificate Permission Denied

**Error:** `EACCES: permission denied, open './secrets/connectathon/...`

**Solution:**
```bash
chmod 600 secrets/connectathon/custom/*.key
chmod 644 secrets/connectathon/custom/*.crt
chmod 644 secrets/connectathon/rootCA.crt
```

### Configuration Not Loading

**Error:** Default values being used instead of `.env` values

**Solution:**
1. Verify `.env` file exists in project root
2. Check `.env` file has no syntax errors
3. Restart the application after `.env` changes
4. Ensure no spaces around `=` in `.env` file

## References

- [Connectathon Findings](./connectathon-findings.md) - API contracts and concrete values
- [Open Questions](./open-questions.md) - Unresolved configuration questions
- [PCM-Connect Repository](https://github.com/8400TheHealthNetwork/PCM-Connect) - Public Connectathon resources
