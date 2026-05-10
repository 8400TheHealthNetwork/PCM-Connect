import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SignJWT, importPKCS8, type KeyLike } from 'jose';
import { readFile } from 'fs/promises';
import { randomUUID, createPrivateKey } from 'crypto';
import { ClientAssertionPayload } from './interfaces/client-assertion-payload.interface';

@Injectable()
export class PcmClientAssertionService implements OnModuleInit {
  private readonly logger = new Logger(PcmClientAssertionService.name);
  private privateKey: KeyLike | null = null;
  private readonly clientId: string;
  private readonly audience: string;
  private readonly privateKeyPath: string;
  private readonly algorithm: 'ES256' | 'RS256';

  constructor(private configService: ConfigService) {
    this.clientId = this.configService.get<string>('pcm.clientId', '');
    this.audience = this.configService.get<string>(
      'pcm.clientAssertion.audience',
      '',
    );
    this.privateKeyPath = this.configService.get<string>(
      'pcm.clientAssertion.privateKeyPath',
      '',
    );
    this.algorithm = this.configService.get<'ES256' | 'RS256'>(
      'pcm.clientAssertion.algorithm',
      'ES256',
    );
  }

  async onModuleInit() {
    if (!this.privateKeyPath) {
      this.logger.warn(
        'PCM client assertion private key path not configured - token acquisition will fail',
      );
      return;
    }

    try {
      await this.loadPrivateKey();
      this.logger.log('PCM client assertion service initialized');
    } catch (error) {
      this.logger.error(
        `Failed to load client assertion private key: ${error instanceof Error ? error.message : 'unknown error'}`,
      );
    }
  }

  /**
   * Load private key for client assertion signing and validate compatibility
   */
  private async loadPrivateKey(): Promise<void> {
    if (!this.privateKeyPath) {
      throw new Error('Client assertion private key path not configured');
    }

    const keyData = await readFile(this.privateKeyPath, 'utf-8');

    // Validate key type compatibility before importing
    try {
      const keyObject = createPrivateKey(keyData);
      const keyType = keyObject.asymmetricKeyType;

      // Check algorithm compatibility
      if (this.algorithm === 'ES256' && keyType !== 'ec') {
        throw new Error(
          `Algorithm ES256 requires EC key, but key type is ${keyType}. ` +
          `Set PCM_CLIENT_ASSERTION_ALGORITHM=RS256 or use an EC P-256 key.`,
        );
      }

      if (this.algorithm === 'RS256' && keyType !== 'rsa') {
        throw new Error(
          `Algorithm RS256 requires RSA key, but key type is ${keyType}. ` +
          `Set PCM_CLIENT_ASSERTION_ALGORITHM=ES256 or use an RSA key.`,
        );
      }

      // For EC keys, validate curve
      if (keyType === 'ec' && this.algorithm === 'ES256') {
        const jwk = keyObject.export({ format: 'jwk' }) as any;
        if (jwk.crv && jwk.crv !== 'P-256') {
          throw new Error(
            `Algorithm ES256 requires P-256 curve, but key uses ${jwk.crv}.`,
          );
        }
      }

      this.logger.log(
        `Validated key compatibility: ${keyType} key with ${this.algorithm} algorithm`,
      );
    } catch (error) {
      if (error instanceof Error && error.message.includes('Algorithm')) {
        throw error; // Re-throw our validation errors
      }
      throw new Error(`Failed to validate key: ${error instanceof Error ? error.message : 'unknown error'}`);
    }

    // Import key with configured algorithm
    this.privateKey = await importPKCS8(keyData, this.algorithm);
  }

  /**
   * Create and sign a client assertion JWT for PCM token request
   *
   * @returns Signed JWT string
   * @throws Error if private key not loaded
   */
  async createClientAssertion(): Promise<string> {
    if (!this.privateKey) {
      throw new Error(
        'Client assertion private key not loaded - cannot create client assertion',
      );
    }

    const now = Math.floor(Date.now() / 1000);
    const exp = now + 60; // 60 seconds expiry

    const payload: ClientAssertionPayload = {
      iss: this.clientId,
      sub: this.clientId,
      aud: this.audience,
      iat: now,
      exp,
      jti: randomUUID(),
    };

    try {
      const jwt = await new SignJWT(payload as any)
        .setProtectedHeader({ alg: this.algorithm, typ: 'JWT' })
        .setIssuedAt(now)
        .setExpirationTime(exp)
        .setIssuer(this.clientId)
        .setSubject(this.clientId)
        .setAudience(this.audience)
        .setJti(payload.jti)
        .sign(this.privateKey);

      // Do NOT log the JWT
      this.logger.debug(`Client assertion created successfully using ${this.algorithm}`);
      return jwt;
    } catch (error) {
      this.logger.error(
        `Failed to sign client assertion with ${this.algorithm}: ${error instanceof Error ? error.message : 'unknown error'}`,
      );
      throw new Error(`Failed to create client assertion: ${error instanceof Error ? error.message : 'signing failed'}`);
    }
  }

  /**
   * Set a mock private key for testing purposes
   * @internal Use only in tests
   */
  setMockPrivateKey(key: KeyLike): void {
    this.privateKey = key;
  }
}
