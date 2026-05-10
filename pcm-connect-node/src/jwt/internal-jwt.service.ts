import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { SignJWT, importPKCS8, type KeyLike } from 'jose';
import { readFile } from 'fs/promises';
import { CreateJwtInput, InternalJwtPayload } from './interfaces/jwt-payload.interface';

@Injectable()
export class InternalJwtService implements OnModuleInit {
  private readonly logger = new Logger(InternalJwtService.name);
  private privateKey: KeyLike | null = null;
  private readonly issuer: string;
  private readonly audience: string;
  private readonly expirySeconds: number;
  private readonly signingKeyPath: string;
  private readonly algorithm: 'ES256' | 'RS256';

  constructor(private configService: ConfigService) {
    this.issuer = this.configService.get<string>('jwt.issuer', 'pcm-adapter');
    this.audience = this.configService.get<string>(
      'jwt.audience',
      'https://fhir.internal.example.com',
    );
    this.expirySeconds = this.configService.get<number>(
      'jwt.expirySeconds',
      60,
    );
    this.signingKeyPath = this.configService.get<string>(
      'jwt.signingKeyPath',
      '',
    );
    this.algorithm = this.configService.get<'ES256' | 'RS256'>(
      'jwt.algorithm',
      'RS256',
    );
  }

  async onModuleInit() {
    if (!this.signingKeyPath) {
      this.logger.log(
        `Internal JWT service initialized without signing key (issuer: ${this.issuer}, expiry: ${this.expirySeconds}s)`,
      );
      this.logger.log(
        'JWT signing key not configured - set JWT_SIGNING_KEY_PATH to enable JWT minting',
      );
      return;
    }

    try {
      await this.loadSigningKey();
      this.logger.log(
        `Internal JWT service initialized with signing key (issuer: ${this.issuer}, algorithm: ${this.algorithm}, expiry: ${this.expirySeconds}s)`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to load signing key from ${this.signingKeyPath}: ${error instanceof Error ? error.message : 'unknown error'}`,
      );
      this.logger.warn(
        'JWT signing will fail until a valid signing key is configured',
      );
    }
  }

  /**
   * Load private key from configured path (ES256 or RS256)
   */
  private async loadSigningKey(): Promise<void> {
    if (!this.signingKeyPath) {
      throw new Error('JWT signing key path not configured');
    }

    const keyData = await readFile(this.signingKeyPath, 'utf-8');
    this.privateKey = await importPKCS8(keyData, this.algorithm);
  }

  /**
   * Create and sign an internal JWT for FHIR server authentication
   *
   * @throws Error if signing key is not loaded or signing fails
   */
  async createJwt(input: CreateJwtInput): Promise<string> {
    if (!this.privateKey) {
      throw new Error(
        'JWT signing key not loaded. Cannot create JWT without valid key.',
      );
    }

    const now = Math.floor(Date.now() / 1000);
    const exp = now + this.expirySeconds;

    const payload: InternalJwtPayload = {
      iss: this.issuer,
      sub: input.serviceProviderId,
      aud: this.audience,
      patient: input.localPatientId,
      scope: input.scope,
      iat: now,
      exp,
    };

    // Add optional correlation ID if provided
    if (input.correlationId) {
      payload.correlation_id = input.correlationId;
    }

    try {
      const jwt = await new SignJWT(payload as any)
        .setProtectedHeader({ alg: this.algorithm, typ: 'JWT' })
        .setIssuedAt(now)
        .setExpirationTime(exp)
        .setIssuer(this.issuer)
        .setSubject(input.serviceProviderId)
        .setAudience(this.audience)
        .sign(this.privateKey);

      return jwt;
    } catch (error) {
      this.logger.error(
        `Failed to sign JWT: ${error instanceof Error ? error.message : 'unknown error'}`,
      );
      throw new Error('Failed to create JWT');
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
