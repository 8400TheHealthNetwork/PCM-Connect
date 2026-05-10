/**
 * ID Replacement response
 * Response from ID Replacement service
 */
export interface IdReplacementResponse {
  localPatientId: string; // Bare local patient ID (e.g., "12345")
  resourceReference: string; // Full FHIR reference (e.g., "Patient/12345")
}
