from __future__ import annotations

import json
import urllib.request
from datetime import date
from email.message import Message
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.courtlistener_acquisition import (
    CourtListenerClientError,
    _CourtListenerRedirectHandler,
    screen_courtlistener_docket_page,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerDocket
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_case_dev_docket_metadata,
)


def test_docket_html_refuses_off_allowlist_redirect_hop() -> None:
    handler = _CourtListenerRedirectHandler()
    with pytest.raises(CourtListenerClientError, match="host allowlist"):
        handler.redirect_request(
            urllib.request.Request("https://www.courtlistener.com/docket/1/"),
            object(),
            302,
            "Found",
            Message(),
            "https://evil.example/docket/1/",
        )


def test_discover_courtlistener_help_documents_live_authority(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "discover-courtlistener", "--help"])
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "--eligibility-anchor" in output
    assert "--search-window-start" in output
    assert "--search-window-end" in output
    assert "--live" in output
    assert "--courtlistener-fixture" in output
    assert "--docket-html-fixture-dir" in output
    assert "--screened-cases-output" in output
    assert "--exclusions-output" in output


def test_discover_courtlistener_produces_plan_public_downloads_input(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    fixture_path = tmp_path / "courtlistener.jsonl"
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir()
    (html_fixture_dir / "123.html").write_text(
        _docket_html(decision_dates=("June 30, 2026",)),
        encoding="utf-8",
    )
    _write_jsonl(
        fixture_path,
        [
            _response(
                path="/search/",
                params={
                    "q": (
                        '"order on motion to dismiss" AND '
                        "entry_date_filed:[2026-06-30 TO 2026-07-12]"
                    ),
                    "type": "r",
                    "order_by": "score desc",
                    "available_only": "on",
                    "page_size": 50,
                },
                payload={
                    "results": [
                        {
                            "docket_id": 123,
                            "docket_entry_id": 16,
                            "description": "Order on motion to dismiss",
                            "entry_date_filed": "2026-06-30",
                        }
                    ],
                    "next": None,
                },
            ),
            _response(
                path="/dockets/123/",
                payload={
                    "id": 123,
                    "court": ("https://www.courtlistener.com/api/rest/v4/courts/nysd/"),
                    "docket_number": "1:26-cv-00001",
                    "case_name": "Fixture v. Example",
                    "nature_of_suit": "Civil Rights",
                    "nos_macro_category": "civil_rights",
                    "related_family_id": "related-fixture",
                    "mdl_family_id": "mdl-fixture",
                    "date_filed": "2026-01-01",
                    "absolute_url": (
                        "https://www.courtlistener.com/docket/123/fixture-v-example/"
                    ),
                },
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                "batch-001",
                "--query-term",
                "order on motion to dismiss",
                "--target-clean-cases",
                "1",
                "--max-candidates",
                "5",
                "--courtlistener-fixture",
                str(fixture_path),
                "--docket-html-fixture-dir",
                str(html_fixture_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [screened] = _read_jsonl(output_root / "courtlistener-screened-cases.jsonl")
    assert screened["candidate"]["docket_id"] == "123"
    assert screened["candidate"]["metadata"]["court"] == "nysd"
    assert screened["candidate"]["metadata"]["nature_of_suit"] == "Civil Rights"
    assert screened["candidate"]["metadata"]["nos_macro_category"] == "civil_rights"
    assert screened["candidate"]["metadata"]["related_family_id"] == ("related-fixture")
    assert screened["candidate"]["metadata"]["mdl_family_id"] == "mdl-fixture"
    assert screened["ai"] == {
        "target_motion_entry_numbers": ["5"],
        "decision_entry_numbers": ["16"],
    }
    assert screened["first_written_mtd_disposition_date"] == "2026-06-30"
    assert len(screened["selected_entries"]) == 3
    assert _read_jsonl(output_root / "courtlistener-discovery-exclusions.jsonl") == []
    assert (output_root / "raw-courtlistener-html" / "123.html").is_file()

    summary = _read_json(output_root / "courtlistener-discovery-summary.json")
    assert summary["accepted_case_count"] == 1
    assert summary["excluded_case_count"] == 0
    assert summary["anchor_date"] == "2026-06-30"
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        assert store.cycle_policy["eligibility_anchor"] == "2026-06-30"
        assert store.batch_digest("batch-001")

    snapshot_path, cycle_hash = _complete_snapshot(
        tmp_path / "cycle",
        [screened],
        raw_html_dir=output_root / "raw-courtlistener-html",
    )

    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--snapshot",
                str(snapshot_path),
                "--expected-cycle-hash",
                cycle_hash,
                "--screened-cases",
                str(snapshot_path / "screened-cases.jsonl"),
                "--raw-html-dir",
                str(output_root / "raw-courtlistener-html"),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(output_root / "public-downloads"),
                "--execute",
            ]
        )
        == 0
    )
    [selected] = _read_jsonl(
        output_root / "public-downloads" / "public-packet-selection.jsonl"
    )
    assert selected["candidate_id"] == "123"
    assert selected["decision_date"] == "2026-06-30"
    assert selected["nature_of_suit"] == "Civil Rights"
    assert selected["nos_macro_category"] == "civil_rights"
    assert selected["related_family_id"] == "related-fixture"
    assert selected["mdl_family_id"] == "mdl-fixture"
    assert selected["target_motion_entry_numbers"] == [5]
    assert selected["decision_entry_numbers"] == [16]


@pytest.mark.parametrize(
    ("first_disposition_date", "expected_reason", "notes_fragment"),
    (
        (
            "June 29, 2026",
            "decision_before_release_anchor",
            "first written MTD disposition",
        ),
        ("", "parse_error", "date could not be parsed"),
    ),
)
def test_discover_courtlistener_excludes_unproven_or_preanchor_first_disposition(
    tmp_path: Path,
    first_disposition_date: str,
    expected_reason: str,
    notes_fragment: str,
) -> None:
    output_root = tmp_path / "acquisition"
    fixture_path = tmp_path / "courtlistener.jsonl"
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir()
    (html_fixture_dir / "123.html").write_text(
        _docket_html(decision_dates=(first_disposition_date, "July 1, 2026")),
        encoding="utf-8",
    )
    _write_jsonl(
        fixture_path,
        [
            _response(
                path="/search/",
                params={
                    "q": (
                        '"order on motion to dismiss" AND '
                        "entry_date_filed:[2026-06-30 TO 2026-07-12]"
                    ),
                    "type": "r",
                    "order_by": "score desc",
                    "available_only": "on",
                    "page_size": 50,
                },
                payload={
                    "results": [{"docket_id": 123, "docket_entry_id": 17}],
                    "next": None,
                },
            ),
            _response(
                path="/dockets/123/",
                payload={
                    "id": 123,
                    "court": "nysd",
                    "docket_number": "1:26-cv-00001",
                    "case_name": "Fixture v. Example",
                    "absolute_url": (
                        "https://www.courtlistener.com/docket/123/fixture-v-example/"
                    ),
                },
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--query-term",
                "order on motion to dismiss",
                "--courtlistener-fixture",
                str(fixture_path),
                "--docket-html-fixture-dir",
                str(html_fixture_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "courtlistener-screened-cases.jsonl") == []
    [exclusion] = _read_jsonl(output_root / "courtlistener-discovery-exclusions.jsonl")
    assert exclusion["stage"] == "eligibility"
    assert exclusion["primary_exclusion_reason"] == expected_reason
    assert notes_fragment in exclusion["notes"]
    assert (output_root / "raw-courtlistener-html" / "123.html").is_file()


@pytest.mark.parametrize(
    "preanchor_entry",
    (
        (16, "June 10, 2026", "Order on Motion to Dismiss"),
        (
            16,
            "October 23, 2025",
            "ELECTRONIC ORDER: motion to dismiss 5 is denied as moot",
        ),
        (16, "June 9, 2026", "ORDER regarding 5 motion to dismiss"),
    ),
)
def test_canonical_screen_excludes_preanchor_generic_or_moot_mtd_disposition(
    preanchor_entry: tuple[int, str, str],
) -> None:
    screened, exclusion = _screen_custom_docket(
        entries=(
            (1, "January 2, 2026", "COMPLAINT filed by Plaintiff"),
            (5, "February 2, 2026", "MOTION to Dismiss filed by Defendant"),
            preanchor_entry,
            (40, "July 2, 2026", "ORDER granting 5 Motion to Dismiss"),
        )
    )

    assert screened is None
    assert exclusion is not None
    assert exclusion.reason == "decision_before_release_anchor"


def test_canonical_screen_excludes_preanchor_recommendation_later_adopted() -> None:
    screened, exclusion = _screen_custom_docket(
        entries=(
            (1, "January 2, 2026", "COMPLAINT filed by Plaintiff"),
            (18, "January 5, 2026", "MOTION to Dismiss filed by Defendant"),
            (31, "January 29, 2026", "Report & Recommendation"),
            (
                33,
                "July 9, 2026",
                "MEMORANDUM ORDER adopting 31 Report & Recommendation; "
                "granting 18 Motion to Dismiss",
            ),
        )
    )

    assert screened is None
    assert exclusion is not None
    assert exclusion.reason == "decision_before_release_anchor"


def test_canonical_screen_accepts_genuinely_first_postanchor_disposition() -> None:
    screened, exclusion = _screen_custom_docket(
        entries=(
            (1, "January 2, 2026", "COMPLAINT filed by Plaintiff"),
            (5, "February 2, 2026", "MOTION to Dismiss filed by Defendant"),
            (
                16,
                "June 20, 2026",
                "Order re Rule 12(b) Motions AND ~Util - Set Deadlines",
            ),
            (20, "July 1, 2026", "Order on Motion to Dismiss"),
            (21, "July 2, 2026", "ORDER granting 5 Motion to Dismiss"),
        )
    )

    assert exclusion is None
    assert screened is not None
    assert screened["first_written_mtd_disposition_date"] == "2026-07-01"


def test_discover_courtlistener_execute_requires_live_or_complete_fixture_pair(
    tmp_path: Path,
    capsys: Any,
) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--output-root",
                str(tmp_path / "output"),
                "--execute",
            ]
        )
        == 2
    )
    assert "requires --live or both" in capsys.readouterr().err


def test_discovery_anchor_stays_fixed_while_search_window_advances(
    tmp_path: Path,
) -> None:
    summaries: list[dict[str, Any]] = []
    for batch, start, end in (
        ("001", "2026-06-30", "2026-07-12"),
        ("002", "2026-07-05", "2026-07-19"),
    ):
        output_root = tmp_path / batch
        assert (
            main(
                [
                    "acquisition",
                    "discover-courtlistener",
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--search-window-start",
                    start,
                    "--search-window-end",
                    end,
                    "--output-root",
                    str(output_root),
                ]
            )
            == 0
        )
        summaries.append(
            _read_json(output_root / "courtlistener-discovery-summary.json")
        )

    assert [summary["anchor_date"] for summary in summaries] == [
        "2026-06-30",
        "2026-06-30",
    ]
    assert summaries[1]["search_window_start"] == "2026-07-05"
    assert summaries[1]["search_window_end"] == "2026-07-19"


def test_discovery_rejects_reversed_search_window(tmp_path: Path, capsys: Any) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-07-12",
                "--search-window-end",
                "2026-07-11",
                "--output-root",
                str(tmp_path / "output"),
            ]
        )
        == 2
    )
    assert "cannot precede" in capsys.readouterr().err


