"""Build 3ak-style blind/eyes audit bundles from an already-parsed docket.

Pass 1 sees only the returned ``BlindBundle``. Decision text is stored on
``EyesBundle`` and is never copied into chronology rows.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from legalforecast.document_need.types import (
    BlindBundle,
    Chronology,
    ChronologyEntry,
    DecisionText,
    DocketDocument,
    EyesBundle,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
)

_PAGE_COUNT_RE = re.compile(r"\b(\d{1,4})\s*(?:pages?|pgs?)\b", re.IGNORECASE)
_NARRATIVE_CAP = 2000


class DocumentNeedPrepError(ValueError):
    """Raised when a docket cannot be turned into a blind/eyes bundle pair."""


@dataclass(frozen=True, slots=True)
class AuditBundles:
    """Paired pass-1 and pass-2 inputs for one candidate."""

    blind: BlindBundle
    eyes: EyesBundle


def parse_page_count(*texts: str) -> int | None:
    """Return the first explicit page count in CourtListener document labels."""

    for text in texts:
        match = _PAGE_COUNT_RE.search(text)
        if match is not None:
            return int(match.group(1))
    return None


def prepare_audit_bundles(
    *,
    candidate_id: str,
    docket: CourtListenerWebDocketPage,
    target_motion_entries: Sequence[int],
    decision_cut_entry: int,
    decision_text: str,
    motion_markdown: Mapping[int, str],
    case_name: str | None = None,
    court: str | None = None,
    docket_number: str | None = None,
    selected_docs: Sequence[Mapping[str, object]] = (),
) -> AuditBundles:
    """Split one parsed docket into pass-1 (blind) and pass-2 (eyes) bundles."""

    _require_text(candidate_id, "candidate_id")
    _require_text(decision_text, "decision text")
    if type(decision_cut_entry) is not int or decision_cut_entry <= 0:
        raise DocumentNeedPrepError("decision_cut_entry must be a positive integer")
    chronology = Chronology(
        candidate_id=candidate_id,
        case_name=case_name,
        court=court,
        docket_number=docket_number,
        target_motion_entries=tuple(target_motion_entries),
        decision_cut_entry=decision_cut_entry,
        entries=_predecision_entries(docket, decision_cut_entry),
    )
    blind = BlindBundle(chronology=chronology, motion_markdown=dict(motion_markdown))
    digest = hashlib.sha256(decision_text.encode("utf-8")).hexdigest()
    eyes = EyesBundle(
        decision=DecisionText(
            candidate_id=candidate_id, text=decision_text, sha256=digest
        ),
        selected_docs=tuple(selected_docs),
    )
    return AuditBundles(blind=blind, eyes=eyes)


def _predecision_entries(
    docket: CourtListenerWebDocketPage, decision_cut_entry: int
) -> tuple[ChronologyEntry, ...]:
    rows: list[ChronologyEntry] = []
    seen: set[int] = set()
    for raw in docket.entries:
        entry_number = _entry_number(raw)
        if entry_number is None or entry_number >= decision_cut_entry:
            continue
        if entry_number in seen:
            raise DocumentNeedPrepError(f"duplicate docket entry {entry_number}")
        seen.add(entry_number)
        text = (raw.narrative_text or raw.text or "").strip()
        if len(text) > _NARRATIVE_CAP:
            text = text[:_NARRATIVE_CAP] + " …[truncated]"
        rows.append(
            ChronologyEntry(
                entry=entry_number,
                filed=raw.filed_at,
                text=text,
                documents=_documents(raw),
                restricted=bool(raw.restricted),
            )
        )
    rows.sort(key=lambda row: row.entry)
    if not rows:
        raise DocumentNeedPrepError("predecision chronology is empty")
    return tuple(rows)


def _documents(raw: CourtListenerWebDocketEntry) -> tuple[DocketDocument, ...]:
    documents: list[DocketDocument] = []
    for index, document in enumerate(raw.documents):
        selector = "main_document" if index == 0 else f"attachment_{index}"
        documents.append(
            DocketDocument(
                selector=selector,
                description=document.description or document.kind,
                freely_available=document.freely_available,
                pacer_only=document.pacer_only,
                page_count=parse_page_count(
                    document.kind, document.description, document.action_label or ""
                ),
                restricted=document.restricted,
            )
        )
    return tuple(documents)


def _entry_number(raw: CourtListenerWebDocketEntry) -> int | None:
    value = raw.entry_number
    if value is None:
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _require_text(value: str, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise DocumentNeedPrepError(f"{label} must be a nonempty string")
    return value
