"""Fallback retrieval diagnostics for supplemental public-record sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legalforecast.ingestion.provenance import SourceDocumentProvenance
from legalforecast.selection.case_mix_diagnostics import FallbackSource
from legalforecast.selection.fallback_rules import (
    FallbackDecision,
    FallbackGap,
    decide_targeted_fallback,
)


@dataclass(frozen=True, slots=True)
class FallbackRetrievalDiagnostics:
    """Auditable summary of one targeted fallback retrieval attempt."""

    candidate_id: str
    case_id: str
    gap: FallbackGap
    source: FallbackSource
    docket_entry_count: int = 0
    documents: tuple[SourceDocumentProvenance, ...] = ()
    missing_reasons: tuple[str, ...] = ()
    request_count: int = 0

    def __post_init__(self) -> None:
        _require_non_empty(self.candidate_id, "candidate_id")
        _require_non_empty(self.case_id, "case_id")
        if self.source is FallbackSource.CASE_DEV_ONLY:
            raise ValueError("fallback retrieval diagnostics require fallback source")
        if self.docket_entry_count < 0:
            raise ValueError("docket_entry_count must be non-negative")
        if self.request_count < 0:
            raise ValueError("request_count must be non-negative")
        for reason in self.missing_reasons:
            _require_non_empty(reason, "missing_reasons")

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def has_reconstructed_material(self) -> bool:
        return self.docket_entry_count > 0 or bool(self.documents)

    @property
    def decision(self) -> FallbackDecision:
        return decide_targeted_fallback(
            self.gap,
            available_sources=(self.source,) if self.has_reconstructed_material else (),
        )

    def to_case_mix_fields(self) -> dict[str, Any]:
        return self.decision.to_case_mix_fields()

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "case_id": self.case_id,
            "gap": self.gap.value,
            "source": self.source.value,
            "docket_entry_count": self.docket_entry_count,
            "document_count": self.document_count,
            "missing_reasons": list(self.missing_reasons),
            "request_count": self.request_count,
            "decision": self.decision.to_record(),
            "documents": [document.to_record() for document in self.documents],
        }


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} is required")
