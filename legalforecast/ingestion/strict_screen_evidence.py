"""Canonical validation for accepted CourtListener strict-screen evidence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any, cast


class StrictScreenEvidenceError(ValueError):
    """Raised when purported strict-screen evidence is not production-shaped."""


def validate_strict_screen_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_candidate_id: str | None = None,
) -> None:
    """Validate one accepted record emitted by the production strict screen.

    The union stage calls this same validator before allowing an authenticated
    source correction to promote an active candidate. This prevents a manifest
    pin from blessing merely plausible-looking dates, entries, or linkage data.
    """

    candidate = _mapping(evidence.get("candidate"), "candidate")
    docket_id = _text(candidate.get("docket_id"), "candidate.docket_id")
    if _text(candidate.get("candidate_key"), "candidate.candidate_key") != docket_id:
        raise StrictScreenEvidenceError("candidate key does not match docket ID")
    metadata = _mapping(candidate.get("metadata"), "candidate.metadata")
    metadata_case_id = _text(
        metadata.get("case_id"),
        "candidate.metadata.case_id",
    )
    for field in ("case_name", "court", "docket_number"):
        _text(metadata.get(field), f"candidate.metadata.{field}")
    if expected_candidate_id is not None:
        evidence_candidate_id = _text(evidence.get("candidate_id"), "candidate_id")
        if evidence_candidate_id != expected_candidate_id:
            raise StrictScreenEvidenceError(
                "strict-screen evidence belongs to a different candidate"
            )
        expected_docket_id = expected_candidate_id.removeprefix("courtlistener-docket-")
        if docket_id != expected_docket_id:
            raise StrictScreenEvidenceError(
                "strict-screen docket ID does not match its candidate"
            )
        if metadata_case_id not in {
            expected_candidate_id,
            expected_docket_id,
        }:
            raise StrictScreenEvidenceError(
                "strict-screen case ID does not match its candidate"
            )

    ai = _mapping(evidence.get("ai"), "ai")
    target_numbers = _text_sequence(
        ai.get("target_motion_entry_numbers"),
        "ai.target_motion_entry_numbers",
    )
    if len(target_numbers) != 1:
        raise StrictScreenEvidenceError(
            "ai.target_motion_entry_numbers must contain exactly one entry"
        )
    decision_numbers = _text_sequence(
        ai.get("decision_entry_numbers"),
        "ai.decision_entry_numbers",
    )

    disposition_date = _iso_date(
        evidence.get("first_written_mtd_disposition_date"),
        "first_written_mtd_disposition_date",
    )
    anchor_date = _iso_date(
        evidence.get("eligibility_anchor_date"),
        "eligibility_anchor_date",
    )
    if disposition_date < anchor_date:
        raise StrictScreenEvidenceError(
            "first written MTD disposition predates the eligibility anchor"
        )

    entries_value = evidence.get("selected_entries")
    if not isinstance(entries_value, list) or not entries_value:
        raise StrictScreenEvidenceError("selected_entries must be a non-empty list")
    entries = cast(list[object], entries_value)
    row_ids: set[str] = set()
    entry_number_to_row_id: dict[str, str] = {}
    for index, value in enumerate(entries, start=1):
        entry = _mapping(value, f"selected_entries[{index}]")
        row_id = _text(entry.get("row_id"), f"selected_entries[{index}].row_id")
        if row_id in row_ids:
            raise StrictScreenEvidenceError("selected_entries repeat a row ID")
        row_ids.add(row_id)
        entry_number_value = entry.get("entry_number")
        if entry_number_value is not None:
            entry_number = _text(
                entry_number_value,
                f"selected_entries[{index}].entry_number",
            )
            if entry_number in entry_number_to_row_id:
                raise StrictScreenEvidenceError(
                    "selected_entries repeat an entry number"
                )
            entry_number_to_row_id[entry_number] = row_id
        filed_at = entry.get("filed_at")
        if filed_at is not None:
            _text(filed_at, f"selected_entries[{index}].filed_at")
        _text(entry.get("text"), f"selected_entries[{index}].text")
        role = _text(entry.get("role"), f"selected_entries[{index}].role")
        if role not in {
            "mtd_notice",
            "mtd_memorandum",
            "opposition",
            "reply",
            "exhibit",
            "decision",
            "other",
        }:
            raise StrictScreenEvidenceError(
                f"selected_entries[{index}].role is invalid"
            )
        _string_list(
            entry.get("restriction_markers"),
            f"selected_entries[{index}].restriction_markers",
            allow_empty=True,
        )
        documents_value = entry.get("documents")
        if not isinstance(documents_value, list):
            raise StrictScreenEvidenceError(
                f"selected_entries[{index}].documents must be a list"
            )
        for document_index, document_value in enumerate(
            cast(list[object], documents_value), start=1
        ):
            document = _mapping(
                document_value,
                f"selected_entries[{index}].documents[{document_index}]",
            )
            _text(
                document.get("kind"),
                f"selected_entries[{index}].documents[{document_index}].kind",
            )
            _optional_text(
                document.get("description"),
                f"selected_entries[{index}].documents[{document_index}].description",
            )
            _optional_text(
                document.get("href"),
                f"selected_entries[{index}].documents[{document_index}].href",
            )
            _optional_text(
                document.get("action_label"),
                f"selected_entries[{index}].documents[{document_index}].action_label",
            )
            _boolean(
                document.get("pacer_only"),
                f"selected_entries[{index}].documents[{document_index}].pacer_only",
            )
            _boolean(
                document.get("freely_available"),
                f"selected_entries[{index}].documents[{document_index}]"
                ".freely_available",
            )
            _string_list(
                document.get("restriction_markers"),
                f"selected_entries[{index}].documents[{document_index}]"
                ".restriction_markers",
                allow_empty=True,
            )

    if not set(target_numbers).issubset(entry_number_to_row_id):
        raise StrictScreenEvidenceError(
            "target motion entry is absent from selected_entries"
        )
    if not set(decision_numbers).issubset(entry_number_to_row_id):
        raise StrictScreenEvidenceError(
            "decision entry is absent from selected_entries"
        )

    screen = _mapping(evidence.get("mtd_decision_screen"), "mtd_decision_screen")
    if screen.get("status") != "accepted_strict_civil_mtd_decision":
        raise StrictScreenEvidenceError("MTD decision screen is not strictly accepted")
    if _string_list(
        screen.get("exclusion_reasons"),
        "mtd_decision_screen.exclusion_reasons",
        allow_empty=True,
    ):
        raise StrictScreenEvidenceError("MTD decision screen contains exclusions")
    screen_decisions_value = screen.get("decision_entries")
    if not isinstance(screen_decisions_value, list) or not screen_decisions_value:
        raise StrictScreenEvidenceError(
            "mtd_decision_screen.decision_entries must be a non-empty list"
        )
    screen_decisions = cast(list[object], screen_decisions_value)
    decision_count = screen.get("actual_mtd_decision_entry_count")
    if (
        not isinstance(decision_count, int)
        or isinstance(decision_count, bool)
        or decision_count < 1
        or decision_count != len(screen_decisions)
    ):
        raise StrictScreenEvidenceError("MTD decision screen count does not match")
    screened_decision_numbers: set[str] = set()
    for index, value in enumerate(screen_decisions, start=1):
        decision = _mapping(value, f"mtd_decision_screen.decision_entries[{index}]")
        if decision.get("actual_mtd_decision") is not True:
            raise StrictScreenEvidenceError(
                "MTD decision screen includes a non-decision"
            )
        screened_decision_numbers.add(
            _text(
                decision.get("entry_number"),
                f"mtd_decision_screen.decision_entries[{index}].entry_number",
            )
        )
    if not set(decision_numbers).issubset(screened_decision_numbers):
        raise StrictScreenEvidenceError(
            "AI-selected decision is absent from the strict decision screen"
        )

    linkage = _mapping(evidence.get("motion_linkage"), "motion_linkage")
    if _text(linkage.get("candidate_id"), "motion_linkage.candidate_id") != docket_id:
        raise StrictScreenEvidenceError(
            "motion_linkage candidate ID does not match its docket"
        )
    allowed_case_ids = {docket_id, metadata_case_id}
    if expected_candidate_id is not None:
        allowed_case_ids.add(expected_candidate_id)
    if _text(linkage.get("case_id"), "motion_linkage.case_id") not in allowed_case_ids:
        raise StrictScreenEvidenceError(
            "motion_linkage case ID does not match its candidate"
        )
    if linkage.get("is_clean") is not True:
        raise StrictScreenEvidenceError("motion_linkage is not clean")
    if _object_list(
        linkage.get("exclusion_entries"),
        "motion_linkage.exclusion_entries",
        allow_empty=True,
    ):
        raise StrictScreenEvidenceError("motion_linkage contains exclusions")
    links = _object_list(linkage.get("links"), "motion_linkage.links")
    target_row_ids = {entry_number_to_row_id[number] for number in target_numbers}
    decision_row_ids = {entry_number_to_row_id[number] for number in decision_numbers}
    linked_motion_ids: set[str] = set()
    linked_decision_ids: set[str] = set()
    for index, link in enumerate(links, start=1):
        if (
            _text(
                link.get("candidate_id"),
                f"motion_linkage.links[{index}].candidate_id",
            )
            != docket_id
        ):
            raise StrictScreenEvidenceError(
                "motion_linkage link candidate ID does not match its docket"
            )
        if (
            _text(
                link.get("case_id"),
                f"motion_linkage.links[{index}].case_id",
            )
            not in allowed_case_ids
        ):
            raise StrictScreenEvidenceError(
                "motion_linkage link case ID does not match its candidate"
            )
        linked_motion_ids.update(
            _text_sequence(
                link.get("motion_entry_ids"),
                f"motion_linkage.links[{index}].motion_entry_ids",
            )
        )
        linked_decision_ids.update(
            _text_sequence(
                link.get("disposition_entry_ids"),
                f"motion_linkage.links[{index}].disposition_entry_ids",
            )
        )
        _text_sequence(
            link.get("linkage_basis"),
            f"motion_linkage.links[{index}].linkage_basis",
        )
    if not target_row_ids.issubset(linked_motion_ids):
        raise StrictScreenEvidenceError(
            "motion_linkage does not bind the selected target motion"
        )
    if not decision_row_ids.issubset(linked_decision_ids):
        raise StrictScreenEvidenceError(
            "motion_linkage does not bind the selected disposition"
        )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise StrictScreenEvidenceError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StrictScreenEvidenceError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise StrictScreenEvidenceError(f"{label} must be a string or null")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise StrictScreenEvidenceError(f"{label} must be a boolean")
    return value


def _iso_date(value: object, label: str) -> date:
    text = _text(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as error:
        raise StrictScreenEvidenceError(f"{label} must be an ISO date") from error
    if parsed.isoformat() != text:
        raise StrictScreenEvidenceError(f"{label} must be a canonical ISO date")
    return parsed


def _string_list(value: object, label: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise StrictScreenEvidenceError(f"{label} must be a list")
    records = cast(list[object], value)
    if not allow_empty and not records:
        raise StrictScreenEvidenceError(f"{label} must not be empty")
    if not all(isinstance(item, str) for item in records):
        raise StrictScreenEvidenceError(f"{label} must contain only strings")
    return tuple(cast(list[str], records))


def _text_sequence(value: object, label: str) -> tuple[str, ...]:
    records = _string_list(value, label, allow_empty=False)
    if any(not item.strip() for item in records) or len(set(records)) != len(records):
        raise StrictScreenEvidenceError(
            f"{label} must contain unique non-empty strings"
        )
    return tuple(item.strip() for item in records)


def _object_list(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise StrictScreenEvidenceError(f"{label} must be a list")
    records = cast(list[object], value)
    if not allow_empty and not records:
        raise StrictScreenEvidenceError(f"{label} must not be empty")
    return tuple(_mapping(record, f"{label}[]") for record in records)
