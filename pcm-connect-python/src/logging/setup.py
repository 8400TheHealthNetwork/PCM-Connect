from __future__ import annotations

import logging
import sys

import structlog


class _MaxLevelFilter(logging.Filter):
    def __init__(self, max_level: int) -> None:
        super().__init__()
        self._max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self._max_level


def configure_logging(level: str = "info") -> None:
    level_int = logging.getLevelName(level.upper())
    if not isinstance(level_int, int):
        level_int = logging.INFO

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(_MaxLevelFilter(logging.WARNING))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(level_int)
    root.handlers = [stdout_handler, stderr_handler]

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_int),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
