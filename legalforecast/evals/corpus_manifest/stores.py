"""Readers for the on-disk corpus stores the freeze tool draws bytes from.

Two readers, both deliberately narrow:

* the **document store** index, keyed by ``source_document_id``, built from the
  parser's ``*.metadata.json`` sidecars.  Every store this cycle produced —
  the lineage parse tree and each validated repair tranche — writes the same
  sidecar shape, so one reader covers the carried cases and the swapped-in
  cases without a per-tranche special case.
* the **byte-role verdict** index, which reads the verdicts that already exist
  and never recomputes one.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

# Every spelling is enumerated positively.  The held-documents union spells the
# field ``byte_role_verdict``; the small tranche verdict files spell it
# ``role_verdict``; the bulk validator output spells it ``verdict``.  A record
# carrying none of them is a hard refusal rather than an absent verdict, so a
# fourth spelling cannot enter unnoticed.
#
# ``heuristic_verdict`` is deliberately NOT in this list.  The validators keep
# it beside ``verdict`` precisely so an adjudication that overrides the
# heuristic stays auditable; reading it would silently prefer the pre-
# adjudication answer.
VERDICT_FIELD_SPELLINGS: Final[tuple[str, ...]] = (
    "byte_role_verdict",
    "role_verdict",
    "verdict",
)
BASIS_FIELD_SPELLINGS: Final[tuple[str, ...]] = ("validation_basis", "basis")

# The role a verdict CERTIFIES: what the validator determined the bytes
# actually are, and what ``verdict: match`` is a statement about.  The union
# head spells it ``role``; the bulk validator spells it ``expected_role``.
# Enumerated positively so a new spelling must be classified by name.
CERTIFIED_ROLE_SPELLINGS: Final[tuple[str, ...]] = ("expected_role", "role")

# The role the corpus CLAIMED at validation time.  Deliberately NOT part of
# CERTIFIED_ROLE_SPELLINGS: a claim certifies nothing, and treating it as
# certification makes the cross-check compare the corpus against its own
# earlier belief.  Retained for reporting and provenance only.
CLAIMED_ROLE_SPELLINGS: Final[tuple[str, ...]] = ("manifest_role",)

ACCEPTED_VERDICTS: Final[frozenset[str]] = frozenset({"match"})
REFUSED_VERDICTS: Final[frozenset[str]] = frozenset({"mismatch", "not_held"})
ADJUDICABLE_VERDICTS: Final[frozenset[str]] = frozenset({"unverifiable"})
KNOWN_VERDICTS: Final[frozenset[str]] = (
    ACCEPTED_VERDICTS | REFUSED_VERDICTS | ADJUDICABLE_VERDICTS
)
ADJUDICATED_BASIS: Final[str] = "adjudicated_text"


class CorpusStoreError(ValueError):
    """Raised when a corpus store cannot be read or is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """One parsed document located in a document store."""

    source_document_id: str
    candidate_id: str
    pdf_path: Path
    markdown_path: Path
    recorded_pdf_sha256: str
    quality_flags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VerdictRecord:
    """One byte-role verdict as it already exists on disk.

    Two roles are recorded, and every consumer must be explicit about which it
    trusts:

    * ``certified_role`` is what the validator determined the BYTES are.  The
      verdict is a statement about this role, so this is the only role that
      may gate anything.  The freeze's role cross-check trusts it over the
      corpus, because certification exists precisely to overrule a claim.
    * ``claimed_role`` is what the corpus asserted when the validation ran.  It
      is provenance, never authority.  It may be stale — a corpus can be
      corrected after the act was recorded — so a consumer that gates on it
      would compare the corpus against its own earlier belief and would let a
      stale claim rescue a mislabel the bytes contradict.

    When the two disagree, the corpus is what needs correcting, and the
    disagreement is surfaced against the CLAIM so an operator knows which
    artifact to fix.
    """

    source_document_id: str
    verdict: str
    certified_role: str | None
    validation_basis: str | None
    source: str
    claimed_role: str | None = None

    @property
    def is_accepted(self) -> bool:
        """Return whether this verdict alone clears a document for a packet."""

        if self.verdict in ACCEPTED_VERDICTS:
            return True
        return (
            self.verdict in ADJUDICABLE_VERDICTS
            and self.validation_basis == ADJUDICATED_BASIS
        )

    @property
    def is_refusal(self) -> bool:
        """Return whether this verdict blocks the document outright."""

        return self.verdict in REFUSED_VERDICTS


def index_document_store(roots: Iterable[Path]) -> dict[str, StoredDocument]:
    """Index every succeeded parser sidecar under *roots* by document id.

    Later roots win over earlier ones, so a repair tranche passed after the
    lineage tree supersedes it for the documents it carries.
    """

    index: dict[str, StoredDocument] = {}
    for root in roots:
        resolved = Path(root).expanduser()
        if not resolved.is_dir():
            raise CorpusStoreError(f"document store root is not a directory: {root}")
        for sidecar in sorted(resolved.rglob("*.metadata.json")):
            stored = _stored_document(sidecar, root=resolved)
            if stored is not None:
                index[stored.source_document_id] = stored
    return index


