export type AuditEventType =
  | 'http_request'
  | 'pcm_token_acquired'
  | 'pcm_introspection'
  | 'id_replacement'
  | 'jwt_minted'
  | 'fhir_request'
  | 'fhir_response'
  | 'security_violation'
  | 'authentication_failure'
  | 'authorization_failure'
  | 'error';

export type AuditOutcome = 'success' | 'failure' | 'warning';

export interface AuditEvent {
  timestamp: string; // ISO 8601
  correlationId: string;
  eventType: AuditEventType;
  outcome: AuditOutcome;
  httpMethod?: string;
  path?: string;
  statusCode?: number;
  durationMs?: number;
  serviceProviderId?: string;
  patientIdMasked?: string;
  errorCode?: string;
  details?: Record<string, any>; // No PHI, no response bodies
}
