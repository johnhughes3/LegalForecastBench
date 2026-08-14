"""Blind two-pass protocol and 3ak-style audit-bundle prep."""

from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.document_need.blindness import (
    BlindnessError,
    Pass1Process,
    assert_pass1_cannot_read_decision,
)
from legalforecast.document_need.cycle_config import (
    DocumentNeedConfigError,
    NeedSelectorIdentity,
)
from legalforecast.document_need.prep import parse_page_count, prepare_audit_bundles
from legalforecast.document_need.protocol import (
    DocumentNeedProtocolError,
    apply_pass2_promotions,
    build_pass1_prompt,
    build_pass2_prompt,
    run_two_pass,
)
from legalforecast.document_need.selector import FixtureClassifier
from legalforecast.document_need.types import (
    BlindBundle,
    Chronology,
    ChronologyEntry,
    DecisionText,
    DocketDocument,
    EntryVerdict,
    EyesBundle,
    NeedBucket,
    Pass1Verdict,
    Pass2Promotion,
    Pass2Verdict,
)
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from tests.document_need_fixtures import (
    HAIKU,
    activated_haiku_config,
    luna_on_cycle1_registry,
)

_DECISION = "UNIQUE_DECISION_BYTES_THE_PASS1_PROCESS_MUST_NOT_SEE"
_BUCKETS = {
    "clearly_required": (
        "Required: the target motion, memorandum, operative pleading, and "
        "filed oppositions/replies when those entries exist."
    ),
    "conditional": (
        "Might be required depending on what the clearly-required documents contain."
    ),
    "clearly_not_required": "Not required for packet completeness.",
}
_HTML = (
    Path(__file__).resolve().parent
    / "fixtures/courtlistener/docket-structural-single-page-2026-07-28.html"
)


def _doc(
    *,
    selector: str = "main_document",
    paid: bool = True,
    pages: int | None = 10,
    description: str = "Main Document (10 pages)",
) -> DocketDocument:
    return DocketDocument(
        selector=selector,
        description=description,
        freely_available=not paid,
        pacer_only=paid,
        page_count=pages,
    )


def _chronology() -> Chronology:
    return Chronology(
        candidate_id="case-a",
        case_name="A v. B",
        court="nysd",
        docket_number="1:26-cv-1",
        target_motion_entries=(10,),
        decision_cut_entry=20,
        entries=(
            ChronologyEntry(
                entry=1,
                filed="2026-01-02",
                text="Complaint.",
                documents=(_doc(paid=False, pages=12, description="Complaint"),),
            ),
            ChronologyEntry(
                entry=10,
                filed="2026-03-01",
                text="Motion to dismiss.",
                documents=(_doc(pages=30, description="MTD (30 pages)"),),
            ),
            ChronologyEntry(
                entry=12,
                filed="2026-03-15",
                text="Response to Motion.",
                documents=(_doc(pages=8, description="Opp (8 pages)"),),
            ),
            ChronologyEntry(
                entry=15,
                filed="2026-03-22",
                text="Notice of appearance.",
                documents=(_doc(pages=1, description="Notice (1 page)"),),
            ),
        ),
    )


def _pass1() -> Pass1Verdict:
    return Pass1Verdict(
        candidate_id="case-a",
        model_id=HAIKU.model_id,
        provider=HAIKU.provider,
        model_version_or_snapshot=HAIKU.model_version_or_snapshot,
        entries=(
            EntryVerdict(
                1, NeedBucket.CLEARLY_REQUIRED, "complaint", "operative pleading"
            ),
            EntryVerdict(
                10, NeedBucket.CLEARLY_REQUIRED, "mtd_memorandum", "target motion"
            ),
            EntryVerdict(
                12, NeedBucket.CONDITIONAL, "opposition", "generic response title"
            ),
            EntryVerdict(15, NeedBucket.CLEARLY_NOT_REQUIRED, None, "appearance"),
        ),
    )


def test_parse_page_count_from_courtlistener_labels() -> None:
    assert parse_page_count("Main Document (15 pages)") == 15
    assert parse_page_count("Opposition 8 pgs") == 8
    assert parse_page_count("no count here") is None


