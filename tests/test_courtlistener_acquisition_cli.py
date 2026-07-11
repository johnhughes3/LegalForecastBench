from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main


def test_discover_courtlistener_help_documents_live_authority(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "discover-courtlistener", "--help"])
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "--decision-filed-on-or-after" in output
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
                        "entry_date_filed:[2026-06-30 TO *]"
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
                "--decision-filed-on-or-after",
                "2026-06-30",
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

    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--screened-cases",
                str(output_root / "courtlistener-screened-cases.jsonl"),
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
                        "entry_date_filed:[2026-06-30 TO *]"
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
                "--decision-filed-on-or-after",
                "2026-06-30",
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


def test_discover_courtlistener_execute_requires_live_or_complete_fixture_pair(
    tmp_path: Path,
    capsys: Any,
) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(tmp_path / "output"),
                "--execute",
            ]
        )
        == 2
    )
    assert "requires --live or both" in capsys.readouterr().err


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
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--output-root",
                str(tmp_path / "output"),
                "--live",
                "--execute",
            ]
        )
        == 2
    )
    assert "COURTLISTENER_API_TOKEN is required" in capsys.readouterr().err


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
) -> str:
    return (
        f'<div class="row" id="entry-{number}">'
        f'<div class="col-xs-1">{number}</div>'
        f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
        f'<div class="col-xs-8">{text}'
        '<div class="recap-documents">'
        "<div>Main Document</div>"
        f"<div>{description}</div>"
        f'<a href="https://storage.courtlistener.com/{number}.pdf">Download PDF</a>'
        "</div></div></div>"
    )


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
