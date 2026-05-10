import { Controller, Get, HttpStatus, HttpCode } from '@nestjs/common';
import { ReadinessService, ReadinessCheck } from './readiness.service';

@Controller()
export class HealthController {
  constructor(private readonly readinessService: ReadinessService) {}

  @Get('/health')
  getHealth() {
    return { status: 'ok' };
  }

  @Get('/ready')
  @HttpCode(HttpStatus.OK)
  async getReadiness(): Promise<ReadinessCheck> {
    return this.readinessService.checkReadiness();
  }
}
