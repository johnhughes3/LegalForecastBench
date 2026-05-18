from __future__ import annotations

from pathlib import Path

from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.public_packet_planner import (
    plan_public_packet_downloads,
)


def test_public_packet_planner_selects_free_core_packet_documents(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(_docket_html(), encoding="utf-8")

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    assert plan.download_request_count == 4
    selected = plan.selected_cases[0]
    assert selected.exclusion_reasons == ()
    assert [document.document_role for document in selected.documents] == [
        DocumentRole.COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.OPPOSITION,
        DocumentRole.DECISION,
    ]
    assert selected.documents[-1].model_visible is False
    assert selected.documents[-1].contains_target_outcome is True
    assert plan.download_requests[0].source_url == (
        "https://storage.courtlistener.com/recap/complaint.pdf"
    )


def test_public_packet_planner_reports_public_document_shortfall(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(
        _docket_html(include_motion=False),
        encoding="utf-8",
    )

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 0
    assert plan.summary_record()["shortfall"] == 25
    assert plan.candidate_plans[0].exclusion_reasons == ("no_free_target_mtd_document",)


def test_public_packet_planner_uses_role_matched_free_documents(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(
        _docket_html_with_procedural_false_positives(),
        encoding="utf-8",
    )

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    planned_roles = [
        (document.document_role, document.description)
        for document in selected.documents
    ]
    assert planned_roles == [
        (DocumentRole.COMPLAINT, "Complaint"),
        (DocumentRole.MTD_MEMORANDUM, "Memorandum of Law"),
        (DocumentRole.DECISION, "Order on Motion to Dismiss"),
    ]
    assert selected.documents[0].source_url == (
        "https://storage.courtlistener.com/recap/complaint.pdf"
    )
    assert selected.documents[1].source_url == (
        "https://storage.courtlistener.com/recap/mtd-memo.pdf"
    )


def test_public_packet_planner_prefers_removal_complaint_attachment(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    (raw_html_dir / "123.html").write_text(
        _docket_html_with_notice_removal_complaint_attachment(),
        encoding="utf-8",
    )

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[0].document_role is DocumentRole.COMPLAINT
    assert selected.documents[0].description == "Exhibit A-E"
    assert selected.documents[0].source_url == (
        "https://storage.courtlistener.com/recap/removal-exhibit-a-e.pdf"
    )


def test_public_packet_planner_accepts_judgment_on_pleadings_target(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    html = _docket_html().replace(
        "MOTION to Dismiss filed by Defendant.",
        "MOTION for Judgment on the Pleadings filed by Defendant.",
    ).replace(
        "Dismiss</p>",
        "Judgment on the Pleadings</p>",
        1,
    )
    (raw_html_dir / "123.html").write_text(html, encoding="utf-8")

    plan = plan_public_packet_downloads(
        (_screened_case(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[1].document_role is DocumentRole.MTD_NOTICE
    assert selected.documents[1].description == "Judgment on the Pleadings"


def test_public_packet_planner_can_use_embedded_selected_entries(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"

    plan = plan_public_packet_downloads(
        (_screened_case_with_embedded_entries(),),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
        use_embedded_entries=True,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert [document.document_role for document in selected.documents] == [
        DocumentRole.COMPLAINT,
        DocumentRole.MTD_NOTICE,
        DocumentRole.DECISION,
    ]
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/5/example/"
    )


def test_public_packet_planner_accepts_exact_target_mtd_memorandum_when_role_is_noisy(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"

    record = _screened_case_with_embedded_entries()
    target_entry = record["selected_entries"][1]
    assert isinstance(target_entry, dict)
    target_entry["text"] = (
        "5 Feb 1, 2026 Notice of manual filing of MOTION to Dismiss by "
        "Defendant. Text of Proposed Order."
    )
    target_entry["documents"] = [
        {
            "kind": "Main Document",
            "description": "Dismiss for Failure to State a Claim",
            "href": "https://ecf.example.invalid/doc1",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        },
        {
            "kind": "Att 1 attachment",
            "description": "Memorandum",
            "href": "https://www.courtlistener.com/docket/123/5/1/example/",
            "action_label": "Download PDF",
            "pacer_only": False,
        },
        {
            "kind": "Att 2 attachment",
            "description": "Text of Proposed Order",
            "href": "https://ecf.example.invalid/doc2",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        },
    ]

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
        use_embedded_entries=True,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[1].document_role is DocumentRole.MTD_MEMORANDUM
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/5/1/example/"
    )


def test_public_packet_planner_prefers_free_support_memo_for_pacer_only_target(
    tmp_path: Path,
) -> None:
    raw_html_dir = tmp_path / "raw_html"
    record = _screened_case_with_embedded_entries()
    target_entry = record["selected_entries"][1]
    assert isinstance(target_entry, dict)
    target_entry["documents"] = [
        {
            "kind": "Main Document",
            "description": "Dismiss",
            "href": "https://ecf.example.invalid/doc1",
            "action_label": "Buy on PACER",
            "pacer_only": True,
        }
    ]
    record["selected_entries"].insert(
        2,
        {
            "row_id": "entry-6",
            "entry_number": "6",
            "filed_at": "Feb 2, 2026",
            "text": "6 Feb 2, 2026 Memorandum in Support re 5 MOTION to Dismiss.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Memorandum",
                    "href": "https://www.courtlistener.com/docket/123/6/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                },
            ],
        },
    )
    record["selected_entries"].insert(
        3,
        {
            "row_id": "entry-7",
            "entry_number": "7",
            "filed_at": "Feb 3, 2026",
            "text": "7 Feb 3, 2026 MOTION to Dismiss unrelated crossclaim.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Dismiss",
                    "href": "https://www.courtlistener.com/docket/123/7/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                },
            ],
        },
    )

    plan = plan_public_packet_downloads(
        (record,),
        raw_html_dir=raw_html_dir,
        target_clean_cases=25,
        allow_inferred_target_mtd=True,
        use_embedded_entries=True,
    )

    assert plan.selected_case_count == 1
    selected = plan.selected_cases[0]
    assert selected.documents[1].document_role is DocumentRole.MTD_MEMORANDUM
    assert selected.documents[1].source_url == (
        "https://www.courtlistener.com/docket/123/6/example/"
    )


def _screened_case() -> dict[str, object]:
    return {
        "candidate": {
            "docket_id": "123",
            "candidate_key": "123",
            "metadata": {
                "case_id": "123",
                "case_name": "Example v. Defendant",
                "court": "District Court, D. Example",
                "docket_number": "1:26-cv-1",
            },
            "url": "https://www.courtlistener.com/docket/123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
    }


def _screened_case_with_embedded_entries() -> dict[str, object]:
    record = _screened_case()
    record["selected_entries"] = [
        {
            "row_id": "entry-1",
            "entry_number": "1",
            "filed_at": "Jan 1, 2026",
            "text": "1 Jan 1, 2026 COMPLAINT filed by Plaintiff.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Complaint",
                    "href": "https://www.courtlistener.com/docket/123/1/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                    "freely_available": True,
                },
            ],
        },
        {
            "row_id": "entry-5",
            "entry_number": "5",
            "filed_at": "Feb 1, 2026",
            "text": "5 Feb 1, 2026 MOTION to Dismiss filed by Defendant.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Dismiss",
                    "href": "https://www.courtlistener.com/docket/123/5/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                    "freely_available": True,
                },
            ],
        },
        {
            "row_id": "entry-16",
            "entry_number": "16",
            "filed_at": "May 8, 2026",
            "text": "16 May 8, 2026 ORDER on Motion to Dismiss.",
            "documents": [
                {
                    "kind": "Main Document",
                    "description": "Order on Motion to Dismiss",
                    "href": "https://www.courtlistener.com/docket/123/16/example/",
                    "action_label": "Download PDF",
                    "pacer_only": False,
                    "freely_available": True,
                },
            ],
        },
    ]
    return record


def _docket_html(*, include_motion: bool = True) -> str:
    motion = (
        """
          <div class="row odd" id="entry-5">
            <div class="col-xs-1 text-center"><p>5</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>MOTION to Dismiss filed by Defendant.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        """
        if include_motion
        else ""
    )
    return f"""
    <html>
      <body>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1 text-center"><p>1</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>COMPLAINT filed by Plaintiff.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Complaint</p></div>
                <a href="https://storage.courtlistener.com/recap/complaint.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          {motion}
          <div class="row even" id="entry-8">
            <div class="col-xs-1 text-center"><p>8</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 15, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>Opposition to Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Opposition to Motion</p></div>
                <a href="https://storage.courtlistener.com/recap/opp.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-16">
            <div class="col-xs-1 text-center"><p>16</p></div>
            <div class="col-xs-3 col-sm-2"><p>May 8, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>ORDER on Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def _docket_html_with_procedural_false_positives() -> str:
    return """
    <html>
      <body>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1 text-center"><p>1</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>COMPLAINT filed by Plaintiff.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Complaint</p></div>
                <a href="https://storage.courtlistener.com/recap/complaint.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-2">
            <div class="col-xs-1 text-center"><p>2</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 2, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>STANDING ORDER upon filing of the complaint.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6">
                  <p>Initial Order upon Filing of Complaint - form only</p>
                </div>
                <a href="https://storage.courtlistener.com/recap/initial-order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row odd" id="entry-5">
            <div class="col-xs-1 text-center"><p>5</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>MOTION to Dismiss filed by Defendant.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Motion to Dismiss</p></div>
                <a href="https://ecf.example.invalid/doc1">Buy on PACER</a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Att 1 achment</p></div>
                <div class="col-xs-6"><p>Declaration</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd-decl.pdf">
                  Download PDF
                </a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Att 2 achment</p></div>
                <div class="col-xs-6"><p>Memorandum of Law</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd-memo.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-9">
            <div class="col-xs-1 text-center"><p>9</p></div>
            <div class="col-xs-3 col-sm-2"><p>Mar 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>Exhibit mentioning facts alleged in the amended complaint.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6">
                  <p>Exhibit 3: Timeline (Alleged in the Amended Complaint)</p>
                </div>
                <a href="https://storage.courtlistener.com/recap/timeline.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-16">
            <div class="col-xs-1 text-center"><p>16</p></div>
            <div class="col-xs-3 col-sm-2"><p>May 8, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>ORDER on Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """


def _docket_html_with_notice_removal_complaint_attachment() -> str:
    return """
    <html>
      <body>
        <div class="fake-table col-xs-12" id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1 text-center"><p>1</p></div>
            <div class="col-xs-3 col-sm-2"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>NOTICE OF REMOVAL from state court. (Attachments: # 1 Exhibit A-E)
              Exhibit A: Complaint and all accompanying documents.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Notice of Removal</p></div>
                <a href="https://storage.courtlistener.com/recap/removal-main.pdf">
                  Download PDF
                </a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Attachment 1</p></div>
                <div class="col-xs-6"><p>Exhibit A-E</p></div>
                <a href="https://storage.courtlistener.com/recap/removal-exhibit-a-e.pdf">
                  Download PDF
                </a>
              </div>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Attachment 2</p></div>
                <div class="col-xs-6"><p>Civil Cover Sheet</p></div>
                <a href="https://storage.courtlistener.com/recap/cover-sheet.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row odd" id="entry-5">
            <div class="col-xs-1 text-center"><p>5</p></div>
            <div class="col-xs-3 col-sm-2"><p>Feb 1, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>MOTION to Dismiss filed by Defendant.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/mtd.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
          <div class="row even" id="entry-16">
            <div class="col-xs-1 text-center"><p>16</p></div>
            <div class="col-xs-3 col-sm-2"><p>May 8, 2026</p></div>
            <div class="col-xs-8 col-lg-7">
              <p>ORDER on Motion to Dismiss.</p>
              <div class="row recap-documents">
                <div class="col-xs-3"><p>Main Document</p></div>
                <div class="col-xs-6"><p>Order on Motion to Dismiss</p></div>
                <a href="https://storage.courtlistener.com/recap/order.pdf">
                  Download PDF
                </a>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
