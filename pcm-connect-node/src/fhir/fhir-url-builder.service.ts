import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class FhirUrlBuilderService {
  private readonly fhirBaseUrl: string;
  private readonly patientReferenceFormat: 'bare' | 'full';
  private readonly securityLabelSystem: string;
  private readonly securityLabelCode: string;

  constructor(private configService: ConfigService) {
    this.fhirBaseUrl = this.configService.get<string>(
      'fhir.baseUrl',
      'https://fhir.internal.example.com',
    );
    this.patientReferenceFormat = this.configService.get<'bare' | 'full'>(
      'fhir.patientReferenceFormat',
      'bare',
    );
    this.securityLabelSystem = this.configService.get<string>(
      'responseVerification.forbiddenLabels.0.system',
      'http://fhir.health.gov.il/cs/il-core-main-security-label',
    );
    this.securityLabelCode = this.configService.get<string>(
      'responseVerification.forbiddenLabels.0.code',
      'V',
    );
  }

  /**
   * Build FHIR URL with patient and security exclusion injected
   *
   * @param path FHIR path (e.g., /Observation)
   * @param queryParams Original query parameters from request
   * @param localPatientId Local patient ID to inject
   * @returns Complete FHIR URL with injected parameters
   */
  buildUrl(
    path: string,
    queryParams: URLSearchParams,
    localPatientId: string,
  ): string {
    // Start with base URL and path
    const url = new URL(path, this.fhirBaseUrl);

    // Copy existing query parameters
    for (const [key, value] of queryParams.entries()) {
      url.searchParams.append(key, value);
    }

    // Inject patient parameter if not already present
    if (!url.searchParams.has('patient')) {
      const patientValue =
        this.patientReferenceFormat === 'full'
          ? `Patient/${localPatientId}`
          : localPatientId;
      url.searchParams.set('patient', patientValue);
    }

    // Inject V-label exclusion if not already present
    const securityNotParam = `${this.securityLabelSystem}|${this.securityLabelCode}`;
    if (!url.searchParams.has('_security:not')) {
      url.searchParams.set('_security:not', securityNotParam);
    }

    return url.toString();
  }
}
