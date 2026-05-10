import { Module } from '@nestjs/common';
import { InternalJwtService } from './internal-jwt.service';

@Module({
  providers: [InternalJwtService],
  exports: [InternalJwtService],
})
export class JwtModule {}
