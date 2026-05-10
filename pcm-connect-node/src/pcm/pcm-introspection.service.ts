import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as https from 'https';
import { PcmTokenService } from './pcm-token.service';
import { PcmHttpClientService } from './pcm-http-client.service';
import { PcmIntrospectionResponse } from './interfaces/pcm-introspection-response.interface';

@Injectable()
export class PcmIntrospectionService {
  private readonly logger = new Logger(PcmIntrospectionService.name);
  private readonly mode: 'pcm' | 'mock';
  private readonly baseUrl: string;
  private readonly introspectionEndpoint: string;

  constructor(
    private configService: ConfigService,
    private tokenService: PcmTokenService,
    private httpClientService: PcmHttpClientService,
  ) {
    this.mode = this.configService.get<'pcm' | 'mock'>(
      'pcm.introspectionMode',
      'pcm',
    );
    this.baseUrl = this.configService.get<string>('pcm.baseUrl', '');
    this.introspectionEndpoint = this.configService.get<string>(
      'pcm.introspectionEndpoint',
      '/introspect',
    );

    if (this.mode === 'mock') {
      this.logger.warn(
        'PCM Introspection running in MOCK mode (local demo only - NOT for production)',
      );
    }
  }

  /**
   * Introspect an opaque Service Provider token with PCM
   *
   * @param opaqueToken The opaque Service Provider token to introspect
   * @returns Introspection response with token metadata
   * @throws Error if introspection fails or token is inactive
   */
  async introspect(opaqueToken: string): Promise<PcmIntrospectionResponse> {
    if (!opaqueToken || opaqueToken.trim() === '') {
      throw new Error('Opaque token is required for introspection');
    }

    if (this.mode === 'mock') {
      return this.introspectMock(opaqueToken);
    }

    // Acquire PCM client access token
    const clientTokenResult = await this.tokenService.acquireToken();
    const clientAccessToken = clientTokenResult.access_token;

    // Build introspection request URL
    const introspectionUrl = this.baseUrl + this.introspectionEndpoint;

    // Build form body (do NOT log opaque token)
    const formBody = new URLSearchParams({
      token: opaqueToken,
    });

    // Get mTLS agent
    const agent = this.httpClientService.getAgent();

    return new Promise<PcmIntrospectionResponse>((resolve, reject) => {
      const urlObj = new URL(introspectionUrl);
      const options: https.RequestOptions = {
        method: 'POST',
        hostname: urlObj.hostname,
        port: urlObj.port || 443,
        path: urlObj.pathname,
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Content-Length': Buffer.byteLength(formBody.toString()),
          Authorization: `Bearer ${clientAccessToken}`,
        },
        agent,
      };

      const req = https.request(options, (res) => {
        let data = '';

        res.on('data', (chunk) => {
          data += chunk;
        });

        res.on('end', () => {
          if (res.statusCode === 200) {
            try {
              const response = JSON.parse(data) as PcmIntrospectionResponse;

              // Log safe metadata only (never log tokens)
              this.logger.log(
                `PCM introspection completed (active: ${response.active}, status: ${res.statusCode})`,
              );

              // Check if token is active
              if (!response.active) {
                this.logger.warn('PCM introspection returned inactive token');
                reject(
                  new Error(
                    'Token is inactive or invalid',
                  ),
                );
                return;
              }

              resolve(response);
            } catch (error) {
              this.logger.error(
                `Failed to parse PCM introspection response: ${error instanceof Error ? error.message : 'unknown error'}`,
              );
              reject(new Error('Failed to parse PCM introspection response'));
            }
          } else {
            // Do not expose raw PCM response body to prevent info leakage
            this.logger.error(
              `PCM introspection failed with status ${res.statusCode}`,
            );
            reject(
              new Error(
                `PCM introspection failed with status ${res.statusCode}`,
              ),
            );
          }
        });
      });

      req.on('error', (error) => {
        this.logger.error(`PCM introspection request error: ${error.message}`);
        reject(error);
      });

      req.write(formBody.toString());
      req.end();
    });
  }

  /**
   * Mock introspection for local demo/testing
   * Returns active response with safe demo fields
   */
  private async introspectMock(
    opaqueToken: string,
  ): Promise<PcmIntrospectionResponse> {
    this.logger.debug('Mock introspection: returning active demo response');

    // Return a valid active introspection response with demo data
    const mockResponse: PcmIntrospectionResponse = {
      active: true,
      patient: '000000018',
      scope: 'patient/Observation.rs patient/Condition.rs',
      client_id: 'mock-service-provider',
      consent_id: 'mock-consent-12345',
      baskets: ['mock-basket-1'],
      access_type: 'continuous',
      sp_organization_id: 'mock-sp-org-123',
      intent: 'treatment',
      aud: 'https://fhir.internal.example.com',
      iss: 'https://pcm-mock',
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 300,
      jti: 'mock-jti-' + Date.now(),
    };

    return mockResponse;
  }
}
