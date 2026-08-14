"""Shared chronology, bundle, and verdict types for document-need triage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

_SHA256_LEN = 64


class NeedBucket(StrEnum):
    """Closed document-need buckets (dn9.1)."""

    CLEARLY_REQUIRED = "clearly_required"
    CONDITIONAL = "conditional"
    CLEARLY_NOT_REQUIRED = "clearly_not_required"


_BUCKET_RANK = {
    NeedBucket.CLEARLY_NOT_REQUIRED: 0,
    NeedBucket.CONDITIONAL: 1,
    NeedBucket.CLEARLY_REQUIRED: 2,
}


def bucket_rank(bucket: NeedBucket) -> int:
    """Return the promotion rank; higher means more required."""

    return _BUCKET_RANK[bucket]


def _require_text(value: str, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _require_sha256(value: str, label: str) -> str:
    digest = _require_text(value, label)
    if len(digest) != _SHA256_LEN or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return digest


@dataclass(frozen=True, slots=True)
class DocketDocument:
    """One RECAP/PACER document attached to a predecision docket entry."""

    selector: str
    description: str
    freely_available: bool
    pacer_only: bool
    page_count: int | None
    restricted: bool = False

    def __post_init__(self) -> None:
        _require_text(self.selector, "document selector")
        if type(self.description) is not str:
            raise ValueError("document description must be a string")
        if type(self.freely_available) is not bool:
            raise ValueError("freely_available must be boolean")
        if type(self.pacer_only) is not bool:
            raise ValueError("pacer_only must be boolean")
        if type(self.restricted) is not bool:
            raise ValueError("restricted must be boolean")
        if self.page_count is not None and (
            type(self.page_count) is not int or self.page_count <= 0
        ):
            raise ValueError("page_count must be a positive integer when set")


@dataclass(frozen=True, slots=True)
class ChronologyEntry:
    """One predecision docket entry with free/paid and page-count metadata."""

    entry: int
    filed: str | None
    text: str
    documents: tuple[DocketDocument, ...]
    restricted: bool = False

    def __post_init__(self) -> None:
        if type(self.entry) is not int or self.entry <= 0:
            raise ValueError("entry number must be a positive integer")
        if self.filed is not None and (
            type(self.filed) is not str or not self.filed.strip()
        ):
            raise ValueError("filed must be a nonempty string when set")
        if type(self.text) is not str:
            raise ValueError("entry text must be a string")
        if type(self.restricted) is not bool:
            raise ValueError("restricted must be boolean")
        selectors = [document.selector for document in self.documents]
        if len(selectors) != len(set(selectors)):
            raise ValueError(f"duplicate document selector on entry {self.entry}")


@dataclass(frozen=True, slots=True)
class Chronology:
    """Predecision docket chronology. Decision-entry rows are excluded."""

    candidate_id: str
    case_name: str | None
    court: str | None
    docket_number: str | None
    target_motion_entries: tuple[int, ...]
    decision_cut_entry: int
    entries: tuple[ChronologyEntry, ...]

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        if type(self.decision_cut_entry) is not int or self.decision_cut_entry <= 0:
            raise ValueError("decision_cut_entry must be a positive integer")
        if not self.target_motion_entries:
            raise ValueError("target_motion_entries must be nonempty")
        if len(self.target_motion_entries) != len(set(self.target_motion_entries)):
            raise ValueError("target_motion_entries must be unique")
        for motion_entry in self.target_motion_entries:
            if type(motion_entry) is not int or motion_entry <= 0:
                raise ValueError("target motion entry must be a positive integer")
            if motion_entry >= self.decision_cut_entry:
                raise ValueError("target motion entry must precede the decision cut")
        seen: set[int] = set()
        for entry in self.entries:
            if entry.entry in seen:
                raise ValueError(f"duplicate chronology entry {entry.entry}")
            if entry.entry >= self.decision_cut_entry:
                raise ValueError(
                    f"chronology entry {entry.entry} is at or after the decision cut"
                )
            seen.add(entry.entry)
        for motion_entry in self.target_motion_entries:
            if motion_entry not in seen:
                raise ValueError(
                    f"target motion entry {motion_entry} is not in the chronology"
                )

    def entry_numbers(self) -> frozenset[int]:
        return frozenset(entry.entry for entry in self.entries)

    def by_number(self) -> dict[int, ChronologyEntry]:
        return {entry.entry: entry for entry in self.entries}


@dataclass(frozen=True, slots=True)
class DecisionText:
    """First-written disposition bytes sequestered from pass 1."""

    candidate_id: str
    text: str
    sha256: str

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.text, "decision text")
        _require_sha256(self.sha256, "decision sha256")


@dataclass(frozen=True, slots=True)
class BlindBundle:
    """Pass-1 inputs: predecision chronology and target-motion markdown."""

    chronology: Chronology
    motion_markdown: Mapping[int, str]

    def __post_init__(self) -> None:
        markdown = dict(self.motion_markdown)
        object.__setattr__(self, "motion_markdown", MappingProxyType(markdown))
        if not markdown:
            raise ValueError("blind bundle requires target-motion markdown")
        expected = set(self.chronology.target_motion_entries)
        if set(markdown) != expected:
            raise ValueError(
                "motion markdown keys must equal chronology.target_motion_entries"
            )
        for _entry_number, body in markdown.items():
            if type(body) is not str or not body.strip():
                raise ValueError("motion markdown must be nonempty")


@dataclass(frozen=True, slots=True)
class EyesBundle:
    """Pass-2 inputs. Decision bytes live here, never on BlindBundle."""

    decision: DecisionText
    selected_docs: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "selected_docs", tuple(dict(row) for row in self.selected_docs)
        )


@dataclass(frozen=True, slots=True)
class EntryVerdict:
    """One docket entry's bucket assignment and rationale."""

    entry: int
    bucket: NeedBucket
    asserted_role: str | None
    rationale: str

    def __post_init__(self) -> None:
        if type(self.entry) is not int or self.entry <= 0:
            raise ValueError("verdict entry must be a positive integer")
        if type(self.bucket) is not NeedBucket:
            raise ValueError("verdict bucket must be a NeedBucket")
        if self.asserted_role is not None:
            _require_text(self.asserted_role, "asserted_role")
        _require_text(self.rationale, "rationale")


