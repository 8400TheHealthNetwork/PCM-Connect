import { Module } from '@nestjs/common';
import { PcmClientAssertionService } from './pcm-client-assertion.service';
import { PcmHttpClientService } from './pcm-http-client.service';
import { PcmTokenService } from './pcm-token.service';
import { PcmIntrospectionService } from './pcm-introspection.service';

@Module({
  providers: [
    PcmClientAssertionService,
    PcmHttpClientService,
    PcmTokenService,
    PcmIntrospectionService,
  ],
  exports: [PcmTokenService, PcmIntrospectionService],
})
export class PcmModule {}
