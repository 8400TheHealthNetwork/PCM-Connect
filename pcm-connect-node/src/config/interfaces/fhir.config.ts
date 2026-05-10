export interface FhirConfig {
  forwardingMode: 'mock' | 'http';
  baseUrl: string;
  patientReferenceFormat: 'bare' | 'full';
  patientIdentifierSystem: string;
  timeoutMs: number;
}
