# PCM Introspection Testing

## Overview

The adapter's `PcmIntrospectionService` validates opaque Service Provider tokens by introspecting them with PCM. This document explains how to test introspection locally.

## What is an Opaque Service Provider Token?

The opaque token is issued by PCM to a **Service Provider** (e.g., a medical portal or application) after the patient grants consent. When the Service Provider makes a request to the Data Source adapter, it includes this opaque token. The adapter must introspect this token with PCM to:

1. Verify the token is active
2. Extract patient identifier
3. Retrieve consent ID and authorization scope
4. Check baskets and access permissions

**Important:** The opaque token is NOT the same as:
- The adapter's client token (from `npm run pcm:token:check`)
- The client assertion JWT
- Internal JWT tokens

## Obtaining a Service Provider Token for Testing

### Option 1: PCM Admin UI (if available)

If PCM provides a test token generation feature:

1. Log into PCM Admin UI
2. Navigate to Service Provider registration
3. Look for "Generate Test Token" or similar feature
4. Copy the generated opaque token

### Option 2: Postman/Curl Service Provider Flow (if documented)

If Connectathon documents the Service Provider OAuth flow:

1. Register as a Service Provider in PCM Admin
2. Obtain Service Provider credentials
3. Use Postman/curl to perform OAuth flow
4. Extract opaque token from response

### Option 3: Request from PCM Team

Contact PCM team or Connectathon organizers to:
- Provide sample/mock Service Provider tokens
- Document the Service Provider token acquisition flow
- Confirm if Data Source adapters can test introspection without a real Service Provider

### Option 4: Use Connectathon Sample Tokens (if provided)

Check Connectathon documentation for:
- Example opaque tokens for testing
- Test Service Provider credentials
- Mock token endpoints

## Testing Introspection Locally

Once you have a valid opaque Service Provider token:

```bash
# Set the opaque token in environment
export PCM_OPAQUE_TOKEN="<your-opaque-token>"

# Run introspection check
npm run pcm:introspect:check
```

**Expected output (success):**

```
PCM Introspection Check
=======================

Opaque Token:    Provided (not displayed for security)
Token Length:    36 characters

Introspecting token with PCM...

✓ SUCCESS
─────────────────────────────
Active:          true
Client ID:       org-hospital-a
Patient:         ****0018
Scope Count:     2 permissions
Consent ID:      consent-12345
Baskets:         1 basket(s)
Access Type:     continuous
SP Org ID:       org-sp-123
Expires In:      25 seconds
Audience:        https://fhir.internal.example.com
Issuer:          https://pcm-core:3000
Fields Present:  client_id, patient, scope, consent_id, baskets, ...
─────────────────────────────
```

## Security Notes

- The script **never prints** the opaque token value
- The script **never prints** the adapter's client access token
- Only safe metadata is displayed (masked patient, field counts, etc.)
- Patient ID is masked to show only last 4 characters

## Current Status

**Implemented:**
- ✅ `PcmIntrospectionService` - introspects tokens with PCM
- ✅ `npm run pcm:introspect:check` - safe local testing script
- ✅ Unit tests for introspection service

**Pending:**
- ⏳ Documentation on how to obtain Service Provider opaque token
- ⏳ Confirmation from PCM team on testing approach

## Next Steps

1. Contact PCM team / Connectathon organizers for guidance on obtaining Service Provider tokens
2. Update this document with specific instructions once available
3. Test introspection with real token from PCM
4. Verify all introspection response fields are correctly parsed
