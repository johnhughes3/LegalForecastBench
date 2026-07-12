from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)


def test_bridge_pacer_gaps_help_documents_identity_and_free_first_flags(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "bridge-pacer-gaps", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "--screened-cases" in output
    assert "--live-case-dev" in output
    assert "never invokes a PACER purchase endpoint" in normalized
    assert "--case-relevance-output" in output
    assert "--public-selection" in output
    assert "--paid-gaps" in output
    assert "--free-download-manifest" in output
    assert "Run download-free" in output


def test_fixture_pacer_gap_flow_reaches_merged_parser_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "acquisition"
    common_document_root = output_root / "documents"
    screened_path = tmp_path / "screened.jsonl"
    case_dev_fixture_path = tmp_path / "case-dev-bridge.jsonl"
    _write_jsonl(screened_path, [_fully_free_case(), _screened_case()])
    snapshot_path, cycle_hash, raw_html_dir = _complete_snapshot(
        tmp_path / "cycle",
        [_fully_free_case(), _screened_case()],
    )
    _write_jsonl(
        case_dev_fixture_path,
        [
            _response(
                params={
                    "type": "search",
                    "query": "1:26-cv-00001",
                    "limit": 20,
                },
                payload={"dockets": [_case_dev_docket()]},
            ),
            _response(
                params={
                    "type": "lookup",
                    "docketId": "case-dev-777",
                    "includeEntries": True,
                    "limit": 500,
                },
                payload={
                    "docket": {
                        **_case_dev_docket(),
                        "entries": [
                            _case_dev_entry(5, "Motion to Dismiss", "case-dev-mtd")
                        ],
                    }
                },
            ),
        ],
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
                str(raw_html_dir),
                "--use-embedded-entries",
                "--target-clean-cases",
                "2",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [free_selection] = _read_jsonl(output_root / "public-packet-selection.jsonl")
    assert free_selection["candidate_id"] == "cl-free"
    [paid_gap] = _read_jsonl(output_root / "public-packet-paid-gaps.jsonl")
    assert paid_gap["candidate_id"] == "cl-123"
    assert paid_gap["paid_gap_reasons"] == [
        "no_free_target_mtd_document",
        "no_free_mtd_memorandum",
    ]
    assert _read_jsonl(output_root / "public-packet-exclusions.jsonl") == []

    free_fixture_path = tmp_path / "free-documents.json"
    _write_json(
        free_fixture_path,
        {
            "https://storage.courtlistener.com/complaint.pdf": "%PDF complaint",
            "https://storage.courtlistener.com/decision.pdf": "%PDF decision",
            "https://storage.courtlistener.com/free-complaint.pdf": (
                "%PDF free complaint"
            ),
            "https://storage.courtlistener.com/free-motion.pdf": "%PDF free motion",
            "https://storage.courtlistener.com/free-decision.pdf": "%PDF free decision",
        },
    )
    assert (
        main(
            [
                "acquisition",
                "download-free",
                "--requests",
                str(output_root / "free-document-requests.jsonl"),
                "--fixture-documents",
                str(free_fixture_path),
                "--document-output-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    merged_manifest = output_root / "document-downloads-merged.jsonl"
    clearance = output_root / "disclosure-clearance.jsonl"
    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--case-dev-fixture",
                str(case_dev_fixture_path),
                "--public-selection",
                str(output_root / "public-packet-selection.jsonl"),
                "--paid-gaps",
                str(output_root / "public-packet-paid-gaps.jsonl"),
                "--free-download-manifest",
                str(output_root / "free-document-downloads.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    reconciled_selection = output_root / "public-packet-selection-reconciled.jsonl"
    selections = _read_jsonl(reconciled_selection)
    assert {record["candidate_id"] for record in selections} == {"cl-free", "cl-123"}
    assert _read_jsonl(output_root / "pacer-gap-bridge-exclusions.jsonl") == []
    assert not (
        {record["candidate_id"] for record in selections}
        & {
            record["candidate_id"]
            for record in _read_jsonl(output_root / "public-packet-exclusions.jsonl")
        }
    )
    assert (
        main(
            [
                "acquisition",
                "filter-core-documents",
                "--case-relevance",
                str(output_root / "case-relevance.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(output_root / "core-filter-results.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    budget = _read_json(output_root / "missing-core-budget-plan.json")
    assert budget["max_projected_budget_usd"] == "2250.00"
    assert budget["max_missing_core_documents_per_case"] == 24
    assert budget["case_plans"][0]["purchase_document_ids"] == ["case-dev-mtd"]

    purchase_fixture_path = tmp_path / "purchase.jsonl"
    download_url = "https://case.dev/download/case-dev-mtd.pdf"
    _write_jsonl(
        purchase_fixture_path,
        [
            {
                "method": "POST",
                "path": "/legal/v1/documents/case-dev-mtd/pacer",
                "params": {"live": True, "acknowledgePacerFees": True},
                "status_code": 200,
                "payload": {
                    "acknowledgePacerFees": True,
                    "downloadUrl": download_url,
                    "pacerFees": {"pacerFee": 0, "serviceFee": 3.05, "total": 3.05},
                },
            }
        ],
    )
    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(output_root / "missing-core-budget-plan.json"),
                "--case-dev-fixture",
                str(purchase_fixture_path),
                "--live-purchase",
                "--acknowledge-pacer-fees",
                "--capability",
                "document_level_purchase",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    purchased_fixture_path = tmp_path / "purchased.json"
    _write_json(purchased_fixture_path, {download_url: "%PDF purchased motion"})
    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(output_root / "case-dev-pacer-purchases.json"),
                "--selection",
                str(reconciled_selection),
                "--fixture-documents",
                str(purchased_fixture_path),
                "--document-output-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "merge-download-manifests",
                "--download-manifest",
                str(output_root / "free-document-downloads.jsonl"),
                "--download-manifest",
                str(output_root / "purchased-document-downloads.jsonl"),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    _write_jsonl(
        clearance,
        [
            {
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "sha256": row["sha256"],
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "byte_count": row["byte_count"],
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["fixture-public-docket"],
                "reviewer_id": "reviewer:test",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": "2026-07-12T18:00:00Z",
            }
            for row in _read_jsonl(merged_manifest)
        ],
    )
    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(merged_manifest),
                "--disclosure-clearance",
                str(clearance),
                "--document-root",
                str(common_document_root),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    parser_requests = _read_jsonl(output_root / "parse-document-requests.jsonl")
    assert {record["source_document_id"] for record in parser_requests} == {
        "case-dev-mtd",
        "entry-1-complaint",
        "entry-5-motion-to-dismiss-memorandum",
        "entry-16-decision",
    }


def _response(
    *,
    params: dict[str, object],
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": params,
        "status_code": 200,
        "payload": payload,
    }


def _case_dev_docket() -> dict[str, object]:
    return {
        "id": "case-dev-777",
        "courtId": "nysd",
        "docketNumber": "1:26-cv-00001",
        "caseName": "Fixture v. Example",
    }


def _case_dev_entry(
    entry_number: int,
    description: str,
    document_id: str,
) -> dict[str, object]:
    return {
        "id": f"case-dev-entry-{entry_number}",
        "entryNumber": entry_number,
        "description": description,
        "documents": [
            {
                "id": document_id,
                "description": description,
                "type": "main_document",
            }
        ],
    }


def _screened_case() -> dict[str, object]:
    return {
        "candidate": {
            "docket_id": "cl-123",
            "candidate_key": "cl-123",
            "metadata": {
                "case_id": "cl-123",
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
            "url": "https://www.courtlistener.com/docket/123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _courtlistener_entry(
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                "https://storage.courtlistener.com/complaint.pdf",
                pacer_only=False,
            ),
            _courtlistener_entry(
                5,
                "MOTION to Dismiss and Memorandum in Support filed by Defendant.",
                "Motion to Dismiss and Memorandum in Support",
                "https://ecf.nysd.uscourts.gov/doc1/12345",
                pacer_only=True,
            ),
            _courtlistener_entry(
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                "https://storage.courtlistener.com/decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _fully_free_case() -> dict[str, object]:
    record = json.loads(json.dumps(_screened_case()))
    candidate = record["candidate"]
    candidate["docket_id"] = "cl-free"
    candidate["candidate_key"] = "cl-free"
    candidate["metadata"] = {
        "case_id": "cl-free",
        "case_name": "Free v. Example",
        "court": "nysd",
        "docket_number": "1:26-cv-00002",
    }
    entries = record["selected_entries"]
    urls = (
        "https://storage.courtlistener.com/free-complaint.pdf",
        "https://storage.courtlistener.com/free-motion.pdf",
        "https://storage.courtlistener.com/free-decision.pdf",
    )
    for entry, url in zip(entries, urls, strict=True):
        document = entry["documents"][0]
        document["href"] = url
        document["pacer_only"] = False
        document["action_label"] = "Download PDF"
    return record


def _courtlistener_entry(
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "kind": "Main Document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _complete_snapshot(
    root: Path,
    screened_records: list[dict[str, object]],
) -> tuple[Path, str, Path]:
    batch_id = "pacer-gap-fixture"
    term = "fixture-term"
    raw_html_dir = root / "raw-courtlistener-html"
    with CycleAcquisitionStore(root / "cycle-acquisition.sqlite3") as store:
        cycle_hash = store.ensure_cycle(
            {"eligibility_anchor": "2026-06-30", "fixture": True}
        )
        store.ensure_batch(batch_id, {"fixture": "pacer-gap"})
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
            store.write_raw_artifact(
                hit.candidate_id,
                raw_html_dir / f"{hit.candidate_id}.html",
                _raw_docket_html(record),
                retrieved_at="2026-07-12T12:00:00Z",
            )
        snapshot_path = store.export_snapshot(
            root / "snapshots",
            snapshot_id="complete-fixture",
            batch_id=batch_id,
            complete=True,
        )
    return snapshot_path, cycle_hash, raw_html_dir


def _raw_docket_html(record: dict[str, object]) -> bytes:
    selected_entries = cast(list[object], record["selected_entries"])
    rows: list[str] = []
    for entry_value in selected_entries:
        entry = cast(dict[str, object], entry_value)
        documents = cast(list[dict[str, object]], entry["documents"])
        [document] = documents
        action_label = str(document["action_label"])
        rows.append(
            '<div class="row" id="entry-{number}">'
            '<div class="col-xs-1">{number}</div>'
            '<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span>'
            "</div>"
            '<div class="col-xs-8">{text}'
            '<div class="recap-documents"><div>{kind}</div>'
            "<div>{description}</div>"
            '<a href="{href}">{action_label}</a>'
            "</div></div></div>".format(
                number=entry["entry_number"],
                filed_at=entry["filed_at"],
                text=entry["text"],
                kind=document["kind"],
                description=document["description"],
                href=document["href"],
                action_label=action_label,
            )
        )
    return (
        "<html><head><title>Fixture docket</title></head><body>"
        '<div id="docket-entry-table">' + "".join(rows) + "</div></body></html>"
    ).encode()


def _write_json(path: Path, record: dict[str, object]) -> None:
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
