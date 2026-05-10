import {
  Controller,
  Get,
  Req,
  Res,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { FastifyRequest, FastifyReply } from 'fastify';
import { PcmIntrospectionService } from '../pcm/pcm-introspection.service';
import { IdReplacementService } from '../identity/id-replacement.service';
import { InternalJwtService } from '../jwt/internal-jwt.service';
import { FhirUrlBuilderService } from './fhir-url-builder.service';
import { FhirForwardService } from './fhir-forward.service';
import { ResponseVerificationService } from '../verification/response-verification.service';
import { AuditService } from '../audit/audit.service';

@Controller('fhir')
export class FhirProxyController {
  private readonly logger = new Logger(FhirProxyController.name);

  constructor(
    private pcmIntrospectionService: PcmIntrospectionService,
    private idReplacementService: IdReplacementService,
    private internalJwtService: InternalJwtService,
    private fhirUrlBuilder: FhirUrlBuilderService,
    private fhirForwardService: FhirForwardService,
    private responseVerificationService: ResponseVerificationService,
    private auditService: AuditService,
  ) {}

  @Get('*')
  async proxyFhirRequest(
    @Req() request: FastifyRequest,
    @Res() reply: FastifyReply,
  ) {
    const correlationId = (request as any).correlationId || 'unknown';
    // Extract path without query string to avoid duplication
    const fullPath = request.url.replace('/fhir', '');
    const path = fullPath.split('?')[0];

    try {
      // Step 1: Extract Bearer token
      const authHeader = request.headers.authorization;
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        this.logger.warn('Missing or invalid Authorization header');
        await this.auditService.audit({
          timestamp: new Date().toISOString(),
          correlationId,
          eventType: 'http_request',
          outcome: 'failure',
          httpMethod: request.method,
          path: request.url,
          statusCode: HttpStatus.UNAUTHORIZED,
          errorCode: 'missing_authorization',
        });
        return reply.status(HttpStatus.UNAUTHORIZED).send({
          resourceType: 'OperationOutcome',
          issue: [
            {
              severity: 'error',
              code: 'security',
              diagnostics: 'Authorization header required',
            },
          ],
        });
      }

      const opaqueToken = authHeader.substring(7); // Remove "Bearer "

      // Step 2: Introspect token with PCM (or mock)
      this.logger.debug(`Introspecting token (correlation: ${correlationId})`);
      const introspection = await this.pcmIntrospectionService.introspect(
        opaqueToken,
      );

      if (!introspection.active) {
        this.logger.warn('Token is inactive');
        await this.auditService.audit({
          timestamp: new Date().toISOString(),
          correlationId,
          eventType: 'http_request',
          outcome: 'failure',
          httpMethod: request.method,
          path: request.url,
          statusCode: HttpStatus.UNAUTHORIZED,
          errorCode: 'token_inactive',
        });
        return reply.status(HttpStatus.UNAUTHORIZED).send({
          resourceType: 'OperationOutcome',
          issue: [
            {
              severity: 'error',
              code: 'security',
              diagnostics: 'Token is invalid or expired',
            },
          ],
        });
      }

      // Step 3: Resolve patient ID
      if (!introspection.patient) {
        this.logger.error('Introspection missing patient field');
        await this.auditService.audit({
          timestamp: new Date().toISOString(),
          correlationId,
          eventType: 'http_request',
          outcome: 'failure',
          httpMethod: request.method,
          path: request.url,
          statusCode: HttpStatus.BAD_REQUEST,
          errorCode: 'missing_patient',
        });
        return reply.status(HttpStatus.BAD_REQUEST).send({
          resourceType: 'OperationOutcome',
          issue: [
            {
              severity: 'error',
              code: 'invalid',
              diagnostics: 'Token missing patient information',
            },
          ],
        });
      }

      const idResolution = await this.idReplacementService.resolve({
        identifierSystem: 'http://fhir.health.gov.il/identifier/il-national-id',
        identifierValue: introspection.patient,
      });

      // Step 4: Mint internal JWT
      const jwtInput: any = {
        sub: introspection.client_id || 'unknown',
        patient: idResolution.localPatientId,
        correlation_id: correlationId,
      };

      // Add optional fields if present
      if (introspection.consent_id) jwtInput.consent_id = introspection.consent_id;
      if (introspection.scope) jwtInput.scope = introspection.scope;
      if (introspection.baskets) jwtInput.baskets = introspection.baskets;
      if (introspection.access_type) jwtInput.access_type = introspection.access_type;
      if (introspection.sp_organization_id) jwtInput.sp_organization_id = introspection.sp_organization_id;

      const internalJwt = await this.internalJwtService.createJwt(jwtInput);

      // Step 5: Build FHIR URL
      const queryParams = new URLSearchParams(request.url.split('?')[1] || '');
      const fhirUrl = this.fhirUrlBuilder.buildUrl(
        path,
        queryParams,
        idResolution.localPatientId,
      );

      // Step 6: Forward to FHIR server
      const fhirResponse = await this.fhirForwardService.forward(
        fhirUrl,
        internalJwt,
        correlationId,
      );

      // Step 7: Verify response
      const verification = this.responseVerificationService.verify(
        fhirResponse,
      );

      if (!verification.passed) {
        this.logger.error(`Response verification failed`);
        await this.auditService.audit({
          timestamp: new Date().toISOString(),
          correlationId,
          eventType: 'http_request',
          outcome: 'failure',
          httpMethod: request.method,
          path: request.url,
          statusCode: HttpStatus.FORBIDDEN,
          errorCode: 'response_verification_failed',
        });
        return reply.status(HttpStatus.FORBIDDEN).send({
          resourceType: 'OperationOutcome',
          issue: [
            {
              severity: 'error',
              code: 'security',
              diagnostics: 'Request could not be processed',
            },
          ],
        });
      }

      // Step 8: Return FHIR response
      await this.auditService.audit({
        timestamp: new Date().toISOString(),
        correlationId,
        eventType: 'http_request',
        outcome: 'success',
        httpMethod: request.method,
        path: request.url,
        statusCode: HttpStatus.OK,
        durationMs: 0,
      });

      return reply.status(HttpStatus.OK).send(fhirResponse);
    } catch (error) {
      this.logger.error(
        `FHIR proxy error: ${error instanceof Error ? error.message : 'unknown error'}`,
      );
      await this.auditService.audit({
        timestamp: new Date().toISOString(),
        correlationId,
        eventType: 'http_request',
        outcome: 'failure',
        httpMethod: request.method,
        path: request.url,
        statusCode: HttpStatus.INTERNAL_SERVER_ERROR,
        errorCode: 'internal_error',
      });
      return reply.status(HttpStatus.INTERNAL_SERVER_ERROR).send({
        resourceType: 'OperationOutcome',
        issue: [
          {
            severity: 'error',
            code: 'exception',
            diagnostics: 'Internal server error',
          },
        ],
      });
    }
  }
}
