import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class ConfigValidationService implements OnModuleInit {
  private readonly logger = new Logger(ConfigValidationService.name);

  constructor(private configService: ConfigService) {}

  onModuleInit() {
    this.validateConfiguration();
  }

  private validateConfiguration(): void {
    const errors: string[] = [];

    // Validate URL configurations
    this.validateUrl('fhir.baseUrl', errors);
    this.validateUrl('jwt.audience', errors);
    this.validateUrl('pcm.baseUrl', errors);

    // Validate JWT issuer (should not contain inline comments or suspicious chars)
    this.validateCleanString('jwt.issuer', errors);

    // Check for common .env file mistakes
    this.checkForInlineComments(errors);

    if (errors.length > 0) {
      this.logger.error('Configuration validation failed:');
      errors.forEach((error) => this.logger.error(`  - ${error}`));
      this.logger.error(
        'Tip: .env file comments must use # on a separate line, not inline like // TODO',
      );
      throw new Error(
        `Configuration validation failed with ${errors.length} error(s)`,
      );
    }

    this.logger.log('Configuration validation passed');
  }

  private validateUrl(configKey: string, errors: string[]): void {
    const value = this.configService.get<string>(configKey);
    if (!value) {
      // Empty is ok for optional configs
      return;
    }

    try {
      new URL(value);
    } catch (error) {
      errors.push(
        `Invalid URL for ${configKey}: "${value}" (${error instanceof Error ? error.message : 'unknown error'})`,
      );
    }
  }

  private validateCleanString(configKey: string, errors: string[]): void {
    const value = this.configService.get<string>(configKey, '');

    // Check for inline comment pollution
    if (value.includes('//') || value.includes('#')) {
      errors.push(
        `Config value ${configKey} contains suspicious characters (// or #): "${value.substring(0, 50)}..." - check for inline comments in .env file`,
      );
    }

    // Check for newline pollution
    if (value.includes('\n') || value.includes('\r')) {
      errors.push(
        `Config value ${configKey} contains newline characters - check .env file formatting`,
      );
    }
  }

  private checkForInlineComments(errors: string[]): void {
    // Get all config keys and check for common pollution patterns
    const suspiciousKeys = [
      'jwt.issuer',
      'jwt.audience',
      'fhir.baseUrl',
      'pcm.baseUrl',
      'pcm.clientId',
    ];

    for (const key of suspiciousKeys) {
      const value = this.configService.get<string>(key, '');
      if (value && (value.includes('TODO') || value.includes('FIXME'))) {
        errors.push(
          `Config value ${key} contains placeholder text (TODO/FIXME): "${value.substring(0, 50)}..." - update configuration`,
        );
      }
    }
  }
}
