import { Module } from '@nestjs/common';
import { APP_FILTER, APP_INTERCEPTOR } from '@nestjs/core';
import { ConfigModule } from './config/config.module';
import { CommonModule } from './common/common.module';
import { AuditModule } from './audit/audit.module';
import { VerificationModule } from './verification/verification.module';
import { PcmModule } from './pcm/pcm.module';
import { JwtModule } from './jwt/jwt.module';
import { IdentityModule } from './identity/identity.module';
import { FhirModule } from './fhir/fhir.module';
import { HealthModule } from './health/health.module';
import {
  HttpExceptionFilter,
  OperationOutcomeBuilder,
} from './common';
import { AuditInterceptor, AuditService } from './audit';

@Module({
  imports: [
    ConfigModule,
    CommonModule,
    AuditModule,
    VerificationModule,
    PcmModule,
    JwtModule,
    IdentityModule,
    FhirModule,
    HealthModule,
  ],
  controllers: [],
  providers: [
    {
      provide: APP_FILTER,
      useFactory: (builder: OperationOutcomeBuilder) => {
        return new HttpExceptionFilter(builder);
      },
      inject: [OperationOutcomeBuilder],
    },
    {
      provide: APP_INTERCEPTOR,
      useFactory: (auditService: AuditService) => {
        return new AuditInterceptor(auditService);
      },
      inject: [AuditService],
    },
  ],
})
export class AppModule {}
