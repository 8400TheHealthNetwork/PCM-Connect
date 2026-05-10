import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { access, constants } from 'fs/promises';

export interface ReadinessCheck {
  status: 'ready' | 'not_ready';
  message: string;
  checks: {
    config: {
      status: 'ok' | 'incomplete';
      missing?: string[];
    };
    certificates: {
      status: 'ok' | 'missing';
      unreadable?: string[];
    };
  };
}

@Injectable()
export class ReadinessService {
  private readonly logger = new Logger(ReadinessService.name);

  constructor(private configService: ConfigService) {}

  async checkReadiness(): Promise<ReadinessCheck> {
    const configCheck = this.checkRequiredConfig();
    const certCheck = await this.checkCertificateFiles();

    const isReady = configCheck.status === 'ok' && certCheck.status === 'ok';

    return {
      status: isReady ? 'ready' : 'not_ready',
      message: isReady
        ? 'All required configuration and certificates are present'
        : 'Missing required configuration or certificate files',
      checks: {
        config: configCheck,
        certificates: certCheck,
      },
    };
  }

  private checkRequiredConfig(): {
    status: 'ok' | 'incomplete';
    missing?: string[];
  } {
    const requiredEnvVars = [
      'DATA_SOURCE_ID',
      'DATA_SOURCE_ENDPOINT',
      'PCM_CLIENT_ID',
      'PCM_BASE_URL',
      'PCM_TOKEN_ENDPOINT',
      'PCM_INTROSPECTION_ENDPOINT',
      'PCM_CLIENT_ASSERTION_AUDIENCE',
      'PCM_MTLS_CERT_PATH',
      'PCM_MTLS_KEY_PATH',
      'PCM_CA_CERT_PATH',
      'PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH',
    ];

    const missing: string[] = [];

    for (const envVar of requiredEnvVars) {
      const value = this.getConfigValue(envVar);
      if (!value || value === '') {
        missing.push(envVar);
      }
    }

    if (missing.length > 0) {
      return { status: 'incomplete', missing };
    }

    return { status: 'ok' };
  }

  private async checkCertificateFiles(): Promise<{
    status: 'ok' | 'missing';
    unreadable?: string[];
  }> {
    const certPaths = [
      {
        label: 'PCM_MTLS_CERT_PATH',
        path: this.configService.get<string>('pcm.mtls.certPath'),
      },
      {
        label: 'PCM_MTLS_KEY_PATH',
        path: this.configService.get<string>('pcm.mtls.keyPath'),
      },
      {
        label: 'PCM_CA_CERT_PATH',
        path: this.configService.get<string>('pcm.mtls.caCertPath'),
      },
      {
        label: 'PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH',
        path: this.configService.get<string>('pcm.clientAssertion.privateKeyPath'),
      },
    ];

    const unreadable: string[] = [];

    for (const { label, path } of certPaths) {
      if (!path || path === '') {
        unreadable.push(label);
        continue;
      }

      try {
        // Check if file exists and is readable (do NOT read contents)
        await access(path, constants.R_OK);
      } catch (error) {
        unreadable.push(label);
        this.logger.debug(
          `Certificate file not accessible: ${label} (${error instanceof Error ? error.message : 'unknown error'})`,
        );
      }
    }

    if (unreadable.length > 0) {
      return { status: 'missing', unreadable };
    }

    return { status: 'ok' };
  }

  private getConfigValue(envVar: string): string | undefined {
    // Map environment variable names to config paths
    const configMap: Record<string, string> = {
      DATA_SOURCE_ID: 'dataSource.id',
      DATA_SOURCE_ENDPOINT: 'dataSource.endpoint',
      PCM_CLIENT_ID: 'pcm.clientId',
      PCM_BASE_URL: 'pcm.baseUrl',
      PCM_TOKEN_ENDPOINT: 'pcm.tokenEndpoint',
      PCM_INTROSPECTION_ENDPOINT: 'pcm.introspectionEndpoint',
      PCM_CLIENT_ASSERTION_AUDIENCE: 'pcm.clientAssertion.audience',
      PCM_MTLS_CERT_PATH: 'pcm.mtls.certPath',
      PCM_MTLS_KEY_PATH: 'pcm.mtls.keyPath',
      PCM_CA_CERT_PATH: 'pcm.mtls.caCertPath',
      PCM_CLIENT_ASSERTION_PRIVATE_KEY_PATH:
        'pcm.clientAssertion.privateKeyPath',
    };

    const configPath = configMap[envVar];
    if (!configPath) {
      return undefined;
    }

    return this.configService.get<string>(configPath);
  }
}
