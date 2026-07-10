"""Reusable synthetic fixtures for offline benchmark tests.

The cases in this module are intentionally synthetic. They exercise the
benchmark's expected edge cases without redistributing public court documents or
depending on live case.dev responses.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

REQUIRED_PIPELINE_LOG_FIELDS = (
    "case_id",
    "candidate_id",
    "stage",
    "source_provider",
    "source_document_id",
    "source_hash",
    "decision",
    "exclusion_reason",
    "elapsed_ms",
    "request_count",
    "estimated_cost",
)


class FixtureEdgeCase(StrEnum):
    """Edge cases the shared golden corpus must keep covering."""

    CLEAN_GRANT = "clean_grant"
    CLEAN_DENIAL = "clean_denial"
    MIXED_DISPOSITION = "mixed_disposition"
    AMENDED_COMPLAINT = "amended_complaint"
    MULTIPLE_DEFENDANTS = "multiple_defendants"
    GROUPED_DEFENDANTS = "grouped_defendants"
    AMBIGUOUS_ORDER = "ambiguous_order"
    FALSE_POSITIVE_DISMISSAL = "false_positive_dismissal"
    RELATED_CASES = "related_cases"
    OCR_NOISE = "ocr_noise"
    MALFORMED_MODEL_OUTPUT = "malformed_model_output"
    MINIMAL_MANIFEST = "minimal_manifest"


@dataclass(frozen=True, slots=True)
class FixtureDocketEntry:
    """Minimal docket line needed by discovery and linkage tests."""

    entry_number: int
    filed_on: str
    text: str

    def __post_init__(self) -> None:
        if self.entry_number <= 0:
            raise ValueError("entry_number must be positive")
        if not self.filed_on:
            raise ValueError("filed_on is required")
        if not self.text.strip():
            raise ValueError("text is required")


@dataclass(frozen=True, slots=True)
class FixtureDocument:
    """Synthetic document text with enough metadata for source hashing."""

    document_id: str
    docket_entry_number: int
    source_provider: str
    text: str
    is_decision_document: bool = False

    def __post_init__(self) -> None:
        if not self.document_id.strip():
            raise ValueError("document_id is required")
        if self.docket_entry_number <= 0:
            raise ValueError("docket_entry_number must be positive")
        if not self.source_provider.strip():
            raise ValueError("source_provider is required")
        if not self.text.strip():
            raise ValueError("text is required")

    @property
    def source_hash(self) -> str:
        payload = {
            "document_id": self.document_id,
            "docket_entry_number": self.docket_entry_number,
            "source_provider": self.source_provider,
            "text": self.text,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """Synthetic case fixture shared by pytest and future fixture E2E runs."""

    case_id: str
    title: str
    edge_case: FixtureEdgeCase
    docket_entries: tuple[FixtureDocketEntry, ...]
    documents: tuple[FixtureDocument, ...]
    expected_decision: str
    candidate_id: str | None = None
    expected_exclusion_reason: str | None = None
    related_family_id: str | None = None
    malformed_model_output: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if not self.docket_entries:
            raise ValueError("at least one docket entry is required")
        if not self.documents:
            raise ValueError("at least one document is required")
        if not self.expected_decision.strip():
            raise ValueError("expected_decision is required")

    @property
    def stable_candidate_id(self) -> str:
        return self.candidate_id or f"cand_{self.case_id}"

    @property
    def primary_source(self) -> FixtureDocument:
        return self.documents[0]

    @property
    def source_hash(self) -> str:
        encoded = json.dumps(
            [document.source_hash for document in self.documents],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def to_record(self) -> dict[str, object]:
        record = asdict(self)
        record["edge_case"] = self.edge_case.value
        record["candidate_id"] = self.stable_candidate_id
        record["source_hash"] = self.source_hash
        return record


def _entry(entry_number: int, filed_on: str, text: str) -> FixtureDocketEntry:
    return FixtureDocketEntry(entry_number=entry_number, filed_on=filed_on, text=text)


def _doc(
    document_id: str,
    docket_entry_number: int,
    text: str,
    *,
    is_decision_document: bool = False,
) -> FixtureDocument:
    return FixtureDocument(
        document_id=document_id,
        docket_entry_number=docket_entry_number,
        source_provider="synthetic-case-dev",
        text=text,
        is_decision_document=is_decision_document,
    )


_GOLDEN_CASES: tuple[GoldenCase, ...] = (
    GoldenCase(
        case_id="fixture_clean_grant",
        title="Alpha Purchaser v. Northstar Labs",
        edge_case=FixtureEdgeCase.CLEAN_GRANT,
        docket_entries=(
            _entry(18, "2026-01-08", "Defendant's motion to dismiss filed."),
            _entry(24, "2026-02-05", "Opposition to motion to dismiss filed."),
            _entry(31, "2026-04-22", "Opinion granting motion to dismiss."),
        ),
        documents=(
            _doc(
                "fixture-clean-grant-motion",
                18,
                "Defendant moves to dismiss the contract and fraud claims.",
            ),
            _doc(
                "fixture-clean-grant-decision",
                31,
                "The motion to dismiss is granted as to all challenged claims.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_clean_full_grant",
    ),
    GoldenCase(
        case_id="fixture_clean_denial",
        title="Harbor Clinic v. Meridian Health",
        edge_case=FixtureEdgeCase.CLEAN_DENIAL,
        docket_entries=(
            _entry(12, "2026-01-12", "Motion to dismiss complaint."),
            _entry(19, "2026-02-09", "Response in opposition."),
            _entry(27, "2026-04-24", "Order denying motion to dismiss."),
        ),
        documents=(
            _doc("fixture-clean-denial-motion", 12, "Defendant challenges Count I."),
            _doc(
                "fixture-clean-denial-decision",
                27,
                "The motion to dismiss is denied.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_clean_denial",
    ),
    GoldenCase(
        case_id="fixture_mixed_disposition",
        title="Riverfront Fund v. Option Metrics LLC",
        edge_case=FixtureEdgeCase.MIXED_DISPOSITION,
        docket_entries=(
            _entry(22, "2026-01-18", "Motion to dismiss Counts I through IV."),
            _entry(34, "2026-04-26", "Memorandum and order granting in part."),
        ),
        documents=(
            _doc(
                "fixture-mixed-motion",
                22,
                "Defendant moves to dismiss four separate statutory counts.",
            ),
            _doc(
                "fixture-mixed-decision",
                34,
                "Counts I and III survive; Counts II and IV are dismissed.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_mixed_grant_and_denial",
    ),
    GoldenCase(
        case_id="fixture_leave_to_amend",
        title="Fields v. Redline Software Inc.",
        edge_case=FixtureEdgeCase.AMENDED_COMPLAINT,
        docket_entries=(
            _entry(15, "2026-01-21", "Motion to dismiss first amended complaint."),
            _entry(29, "2026-04-28", "Order granting dismissal with leave to amend."),
        ),
        documents=(
            _doc(
                "fixture-amend-motion",
                15,
                "The motion challenges the amended pleading under Rule 12(b)(6).",
            ),
            _doc(
                "fixture-amend-decision",
                29,
                "The claim is dismissed without prejudice and plaintiff may amend.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_full_grant_with_amendment_opportunity",
    ),
    GoldenCase(
        case_id="fixture_multiple_defendants",
        title="Luna Markets v. Apex Holdings",
        edge_case=FixtureEdgeCase.MULTIPLE_DEFENDANTS,
        docket_entries=(
            _entry(
                41,
                "2026-01-25",
                "Motion to dismiss by Apex and individual officers.",
            ),
            _entry(55, "2026-04-30", "Order on defendants' motion to dismiss."),
        ),
        documents=(
            _doc(
                "fixture-multi-def-motion",
                41,
                "Apex, Gray, and Patel jointly move against securities claims.",
            ),
            _doc(
                "fixture-multi-def-decision",
                55,
                "Claims against Gray are dismissed; Apex and Patel remain.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_multiple_defendant_split",
    ),
    GoldenCase(
        case_id="fixture_grouped_defendants",
        title="Novak v. County Board",
        edge_case=FixtureEdgeCase.GROUPED_DEFENDANTS,
        docket_entries=(
            _entry(33, "2026-02-01", "County defendants move to dismiss."),
            _entry(44, "2026-05-02", "Order granting county defendants' motion."),
        ),
        documents=(
            _doc(
                "fixture-grouped-def-motion",
                33,
                "The sheriff, county, and board move as the county defendants.",
            ),
            _doc(
                "fixture-grouped-def-decision",
                44,
                "The county defendants' motion is granted in full.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_grouped_defendant_unit",
    ),
    GoldenCase(
        case_id="fixture_ambiguous_order",
        title="Chen v. Metro Lending",
        edge_case=FixtureEdgeCase.AMBIGUOUS_ORDER,
        docket_entries=(
            _entry(17, "2026-02-07", "Motion to dismiss."),
            _entry(28, "2026-05-04", "Minute order: motion granted in part."),
        ),
        documents=(
            _doc(
                "fixture-ambiguous-motion",
                17,
                "Defendant challenges several counts.",
            ),
            _doc(
                "fixture-ambiguous-order",
                28,
                "Motion granted in part for reasons stated on the record.",
                is_decision_document=True,
            ),
        ),
        expected_decision="route_to_review_or_exclude",
        expected_exclusion_reason="ambiguous_disposition",
    ),
    GoldenCase(
        case_id="fixture_false_positive_dismissal",
        title="Owen v. Summit Retail",
        edge_case=FixtureEdgeCase.FALSE_POSITIVE_DISMISSAL,
        docket_entries=(
            _entry(9, "2026-02-11", "Notice of voluntary dismissal of Doe defendants."),
            _entry(10, "2026-02-12", "Dismissal entered as to Doe defendants only."),
        ),
        documents=(
            _doc(
                "fixture-false-positive-notice",
                9,
                "Plaintiff voluntarily dismisses unnamed Doe defendants.",
            ),
        ),
        expected_decision="exclude_false_positive_docket_match",
        expected_exclusion_reason="not_motion_to_dismiss",
    ),
    GoldenCase(
        case_id="fixture_related_cases",
        title="In re Atlas Billing Litigation",
        edge_case=FixtureEdgeCase.RELATED_CASES,
        docket_entries=(
            _entry(61, "2026-02-19", "Motion to dismiss master complaint."),
            _entry(77, "2026-05-05", "Order adopting related case reasoning."),
        ),
        documents=(
            _doc(
                "fixture-related-motion",
                61,
                "Defendants move to dismiss claims overlapping related actions.",
            ),
            _doc(
                "fixture-related-decision",
                77,
                "The court adopts its related-case analysis and grants the motion.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_with_related_family_flag",
        related_family_id="synthetic-atlas-billing",
    ),
    GoldenCase(
        case_id="fixture_ocr_noise",
        title="Diaz v. Lakeview Finance",
        edge_case=FixtureEdgeCase.OCR_NOISE,
        docket_entries=(
            _entry(16, "2026-02-23", "Motion to dismiss complaint."),
            _entry(26, "2026-05-06", "Opinion on motion to dismiss."),
        ),
        documents=(
            _doc(
                "fixture-ocr-motion",
                16,
                "Defendant's m0t10n t0 dism1ss challenges Count II.",
            ),
            _doc(
                "fixture-ocr-decision",
                26,
                "After correcting OCR noise, Count II is dismissed.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_with_ocr_noise_flag",
    ),
    GoldenCase(
        case_id="fixture_malformed_model_output",
        title="Keller v. Prime Ledger",
        edge_case=FixtureEdgeCase.MALFORMED_MODEL_OUTPUT,
        docket_entries=(
            _entry(20, "2026-03-01", "Motion to dismiss."),
            _entry(36, "2026-05-07", "Order denying motion to dismiss."),
        ),
        documents=(
            _doc("fixture-malformed-motion", 20, "Defendant moves to dismiss Count I."),
            _doc(
                "fixture-malformed-decision",
                36,
                "The motion is denied.",
                is_decision_document=True,
            ),
        ),
        expected_decision="include_parser_failure_fixture",
        malformed_model_output='{"unit_id": "u1", "probability": 1.4',
    ),
    GoldenCase(
        case_id="fixture_minimal_manifest",
        title="Synthetic Manifest Fixture",
        edge_case=FixtureEdgeCase.MINIMAL_MANIFEST,
        docket_entries=(
            _entry(1, "2026-03-05", "Synthetic manifest and freeze smoke fixture."),
        ),
        documents=(
            _doc(
                "fixture-minimal-manifest",
                1,
                "Fixture used for manifest and hash validation tests.",
            ),
        ),
        expected_decision="manifest_freeze_smoke_fixture",
    ),
)

_GOLDEN_CASES_BY_ID = {case.case_id: case for case in _GOLDEN_CASES}


def iter_golden_cases() -> tuple[GoldenCase, ...]:
    """Return all synthetic golden cases in stable order."""

    return _GOLDEN_CASES


def golden_case_ids() -> tuple[str, ...]:
    """Return stable golden-case identifiers."""

    return tuple(case.case_id for case in _GOLDEN_CASES)


def get_golden_case(case_id: str) -> GoldenCase:
    """Return a single golden case by ID."""

    try:
        return _GOLDEN_CASES_BY_ID[case_id]
    except KeyError as exc:
        known = ", ".join(golden_case_ids())
        message = f"Unknown golden case {case_id!r}; known cases: {known}"
        raise KeyError(message) from exc


def pipeline_log_context(
    case: GoldenCase,
    *,
    stage: str,
    decision: str,
    exclusion_reason: str | None = None,
    elapsed_ms: int = 0,
    request_count: int = 0,
    estimated_cost: float = 0.0,
) -> dict[str, object]:
    """Build canonical structured-log context for fixture pipeline tests."""

    if not stage.strip():
        raise ValueError("stage is required")
    if not decision.strip():
        raise ValueError("decision is required")
    if elapsed_ms < 0:
        raise ValueError("elapsed_ms cannot be negative")
    if request_count < 0:
        raise ValueError("request_count cannot be negative")
    if estimated_cost < 0:
        raise ValueError("estimated_cost cannot be negative")

    primary_source = case.primary_source
    return {
        "case_id": case.case_id,
        "candidate_id": case.stable_candidate_id,
        "stage": stage,
        "source_provider": primary_source.source_provider,
        "source_document_id": primary_source.document_id,
        "source_hash": case.source_hash,
        "decision": decision,
        "exclusion_reason": exclusion_reason,
        "elapsed_ms": elapsed_ms,
        "request_count": request_count,
        "estimated_cost": estimated_cost,
    }
