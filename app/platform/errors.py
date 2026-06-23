"""Shared error types."""


class DomainError(Exception):
    """Base type for module-level domain errors."""

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code