def test_prep_puts_decision_only_in_eyes_bundle() -> None:
    html = _HTML.read_text(encoding="utf-8")
    docket = parse_courtlistener_docket_html(html)
    bundles = prepare_audit_bundles(
        candidate_id="70754103",
        docket=docket,
        target_motion_entries=(4,),
        decision_cut_entry=10,
        decision_text=_DECISION,
        motion_markdown={4: "Motion to dismiss memorandum text."},
    )
    assert _DECISION not in build_pass1_prompt(
        bundles.blind, bucket_definitions=_BUCKETS
    )
    assert bundles.eyes.decision.text == _DECISION
    assert bundles.blind.chronology.entries[0].entry == 4


def test_pass1_process_refuses_decision_bytes() -> None:
    bundle = BlindBundle(
        chronology=_chronology(),
        motion_markdown={10: "Motion memorandum."},
    )
    process = Pass1Process(bundle)
    with pytest.raises(BlindnessError, match="must not receive decision"):
        process.attach_decision(_DECISION)


def test_pass1_prompt_checker_fails_when_decision_leaks_into_motion_markdown() -> None:
    tainted = BlindBundle(
        chronology=_chronology(),
        motion_markdown={10: _DECISION},
    )
    prompt = build_pass1_prompt(tainted, bucket_definitions=_BUCKETS)
    decision = DecisionText(
        candidate_id="case-a",
        text=_DECISION,
        sha256="a" * 64,
    )
    with pytest.raises(BlindnessError, match="contains decision bytes"):
        assert_pass1_cannot_read_decision(prompt, decision)


def test_two_pass_promotes_conditional_opposition() -> None:
    blind = BlindBundle(
        chronology=_chronology(),
        motion_markdown={10: "Motion memorandum."},
    )
    eyes = EyesBundle(
        decision=DecisionText(
            candidate_id="case-a",
            text=_DECISION,
            sha256="b" * 64,
        )
    )
    classifier = FixtureClassifier(
        pass1={"case-a": _pass1()},
        pass2={
            "case-a": Pass2Verdict(
                candidate_id="case-a",
                model_id=HAIKU.model_id,
                provider=HAIKU.provider,
                model_version_or_snapshot=HAIKU.model_version_or_snapshot,
                promotions=(
                    Pass2Promotion(
                        entry=12,
                        from_bucket=NeedBucket.CONDITIONAL,
                        to_bucket=NeedBucket.CLEARLY_REQUIRED,
                        rationale="decision treats the response as the opposition",
                        predecision_entry_cited=12,
                    ),
                ),
                completeness_ok=True,
            )
        },
        provider=HAIKU.provider,
        model_id=HAIKU.model_id,
        model_version_or_snapshot=HAIKU.model_version_or_snapshot,
    )
    merged = run_two_pass(
        blind=blind,
        eyes=eyes,
        classifier=classifier,
        config=activated_haiku_config(),
    )
    assert merged.by_entry()[12].bucket is NeedBucket.CLEARLY_REQUIRED
    assert merged.pass1_model_id == HAIKU.model_id
    assert merged.pass2_model_id == HAIKU.model_id


def test_pass2_cannot_demote() -> None:
    with pytest.raises(ValueError, match="only promote"):
        Pass2Promotion(
            entry=10,
            from_bucket=NeedBucket.CLEARLY_REQUIRED,
            to_bucket=NeedBucket.CONDITIONAL,
            rationale="would leak outcome-neutrality",
            predecision_entry_cited=10,
        )


def test_pass2_rejects_non_predecision_promotion() -> None:
    with pytest.raises(DocumentNeedProtocolError, match="non-predecision"):
        apply_pass2_promotions(
            _chronology(),
            _pass1(),
            Pass2Verdict(
                candidate_id="case-a",
                model_id="fixture:document-need-v1",
                provider="fixture",
                model_version_or_snapshot="fixture:document-need-v1",
                promotions=(
                    Pass2Promotion(
                        entry=20,
                        from_bucket=NeedBucket.CLEARLY_NOT_REQUIRED,
                        to_bucket=NeedBucket.CLEARLY_REQUIRED,
                        rationale="decision entry",
                        predecision_entry_cited=20,
                    ),
                ),
                completeness_ok=True,
            ),
        )