def test_discover_courtlistener_live_requires_token(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.delenv("COURTLISTENER_API_TOKEN", raising=False)

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--output-root",
                str(tmp_path / "output"),
                "--live",
                "--execute",
            ]
        )
        == 2
    )
    assert "COURTLISTENER_API_TOKEN is required" in capsys.readouterr().err


def test_discover_courtlistener_records_local_validation_failure(
    tmp_path: Path,
    capsys: Any,
) -> None:
    output_root = tmp_path / "output"
    fixture_path = tmp_path / "courtlistener.jsonl"
    fixture_path.write_text("", encoding="utf-8")
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir()

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--search-page-size",
                "101",
                "--courtlistener-fixture",
                str(fixture_path),
                "--docket-html-fixture-dir",
                str(html_fixture_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    expected_reason = "search_page_size must be between 1 and 100"
    assert expected_reason in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards" / "discover-courtlistener.json")
    assert failure["status"] == "failed"
    assert failure["failure_reason"] == expected_reason
    assert failure["paid_activity_executed"] is False


@pytest.mark.parametrize(
    ("changed_flag", "changed_value"),
    (
        ("--target-clean-cases", "2"),
        ("--max-candidates", "10"),
    ),
)
def test_discover_courtlistener_rejects_batch_limit_drift(
    tmp_path: Path,
    capsys: Any,
    changed_flag: str,
    changed_value: str,
) -> None:
    args = _cycle_store_discovery_args(tmp_path)
    assert main(args) == 0

    changed_args = [*args]
    changed_args[changed_args.index(changed_flag) + 1] = changed_value
    assert main(changed_args) == 2
    assert "batch config mismatch" in capsys.readouterr().err


def test_discover_courtlistener_invalid_limits_do_not_freeze_batch(
    tmp_path: Path,
    capsys: Any,
) -> None:
    args = _cycle_store_discovery_args(tmp_path)
    invalid_args = [*args]
    invalid_args[invalid_args.index("--search-page-size") + 1] = "101"

    assert main(invalid_args) == 2
    assert "search_page_size must be between 1 and 100" in capsys.readouterr().err

    assert main(args) == 0


def _cycle_store_discovery_args(tmp_path: Path) -> list[str]:
    fixture_path = tmp_path / "courtlistener.jsonl"
    _write_jsonl(
        fixture_path,
        [
            _response(
                path="/search/",
                params={
                    "q": '"test" AND entry_date_filed:[2026-06-30 TO 2026-07-12]',
                    "type": "r",
                    "order_by": "score desc",
                    "available_only": "on",
                    "page_size": 50,
                },
                payload={"results": [], "next": None},
            )
        ],
    )
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir(exist_ok=True)
    return [
        "acquisition",
        "discover-courtlistener",
        "--eligibility-anchor",
        "2026-06-30",
        "--search-window-start",
        "2026-06-30",
        "--search-window-end",
        "2026-07-12",
        "--cycle-store",
        str(tmp_path / "cycle.sqlite3"),
        "--batch-id",
        "batch-001",
        "--query-term",
        "test",
        "--target-clean-cases",
        "1",
        "--max-candidates",
        "5",
        "--search-page-size",
        "50",
        "--courtlistener-fixture",
        str(fixture_path),
        "--docket-html-fixture-dir",
        str(html_fixture_dir),
        "--output-root",
        str(tmp_path / "output"),
        "--execute",
    ]


def _response(
    *,
    path: str,
    payload: dict[str, object],
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "method": "GET",
        "path": path,
        "params": {} if params is None else params,
        "status_code": 200,
        "payload": payload,
    }


def _docket_html(*, decision_dates: tuple[str, ...]) -> str:
    decision_rows = "".join(
        _entry_html(
            number=16 + index,
            filed_at=filed_at,
            text="ORDER granting in part and denying in part Motion to Dismiss",
            description="Order on Motion to Dismiss",
        )
        for index, filed_at in enumerate(decision_dates)
    )
    return (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=1,
            filed_at="January 2, 2026",
            text="COMPLAINT filed by Plaintiff",
            description="Complaint",
        )
        + _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
            extra_document_description="Memorandum in Support of Motion to Dismiss",
        )
        + decision_rows
        + "</div></body></html>"
    )


