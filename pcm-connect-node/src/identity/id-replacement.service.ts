import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { IdReplacementRequest } from './interfaces/id-replacement-request.interface';
import { IdReplacementResponse } from './interfaces/id-replacement-response.interface';

@Injectable()
export class IdReplacementService {
  private readonly logger = new Logger(IdReplacementService.name);
  private readonly mode: 'mock' | 'http';
  private readonly baseUrl: string;
  private readonly endpoint: string;
  private readonly timeout: number;

  constructor(private configService: ConfigService) {
    this.mode = this.configService.get<'mock' | 'http'>(
      'idReplacement.mode',
      'mock',
    );
    this.baseUrl = this.configService.get<string>(
      'idReplacement.baseUrl',
      '',
    );
    this.endpoint = this.configService.get<string>(
      'idReplacement.endpoint',
      '/api/v1/resolve',
    );
    this.timeout = this.configService.get<number>(
      'idReplacement.timeoutMs',
      5000,
    );

    if (this.mode === 'mock') {
      this.logger.log(
        'ID Replacement running in MOCK mode (local demo only)',
      );
    } else {
      this.logger.log(
        `ID Replacement configured for HTTP mode (endpoint: ${this.baseUrl}${this.endpoint})`,
      );
    }
  }

  /**
   * Resolve national ID to local patient ID
   *
   * @param request ID replacement request
   * @returns Local patient ID and resource reference
   */
  async resolve(
    request: IdReplacementRequest,
  ): Promise<IdReplacementResponse> {
    // Mask patient identifier for logging (last 4 digits only)
    const maskedIdentifier =
      request.identifierValue.length > 4
        ? '****' + request.identifierValue.slice(-4)
        : '****';

    this.logger.debug(
      `Resolving patient identifier (masked: ${maskedIdentifier})`,
    );

    if (this.mode === 'mock') {
      return this.resolveMock(request);
    } else {
      return this.resolveHttp(request);
    }
  }

  /**
   * Mock mode: generate deterministic local patient ID
   */
  private async resolveMock(
    request: IdReplacementRequest,
  ): Promise<IdReplacementResponse> {
    // Generate deterministic mock patient ID from last 4 chars
    const last4 =
      request.identifierValue.length >= 4
        ? request.identifierValue.slice(-4)
        : request.identifierValue.padStart(4, '0');

    const localPatientId = `mock-patient-${last4}`;
    const resourceReference = `Patient/${localPatientId}`;

    this.logger.debug(
      `Mock mode resolved to: ${resourceReference}`,
    );

    return {
      localPatientId,
      resourceReference,
    };
  }

  /**
   * HTTP mode: call real ID Replacement service
   * Structure prepared but network call mocked for V1
   */
  private async resolveHttp(
    request: IdReplacementRequest,
  ): Promise<IdReplacementResponse> {
    // TODO: Implement real HTTP call when service available
    // For V1, throw error if HTTP mode is configured but not implemented
    throw new Error(
      'ID Replacement HTTP mode not yet implemented - use mock mode for V1',
    );
  }
}
