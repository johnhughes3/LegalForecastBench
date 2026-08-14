"""Two-pass document-need protocol: blind buckets, then promote-only pass 2."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, cast

from legalforecast.document_need.blindness import (
    Pass1Process,
    assert_pass1_cannot_read_decision,
)
from legalforecast.document_need.types import (
    BlindBundle,
    Chronology,
    EntryVerdict,
    EyesBundle,
    NeedBucket,
    Pass1Verdict,
    Pass2Promotion,
    Pass2Verdict,
)

PASS1_SCHEMA = "legalforecast.document_need_pass1.v1"
PASS2_SCHEMA = "legalforecast.document_need_pass2.v1"


class DocumentNeedProtocolError(ValueError):
    """Raised when a two-pass verdict cannot be applied to a chronology."""


class PassClassifier(Protocol):
    """Fixture or live classifier. Prompts are already blindness-checked."""

    def classify_pass1(self, prompt: str, *, candidate_id: str) -> Pass1Verdict: ...

    def classify_pass2(self, prompt: str, *, candidate_id: str) -> Pass2Verdict: ...


@dataclass(frozen=True, slots=True)
class MergedCaseBuckets:
    """Pass-1 buckets after pass-2 promotions, with exact model IDs."""

    candidate_id: str
    pass1_model_id: str
    pass2_model_id: str | None
    entries: tuple[EntryVerdict, ...]
    promotions: tuple[Pass2Promotion, ...]

    def by_entry(self) -> dict[int, EntryVerdict]:
        return {row.entry: row for row in self.entries}


def build_pass1_prompt(bundle: BlindBundle) -> str:
    """Render the pass-1 prompt from chronology and motion markdown only."""

    chronology = {
        "candidate_id": bundle.chronology.candidate_id,
        "case_name": bundle.chronology.case_name,
        "court": bundle.chronology.court,
        "docket_number": bundle.chronology.docket_number,
        "target_motion_entries": list(bundle.chronology.target_motion_entries),
        "decision_cut_entry": bundle.chronology.decision_cut_entry,
        "note": "Entries at or after the decision cut are excluded.",
        "entries": [
            {
                "entry": row.entry,
                "filed": row.filed,
                "text": row.text,
                "documents": [
                    {
                        "selector": document.selector,
                        "description": document.description,
                        "freely_available": document.freely_available,
                        "pacer_only": document.pacer_only,
                        "page_count": document.page_count,
                        "restricted": document.restricted,
                    }
                    for document in row.documents
                ],
            }
            for row in bundle.chronology.entries
        ],
    }
    motions = {
        str(entry): body for entry, body in sorted(bundle.motion_markdown.items())
    }
    return (
        "Classify every predecision docket entry into clearly_required, "
        "conditional, or clearly_not_required for MTD packet completeness. "
        "Use only this chronology and target-motion text. Do not use a "
        "decision or outcome.\n\n"
        f"CHRONOLOGY_JSON:\n{json.dumps(chronology, indent=2, sort_keys=True)}\n\n"
        f"MOTION_MARKDOWN_JSON:\n{json.dumps(motions, indent=2, sort_keys=True)}\n"
    )


def build_pass2_prompt(
    *,
    pass1: Pass1Verdict,
    eyes: EyesBundle,
    chronology: Chronology,
) -> str:
    """Render the pass-2 prompt. May promote entries; may not demote."""

    pass1_json = {
        "candidate_id": pass1.candidate_id,
        "model_id": pass1.model_id,
        "entries": [
            {
                "entry": row.entry,
                "bucket": row.bucket.value,
                "asserted_role": row.asserted_role,
                "rationale": row.rationale,
            }
            for row in pass1.entries
        ],
    }
    return (
        "You may PROMOTE predecision entries (clearly_not_required -> "
        "conditional or clearly_required; conditional -> clearly_required) "
        "after reading the decision. Never demote. Every promotion must cite "
        "its predecision entry number. Inclusion stays outcome-neutral.\n\n"
        f"PASS1_JSON:\n{json.dumps(pass1_json, indent=2, sort_keys=True)}\n\n"
        f"DECISION_TEXT:\n{eyes.decision.text}\n\n"
        f"PREDECISION_ENTRY_NUMBERS:\n{sorted(chronology.entry_numbers())}\n"
    )


def run_two_pass(
    *,
    blind: BlindBundle,
    eyes: EyesBundle | None,
    classifier: PassClassifier,
) -> MergedCaseBuckets:
    """Run pass 1 (blind) then optional pass 2 (promote only)."""

    process = Pass1Process(blind)
    prompt1 = build_pass1_prompt(process.bundle)
    if eyes is not None:
        assert_pass1_cannot_read_decision(prompt1, eyes.decision)
    pass1 = classifier.classify_pass1(
        prompt1, candidate_id=blind.chronology.candidate_id
    )
    _require_pass1_coverage(blind.chronology, pass1)
    if eyes is None:
        return MergedCaseBuckets(
            candidate_id=blind.chronology.candidate_id,
            pass1_model_id=pass1.model_id,
            pass2_model_id=None,
            entries=pass1.entries,
            promotions=(),
        )
    prompt2 = build_pass2_prompt(pass1=pass1, eyes=eyes, chronology=blind.chronology)
    pass2 = classifier.classify_pass2(
        prompt2, candidate_id=blind.chronology.candidate_id
    )
    return apply_pass2_promotions(blind.chronology, pass1, pass2)


def apply_pass2_promotions(
    chronology: Chronology,
    pass1: Pass1Verdict,
    pass2: Pass2Verdict,
) -> MergedCaseBuckets:
    """Apply promote-only pass 2. Unknown chronology entries are rejected."""

    if pass1.candidate_id != chronology.candidate_id:
        raise DocumentNeedProtocolError("pass-1 candidate_id does not match chronology")
    if pass2.candidate_id != chronology.candidate_id:
        raise DocumentNeedProtocolError("pass-2 candidate_id does not match chronology")
    _require_pass1_coverage(chronology, pass1)
    current: dict[int, EntryVerdict] = {row.entry: row for row in pass1.entries}
    allowed = chronology.entry_numbers()
    applied: list[Pass2Promotion] = []
    for promotion in pass2.promotions:
        if promotion.entry not in allowed:
            raise DocumentNeedProtocolError(
                f"pass-2 promotion cites a non-predecision entry {promotion.entry}"
            )
        existing = current[promotion.entry]
        if existing.bucket is not promotion.from_bucket:
            raise DocumentNeedProtocolError(
                f"pass-2 from_bucket does not match pass 1 for entry {promotion.entry}"
            )
        current[promotion.entry] = EntryVerdict(
            entry=promotion.entry,
            bucket=promotion.to_bucket,
            asserted_role=existing.asserted_role,
            rationale=f"{existing.rationale} [pass2 promote] {promotion.rationale}",
        )
        applied.append(promotion)
    ordered = tuple(current[number] for number in sorted(current))
    return MergedCaseBuckets(
        candidate_id=chronology.candidate_id,
        pass1_model_id=pass1.model_id,
        pass2_model_id=pass2.model_id,
        entries=ordered,
        promotions=tuple(applied),
    )


def parse_pass1_verdict(
    payload: Mapping[str, object], *, model_id: str
) -> Pass1Verdict:
    """Parse a strict pass-1 JSON object."""

    _require_schema(payload, PASS1_SCHEMA, "pass-1")
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or isinstance(raw_entries, str):
        raise DocumentNeedProtocolError("pass-1 entries must be a list")
    entries = tuple(
        _parse_entry_verdict(item, index)
        for index, item in enumerate(cast(list[object], raw_entries))
    )
    return Pass1Verdict(
        candidate_id=_text(payload.get("candidate_id"), "pass-1 candidate_id"),
        model_id=model_id,
        entries=entries,
    )


def parse_pass2_verdict(
    payload: Mapping[str, object], *, model_id: str
) -> Pass2Verdict:
    """Parse a strict pass-2 JSON object."""

    _require_schema(payload, PASS2_SCHEMA, "pass-2")
    raw_promotions = payload.get("promotions")
    if not isinstance(raw_promotions, list) or isinstance(raw_promotions, str):
        raise DocumentNeedProtocolError("pass-2 promotions must be a list")
    completeness = payload.get("completeness_ok")
    if type(completeness) is not bool:
        raise DocumentNeedProtocolError("completeness_ok must be boolean")
    promotions = tuple(
        _parse_promotion(item, index)
        for index, item in enumerate(cast(list[object], raw_promotions))
    )
    return Pass2Verdict(
        candidate_id=_text(payload.get("candidate_id"), "pass-2 candidate_id"),
        model_id=model_id,
        promotions=promotions,
        completeness_ok=completeness,
    )


def _require_pass1_coverage(chronology: Chronology, pass1: Pass1Verdict) -> None:
    expected = chronology.entry_numbers()
    observed = frozenset(row.entry for row in pass1.entries)
    if observed != expected:
        raise DocumentNeedProtocolError(
            "pass-1 must classify every predecision entry exactly once "
            f"(missing={sorted(expected - observed)}, "
            f"extra={sorted(observed - expected)})"
        )


def _parse_entry_verdict(item: object, index: int) -> EntryVerdict:
    if not isinstance(item, Mapping):
        raise DocumentNeedProtocolError(f"pass-1 entries[{index}] must be an object")
    record = cast(Mapping[str, object], item)
    entry = record.get("entry")
    if type(entry) is not int:
        raise DocumentNeedProtocolError(
            f"pass-1 entries[{index}].entry must be an integer"
        )
    try:
        bucket = NeedBucket(
            _text(record.get("bucket"), f"pass-1 entries[{index}].bucket")
        )
    except ValueError as exc:
        raise DocumentNeedProtocolError(
            f"pass-1 entries[{index}].bucket is not a document-need bucket"
        ) from exc
    role = record.get("asserted_role")
    if role is not None and (type(role) is not str or not role.strip()):
        raise DocumentNeedProtocolError(
            f"pass-1 entries[{index}].asserted_role must be a nonempty string when set"
        )
    return EntryVerdict(
        entry=entry,
        bucket=bucket,
        asserted_role=role.strip() if type(role) is str else None,
        rationale=_text(record.get("rationale"), f"pass-1 entries[{index}].rationale"),
    )


def _parse_promotion(item: object, index: int) -> Pass2Promotion:
    if not isinstance(item, Mapping):
        raise DocumentNeedProtocolError(f"pass-2 promotions[{index}] must be an object")
    record = cast(Mapping[str, object], item)
    entry = record.get("entry")
    cited = record.get("predecision_entry_cited")
    if type(entry) is not int or type(cited) is not int:
        raise DocumentNeedProtocolError(
            f"pass-2 promotions[{index}] entry citations must be integers"
        )
    try:
        from_bucket = NeedBucket(
            _text(record.get("from_bucket"), f"pass-2 promotions[{index}].from_bucket")
        )
        to_bucket = NeedBucket(
            _text(record.get("to_bucket"), f"pass-2 promotions[{index}].to_bucket")
        )
    except ValueError as exc:
        raise DocumentNeedProtocolError(
            f"pass-2 promotions[{index}] buckets are invalid"
        ) from exc
    try:
        return Pass2Promotion(
            entry=entry,
            from_bucket=from_bucket,
            to_bucket=to_bucket,
            rationale=_text(
                record.get("rationale"), f"pass-2 promotions[{index}].rationale"
            ),
            predecision_entry_cited=cited,
        )
    except ValueError as exc:
        raise DocumentNeedProtocolError(str(exc)) from exc


def _require_schema(payload: Mapping[str, object], expected: str, label: str) -> None:
    schema = payload.get("schema") or payload.get("schema_version")
    if schema != expected:
        raise DocumentNeedProtocolError(f"{label} schema must be {expected}")


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise DocumentNeedProtocolError(f"{label} must be a nonempty string")
    return value.strip()
