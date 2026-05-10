import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { FastifyRequest, FastifyReply } from 'fastify';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { AuditService } from './audit.service';

@Injectable()
export class AuditInterceptor implements NestInterceptor {
  constructor(private readonly auditService: AuditService) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<any> {
    const ctx = context.switchToHttp();
    const request = ctx.getRequest<FastifyRequest>();
    const response = ctx.getResponse<FastifyReply>();

    const startTime = Date.now();
    const correlationId = (request.raw as any).correlationId || 'unknown';
    const method = request.method;
    const path = request.url;

    return next.handle().pipe(
      tap({
        next: () => {
          // Success path
          const durationMs = Date.now() - startTime;
          const statusCode = response.statusCode || 200;

          this.auditService.audit(
            this.auditService.createHttpRequestEvent(
              correlationId,
              method,
              path,
              statusCode,
              durationMs,
              'success',
            ),
          );
        },
        error: (error: any) => {
          // Error path
          const durationMs = Date.now() - startTime;
          const statusCode = error.status || 500;

          this.auditService.audit(
            this.auditService.createHttpRequestEvent(
              correlationId,
              method,
              path,
              statusCode,
              durationMs,
              'failure',
            ),
          );
        },
      }),
    );
  }
}
