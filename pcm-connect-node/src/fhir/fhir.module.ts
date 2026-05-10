import { Module } from '@nestjs/common';
import { FhirProxyController } from './fhir-proxy.controller';
import { FhirUrlBuilderService } from './fhir-url-builder.service';
import { FhirForwardService } from './fhir-forward.service';
import { PcmModule } from '../pcm/pcm.module';
import { IdentityModule } from '../identity/identity.module';
import { JwtModule } from '../jwt/jwt.module';
import { VerificationModule } from '../verification/verification.module';
import { AuditModule} from '../audit/audit.module';

@Module({
  imports: [
    PcmModule,
    IdentityModule,
    JwtModule,
    VerificationModule,
    AuditModule,
  ],
  controllers: [FhirProxyController],
  providers: [FhirUrlBuilderService, FhirForwardService],
})
export class FhirModule {}