def test_pass1_must_cover_every_chronology_entry() -> None:
    incomplete = Pass1Verdict(
        candidate_id="case-a",
        model_id="fixture:document-need-v1",
        provider="fixture",
        model_version_or_snapshot="fixture:document-need-v1",
        entries=_pass1().entries[:2],
    )
    with pytest.raises(DocumentNeedProtocolError, match="exactly once"):
        apply_pass2_promotions(
            _chronology(),
            incomplete,
            Pass2Verdict(
                candidate_id="case-a",
                model_id="fixture:document-need-v1",
                provider="fixture",
                model_version_or_snapshot="fixture:document-need-v1",
                promotions=(),
                completeness_ok=True,
            ),
        )


def test_pass2_rejects_decision_from_another_candidate() -> None:
    blind = BlindBundle(
        chronology=_chronology(),
        motion_markdown={10: "Motion memorandum."},
    )
    eyes = EyesBundle(
        decision=DecisionText(
            candidate_id="case-b",
            text=_DECISION,
            sha256="c" * 64,
        )
    )
    classifier = FixtureClassifier(
        pass1={"case-a": _pass1()},
        pass2={},
        provider=HAIKU.provider,
        model_id=HAIKU.model_id,
        model_version_or_snapshot=HAIKU.model_version_or_snapshot,
    )
    with pytest.raises(DocumentNeedProtocolError, match="does not match"):
        run_two_pass(
            blind=blind,
            eyes=eyes,
            classifier=classifier,
            config=activated_haiku_config(),
        )


def test_pass2_incomplete_check_is_rejected() -> None:
    with pytest.raises(DocumentNeedProtocolError, match="completeness check failed"):
        apply_pass2_promotions(
            _chronology(),
            _pass1(),
            Pass2Verdict(
                candidate_id="case-a",
                model_id="fixture:document-need-v1",
                provider="fixture",
                model_version_or_snapshot="fixture:document-need-v1",
                promotions=(),
                completeness_ok=False,
            ),
        )


def test_blind_bundle_markdown_must_match_target_motion_entries() -> None:
    with pytest.raises(ValueError, match="must equal"):
        BlindBundle(
            chronology=_chronology(),
            motion_markdown={12: "Wrong filing text."},
        )


def test_chronology_requires_target_motion_in_entries() -> None:
    with pytest.raises(ValueError, match="not in the chronology"):
        Chronology(
            candidate_id="case-a",
            case_name="A v. B",
            court="nysd",
            docket_number="1:26-cv-1",
            target_motion_entries=(9,),
            decision_cut_entry=20,
            entries=_chronology().entries,
        )


def test_pass1_prompt_checker_detects_json_escaped_decision_text() -> None:
    leaked = 'The court said "UNIQUE_QUOTED_HOLDING".'
    tainted = BlindBundle(
        chronology=_chronology(),
        motion_markdown={10: leaked},
    )
    prompt = build_pass1_prompt(tainted, bucket_definitions=_BUCKETS)
    decision = DecisionText(
        candidate_id="case-a",
        text=leaked,
        sha256="d" * 64,
    )
    assert leaked not in prompt
    with pytest.raises(BlindnessError, match="contains decision bytes"):
        assert_pass1_cannot_read_decision(prompt, decision)


def test_pass1_rejects_verdict_for_another_candidate_without_eyes() -> None:
    class _WrongCandidate:
        def selector_identity(self) -> NeedSelectorIdentity:
            return NeedSelectorIdentity(
                provider=HAIKU.provider,
                model_id=HAIKU.model_id,
                model_version_or_snapshot=HAIKU.model_version_or_snapshot,
            )

        def classify_pass1(self, prompt: str, *, candidate_id: str) -> Pass1Verdict:
            del prompt, candidate_id
            source = _pass1()
            return Pass1Verdict(
                candidate_id="case-b",
                model_id=source.model_id,
                provider=source.provider,
                model_version_or_snapshot=source.model_version_or_snapshot,
                entries=source.entries,
            )

        def classify_pass2(self, prompt: str, *, candidate_id: str) -> Pass2Verdict:
            raise AssertionError("pass 2 should not run")

    with pytest.raises(DocumentNeedProtocolError, match="pass-1 candidate_id"):
        run_two_pass(
            blind=BlindBundle(
                chronology=_chronology(),
                motion_markdown={10: "Motion memorandum."},
            ),
            eyes=None,
            classifier=_WrongCandidate(),
            config=activated_haiku_config(),
        )


