import { ServerConfig } from './server.config';
import { DataSourceConfig } from './data-source.config';
import { PcmConfig } from './pcm.config';
import { FhirConfig } from './fhir.config';
import { IdReplacementConfig } from './id-replacement.config';
import { JwtConfig } from './jwt.config';
import { ResponseVerificationConfig } from './response-verification.config';
import { AuditConfig } from './audit.config';

export interface AppConfig {
  server: ServerConfig;
  dataSource: DataSourceConfig;
  pcm: PcmConfig;
  fhir: FhirConfig;
  idReplacement: IdReplacementConfig;
  jwt: JwtConfig;
  responseVerification: ResponseVerificationConfig;
  audit: AuditConfig;
}
