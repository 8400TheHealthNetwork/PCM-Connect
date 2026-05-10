/**
 * PCM Introspection Response (RFC 7662 + PCM extensions)
 * Response from PCM when introspecting an opaque Service Provider token
 */
export interface PcmIntrospectionResponse {
  // RFC 7662 standard fields
  active: boolean;
  scope?: string;
  client_id?: string;
  token_type?: string;
  exp?: number;
  iat?: number;
  nbf?: number;
  sub?: string;
  aud?: string;
  iss?: string;
  jti?: string;

  // PCM-specific fields
  patient?: string; // National ID or identifier
  consent_id?: string;
  baskets?: string[]; // Array of basket identifiers
  access_type?: string;
  sp_organization_id?: string;
  intent?: string;
  cnf?: {
    'x5t#S256'?: string; // Certificate thumbprint for DPoP
  };

  // Allow additional unknown fields
  [key: string]: any;
}
