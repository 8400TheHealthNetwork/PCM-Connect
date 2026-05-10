import {
  ExceptionFilter,
  Catch,
  ArgumentsHost,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import { FastifyReply, FastifyRequest } from 'fastify';
import { OperationOutcomeBuilder } from './operation-outcome.builder';
import { AppError } from './app-error';

@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(HttpExceptionFilter.name);

  constructor(
    private readonly operationOutcomeBuilder: OperationOutcomeBuilder,
  ) {}

  catch(exception: unknown, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<FastifyReply>();
    const request = ctx.getRequest<FastifyRequest>();

    const correlationId = (request.raw as any).correlationId || 'unknown';

    let status = HttpStatus.INTERNAL_SERVER_ERROR;
    let operationOutcome;

    if (exception instanceof AppError) {
      // Custom application error
      status = exception.httpStatus;
      operationOutcome = this.operationOutcomeBuilder.buildSingle(
        exception.issueSeverity,
        exception.issueCode,
        exception.getClientMessage(),
      );

      // Log internal details (not exposed to client)
      this.logger.warn(
        `AppError [${correlationId}]: ${exception.message}`,
        exception.stack,
      );
    } else if (exception instanceof HttpException) {
      // NestJS HTTP exception
      status = exception.getStatus();
      const exceptionResponse = exception.getResponse();

      const message =
        typeof exceptionResponse === 'string'
          ? exceptionResponse
          : (exceptionResponse as any).message || 'An error occurred';

      operationOutcome = this.operationOutcomeBuilder.buildSingle(
        'error',
        this.mapStatusToIssueCode(status),
        Array.isArray(message) ? message.join(', ') : message,
      );

      this.logger.warn(
        `HttpException [${correlationId}]: ${exception.message}`,
        exception.stack,
      );
    } else if (exception instanceof Error) {
      // Unknown error
      operationOutcome = this.operationOutcomeBuilder.buildGenericError();

      this.logger.error(
        `Unexpected error [${correlationId}]: ${exception.message}`,
        exception.stack,
      );
    } else {
      // Non-error exception
      operationOutcome = this.operationOutcomeBuilder.buildGenericError();

      this.logger.error(
        `Unknown exception [${correlationId}]: ${JSON.stringify(exception)}`,
      );
    }

    response.status(status).send(operationOutcome);
  }

  private mapStatusToIssueCode(status: number): any {
    switch (status) {
      case HttpStatus.BAD_REQUEST:
        return 'invalid';
      case HttpStatus.UNAUTHORIZED:
        return 'login';
      case HttpStatus.FORBIDDEN:
        return 'forbidden';
      case HttpStatus.NOT_FOUND:
        return 'not-found';
      case HttpStatus.REQUEST_TIMEOUT:
        return 'timeout';
      case HttpStatus.CONFLICT:
        return 'conflict';
      case HttpStatus.TOO_MANY_REQUESTS:
        return 'throttled';
      default:
        return 'processing';
    }
  }
}
