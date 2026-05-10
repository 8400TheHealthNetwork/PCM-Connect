import { HttpStatus } from '@nestjs/common';
import { IssueCode, IssueSeverity } from './operation-outcome.builder';

/**
 * Base application error that maps to FHIR OperationOutcome
 */
export class AppError extends Error {
  constructor(
    message: string,
    public readonly httpStatus: HttpStatus = HttpStatus.INTERNAL_SERVER_ERROR,
    public readonly issueSeverity: IssueSeverity = 'error',
    public readonly issueCode: IssueCode = 'processing',
    public readonly isClientSafe: boolean = false,
  ) {
    super(message);
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }

  /**
   * Get the message to show to the client
   * If not client-safe, returns a generic message
   */
  getClientMessage(): string {
    return this.isClientSafe ? this.message : 'Request could not be processed';
  }
}

/**
 * Security-sensitive error that should return generic message
 */
export class SecurityError extends AppError {
  constructor(message: string, issueCode: IssueCode = 'forbidden') {
    super(message, HttpStatus.FORBIDDEN, 'error', issueCode, false);
  }
}

/**
 * Authentication error
 */
export class AuthenticationError extends AppError {
  constructor(message: string = 'Authentication required') {
    super(message, HttpStatus.UNAUTHORIZED, 'error', 'login', true);
  }
}

/**
 * Authorization error
 */
export class AuthorizationError extends AppError {
  constructor(message: string = 'Access denied') {
    super(message, HttpStatus.FORBIDDEN, 'error', 'forbidden', true);
  }
}

/**
 * Not found error
 */
export class NotFoundError extends AppError {
  constructor(message: string = 'Resource not found') {
    super(message, HttpStatus.NOT_FOUND, 'error', 'not-found', true);
  }
}

/**
 * Bad request error
 */
export class BadRequestError extends AppError {
  constructor(message: string) {
    super(message, HttpStatus.BAD_REQUEST, 'error', 'invalid', true);
  }
}

/**
 * Timeout error
 */
export class TimeoutError extends AppError {
  constructor(message: string = 'Request timeout') {
    super(message, HttpStatus.REQUEST_TIMEOUT, 'error', 'timeout', true);
  }
}
