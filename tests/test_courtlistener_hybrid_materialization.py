from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    verify_snapshot,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlConfig,
    FirecrawlCourtListenerHTMLSource,
    FirecrawlFixtureTransport,
    FirecrawlHTTPResponse,
)

_DOCKET_ID = "123"
_CANONICAL_DOCKET_URL = "https://www.courtlistener.com/docket/123/"
_DOCKET_URL = f"{_CANONICAL_DOCKET_URL}fixture-v-example/"
_QUERY = "order on motion to dismiss"


def test_hybrid_discovery_materializes_with_exact_firecrawl_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery(tmp_path, monkeypatch)
    snapshot = _materialize_hybrid(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )

    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash
    manifest = verify_snapshot(
        snapshot,
        expected_cycle_hash=cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    assert manifest["complete"] is True
    assert manifest["saturated"] is True
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert lineage["docket_html_source"] == "firecrawl"
    assert lineage["firecrawl_run_id"] == ("hybrid-batch-courtlistener-docket-html-v1")
    assert lineage["firecrawl_source_receipt_count"] == 1
    assert lineage["firecrawl_run_reserved_credits"] == 1
    assert lineage["firecrawl_run_reported_credits"] == 1


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("schema_version", "legalforecast.firecrawl_docket_html_source_receipt.v0"),
        ("batch_digest", "0" * 64),
        ("firecrawl_run_id", "other-run"),
        ("firecrawl_target_id", "courtlistener-docket:999"),
        ("firecrawl_attempt_id", 999),
        ("request_url", "https://www.courtlistener.com/docket/999/"),
        ("reserved_credits", 2),
        ("reported_credits", 0),
        ("proxy_used", "stealth"),
        ("target_http_status", 404),
        ("artifact_sha256", "0" * 64),
        ("artifact_byte_count", 1),
        ("authorized_at", ""),
        ("completed_at", ""),
        ("authorized_at", "2026-07-15-not-a-dateZ"),
        ("completed_at", "2026-07-15T00:00:00+00:00"),
    ],
)
def test_hybrid_materialization_rejects_tampered_source_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: object,
    capsys: Any,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery(tmp_path, monkeypatch)
    raw_manifest_path = discovery_root / "courtlistener-raw-artifacts.jsonl"
    [record] = _read_jsonl(raw_manifest_path)
    receipt = record["source_receipt"]
    assert isinstance(receipt, dict)
    receipt[field] = replacement
    _write_jsonl(raw_manifest_path, [record])
    _recommit_output(discovery_root, "raw_artifacts", raw_manifest_path)

    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
                snapshot_id=f"tampered-{field.replace('_', '-')}",
            )
        )
        == 2
    )
    assert "Firecrawl source receipt" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("firecrawl_source_receipt_count", 0),
        ("run_reserved_credits", 2),
        ("run_reported_credits", 0),
        ("pacer_paid_activity_executed", True),
    ],
)
def test_hybrid_materialization_rejects_unreconciled_metered_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: object,
    capsys: Any,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery(tmp_path, monkeypatch)
    run_card_path = discovery_root / "run-cards" / "discover-courtlistener.json"
    run_card = _read_json(run_card_path)
    run_card[field] = replacement
    run_card_path.write_text(json.dumps(run_card, sort_keys=True), encoding="utf-8")

    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
                snapshot_id=f"unreconciled-{field.replace('_', '-')}",
            )
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "Firecrawl" in error or "PACER" in error


