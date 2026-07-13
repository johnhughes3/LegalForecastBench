from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion.courtlistener_web import CourtListenerWebDocketEntry
from legalforecast.ingestion.packet_input_planner import (
    PacketInputPlanningError,
    _docket_entries,
    _docket_screen_with_first_disposition_anchor,
    plan_packet_build_inputs,
)


def test_packet_time_leakage_screen_excludes_adversarial_docket_entries() -> None:
    selection = _selection(decision_entry_numbers=[50])
    plan = _docket_entries(
        (
            CourtListenerWebDocketEntry(
                row_id="entry-20",
                entry_number="20",
                filed_at="May 2, 2026",
                text="Minute order granting the motion to dismiss after oral ruling.",
            ),
            CourtListenerWebDocketEntry(
                row_id="entry-30",
                entry_number="30",
                filed_at="May 3, 2026",
                text=(
                    "Report and recommendation recommends granting defendants' "
                    "motion to dismiss."
                ),
            ),
            CourtListenerWebDocketEntry(
                row_id="entry-40",
                entry_number="40",
                filed_at="May 4, 2026",
                text="Tentative ruling denies the motion to dismiss.",
            ),
            CourtListenerWebDocketEntry(
                row_id="entry-50",
                entry_number="50",
                filed_at="May 5, 2026",
                text="Order deciding the motion to dismiss.",
            ),
        ),
        selection=selection,
        source_document_ids_by_entry={},
        generated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )

    leaky_entries = plan.entries[:3]
    assert all(not entry.model_visible for entry in leaky_entries)
    assert all(entry.contains_target_outcome for entry in leaky_entries)
    assert plan.exclusion_ledger_records
    assert plan.exclusion_ledger_records[0]["reason"] == "outcome_leakage"
    assert {
        "minute_order_resolving_target",
        "rr_already_resolving_target",
        "tentative_ruling_revealing_target",
    }.issubset(set(plan.exclusion_ledger_records[0]["secondary_exclusion_reasons"]))


def test_packet_planning_rejects_raw_prediction_units(tmp_path: Path) -> None:
    raw = _prediction_unit_record("candidate-1")
    raw.pop("schema_version")

    with pytest.raises(PacketInputPlanningError, match="must be finalized"):
        plan_packet_build_inputs(
            selection_records=(),
            download_records=(),
            parser_records=(),
            prediction_unit_records=(raw,),
            raw_html_dir=tmp_path,
            document_root=tmp_path,
            markdown_root=tmp_path,
            source_dir=tmp_path,
        )


def test_packet_planning_skips_candidate_exclusion(tmp_path: Path) -> None:
    excluded = _prediction_unit_record("candidate-1")
    excluded["status"] = "candidate_excluded"
    excluded["prediction_units"] = []
    excluded["exclusion"] = {
        "reason": "stage_a_boundary_unresolvable",
        "adjudication_id": "adj-candidate-1",
        "adjudication_sha256": "a" * 64,
    }

    plan = plan_packet_build_inputs(
        selection_records=(_selection(decision_entry_numbers=[50]),),
        download_records=(),
        parser_records=(),
        prediction_unit_records=(excluded,),
        raw_html_dir=tmp_path,
        document_root=tmp_path,
        markdown_root=tmp_path,
        source_dir=tmp_path,
    )

    assert plan.case_count == 0
    assert plan.packet_build_records == ()
    assert plan.candidate_manifest_records == ()


def test_packet_docket_planning_rejects_missing_decision_entry_numbers() -> None:
    with pytest.raises(PacketInputPlanningError, match="decision_entry_numbers"):
        _docket_entries(
            (
                CourtListenerWebDocketEntry(
                    row_id="entry-1",
                    entry_number="1",
                    filed_at="May 1, 2026",
                    text="Complaint.",
                ),
            ),
            selection=_selection(decision_entry_numbers=[]),
            source_document_ids_by_entry={},
            generated_at=datetime(2026, 5, 6, tzinfo=UTC),
        )


