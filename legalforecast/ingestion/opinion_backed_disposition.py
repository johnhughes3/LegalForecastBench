"""Bind public CourtListener opinions to their resolved RECAP docket entries.

CourtListener's case-law and RECAP namespaces use different docket records.  A
case-law opinion can contain the complete written disposition while the RECAP
docket exposes only a terse relationship label such as ``Order on Motion to
Dismiss``.  This module joins those two public records without treating the
opinion as model-visible pre-decision material.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, cast

from legalforecast.ingestion.courtlistener_client import CourtListenerClient
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketEntry,
    CourtListenerWebDocketPage,
    CourtListenerWebDocument,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    MtdDocketDecisionScreen,
    screen_courtlistener_docket_for_mtd_decision,
    screen_courtlistener_entry_for_mtd_decision,
)


class OpinionBackedDispositionError(ValueError):
    """Raised when an opinion cannot be bound to one docket disposition."""


@dataclass(frozen=True, slots=True)
class OpinionBackedDisposition:
    """A public opinion bound to exactly one real RECAP docket entry."""

    page: CourtListenerWebDocketPage
    screen: MtdDocketDecisionScreen
    opinion_id: str
    opinion_date: date
    decision_row_id: str
    decision_entry_number: str
    public_pdf_url: str
    plain_text_sha256: str
    disposition_excerpt: str

    def to_evidence_record(self) -> dict[str, object]:
        return {
            "schema_version": "legalforecast.opinion_backed_disposition.v1",
            "opinion_id": self.opinion_id,
            "opinion_date": self.opinion_date.isoformat(),
            "decision_row_id": self.decision_row_id,
            "decision_entry_number": self.decision_entry_number,
            "public_pdf_url": self.public_pdf_url,
            "plain_text_sha256": self.plain_text_sha256,
            "disposition_excerpt": self.disposition_excerpt,
            "screen": self.screen.to_record(),
        }


@dataclass(frozen=True, slots=True)
class FetchedOpinionBackedDisposition:
    """A bound disposition plus immutable provider-response commitments."""

    disposition: OpinionBackedDisposition
    evidence: Mapping[str, object]


def select_opinion_resolution_for_page(
    page: CourtListenerWebDocketPage,
    resolution_evidence: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Select the unique resolution whose date matches one real MTD order.

    Multiple opinion clusters can resolve to the same RECAP docket.  The
    resolver preserves them under ``additional_resolutions``; selection uses
    only frozen dates and reconstructed docket anchors, before spending the two
    CourtListener requests needed to fetch cluster/opinion content.
    """

    additional = resolution_evidence.get("additional_resolutions", [])
    if not isinstance(additional, list):
        raise OpinionBackedDispositionError(
            "opinion resolution additional_resolutions must be a list"
        )
    primary = dict(resolution_evidence)
    primary.pop("additional_resolutions", None)
    resolutions: list[Mapping[str, Any]] = [primary]
    for value in cast(list[object], additional):
        if not isinstance(value, Mapping):
            raise OpinionBackedDispositionError(
                "opinion resolution additional_resolutions must contain objects"
            )
        resolutions.append(cast(Mapping[str, Any], value))

    viable: list[Mapping[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for resolution in resolutions:
        if resolution.get("schema_version") != (
            "legalforecast.opinion_recap_resolution.v1"
        ):
            raise OpinionBackedDispositionError(
                "additional opinion resolution has an unsupported schema_version"
            )
        source = _required_mapping(resolution, "source_opinion")
        identity = (
            _required_positive_id(source, "candidate_id"),
            _required_positive_id(source, "cluster_id"),
        )
        if identity in identities:
            raise OpinionBackedDispositionError(
                "opinion resolution contains a duplicate source cluster"
            )
        identities.add(identity)
        opinion_date = _required_iso_date(source, "date_filed")
        matching_entries = tuple(
            entry
            for entry in page.entries
            if _entry_date(entry) == opinion_date and _is_mtd_disposition_anchor(entry)
        )
        if len(matching_entries) == 1:
            viable.append(resolution)
    if len(viable) != 1:
        raise OpinionBackedDispositionError(
            "resolved opinion set must identify exactly one same-day MTD "
            f"disposition; found {len(viable)}"
        )
    return viable[0]


def validate_resolved_recap_identity(
    resolution_evidence: Mapping[str, Any],
    *,
    docket_id: str,
    court_id: str | None,
    docket_number: str | None,
    case_name: str,
) -> None:
    """Fail closed if live RECAP identity drifts from the resolver commitment."""

    resolved = _required_mapping(resolution_evidence, "resolved_recap")
    expected = {
        "docket_id": _required_positive_id(resolved, "docket_id"),
        "court_id": _required_text(resolved, "court_id"),
        "docket_number": _required_text(resolved, "docket_number"),
        "case_name": _required_text(resolved, "case_name"),
    }
    live = {
        "docket_id": _positive_id_value(docket_id, "docket_id"),
        "court_id": court_id,
        "docket_number": docket_number,
        "case_name": case_name,
    }
    if expected["docket_id"] != live["docket_id"]:
        raise OpinionBackedDispositionError(
            "resolved RECAP docket id changed after resolution"
        )
    for field_name in ("court_id", "docket_number", "case_name"):
        live_value = live[field_name]
        if not isinstance(live_value, str) or not live_value.strip():
            raise OpinionBackedDispositionError(
                f"live resolved RECAP {field_name} is missing"
            )
        if _identity_text(expected[field_name]) != _identity_text(live_value):
            raise OpinionBackedDispositionError(
                f"resolved RECAP {field_name} changed after resolution"
            )


def fetch_and_bind_public_opinion(
    client: CourtListenerClient,
    *,
    page: CourtListenerWebDocketPage,
    resolved_recap_docket_id: str,
    resolution_evidence: Mapping[str, Any],
) -> FetchedOpinionBackedDisposition:
    """Revalidate frozen resolver evidence against live CourtListener records."""

    schema = resolution_evidence.get("schema_version")
    if schema != "legalforecast.opinion_recap_resolution.v1":
        raise OpinionBackedDispositionError(
            "opinion resolution evidence has an unsupported schema_version"
        )
    resolved = _required_mapping(resolution_evidence, "resolved_recap")
    frozen_resolved_id = _required_positive_id(resolved, "docket_id")
    normalized_resolved_id = _positive_id_value(
        resolved_recap_docket_id,
        "resolved_recap_docket_id",
    )
    if frozen_resolved_id != normalized_resolved_id:
        raise OpinionBackedDispositionError(
            "opinion resolution resolved RECAP docket does not match candidate"
        )
    if page.docket_id != normalized_resolved_id:
        raise OpinionBackedDispositionError(
            "reconstructed page does not match resolved RECAP docket"
        )

    source = _required_mapping(resolution_evidence, "source_opinion")
    source_docket_id = _required_positive_id(source, "candidate_id")
    cluster_id = _required_positive_id(source, "cluster_id")
    frozen_date = _required_iso_date(source, "date_filed")
    cluster = client.get_opinion_cluster(cluster_id)
    if cluster.docket_id != source_docket_id:
        raise OpinionBackedDispositionError(
            "CourtListener cluster docket does not match frozen opinion lead"
        )
    try:
        cluster_date = date.fromisoformat(cluster.date_filed)
    except ValueError as exc:
        raise OpinionBackedDispositionError(
            "CourtListener opinion cluster has an invalid date_filed"
        ) from exc
    if cluster_date != frozen_date:
        raise OpinionBackedDispositionError(
            "CourtListener cluster date does not match frozen opinion lead"
        )
    if cluster.blocked is True:
        raise OpinionBackedDispositionError("CourtListener opinion cluster is blocked")

    declared_sub_opinions = _declared_sub_opinions(source)
    declared_ids = tuple(item["opinion_id"] for item in declared_sub_opinions)
    if cluster.sub_opinion_ids != declared_ids:
        raise OpinionBackedDispositionError(
            "CourtListener cluster sub-opinions do not match frozen resolver evidence"
        )
    if len(cluster.sub_opinion_ids) != 1:
        raise OpinionBackedDispositionError(
            "opinion-backed disposition requires exactly one sub-opinion"
        )
    declared = declared_sub_opinions[0]
    opinion = client.get_opinion(cluster.sub_opinion_ids[0])
    if opinion.cluster_id != cluster_id:
        raise OpinionBackedDispositionError(
            "CourtListener sub-opinion cluster does not match requested cluster"
        )
    for field_name, live_value in (
        ("absolute_url", opinion.absolute_url),
        ("download_url", opinion.download_url),
        ("local_path", opinion.local_path),
    ):
        frozen_value = declared.get(field_name)
        if frozen_value is not None and frozen_value != live_value:
            raise OpinionBackedDispositionError(
                f"CourtListener sub-opinion {field_name} changed after resolution"
            )
    if opinion.plain_text is None or opinion.local_path is None:
        raise OpinionBackedDispositionError(
            "CourtListener sub-opinion lacks public text or PDF path"
        )

    disposition = bind_public_opinion_to_docket(
        page,
        opinion_id=opinion.opinion_id,
        opinion_date=cluster_date,
        plain_text=opinion.plain_text,
        local_path=opinion.local_path,
    )
    return FetchedOpinionBackedDisposition(
        disposition=disposition,
        evidence={
            **disposition.to_evidence_record(),
            "source_opinion_docket_id": source_docket_id,
            "cluster_id": cluster.cluster_id,
            "opinion_id": opinion.opinion_id,
            "cluster_response_sha256": _record_sha256(cluster.raw),
            "opinion_response_sha256": _record_sha256(opinion.raw),
        },
    )


def public_opinion_pdf_url(local_path: str) -> str | None:
    """Normalize one CourtListener opinion ``local_path`` to public storage.

    Only relative PDF paths are accepted.  Query strings, fragments, encoded
    traversal, whitespace, credentials, and alternate origins fail closed.
    """

    raw = local_path.strip()
    if not raw or raw != local_path or "\\" in raw:
        return None
    if any(character.isspace() or ord(character) < 32 for character in raw):
        return None
    parsed = urllib.parse.urlparse(raw)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or parsed.params
    ):
        return None
    path = parsed.path.lstrip("/")
    for _ in range(len(path) + 1):
        decoded = urllib.parse.unquote(path)
        if decoded == path:
            break
        path = decoded
    else:
        return None
    if not path or "\\" in path:
        return None
    if any(character.isspace() or ord(character) < 32 for character in path):
        return None
    if any(segment in {"", ".", ".."} for segment in path.split("/")):
        return None
    if not path.casefold().endswith(".pdf"):
        return None
    return f"https://storage.courtlistener.com/{path}"


def bind_public_opinion_to_docket(
    page: CourtListenerWebDocketPage,
    *,
    opinion_id: str,
    opinion_date: date,
    plain_text: str,
    local_path: str,
) -> OpinionBackedDisposition:
    """Attach one public opinion to a unique same-day MTD disposition row.

    The original docket must already identify a unique same-day MTD order.  The
    opinion supplies the missing disposition language and a free decision PDF;
    it does not invent a docket entry or choose among ambiguous candidates.
    """

    normalized_opinion_id = opinion_id.strip()
    if not normalized_opinion_id.isdecimal() or int(normalized_opinion_id) <= 0:
        raise OpinionBackedDispositionError("opinion_id must be a positive integer")
    normalized_text = plain_text.strip()
    if not normalized_text:
        raise OpinionBackedDispositionError("opinion plain_text is required")
    disposition_excerpt = verbatim_mtd_disposition_excerpt(normalized_text)
    if disposition_excerpt is None:
        raise OpinionBackedDispositionError(
            "public opinion text does not prove an actual MTD disposition"
        )
    pdf_url = public_opinion_pdf_url(local_path)
    if pdf_url is None:
        raise OpinionBackedDispositionError(
            "opinion does not expose a safe public CourtListener PDF path"
        )

    candidates = tuple(
        entry
        for entry in page.entries
        if _entry_date(entry) == opinion_date and _is_mtd_disposition_anchor(entry)
    )
    if len(candidates) != 1:
        raise OpinionBackedDispositionError(
            "opinion date must match exactly one MTD disposition docket entry; "
            f"found {len(candidates)}"
        )
    target = candidates[0]
    if target.entry_number is None or not target.entry_number.isdecimal():
        raise OpinionBackedDispositionError(
            "opinion-backed disposition entry requires a numeric docket number"
        )
    if target.restricted:
        raise OpinionBackedDispositionError(
            "opinion-backed disposition entry carries restricted-material markers"
        )

    public_opinion_document = CourtListenerWebDocument(
        kind="main",
        description=(
            f"CourtListener Opinion {normalized_opinion_id} on Motion to Dismiss"
        ),
        href=pdf_url,
        action_label="Download PDF",
        pacer_only=False,
    )
    # A PACER-only RECAP object can be the same decision that CourtListener has
    # already published in its opinion corpus.  Retaining that duplicate would
    # manufacture a paid gap, so preserve any independently free documents and
    # replace unavailable duplicates with the public opinion PDF.
    documents = tuple(
        document for document in target.documents if document.freely_available
    )
    augmented_target = replace(
        target,
        text=f"{target.text.strip()}\n\n{disposition_excerpt}",
        documents=(*documents, public_opinion_document),
    )
    augmented_page = replace(
        page,
        entries=tuple(
            augmented_target if entry.row_id == target.row_id else entry
            for entry in page.entries
        ),
    )
    screen = screen_courtlistener_docket_for_mtd_decision(augmented_page)
    decision_row_ids = {entry.row_id for entry in screen.decision_entries}
    if target.row_id not in decision_row_ids:
        raise OpinionBackedDispositionError(
            "public opinion text does not prove an actual MTD disposition"
        )
    if not screen.strict_clean:
        reasons = ", ".join(screen.exclusion_reasons) or "unknown strict exclusion"
        raise OpinionBackedDispositionError(
            f"opinion-backed docket failed the strict clean screen: {reasons}"
        )
    return OpinionBackedDisposition(
        page=augmented_page,
        screen=screen,
        opinion_id=normalized_opinion_id,
        opinion_date=opinion_date,
        decision_row_id=target.row_id,
        decision_entry_number=target.entry_number,
        public_pdf_url=pdf_url,
        plain_text_sha256=hashlib.sha256(normalized_text.encode()).hexdigest(),
        disposition_excerpt=disposition_excerpt,
    )


def verbatim_mtd_disposition_excerpt(plain_text: str) -> str | None:
    """Return the last compact verbatim passage proving an MTD disposition.

    Full opinions often discuss unrelated criminal or jurisdictional doctrines.
    Injecting the entire decision into the docket posture screen can therefore
    create false posture exclusions.  Candidate passages are preserved exactly
    (apart from outer whitespace) and accepted only when the existing strict
    entry classifier itself recognizes an actual MTD disposition.
    """

    text = plain_text.strip()
    if not text:
        return None
    candidates: list[str] = []
    paragraphs = tuple(
        paragraph.strip()
        for paragraph in re.split(r"(?:\r?\n)[ \t]*(?:\r?\n)+", text)
        if paragraph.strip()
    )
    candidates.extend(paragraph for paragraph in paragraphs if len(paragraph) <= 4_000)

    # OCR/plain-text opinions sometimes collapse the conclusion into one very
    # long paragraph.  Sentence windows recover a compact verbatim passage while
    # retaining enough adjacent context for a split "motion" / "granted" phrase.
    sentences = tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", text)
        if sentence.strip()
    )
    for index in range(len(sentences)):
        start = max(0, index - 1)
        end = min(len(sentences), index + 2)
        window = " ".join(sentences[start:end])
        if len(window) <= 4_000:
            candidates.append(window)

    valid: list[str] = []
    for candidate in candidates:
        probe = CourtListenerWebDocketEntry(
            row_id="opinion-excerpt-probe",
            entry_number="1",
            filed_at="January 1, 2000",
            text=f"MEMORANDUM OPINION. {candidate}",
        )
        if screen_courtlistener_entry_for_mtd_decision(probe).actual_mtd_decision:
            valid.append(candidate)
    return min(valid, key=len) if valid else None


