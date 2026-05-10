import { Injectable } from '@nestjs/common';

export type IssueSeverity = 'fatal' | 'error' | 'warning' | 'information';

export type IssueCode =
  | 'invalid'
  | 'structure'
  | 'required'
  | 'value'
  | 'invariant'
  | 'security'
  | 'login'
  | 'unknown'
  | 'expired'
  | 'forbidden'
  | 'suppressed'
  | 'processing'
  | 'not-supported'
  | 'duplicate'
  | 'multiple-matches'
  | 'not-found'
  | 'deleted'
  | 'too-long'
  | 'code-invalid'
  | 'extension'
  | 'too-costly'
  | 'business-rule'
  | 'conflict'
  | 'transient'
  | 'lock-error'
  | 'no-store'
  | 'exception'
  | 'timeout'
  | 'incomplete'
  | 'throttled'
  | 'informational';

export interface OperationOutcomeIssue {
  severity: IssueSeverity;
  code: IssueCode;
  diagnostics: string;
  details?: {
    text?: string;
    coding?: Array<{
      system?: string;
      code?: string;
      display?: string;
    }>;
  };
}

export interface OperationOutcome {
  resourceType: 'OperationOutcome';
  issue: OperationOutcomeIssue[];
}

@Injectable()
export class OperationOutcomeBuilder {
  /**
   * Build a FHIR R4 OperationOutcome resource
   */
  build(issues: OperationOutcomeIssue[]): OperationOutcome {
    return {
      resourceType: 'OperationOutcome',
      issue: issues,
    };
  }

  /**
   * Build a simple OperationOutcome with a single issue
   */
  buildSingle(
    severity: IssueSeverity,
    code: IssueCode,
    diagnostics: string,
  ): OperationOutcome {
    return this.build([{ severity, code, diagnostics }]);
  }

  /**
   * Build a generic error OperationOutcome (for security-sensitive failures)
   */
  buildGenericError(message?: string): OperationOutcome {
    return this.buildSingle(
      'error',
      'processing',
      message || 'Request could not be processed',
    );
  }

  /**
   * Build an unauthorized OperationOutcome
   */
  buildUnauthorized(message?: string): OperationOutcome {
    return this.buildSingle(
      'error',
      'login',
      message || 'Authentication required',
    );
  }

  /**
   * Build a forbidden OperationOutcome
   */
  buildForbidden(message?: string): OperationOutcome {
    return this.buildSingle(
      'error',
      'forbidden',
      message || 'Access denied',
    );
  }

  /**
   * Build a not found OperationOutcome
   */
  buildNotFound(message?: string): OperationOutcome {
    return this.buildSingle(
      'error',
      'not-found',
      message || 'Resource not found',
    );
  }

  /**
   * Build a bad request OperationOutcome
   */
  buildBadRequest(message: string): OperationOutcome {
    return this.buildSingle('error', 'invalid', message);
  }

  /**
   * Build a timeout OperationOutcome
   */
  buildTimeout(message?: string): OperationOutcome {
    return this.buildSingle(
      'error',
      'timeout',
      message || 'Request timeout',
    );
  }
}