def _run_hybrid_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    output_root = tmp_path / "discovery"
    cycle_store = tmp_path / "cycle.sqlite3"
    fixture_path = tmp_path / "courtlistener.jsonl"
    _write_jsonl(
        fixture_path,
        [
            _fixture_response(
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
                            "docket_id": int(_DOCKET_ID),
                            "docket_entry_id": 16,
                            "description": "Order on motion to dismiss",
                            "entry_date_filed": "2026-06-30",
                        }
                    ],
                    "next": None,
                },
            ),
            _fixture_response(
                path=f"/dockets/{_DOCKET_ID}/",
                payload={
                    "id": int(_DOCKET_ID),
                    "court": "nysd",
                    "docket_number": "1:26-cv-00001",
                    "case_name": "Fixture v. Example",
                    "absolute_url": _DOCKET_URL,
                },
            ),
        ],
    )
    fixture_client = CourtListenerClient(
        config=CourtListenerConfig(api_token="fixture-token"),
        transport=CourtListenerFixtureTransport.from_jsonl(fixture_path),
    )
    firecrawl_source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="fixture-key", proxy="basic"),
        transport=FirecrawlFixtureTransport(
            [
                FirecrawlHTTPResponse(
                    status_code=200,
                    payload={
                        "success": True,
                        "data": {
                            "rawHtml": _docket_html(),
                            "metadata": {
                                "statusCode": 200,
                                "proxyUsed": "basic",
                                "cacheState": "miss",
                                "creditsUsed": 1,
                                "sourceURL": _DOCKET_URL,
                            },
                        },
                    },
                )
            ]
        ),
    )
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fixture-key")

    def fixture_client_factory(**_kwargs: object) -> CourtListenerClient:
        return fixture_client

    def fixture_firecrawl_source(
        _config: FirecrawlConfig,
    ) -> FirecrawlCourtListenerHTMLSource:
        return firecrawl_source

    monkeypatch.setattr(
        "legalforecast.cli.CourtListenerClient",
        fixture_client_factory,
    )
    monkeypatch.setattr(
        "legalforecast.cli.FirecrawlCourtListenerHTMLSource",
        fixture_firecrawl_source,
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
                str(cycle_store),
                "--batch-id",
                "hybrid-batch",
                "--query-term",
                _QUERY,
                "--target-clean-cases",
                "2",
                "--max-candidates",
                "5",
                "--output-root",
                str(output_root),
                "--live",
                "--live-firecrawl-docket-html",
                "--execute",
            ]
        )
        == 0
    )
    return output_root, cycle_store


def _materialize_hybrid(
    *,
    tmp_path: Path,
    discovery_root: Path,
    cycle_store: Path,
) -> Path:
    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
                snapshot_id="hybrid-complete",
            )
        )
        == 0
    )
    return tmp_path / "snapshots" / "hybrid-complete"


def _materialize_command(
    *,
    tmp_path: Path,
    discovery_root: Path,
    cycle_store: Path,
    snapshot_id: str,
) -> list[str]:
    run_card = discovery_root / "run-cards" / "discover-courtlistener.json"
    return [
        "acquisition",
        "materialize-courtlistener-snapshot",
        "--cycle-store",
        str(cycle_store),
        "--batch-id",
        "hybrid-batch",
        "--discovery-run-card",
        str(run_card),
        "--expected-discovery-run-card-sha256",
        hashlib.sha256(run_card.read_bytes()).hexdigest(),
        "--snapshot-root",
        str(tmp_path / "snapshots"),
        "--snapshot-id",
        snapshot_id,
        "--output-root",
        str(tmp_path / "materialization" / snapshot_id),
        "--execute",
    ]


def _recommit_output(discovery_root: Path, key: str, path: Path) -> None:
    run_card_path = discovery_root / "run-cards" / "discover-courtlistener.json"
    run_card = _read_json(run_card_path)
    payload = path.read_bytes()
    run_card["output_commitments"][key] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": payload.count(b"\n"),
    }
    run_card_path.write_text(json.dumps(run_card, sort_keys=True), encoding="utf-8")


def _fixture_response(
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


def _docket_html() -> str:
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
        + _entry_html(
            number=16,
            filed_at="June 30, 2026",
            text="ORDER granting in part and denying in part Motion to Dismiss",
            description="Order on Motion to Dismiss",
        )
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


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
