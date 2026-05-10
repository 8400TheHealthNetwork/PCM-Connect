import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class FhirForwardService {
  private readonly logger = new Logger(FhirForwardService.name);
  private readonly mode: 'mock' | 'http';
  private readonly fhirBaseUrl: string;
  private readonly timeoutMs: number;

  constructor(private configService: ConfigService) {
    this.mode = this.configService.get<'mock' | 'http'>(
      'fhir.forwardingMode',
      'mock',
    );
    this.fhirBaseUrl = this.configService.get<string>(
      'fhir.baseUrl',
      'https://fhir.internal.example.com',
    );
    this.timeoutMs = this.configService.get<number>('fhir.timeoutMs', 30000);

    if (this.mode === 'mock') {
      this.logger.log(
        'FHIR Forwarding running in MOCK mode (local demo only)',
      );
    } else {
      this.logger.log(
        `FHIR Forwarding configured for HTTP mode (endpoint: ${this.fhirBaseUrl})`,
      );
    }
  }

  /**
   * Forward request to FHIR server
   *
   * @param url Full FHIR URL with query parameters
   * @param internalJwt Internal JWT for authentication
   * @param correlationId Correlation ID for tracking
   * @returns FHIR Bundle or resource
   */
  async forward(
    url: string,
    internalJwt: string,
    correlationId: string,
  ): Promise<any> {
    this.logger.debug(
      `Forwarding request to FHIR (correlation: ${correlationId})`,
    );

    if (this.mode === 'mock') {
      return this.forwardMock(url, correlationId);
    } else {
      return this.forwardHttp(url, internalJwt, correlationId);
    }
  }

  /**
   * Mock mode: return minimal valid FHIR Bundle
   */
  private async forwardMock(
    url: string,
    correlationId: string,
  ): Promise<any> {
    this.logger.debug(`Mock mode: returning minimal FHIR Bundle`);

    // Extract resource type from URL
    const urlObj = new URL(url);
    const pathParts = urlObj.pathname.split('/').filter((p) => p);
    const resourceType = pathParts[pathParts.length - 1] || 'Observation';

    // Return minimal valid FHIR R4 searchset Bundle
    return {
      resourceType: 'Bundle',
      type: 'searchset',
      total: 2,
      link: [
        {
          relation: 'self',
          url: url,
        },
      ],
      entry: [
        {
          fullUrl: `${this.fhirBaseUrl}/${resourceType}/mock-1`,
          resource: {
            resourceType,
            id: 'mock-1',
            meta: {
              versionId: '1',
              lastUpdated: new Date().toISOString(),
            },
            text: {
              status: 'generated',
              div: '<div xmlns="http://www.w3.org/1999/xhtml">Mock resource 1</div>',
            },
          },
        },
        {
          fullUrl: `${this.fhirBaseUrl}/${resourceType}/mock-2`,
          resource: {
            resourceType,
            id: 'mock-2',
            meta: {
              versionId: '1',
              lastUpdated: new Date().toISOString(),
            },
            text: {
              status: 'generated',
              div: '<div xmlns="http://www.w3.org/1999/xhtml">Mock resource 2</div>',
            },
          },
        },
      ],
    };
  }

  /**
   * HTTP mode: forward to real FHIR server
   * Structure prepared but not fully implemented for V1
   */
  private async forwardHttp(
    url: string,
    internalJwt: string,
    correlationId: string,
  ): Promise<any> {
    // TODO: Implement real HTTP forwarding when FHIR server available
    throw new Error(
      'FHIR HTTP forwarding not yet implemented - use mock mode for V1',
    );
  }
}
