import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as https from 'https';
import { PcmClientAssertionService } from './pcm-client-assertion.service';
import { PcmHttpClientService } from './pcm-http-client.service';
import {
  PcmTokenResponse,
  CachedToken,
} from './interfaces/pcm-token-response.interface';

@Injectable()
export class PcmTokenService {
  private readonly logger = new Logger(PcmTokenService.name);
  private readonly baseUrl: string;
  private readonly tokenEndpoint: string;
  private readonly resource?: string;
  private readonly cacheEnabled: boolean;
  private readonly cacheSafetyMarginSeconds: number;
  private cachedToken: CachedToken | null = null;

  constructor(
    private configService: ConfigService,
    private clientAssertionService: PcmClientAssertionService,
    private httpClientService: PcmHttpClientService,
  ) {
    this.baseUrl = this.configService.get<string>('pcm.baseUrl', '');
    this.tokenEndpoint = this.configService.get<string>(
      'pcm.tokenEndpoint',
      '/token',
    );
    this.resource = this.configService.get<string>('pcm.resource');
    this.cacheEnabled = this.configService.get<boolean>(
      'pcm.clientTokenCacheEnabled',
      false,
    );
    this.cacheSafetyMarginSeconds = this.configService.get<number>(
      'pcm.clientTokenCacheSafetyMarginSeconds',
      5,
    );
  }

  /**
   * Acquire an access token from PCM
   * Uses cache if enabled and token is still valid
   *
   * @returns Object with access_token and metadata
   */
  async acquireToken(): Promise<{
    access_token: string;
    token_type: string;
    expires_in: number;
    from_cache: boolean;
  }> {
    // Check cache first
    if (this.cacheEnabled && this.cachedToken) {
      const now = Math.floor(Date.now() / 1000);
      const expiresWithSafety =
        this.cachedToken.expires_at - this.cacheSafetyMarginSeconds;

      if (now < expiresWithSafety) {
        const remainingSeconds = this.cachedToken.expires_at - now;
        this.logger.debug(
          `Using cached PCM token (expires in ${remainingSeconds}s)`,
        );
        return {
          access_token: this.cachedToken.access_token,
          token_type: this.cachedToken.token_type,
          expires_in: remainingSeconds,
          from_cache: true,
        };
      }

      this.logger.debug('Cached token expired or approaching expiry');
      this.cachedToken = null;
    }

    // Request new token
    const tokenResponse = await this.requestToken();

    // Cache token if caching is enabled
    if (this.cacheEnabled) {
      const now = Math.floor(Date.now() / 1000);
      this.cachedToken = {
        access_token: tokenResponse.access_token,
        token_type: tokenResponse.token_type,
        expires_at: now + tokenResponse.expires_in,
      };
      this.logger.debug(
        `Cached PCM token (expires in ${tokenResponse.expires_in}s)`,
      );
    }

    return {
      ...tokenResponse,
      from_cache: false,
    };
  }

  /**
   * Request a new token from PCM
   */
  private async requestToken(): Promise<PcmTokenResponse> {
    // Create client assertion
    const clientAssertion =
      await this.clientAssertionService.createClientAssertion();

    // Build token request URL
    const tokenUrl = this.baseUrl + this.tokenEndpoint;

    // Build form body
    const formParams: Record<string, string> = {
      grant_type: 'client_credentials',
      client_assertion_type:
        'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
      client_assertion: clientAssertion,
    };

    // Add resource parameter if configured (RFC 8707)
    if (this.resource) {
      formParams.resource = this.resource;
    }

    const formBody = new URLSearchParams(formParams);

    // Get mTLS agent
    const agent = this.httpClientService.getAgent();

    return new Promise<PcmTokenResponse>((resolve, reject) => {
      const urlObj = new URL(tokenUrl);
      const options: https.RequestOptions = {
        method: 'POST',
        hostname: urlObj.hostname,
        port: urlObj.port || 443,
        path: urlObj.pathname,
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Content-Length': Buffer.byteLength(formBody.toString()),
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
              const response = JSON.parse(data) as PcmTokenResponse;

              // Log safe metadata only (never log token value)
              this.logger.log(
                `PCM token acquired successfully (type: ${response.token_type}, expires_in: ${response.expires_in}s, token_length: ${response.access_token.length})`,
              );

              resolve(response);
            } catch (error) {
              this.logger.error(
                `Failed to parse PCM token response: ${error instanceof Error ? error.message : 'unknown error'}`,
              );
              reject(new Error('Failed to parse PCM token response'));
            }
          } else {
            this.logger.error(
              `PCM token request failed with status ${res.statusCode}: ${data.substring(0, 200)}`,
            );
            reject(
              new Error(`PCM token request failed with status ${res.statusCode}`),
            );
          }
        });
      });

      req.on('error', (error) => {
        this.logger.error(
          `PCM token request error: ${error.message}`,
        );
        reject(error);
      });

      req.write(formBody.toString());
      req.end();
    });
  }

  /**
   * Clear cached token (for testing or forced refresh)
   */
  clearCache(): void {
    this.cachedToken = null;
    this.logger.debug('PCM token cache cleared');
  }
}
