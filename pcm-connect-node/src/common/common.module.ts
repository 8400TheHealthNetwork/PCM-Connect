import { Module, MiddlewareConsumer, NestModule } from '@nestjs/common';
import { CorrelationIdMiddleware } from './correlation/correlation-id.middleware';
import { OperationOutcomeBuilder } from './errors/operation-outcome.builder';

@Module({
  providers: [OperationOutcomeBuilder],
  exports: [OperationOutcomeBuilder],
})
export class CommonModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    consumer.apply(CorrelationIdMiddleware).forRoutes('*');
  }
}
