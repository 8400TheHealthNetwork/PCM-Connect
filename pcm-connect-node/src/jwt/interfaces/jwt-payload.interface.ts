/**
 * Input for creating an internal JWT
 */
export interface CreateJwtInput {
  serviceProviderId: string; // Subject (sub) - who is requesting
  localPatientId: string; // Patient context
  scope: string; // Space-separated scopes from PCM
  correlationId?: string; // Optional request correlation ID
}

/**
 * JWT payload claims for internal FHIR server authentication
 */
export interface InternalJwtPayload {
  iss: string; // Issuer - this adapter
  sub: string; // Subject - service provider ID
  aud: string; // Audience - internal FHIR server
  patient: string; // Patient context (local ID)
  scope: string; // Space-separated scopes
  iat: number; // Issued at (Unix timestamp)
  exp: number; // Expires at (Unix timestamp)
  correlation_id?: string; // Optional request tracking
}