def _is_mtd_disposition_anchor(entry: CourtListenerWebDocketEntry) -> bool:
    screen = screen_courtlistener_entry_for_mtd_decision(entry)
    return screen.actual_mtd_decision or screen.exclusion_reasons == (
        "mtd_disposition_unproven",
    )


_LONG_DATE = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})")


def _entry_date(entry: CourtListenerWebDocketEntry) -> date | None:
    raw = entry.filed_at
    if raw is None:
        return None
    stripped = raw.strip()
    try:
        return date.fromisoformat(stripped[:10])
    except ValueError:
        pass
    match = _LONG_DATE.match(stripped)
    if match is None:
        return None
    try:
        return datetime.strptime(
            " ".join((match.group("month"), match.group("day"), match.group("year"))),
            "%B %d %Y",
        ).date()
    except ValueError:
        return None


def _record_sha256(record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _required_mapping(record: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = record.get(field_name)
    if not isinstance(value, Mapping):
        raise OpinionBackedDispositionError(
            f"opinion resolution {field_name} must be an object"
        )
    return cast(Mapping[str, Any], value)


def _positive_id_value(value: object, field_name: str) -> str:
    if isinstance(value, bool):
        raise OpinionBackedDispositionError(f"{field_name} must be a positive integer")
    normalized = str(value).strip()
    if not normalized.isdecimal() or normalized.startswith("0"):
        raise OpinionBackedDispositionError(f"{field_name} must be a positive integer")
    return normalized


def _required_positive_id(record: Mapping[str, Any], field_name: str) -> str:
    if field_name not in record:
        raise OpinionBackedDispositionError(
            f"opinion resolution is missing {field_name}"
        )
    return _positive_id_value(record[field_name], field_name)


def _required_text(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise OpinionBackedDispositionError(
            f"opinion resolution is missing {field_name}"
        )
    return value.strip()


def _identity_text(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _required_iso_date(record: Mapping[str, Any], field_name: str) -> date:
    value = record.get(field_name)
    if not isinstance(value, str):
        raise OpinionBackedDispositionError(
            f"opinion resolution {field_name} must be an ISO date"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise OpinionBackedDispositionError(
            f"opinion resolution {field_name} must be an ISO date"
        ) from exc


def _declared_sub_opinions(
    source: Mapping[str, Any],
) -> tuple[Mapping[str, str | None], ...]:
    value = source.get("sub_opinions")
    if not isinstance(value, list):
        raise OpinionBackedDispositionError(
            "opinion resolution sub_opinions must be a list"
        )
    records: list[Mapping[str, str | None]] = []
    for item in cast(list[object], value):
        if not isinstance(item, Mapping):
            raise OpinionBackedDispositionError(
                "opinion resolution sub_opinions must contain objects"
            )
        raw = cast(Mapping[str, object], item)
        opinion_id = _required_positive_id(raw, "opinion_id")
        normalized: dict[str, str | None] = {"opinion_id": opinion_id}
        for field_name in ("absolute_url", "download_url", "local_path"):
            field_value = raw.get(field_name)
            if field_value is not None and not isinstance(field_value, str):
                raise OpinionBackedDispositionError(
                    "opinion resolution sub-opinion "
                    f"{field_name} must be a string or null"
                )
            normalized[field_name] = field_value
        records.append(normalized)
    if len({record["opinion_id"] for record in records}) != len(records):
        raise OpinionBackedDispositionError(
            "opinion resolution contains duplicate sub-opinion ids"
        )
    return tuple(records)
