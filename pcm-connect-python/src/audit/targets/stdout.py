from __future__ import annotations

import logging


class StdoutTarget:
    """Emit already-formatted audit documents through the stdout handler."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("audit")
        # Audit delivery must not disappear when the application log level is
        # raised above INFO. Propagated records are still handled by the
        # configured stdout handler.
        self._logger.setLevel(logging.INFO)

    async def start(self) -> None:
        return None

    async def send(self, payload: str) -> None:
        self._logger.info(payload)

    async def aclose(self) -> None:
        return None
