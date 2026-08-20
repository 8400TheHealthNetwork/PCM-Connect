from __future__ import annotations

import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from src.config.models import FileTargetConfig


class FileTarget:
    def __init__(self, config: FileTargetConfig) -> None:
        self._config = config
        self._lock = asyncio.Lock()
        self._handler: logging.FileHandler | None = None

    async def start(self) -> None:
        path = Path(self._config.path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if self._config.rotation == "none":
            self._handler = logging.FileHandler(filename=str(path), encoding="utf-8")
        else:
            when = "H" if self._config.rotation == "hourly" else "D"
            self._handler = TimedRotatingFileHandler(
                filename=str(path),
                when=when,
                backupCount=self._config.max_files,
                encoding="utf-8",
            )
        self._handler.setFormatter(logging.Formatter("%(message)s"))

    async def send(self, payload: str) -> None:
        if self._handler is None:
            await self.start()
        assert self._handler is not None
        async with self._lock:
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