def test_pass1_prompt_includes_configured_bucket_definitions() -> None:
    prompt = build_pass1_prompt(
        BlindBundle(
            chronology=_chronology(),
            motion_markdown={10: "Motion memorandum."},
        ),
        bucket_definitions=_BUCKETS,
    )
    assert "BUCKET_DEFINITIONS_JSON" in prompt
    assert "filed oppositions/replies" in prompt
    with pytest.raises(DocumentNeedProtocolError, match="bucket_definitions"):
        build_pass1_prompt(
            BlindBundle(
                chronology=_chronology(),
                motion_markdown={10: "Motion memorandum."},
            ),
            bucket_definitions={"clearly_required": "only one"},
        )


def test_pass2_prompt_includes_selected_docs() -> None:
    prompt = build_pass2_prompt(
        pass1=_pass1(),
        eyes=EyesBundle(
            decision=DecisionText(
                candidate_id="case-a",
                text=_DECISION,
                sha256="e" * 64,
            ),
            selected_docs=({"entry": 12, "excerpt": "UNIQUE_SELECTED_DOC_EXCERPT"},),
        ),
        chronology=_chronology(),
    )
    assert "SELECTED_DOCS_JSON" in prompt
    assert "UNIQUE_SELECTED_DOC_EXCERPT" in prompt


def test_run_two_pass_preflights_before_classifier() -> None:
    class _Boom:
        def classify_pass1(self, prompt: str, *, candidate_id: str) -> Pass1Verdict:
            raise AssertionError("classifier must not run before selector preflight")

        def classify_pass2(self, prompt: str, *, candidate_id: str) -> Pass2Verdict:
            raise AssertionError("classifier must not run before selector preflight")

    with pytest.raises(DocumentNeedConfigError, match=r"gpt-5\.6-luna"):
        run_two_pass(
            blind=BlindBundle(
                chronology=_chronology(),
                motion_markdown={10: "Motion memorandum."},
            ),
            eyes=None,
            classifier=_Boom(),
            config=luna_on_cycle1_registry(),
        )


def test_run_two_pass_uses_cycle_bucket_definitions() -> None:
    captured: list[str] = []

    class _Capture:
        def selector_identity(self) -> NeedSelectorIdentity:
            return NeedSelectorIdentity(
                provider=HAIKU.provider,
                model_id=HAIKU.model_id,
                model_version_or_snapshot=HAIKU.model_version_or_snapshot,
            )

        def classify_pass1(self, prompt: str, *, candidate_id: str) -> Pass1Verdict:
            captured.append(prompt)
            return _pass1()

        def classify_pass2(self, prompt: str, *, candidate_id: str) -> Pass2Verdict:
            raise AssertionError("pass 2 should not run")

    run_two_pass(
        blind=BlindBundle(
            chronology=_chronology(),
            motion_markdown={10: "Motion memorandum."},
        ),
        eyes=None,
        classifier=_Capture(),
        config=activated_haiku_config(),
    )
    assert captured
    assert "pinned cohort policy" in captured[0]
    assert "filed oppositions/replies when those entries exist" not in captured[0]


def test_run_two_pass_rejects_unapproved_classifier_identity() -> None:
    classifier = FixtureClassifier(pass1={"case-a": _pass1()}, pass2={})
    with pytest.raises(DocumentNeedProtocolError, match="selector-model policy"):
        run_two_pass(
            blind=BlindBundle(
                chronology=_chronology(),
                motion_markdown={10: "Motion memorandum."},
            ),
            eyes=None,
            classifier=classifier,
            config=activated_haiku_config(),
        )
