import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { readFile } from 'fs/promises';
import * as https from 'https';

@Injectable()
export class PcmHttpClientService implements OnModuleInit {
  private readonly logger = new Logger(PcmHttpClientService.name);
  private httpsAgent: https.Agent | null = null;
  private readonly certPath: string;
  private readonly keyPath: string;
  private readonly caCertPath: string;
  private readonly tlsServername?: string;

  constructor(private configService: ConfigService) {
    this.certPath = this.configService.get<string>('pcm.mtls.certPath', '');
    this.keyPath = this.configService.get<string>('pcm.mtls.keyPath', '');
    this.caCertPath = this.configService.get<string>('pcm.mtls.caCertPath', '');
    this.tlsServername = this.configService.get<string>('pcm.mtls.tlsServername');
  }

  async onModuleInit() {
    if (!this.certPath || !this.keyPath) {
      this.logger.warn(
        'PCM mTLS certificate paths not configured - token acquisition will fail',
      );
      return;
    }

    try {
      await this.loadHttpsAgent();
      this.logger.log('PCM mTLS HTTPS client initialized');
    } catch (error) {
      this.logger.error(
        `Failed to initialize mTLS HTTPS client: ${error instanceof Error ? error.message : 'unknown error'}`,
      );
    }
  }

  /**
   * Load mTLS certificates and create HTTPS agent
   */
  private async loadHttpsAgent(): Promise<void> {
    if (!this.certPath || !this.keyPath) {
      throw new Error('mTLS certificate paths not configured');
    }

    // Load client certificate and key (do NOT log contents)
    const cert = await readFile(this.certPath, 'utf-8');
    const key = await readFile(this.keyPath, 'utf-8');

    // Load CA certificate if configured
    let ca: string | undefined;
    if (this.caCertPath) {
      ca = await readFile(this.caCertPath, 'utf-8');
    }

    // Create HTTPS agent with mTLS configuration
    const agentOptions: https.AgentOptions = {
      cert,
      key,
      ca,
      rejectUnauthorized: true, // Always verify server certificate
    };

    // Add TLS servername override if configured (for SNI when hostname != cert SAN)
    if (this.tlsServername) {
      agentOptions.servername = this.tlsServername;
      this.logger.log(`TLS servername override configured: ${this.tlsServername}`);
    }

    this.httpsAgent = new https.Agent(agentOptions);

    this.logger.debug(
      `mTLS HTTPS agent created (CA: ${this.caCertPath ? 'configured' : 'system default'})`,
    );
  }

  /**
   * Get the configured HTTPS agent for PCM requests
   *
   * @throws Error if agent not initialized
   */
  getAgent(): https.Agent {
    if (!this.httpsAgent) {
      throw new Error('mTLS HTTPS agent not initialized');
    }
    return this.httpsAgent;
  }

  /**
   * Set a mock agent for testing purposes
   * @internal Use only in tests
   */
  setMockAgent(agent: https.Agent): void {
    this.httpsAgent = agent;
  }
}
