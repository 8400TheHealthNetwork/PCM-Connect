export interface ForbiddenSecurityLabel {
  system: string;
  code: string;
}

export interface ResponseVerificationConfig {
  enabled: boolean;
  forbiddenLabels: ForbiddenSecurityLabel[];
}