def index_verdicts(sources: Iterable[Path]) -> dict[str, tuple[VerdictRecord, ...]]:
    """Index every existing byte-role verdict under *sources* by document id.

    Verdicts are read, never recomputed.  Every verdict found for a document is
    retained so a later disagreement between stores is visible rather than
    resolved silently by read order.
    """

    index: dict[str, list[VerdictRecord]] = {}
    for source in sources:
        resolved = Path(source).expanduser()
        if not resolved.exists():
            raise CorpusStoreError(f"verdict source not found: {source}")
        for record in _verdict_records(resolved):
            index.setdefault(record.source_document_id, []).append(record)
    return {key: tuple(value) for key, value in index.items()}


def _stored_document(sidecar: Path, *, root: Path) -> StoredDocument | None:
    try:
        payload: object = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusStoreError(f"unreadable parser sidecar: {sidecar}") from exc
    if not isinstance(payload, Mapping):
        return None
    record = cast("Mapping[str, Any]", payload)
    document_id = record.get("source_document_id")
    markdown_path = record.get("markdown_path")
    input_path = record.get("input_path")
    if not isinstance(document_id, str) or not isinstance(markdown_path, str):
        return None
    if record.get("status") != "succeeded":
        return None
    if not isinstance(input_path, str) or not input_path.strip():
        raise CorpusStoreError(f"parser sidecar has no input_path: {sidecar}")
    recorded_sha256 = record.get("source_sha256")
    if not isinstance(recorded_sha256, str):
        raise CorpusStoreError(f"parser sidecar has no source_sha256: {sidecar}")
    candidate_id = record.get("candidate_id")
    return StoredDocument(
        source_document_id=document_id,
        candidate_id=candidate_id if isinstance(candidate_id, str) else "",
        pdf_path=Path(input_path),
        markdown_path=_resolve_markdown_path(markdown_path, sidecar=sidecar, root=root),
        recorded_pdf_sha256=recorded_sha256,
        quality_flags=_quality_flags(record.get("quality_flags")),
    )


def _resolve_markdown_path(value: str, *, sidecar: Path, root: Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    # Sidecars record the markdown path relative to their own parse root.  The
    # sibling form is authoritative when it exists, because a tranche and the
    # lineage tree can spell the same relative path differently.
    sibling = sidecar.parent / candidate.name
    if sibling.is_file():
        return sibling
    return root / candidate


def _quality_flags(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in cast("list[object]", value) if isinstance(item, str))


def _verdict_records(source: Path) -> tuple[VerdictRecord, ...]:
    if source.is_dir():
        raise CorpusStoreError(f"verdict source must be a file: {source}")
    rows: list[object]
    if source.suffix == ".jsonl":
        rows = [
            cast("object", json.loads(line))
            for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        payload: object = json.loads(source.read_text(encoding="utf-8"))
        rows = _verdict_rows_from_object(payload, source=source)
    records: list[VerdictRecord] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        record = _verdict_record(cast("Mapping[str, Any]", row), source=source)
        if record is not None:
            records.append(record)
    return tuple(records)


def _verdict_rows_from_object(payload: object, *, source: Path) -> list[object]:
    if not isinstance(payload, Mapping):
        raise CorpusStoreError(f"verdict file must be an object or JSONL: {source}")
    record = cast("Mapping[str, Any]", payload)
    # Container keys are enumerated positively; the sixth-successor purchase
    # gate spells its rows under "results".  An unknown container refuses
    # rather than reporting an empty verdict set.
    for key in ("records", "verdicts", "adjudications", "results"):
        rows = record.get(key)
        if isinstance(rows, list):
            return list(cast("list[object]", rows))
    raise CorpusStoreError(
        f"verdict file has no records, verdicts, adjudications, or results "
        f"list: {source}"
    )


def _verdict_record(
    row: Mapping[str, Any],
    *,
    source: Path,
) -> VerdictRecord | None:
    document_id = row.get("source_document_id")
    if not isinstance(document_id, str):
        return None
    verdict = _first_string(row, VERDICT_FIELD_SPELLINGS)
    if verdict is None:
        # A known spelling present but null is a *recorded absence* of a
        # verdict: the row carries no verdict, and any model-visible document
        # relying on it will fail the freeze's no-verdict check.  A row with no
        # known spelling at all is different — it may be hiding a third
        # spelling — and stays a hard refusal so a new spelling cannot enter
        # unnoticed.
        if any(name in row for name in VERDICT_FIELD_SPELLINGS):
            return None
        raise CorpusStoreError(
            f"{source.name}: verdict row for {document_id} carries none of the "
            f"known verdict spellings {', '.join(VERDICT_FIELD_SPELLINGS)}"
        )
    if verdict not in KNOWN_VERDICTS:
        raise CorpusStoreError(
            f"{source.name}: unknown byte-role verdict '{verdict}' for "
            f"{document_id}; classify it before it can be admitted or refused"
        )
    return VerdictRecord(
        source_document_id=document_id,
        verdict=verdict,
        certified_role=_first_string(row, CERTIFIED_ROLE_SPELLINGS),
        validation_basis=_first_string(row, BASIS_FIELD_SPELLINGS),
        source=source.name,
        claimed_role=_first_string(row, CLAIMED_ROLE_SPELLINGS),
    )


def _first_string(row: Mapping[str, Any], names: Iterable[str]) -> str | None:
    for name in names:
        value = row.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None