@dataclass(frozen=True, slots=True)
class Pass1Verdict:
    """Pass-1 buckets computed from the blind bundle only."""

    candidate_id: str
    model_id: str
    provider: str
    model_version_or_snapshot: str
    entries: tuple[EntryVerdict, ...]

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.model_id, "model_id")
        _require_text(self.provider, "provider")
        _require_text(self.model_version_or_snapshot, "model_version_or_snapshot")
        seen: set[int] = set()
        for row in self.entries:
            if row.entry in seen:
                raise ValueError(f"pass-1 duplicate entry {row.entry}")
            seen.add(row.entry)

    def bucket_by_entry(self) -> dict[int, NeedBucket]:
        return {row.entry: row.bucket for row in self.entries}


@dataclass(frozen=True, slots=True)
class Pass2Promotion:
    """Outcome-neutral promotion of a predecision entry after reading the decision."""

    entry: int
    from_bucket: NeedBucket
    to_bucket: NeedBucket
    rationale: str
    predecision_entry_cited: int

    def __post_init__(self) -> None:
        if type(self.entry) is not int or self.entry <= 0:
            raise ValueError("promotion entry must be a positive integer")
        if bucket_rank(self.to_bucket) <= bucket_rank(self.from_bucket):
            raise ValueError("pass 2 may only promote entries, never demote")
        _require_text(self.rationale, "promotion rationale")
        if self.predecision_entry_cited != self.entry:
            raise ValueError("promotion must cite its own predecision entry")


@dataclass(frozen=True, slots=True)
class Pass2Verdict:
    """Pass-2 completeness check. Promotions only."""

    candidate_id: str
    model_id: str
    provider: str
    model_version_or_snapshot: str
    promotions: tuple[Pass2Promotion, ...]
    completeness_ok: bool

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        _require_text(self.model_id, "model_id")
        _require_text(self.provider, "provider")
        _require_text(self.model_version_or_snapshot, "model_version_or_snapshot")
        if type(self.completeness_ok) is not bool:
            raise ValueError("completeness_ok must be boolean")
        seen: set[int] = set()
        for row in self.promotions:
            if row.entry in seen:
                raise ValueError(f"pass-2 duplicate promotion {row.entry}")
            seen.add(row.entry)