def test_anchor_window_exclusion_records_ledger_and_continues_batch(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw-html"
    raw_html_dir.mkdir()
    (raw_html_dir / "old-candidate.html").write_text(
        _packet_input_docket_html(decision_date="May 8, 2026"),
        encoding="utf-8",
    )
    (raw_html_dir / "new-candidate.html").write_text(
        _packet_input_docket_html(decision_date="May 12, 2026"),
        encoding="utf-8",
    )
    markdown_root = tmp_path / "markdown"
    for source_document_id in ("complaint", "mtd-memo", "decision"):
        markdown_path = markdown_root / "new-candidate" / f"{source_document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(f"{source_document_id} markdown", encoding="utf-8")

    plan = plan_packet_build_inputs(
        selection_records=(
            _packet_selection_record(
                candidate_id="old-candidate",
                case_id="old-case",
                decision_date="2026-05-08",
            ),
            _packet_selection_record(
                candidate_id="new-candidate",
                case_id="new-case",
                decision_date="2026-05-12",
            ),
        ),
        download_records=_packet_download_records("new-candidate"),
        parser_records=_packet_parser_records("new-candidate"),
        prediction_unit_records=(
            _prediction_unit_record("old-candidate"),
            _prediction_unit_record("new-candidate"),
        ),
        raw_html_dir=raw_html_dir,
        document_root=tmp_path / "documents",
        markdown_root=markdown_root,
        source_dir=tmp_path,
        generated_at=datetime(2026, 5, 13, tzinfo=UTC),
        decision_filed_on_or_after=date(2026, 5, 10),
    )

    assert [row["candidate_id"] for row in plan.packet_build_records] == [
        "new-candidate"
    ]
    assert [row["candidate_id"] for row in plan.candidate_manifest_records] == [
        "old-candidate",
        "new-candidate",
    ]
    assert len(plan.exclusion_ledger_records) == 1
    ledger_record = plan.exclusion_ledger_records[0]
    assert ledger_record["candidate_id"] == "old-candidate"
    assert ledger_record["primary_exclusion_reason"] == (
        "decision_before_release_anchor"
    )
    assert ledger_record["stage"] == "eligibility"
    assert ledger_record["secondary_exclusion_reasons"] == [
        "first_written_mtd_disposition_before_release_anchor"
    ]
    old_manifest = plan.candidate_manifest_records[0]
    assert old_manifest["mtd_decision_screen"]["status"] == "excluded"
    assert old_manifest["exclusion_ledger_entries"] == [ledger_record]


def test_anchor_excludes_when_first_written_mtd_disposition_precedes_anchor(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw-html"
    raw_html_dir.mkdir()
    (raw_html_dir / "candidate-1.html").write_text(
        _packet_input_docket_html(
            decision_date="July 1, 2026",
            earlier_decision_date="June 29, 2026",
        ),
        encoding="utf-8",
    )

    plan = plan_packet_build_inputs(
        selection_records=(
            _packet_selection_record(
                candidate_id="candidate-1",
                case_id="case-1",
                decision_date="2026-07-01",
            ),
        ),
        download_records=(),
        parser_records=(),
        prediction_unit_records=(_prediction_unit_record("candidate-1"),),
        raw_html_dir=raw_html_dir,
        document_root=tmp_path / "documents",
        markdown_root=tmp_path / "markdown",
        source_dir=tmp_path,
        generated_at=datetime(2026, 7, 2, tzinfo=UTC),
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert plan.packet_build_records == ()
    assert len(plan.exclusion_ledger_records) == 1
    ledger_record = plan.exclusion_ledger_records[0]
    assert ledger_record["primary_exclusion_reason"] == (
        "decision_before_release_anchor"
    )
    assert ledger_record["secondary_exclusion_reasons"] == [
        "first_written_mtd_disposition_before_release_anchor"
    ]
    assert ledger_record["source_entry_ids"] == ["entry-40"]
    assert "2026-06-29" in ledger_record["notes"]
    assert "2026-06-30" in ledger_record["notes"]
    candidate_manifest = plan.candidate_manifest_records[0]
    assert candidate_manifest["exclusion_ledger_entries"] == [ledger_record]


def test_anchor_pass_preserves_preexisting_strict_screen_exclusion_reasons() -> None:
    screen = _docket_screen_with_first_disposition_anchor(
        {
            "status": "excluded",
            "exclusion_reasons": ["multiple_target_motions_unlinked"],
            "decision_entries": [
                {
                    "row_id": "entry-16",
                    "entry_number": "16",
                    "filed_at": "July 1, 2026",
                    "text": "Order deciding motion to dismiss.",
                }
            ],
        },
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert screen["first_written_mtd_disposition_anchor_passed"] is True
    assert screen["status"] == "excluded"
    assert screen["exclusion_reasons"] == ["multiple_target_motions_unlinked"]


def test_any_packet_time_leakage_excludes_candidate_with_one_complete_ledger_entry(
    tmp_path: Path,
) -> None:
    candidate_id = "leaky-candidate"
    raw_html_dir = tmp_path / "raw-html"
    raw_html_dir.mkdir()
    (raw_html_dir / f"{candidate_id}.html").write_text(
        _packet_input_docket_html(
            decision_date="July 1, 2026",
            include_leaking_predecision_entry=True,
        ),
        encoding="utf-8",
    )
    markdown_root = tmp_path / "markdown"
    for source_document_id, markdown in {
        "complaint": (
            "Press report: the motion to dismiss survives as to the core claim."
        ),
        "mtd-memo": "Motion to dismiss memorandum.",
        "decision": "Decision markdown.",
    }.items():
        markdown_path = markdown_root / candidate_id / f"{source_document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")

    plan = plan_packet_build_inputs(
        selection_records=(
            _packet_selection_record(
                candidate_id=candidate_id,
                case_id="leaky-case",
                decision_date="2026-07-01",
            ),
        ),
        download_records=_packet_download_records(candidate_id),
        parser_records=_packet_parser_records(candidate_id),
        prediction_unit_records=(_prediction_unit_record(candidate_id),),
        raw_html_dir=raw_html_dir,
        document_root=tmp_path / "documents",
        markdown_root=markdown_root,
        source_dir=tmp_path,
        generated_at=datetime(2026, 7, 2, tzinfo=UTC),
    )

    assert plan.packet_build_records == ()
    assert len(plan.exclusion_ledger_records) == 1
    ledger_record = plan.exclusion_ledger_records[0]
    assert ledger_record["primary_exclusion_reason"] == "outcome_leakage"
    assert set(ledger_record["secondary_exclusion_reasons"]) == {
        "minute_order_resolving_target",
        "public_reporting_revealing_target",
    }
    assert ledger_record["source_entry_ids"] == ["entry-20"]
    assert ledger_record["source_document_ids"] == [f"{candidate_id}-complaint"]
    candidate_manifest = plan.candidate_manifest_records[0]
    assert candidate_manifest["exclusion_ledger_entries"] == [ledger_record]


def test_download_restriction_overrides_conflicting_public_selection_metadata(
    tmp_path: Path,
) -> None:
    candidate_id = "public-candidate"
    raw_html_dir = tmp_path / "raw-html"
    raw_html_dir.mkdir()
    (raw_html_dir / f"{candidate_id}.html").write_text(
        _packet_input_docket_html(decision_date="July 1, 2026"),
        encoding="utf-8",
    )
    markdown_root = tmp_path / "markdown"
    for source_document_id in ("complaint", "mtd-memo", "decision", "sealed"):
        markdown_path = markdown_root / candidate_id / f"{source_document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text("source markdown", encoding="utf-8")
    selection = _packet_selection_record(
        candidate_id=candidate_id,
        case_id="public-case",
        decision_date="2026-07-01",
    )
    documents = cast(list[dict[str, object]], selection["documents"])
    sealed_document = _selection_document(
        candidate_id,
        "sealed",
        "other",
        35,
        True,
    )
    sealed_document["redaction_or_seal_status"] = "public"
    documents.append(sealed_document)
    download_records = (
        *_packet_download_records(candidate_id),
        {
            "candidate_id": candidate_id,
            "source_provider": "courtlistener",
            "source_document_id": "sealed",
            "docket_entry_number": 35,
            "document_role": "other",
            "source_url": f"fixture://{candidate_id}/sealed.pdf",
            "local_path": f"{candidate_id}/sealed.pdf",
            "sha256": f"{'sealed':0<64}"[:64],
            "is_sealed": True,
        },
    )
    parser_records: tuple[dict[str, object], ...] = (
        *_packet_parser_records(candidate_id),
        {
            "candidate_id": candidate_id,
            "source_document_id": "sealed",
            "status": "succeeded",
            "markdown_path": f"{candidate_id}/sealed.md",
            "quality_flags": [],
            "extracted_text": {
                "source_document_id": "sealed",
                "text_sha256": f"{'sealed':0<64}"[:64],
                "quality_flags": [],
            },
        },
    )

    plan = plan_packet_build_inputs(
        selection_records=(selection,),
        download_records=download_records,
        parser_records=parser_records,
        prediction_unit_records=(_prediction_unit_record(candidate_id),),
        raw_html_dir=raw_html_dir,
        document_root=tmp_path / "documents",
        markdown_root=markdown_root,
        source_dir=tmp_path,
        generated_at=datetime(2026, 7, 2, tzinfo=UTC),
    )

    packet_record = plan.packet_build_records[0]
    sealed_source = next(
        document
        for document in packet_record["documents"]
        if document["source_document_id"] == f"{candidate_id}-sealed"
    )
    assert sealed_source["redaction_or_seal_status"] == "sealed"
    assert sealed_source["availability_status"] == "restricted"
    assert sealed_source["is_mounted_for_model"] is False
    assert all(
        record["source_document_id"] != f"{candidate_id}-sealed"
        for record in plan.document_manifest_records
    )
    assert all(
        record["source_document_id"] != f"{candidate_id}-sealed"
        for record in packet_record["parsed_documents"]
    )


def _selection(*, decision_entry_numbers: list[int]) -> dict[str, object]:
    return {
        "candidate_id": "candidate-1",
        "case_id": "case-1",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "decision_date": "2026-05-05",
        "decision_entry_numbers": decision_entry_numbers,
    }


def _packet_selection_record(
    *,
    candidate_id: str,
    case_id: str,
    decision_date: str,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "case_id": case_id,
        "case_name": f"{case_id} plaintiff v. defendant",
        "court": "S.D.N.Y.",
        "docket_number": f"1:26-cv-{case_id[-4:]}",
        "source_url": f"https://www.courtlistener.com/docket/{candidate_id}/",
        "decision_date": decision_date,
        "target_motion_entry_numbers": [34],
        "decision_entry_numbers": [50],
        "documents": [
            _selection_document(candidate_id, "complaint", "complaint", 1, True),
            _selection_document(
                candidate_id,
                "mtd-memo",
                "motion_to_dismiss_memorandum",
                34,
                True,
            ),
            _selection_document(candidate_id, "decision", "decision", 50, False),
        ],
    }


def _selection_document(
    candidate_id: str,
    source_document_id: str,
    document_role: str,
    docket_entry_number: int,
    model_visible: bool,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": document_role,
        "source_url": f"fixture://{candidate_id}/{source_document_id}.pdf",
        "description": source_document_id,
        "model_visible": model_visible,
        "contains_target_outcome": not model_visible,
    }


def _packet_download_records(candidate_id: str) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "candidate_id": candidate_id,
            "source_provider": "courtlistener",
            "source_document_id": source_document_id,
            "docket_entry_number": docket_entry_number,
            "document_role": role,
            "source_url": f"fixture://{candidate_id}/{source_document_id}.pdf",
            "local_path": f"{candidate_id}/{source_document_id}.pdf",
            "sha256": f"{source_document_id:0<64}"[:64],
        }
        for source_document_id, role, docket_entry_number in (
            ("complaint", "complaint", 1),
            ("mtd-memo", "motion_to_dismiss_memorandum", 34),
            ("decision", "decision", 50),
        )
    )


def _packet_parser_records(candidate_id: str) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "candidate_id": candidate_id,
            "source_document_id": source_document_id,
            "status": "succeeded",
            "markdown_path": f"{candidate_id}/{source_document_id}.md",
            "quality_flags": [],
            "extracted_text": {
                "source_document_id": source_document_id,
                "text_sha256": f"{source_document_id:0<64}"[:64],
                "quality_flags": [],
            },
        }
        for source_document_id in ("complaint", "mtd-memo", "decision")
    )


