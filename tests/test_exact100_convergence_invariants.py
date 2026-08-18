"""The exact-100 final convergence invariant suite.

Fixtures are hand-authored (``synthetic: true``) miniatures of the real
artifacts: a manifest projection row, an adjudication overlay row carrying
byte-role validation evidence, and an owner disposition overlay row. The suite
is sized by ``REQUIRED_CASE_COUNT`` so the miniature corpus deliberately fails
invariant 1 -- every other test asserts on its own invariant's failures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.exact100_convergence_invariants import (
    ConvergenceInputs,
    evaluate_convergence,
    load_inputs,
)
from legalforecast.ingestion.exact100_convergence_invariants_cli import (
    EXIT_BLOCKED,
    EXIT_UNREADABLE,
    build_report,
    run,
)

SYNTHETIC: dict[str, bool] = {"synthetic": True}

INVARIANT_KEYS = (
    "exactly_100_eligible_unique_cases",
    "one_eligible_target_motion_per_case",
    "attacked_pleading_and_target_motion_present",
    "docketed_target_motion_briefs_included_and_linked",
    "superseded_filings_removed",
    "no_collateral_filing_linked_as_target_briefing",
    "selected_documents_parseable_and_byte_role_validated",
    "replacements_fully_validated",
    "owner_and_corpus_state_reconciled",
)


def _required(
    entry: int, role: str, *, linked: list[int] | None = None
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "confidence": "high",
        "document_selector": "main",
        "entry": entry,
        "evidence": "synthetic docket text",
        "opinion_derived": False,
        "role": role,
        "source": "pass1",
    }
    if linked is not None:
        row["linked_motion_entries"] = linked
        row["linkage_basis"] = ["explicit_entry_reference"]
    return row


def _corpus_row(
    candidate_id: str = "70000001",
    *,
    required: list[dict[str, Any]] | None = None,
    missing: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "current_selection": [{"entry": 1, "role": "complaint"}],
        "missing_docs": missing or [],
        "needs_human": True,
        "required_entries": required
        or [
            _required(1, "complaint"),
            _required(9, "target_motion"),
            _required(12, "opposition", linked=[9]),
            _required(14, "reply", linked=[9]),
        ],
        "verdict": "repair",
    }


def _validated_status(
    entry: int, role: str, *, verdict: str = "match"
) -> dict[str, Any]:
    return {
        "acquired_document_role": role,
        "acquired_evidence": {
            "docket_entry_number": entry,
            "source_document_id": f"doc-{entry}",
        },
        "acquisition_status": "acquired",
        "byte_role_validation": {
            "byte_role_verdict": verdict,
            "expected_role": role,
            "source_document_id": f"doc-{entry}",
            "validation_basis": "parsed_heading",
        },
        "entry": entry,
        "role": role,
    }


def _adjudication_row(
    candidate_id: str = "70000001",
    *,
    statuses: list[dict[str, Any]] | None = None,
    decision_status: str = "pending_human_adjudication",
) -> dict[str, Any]:
    return {
        "byte_mismatches": [],
        "candidate_id": candidate_id,
        "decision_status": decision_status,
        "missing_document_status": statuses
        or [
            _validated_status(1, "complaint"),
            _validated_status(9, "target_motion"),
            _validated_status(12, "opposition"),
            _validated_status(14, "reply"),
        ],
    }


def _disposition(
    candidate_id: str = "70000001",
    *,
    execution_state: str = "complete",
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "candidate_id": candidate_id,
        "decision": "accept_existing_audit_repair",
        "execution_state": execution_state,
    }
    row.update(extra)
    return row


def _inputs(
    *,
    corpus: list[dict[str, Any]] | None = None,
    adjudication: list[dict[str, Any]] | None = None,
    dispositions: list[dict[str, Any]] | None = None,
    parse_quality: dict[str, Any] | None = None,
    replacements: list[dict[str, Any]] | None = None,
) -> ConvergenceInputs:
    return ConvergenceInputs.build(
        corpus=corpus if corpus is not None else [_corpus_row()],
        adjudication=adjudication
        if adjudication is not None
        else [_adjudication_row()],
        dispositions=dispositions if dispositions is not None else [_disposition()],
        parse_quality=parse_quality if parse_quality is not None else {"rejected": []},
        replacements=replacements if replacements is not None else [],
    )


def _result(report: Any, key: str) -> Any:
    return next(result for result in report.results if result.key == key)


def test_suite_runs_all_nine_invariants_in_order() -> None:
    report = evaluate_convergence(_inputs())
    assert tuple(result.key for result in report.results) == INVARIANT_KEYS


def test_a_short_corpus_blocks_the_case_count_invariant() -> None:
    report = evaluate_convergence(_inputs())
    result = _result(report, "exactly_100_eligible_unique_cases")
    assert not result.passed
    assert "1 eligible unique cases" in result.failures[0].detail
    assert report.passed is False


def test_duplicate_candidate_is_named() -> None:
    report = evaluate_convergence(
        _inputs(
            corpus=[_corpus_row(), _corpus_row()], adjudication=[_adjudication_row()]
        )
    )
    result = _result(report, "exactly_100_eligible_unique_cases")
    assert any(
        failure.candidate_id == "70000001" and "appears 2 times" in failure.detail
        for failure in result.failures
    )


def test_two_target_motions_block_and_name_the_case() -> None:
    corpus = [
        _corpus_row(
            required=[
                _required(1, "complaint"),
                _required(9, "target_motion"),
                _required(10, "target_motion"),
            ]
        )
    ]
    report = evaluate_convergence(_inputs(corpus=corpus))
    result = _result(report, "one_eligible_target_motion_per_case")
    assert not result.passed
    assert result.blocking_candidate_ids == ("70000001",)
    assert "2 target motions" in result.failures[0].detail


def test_owner_relabel_supplies_the_target_motion() -> None:
    corpus = [
        _corpus_row(
            required=[
                _required(1, "complaint"),
                _required(22, "motion_to_dismiss_memorandum"),
            ]
        )
    ]
    blocked = evaluate_convergence(_inputs(corpus=corpus))
    assert not _result(blocked, "one_eligible_target_motion_per_case").passed

    relabelled = evaluate_convergence(
        _inputs(
            corpus=corpus,
            dispositions=[
                _disposition(
                    relabels=[
                        {
                            "entry": 22,
                            "from_role": "motion_to_dismiss_memorandum",
                            "to_role": "target_motion",
                        }
                    ]
                )
            ],
        )
    )
    assert _result(relabelled, "one_eligible_target_motion_per_case").passed


def test_missing_pleading_is_named() -> None:
    corpus = [_corpus_row(required=[_required(9, "target_motion")])]
    report = evaluate_convergence(_inputs(corpus=corpus))
    result = _result(report, "attacked_pleading_and_target_motion_present")
    assert "no attacked pleading" in result.failures[0].detail
    assert result.failures[0].candidate_id == "70000001"


def test_unheld_target_motion_names_its_entry() -> None:
    corpus = [_corpus_row(missing=[_required(9, "target_motion")])]
    report = evaluate_convergence(
        _inputs(
            corpus=corpus,
            adjudication=[
                _adjudication_row(
                    statuses=[
                        _validated_status(1, "complaint"),
                        _validated_status(12, "opposition"),
                        _validated_status(14, "reply"),
                    ]
                )
            ],
        )
    )
    result = _result(report, "attacked_pleading_and_target_motion_present")
    assert any(
        failure.entry_number == 9 and "not yet held" in failure.detail
        for failure in result.failures
    )


def test_unheld_brief_names_its_entry() -> None:
    corpus = [_corpus_row(missing=[_required(14, "reply", linked=[9])])]
    report = evaluate_convergence(
        _inputs(
            corpus=corpus,
            adjudication=[
                _adjudication_row(
                    statuses=[
                        _validated_status(1, "complaint"),
                        _validated_status(9, "target_motion"),
                        _validated_status(12, "opposition"),
                    ]
                )
            ],
        )
    )
    result = _result(report, "docketed_target_motion_briefs_included_and_linked")
    assert any(
        failure.entry_number == 14 and "not yet held" in failure.detail
        for failure in result.failures
    )


def test_owner_drop_excuses_an_unheld_brief() -> None:
    corpus = [_corpus_row(missing=[_required(14, "reply", linked=[9])])]
    adjudication = [
        _adjudication_row(
            statuses=[
                _validated_status(1, "complaint"),
                _validated_status(9, "target_motion"),
                _validated_status(12, "opposition"),
            ]
        )
    ]
    report = evaluate_convergence(
        _inputs(
            corpus=corpus,
            adjudication=adjudication,
            dispositions=[
                _disposition(drops=[{"entry": 14, "reason": "court-issued letter"}])
            ],
        )
    )
    assert _result(report, "docketed_target_motion_briefs_included_and_linked").passed


def test_brief_linked_to_a_different_motion_is_named() -> None:
    corpus = [
        _corpus_row(
            required=[
                _required(1, "complaint"),
                _required(9, "target_motion"),
                _required(30, "opposition", linked=[25]),
            ]
        )
    ]
    report = evaluate_convergence(
        _inputs(
            corpus=corpus,
            adjudication=[
                _adjudication_row(
                    statuses=[
                        _validated_status(1, "complaint"),
                        _validated_status(9, "target_motion"),
                        _validated_status(30, "opposition"),
                    ]
                )
            ],
        )
    )
    result = _result(report, "docketed_target_motion_briefs_included_and_linked")
    assert any(
        failure.entry_number == 30
        and "none of which is the target motion" in failure.detail
        for failure in result.failures
    )


def test_superseded_entry_left_in_the_packet_is_named() -> None:
    disposition = _disposition(
        final_packet=[
            {"entry": 1, "role": "complaint"},
            {"entry": 9, "role": "target_motion"},
            {"entry": 18, "role": "response"},
        ],
        superseded=[{"entry": 18, "superseded_by_entry": 19}],
    )
    report = evaluate_convergence(_inputs(dispositions=[disposition]))
    result = _result(report, "superseded_filings_removed")
    assert not result.passed
    assert result.failures[0].entry_number == 18
    assert "superseded by E19" in result.failures[0].detail


def test_superseded_entry_removed_passes() -> None:
    disposition = _disposition(superseded=[{"entry": 18, "superseded_by_entry": 19}])
    report = evaluate_convergence(_inputs(dispositions=[disposition]))
    assert _result(report, "superseded_filings_removed").passed


def test_collateral_left_in_the_packet_is_named() -> None:
    disposition = _disposition(
        final_packet=[
            {"entry": 1, "role": "complaint"},
            {"entry": 9, "role": "target_motion"},
            {"entry": 11, "role": "declaration"},
        ],
        collateral=[{"entry": 11, "role": "declaration"}],
    )
    report = evaluate_convergence(_inputs(dispositions=[disposition]))
    result = _result(report, "no_collateral_filing_linked_as_target_briefing")
    assert result.failures[0].entry_number == 11
    assert "classified collateral" in result.failures[0].detail


def test_unvalidated_document_is_named() -> None:
    adjudication = [
        _adjudication_row(
            statuses=[
                _validated_status(1, "complaint"),
                _validated_status(9, "target_motion"),
                _validated_status(12, "opposition"),
                {
                    "acquired_document_role": "reply",
                    "acquired_evidence": {"docket_entry_number": 14},
                    "acquisition_status": "acquired",
                    "entry": 14,
                    "role": "reply",
                },
            ]
        )
    ]
    report = evaluate_convergence(_inputs(adjudication=adjudication))
    result = _result(report, "selected_documents_parseable_and_byte_role_validated")
    assert any(
        failure.entry_number == 14 and "no byte-role validation" in failure.detail
        for failure in result.failures
    )


def test_nonmatching_verdict_is_named() -> None:
    adjudication = [
        _adjudication_row(
            statuses=[
                _validated_status(1, "complaint"),
                _validated_status(9, "target_motion"),
                _validated_status(12, "opposition"),
                _validated_status(14, "reply", verdict="mismatch"),
            ]
        )
    ]
    report = evaluate_convergence(_inputs(adjudication=adjudication))
    result = _result(report, "selected_documents_parseable_and_byte_role_validated")
    assert any(
        failure.entry_number == 14
        and "verdict for the selected reply is mismatch" in failure.detail
        for failure in result.failures
    )


def test_missing_parse_quality_artifact_is_an_evidence_gap() -> None:
    inputs = ConvergenceInputs.build(
        corpus=[_corpus_row()],
        adjudication=[_adjudication_row()],
        dispositions=[_disposition()],
        parse_quality=None,
        replacements=[],
    )
    report = evaluate_convergence(inputs)
    result = _result(report, "selected_documents_parseable_and_byte_role_validated")
    assert any("evidence_gap" in failure.detail for failure in result.failures)


def test_parse_quality_rejection_is_named_with_its_document() -> None:
    report = evaluate_convergence(
        _inputs(
            parse_quality={
                "rejected": [
                    {
                        "candidate_id": "70000001",
                        "source_document_id": "doc-9",
                        "reason": "no_substantive_text",
                    }
                ]
            }
        )
    )
    result = _result(report, "selected_documents_parseable_and_byte_role_validated")
    assert any(
        failure.source_document_id == "doc-9"
        and "no_substantive_text" in failure.detail
        for failure in result.failures
    )


def test_case_without_validation_evidence_is_an_evidence_gap() -> None:
    report = evaluate_convergence(
        _inputs(corpus=[_corpus_row(), _corpus_row("70000002")])
    )
    result = _result(report, "selected_documents_parseable_and_byte_role_validated")
    assert any(
        failure.candidate_id == "70000002" and "evidence_gap" in failure.detail
        for failure in result.failures
    )


def test_exclusion_without_replacement_evidence_is_named() -> None:
    disposition = _disposition(
        decision="exclude_and_promote_replacement",
        execution_state="blocked",
        execution_blocked_on="replacement_validation",
        exclusion={"replacement_candidate_id": "69437817"},
    )
    report = evaluate_convergence(_inputs(dispositions=[disposition]))
    result = _result(report, "replacements_fully_validated")
    assert result.failures[0].candidate_id == "69437817"
    assert "evidence_gap" in result.failures[0].detail


def test_exclusion_with_unsourced_replacement_is_named() -> None:
    disposition = _disposition(
        decision="exclude_and_promote_replacement",
        execution_state="blocked",
        exclusion={"replacement_candidate_id": None},
    )
    report = evaluate_convergence(_inputs(dispositions=[disposition]))
    result = _result(report, "replacements_fully_validated")
    assert "no sourced replacement candidate" in result.failures[0].detail


def test_a_posted_proposal_is_neither_unsourced_nor_approved() -> None:
    """A sourced-but-unapproved successor must read as exactly that."""

    disposition = _disposition(
        decision="exclude_and_promote_replacement",
        execution_state="blocked",
        exclusion={
            "replacement_candidate_id": None,
            "proposed_replacement_candidate_id": "70142291",
        },
    )
    report = evaluate_convergence(_inputs(dispositions=[disposition]))
    for key in ("replacements_fully_validated", "exactly_100_eligible_unique_cases"):
        details = [failure.detail for failure in _result(report, key).failures]
        assert any(
            "70142291 is sourced and posted but not yet owner-approved" in detail
            for detail in details
        ), key
        assert not any("no sourced replacement candidate" in d for d in details), key


def test_fully_validated_replacement_passes_and_refills_the_slot() -> None:
    disposition = _disposition(
        decision="exclude_and_promote_replacement",
        exclusion={"replacement_candidate_id": "69437817"},
    )
    report = evaluate_convergence(
        _inputs(
            dispositions=[disposition],
            replacements=[{"candidate_id": "69437817", "fully_validated": True}],
        )
    )
    assert _result(report, "replacements_fully_validated").passed
    count = _result(report, "exactly_100_eligible_unique_cases")
    assert not any("is not yet fully validated" in f.detail for f in count.failures)


def test_pending_row_without_a_disposition_is_named() -> None:
    report = evaluate_convergence(
        _inputs(
            adjudication=[_adjudication_row(), _adjudication_row("70000009")],
            dispositions=[_disposition()],
        )
    )
    result = _result(report, "owner_and_corpus_state_reconciled")
    assert any(
        failure.candidate_id == "70000009"
        and "carries no owner disposition" in failure.detail
        for failure in result.failures
    )


def test_incomplete_execution_state_blocks_reconciliation() -> None:
    report = evaluate_convergence(
        _inputs(
            dispositions=[
                _disposition(
                    execution_state="blocked", execution_blocked_on="acquisition"
                )
            ]
        )
    )
    result = _result(report, "owner_and_corpus_state_reconciled")
    assert any(
        "is blocked (acquisition)" in failure.detail for failure in result.failures
    )


def test_unknown_execution_state_is_rejected() -> None:
    report = evaluate_convergence(
        _inputs(dispositions=[_disposition(execution_state="done")])
    )
    result = _result(report, "owner_and_corpus_state_reconciled")
    assert any(
        "is not one of ready/blocked/complete" in f.detail for f in result.failures
    )


def test_out_of_corpus_disposition_is_allowed_when_declared() -> None:
    report = evaluate_convergence(
        _inputs(
            dispositions=[
                _disposition(),
                _disposition("73215717", in_corpus=False),
            ]
        )
    )
    result = _result(report, "owner_and_corpus_state_reconciled")
    assert not any(
        "absent from the corpus" in failure.detail for failure in result.failures
    )


def test_undeclared_out_of_corpus_disposition_is_named() -> None:
    report = evaluate_convergence(
        _inputs(dispositions=[_disposition(), _disposition("73215717")])
    )
    result = _result(report, "owner_and_corpus_state_reconciled")
    assert any(
        failure.candidate_id == "73215717"
        and "absent from the corpus" in failure.detail
        for failure in result.failures
    )


def test_report_is_deterministic() -> None:
    first = evaluate_convergence(_inputs()).to_json()
    second = evaluate_convergence(_inputs()).to_json()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_text_report_names_every_invariant() -> None:
    text = evaluate_convergence(_inputs()).render_text()
    for key in INVARIANT_KEYS:
        assert key in text
    assert "BLOCKED" in text


def _write(tmp_path: Path, name: str, rows: list[dict[str, Any]]) -> Path:
    path = tmp_path / name
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def test_cli_reads_artifacts_and_reports_blocked(tmp_path: Path) -> None:
    report = build_report(
        corpus=_write(tmp_path, "corpus.jsonl", [_corpus_row()]),
        adjudication=_write(tmp_path, "adj.jsonl", [_adjudication_row()]),
        dispositions=_write(tmp_path, "disp.jsonl", [_disposition()]),
    )
    assert report.passed is False
    assert _result(report, "exactly_100_eligible_unique_cases").passed is False


def test_cli_run_writes_json_and_returns_blocked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    output = tmp_path / "report.json"
    args = argparse.Namespace(
        corpus=_write(tmp_path, "corpus.jsonl", [_corpus_row()]),
        adjudication=_write(tmp_path, "adj.jsonl", [_adjudication_row()]),
        dispositions=_write(tmp_path, "disp.jsonl", [_disposition()]),
        parse_quality=None,
        replacements=None,
        emit_json=True,
        output=output,
    )
    assert run(args) == EXIT_BLOCKED
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["converged"] is False
    assert len(payload["invariants"]) == 9
    assert "converged" in capsys.readouterr().out


def test_cli_reports_unreadable_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    args = argparse.Namespace(
        corpus=tmp_path / "absent.jsonl",
        adjudication=_write(tmp_path, "adj.jsonl", [_adjudication_row()]),
        dispositions=_write(tmp_path, "disp.jsonl", [_disposition()]),
        parse_quality=None,
        replacements=None,
        emit_json=False,
        output=None,
    )
    assert run(args) == EXIT_UNREADABLE
    assert "unreadable input" in capsys.readouterr().out


def _acquisition(
    candidate_id: str, entry: int, role: str, *, verdict: str = "match"
) -> dict[str, Any]:
    return {
        "byte_role_verdict": verdict,
        "candidate_id": candidate_id,
        "entry": entry,
        "role": role,
        "source_document_id": f"doc-{candidate_id}-{entry}",
        "validation_basis": "parsed_heading",
    }


def test_acquisitions_supply_held_evidence_for_cases_outside_the_overlay() -> None:
    """A case with no adjudication row is an evidence gap until acquisitions land."""

    corpus = [_corpus_row(), _corpus_row("70000002")]
    gap = evaluate_convergence(_inputs(corpus=corpus))
    assert any(
        failure.candidate_id == "70000002" and "evidence_gap" in failure.detail
        for failure in _result(
            gap, "selected_documents_parseable_and_byte_role_validated"
        ).failures
    )

    supplied = evaluate_convergence(
        ConvergenceInputs.build(
            corpus=corpus,
            adjudication=[_adjudication_row()],
            dispositions=[_disposition()],
            parse_quality={"rejected": []},
            replacements=[],
            acquisitions=[
                _acquisition("70000002", 1, "complaint"),
                _acquisition("70000002", 9, "target_motion"),
                _acquisition("70000002", 12, "opposition"),
                _acquisition("70000002", 14, "reply"),
            ],
        )
    )
    assert _result(
        supplied, "selected_documents_parseable_and_byte_role_validated"
    ).passed


def test_acquisitions_do_not_displace_overlay_evidence() -> None:
    """An overlay row's own status wins; acquisitions only fill entries it lacks."""

    inputs = ConvergenceInputs.build(
        corpus=[_corpus_row()],
        adjudication=[
            _adjudication_row(
                statuses=[_validated_status(1, "complaint", verdict="mismatch")]
            )
        ],
        dispositions=[_disposition()],
        parse_quality={"rejected": []},
        replacements=[],
        acquisitions=[
            _acquisition("70000001", 1, "complaint"),
            _acquisition("70000001", 9, "target_motion"),
        ],
    )
    view = inputs.validation_views["70000001"]
    assert view.verdict_for_entry(1) == "mismatch"
    assert view.verdict_for_entry(9) == "match"


def test_acquisitions_absent_leaves_adjudication_rows_untouched() -> None:
    inputs = ConvergenceInputs.build(
        corpus=[_corpus_row()],
        adjudication=[_adjudication_row()],
        dispositions=[_disposition()],
        acquisitions=None,
    )
    assert set(inputs.validation_views) == {"70000001"}


def test_load_inputs_parses_every_artifact() -> None:
    inputs = load_inputs(
        corpus_text=json.dumps(_corpus_row()) + "\n\n",
        adjudication_text=json.dumps(_adjudication_row()) + "\n",
        dispositions_text=json.dumps(_disposition()) + "\n",
        parse_quality_text=json.dumps({"rejected": []}),
        replacements_text="",
    )
    assert len(inputs.corpus) == 1
    assert len(inputs.dispositions) == 1
    assert inputs.replacements == ()
    assert set(inputs.validation_views) == {"70000001"}
