class DSAdapterError(Exception):
    """Base error carrying a stable code from the DS Adapter error catalog."""

    code: str = "GEN_001"

    def __init__(self, message: str = "", code: str | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        if code is not None:
            self.code = code


class ConfigurationError(DSAdapterError):
    code = "CFG_001"


__all__ = ["DSAdapterError", "ConfigurationError"]
