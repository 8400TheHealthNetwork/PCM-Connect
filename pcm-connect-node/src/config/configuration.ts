import { AppConfig } from './interfaces/app.config';

export default (): AppConfig => ({
  server: {
    port: parseInt(process.env.PORT || '3009', 10),
    nodeEnv: process.env.NODE_ENV || 'development',
  },
  dataSource: {
    id: process.env.DATA_SOURCE_ID || 'data-source-org-id',
    endpoint: process.env.DATA_SOURCE_ENDPOINT || 'https://data-source.example.com',
  },
  pcm: {
    introspectionMode: (process.env.PCM_INTROSPECTION_MODE === 'mock' ? 'mock' : 'pcm') as 'pcm' | 'mock',
    baseUrl: process.env.PCM_BASE_URL || 'https://pcm.example.com',
    tokenEndpoint: process.env.PCM_TOKEN_ENDPOINT || '/token',
    introspectionEndpoint:
      process.env.PCM_INTROSPECTION_ENDPOINT || '/introspect',
    metadataEndpoint:
      process.env.PCM_METADATA_ENDPOINT || 'https://pcm.example.com/.well-known/oauth-authorization-server',
    clientId: process.env.PCM_CLIENT_ID || process.env.DATA_SOURCE_ENDPOINT || 'https://data-source.example.com',
    clientCertThumbprint: process.env.PCM_CLIENT_CERT_THUMBPRINT || '',
    resource: process.env.PCM_RESOURCE || undefined,
    clientTokenCacheEnabled:
      process.env.PCM_CLIENT_TOKEN_CACHE_ENABLED === 'true' || false,
    clientTokenCacheSafetyMarginSeconds: parseInt(
      process.env.PCM_CLIENT_TOKEN_CACHE_SAFETY_MARGIN_SECONDS || '5',
      10,
    ),
    mtls: {
      certPath: process.env.PCM_MTLS_CERT_PATH || '',
      keyPath: process.env.PCM_MTLS_KEY_PATH || '',
      caCertPath: process.env.PCM_CA_CERT_PATH || '',
      tlsServername: process.env.PCM_TLS_SERVERNAME || undefined,
    },
    clientAssertion: {
      privateKeyPath: process.env.PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH || '',
      audience: process.env.PCM_CLIENT_ASSERTION_AUDIENCE ||
        (process.env.PCM_BASE_URL || 'https://pcm.example.com') + (process.env.PCM_TOKEN_ENDPOINT || '/token'),
      algorithm: (process.env.PCM_CLIENT_ASSERTION_ALGORITHM === 'RS256' ? 'RS256' : 'ES256') as 'ES256' | 'RS256',
    },
  },
  fhir: {
    forwardingMode: (process.env.FHIR_FORWARDING_MODE === 'http' ? 'http' : 'mock') as 'mock' | 'http',
    baseUrl: process.env.FHIR_BASE_URL || 'https://fhir.internal.example.com',
    patientReferenceFormat:
      (process.env.FHIR_PATIENT_REFERENCE_FORMAT as 'bare' | 'full') || 'bare',
    patientIdentifierSystem:
      process.env.FHIR_PATIENT_IDENTIFIER_SYSTEM ||
      'http://fhir.health.gov.il/identifier/israeli-id',
    timeoutMs: parseInt(process.env.FHIR_TIMEOUT_MS || '30000', 10),
  },
  idReplacement: {
    mode: (process.env.ID_REPLACEMENT_MODE === 'http' ? 'http' : 'mock') as 'mock' | 'http',
    baseUrl:
      process.env.ID_REPLACEMENT_BASE_URL ||
      'https://id-swap.internal.example.com',
    endpoint: process.env.ID_REPLACEMENT_ENDPOINT || '/api/v1/resolve',
    timeoutMs: parseInt(process.env.ID_REPLACEMENT_TIMEOUT_MS || '5000', 10),
  },
  jwt: {
    issuer: process.env.JWT_ISSUER || 'data-source-org-id',
    audience:
      process.env.JWT_AUDIENCE || 'https://fhir.internal.example.com',
    expirySeconds: parseInt(process.env.JWT_EXPIRY_SECONDS || '60', 10),
    signingKeyPath: process.env.JWT_SIGNING_KEY_PATH || '',
    algorithm: (process.env.JWT_ALGORITHM === 'ES256' ? 'ES256' : 'RS256') as 'ES256' | 'RS256',
  },
  responseVerification: {
    enabled: process.env.RESPONSE_VERIFICATION_ENABLED !== 'false',
    forbiddenLabels: [
      {
        system:
          process.env.FORBIDDEN_SECURITY_LABEL_SYSTEM ||
          'http://fhir.health.gov.il/cs/il-core-main-security-label',
        code: process.env.FORBIDDEN_SECURITY_LABEL_CODE || 'V',
      },
    ],
  },
  audit: {
    enabled: process.env.AUDIT_ENABLED !== 'false',
  },
});