def _entry_html(
    *,
    number: int,
    filed_at: str,
    text: str,
    description: str,
    extra_document_description: str | None = None,
) -> str:
    extra_document = (
        ""
        if extra_document_description is None
        else (
            '<div class="row recap-documents"><div>Attachment 1</div>'
            f"<div>{extra_document_description}</div>"
            f'<a href="https://storage.courtlistener.com/{number}-memo.pdf">'
            "Download PDF</a></div>"
        )
    )
    return (
        f'<div class="row" id="entry-{number}">'
        f'<div class="col-xs-1">{number}</div>'
        f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
        f'<div class="col-xs-8">{text}'
        '<div class="recap-documents">'
        "<div>Main Document</div>"
        f"<div>{description}</div>"
        f'<a href="https://storage.courtlistener.com/{number}.pdf">Download PDF</a>'
        f"</div>{extra_document}</div></div>"
    )


def _screen_custom_docket(
    *,
    entries: tuple[tuple[int, str, str], ...],
) -> tuple[dict[str, Any] | None, Any]:
    html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + "".join(
            _entry_html(
                number=number,
                filed_at=filed_at,
                text=text,
                description=text,
            )
            for number, filed_at, text in entries
        )
        + "</div></body></html>"
    )
    docket = CourtListenerDocket(
        docket_id="123",
        court_id="nysd",
        docket_number="1:26-cv-00001",
        case_name="Fixture v. Example",
        date_filed="2026-01-02",
        source_url="https://www.courtlistener.com/docket/123/fixture-v-example/",
        raw={},
    )
    metadata_screen = screen_case_dev_docket_metadata(
        {
            "id": "123",
            "courtId": "nysd",
            "court": "District Court, S.D. New York",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Fixture v. Example",
        }
    )
    page = parse_courtlistener_docket_html(
        html,
        source_url=docket.source_url,
        docket_id=docket.docket_id,
    )
    screened, exclusion = screen_courtlistener_docket_page(
        docket=docket,
        metadata_screen=metadata_screen,
        page=page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    return (None if screened is None else dict(screened)), exclusion


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _complete_snapshot(
    root: Path,
    screened_records: list[dict[str, object]],
    *,
    raw_html_dir: Path,
) -> tuple[Path, str]:
    batch_id = "courtlistener-fixture"
    term = "fixture-term"
    with CycleAcquisitionStore(root / "cycle-acquisition.sqlite3") as store:
        cycle_hash = store.ensure_cycle(
            {"eligibility_anchor": "2026-06-30", "fixture": True}
        )
        store.ensure_batch(batch_id, {"fixture": "courtlistener"})
        store.ensure_terms(batch_id, [term])
        hits_list: list[DiscoveryHit] = []
        for index, record in enumerate(screened_records):
            candidate = cast(dict[str, object], record["candidate"])
            candidate_id = candidate["docket_id"]
            assert isinstance(candidate_id, str)
            hits_list.append(
                DiscoveryHit(
                    provider_hit_id=f"fixture-hit-{index}",
                    candidate_id=candidate_id,
                    payload={"fixture_index": index},
                )
            )
        hits = tuple(hits_list)
        store.commit_search_page(
            batch_id,
            term,
            None,
            hits,
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        for hit, record in zip(hits, screened_records, strict=True):
            store.record_observation(
                hit.candidate_id,
                batch_id=batch_id,
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence=record,
            )
            raw_html_path = raw_html_dir / f"{hit.candidate_id}.html"
            store.write_raw_artifact(
                hit.candidate_id,
                raw_html_path,
                raw_html_path.read_bytes(),
                retrieved_at="2026-07-12T12:00:00Z",
            )
        snapshot_path = store.export_snapshot(
            root / "snapshots",
            snapshot_id="complete-fixture",
            batch_id=batch_id,
            complete=True,
        )
    return snapshot_path, cycle_hash


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
