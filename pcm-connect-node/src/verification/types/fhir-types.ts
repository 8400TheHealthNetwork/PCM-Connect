/**
 * Minimal FHIR R4 types for response verification
 * These are NOT a complete FHIR SDK - only what's needed for security label checking
 */

export interface FhirCoding {
  system?: string;
  code?: string;
  display?: string;
}

export interface FhirMeta {
  security?: FhirCoding[];
  [key: string]: any; // Other meta fields we don't inspect
}

export interface FhirResource {
  resourceType: string;
  meta?: FhirMeta;
  [key: string]: any; // Resource fields we don't inspect
}

export interface FhirBundleEntry {
  resource?: FhirResource;
  [key: string]: any; // Other entry fields we don't inspect
}

export interface FhirBundle extends FhirResource {
  resourceType: 'Bundle';
  type?: string;
  entry?: FhirBundleEntry[];
}

/**
 * Type guard to check if response is a FHIR Bundle
 */
export function isFhirBundle(data: any): data is FhirBundle {
  return (
    data &&
    typeof data === 'object' &&
    data.resourceType === 'Bundle' &&
    (data.entry === undefined || Array.isArray(data.entry))
  );
}

/**
 * Type guard to check if response is a FHIR Resource
 */
export function isFhirResource(data: any): data is FhirResource {
  return (
    data &&
    typeof data === 'object' &&
    typeof data.resourceType === 'string'
  );
}
