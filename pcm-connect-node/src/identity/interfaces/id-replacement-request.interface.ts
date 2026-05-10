/**
 * ID Replacement request
 * Request to resolve national ID to local patient ID
 */
export interface IdReplacementRequest {
  identifierSystem: string; // e.g., http://fhir.health.gov.il/identifier/il-national-id
  identifierValue: string; // e.g., national ID
}
