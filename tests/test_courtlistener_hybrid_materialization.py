from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
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
    FirecrawlServerError,
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


def test_hybrid_discovery_materializes_zero_credit_success_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery(
        tmp_path,
        monkeypatch,
        reported_credits=0,
    )

    [raw_artifact] = _read_jsonl(discovery_root / "courtlistener-raw-artifacts.jsonl")
    assert raw_artifact["source_receipt"]["reported_credits"] == 0

    snapshot = _materialize_hybrid(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    manifest = verify_snapshot(snapshot, require_complete=True, require_saturated=True)
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert lineage["firecrawl_run_reserved_credits"] == 1
    assert lineage["firecrawl_run_reported_credits"] == 0


def test_hybrid_transient_firecrawl_retry_materializes_exact_attempt_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery(
        tmp_path,
        monkeypatch,
        transient_failures=1,
    )

    with CycleAcquisitionStore(cycle_store) as store:
        attempts = store.firecrawl_attempts("hybrid-batch-courtlistener-docket-html-v1")
    assert [attempt.status for attempt in attempts] == [
        "provider_error",
        "succeeded",
    ]
    assert attempts[0].failure_code == "provider_server_error"
    assert attempts[0].failure_transient is True
    assert [attempt.attempt_number for attempt in attempts] == [1, 2]

    snapshot = _materialize_hybrid(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    manifest = verify_snapshot(snapshot, require_complete=True, require_saturated=True)
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert lineage["firecrawl_run_reserved_credits"] == 2
    assert lineage["firecrawl_run_reported_credits"] == 1


def test_hybrid_exhausted_provider_retries_materialize_as_terminal_exclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery(
        tmp_path,
        monkeypatch,
        transient_failures=3,
    )

    [exclusion] = _read_jsonl(
        discovery_root / "courtlistener-discovery-exclusions.jsonl"
    )
    assert exclusion["candidate_id"] == _DOCKET_ID
    assert exclusion["stage"] == "retrieval"
    assert exclusion["reason"] == "courtlistener_docket_html_provider_exhausted"
    with CycleAcquisitionStore(cycle_store) as store:
        attempts = store.firecrawl_attempts("hybrid-batch-courtlistener-docket-html-v1")
        [target] = store.firecrawl_targets("hybrid-batch-courtlistener-docket-html-v1")
    assert [attempt.attempt_number for attempt in attempts] == [1, 2, 3]
    assert {attempt.status for attempt in attempts} == {"provider_error"}
    assert {attempt.failure_code for attempt in attempts} == {"provider_server_error"}
    assert target.status == "terminal_error"

    snapshot = _materialize_hybrid(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    manifest = verify_snapshot(snapshot, require_complete=True, require_saturated=True)
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert lineage["accepted_case_count"] == 0
    assert lineage["excluded_case_count"] == 1
    assert lineage["firecrawl_source_receipt_count"] == 0
    assert lineage["firecrawl_run_reserved_credits"] == 3
    assert lineage["firecrawl_run_reported_credits"] == 0


@pytest.mark.parametrize("failure_kind", ["target_404", "target_410", "abandoned"])
def test_hybrid_terminal_retrieval_exclusion_materializes_with_durable_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery_with_terminal_exclusion(
        tmp_path,
        monkeypatch,
        failure_kind=failure_kind,
    )

    [exclusion] = _read_jsonl(
        discovery_root / "courtlistener-discovery-exclusions.jsonl"
    )
    assert exclusion["candidate_id"] == "122"
    assert exclusion["stage"] == "retrieval"
    assert exclusion["reason"] == "courtlistener_docket_html_unavailable"
    with CycleAcquisitionStore(cycle_store) as store:
        attempts = store.firecrawl_attempts("hybrid-batch-courtlistener-docket-html-v1")
    assert len(attempts) == 2
    failed, succeeded = attempts
    if failure_kind.startswith("target_"):
        assert failed.status == "target_error"
        assert failed.failure_code == "target_http_status_invalid"
        assert failed.target_http_status == int(failure_kind.removeprefix("target_"))
    else:
        assert failed.status == "interrupted"
        assert failed.failure_code == "authorization_abandoned"
        assert failed.failure_transient is False
    assert succeeded.status == "succeeded"

    snapshot = _materialize_hybrid(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    manifest = verify_snapshot(snapshot, require_complete=True, require_saturated=True)
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert lineage["accepted_case_count"] == 1
    assert lineage["excluded_case_count"] == 1
    assert lineage["firecrawl_source_receipt_count"] == 1
    assert lineage["firecrawl_run_reserved_credits"] == 2
    assert lineage["firecrawl_run_reported_credits"] == (
        2 if failure_kind.startswith("target_") else 1
    )


@pytest.mark.parametrize("failure_kind", ["target_404", "target_410"])
def test_hybrid_terminal_retrieval_exclusion_materializes_zero_credit_outcomes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery_with_terminal_exclusion(
        tmp_path,
        monkeypatch,
        failure_kind=failure_kind,
        reported_credits=0,
    )

    snapshot = _materialize_hybrid(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    manifest = verify_snapshot(snapshot, require_complete=True, require_saturated=True)
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert lineage["firecrawl_run_reserved_credits"] == 2
    assert lineage["firecrawl_run_reported_credits"] == 0


def test_hybrid_rest_docket_unavailable_materializes_from_durable_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery_with_terminal_exclusion(
        tmp_path,
        monkeypatch,
        failure_kind="rest_404",
    )

    [exclusion] = _read_jsonl(
        discovery_root / "courtlistener-discovery-exclusions.jsonl"
    )
    assert exclusion["candidate_id"] == "122"
    assert exclusion["stage"] == "retrieval"
    assert exclusion["reason"] == "courtlistener_docket_unavailable"
    snapshot = _materialize_hybrid(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    manifest = verify_snapshot(snapshot, require_complete=True, require_saturated=True)
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert lineage["accepted_case_count"] == 1
    assert lineage["excluded_case_count"] == 1
    assert lineage["firecrawl_source_receipt_count"] == 1
    assert lineage["firecrawl_run_reserved_credits"] == 1


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("reason", "courtlistener_docket_unavailable"),
        ("stage", "screening"),
    ],
)
def test_hybrid_materialization_rejects_unmatched_terminal_retrieval_exclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: str,
    capsys: Any,
) -> None:
    discovery_root, cycle_store = _run_hybrid_discovery_with_terminal_exclusion(
        tmp_path,
        monkeypatch,
        failure_kind="target_404",
    )
    exclusions_path = discovery_root / "courtlistener-discovery-exclusions.jsonl"
    [exclusion] = _read_jsonl(exclusions_path)
    exclusion[field] = replacement
    _write_jsonl(exclusions_path, [exclusion])
    _recommit_output(discovery_root, "exclusions", exclusions_path)

    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
                snapshot_id=f"unmatched-terminal-{field}",
            )
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "Firecrawl" in error or "durable candidate evidence" in error


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
        ("reported_credits", 2),
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
    *,
    reported_credits: int = 1,
    transient_failures: int = 0,
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
    success_response = FirecrawlHTTPResponse(
        status_code=200,
        payload={
            "success": True,
            "data": {
                "rawHtml": _docket_html(),
                "metadata": {
                    "statusCode": 200,
                    "proxyUsed": "basic",
                    "cacheState": "miss",
                    "creditsUsed": reported_credits,
                    "sourceURL": _DOCKET_URL,
                },
            },
        },
    )
    firecrawl_source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="fixture-key", proxy="basic"),
        transport=(
            _TransientThenSuccessTransport(
                success_response,
                transient_failures=transient_failures,
            )
            if transient_failures
            else FirecrawlFixtureTransport([success_response])
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


def _run_hybrid_discovery_with_terminal_exclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    failure_kind: str,
    reported_credits: int = 1,
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
                            "docket_id": 122,
                            "docket_entry_id": 15,
                            "description": "Order on motion to dismiss",
                            "entry_date_filed": "2026-06-30",
                        },
                        {
                            "docket_id": int(_DOCKET_ID),
                            "docket_entry_id": 16,
                            "description": "Order on motion to dismiss",
                            "entry_date_filed": "2026-06-30",
                        },
                    ],
                    "next": None,
                },
            ),
            _fixture_response(
                path="/dockets/122/",
                payload=(
                    {"detail": "Not found."}
                    if failure_kind == "rest_404"
                    else {
                        "id": 122,
                        "court": "nysd",
                        "docket_number": "1:26-cv-00000",
                        "case_name": "Unavailable v. Example",
                        "absolute_url": (
                            "https://www.courtlistener.com/docket/122/"
                            "unavailable-v-example/"
                        ),
                    }
                ),
                status_code=404 if failure_kind == "rest_404" else 200,
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
    success_response = _firecrawl_success_response(reported_credits)
    transport = (
        FirecrawlFixtureTransport([success_response])
        if failure_kind == "rest_404"
        else FirecrawlFixtureTransport(
            [
                _firecrawl_unavailable_response(
                    int(failure_kind.removeprefix("target_")),
                    reported_credits,
                ),
                success_response,
            ]
        )
        if failure_kind.startswith("target_")
        else _AbandonThenSuccessTransport(success_response)
    )
    firecrawl_source = FirecrawlCourtListenerHTMLSource(
        FirecrawlConfig(api_key="fixture-key", proxy="basic"),
        transport=transport,
    )
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fixture-key")

    def fixture_client_factory(**_kwargs: object) -> CourtListenerClient:
        return fixture_client

    def fixture_firecrawl_source(
        _config: FirecrawlConfig,
    ) -> FirecrawlCourtListenerHTMLSource:
        return firecrawl_source

    monkeypatch.setattr("legalforecast.cli.CourtListenerClient", fixture_client_factory)
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
                "3",
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


class _AbandonThenSuccessTransport:
    def __init__(self, success_response: FirecrawlHTTPResponse) -> None:
        self._success_response = success_response
        self._calls = 0

    def scrape(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> FirecrawlHTTPResponse:
        del endpoint, headers, payload, timeout_seconds
        self._calls += 1
        if self._calls == 1:
            raise RuntimeError("injected provider transport interruption")
        return self._success_response


class _TransientThenSuccessTransport:
    def __init__(
        self,
        success_response: FirecrawlHTTPResponse,
        *,
        transient_failures: int,
    ) -> None:
        self._success_response = success_response
        self._remaining_failures = transient_failures

    def scrape(
        self,
        *,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> FirecrawlHTTPResponse:
        del endpoint, headers, payload, timeout_seconds
        if self._remaining_failures:
            self._remaining_failures -= 1
            raise FirecrawlServerError(
                "injected transient provider failure",
                provider_http_status=503,
            )
        return self._success_response


def _firecrawl_unavailable_response(
    target_status: int,
    reported_credits: int = 1,
) -> FirecrawlHTTPResponse:
    return FirecrawlHTTPResponse(
        status_code=200,
        payload={
            "success": True,
            "data": {
                "rawHtml": "<html><body>Not found</body></html>",
                "metadata": {
                    "statusCode": target_status,
                    "proxyUsed": "basic",
                    "cacheState": "miss",
                    "creditsUsed": reported_credits,
                    "sourceURL": "https://www.courtlistener.com/docket/122/",
                },
            },
        },
    )


def _firecrawl_success_response(
    reported_credits: int = 1,
) -> FirecrawlHTTPResponse:
    return FirecrawlHTTPResponse(
        status_code=200,
        payload={
            "success": True,
            "data": {
                "rawHtml": _docket_html(),
                "metadata": {
                    "statusCode": 200,
                    "proxyUsed": "basic",
                    "cacheState": "miss",
                    "creditsUsed": reported_credits,
                    "sourceURL": _DOCKET_URL,
                },
            },
        },
    )


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
    status_code: int = 200,
) -> dict[str, object]:
    return {
        "method": "GET",
        "path": path,
        "params": {} if params is None else params,
        "status_code": status_code,
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
