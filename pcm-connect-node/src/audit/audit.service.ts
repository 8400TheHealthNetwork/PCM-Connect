import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { AuditEvent } from './interfaces/audit-event.interface';

@Injectable()
export class AuditService {
  private readonly logger = new Logger(AuditService.name);
  private readonly enabled: boolean;

  constructor(private configService: ConfigService) {
    this.enabled = this.configService.get<boolean>('audit.enabled', true);

    if (!this.enabled) {
      this.logger.warn('Audit is DISABLED via configuration');
    }
  }

  /**
   * Write an audit event
   * This method MUST NOT throw errors - audit failures should never break the request path
   */
  async audit(event: AuditEvent): Promise<void> {
    if (!this.enabled) {
      return;
    }

    try {
      // Ensure timestamp is present
      const auditEvent: AuditEvent = {
        ...event,
        timestamp: event.timestamp || new Date().toISOString(),
      };

      // Write to stdout as JSON (one line per event)
      // Using console.log (not Logger) to keep audit separate from application logs
      console.log(JSON.stringify(auditEvent));
    } catch (error) {
      // Log the audit failure internally, but DO NOT throw
      this.logger.error(
        `Failed to write audit event: ${error instanceof Error ? error.message : 'unknown error'}`,
      );
    }
  }

  /**
   * Create a basic HTTP request audit event
   */
  createHttpRequestEvent(
    correlationId: string,
    method: string,
    path: string,
    statusCode: number,
    durationMs: number,
    outcome: AuditEvent['outcome'] = 'success',
  ): AuditEvent {
    return {
      timestamp: new Date().toISOString(),
      correlationId,
      eventType: 'http_request',
      outcome,
      httpMethod: method,
      path,
      statusCode,
      durationMs,
    };
  }

  /**
   * Create a security violation audit event
   */
  createSecurityViolationEvent(
    correlationId: string,
    details: string,
    patientIdMasked?: string,
  ): AuditEvent {
    return {
      timestamp: new Date().toISOString(),
      correlationId,
      eventType: 'security_violation',
      outcome: 'failure',
      patientIdMasked,
      details: { message: details },
    };
  }

  /**
   * Create an error audit event
   */
  createErrorEvent(
    correlationId: string,
    errorCode: string,
    errorMessage: string,
    httpMethod?: string,
    path?: string,
  ): AuditEvent {
    return {
      timestamp: new Date().toISOString(),
      correlationId,
      eventType: 'error',
      outcome: 'failure',
      httpMethod,
      path,
      errorCode,
      details: { message: errorMessage },
    };
  }
}
