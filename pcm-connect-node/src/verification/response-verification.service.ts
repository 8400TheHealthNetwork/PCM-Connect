import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SecurityError } from '../common';
import {
  FhirBundle,
  FhirResource,
  FhirCoding,
  isFhirBundle,
  isFhirResource,
} from './types/fhir-types';

export interface ForbiddenLabel {
  system: string;
  code: string;
}

export interface VerificationResult {
  passed: boolean;
  forbiddenLabelFound?: ForbiddenLabel;
  resourceType?: string;
  entryIndex?: number;
}

@Injectable()
export class ResponseVerificationService {
  private readonly logger = new Logger(ResponseVerificationService.name);
  private readonly enabled: boolean;
  private readonly forbiddenLabels: ForbiddenLabel[];

  constructor(private configService: ConfigService) {
    this.enabled = this.configService.get<boolean>(
      'responseVerification.enabled',
      true,
    );

    const configuredLabels = this.configService.get<ForbiddenLabel[]>(
      'responseVerification.forbiddenLabels',
      [],
    );

    this.forbiddenLabels = configuredLabels;

    if (!this.enabled) {
      this.logger.warn('Response verification is DISABLED via configuration');
    } else {
      this.logger.log(
        `Response verification enabled with ${this.forbiddenLabels.length} forbidden label(s)`,
      );
    }
  }

  /**
   * Verify a FHIR response does not contain forbidden security labels
   *
   * V1 Assumptions:
   * - Input is JSON (already parsed)
   * - If not FHIR-like structure, pass as clean (don't crash on non-FHIR responses)
   * - Only check top-level resource and Bundle entries
   * - Do NOT check contained resources in V1 (documented limitation)
   *
   * @throws SecurityError if forbidden label found
   */
  verify(response: any): VerificationResult {
    // If disabled, always pass
    if (!this.enabled) {
      return { passed: true };
    }

    // V1 Assumption: If response is not an object or is null, pass as clean
    // This handles non-JSON responses gracefully
    if (!response || typeof response !== 'object') {
      this.logger.debug('Response is not an object, passing as clean');
      return { passed: true };
    }

    // Check if it's a FHIR Bundle
    if (isFhirBundle(response)) {
      return this.verifyBundle(response);
    }

    // Check if it's a single FHIR Resource
    if (isFhirResource(response)) {
      return this.verifyResource(response);
    }

    // V1 Assumption: Non-FHIR responses pass as clean
    // We don't want to block valid responses that happen to not be FHIR
    this.logger.debug('Response is not FHIR structure, passing as clean');
    return { passed: true };
  }

  /**
   * Verify a FHIR Bundle
   */
  private verifyBundle(bundle: FhirBundle): VerificationResult {
    // Check bundle itself first (rare but possible)
    const bundleCheck = this.checkResourceSecurity(bundle);
    if (!bundleCheck.passed) {
      this.logger.warn(
        `Forbidden security label found in Bundle resource itself`,
      );
      return bundleCheck;
    }

    // Check each entry
    if (bundle.entry && Array.isArray(bundle.entry)) {
      for (let i = 0; i < bundle.entry.length; i++) {
        const entry = bundle.entry[i];
        if (entry.resource) {
          const result = this.checkResourceSecurity(entry.resource);
          if (!result.passed) {
            this.logger.warn(
              `Forbidden security label found in Bundle entry ${i}, resourceType: ${entry.resource.resourceType}`,
            );
            return {
              ...result,
              entryIndex: i,
            };
          }
        }
      }
    }

    return { passed: true };
  }

  /**
   * Verify a single FHIR Resource
   */
  private verifyResource(resource: FhirResource): VerificationResult {
    return this.checkResourceSecurity(resource);
  }

  /**
   * Check a single resource's meta.security for forbidden labels
   *
   * V1 Limitation: Does NOT check contained resources
   * Future enhancement: Add recursive check for resource.contained[]
   */
  private checkResourceSecurity(
    resource: FhirResource,
  ): VerificationResult {
    // If no meta or no security, pass
    if (!resource.meta || !resource.meta.security) {
      return { passed: true };
    }

    const securityLabels = resource.meta.security;
    if (!Array.isArray(securityLabels)) {
      this.logger.warn('meta.security is not an array, passing as clean');
      return { passed: true };
    }

    // Check each security label
    for (const label of securityLabels) {
      if (this.isForbiddenLabel(label)) {
        return {
          passed: false,
          forbiddenLabelFound: {
            system: label.system || '',
            code: label.code || '',
          },
          resourceType: resource.resourceType,
        };
      }
    }

    return { passed: true };
  }

  /**
   * Check if a coding matches any forbidden label
   */
  private isForbiddenLabel(coding: FhirCoding): boolean {
    if (!coding.system || !coding.code) {
      return false;
    }

    return this.forbiddenLabels.some(
      (forbidden) =>
        forbidden.system === coding.system && forbidden.code === coding.code,
    );
  }

  /**
   * Verify and throw if forbidden label found
   * Convenience method for use in request handlers
   *
   * @throws SecurityError if forbidden label found
   */
  verifyOrThrow(response: any): void {
    const result = this.verify(response);

    if (!result.passed) {
      // Throw SecurityError with internal details
      // The error message contains details for logging/audit
      // but getClientMessage() will return generic message
      const details = `Forbidden security label detected: ${result.forbiddenLabelFound?.system}|${result.forbiddenLabelFound?.code} in ${result.resourceType || 'unknown'}${result.entryIndex !== undefined ? ` at entry ${result.entryIndex}` : ''}`;

      throw new SecurityError(details, 'suppressed');
    }
  }
}
