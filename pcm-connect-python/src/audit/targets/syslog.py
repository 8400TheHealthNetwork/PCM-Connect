from __future__ import annotations

import logging
import logging.handlers

from src.config.models import SyslogTargetConfig


class SyslogTarget:
    def __init__(self, config: SyslogTargetConfig) -> None:
        self._config = config
        self._handler: logging.handlers.SysLogHandler | None = None

    async def start(self) -> None:
        socktype = None
        if self._config.protocol == "tcp":
            import socket

            socktype = socket.SOCK_STREAM
        self._handler = logging.handlers.SysLogHandler(
            address=(self._config.host, self._config.port),
            facility=logging.handlers.SysLogHandler.LOG_LOCAL0,
            socktype=socktype,
        )

    async def send(self, payload: str) -> None:
        if self._handler is None:
            await self.start()
        assert self._handler is not None
        record = logging.LogRecord(
            name="audit",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=payload,
            args=(),
            exc_info=None,
        )
        self._handler.emit(record)

    async def aclose(self) -> None:
        if self._handler is not None:
            self._handler.close()
            self._handler = None
