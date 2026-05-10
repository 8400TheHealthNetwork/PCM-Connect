from __future__ import annotations

import structlog

from src.config.models import KafkaTargetConfig

log = structlog.get_logger()


class KafkaTarget:
    def __init__(self, config: KafkaTargetConfig) -> None:
        self._config = config
        self._producer = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError:
            log.warning("aiokafka_not_installed_kafka_target_disabled")
            return

        self._producer = AIOKafkaProducer(bootstrap_servers=self._config.brokers)
        await self._producer.start()

    async def send(self, payload: str) -> None:
        if self._producer is None:
            return
        await self._producer.send_and_wait(self._config.topic, payload.encode("utf-8"))

    async def aclose(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
