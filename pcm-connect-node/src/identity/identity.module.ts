import { Module } from '@nestjs/common';
import { IdReplacementService } from './id-replacement.service';

@Module({
  providers: [IdReplacementService],
  exports: [IdReplacementService],
})
export class IdentityModule {}
