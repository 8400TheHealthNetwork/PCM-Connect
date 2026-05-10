import { Module } from '@nestjs/common';
import { ResponseVerificationService } from './response-verification.service';

@Module({
  providers: [ResponseVerificationService],
  exports: [ResponseVerificationService],
})
export class VerificationModule {}
