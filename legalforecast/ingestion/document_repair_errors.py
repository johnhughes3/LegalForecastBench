"""Shared fail-closed errors for document-repair helpers."""


class DocumentRepairExecutorError(ValueError):
    """Raised when repair execution is not exactly authorized and replayable."""