def _prediction_unit_record(candidate_id: str) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.finalized_prediction_units.v1",
        "status": "finalized",
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "raw_prediction_units_sha256": "a" * 64,
        "prediction_units": [
            {
                "unit_id": f"{candidate_id}-unit",
                "source_citations": [{"document_id": "complaint", "page": 1}],
                "source_unit_sha256s": ["b" * 64],
                "adjudication_id": f"automatic:{'b' * 64}",
                "adjudication_sha256": None,
                "disposition": "ACCEPT",
            }
        ],
        "exclusion": None,
    }


def _packet_input_docket_html(
    *,
    decision_date: str,
    earlier_decision_date: str | None = None,
    include_leaking_predecision_entry: bool = False,
) -> str:
    earlier_decision = (
        ""
        if earlier_decision_date is None
        else f"""
          <div class="row odd" id="entry-40">
            <div class="col-xs-1"><p>40</p></div>
            <div class="col-xs-3"><p>{earlier_decision_date}</p></div>
            <div class="col-xs-8"><p>ORDER granting Motion to Dismiss.</p></div>
          </div>
        """
    )
    leaking_predecision = (
        ""
        if not include_leaking_predecision_entry
        else """
          <div class="row odd" id="entry-20">
            <div class="col-xs-1"><p>20</p></div>
            <div class="col-xs-3"><p>Feb 2, 2026</p></div>
            <div class="col-xs-8">
              <p>Minute order granting the motion to dismiss after oral ruling.</p>
            </div>
          </div>
        """
    )
    return f"""
    <html>
      <body>
        <div id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1"><p>1</p></div>
            <div class="col-xs-3"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8"><p>COMPLAINT filed by Plaintiff.</p></div>
          </div>
          <div class="row even" id="entry-34">
            <div class="col-xs-1"><p>34</p></div>
            <div class="col-xs-3"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8"><p>MOTION to Dismiss.</p></div>
          </div>
          {leaking_predecision}
          {earlier_decision}
          <div class="row odd" id="entry-50">
            <div class="col-xs-1"><p>50</p></div>
            <div class="col-xs-3"><p>{decision_date}</p></div>
            <div class="col-xs-8"><p>ORDER granting 34 Motion to Dismiss.</p></div>
          </div>
        </div>
      </body>
    </html>
    """
