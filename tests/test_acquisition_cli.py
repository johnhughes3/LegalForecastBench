# pyright: reportPrivateUsage=false
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn, cast

import legalforecast.cli as cli
import legalforecast.ingestion.courtlistener_recap_fetch as recap_fetch
import legalforecast.ingestion.recap_fetch_broker as recap_broker
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from legalforecast.cli import main
from legalforecast.ingestion import (
    exact100_successor_replacement_v2_cli as successor_v2_cli,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    generate_case_dev_purchase_policy,
)
from legalforecast.ingestion.exact100_successor_replacement_v2 import (
    _mint_verified_exact100_v2_base,
)
from legalforecast.ingestion.free_document_downloader import FreeDocumentFetch
from legalforecast.ingestion.mistral_markdown_parser import ParserProcessResult
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    TerminalExclusionReason,
    _mint_terminal_evidence,
    verify_post_selection_terminal_exclusions,
)
from legalforecast.unitization.review import apply_unitization_reviews
from pytest import CaptureFixture, MonkeyPatch
from tests.purchase_approval_fixtures import (
    ApprovedPurchaseFixture,
    allow_historical_v1_algorithm_fixtures,
    build_approved_purchase_fixture,
    build_completed_projection_fixture,
)
from tests.test_exact100_successor_replacement_v2 import _fixture as _v2_fixture


@pytest.fixture
def _historical_v1_algorithm_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)


JsonRecord = dict[str, Any]
_GENERATED_AT = "2026-05-17T12:00:00Z"


def _materialized_cli_unit_fixture(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    *,
    skip_packet_planner_replay: bool = False,
    free_public_download_capability: object | None = None,
) -> tuple[Path, Path]:
    """Isolate downstream semantics; real lineage is covered by target-100 E2E."""

    document_root = tmp_path / "materialized-documents"
    document_root.mkdir(exist_ok=True)
    run_card = tmp_path / "materialization-run-card.json"
    placeholder_outputs = [
        tmp_path / "materialized-manifest.jsonl",
        tmp_path / "materialized-clearance.jsonl",
        tmp_path / "materialized-restrictions.jsonl",
        tmp_path / "materialized-derivations.jsonl",
        tmp_path / "materialization-summary.json",
    ]
    for path in placeholder_outputs:
        path.write_text("\n", encoding="utf-8")
    _write_json(
        run_card,
        {
            "stage": "materialize-cohort-documents",
            "output_paths": [
                *(str(path) for path in placeholder_outputs),
                str(document_root),
            ],
        },
    )
    monkeypatch.setattr(
        cli,
        "_require_consistent_materialization_markers",
        lambda *args: True,
    )
    monkeypatch.setattr(
        cli,
        "_preflight_materialization_purchase_runtime",
        lambda _args: None,
    )

    def verified_materialized_lineage(
        **kwargs: object,
    ) -> cli._VerifiedMaterializedDownstreamLineage:
        manifest_path = cast(Path, kwargs["manifest_path"])
        clearance_path = cast(Path, kwargs["clearance_path"])
        selection_path = cast(Path | None, kwargs.get("selection_path"))
        artifact_paths = [run_card, manifest_path, clearance_path]
        if selection_path is not None:
            artifact_paths.append(selection_path)
        return cli._VerifiedMaterializedDownstreamLineage(
            paths=(run_card,),
            artifact_bytes={
                str(path.resolve()): path.read_bytes() for path in artifact_paths
            },
            manifest_records=tuple(_read_jsonl(manifest_path)),
            clearance_records=tuple(_read_jsonl(clearance_path)),
            selection_records=(
                tuple(_read_jsonl(selection_path)) if selection_path is not None else ()
            ),
            resolved_records=(),
            document_tree={},
            free_public_download_capability=free_public_download_capability,
        )

    monkeypatch.setattr(
        cli,
        "_verify_materialized_downstream_lineage",
        verified_materialized_lineage,
    )
    monkeypatch.setattr(
        cli,
        "_verify_packet_raw_artifacts_snapshot_binding",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_authenticated_materialization_snapshot_manifest_path",
        lambda *args, **kwargs: run_card,
    )
    monkeypatch.setattr(
        cli,
        "_verify_parser_packet_authority",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_packet_authority",
        lambda **kwargs: None,
    )
    if skip_packet_planner_replay:
        monkeypatch.setattr(
            cli,
            "_validate_packet_input_run_card",
            lambda *args, **kwargs: cli._PacketPlannerReplay(
                packet_build_records=tuple(
                    cli._read_records(kwargs["packet_build_input_path"])
                ),
                packet_build_input_sha256=cli._path_sha256(
                    kwargs["packet_build_input_path"]
                ),
                selection_records=tuple(cli._read_records(kwargs["selection_path"])),
                download_records=tuple(
                    cli._read_records(kwargs["download_manifest_path"])
                ),
                parser_records=tuple(cli._read_records(kwargs["parser_manifest_path"])),
                clearance_records=tuple(cli._read_records(kwargs["clearance_path"])),
                clearance_sha256=cli._path_sha256(kwargs["clearance_path"]),
                parser_manifest_sha256=cli._path_sha256(kwargs["parser_manifest_path"]),
                parser_record_count=len(
                    cli._read_records(kwargs["parser_manifest_path"])
                ),
                prediction_unit_records=tuple(
                    cli._read_records(kwargs["prediction_units_path"])
                ),
                model_registry=cli.load_model_registry(kwargs["model_registry_path"]),
                model_registry_sha256=cli._path_sha256(kwargs["model_registry_path"]),
            ),
        )
    return document_root, run_card


def _write_packet_planner_card(
    path: Path,
    *,
    packet_input: Path,
    selection: Path,
    manifest: Path,
    clearance: Path,
    document_root: Path,
    materialization_run_card: Path,
) -> None:
    _write_json(
        path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "plan-packet-inputs",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "authenticated_materialization_lineage": (
                cli._packet_materialization_lineage_commitments(
                    selection_path=selection,
                    download_manifest_path=manifest,
                    clearance_path=clearance,
                    document_root=document_root,
                    materialization_run_card_path=materialization_run_card,
                )
            ),
            "output_commitments": {
                "packet_build_input": {
                    "path": str(packet_input.resolve()),
                    "sha256": "sha256:"
                    + hashlib.sha256(packet_input.read_bytes()).hexdigest(),
                }
            },
        },
    )


def test_fetch_firecrawl_dockets_runs_bounded_offline_bridge(tmp_path: Path) -> None:
    output_root = tmp_path / "acquisition"
    candidates_path = tmp_path / "candidates.jsonl"
    case_dev_fixture = tmp_path / "case-dev.jsonl"
    firecrawl_fixture = tmp_path / "firecrawl.jsonl"
    _write_jsonl(
        candidates_path,
        [{"case_id": "case-a", "candidate_id": "candidate-a"}],
    )
    _write_jsonl(
        case_dev_fixture,
        [
            {
                "method": "POST",
                "path": "/legal/v1/docket",
                "params": {"type": "lookup", "docketId": "case-a"},
                "status_code": 200,
                "payload": {
                    "id": "case-a",
                    "caseName": "Fixture v. Example",
                    "courtId": "nysd",
                    "docketNumber": "1:26-cv-00001",
                    "url": ("https://www.courtlistener.com/api/rest/v4/dockets/101/"),
                },
            }
        ],
    )
    raw_html = "<html><div id='docket-entry-table'></div></html>"
    _write_jsonl(
        firecrawl_fixture,
        [
            {
                "status_code": 200,
                "payload": {
                    "success": True,
                    "data": {
                        "rawHtml": raw_html,
                        "metadata": {
                            "statusCode": 200,
                            "sourceURL": ("https://www.courtlistener.com/docket/101/"),
                            "proxyUsed": "basic",
                            "cacheState": "miss",
                            "creditsUsed": 1,
                        },
                    },
                },
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "fetch-firecrawl-dockets",
                "--candidates",
                str(candidates_path),
                "--max-candidates",
                "1",
                "--case-dev-fixture",
                str(case_dev_fixture),
                "--firecrawl-fixture",
                str(firecrawl_fixture),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    assert (output_root / "raw-docket-html" / "101.html").read_text() == raw_html
    [success] = _read_jsonl(output_root / "firecrawl-docket-successes.jsonl")
    assert success["candidate_id"] == "candidate-a"
    assert success["docket_id"] == "101"
    assert success["case_metadata"]["case_id"] == "case-a"
    summary = _read_json(output_root / "firecrawl-docket-summary.json")
    assert summary["scrape_count"] == 1
    assert summary["firecrawl_proxy"] == "basic"
    assert summary["firecrawl_max_credits_per_scrape"] == 1

    assert (
        main(
            [
                "acquisition",
                "fetch-firecrawl-dockets",
                "--candidates",
                str(candidates_path),
                "--max-candidates",
                "1",
                "--case-dev-fixture",
                str(case_dev_fixture),
                "--firecrawl-fixture",
                str(firecrawl_fixture),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    resumed_summary = _read_json(output_root / "firecrawl-docket-summary.json")
    assert resumed_summary["success_count"] == 1
    assert resumed_summary["scrape_count"] == 0


def test_acquisition_plan_defaults_to_dry_run_with_log_and_run_card(
    tmp_path: Path,
) -> None:
    core_results = tmp_path / "core-filter-results.jsonl"
    output_root = tmp_path / "acquisition"
    _write_jsonl(core_results, [_core_filter_result()])

    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )

    plan = _read_json(output_root / "missing-core-budget-plan.json")
    assert plan["dry_run"] is True
    assert plan["total_missing_core_documents"] == 1
    assert plan["total_estimated_cost_usd"] == "3.05"

    log = _read_jsonl(output_root / "logs" / "acquisition-plan.jsonl")[0]
    assert log["event"] == "stage_completed"
    assert log["dry_run"] is True
    assert log["paid_activity_executed"] is False
    assert log["record_count"] == 1
    run_card = _read_json(output_root / "run-cards" / "acquisition-plan.json")
    assert run_card["schema_version"] == "legalforecast.acquisition_run_card.v1"
    assert run_card["stage"] == "acquisition-plan"


def test_acquisition_plan_can_emit_budget_capped_frontier(tmp_path: Path) -> None:
    core_results = tmp_path / "core-filter-results.jsonl"
    output_root = tmp_path / "acquisition"
    first = _core_filter_result()
    second = {**first, "candidate_id": "candidate-b"}
    second["core_missing_documents"] = ["document-b1", "document-b2"]
    second["purchase_document_ids"] = ["document-b1", "document-b2"]
    _write_jsonl(core_results, [second, first])

    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
                "--max-projected-budget-usd",
                "3.05",
                "--truncate-to-budget",
            ]
        )
        == 0
    )

    plan = _read_json(output_root / "missing-core-budget-plan.json")
    assert [row["candidate_id"] for row in plan["case_plans"]] == ["cand-1"]
    assert plan["frontier_truncated"] is True
    assert plan["omitted_candidate_ids"] == ["candidate-b"]
    reloaded = cli._missing_core_budget_plan(plan).to_record()
    assert reloaded["frontier_rows"] == plan["frontier_rows"]
    assert reloaded["omitted_candidate_ids"] == plan["omitted_candidate_ids"]
    assert reloaded["frontier_truncated"] is True


def test_acquisition_plan_can_cap_the_cheapest_complete_case_count(
    tmp_path: Path,
) -> None:
    core_results = tmp_path / "core-filter-results.jsonl"
    output_root = tmp_path / "acquisition"
    cheapest = {**_core_filter_result(), "candidate_id": "candidate-free"}
    cheapest["core_missing_documents"] = []
    cheapest["purchase_document_ids"] = []
    one_gap = {**_core_filter_result(), "candidate_id": "candidate-one-gap"}
    two_gaps = {**_core_filter_result(), "candidate_id": "candidate-two-gaps"}
    two_gaps["core_missing_documents"] = ["document-b1", "document-b2"]
    two_gaps["purchase_document_ids"] = ["document-b1", "document-b2"]
    _write_jsonl(core_results, [two_gaps, one_gap, cheapest])

    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
                "--execute",
                "--target-case-count",
                "2",
            ]
        )
        == 0
    )

    plan = _read_json(output_root / "missing-core-budget-plan.json")
    assert [row["candidate_id"] for row in plan["case_plans"]] == [
        "candidate-free",
        "candidate-one-gap",
    ]
    assert plan["target_case_count"] == 2
    assert plan["target_case_count_met"] is True
    assert plan["omitted_candidate_ids"] == ["candidate-two-gaps"]
    assert plan["total_estimated_cost_usd"] == "3.05"


def test_acquisition_plan_records_target_case_shortfall(tmp_path: Path) -> None:
    core_results = tmp_path / "core-filter-results.jsonl"
    output_root = tmp_path / "acquisition"
    _write_jsonl(core_results, [_core_filter_result()])

    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
                "--execute",
                "--target-case-count",
                "100",
            ]
        )
        == 0
    )

    plan = _read_json(output_root / "missing-core-budget-plan.json")
    assert plan["target_case_count"] == 100
    assert plan["target_case_count_met"] is False
    assert len(plan["case_plans"]) == 1


def test_acquisition_plan_ranks_full_pool_deterministically_before_cheapest_100(
    tmp_path: Path,
) -> None:
    records: list[JsonRecord] = []
    for index in range(200):
        missing_count = index % 4
        record = {**_core_filter_result(), "candidate_id": f"candidate-{index:03d}"}
        document_ids = [f"document-{index}-{gap}" for gap in range(missing_count)]
        record["core_missing_documents"] = document_ids
        record["purchase_document_ids"] = document_ids
        records.append(record)

    selected: list[list[str]] = []
    for name, ordering in (("forward", records), ("reverse", reversed(records))):
        input_path = tmp_path / f"{name}.jsonl"
        output_root = tmp_path / name
        _write_jsonl(input_path, ordering)
        assert (
            main(
                [
                    "acquisition",
                    "plan",
                    "--core-filter-results",
                    str(input_path),
                    "--output-root",
                    str(output_root),
                    "--execute",
                    "--target-case-count",
                    "100",
                ]
            )
            == 0
        )
        plan = _read_json(output_root / "missing-core-budget-plan.json")
        selected.append([row["candidate_id"] for row in plan["case_plans"]])

    assert selected[0] == selected[1]
    assert len(selected[0]) == 100
    assert selected[0][:3] == ["candidate-000", "candidate-004", "candidate-008"]
    assert selected[0][-1] == "candidate-197"


def test_acquisition_plan_excludes_cap_outlier_and_fills_from_reserve(
    tmp_path: Path,
) -> None:
    records: list[JsonRecord] = []
    for index in range(100):
        record = {**_core_filter_result(), "candidate_id": f"candidate-{index:03d}"}
        document_ids = [f"document-{index}"]
        record["core_missing_documents"] = document_ids
        record["purchase_document_ids"] = document_ids
        records.append(record)
    outlier = {**_core_filter_result(), "candidate_id": "candidate-cap-outlier"}
    outlier_ids = [f"outlier-document-{index}" for index in range(25)]
    outlier["core_missing_documents"] = outlier_ids
    outlier["purchase_document_ids"] = outlier_ids
    records.insert(0, outlier)
    input_path = tmp_path / "core-results.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(input_path, records)

    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(input_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--target-case-count",
                "100",
            ]
        )
        == 0
    )

    plan = _read_json(output_root / "missing-core-budget-plan.json")
    assert plan["target_case_count_met"] is True
    assert len(plan["case_plans"]) == 100
    assert [row["candidate_id"] for row in plan["excluded_case_plans"]] == [
        "candidate-cap-outlier"
    ]
    [exclusion] = _read_jsonl(output_root / "missing-core-budget-exclusions.jsonl")
    assert exclusion["candidate_id"] == "candidate-cap-outlier"
    assert exclusion["reason"] == "missing_core_document_cap_exceeded"
    assert exclusion["stage"] == "extraction"
    assert exclusion["source_document_ids"] == outlier_ids


@pytest.mark.usefixtures("_historical_v1_algorithm_fixture")
def test_purchase_missing_requires_non_dry_run_plan_and_paid_activity_flags(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path = _write_execute_budget_plan(tmp_path, output_root)
    policy_path, ledger_path, cohort_path = _write_purchase_policy(tmp_path)

    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(plan_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert "--live-purchase" in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards" / "purchase-missing.json")
    assert failure["status"] == "failed"
    assert failure["paid_activity_executed"] is False
    assert failure["failure_reason"] == (
        "live_purchase_and_fee_acknowledgment_required"
    )


@pytest.mark.usefixtures("_historical_v1_algorithm_fixture")
def test_purchase_missing_refuses_legacy_live_case_dev_before_provider_activity(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path = _write_execute_budget_plan(tmp_path, output_root)
    policy_path, ledger_path, cohort_path = _write_purchase_policy(tmp_path)

    def unexpected_provider(*args: object, **kwargs: object) -> object:
        raise AssertionError("legacy live Case.dev provider must not be constructed")

    monkeypatch.setattr(cli, "_case_dev_client", unexpected_provider)
    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(plan_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
            ]
        )
        == 2
    )
    assert (
        "legacy Case.dev live document purchase is disabled" in capsys.readouterr().err
    )
    assert not ledger_path.exists()
    assert not (output_root / "case-dev-pacer-purchases.json").exists()
    assert not (output_root / "case-dev-pacer-purchases.json").exists()


@pytest.mark.usefixtures("_historical_v1_algorithm_fixture")
def test_purchase_missing_uses_fixture_only_after_explicit_fee_flags(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path = _write_execute_budget_plan(tmp_path, output_root)
    policy_path, ledger_path, cohort_path = _write_purchase_policy(tmp_path)
    _initialize_purchase_ledger(
        tmp_path,
        policy_path=policy_path,
        ledger_path=ledger_path,
        cohort_path=cohort_path,
    )
    fixture_path = tmp_path / "case-dev-purchase.jsonl"
    _write_jsonl(
        fixture_path,
        [
            {
                "method": "POST",
                "path": "/legal/v1/documents/mtd-memo/pacer",
                "params": {"acknowledgePacerFees": True, "live": True},
                "status_code": 200,
                "payload": {
                    "acknowledgePacerFees": True,
                    "downloadUrl": "https://case.dev/download/mtd-memo.pdf",
                    "pacerFees": {
                        "pacerFee": 0,
                        "serviceFee": 3.05,
                        "total": 3.05,
                    },
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
                str(plan_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
                "--capability",
                "document_level_purchase",
                "--case-dev-fixture",
                str(fixture_path),
            ]
        )
        == 0
    )

    purchase = _read_json(output_root / "case-dev-pacer-purchases.json")
    assert purchase["executed_purchase_count"] == 1
    assert purchase["attempts"][0]["status"] == "purchased"
    assert purchase["attempts"][0]["pacer_fees"]["total_usd"] == "3.05"
    run_card = _read_json(output_root / "run-cards" / "purchase-missing.json")
    assert run_card["paid_activity_requested"] is True
    assert run_card["paid_activity_executed"] is True


def test_recap_fetch_live_purchase_wires_signed_broker_without_pacer_credentials(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path = approval.policy
    ledger_path = approval.ledger
    cohort_path = approval.cohort_policy
    output_root = tmp_path / "acquisition"
    document_ids = [
        str(document_id)
        for case_plan in _read_json(plan_path)["case_plans"]
        for document_id in case_plan["purchase_document_ids"]
    ]
    request_ledger = tmp_path / "courtlistener-requests.sqlite3"
    broker_transport = _BrokerTransport(
        *(
            recap_broker.BrokerRawResponse(
                201,
                json.dumps(
                    {"reservation_id": f"reservation-{index}", "id": str(77 + index)}
                ).encode(),
                {"content-type": "application/json"},
            )
            for index, _ in enumerate(document_ids)
        )
    )
    courtlistener_transport = recap_fetch.FixtureRecapFetchTransport(
        [
            response
            for index, document_id in enumerate(document_ids)
            for response in (
                recap_fetch.RecordedRecapFetchResponse(
                    "GET",
                    f"/recap-documents/{document_id}/",
                    {},
                    200,
                    {"id": int(document_id)},
                ),
                recap_fetch.RecordedRecapFetchResponse(
                    "GET", f"/recap-fetch/{77 + index}/", {}, 200, {"status": 2}
                ),
                recap_fetch.RecordedRecapFetchResponse(
                    "GET",
                    f"/recap-documents/{document_id}/",
                    {},
                    200,
                    {
                        "id": int(document_id),
                        "is_available": True,
                        "filepath_local": (
                            f"https://storage.courtlistener.com/{document_id}.pdf"
                        ),
                    },
                ),
            )
        ]
    )
    monkeypatch.setattr(recap_broker, "UrlLibBrokerTransport", lambda: broker_transport)

    def courtlistener_transport_factory(
        base_url: str,
    ) -> recap_fetch.FixtureRecapFetchTransport:
        del base_url
        return courtlistener_transport

    monkeypatch.setattr(
        cli,
        "UrlLibRecapFetchTransport",
        courtlistener_transport_factory,
    )
    for name, value in _recap_fetch_broker_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    monkeypatch.delenv("PACER_USERNAME", raising=False)
    monkeypatch.delenv("PACER_PASSWORD", raising=False)

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                "--controlled-private-root",
                str(approval.controlled_private_root),
                "--purchase-ledger-initialization-receipt",
                str(approval.initialization_receipt),
                "--request-ledger",
                str(request_ledger),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
            ]
        )
        == 0
    )

    assert len(broker_transport.requests) == len(document_ids)
    method, url, body, _ = broker_transport.requests[0]
    assert method == "POST"
    assert url.endswith("/v1/recap-fetch")
    submission = json.loads(body)
    assert submission["recap_document"] == document_ids[0]
    assert (
        submission["purchase_policy_sha256"] == _read_json(policy_path)["policy_sha256"]
    )
    assert submission["reservation_usd"] == "3.05"
    assert courtlistener_transport.requests == [
        request
        for index, document_id in enumerate(document_ids)
        for request in (
            ("GET", f"/recap-documents/{document_id}/", {}),
            ("GET", f"/recap-fetch/{77 + index}/", {}),
            ("GET", f"/recap-documents/{document_id}/", {}),
        )
    ]
    result = _read_json(output_root / "courtlistener-recap-fetch-purchases.json")
    assert result["executed_purchase_count"] == len(document_ids)
    run_card = _read_json(
        output_root / "run-cards" / "purchase-missing-recap-fetch.json"
    )
    assert run_card["paid_activity_requested"] is True
    assert run_card["paid_activity_executed"] is True
    expected_requests = 3 * len(document_ids)
    assert run_card["courtlistener_physical_requests"] == expected_requests
    assert run_card["courtlistener_reservations_this_phase"] == expected_requests
    assert run_card["courtlistener_reservations_total"] == expected_requests
    assert run_card["courtlistener_request_ledger"] == str(request_ledger.resolve())


def test_recap_fetch_live_purchase_missing_config_fails_before_journal_or_http(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path, ledger_path, cohort_path = (
        approval.policy,
        approval.ledger,
        approval.cohort_policy,
    )
    request_ledger = tmp_path / "courtlistener-requests.sqlite3"
    for name in _recap_fetch_broker_env():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *_approved_runtime_args(approval),
                "--request-ledger",
                str(request_ledger),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
            ]
        )
        == 2
    )

    error = capsys.readouterr().err
    assert "missing required broker configuration" in error
    assert "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK" in error
    assert ledger_path.exists()
    assert not output_root.exists()


def test_recap_fetch_live_rejects_offline_fixtures_before_ledger(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path, ledger_path, cohort_path = (
        approval.policy,
        approval.ledger,
        approval.cohort_policy,
    )
    request_ledger = tmp_path / "courtlistener-requests.sqlite3"
    courtlistener_fixture = tmp_path / "courtlistener.jsonl"
    broker_fixture = tmp_path / "broker.json"
    _write_jsonl(courtlistener_fixture, [])
    _write_json(broker_fixture, [])

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *_approved_runtime_args(approval),
                "--request-ledger",
                str(request_ledger),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--purchase-broker-fixture",
                str(broker_fixture),
            ]
        )
        == 2
    )

    assert "cannot be combined with offline fixtures" in capsys.readouterr().err
    assert ledger_path.exists()
    assert not output_root.exists()


def test_recap_fetch_live_requires_request_ledger_before_transport_or_journal(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path, ledger_path, cohort_path = (
        approval.policy,
        approval.ledger,
        approval.cohort_policy,
    )
    for name, value in _recap_fetch_broker_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    monkeypatch.setattr(
        cli,
        "UrlLibRecapFetchTransport",
        lambda _base_url: pytest.fail("CourtListener transport constructed"),
    )

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *_approved_runtime_args(approval),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
            ]
        )
        == 2
    )

    assert "--request-ledger is required" in capsys.readouterr().err
    assert ledger_path.exists()
    assert not output_root.exists()


def test_recap_fetch_invalid_courtlistener_base_fails_before_journal(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path, ledger_path, cohort_path = (
        approval.policy,
        approval.ledger,
        approval.cohort_policy,
    )
    request_ledger = tmp_path / "courtlistener-requests.sqlite3"
    for name, value in _recap_fetch_broker_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    monkeypatch.setenv("COURTLISTENER_BASE_URL", "https://example.com/api/rest/v4")

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *_approved_runtime_args(approval),
                "--request-ledger",
                str(request_ledger),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
            ]
        )
        == 2
    )

    error = capsys.readouterr().err
    assert "CourtListener base URL must be HTTPS on www.courtlistener.com" in error
    assert "Traceback" not in error
    assert ledger_path.exists()
    assert not output_root.exists()


def test_recap_fetch_journal_open_failure_precedes_output_root(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path, ledger_path, cohort_path = (
        approval.policy,
        approval.ledger,
        approval.cohort_policy,
    )
    request_ledger = tmp_path / "courtlistener-requests.sqlite3"
    ledger_path.unlink()
    ledger_path.mkdir()
    for name, value in _recap_fetch_broker_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    monkeypatch.setattr(
        cli,
        "UrlLibRecapFetchTransport",
        lambda _base_url: recap_fetch.FixtureRecapFetchTransport([]),
    )

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *_approved_runtime_args(approval),
                "--request-ledger",
                str(request_ledger),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
            ]
        )
        == 2
    )

    assert "Traceback" not in capsys.readouterr().err
    assert not output_root.exists()


def test_recap_fetch_offline_failure_never_records_paid_activity(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path, ledger_path, cohort_path = (
        approval.policy,
        approval.ledger,
        approval.cohort_policy,
    )
    document_id = str(
        _read_json(plan_path)["case_plans"][0]["purchase_document_ids"][0]
    )
    courtlistener_fixture = tmp_path / "courtlistener.jsonl"
    broker_fixture = tmp_path / "broker.json"
    _write_jsonl(
        courtlistener_fixture,
        [
            {
                "method": "GET",
                "path": f"/recap-documents/{document_id}/",
                "status_code": 200,
                "payload": {"id": int(document_id)},
            }
        ],
    )
    _write_json(
        broker_fixture,
        [{"reservation_id": "reservation-1", "id": "77"}],
    )

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *_approved_runtime_args(approval),
                "--output-root",
                str(output_root),
                "--execute",
                "--acknowledge-pacer-fees",
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--purchase-broker-fixture",
                str(broker_fixture),
            ]
        )
        == 2
    )

    run_card = _read_json(
        output_root / "run-cards" / "purchase-missing-recap-fetch.json"
    )
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False


@pytest.mark.parametrize(
    ("status_code", "error_code"),
    [
        (401, "machine_auth_required"),
        (409, "policy_not_active"),
        (503, "broker_unavailable"),
    ],
)
def test_recap_fetch_live_receipt_rejection_is_clean_nonpaid_failure(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    status_code: int,
    error_code: str,
) -> None:
    output_root = tmp_path / "acquisition"
    plan_path, selection_path, approval = _write_approved_recap_fetch_inputs(
        tmp_path, monkeypatch
    )
    policy_path, ledger_path, cohort_path = (
        approval.policy,
        approval.ledger,
        approval.cohort_policy,
    )
    request_ledger = tmp_path / "courtlistener-requests.sqlite3"
    policy = cli.verify_case_dev_purchase_policy(_read_json(policy_path))
    plan = cli._missing_core_budget_plan(_read_json(plan_path))
    document_id = plan.case_plans[0].purchase_document_ids[0]
    with CaseDevPurchaseJournal(
        ledger_path,
        policy=policy,
        controlled_private_root=approval.controlled_private_root,
        initialization_receipt_path=approval.initialization_receipt,
    ) as journal:
        journal.plan(plan)
        assert journal.submit(document_id)
        journal.mark_unknown(document_id, "prior ambiguous submission")
        operation = journal.operation_evidence(document_id)
        assert operation is not None
        operation_key = str(operation["operation_key"])
    broker_transport = _BrokerTransport(
        recap_broker.BrokerRawResponse(
            status_code,
            json.dumps(
                {"error": {"code": error_code, "message": "rejected"}},
                separators=(",", ":"),
            ).encode(),
            {"content-type": "application/json"},
        )
    )
    monkeypatch.setattr(recap_broker, "UrlLibBrokerTransport", lambda: broker_transport)
    for name, value in _recap_fetch_broker_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")

    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--budget-plan",
                str(plan_path),
                "--selection",
                str(selection_path),
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *_approved_runtime_args(approval),
                "--request-ledger",
                str(request_ledger),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
            ]
        )
        == 2
    )

    error = capsys.readouterr().err
    assert f"purchase broker rejected receipt recovery: {error_code}" in error
    assert "Traceback" not in error
    assert len(broker_transport.requests) == 1
    assert broker_transport.requests[0][1].endswith(f"/v1/receipts/{operation_key}")
    run_card = _read_json(
        output_root / "run-cards" / "purchase-missing-recap-fetch.json"
    )
    assert run_card["paid_activity_requested"] is True
    assert run_card["paid_activity_executed"] is False
    assert run_card["courtlistener_physical_requests"] == 0
    with CaseDevPurchaseJournal(
        ledger_path,
        policy=policy,
        controlled_private_root=approval.controlled_private_root,
        initialization_receipt_path=approval.initialization_receipt,
    ) as journal:
        assert journal.statuses()[document_id] == "unknown"


@pytest.mark.usefixtures("_historical_v1_algorithm_fixture")
def test_core_filter_purchase_and_recovery_flow_builds_parser_requests(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    case_relevance_path = tmp_path / "case-relevance.jsonl"
    _write_jsonl(
        case_relevance_path,
        [
            {
                "candidate_id": "cand-1",
                "documents": [
                    {
                        "source_document_id": "complaint",
                        "setup_runner_label": "core_mtd",
                        "document_role": "complaint",
                        "docket_entry_number": 1,
                        "availability_status": "available",
                        "requires_paid_recovery": False,
                    },
                    {
                        "source_document_id": "mtd-memo",
                        "setup_runner_label": "core_mtd",
                        "document_role": "motion_to_dismiss_memorandum",
                        "docket_entry_number": 34,
                        "availability_status": "unavailable",
                        "requires_paid_recovery": True,
                    },
                ],
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "filter-core-documents",
                "--case-relevance",
                str(case_relevance_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    core_results_path = output_root / "core-filter-results.jsonl"
    assert _read_jsonl(core_results_path)[0]["purchase_document_ids"] == ["mtd-memo"]

    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    policy_path, ledger_path, cohort_path = _write_purchase_policy(tmp_path)
    _initialize_purchase_ledger(
        tmp_path,
        policy_path=policy_path,
        ledger_path=ledger_path,
        cohort_path=cohort_path,
    )
    purchase_fixture_path = tmp_path / "case-dev-purchase.jsonl"
    download_url = "https://case.dev/download/mtd-memo.pdf"
    _write_jsonl(
        purchase_fixture_path,
        [
            {
                "method": "POST",
                "path": "/legal/v1/documents/mtd-memo/pacer",
                "params": {"acknowledgePacerFees": True, "live": True},
                "status_code": 200,
                "payload": {
                    "acknowledgePacerFees": True,
                    "downloadUrl": download_url,
                    "pacerFees": {
                        "pacerFee": 0,
                        "serviceFee": 3.05,
                        "total": 3.05,
                    },
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
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-purchase",
                "--acknowledge-pacer-fees",
                "--capability",
                "document_level_purchase",
                "--case-dev-fixture",
                str(purchase_fixture_path),
            ]
        )
        == 0
    )

    selection_path = tmp_path / "selection.jsonl"
    _write_jsonl(selection_path, [_packet_selection_record()])
    document_fixture_path = tmp_path / "purchased-documents.json"
    _write_json(document_fixture_path, {download_url: "%PDF purchased MTD memo"})
    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(output_root / "case-dev-pacer-purchases.json"),
                "--selection",
                str(selection_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--fixture-documents",
                str(document_fixture_path),
            ]
        )
        == 0
    )

    purchased_manifest_path = output_root / "purchased-document-downloads.jsonl"
    manifest = _read_jsonl(purchased_manifest_path)
    assert manifest[0]["free_or_purchased"] == "purchased"
    assert manifest[0]["purchase_cost_usd"] == "3.05"
    assert manifest[0]["local_path"] == ("cand-1/case-dev-pacer/entry-34_mtd-memo.pdf")
    purchased_document_root = output_root / "documents" / "purchased"
    assert (purchased_document_root / manifest[0]["local_path"]).is_file()
    clearance_path = tmp_path / "purchased-clearance.jsonl"
    _write_clearance(purchased_manifest_path, clearance_path)
    _, materialization_card = _materialized_cli_unit_fixture(monkeypatch, tmp_path)

    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(purchased_manifest_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--document-root",
                str(purchased_document_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    parser_request = _read_jsonl(output_root / "parse-document-requests.jsonl")[0]
    assert parser_request["source_document_id"] == "mtd-memo"
    assert Path(parser_request["input_path"]).is_file()


def test_recover_purchased_rejects_unproven_purchase_result(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    purchase_result_path = tmp_path / "purchase-result.json"
    selection_path = tmp_path / "selection.jsonl"
    purchase_result = {
        "live": True,
        "acknowledge_pacer_fees": False,
        "capability": "document_level_purchase",
        "dry_run": False,
        "projected_cost_usd": "3.05",
        "max_projected_budget_usd": "2250.00",
        "attempts": [],
    }
    _write_json(purchase_result_path, purchase_result)
    _write_jsonl(selection_path, [_packet_selection_record()])

    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(purchase_result_path),
                "--selection",
                str(selection_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--fixture-documents",
                str(tmp_path / "unused.json"),
            ]
        )
        == 2
    )
    assert "fee acknowledgment" in capsys.readouterr().err
    assert not (output_root / "purchased-document-downloads.jsonl").exists()
    failure = _read_json(output_root / "run-cards" / "recover-purchased.json")
    assert failure["status"] == "failed"
    assert "fee acknowledgment" in failure["failure_reason"]


def test_recover_purchased_audits_incomplete_recovery_as_failure(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    purchase_result_path = tmp_path / "purchase-result.json"
    selection_path = tmp_path / "selection.jsonl"
    fixture_path = tmp_path / "purchased-documents.json"
    _write_json(
        purchase_result_path,
        {
            "live": True,
            "acknowledge_pacer_fees": True,
            "capability": "document_level_purchase",
            "dry_run": False,
            "projected_cost_usd": "3.05",
            "max_projected_budget_usd": "2250.00",
            "intended_purchase_count": 1,
            "executed_purchase_count": 1,
            "attempts": [
                {
                    "candidate_id": "cand-1",
                    "source_document_id": "mtd-memo",
                    "status": "purchased",
                    "reason": None,
                    "fee_acknowledged": True,
                    "pacer_fees": {"total_usd": "3.05"},
                    "download_url": "https://case.dev/download/missing.pdf",
                }
            ],
        },
    )
    _write_jsonl(selection_path, [_packet_selection_record()])
    _write_json(fixture_path, {})

    assert (
        main(
            [
                "acquisition",
                "recover-purchased",
                "--purchase-result",
                str(purchase_result_path),
                "--selection",
                str(selection_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--fixture-documents",
                str(fixture_path),
            ]
        )
        == 2
    )
    assert "recovered 0 of 1" in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards" / "recover-purchased.json")
    assert failure["status"] == "failed"
    assert failure["failure_reason"] == "recovered 0 of 1 purchased documents"


def test_download_free_fixture_stage_resume_preserves_manifest_bytes(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    fixture_bytes = b"%PDF Complaint fixture bytes"
    _write_json(fixture_path, {source_url: fixture_bytes.decode()})

    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]
    assert main(command) == 0
    manifest_path = output_root / "free-document-downloads.jsonl"
    first_manifest = manifest_path.read_bytes()
    assert main(command) == 0

    assert manifest_path.read_bytes() == first_manifest
    records = _read_jsonl(manifest_path)
    assert records[0]["reused_existing"] is False
    assert records[0]["sha256"] == hashlib.sha256(fixture_bytes).hexdigest()
    log_records = _read_jsonl(output_root / "logs" / "download-free.jsonl")
    assert len(log_records) == 2
    assert all(record["paid_activity_executed"] is False for record in log_records)


def test_download_free_execute_replaces_exact_dry_run_manifest(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    fixture_bytes = b"%PDF Complaint fixture bytes"
    _write_json(fixture_path, {source_url: fixture_bytes.decode()})
    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--fixture-documents",
        str(fixture_path),
    ]

    assert main(command) == 0
    assert _read_jsonl(output_root / "free-document-downloads.jsonl") == [
        {
            "document_output_root": str(output_root / "documents/free"),
            "dry_run": True,
            "request_count": 1,
            "stage": "download-free",
        }
    ]

    assert main([*command, "--execute"]) == 0
    [record] = _read_jsonl(output_root / "free-document-downloads.jsonl")
    assert record["candidate_id"] == "cand-1"
    assert record["sha256"] == hashlib.sha256(fixture_bytes).hexdigest()
    assert record["reused_existing"] is False


def test_download_free_resume_rejects_changed_requests_without_rewriting_manifest(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    request = {
        "candidate_id": "cand-1",
        "source_provider": "courtlistener",
        "source_document_id": "complaint",
        "docket_entry_number": 1,
        "document_role": "complaint",
        "source_url": source_url,
    }
    _write_jsonl(requests_path, [request])
    _write_json(fixture_path, {source_url: "%PDF Complaint fixture bytes"})
    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]

    assert main(command) == 0
    manifest_path = output_root / "free-document-downloads.jsonl"
    manifest_before = manifest_path.read_bytes()
    changed_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-2.pdf"
    _write_jsonl(requests_path, [{**request, "source_url": changed_url}])
    _write_json(
        fixture_path,
        {
            source_url: "%PDF Complaint fixture bytes",
            changed_url: "%PDF Changed request bytes",
        },
    )

    assert main(command) == 2
    assert "completed free-download manifest does not match current requests" in (
        capsys.readouterr().err
    )
    assert manifest_path.read_bytes() == manifest_before


def test_download_free_resume_rejects_blank_manifest_row_with_failure_card(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    _write_json(fixture_path, {source_url: "%PDF Complaint fixture bytes"})
    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]

    assert main(command) == 0
    manifest_path = output_root / "free-document-downloads.jsonl"
    manifest_path.write_bytes(manifest_path.read_bytes() + b"\n")

    assert main(command) == 2
    assert "unreadable or invalid" in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards/download-free.json")
    assert failure["status"] == "failed"
    assert failure["paid_activity_requested"] is False


def test_download_free_resume_rejects_broken_manifest_symlink(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    _write_json(fixture_path, {source_url: "%PDF Complaint fixture bytes"})
    output_root.mkdir()
    manifest_path = output_root / "free-document-downloads.jsonl"
    manifest_path.symlink_to(tmp_path / "missing-manifest-target.jsonl")

    assert (
        main(
            [
                "acquisition",
                "download-free",
                "--requests",
                str(requests_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--fixture-documents",
                str(fixture_path),
            ]
        )
        == 2
    )

    assert "singly linked regular non-symlink file" in capsys.readouterr().err
    assert manifest_path.is_symlink()
    assert not (tmp_path / "missing-manifest-target.jsonl").exists()
    failure = _read_json(output_root / "run-cards/download-free.json")
    assert failure["status"] == "failed"


def test_download_free_resume_attributes_invalid_checkpoint(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    _write_json(fixture_path, {source_url: "%PDF Complaint fixture bytes"})
    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]

    assert main(command) == 0
    checkpoint = output_root / "documents/free/.download-checkpoint.jsonl"
    checkpoint.write_bytes(checkpoint.read_bytes() + b"\n")

    assert main(command) == 2
    assert "completed free-download checkpoint is unreadable or invalid" in (
        capsys.readouterr().err
    )


def test_download_free_resume_rejects_changed_document_bytes_without_refetch(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    fixture_bytes = b"%PDF Complaint fixture bytes"
    _write_json(fixture_path, {source_url: fixture_bytes.decode()})
    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]

    assert main(command) == 0
    manifest_path = output_root / "free-document-downloads.jsonl"
    manifest_before = manifest_path.read_bytes()
    [record] = _read_jsonl(manifest_path)
    document_path = output_root / "documents/free" / str(record["local_path"])
    document_path.write_bytes(b"%PDF Changed on-disk bytes")

    assert main(command) == 2
    assert "completed free-download document bytes differ" in (capsys.readouterr().err)
    assert manifest_path.read_bytes() == manifest_before
    assert document_path.read_bytes() == b"%PDF Changed on-disk bytes"


def test_download_free_no_resume_rejects_existing_artifacts(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    fixture_path = tmp_path / "free-fixtures.json"
    source_url = "https://www.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )
    _write_json(fixture_path, {source_url: "%PDF Complaint fixture bytes"})

    command = [
        "acquisition",
        "download-free",
        "--requests",
        str(requests_path),
        "--output-root",
        str(output_root),
        "--execute",
        "--fixture-documents",
        str(fixture_path),
    ]
    assert main(command) == 0

    assert main([*command, "--no-resume"]) == 2

    assert "resume is disabled" in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards" / "download-free.json")
    assert failure["status"] == "failed"
    assert failure["paid_activity_executed"] is False
    assert failure["failure_reason"].startswith("existing document artifact")


def test_download_free_live_public_source_requires_explicit_flag(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    requests_path = tmp_path / "free-requests.jsonl"
    source_url = "https://storage.courtlistener.com/recap/gov.uscourts/doc-1.pdf"
    requested_urls: list[str] = []

    class _FakeLiveSource:
        def fetch(self, source_url: str) -> FreeDocumentFetch:
            requested_urls.append(source_url)
            return FreeDocumentFetch(content=b"%PDF live free document")

    monkeypatch.setattr(cli, "UrlLibFreeDocumentSource", _FakeLiveSource)
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": source_url,
            }
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "download-free",
                "--requests",
                str(requests_path),
                "--output-root",
                str(output_root),
                "--execute",
                "--live-public-download",
            ]
        )
        == 0
    )

    assert requested_urls == [source_url]
    records = _read_jsonl(output_root / "free-document-downloads.jsonl")
    assert records[0]["byte_count"] == len(b"%PDF live free document")
    assert records[0]["reused_existing"] is False


@pytest.mark.parametrize("v3_free_public_download", [False, True])
def test_plan_parse_documents_derives_parser_requests_from_download_manifest(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    v3_free_public_download: bool,
) -> None:
    output_root = tmp_path / "acquisition"
    manifest_path = tmp_path / "free-document-downloads.jsonl"
    document_path = (
        output_root / "documents/free/cand-1/courtlistener/entry-1_doc-1.pdf"
    )
    document_path.parent.mkdir(parents=True)
    document_path.write_bytes(b"0123456789")
    digest = hashlib.sha256(document_path.read_bytes()).hexdigest()
    _write_jsonl(
        manifest_path,
        [
            {
                "candidate_id": "cand-1",
                "source_provider": "courtlistener",
                "source_document_id": "entry-1-complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": "https://storage.courtlistener.com/recap/doc-1.pdf",
                "local_path": "cand-1/courtlistener/entry-1_doc-1.pdf",
                "sha256": digest,
                "byte_count": 10,
                "free_or_purchased": "free",
                "retry_count": 0,
                "rate_limited": False,
                "reused_existing": False,
            }
        ],
    )
    clearance_path = tmp_path / "clearance.jsonl"
    _write_clearance(manifest_path, clearance_path)
    free_public_download_capability: object | None = None
    if v3_free_public_download:
        [clearance] = _read_jsonl(clearance_path)
        clearance.update(
            {
                "clearance_basis": "courtlistener_public_download",
                "free_or_purchased": "free",
                "restriction_evidence": [
                    "courtlistener_public_download_record_checked",
                    "document_repair_byte_role_validation_match",
                ],
                "is_private": False,
                "is_sealed": False,
                "reviewer_id": None,
                "controlled_store_provenance": None,
                "reviewed_at": None,
            }
        )
        _write_jsonl(clearance_path, [clearance])
        free_public_download_capability = vars(cli.disclosure_clearance_module)[
            "_FREE_PUBLIC_DOWNLOAD_AUTHORITY"
        ]
    _, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch,
        tmp_path,
        free_public_download_capability=free_public_download_capability,
    )

    assert (
        main(
            [
                "acquisition",
                "plan-parse-documents",
                "--download-manifest",
                str(manifest_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    requests = _read_jsonl(output_root / "parse-document-requests.jsonl")
    assert requests == [
        {
            "candidate_id": "cand-1",
            "source_document_id": "entry-1-complaint",
            "document_role": "complaint",
            "expected_sha256": digest,
            "expected_byte_count": 10,
            "input_path": str(
                output_root
                / "documents"
                / "free"
                / "cand-1"
                / "courtlistener"
                / "entry-1_doc-1.pdf"
            ),
            "markdown_output_path": "markdown/cand-1/entry-1-complaint.md",
        }
    ]


def test_live_mistral_request_carries_role_into_quality_gate(tmp_path: Path) -> None:
    source = tmp_path / "complaint.pdf"
    source.write_bytes(b"%PDF fixture")
    request = cli._mistral_markdown_request(
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "document_role": "complaint",
            "input_path": str(source),
            "expected_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "expected_byte_count": source.stat().st_size,
        },
        output_root=tmp_path / "output",
    )

    class _ShortParser:
        def run(
            self,
            command: tuple[str, ...],
            *,
            cwd: Path,
            timeout_seconds: int,
        ) -> ParserProcessResult:
            del cwd, timeout_seconds
            Path(command[command.index("--file") + 1]).with_suffix(".md").write_text(
                "Short.", encoding="utf-8"
            )
            return ParserProcessResult(return_code=0)

    (record,) = cli.convert_documents_to_markdown(
        (request,),
        config=cli.MistralParserConfig(parser_root=tmp_path),
        runner=_ShortParser(),
    )

    assert request.document_role == "complaint"
    assert record.status is cli.MistralMarkdownConversionStatus.FAILED
    assert record.quality_flags == ("parse_quality_rejected",)


def test_parse_and_build_packet_acquisition_fixture_flow(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    fixture_markdown = tmp_path / "fixture-markdown"
    fixture_markdown.mkdir()
    (fixture_markdown / "complaint.md").write_text(
        "Complaint markdown", encoding="utf-8"
    )
    (fixture_markdown / "mtd-memo.md").write_text("MTD markdown", encoding="utf-8")
    parse_requests = tmp_path / "parse-requests.jsonl"
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF fixture")
    source_digest = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    _write_jsonl(
        parse_requests,
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": "complaint",
                "input_path": str(source_pdf),
                "expected_sha256": source_digest,
                "expected_byte_count": source_pdf.stat().st_size,
            },
            {
                "candidate_id": "cand-1",
                "source_document_id": "mtd-memo",
                "input_path": str(source_pdf),
                "expected_sha256": source_digest,
                "expected_byte_count": source_pdf.stat().st_size,
            },
        ],
    )
    parse_clearance = tmp_path / "parse-clearance.jsonl"
    _write_jsonl(
        parse_clearance,
        [
            {
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "sha256": source_digest,
                "byte_count": source_pdf.stat().st_size,
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["controlled fixture review"],
                "reviewer_id": "fixture-reviewer",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": "2026-07-12T18:00:00Z",
            }
            for document_id in ("complaint", "mtd-memo")
        ],
    )
    document_root, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch, tmp_path, skip_packet_planner_replay=True
    )
    selection = tmp_path / "materialized-selection.jsonl"
    manifest = tmp_path / "materialized-manifest.jsonl"
    _write_jsonl(selection, [{"candidate_id": "cand-1"}])
    _write_jsonl(
        manifest,
        [
            {"candidate_id": "cand-1", "source_document_id": document_id}
            for document_id in ("complaint", "mtd-memo")
        ],
    )
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(parse_requests),
                "--disclosure-clearance",
                str(parse_clearance),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
                "--fixture-markdown-dir",
                str(fixture_markdown),
            ]
        )
        == 0
    )

    conversions = _read_jsonl(output_root / "mistral-markdown-conversions.jsonl")
    packet_input = tmp_path / "packet-input.jsonl"
    _write_jsonl(
        packet_input,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "court": "S.D.N.Y.",
                "docket_number": "1:26-cv-1",
                "generated_at": _GENERATED_AT,
                "docket_markdown": {
                    "model_visible_markdown": "# Model docket\n\nMTD filed.",
                    "audit_markdown": "# Audit docket\n\nOrder excluded.",
                },
                "documents": [
                    _provenance("complaint", "complaint", 1),
                    _provenance("mtd-memo", "motion_to_dismiss_memorandum", 34),
                ],
                "parsed_documents": [
                    {
                        "source_document_id": conversion["source_document_id"],
                        "markdown_path": conversion["markdown_path"],
                        "extraction_method": "fixture_markdown",
                    }
                    for conversion in conversions
                ],
                "prediction_units": [_prediction_unit()],
                "target_docket_entry_numbers": [34],
            }
        ],
    )
    planner_card = tmp_path / "packet-planner.json"
    _write_packet_planner_card(
        planner_card,
        packet_input=packet_input,
        selection=selection,
        manifest=manifest,
        clearance=parse_clearance,
        document_root=document_root,
        materialization_run_card=materialization_card,
    )
    model_registry = _write_model_registry(tmp_path)

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_input),
                "--packet-input-run-card",
                str(planner_card),
                "--selection",
                str(selection),
                "--download-manifest",
                str(manifest),
                "--parser-manifest",
                str(selection),
                "--parser-run-card",
                str(output_root / "run-cards/parse-documents.json"),
                "--parse-plan-run-card",
                str(output_root / "run-cards/parse-documents.json"),
                "--disclosure-clearance",
                str(parse_clearance),
                "--raw-prediction-units",
                str(selection),
                "--prediction-units",
                str(selection),
                "--llm-unitization-audit",
                str(selection),
                "--llm-unitize-run-card",
                str(selection),
                "--llm-unitize-provider-journal",
                str(selection),
                "--original-unitization-review-queue",
                str(selection),
                "--stage-a-structural-flags",
                str(selection),
                "--stage-a-structural-review-audit",
                str(selection),
                "--stage-a-review-run-card",
                str(selection),
                "--stage-a-review-provider-journal",
                str(selection),
                "--stage-a-review-model-registry",
                str(model_registry),
                "--stage-a-review-model-key",
                "fixture:fixture-model",
                "--unitization-review-queue",
                str(selection),
                "--unitization-review-adjudications",
                str(selection),
                "--apply-unitization-review-run-card",
                str(selection),
                "--model-registry",
                str(model_registry),
                "--expected-model-registry-sha256",
                hashlib.sha256(model_registry.read_bytes()).hexdigest(),
                "--raw-html-dir",
                str(document_root),
                "--raw-artifacts-manifest",
                str(selection),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(document_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    packet = _read_jsonl(output_root / "packets.jsonl")[0]
    assert [document["source_document_id"] for document in packet["documents"]] == [
        "cand-1:controlled-docket",
        "complaint",
        "mtd-memo",
    ]
    assert (output_root / "case-packets.jsonl").exists()
    audit = _read_jsonl(output_root / "packet-audit.jsonl")[0]
    assert (
        audit["controlled_docket"]["audit_markdown"]
        == "# Audit docket\n\nOrder excluded."
    )


@pytest.mark.parametrize("with_gap", [False, True])
def test_parse_documents_reuses_authenticated_live_mistral_output_and_parses_only_gaps(
    tmp_path: Path, monkeypatch: MonkeyPatch, with_gap: bool
) -> None:
    """Relocated exact inputs copy; only unmatched inputs reach the parser."""

    output_root = tmp_path / "successor"
    previous_root = tmp_path / "previous-markdown"
    previous_markdown = previous_root / "cand-1" / "complaint.md"
    previous_markdown.parent.mkdir(parents=True)
    # Reused Markdown is reassessed under the authenticated ``complaint`` role,
    # so the historical fixture must clear the pleading threshold it claims.
    markdown = (
        "# Complaint\n\nExact historical Markdown that states enough of the "
        "pleading to clear the complaint role's substantive-density floor "
        "rather than relying on the permissive unknown-role fallback.\n\n"
        "Plaintiff alleges breach of the parties' written agreement and seeks "
        "damages, interest, and costs.\n"
    )
    previous_markdown.write_text(markdown, encoding="utf-8")
    source = tmp_path / "relocated" / "complaint.pdf"
    source.parent.mkdir()
    source.write_bytes(b"%PDF exact content")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    previous_request = tmp_path / "previous-requests.jsonl"
    current_request = tmp_path / "current-requests.jsonl"
    request_record = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "document_role": "complaint",
        "expected_sha256": digest,
        "expected_byte_count": source.stat().st_size,
    }
    _write_jsonl(
        previous_request,
        [{**request_record, "input_path": str(tmp_path / "old" / "complaint.pdf")}],
    )
    current_requests = [{**request_record, "input_path": str(source)}]
    gap_source = tmp_path / "relocated" / "new.pdf"
    gap_source.write_bytes(b"%PDF new content")
    gap_digest = hashlib.sha256(gap_source.read_bytes()).hexdigest()
    if with_gap:
        current_requests.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": "new",
                "document_role": "complaint",
                "expected_sha256": gap_digest,
                "expected_byte_count": gap_source.stat().st_size,
                "input_path": str(gap_source),
            }
        )
    _write_jsonl(current_request, current_requests)
    conversion = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "status": "succeeded",
        "input_path": str(tmp_path / "old" / "complaint.pdf"),
        "markdown_path": "cand-1/complaint.md",
        "metadata_path": "cand-1/complaint.metadata.json",
        "parser_config": {
            "engine": "mistral",
            "parser_root": str(tmp_path / "parser"),
            "parser_version": "1.0.0",
            "parser_revision": cli.EXPECTED_PARSER_REVISION,
            "expected_parser_revision": cli.EXPECTED_PARSER_REVISION,
            "timeout_seconds": 600,
            "debug": False,
            "command": [
                "uv",
                "run",
                "parser-pdf",
                "--file",
                str(tmp_path / "old" / "complaint.pdf"),
                "--mistral",
                "--no-ocr",
            ],
        },
        "quality_flags": [],
        "extracted_text": {
            "source_document_id": "complaint",
            "extracted_at": _GENERATED_AT,
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "quality_flags": [],
        },
        "source_sha256": digest,
        "source_byte_count": source.stat().st_size,
        "stdout": "",
        "stderr": "",
        "error_message": None,
    }
    _write_json(previous_markdown.with_suffix(".metadata.json"), conversion)
    previous_manifest = tmp_path / "previous-conversions.jsonl"
    _write_jsonl(previous_manifest, [conversion])
    previous_card = tmp_path / "previous-parse.json"
    _write_json(
        previous_card,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "parse-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "record_count": 1,
            "source_commitments": {
                "requests": {
                    "path": str(previous_request.resolve()),
                    "sha256": cli._bytes_sha256(previous_request.read_bytes()),
                }
            },
            "output_commitments": {
                "parser_manifest": {
                    "path": str(previous_manifest.resolve()),
                    "sha256": cli._bytes_sha256(previous_manifest.read_bytes()),
                }
            },
            "parser_execution": {
                "mode": "live_mistral",
                "engine": "mistral",
                "parser_revision": cli.EXPECTED_PARSER_REVISION,
                "parser_root": str(tmp_path / "parser"),
                "fixture_markdown": False,
            },
        },
    )
    clearance = tmp_path / "clearance.jsonl"
    clearance_records = [
        {
            "schema_version": "legalforecast.disclosure_clearance.v1",
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "sha256": digest,
            "byte_count": source.stat().st_size,
            "status": "cleared",
            "restriction_status": "public",
            "restriction_evidence": ["fixture"],
            "reviewer_id": "fixture-reviewer",
            "controlled_store_provenance": "private-store://fixture/reviews",
            "reviewed_at": _GENERATED_AT,
        }
    ]
    if with_gap:
        clearance_records.append(
            {
                **clearance_records[0],
                "source_document_id": "new",
                "sha256": gap_digest,
                "byte_count": gap_source.stat().st_size,
            }
        )
    _write_jsonl(clearance, clearance_records)
    _, materialization_card = _materialized_cli_unit_fixture(monkeypatch, tmp_path)
    # The verified materialization manifest is the authenticated statement of
    # each document's role; the live parse plan is bound to it.
    materialized_manifest_records = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "complaint",
            "document_role": "complaint",
        }
    ]
    if with_gap:
        materialized_manifest_records.append(
            {
                "candidate_id": "cand-1",
                "source_document_id": "new",
                "document_role": "complaint",
            }
        )
    _write_jsonl(
        tmp_path / "materialized-manifest.jsonl", materialized_manifest_records
    )

    provider_requests: list[tuple[str, ...]] = []

    def parse_gaps(
        requests: tuple[cli.MistralMarkdownConversionRequest, ...],
        **_kwargs: object,
    ) -> tuple[cli.MistralMarkdownConversionRecord, ...]:
        provider_requests.append(
            tuple(request.source_document_id for request in requests)
        )
        if not with_gap:
            raise AssertionError("live Mistral provider conversion must not run")
        assert tuple(request.source_document_id for request in requests) == ("new",)
        request = requests[0]
        gap_markdown = (
            "# New\n\nThe freshly parsed gap document also carries enough "
            "substantive pleading text to clear the complaint role's density "
            "floor when the completed run is later reauthenticated.\n\n"
            "Plaintiff alleges breach of the same written supply agreement "
            "and seeks damages, interest, and costs.\n"
        )
        request.markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        request.markdown_output_path.write_text(gap_markdown, encoding="utf-8")
        record = cli.MistralMarkdownConversionRecord(
            candidate_id=request.candidate_id,
            source_document_id=request.source_document_id,
            status=cli.MistralMarkdownConversionStatus.SUCCEEDED,
            input_path=str(request.input_path),
            markdown_path="cand-1/new.md",
            metadata_path="cand-1/new.metadata.json",
            parser_config={
                "engine": "mistral",
                "parser_root": str(tmp_path / "parser"),
                "parser_version": "1.0.0",
                "parser_revision": cli.EXPECTED_PARSER_REVISION,
                "expected_parser_revision": cli.EXPECTED_PARSER_REVISION,
                "timeout_seconds": 600,
                "debug": False,
                "command": [
                    "uv",
                    "run",
                    "parser-pdf",
                    "--file",
                    str(request.input_path),
                    "--mistral",
                    "--no-ocr",
                ],
            },
            quality_flags=(),
            extracted_text=cli.ExtractedTextArtifact(
                source_document_id=request.source_document_id,
                extracted_at=datetime.fromisoformat(_GENERATED_AT),
                extraction_method="mistral_parser_markdown",
                text_sha256=hashlib.sha256(gap_markdown.encode()).hexdigest(),
            ),
            source_sha256=request.expected_sha256,
            source_byte_count=request.expected_byte_count,
        )
        _write_json(
            request.markdown_output_path.with_suffix(".metadata.json"),
            record.to_record(),
        )
        return (record,)

    monkeypatch.setattr(cli, "convert_documents_to_markdown", parse_gaps)
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(current_request),
                "--disclosure-clearance",
                str(clearance),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
                "--resume",
                "--reuse-live-mistral-run-card",
                str(previous_card),
                "--reuse-markdown-root",
                str(previous_root),
            ]
        )
        == 0
    )
    assert (output_root / "markdown" / "cand-1" / "complaint.md").read_text(
        encoding="utf-8"
    ) == markdown
    assert (
        json.loads(
            (
                output_root / "markdown" / "cand-1" / "complaint.metadata.json"
            ).read_text()
        )
        == conversion
    )
    manifest = _read_jsonl(output_root / "mistral-markdown-conversions.jsonl")
    assert manifest[0] == conversion
    assert [record["source_document_id"] for record in manifest] == (
        ["complaint", "new"] if with_gap else ["complaint"]
    )
    assert provider_requests == ([("new",)] if with_gap else [])
    run_card = json.loads(
        (output_root / "run-cards" / "parse-documents.json").read_text()
    )
    assert all(
        set(commitment) == {"path", "sha256"}
        for commitment in run_card["source_commitments"].values()
    )
    assert (
        run_card["parser_execution"]["reused_live_mistral"]["reused_record_count"] == 1
    )
    assert run_card["parser_execution"]["reused_live_mistral"]["parsed_gap_count"] == (
        1 if with_gap else 0
    )
    manifest_bytes = (output_root / "mistral-markdown-conversions.jsonl").read_bytes()
    run_card_bytes = (output_root / "run-cards" / "parse-documents.json").read_bytes()

    def reject_duplicate_provider_call(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("completed parse reuse must not call the provider")

    monkeypatch.setattr(
        cli, "convert_documents_to_markdown", reject_duplicate_provider_call
    )
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(current_request),
                "--disclosure-clearance",
                str(clearance),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
                "--resume",
                "--reuse-live-mistral-run-card",
                str(previous_card),
                "--reuse-markdown-root",
                str(previous_root),
            ]
        )
        == 0
    )
    assert (
        output_root / "mistral-markdown-conversions.jsonl"
    ).read_bytes() == manifest_bytes
    assert (output_root / "run-cards" / "parse-documents.json").read_bytes() == (
        run_card_bytes
    )
    (output_root / "mistral-markdown-conversions.jsonl").write_bytes(
        manifest_bytes + b"\n"
    )
    assert (
        main(
            [
                "acquisition",
                "parse-documents",
                "--requests",
                str(current_request),
                "--disclosure-clearance",
                str(clearance),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--execute",
                "--resume",
                "--reuse-live-mistral-run-card",
                str(previous_card),
                "--reuse-markdown-root",
                str(previous_root),
            ]
        )
        == 2
    )


@pytest.mark.parametrize(
    "failure", ["tamper", "config", "quality", "symlink", "partial", "path"]
)
def test_live_mistral_reuse_helper_fails_closed(tmp_path: Path, failure: str) -> None:
    root = tmp_path / "prior"
    artifact = root / "cand" / "doc.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("historical", encoding="utf-8")
    digest = hashlib.sha256(b"source").hexdigest()
    record = {
        "candidate_id": "cand",
        "source_document_id": "doc",
        "status": "succeeded",
        "input_path": "/old/doc.pdf",
        "markdown_path": "cand/doc.md",
        "metadata_path": "cand/doc.metadata.json",
        "parser_config": {
            "engine": "mistral",
            "parser_root": "/parser",
            "parser_revision": cli.EXPECTED_PARSER_REVISION,
            "expected_parser_revision": cli.EXPECTED_PARSER_REVISION,
            "timeout_seconds": 60,
            "debug": False,
            "command": [
                "uv",
                "run",
                "parser-pdf",
                "--file",
                "/old/doc.pdf",
                "--mistral",
                "--no-ocr",
            ],
        },
        "quality_flags": [],
        "extracted_text": {
            "source_document_id": "doc",
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": hashlib.sha256(b"historical").hexdigest(),
            "quality_flags": [],
        },
        "source_sha256": digest,
        "source_byte_count": 6,
        "stdout": "",
        "stderr": "",
        "error_message": None,
    }
    artifact.with_suffix(".metadata.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    requests_path = tmp_path / "requests.jsonl"
    manifest_path = tmp_path / "manifest.jsonl"
    _write_jsonl(
        requests_path,
        [
            {
                "candidate_id": "cand",
                "source_document_id": "doc",
                "input_path": "/old/doc.pdf",
                "expected_sha256": digest,
                "expected_byte_count": 6,
            }
        ],
    )
    _write_jsonl(manifest_path, [record])
    card_path = tmp_path / "card.json"
    _write_json(
        card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "parse-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "record_count": 1,
            "source_commitments": {
                "requests": {
                    "path": str(requests_path),
                    "sha256": cli._bytes_sha256(requests_path.read_bytes()),
                }
            },
            "output_commitments": {
                "parser_manifest": {
                    "path": str(manifest_path),
                    "sha256": cli._bytes_sha256(manifest_path.read_bytes()),
                }
            },
            "parser_execution": {
                "mode": "live_mistral",
                "engine": "mistral",
                "parser_revision": cli.EXPECTED_PARSER_REVISION,
                "fixture_markdown": False,
            },
        },
    )
    request = cli.MistralMarkdownConversionRequest(
        "cand",
        "doc",
        tmp_path / "new.pdf",
        tmp_path / "out" / "markdown" / "cand" / "doc.md",
        digest,
        6,
    )
    if failure == "tamper":
        artifact.write_text("tampered", encoding="utf-8")
    elif failure == "config":
        record["parser_config"]["debug"] = True
        artifact.with_suffix(".metadata.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        _write_jsonl(manifest_path, [record])
        _write_json(
            card_path,
            {
                **json.loads(card_path.read_text()),
                "output_commitments": {
                    "parser_manifest": {
                        "path": str(manifest_path),
                        "sha256": cli._bytes_sha256(manifest_path.read_bytes()),
                    }
                },
            },
        )
    elif failure == "quality":
        record["quality_flags"] = ["empty_markdown"]
        record["extracted_text"]["quality_flags"] = ["empty_markdown"]
        artifact.with_suffix(".metadata.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        _write_jsonl(manifest_path, [record])
        card = json.loads(card_path.read_text())
        card["output_commitments"] = {
            "parser_manifest": {
                "path": str(manifest_path),
                "sha256": cli._bytes_sha256(manifest_path.read_bytes()),
            }
        }
        _write_json(card_path, card)
    elif failure == "symlink":
        artifact.unlink()
        artifact.symlink_to(tmp_path / "elsewhere")
    elif failure == "partial":
        destination = request.markdown_output_path
        destination.parent.mkdir(parents=True)
        destination.write_text("partial", encoding="utf-8")
    else:
        request = cli.MistralMarkdownConversionRequest(
            "cand",
            "doc",
            tmp_path / "new.pdf",
            tmp_path / "out" / "markdown" / "cand" / "other.md",
            digest,
            6,
        )
    with pytest.raises(cli.CommandError):
        cli._reuse_live_mistral_parse_outputs(
            prior_run_card_path=card_path,
            prior_markdown_root=root,
            requests=(request,),
            output_root=tmp_path / "out",
        )


def test_live_mistral_reuse_plans_exact_intersection_and_authenticates_dropped_rows(
    tmp_path: Path,
) -> None:
    prior_root = tmp_path / "prior"
    digest_by_document = {
        "kept": hashlib.sha256(b"kept-source").hexdigest(),
        "dropped": hashlib.sha256(b"dropped-source").hexdigest(),
    }
    prior_requests: list[dict[str, object]] = []
    prior_records: list[dict[str, object]] = []
    markdown_by_document: dict[str, str] = {}
    for document_id, digest in digest_by_document.items():
        # Reuse reassesses Markdown under the current authenticated role, so the
        # prior fixture has to clear the complaint threshold it is reused under.
        markdown = (
            f"# {document_id}\n\nPlaintiff alleges that the defendant breached "
            "the parties' written supply agreement by refusing to deliver the "
            "goods it had promised.\n\nPlaintiff seeks damages, interest, and "
            "costs for the resulting losses, together with such further relief "
            "as the court deems just.\n"
        )
        markdown_by_document[document_id] = markdown
        markdown_path = prior_root / "cand" / f"{document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
        request = {
            "candidate_id": "cand",
            "source_document_id": document_id,
            "input_path": f"/old/{document_id}.pdf",
            "expected_sha256": digest,
            "expected_byte_count": len(f"{document_id}-source"),
        }
        record = {
            "candidate_id": "cand",
            "source_document_id": document_id,
            "status": "succeeded",
            "input_path": f"/old/{document_id}.pdf",
            "markdown_path": f"cand/{document_id}.md",
            "metadata_path": f"cand/{document_id}.metadata.json",
            "parser_config": {
                "engine": "mistral",
                "parser_root": "/parser",
                "parser_revision": cli.EXPECTED_PARSER_REVISION,
                "expected_parser_revision": cli.EXPECTED_PARSER_REVISION,
                "timeout_seconds": 60,
                "debug": False,
                "command": [
                    "uv",
                    "run",
                    "parser-pdf",
                    "--file",
                    f"/old/{document_id}.pdf",
                    "--mistral",
                    "--no-ocr",
                ],
            },
            "quality_flags": [],
            "extracted_text": {
                "source_document_id": document_id,
                "extraction_method": "mistral_parser_markdown",
                "text_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
                "quality_flags": [],
            },
            "source_sha256": digest,
            "source_byte_count": len(f"{document_id}-source"),
            "stdout": "",
            "stderr": "",
            "error_message": None,
        }
        _write_json(markdown_path.with_suffix(".metadata.json"), record)
        prior_requests.append(request)
        prior_records.append(record)
    requests_path = tmp_path / "prior-requests.jsonl"
    manifest_path = tmp_path / "prior-manifest.jsonl"
    _write_jsonl(requests_path, prior_requests)
    _write_jsonl(manifest_path, prior_records)
    card_path = tmp_path / "prior-card.json"
    _write_json(
        card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "parse-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "record_count": 2,
            "source_commitments": {
                "requests": {
                    "path": str(requests_path),
                    "sha256": cli._bytes_sha256(requests_path.read_bytes()),
                }
            },
            "output_commitments": {
                "parser_manifest": {
                    "path": str(manifest_path),
                    "sha256": cli._bytes_sha256(manifest_path.read_bytes()),
                }
            },
            "parser_execution": {
                "mode": "live_mistral",
                "engine": "mistral",
                "parser_revision": cli.EXPECTED_PARSER_REVISION,
                "fixture_markdown": False,
            },
        },
    )
    output_root = tmp_path / "out"
    kept = cli.MistralMarkdownConversionRequest(
        "cand",
        "kept",
        tmp_path / "relocated-kept.pdf",
        output_root / "markdown" / "cand" / "kept.md",
        digest_by_document["kept"],
        len("kept-source"),
        document_role="complaint",
    )
    new_digest = hashlib.sha256(b"new-source").hexdigest()
    new = cli.MistralMarkdownConversionRequest(
        "cand",
        "new",
        tmp_path / "new.pdf",
        output_root / "markdown" / "cand" / "new.md",
        new_digest,
        len("new-source"),
        document_role="complaint",
    )

    plan = cli._reuse_live_mistral_parse_outputs(
        prior_run_card_path=card_path,
        prior_markdown_root=prior_root,
        requests=(new, kept),
        output_root=output_root,
    )

    assert plan.gaps == (new,)
    assert len(plan.records_by_key) == 1
    assert plan.source["prior_record_count"] == 2
    assert plan.source["reused_record_count"] == 1
    assert plan.source["parsed_gap_count"] == 1
    assert (
        kept.markdown_output_path.read_text(encoding="utf-8")
        == (markdown_by_document["kept"])
    )

    (prior_root / "cand" / "dropped.md").write_text(
        "tampered dropped row", encoding="utf-8"
    )
    second_output = tmp_path / "second-out"
    with pytest.raises(cli.CommandError):
        cli._reuse_live_mistral_parse_outputs(
            prior_run_card_path=card_path,
            prior_markdown_root=prior_root,
            requests=(new, kept),
            output_root=second_output,
        )
    assert not second_output.exists()


@pytest.mark.parametrize(
    "producer_mutation", [None, "input", "raw", "markdown", "bridge"]
)
def test_plan_packet_inputs_bridges_acquisition_outputs_to_build_packets(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    producer_mutation: str | None,
) -> None:
    candidate_id = "123"
    output_root = tmp_path / "acquisition"
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    raw_html = _packet_input_docket_html().encode()
    raw_html_path = raw_html_dir / f"{candidate_id}.html"
    raw_html_path.write_bytes(raw_html)
    raw_artifacts_path = tmp_path / "raw-artifacts.jsonl"
    _write_jsonl(
        raw_artifacts_path,
        [
            {
                "candidate_id": f"courtlistener-docket-{candidate_id}",
                "path": str(raw_html_path),
                "byte_count": len(raw_html),
                "sha256": hashlib.sha256(raw_html).hexdigest(),
            }
        ],
    )
    selection_path = tmp_path / "selection.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    clearance_path = tmp_path / "clearance.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "units.jsonl"
    registry_path = _write_model_registry(tmp_path)
    markdown_root = output_root / "markdown"
    for source_document_id, markdown in {
        "complaint": "Complaint markdown",
        "mtd-memo": "MTD markdown",
        "decision": "Decision markdown",
    }.items():
        markdown_path = markdown_root / candidate_id / f"{source_document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
    selection_record = _packet_selection_record(candidate_id)
    selection_record.update(
        {
            "nature_of_suit": "Civil Rights",
            "nos_macro_category": "civil_rights",
            "related_family_id": "related-fixture",
            "mdl_family_id": "mdl-fixture",
        }
    )
    _write_jsonl(selection_path, [selection_record])
    _write_jsonl(
        downloads_path,
        [
            _download_record("complaint", "complaint", 1, candidate_id=candidate_id),
            _download_record(
                "mtd-memo",
                "motion_to_dismiss_memorandum",
                34,
                candidate_id=candidate_id,
            ),
            _download_record("decision", "decision", 50, candidate_id=candidate_id),
        ],
    )
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", candidate_id=candidate_id),
            _parser_record("mtd-memo", candidate_id=candidate_id),
            _parser_record("decision", candidate_id=candidate_id),
        ],
    )
    _write_clearance(downloads_path, clearance_path)
    _write_jsonl(
        units_path,
        [_finalized_prediction_unit_record(candidate_id)],
    )
    document_root, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch, tmp_path
    )
    raw_provenance_bridge_path: Path | None = None
    bridge_load_count = 0
    if producer_mutation == "bridge":
        raw_provenance_bridge_path = tmp_path / "raw-provenance-bridge.json"
        raw_provenance_bridge_path.write_bytes(b"original bridge")

        def load_bridge(path: Path) -> Any:
            nonlocal bridge_load_count
            assert path == raw_provenance_bridge_path
            bridge_load_count += 1
            return SimpleNamespace(
                raw_artifacts_manifest_path=raw_artifacts_path.resolve(),
                source_raw_html_dir=raw_html_dir.resolve(),
                raw_artifact_bytes_by_path=(
                    {}
                    if path.read_bytes() == b"original bridge"
                    else {"mutated": b"bridge"}
                ),
            )

        monkeypatch.setattr(
            cli,
            "load_verified_target_raw_docket_auxiliary_provenance_bridge",
            load_bridge,
        )
    command = [
        "acquisition",
        "plan-packet-inputs",
        "--selection",
        str(selection_path),
        "--download-manifest",
        str(downloads_path),
        "--parser-manifest",
        str(parser_path),
        "--disclosure-clearance",
        str(clearance_path),
        "--prediction-units",
        str(units_path),
        "--model-registry",
        str(registry_path),
        "--raw-html-dir",
        str(raw_html_dir),
        "--raw-artifacts-manifest",
        str(raw_artifacts_path),
        "--document-root",
        str(document_root),
        "--markdown-root",
        str(markdown_root),
        "--materialization-run-card",
        str(materialization_card),
        "--output-root",
        str(output_root),
        "--generated-at",
        _GENERATED_AT,
        "--search-window",
        "2026-04-24..2026-05-18",
        "--execute",
    ]
    if raw_provenance_bridge_path is not None:
        command.extend(("--raw-provenance-bridge", str(raw_provenance_bridge_path)))
    tree_snapshot_roots: list[Path] = []
    original_tree_snapshot = cli._materializer_tree_snapshot

    def counted_tree_snapshot(root: Path) -> dict[str, bytes]:
        tree_snapshot_roots.append(root.resolve())
        return original_tree_snapshot(root)

    snapshot_check_labels: list[str] = []
    original_snapshot_check = cli._require_snapshot_unchanged

    def counted_snapshot_check(snapshots: Mapping[Path, bytes], *, label: str) -> None:
        snapshot_check_labels.append(label)
        original_snapshot_check(snapshots, label=label)

    monkeypatch.setattr(cli, "_materializer_tree_snapshot", counted_tree_snapshot)
    monkeypatch.setattr(cli, "_require_snapshot_unchanged", counted_snapshot_check)
    if producer_mutation is not None:
        original_planner = cli.plan_packet_build_inputs

        def mutate_after_planning(**kwargs: Any) -> Any:
            plan = original_planner(**kwargs)
            target = {
                "input": selection_path,
                "raw": raw_html_path,
                "markdown": markdown_root / candidate_id / "complaint.md",
                "bridge": raw_provenance_bridge_path,
            }[producer_mutation]
            assert target is not None
            target.write_bytes(b"mutated after captured-byte planning")
            return plan

        monkeypatch.setattr(cli, "plan_packet_build_inputs", mutate_after_planning)
        expected = {
            "input": "plan-packet-inputs input changed",
            "raw": "raw HTML tree changed",
            "markdown": "Markdown tree changed",
            "bridge": "plan-packet-inputs input changed",
        }[producer_mutation]
        assert main(command) == 2
        assert expected in capsys.readouterr().err
        assert not (output_root / "run-cards" / "plan-packet-inputs.json").exists()
        if producer_mutation == "bridge":
            assert bridge_load_count == 1
        return

    assert main(command) == 0
    assert tree_snapshot_roots.count(raw_html_dir.resolve()) == 2
    assert tree_snapshot_roots.count(markdown_root.resolve()) == 2
    assert snapshot_check_labels.count("plan-packet-inputs input") == 1

    packet_input = _read_jsonl(output_root / "packet-build-input.jsonl")[0]
    assert packet_input["decision_date"] == "2026-05-18"
    assert packet_input["metadata"]["decision_date"] == "2026-05-18"
    assert packet_input["metadata"]["nature_of_suit"] == "Civil Rights"
    assert packet_input["metadata"]["nos_macro_category"] == "civil_rights"
    assert packet_input["related_family_id"] == "related-fixture"
    assert packet_input["mdl_family_id"] == "mdl-fixture"
    assert (
        packet_input["documents"][0]["source_document_id"]
        == f"{candidate_id}-complaint"
    )
    assert packet_input["prediction_units"][0]["source_citations"] == [
        {"document_id": f"{candidate_id}-complaint", "page": 1}
    ]
    expected_raw_provenance = {
        "selection_candidate_id": candidate_id,
        "manifest_candidate_id": f"courtlistener-docket-{candidate_id}",
        "binding_kind": "courtlistener_docket_numeric_alias",
        "manifest_path": str(raw_html_path),
        "sha256": hashlib.sha256(raw_html).hexdigest(),
        "byte_count": len(raw_html),
    }
    assert packet_input["raw_artifact_provenance"] == expected_raw_provenance
    assert len(_read_jsonl(output_root / "document-manifest.jsonl")) == 3
    candidate_manifest = _read_jsonl(output_root / "candidate-manifest.jsonl")[0]
    assert candidate_manifest["manifest_record_hash"]
    assert candidate_manifest["nature_of_suit"] == "Civil Rights"
    assert candidate_manifest["nos_macro_category"] == "civil_rights"
    assert candidate_manifest["related_family_id"] == "related-fixture"
    assert candidate_manifest["mdl_family_id"] == "mdl-fixture"
    assert candidate_manifest["raw_artifact_provenance"] == expected_raw_provenance
    run_card = _read_json(output_root / "run-cards" / "plan-packet-inputs.json")
    assert run_card["raw_artifacts_manifest_path"] == str(raw_artifacts_path.resolve())
    assert (
        run_card["raw_artifacts_manifest_sha256"]
        == hashlib.sha256(raw_artifacts_path.read_bytes()).hexdigest()
    )
    assert run_card["model_registry_path"] == str(registry_path.resolve())
    assert (
        run_card["model_registry_sha256"]
        == hashlib.sha256(registry_path.read_bytes()).hexdigest()
    )
    assert str(raw_artifacts_path) in run_card["input_paths"]
    assert str(registry_path) in run_card["input_paths"]

    packet_input_path = output_root / "packet-build-input.jsonl"
    planner_card_path = output_root / "run-cards/plan-packet-inputs.json"
    replay_kwargs = {
        "packet_build_input_path": packet_input_path,
        "selection_path": selection_path,
        "download_manifest_path": downloads_path,
        "parser_manifest_path": parser_path,
        "clearance_path": clearance_path,
        "prediction_units_path": units_path,
        "model_registry_path": registry_path,
        "raw_html_dir": raw_html_dir,
        "raw_artifacts_manifest_path": raw_artifacts_path,
        "document_root": document_root,
        "markdown_root": markdown_root,
        "materialization_run_card_path": materialization_card,
        "resolved_post_recovery_documents_path": None,
    }
    original_planner = cli.plan_packet_build_inputs
    for replay_mutation, target, expected in (
        ("raw", raw_html_path, "raw HTML tree changed during replay"),
        (
            "markdown",
            markdown_root / candidate_id / "complaint.md",
            "Markdown tree changed during replay",
        ),
    ):
        original_target = target.read_bytes()

        def mutate_during_replay(
            *, _target: Path = target, _kind: str = replay_mutation, **kwargs: Any
        ) -> Any:
            plan = original_planner(**kwargs)
            _target.write_bytes(f"mutated replay {_kind}".encode())
            return plan

        monkeypatch.setattr(cli, "plan_packet_build_inputs", mutate_during_replay)
        with pytest.raises(cli.CommandError, match=expected):
            cli._validate_packet_input_run_card(planner_card_path, **replay_kwargs)
        target.write_bytes(original_target)
    monkeypatch.setattr(cli, "plan_packet_build_inputs", original_planner)

    original_packet_input = packet_input_path.read_bytes()
    original_planner_card = planner_card_path.read_bytes()
    cross_candidate_input = _read_jsonl(packet_input_path)
    cross_candidate_input[0]["candidate_id"] = "attacker-rehashed"
    _write_jsonl(packet_input_path, cross_candidate_input)
    rehashed_planner_card = _read_json(planner_card_path)
    rehashed_planner_card["output_commitments"]["packet_build_input"]["sha256"] = (
        cli._path_sha256(packet_input_path)
    )
    _write_json(planner_card_path, rehashed_planner_card)
    with pytest.raises(cli.CommandError, match="packet planner replay mismatch"):
        cli._validate_packet_input_run_card(
            planner_card_path,
            packet_build_input_path=packet_input_path,
            selection_path=selection_path,
            download_manifest_path=downloads_path,
            parser_manifest_path=parser_path,
            clearance_path=clearance_path,
            prediction_units_path=units_path,
            model_registry_path=registry_path,
            raw_html_dir=raw_html_dir,
            raw_artifacts_manifest_path=raw_artifacts_path,
            document_root=document_root,
            markdown_root=output_root / "markdown",
            materialization_run_card_path=materialization_card,
            resolved_post_recovery_documents_path=None,
        )
    packet_input_path.write_bytes(original_packet_input)
    planner_card_path.write_bytes(original_planner_card)

    substituted_units_path = tmp_path / "substituted-units.jsonl"
    substituted_unit = _prediction_unit()
    substituted_unit.update(
        {
            "unit_id": "attacker-unit",
            "claim_name": "Substituted claim",
        }
    )
    [substituted_envelope] = apply_unitization_reviews(
        prediction_unit_records=[
            {
                "candidate_id": candidate_id,
                "case_id": "case-1",
                "prediction_units": [substituted_unit],
            }
        ],
        review_records=(),
        adjudication_records=(),
    )
    _write_jsonl(substituted_units_path, [substituted_envelope])
    substituted_root = tmp_path / "substituted-packet-plan"
    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(substituted_units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(markdown_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(substituted_root),
                "--generated-at",
                _GENERATED_AT,
                "--search-window",
                "2026-04-24..2026-05-18",
                "--execute",
            ]
        )
        == 0
    )
    substituted_input_path = substituted_root / "packet-build-input.jsonl"
    assert (
        _read_jsonl(substituted_input_path)[0]["prediction_units"][0]["unit_id"]
        == "attacker-unit"
    )
    with pytest.raises(
        cli.CommandError,
        match="packet run card prediction_units path mismatch",
    ):
        cli._validate_packet_input_run_card(
            substituted_root / "run-cards/plan-packet-inputs.json",
            packet_build_input_path=substituted_input_path,
            selection_path=selection_path,
            download_manifest_path=downloads_path,
            parser_manifest_path=parser_path,
            clearance_path=clearance_path,
            prediction_units_path=units_path,
            model_registry_path=registry_path,
            raw_html_dir=raw_html_dir,
            raw_artifacts_manifest_path=raw_artifacts_path,
            document_root=document_root,
            markdown_root=markdown_root,
            materialization_run_card_path=materialization_card,
            resolved_post_recovery_documents_path=None,
        )

    monkeypatch.setattr(
        cli,
        "_verify_packet_raw_artifacts_snapshot_binding",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_authenticated_materialization_snapshot_manifest_path",
        lambda *args, **kwargs: materialization_card,
    )
    monkeypatch.setattr(
        cli,
        "_verify_parser_packet_authority",
        lambda **kwargs: None,
    )

    def verify_stage_a_packet_authority(**kwargs: object) -> None:
        finalized = cast(list[JsonRecord], kwargs["finalized_prediction_unit_records"])
        if finalized[0]["prediction_units"][0]["unit_id"] != "count-i-issuer":
            raise cli.CommandError("substituted Stage A units")

    monkeypatch.setattr(
        cli,
        "_verify_stage_a_packet_authority",
        verify_stage_a_packet_authority,
    )
    packet_authority_args = [
        "--parser-run-card",
        str(materialization_card),
        "--parse-plan-run-card",
        str(materialization_card),
        "--raw-prediction-units",
        str(units_path),
        "--llm-unitization-audit",
        str(units_path),
        "--llm-unitize-run-card",
        str(units_path),
        "--llm-unitize-provider-journal",
        str(units_path),
        "--original-unitization-review-queue",
        str(units_path),
        "--stage-a-structural-flags",
        str(units_path),
        "--stage-a-structural-review-audit",
        str(units_path),
        "--stage-a-review-run-card",
        str(units_path),
        "--stage-a-review-provider-journal",
        str(units_path),
        "--stage-a-review-model-registry",
        str(registry_path),
        "--stage-a-review-model-key",
        "fixture:fixture-model",
        "--unitization-review-queue",
        str(units_path),
        "--unitization-review-adjudications",
        str(units_path),
        "--apply-unitization-review-run-card",
        str(units_path),
        "--expected-model-registry-sha256",
        hashlib.sha256(registry_path.read_bytes()).hexdigest(),
    ]

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(substituted_input_path),
                "--packet-input-run-card",
                str(substituted_root / "run-cards/plan-packet-inputs.json"),
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(substituted_units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(markdown_root),
                "--materialization-run-card",
                str(materialization_card),
                *packet_authority_args,
                "--output-root",
                str(substituted_root),
                "--execute",
            ]
        )
        == 2
    )

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(output_root / "packet-build-input.jsonl"),
                "--packet-input-run-card",
                str(output_root / "run-cards/plan-packet-inputs.json"),
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(output_root / "markdown"),
                "--materialization-run-card",
                str(materialization_card),
                *packet_authority_args,
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    packet = _read_jsonl(output_root / "packets.jsonl")[0]
    assert packet["decision_date"] == "2026-05-18"
    assert packet["metadata"]["nature_of_suit"] == "Civil Rights"
    assert packet["metadata"]["nos_macro_category"] == "civil_rights"
    assert packet["related_family_id"] == "related-fixture"
    assert packet["mdl_family_id"] == "mdl-fixture"
    assert f"{candidate_id}-decision" in packet["excluded_document_ids"]
    assert packet["prediction_units"][0]["unit_id"] == "count-i-issuer"
    assert "raw_artifact_provenance" not in packet

    original_validator = cli._validate_packet_input_run_card
    original_packet_input_bytes = packet_input_path.read_bytes()

    def validate_then_swap_input(*args: Any, **kwargs: Any) -> cli._PacketPlannerReplay:
        replay = original_validator(*args, **kwargs)
        swapped = _read_jsonl(packet_input_path)
        swapped[0]["candidate_id"] = "attacker-path-swap"
        _write_jsonl(packet_input_path, swapped)
        return replay

    monkeypatch.setattr(
        cli,
        "_validate_packet_input_run_card",
        validate_then_swap_input,
    )
    race_output_root = tmp_path / "race-build"
    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_input_path),
                "--packet-input-run-card",
                str(planner_card_path),
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(markdown_root),
                "--materialization-run-card",
                str(materialization_card),
                *packet_authority_args,
                "--output-root",
                str(race_output_root),
                "--execute",
            ]
        )
        == 0
    )
    assert _read_jsonl(race_output_root / "packets.jsonl")[0]["candidate_id"] == (
        candidate_id
    )
    packet_input_path.write_bytes(original_packet_input_bytes)
    monkeypatch.setattr(
        cli,
        "_validate_packet_input_run_card",
        original_validator,
    )

    build_card_path = output_root / "run-cards/build-packets.json"
    packets_path = output_root / "packets.jsonl"
    rehashed_packets = _read_jsonl(packets_path)
    rehashed_packets[0]["candidate_id"] = "attacker-rehashed"
    _write_jsonl(packets_path, rehashed_packets)
    rehashed_build_card = _read_json(build_card_path)
    rehashed_build_card["output_commitments"]["packets"]["sha256"] = cli._path_sha256(
        packets_path
    )
    _write_json(build_card_path, rehashed_build_card)
    with pytest.raises(cli.CommandError, match="packet build replay mismatch"):
        cli._validate_packet_build_run_card(
            build_card_path,
            packet_input_run_card_path=planner_card_path,
            packet_build_input_path=packet_input_path,
            packet_build_records=_read_jsonl(packet_input_path),
            packets_path=packets_path,
            selection_path=selection_path,
            download_manifest_path=downloads_path,
            clearance_path=clearance_path,
            document_root=document_root,
            materialization_run_card_path=materialization_card,
            expected_model_registry_sha256=hashlib.sha256(
                registry_path.read_bytes()
            ).hexdigest(),
        )

    mismatched_raw_artifact = _read_jsonl(raw_artifacts_path)[0]
    mismatched_raw_artifact["candidate_id"] = "different-candidate"
    _write_jsonl(raw_artifacts_path, [mismatched_raw_artifact])
    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--generated-at",
                _GENERATED_AT,
                "--execute",
            ]
        )
        == 2
    )


def test_plan_packet_inputs_requires_model_registry(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(tmp_path / "selection.jsonl"),
                "--download-manifest",
                str(tmp_path / "downloads.jsonl"),
                "--parser-manifest",
                str(tmp_path / "parser.jsonl"),
                "--prediction-units",
                str(tmp_path / "units.jsonl"),
                "--raw-html-dir",
                str(tmp_path / "raw-html"),
                "--output-root",
                str(tmp_path / "out"),
                "--execute",
            ]
        )

    assert exc_info.value.code == 2
    assert "--model-registry" in capsys.readouterr().err


def test_plan_packet_inputs_execute_requires_materialization_run_card_first(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(tmp_path / "selection.jsonl"),
                "--download-manifest",
                str(tmp_path / "downloads.jsonl"),
                "--parser-manifest",
                str(tmp_path / "parser.jsonl"),
                "--disclosure-clearance",
                str(tmp_path / "clearance.jsonl"),
                "--prediction-units",
                str(tmp_path / "units.jsonl"),
                "--model-registry",
                str(tmp_path / "registry.json"),
                "--raw-html-dir",
                str(tmp_path / "raw-html"),
                "--output-root",
                str(tmp_path / "out"),
                "--execute",
            ]
        )
        == 2
    )
    assert "--materialization-run-card" in capsys.readouterr().err


def test_plan_packet_inputs_keeps_selected_mtd_memo_with_notice_target(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    raw_html_path = raw_html_dir / "cand-1.html"
    raw_html_path.write_text(
        _packet_input_docket_html(),
        encoding="utf-8",
    )
    raw_artifacts_path = _write_raw_artifact_manifest(raw_html_path)
    selection = _packet_selection_record()
    selection["target_motion_entry_numbers"] = [33]
    selection_path = tmp_path / "selection.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    clearance_path = tmp_path / "clearance.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "units.jsonl"
    registry_path = _write_model_registry(tmp_path)
    markdown_root = output_root / "markdown"
    for source_document_id, markdown in {
        "complaint": "Complaint markdown",
        "mtd-memo": "MTD markdown",
        "decision": "Decision markdown",
    }.items():
        markdown_path = markdown_root / "cand-1" / f"{source_document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
    _write_jsonl(selection_path, [selection])
    _write_jsonl(
        downloads_path,
        [
            _download_record("complaint", "complaint", 1),
            _download_record("mtd-memo", "motion_to_dismiss_memorandum", 34),
            _download_record("decision", "decision", 50),
        ],
    )
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint"),
            _parser_record("mtd-memo"),
            _parser_record("decision"),
        ],
    )
    _write_clearance(downloads_path, clearance_path)
    _write_jsonl(
        units_path,
        [_finalized_prediction_unit_record()],
    )
    document_root, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch, tmp_path
    )
    verify_materialized_lineage = cli._verify_materialized_downstream_lineage
    materialization_verifications: list[object] = []

    def count_materialization_verification(
        **kwargs: object,
    ) -> cli._VerifiedMaterializedDownstreamLineage:
        materialization_verifications.append(kwargs)
        return verify_materialized_lineage(**kwargs)

    monkeypatch.setattr(
        cli,
        "_verify_materialized_downstream_lineage",
        count_materialization_verification,
    )

    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--generated-at",
                _GENERATED_AT,
                "--search-window",
                "2026-04-24..2026-05-18",
                "--execute",
            ]
        )
        == 0
    )
    assert len(materialization_verifications) == 1

    packet_input = _read_jsonl(output_root / "packet-build-input.jsonl")[0]
    assert packet_input["target_docket_entry_numbers"] == [33, 34]
    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(output_root / "packet-build-input.jsonl"),
                "--packet-input-run-card",
                str(output_root / "run-cards/plan-packet-inputs.json"),
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(output_root / "markdown"),
                "--materialization-run-card",
                str(materialization_card),
                *_packet_authority_args(
                    parser_run_card=materialization_card,
                    stage_a_artifact=units_path,
                    registry_path=registry_path,
                ),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    packet = _read_jsonl(output_root / "packets.jsonl")[0]
    assert [document["source_document_id"] for document in packet["documents"]] == [
        "cand-1:controlled-docket",
        "cand-1-complaint",
        "cand-1-mtd-memo",
    ]
    assert len(materialization_verifications) == 2


def test_materialization_lineage_stability_rejects_post_verification_changes(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b"original")
    document_root = tmp_path / "documents"
    document_root.mkdir()
    document = document_root / "document.md"
    document.write_bytes(b"document")
    ledger = (tmp_path / "purchases.sqlite3").resolve()
    verified = cli._VerifiedMaterializedDownstreamLineage(
        paths=(artifact,),
        artifact_bytes={str(artifact.resolve()): b"original"},
        manifest_records=(),
        clearance_records=(),
        selection_records=(),
        resolved_records=(),
        document_tree={"document.md": b"document"},
        fresh_ledger_namespace=ledger,
    )

    artifact.write_bytes(b"replacement")
    with pytest.raises(cli.CommandError, match="artifact changed during execution"):
        cli._require_materialized_downstream_lineage_unchanged(
            verified,
            document_root=document_root,
        )

    artifact.write_bytes(b"original")
    (document_root / "added.md").write_bytes(b"added")
    with pytest.raises(
        cli.CommandError, match="document tree changed during execution"
    ):
        cli._require_materialized_downstream_lineage_unchanged(
            verified,
            document_root=document_root,
        )

    (document_root / "added.md").unlink()
    ledger.write_bytes(b"initialized")
    with pytest.raises(cli.CommandError, match="absent fresh ledger namespace"):
        cli._require_materialized_downstream_lineage_unchanged(
            verified,
            document_root=document_root,
        )


def test_plan_packet_inputs_excludes_adversarial_leakage_docket_entries(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    raw_html_dir = tmp_path / "raw_html"
    raw_html_dir.mkdir()
    raw_html_path = raw_html_dir / "cand-1.html"
    raw_html_path.write_text(
        _adversarial_packet_input_docket_html(),
        encoding="utf-8",
    )
    raw_artifacts_path = _write_raw_artifact_manifest(raw_html_path)
    selection_path = tmp_path / "selection.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    clearance_path = tmp_path / "clearance.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "units.jsonl"
    registry_path = _write_model_registry(
        tmp_path,
        release_timestamp="2026-01-01T09:00:00Z",
    )
    markdown_root = output_root / "markdown"
    for source_document_id, markdown in {
        "complaint": "Complaint markdown",
        "mtd-memo": "MTD markdown",
        "opposition": (
            "Press report: the motion to dismiss survives as to the core claim."
        ),
        "decision": "Decision markdown",
    }.items():
        markdown_path = markdown_root / "cand-1" / f"{source_document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
    selection = _packet_selection_record()
    cast(list[JsonRecord], selection["documents"]).append(
        {
            "candidate_id": "cand-1",
            "source_document_id": "opposition",
            "docket_entry_number": 34,
            "document_role": "opposition",
            "source_url": "https://storage.courtlistener.com/opposition.pdf",
            "description": "Opposition",
            "model_visible": True,
            "contains_target_outcome": False,
            "redaction_or_seal_status": "public",
            "restriction_evidence": ["fixture_public_download_verified"],
        }
    )
    _write_jsonl(selection_path, [selection])
    _write_jsonl(
        downloads_path,
        [
            _download_record("complaint", "complaint", 1),
            _download_record("mtd-memo", "motion_to_dismiss_memorandum", 34),
            _download_record("opposition", "opposition", 34),
            _download_record("decision", "decision", 50),
        ],
    )
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint"),
            _parser_record("mtd-memo"),
            _parser_record("opposition"),
            _parser_record("decision"),
        ],
    )
    _write_clearance(downloads_path, clearance_path)
    _write_jsonl(
        units_path,
        [_finalized_prediction_unit_record()],
    )
    document_root, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch, tmp_path
    )

    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--document-root",
                str(document_root),
                "--materialization-run-card",
                str(materialization_card),
                "--output-root",
                str(output_root),
                "--generated-at",
                _GENERATED_AT,
                "--search-window",
                "2026-04-24..2026-05-18",
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "packet-build-input.jsonl") == []
    ledger = _read_jsonl(output_root / "exclusion-ledger.jsonl")
    assert len(ledger) == 1
    assert {record["primary_exclusion_reason"] for record in ledger} == {
        "outcome_leakage"
    }
    secondary_reasons = {
        reason
        for record in ledger
        for reason in cast(list[str], record["secondary_exclusion_reasons"])
    }
    assert {
        "minute_order_resolving_target",
        "rr_already_resolving_target",
        "tentative_ruling_revealing_target",
        "public_reporting_revealing_target",
    }.issubset(secondary_reasons)
    assert ledger[0]["source_document_ids"] == ["cand-1-opposition"]
    assert {
        "entry-20",
        "entry-21",
        "entry-22",
    }.issubset(set(cast(list[str], ledger[0]["source_entry_ids"])))
    candidate_manifest = _read_jsonl(output_root / "candidate-manifest.jsonl")[0]
    assert candidate_manifest["exclusion_ledger_entries"] == ledger


def test_build_packets_rejects_mounted_outcome_leakage(
    tmp_path: Path,
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    packet_input = tmp_path / "packet-input.jsonl"
    _write_jsonl(
        packet_input,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "court": "S.D.N.Y.",
                "docket_number": "1:26-cv-1",
                "generated_at": _GENERATED_AT,
                "docket_markdown": {
                    "model_visible_markdown": "# Model docket",
                    "audit_markdown": "# Audit docket",
                },
                "documents": [
                    _provenance("complaint", "complaint", 1),
                    _provenance("mtd-memo", "motion_to_dismiss_memorandum", 34),
                    {
                        **_provenance("decision", "decision", 50),
                        "contains_target_outcome": True,
                    },
                ],
                "parsed_documents": [
                    {
                        "source_document_id": "complaint",
                        "markdown": "Complaint markdown",
                    },
                    {"source_document_id": "mtd-memo", "markdown": "MTD markdown"},
                    {
                        "source_document_id": "decision",
                        "markdown": "Decision grants the motion",
                    },
                ],
                "prediction_units": [_prediction_unit()],
            }
        ],
    )
    document_root, materialization_card = _materialized_cli_unit_fixture(
        monkeypatch, tmp_path, skip_packet_planner_replay=True
    )
    selection = tmp_path / "selection.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    clearance = tmp_path / "clearance.jsonl"
    registry_path = _write_model_registry(tmp_path)
    _write_jsonl(selection, [{"candidate_id": "cand-1"}])
    _write_jsonl(manifest, [{"candidate_id": "cand-1"}])
    _write_jsonl(clearance, [{"candidate_id": "cand-1", "status": "cleared"}])
    planner_card = tmp_path / "packet-planner.json"
    _write_packet_planner_card(
        planner_card,
        packet_input=packet_input,
        selection=selection,
        manifest=manifest,
        clearance=clearance,
        document_root=document_root,
        materialization_run_card=materialization_card,
    )

    assert (
        main(
            [
                "acquisition",
                "build-packets",
                "--input",
                str(packet_input),
                "--packet-input-run-card",
                str(planner_card),
                "--selection",
                str(selection),
                "--download-manifest",
                str(manifest),
                "--parser-manifest",
                str(selection),
                "--disclosure-clearance",
                str(clearance),
                "--prediction-units",
                str(selection),
                "--model-registry",
                str(registry_path),
                "--raw-html-dir",
                str(document_root),
                "--raw-artifacts-manifest",
                str(selection),
                "--document-root",
                str(document_root),
                "--markdown-root",
                str(document_root),
                "--materialization-run-card",
                str(materialization_card),
                *_packet_authority_args(
                    parser_run_card=materialization_card,
                    stage_a_artifact=selection,
                    registry_path=registry_path,
                ),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert "must not expose target outcomes" in capsys.readouterr().err
    assert not (output_root / "packets.jsonl").exists()


def test_packet_planner_card_rejects_cross_materialization_substitution(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.jsonl"
    alternate_selection = tmp_path / "alternate-selection.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    clearance = tmp_path / "clearance.jsonl"
    materialization_card = tmp_path / "materialization.json"
    packet_input = tmp_path / "packet-input.jsonl"
    document_root = tmp_path / "documents"
    document_root.mkdir()
    (document_root / "document.pdf").write_bytes(b"%PDF authenticated")
    _write_jsonl(selection, [{"candidate_id": "case-a"}])
    _write_jsonl(alternate_selection, [{"candidate_id": "case-b"}])
    _write_jsonl(manifest, [{"candidate_id": "case-a"}])
    _write_jsonl(clearance, [{"candidate_id": "case-a", "status": "cleared"}])
    _write_json(materialization_card, {"stage": "materialize-cohort-documents"})
    _write_jsonl(packet_input, [{"candidate_id": "case-a"}])
    planner_card = tmp_path / "packet-planner.json"
    _write_json(
        planner_card,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "plan-packet-inputs",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "authenticated_materialization_lineage": (
                cli._packet_materialization_lineage_commitments(
                    selection_path=selection,
                    download_manifest_path=manifest,
                    clearance_path=clearance,
                    document_root=document_root,
                    materialization_run_card_path=materialization_card,
                )
            ),
            "output_commitments": {
                "packet_build_input": {
                    "path": str(packet_input.resolve()),
                    "sha256": "sha256:"
                    + hashlib.sha256(packet_input.read_bytes()).hexdigest(),
                }
            },
        },
    )

    with pytest.raises(
        cli.CommandError,
        match="lacks deterministic replay data",
    ):
        cli._validate_packet_input_run_card(
            planner_card,
            packet_build_input_path=packet_input,
            selection_path=selection,
            download_manifest_path=manifest,
            parser_manifest_path=manifest,
            clearance_path=clearance,
            prediction_units_path=manifest,
            model_registry_path=materialization_card,
            raw_html_dir=document_root,
            raw_artifacts_manifest_path=manifest,
            document_root=document_root,
            markdown_root=document_root,
            materialization_run_card_path=materialization_card,
            resolved_post_recovery_documents_path=None,
        )
    with pytest.raises(
        cli.CommandError,
        match="belongs to different materialized inputs",
    ):
        cli._validate_packet_input_run_card(
            planner_card,
            packet_build_input_path=packet_input,
            selection_path=alternate_selection,
            download_manifest_path=manifest,
            parser_manifest_path=manifest,
            clearance_path=clearance,
            prediction_units_path=manifest,
            model_registry_path=materialization_card,
            raw_html_dir=document_root,
            raw_artifacts_manifest_path=manifest,
            document_root=document_root,
            markdown_root=document_root,
            materialization_run_card_path=materialization_card,
            resolved_post_recovery_documents_path=None,
        )
    hardlinked_planner_card = tmp_path / "hardlinked-packet-planner.json"
    hardlinked_planner_card.hardlink_to(planner_card)
    with pytest.raises(cli.CommandError, match="must not be hardlinked"):
        cli._validate_packet_input_run_card(
            hardlinked_planner_card,
            packet_build_input_path=packet_input,
            selection_path=selection,
            download_manifest_path=manifest,
            parser_manifest_path=manifest,
            clearance_path=clearance,
            prediction_units_path=manifest,
            model_registry_path=materialization_card,
            raw_html_dir=document_root,
            raw_artifacts_manifest_path=manifest,
            document_root=document_root,
            markdown_root=document_root,
            materialization_run_card_path=materialization_card,
            resolved_post_recovery_documents_path=None,
        )


def test_packet_build_card_rejects_hand_authored_output_commitments(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    clearance = tmp_path / "clearance.jsonl"
    materialization_card = tmp_path / "materialization.json"
    planner_card = tmp_path / "packet-planner.json"
    packet_input = tmp_path / "packet-input.jsonl"
    packets = tmp_path / "packets.jsonl"
    document_root = tmp_path / "documents"
    document_root.mkdir()
    (document_root / "document.pdf").write_bytes(b"%PDF authenticated")
    for path in (selection, manifest, clearance, packet_input, packets):
        _write_jsonl(path, [{"candidate_id": "case-a"}])
    _write_json(materialization_card, {"stage": "materialize-cohort-documents"})
    lineage = cli._packet_materialization_lineage_commitments(
        selection_path=selection,
        download_manifest_path=manifest,
        clearance_path=clearance,
        document_root=document_root,
        materialization_run_card_path=materialization_card,
    )
    _write_json(planner_card, {"stage": "plan-packet-inputs"})
    build_card = tmp_path / "packet-build.json"
    _write_json(
        build_card,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "build-packets",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "authenticated_materialization_lineage": lineage,
            "expected_model_registry_sha256": "sha256:" + "a" * 64,
            "source_commitments": {
                "packet_input_run_card": {
                    "path": str(planner_card.resolve()),
                    "sha256": "sha256:"
                    + hashlib.sha256(planner_card.read_bytes()).hexdigest(),
                },
                "packet_build_input": {
                    "path": str(packet_input.resolve()),
                    "sha256": "sha256:"
                    + hashlib.sha256(packet_input.read_bytes()).hexdigest(),
                },
            },
            "output_commitments": {
                "packets": {
                    "path": str(packets.resolve()),
                    "sha256": "sha256:"
                    + hashlib.sha256(packets.read_bytes()).hexdigest(),
                }
            },
        },
    )
    kwargs = {
        "packet_input_run_card_path": planner_card,
        "packet_build_input_path": packet_input,
        "packet_build_records": _read_jsonl(packet_input),
        "packets_path": packets,
        "selection_path": selection,
        "download_manifest_path": manifest,
        "clearance_path": clearance,
        "document_root": document_root,
        "materialization_run_card_path": materialization_card,
        "expected_model_registry_sha256": "a" * 64,
    }
    with pytest.raises(
        cli.CommandError,
        match="different frozen registry digest",
    ):
        cli._validate_packet_build_run_card(
            build_card,
            **{**kwargs, "expected_model_registry_sha256": "b" * 64},
        )
    with pytest.raises(
        cli.CommandError,
        match="lacks deterministic parameters",
    ):
        cli._validate_packet_build_run_card(build_card, **kwargs)
    hardlinked_build_card = tmp_path / "hardlinked-packet-build.json"
    hardlinked_build_card.hardlink_to(build_card)
    with pytest.raises(cli.CommandError, match="must not be hardlinked"):
        cli._validate_packet_build_run_card(hardlinked_build_card, **kwargs)


def test_packet_replay_rejects_parent_symlinks_and_hardlinked_files(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    source = real_root / "source.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    alias_root = tmp_path / "alias"
    alias_root.symlink_to(real_root, target_is_directory=True)
    alias_source = alias_root / source.name
    alias_commitments = {
        "source": {
            "path": str(alias_source),
            "sha256": cli._path_sha256(source),
        }
    }
    with pytest.raises(cli.CommandError, match="parent is a symlink"):
        cli._packet_card_committed_snapshot(alias_commitments, name="source")

    hardlink = tmp_path / "hardlinked.jsonl"
    hardlink.hardlink_to(source)
    hardlink_commitments = {
        "source": {
            "path": str(hardlink),
            "sha256": cli._path_sha256(hardlink),
        }
    }
    with pytest.raises(cli.CommandError, match="singly linked regular"):
        cli._packet_card_committed_snapshot(hardlink_commitments, name="source")
    with pytest.raises(cli.CommandError, match="must not be hardlinked"):
        cli._verify_parser_packet_authority(
            parse_plan_run_card_path=hardlink,
            parser_run_card_path=hardlink,
            parser_manifest_path=source,
            parser_records=({},),
            parser_manifest_sha256=cli._path_sha256(source),
            parser_record_count=1,
            selection_path=source,
            selection_records=({},),
            download_manifest_path=source,
            download_records=({},),
            clearance_path=source,
            clearance_records=({},),
            clearance_sha256=cli._path_sha256(source),
            materialization_run_card_path=source,
            document_root=real_root,
            markdown_root=real_root,
        )


def test_packet_materialization_commitments_require_complete_snapshot(
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    clearance = tmp_path / "clearance.jsonl"
    card = tmp_path / "card.json"
    document_root = tmp_path / "documents"
    document_root.mkdir()
    for path in (selection, manifest, clearance, card):
        path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(cli.CommandError, match="snapshot is missing"):
        cli._packet_materialization_lineage_commitments(
            selection_path=selection,
            download_manifest_path=manifest,
            clearance_path=clearance,
            document_root=document_root,
            materialization_run_card_path=card,
            captured_artifact_bytes={str(selection.resolve()): selection.read_bytes()},
            document_tree_snapshot={},
        )


def test_merge_artifacts_prefers_packet_buildable_inputs(tmp_path: Path) -> None:
    base = tmp_path / "base"
    recovered = tmp_path / "recovered"
    output_root = tmp_path / "merged"
    _write_merge_root(base, case_id="case-1", unit_id="unit-1")
    _write_jsonl(
        base / "public-packet-selection.jsonl",
        [{"case_id": "case-1"}, {"case_id": "failed-case"}],
    )
    _write_jsonl(
        base / "public-packet-selection-packet-buildable-labeled.jsonl",
        [{"case_id": "case-1"}],
    )
    _write_jsonl(base / "labels-packet-buildable.jsonl", [{"unit_id": "unit-1"}])
    _write_jsonl(
        base / "prediction-units-packet-buildable-labeled.jsonl",
        [{"case_id": "case-1", "prediction_units": [{"unit_id": "unit-1"}]}],
    )
    _write_merge_root(recovered, case_id="case-2", unit_id="unit-2")
    _write_jsonl(recovered / "labels.jsonl", [{"unit_id": "unit-2"}])
    _write_jsonl(
        recovered / "prediction-units.jsonl",
        [{"case_id": "case-2", "prediction_units": [{"unit_id": "unit-2"}]}],
    )

    assert (
        main(
            [
                "acquisition",
                "merge-artifacts",
                "--source-root",
                str(base),
                "--source-root",
                str(recovered),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    assert [
        record["case_id"] for record in _read_jsonl(output_root / "packets.jsonl")
    ] == ["case-1", "case-2"]
    assert [
        record["unit_id"] for record in _read_jsonl(output_root / "labels.jsonl")
    ] == ["unit-1", "unit-2"]
    assert [
        record["case_id"]
        for record in _read_jsonl(output_root / "public-packet-selection.jsonl")
    ] == ["case-1", "case-2"]
    assert (output_root / "documents" / "free" / "case-1" / "doc-1.pdf").exists()
    assert (output_root / "documents" / "free" / "case-2" / "doc-2.pdf").exists()
    summary = _read_json(output_root / "merge-artifacts-summary.json")
    assert summary["record_counts"]["packets.jsonl"] == 2
    assert summary["record_counts"]["prediction-units.jsonl"] == 2


def _write_execute_budget_plan(tmp_path: Path, output_root: Path) -> Path:
    core_results = tmp_path / "core-filter-results.jsonl"
    _write_jsonl(core_results, [_core_filter_result()])
    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    return output_root / "missing-core-budget-plan.json"


def _write_recap_fetch_inputs(tmp_path: Path, output_root: Path) -> tuple[Path, Path]:
    core_results = tmp_path / "recap-core-filter-results.jsonl"
    result = _core_filter_result()
    result["purchase_document_ids"] = ["123"]
    result["core_mtd_documents"] = ["123"]
    result["model_visible_document_ids"] = ["complaint", "123"]
    result["core_missing_documents"] = ["123"]
    _write_jsonl(core_results, [result])
    assert (
        main(
            [
                "acquisition",
                "plan",
                "--core-filter-results",
                str(core_results),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    selection_path = tmp_path / "recap-selection.jsonl"
    selection = _packet_selection_record()
    selection["documents"] = [
        {
            "candidate_id": "cand-1",
            "source_document_id": "123",
            "docket_entry_number": 34,
            "document_role": "motion_to_dismiss_memorandum",
            "source_url": None,
            "description": "Memorandum",
            "model_visible": True,
            "contains_target_outcome": False,
            "redaction_or_seal_status": "public",
            "is_sealed": False,
            "is_private": False,
        }
    ]
    _write_jsonl(selection_path, [selection])
    return output_root / "missing-core-budget-plan.json", selection_path


def _write_approved_recap_fetch_inputs(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> tuple[Path, Path, ApprovedPurchaseFixture]:
    """Build current v2 authority over one real completed projection."""

    completed = build_completed_projection_fixture(
        tmp_path / "completed-projection",
        monkeypatch=monkeypatch,
    )
    approval = build_approved_purchase_fixture(
        tmp_path / "purchase-v2-authority", target_cohort_root=completed.root
    )
    _initialize_purchase_ledger(
        tmp_path,
        policy_path=approval.policy,
        ledger_path=approval.ledger,
        cohort_path=approval.cohort_policy,
        controlled_private_root=approval.controlled_private_root,
        initialization_receipt=approval.initialization_receipt,
    )
    return (
        completed.budget_plan,
        completed.selection,
        approval,
    )


def _approved_runtime_args(approval: ApprovedPurchaseFixture) -> list[str]:
    return [
        "--controlled-private-root",
        str(approval.controlled_private_root),
        "--purchase-ledger-initialization-receipt",
        str(approval.initialization_receipt),
    ]


def _write_purchase_policy(tmp_path: Path) -> tuple[Path, Path, Path]:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    policy_path = tmp_path / "purchase-policy.json"
    cohort_path = tmp_path / "cohort-policy.json"
    decisions = cli._fixture_cohort_policy_decisions()
    decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "2250.00",
        "max_per_case_usd": "73.20",
        "reservation_headroom_required": True,
    }
    cohort = cli.generate_cohort_policy(decisions)
    _write_json(cohort_path, cohort)
    _write_json(
        policy_path,
        generate_case_dev_purchase_policy(
            {
                "cycle_id": "cycle-1",
                "cohort_policy_sha256": cohort["policy_sha256"],
                "canonical_ledger_path": str(ledger),
                "hard_cap_usd": "2250.00",
                "opening_committed_spend_usd": "0.00",
                "opening_case_committed_spend_usd": {},
                "max_per_case_usd": "73.20",
                "per_document_reservation_usd": "3.05",
                "fee_schedule": {
                    "source_citation": "case.dev pricing docs",
                    "verified_at_utc": "2026-07-13T00:00:00Z",
                    "includes_pacer_fees": True,
                    "includes_service_fees": True,
                    "includes_rounding": True,
                },
            }
        ),
    )
    return policy_path, ledger, cohort_path


def _initialize_purchase_ledger(
    tmp_path: Path,
    *,
    policy_path: Path,
    ledger_path: Path,
    cohort_path: Path,
    controlled_private_root: Path | None = None,
    initialization_receipt: Path | None = None,
) -> None:
    authority_args = (
        [
            "--controlled-private-root",
            str(controlled_private_root),
            "--initialization-receipt-output",
            str(initialization_receipt),
        ]
        if controlled_private_root is not None and initialization_receipt is not None
        else []
    )
    assert (
        main(
            [
                "acquisition",
                "init-purchase-ledger",
                "--purchase-policy",
                str(policy_path),
                "--cohort-policy",
                str(cohort_path),
                "--purchase-ledger",
                str(ledger_path),
                *authority_args,
                "--output-root",
                str(tmp_path / "ledger-initialization"),
                "--execute",
            ]
        )
        == 0
    )


class _BrokerTransport:
    def __init__(self, *responses: recap_broker.BrokerRawResponse) -> None:
        self.responses = list(responses)
        self.requests: list[tuple[str, str, bytes, dict[str, str]]] = []

    def request(
        self,
        *,
        method: str,
        url: str,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> recap_broker.BrokerRawResponse:
        del timeout_seconds
        self.requests.append((method, url, body, dict(headers)))
        return self.responses.pop(0)


def _recap_fetch_broker_env() -> dict[str, str]:
    key = ec.derive_private_key(7, ec.SECP256R1())
    numbers = key.private_numbers()
    public = numbers.public_numbers

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    private_jwk = json.dumps(
        {
            "kty": "EC",
            "crv": "P-256",
            "x": encode(public.x.to_bytes(32, "big")),
            "y": encode(public.y.to_bytes(32, "big")),
            "d": encode(numbers.private_value.to_bytes(32, "big")),
        },
        separators=(",", ":"),
    )
    public_jwk = json.dumps(
        {
            "crv": "P-256",
            "kty": "EC",
            "x": encode(public.x.to_bytes(32, "big")),
            "y": encode(public.y.to_bytes(32, "big")),
        },
        separators=(",", ":"),
    )
    identity_policy = json.dumps(
        {
            "version": "recap-fetch-identity-policy-v1",
            "machine_id": "fixture-machine",
            "public_key_sha256": hashlib.sha256(public_jwk.encode()).hexdigest(),
            "tailscale_node_id": "fixture-node",
            "allowed_source_ips": ["192.0.2.1"],
            "activated_at": "2026-07-14T12:00:00.000Z",
            "expires_at": "2026-07-15T12:00:00.000Z",
        },
        separators=(",", ":"),
    )
    return {
        "RECAP_FETCH_BROKER_URL": ("https://secure-gate-recap-fetch.johnjhughes.com"),
        "RECAP_FETCH_BROKER_MACHINE_ID": "fixture-machine",
        "RECAP_FETCH_BROKER_PRIVATE_KEY_JWK": private_jwk,
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON": identity_policy,
        "RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256": hashlib.sha256(
            identity_policy.encode()
        ).hexdigest(),
    }


def _write_merge_root(root: Path, *, case_id: str, unit_id: str) -> None:
    document_id = f"doc-{case_id[-1]}"
    document_path = root / "documents" / "free" / case_id / f"{document_id}.pdf"
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_bytes(f"{case_id} pdf".encode())
    markdown_path = root / "markdown" / case_id / f"{document_id}.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(f"# {case_id}\n", encoding="utf-8")
    packet = {
        "case_id": case_id,
        "candidate_id": case_id,
        "ablation": "full_packet",
        "prediction_units": [{"unit_id": unit_id}],
    }
    _write_jsonl(root / "packets.jsonl", [packet])
    _write_jsonl(root / "case-packets.jsonl", [packet])
    _write_jsonl(root / "candidate-manifest.jsonl", [{"case_id": case_id}])
    _write_jsonl(
        root / "document-manifest.jsonl",
        [
            {
                "source_document_id": document_id,
                "path": str(document_path.relative_to(root)),
            }
        ],
    )
    _write_jsonl(root / "extracted_texts.jsonl", [{"source_document_id": document_id}])
    _write_jsonl(
        root / "mistral-markdown-conversions.jsonl",
        [{"source_document_id": document_id, "markdown_path": str(markdown_path)}],
    )
    _write_jsonl(root / "packet-build-input.jsonl", [{"case_id": case_id}])
    _write_jsonl(root / "public-packet-selection.jsonl", [{"case_id": case_id}])
    _write_jsonl(
        root / "prediction-units.jsonl",
        [{"case_id": case_id, "prediction_units": [{"unit_id": unit_id}]}],
    )


def _core_filter_result() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "purchase_document_ids": ["mtd-memo"],
        "core_mtd_documents": ["mtd-memo"],
        "core_exhibit_documents": [],
        "model_visible_document_ids": ["complaint", "mtd-memo"],
        "operative_complaint_document_id": "complaint",
        "operative_complaint_documents": ["complaint"],
        "audit_only_document_ids": [],
        "core_missing_documents": ["mtd-memo"],
        "exclusion_reasons": [],
    }


def _packet_selection_record(candidate_id: str = "cand-1") -> JsonRecord:
    return {
        "candidate_id": candidate_id,
        "case_id": "case-1",
        "case_name": "Example v. Defendant",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "decision_date": "2026-05-18",
        "source_url": f"https://www.courtlistener.com/docket/{candidate_id}/example/",
        "selected": True,
        "exclusion_reasons": [],
        "target_motion_entry_numbers": [34],
        "decision_entry_numbers": [50],
        "documents": [
            {
                "candidate_id": candidate_id,
                "source_document_id": "complaint",
                "docket_entry_number": 1,
                "document_role": "complaint",
                "source_url": "https://storage.courtlistener.com/complaint.pdf",
                "description": "Complaint",
                "model_visible": True,
                "contains_target_outcome": False,
                "redaction_or_seal_status": "public",
                "restriction_evidence": ["fixture_public_download_verified"],
            },
            {
                "candidate_id": candidate_id,
                "source_document_id": "mtd-memo",
                "docket_entry_number": 34,
                "document_role": "motion_to_dismiss_memorandum",
                "source_url": "https://storage.courtlistener.com/mtd.pdf",
                "description": "Memorandum",
                "model_visible": True,
                "contains_target_outcome": False,
                "redaction_or_seal_status": "public",
                "restriction_evidence": ["fixture_public_download_verified"],
            },
            {
                "candidate_id": candidate_id,
                "source_document_id": "decision",
                "docket_entry_number": 50,
                "document_role": "decision",
                "source_url": "https://storage.courtlistener.com/decision.pdf",
                "description": "Decision",
                "model_visible": False,
                "contains_target_outcome": True,
                "redaction_or_seal_status": "public",
                "restriction_evidence": ["fixture_public_download_verified"],
            },
        ],
    }


def _write_model_registry(
    tmp_path: Path,
    *,
    release_timestamp: str = "2026-05-05T09:00:00Z",
) -> Path:
    registry_path = tmp_path / "model-registry.json"
    records: list[JsonRecord] = [
        {
            "provider": "fixture",
            "model_id": "fixture-model",
            "display_name": "Fixture Model",
            "model_version_or_snapshot": "fixture-model-2026-05-05",
            "release_timestamp": release_timestamp,
            "release_timestamp_source": "fixture test registry",
            "provider_training_cutoff_status": "known",
            "provider_training_cutoff": "2026-04-01",
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 4096,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "controlled_docket_tool_only",
            "context_limit": 200000,
            "pricing_source": "fixture",
            "input_token_price": 0.25,
            "output_token_price": 1.0,
            "known_cutoff_publicity_caveats": [],
        }
    ]
    _write_json(registry_path, records)
    return registry_path


def _packet_authority_args(
    *,
    parser_run_card: Path,
    stage_a_artifact: Path,
    registry_path: Path,
) -> list[str]:
    return [
        "--parser-run-card",
        str(parser_run_card),
        "--parse-plan-run-card",
        str(parser_run_card),
        "--raw-prediction-units",
        str(stage_a_artifact),
        "--llm-unitization-audit",
        str(stage_a_artifact),
        "--llm-unitize-run-card",
        str(stage_a_artifact),
        "--llm-unitize-provider-journal",
        str(stage_a_artifact),
        "--original-unitization-review-queue",
        str(stage_a_artifact),
        "--stage-a-structural-flags",
        str(stage_a_artifact),
        "--stage-a-structural-review-audit",
        str(stage_a_artifact),
        "--stage-a-review-run-card",
        str(stage_a_artifact),
        "--stage-a-review-provider-journal",
        str(stage_a_artifact),
        "--stage-a-review-model-registry",
        str(registry_path),
        "--stage-a-review-model-key",
        "fixture:fixture-model",
        "--unitization-review-queue",
        str(stage_a_artifact),
        "--unitization-review-adjudications",
        str(stage_a_artifact),
        "--apply-unitization-review-run-card",
        str(stage_a_artifact),
        "--expected-model-registry-sha256",
        hashlib.sha256(registry_path.read_bytes()).hexdigest(),
    ]


def _download_record(
    source_document_id: str,
    role: str,
    docket_entry_number: int,
    *,
    candidate_id: str = "cand-1",
) -> JsonRecord:
    return {
        "candidate_id": candidate_id,
        "source_provider": "courtlistener",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "source_url": f"https://storage.courtlistener.com/{source_document_id}.pdf",
        "local_path": f"{candidate_id}/courtlistener/{source_document_id}.pdf",
        "sha256": hashlib.sha256(source_document_id.encode()).hexdigest(),
        "byte_count": 10,
        "free_or_purchased": "free",
        "retry_count": 0,
        "rate_limited": False,
        "reused_existing": False,
    }


def _parser_record(
    source_document_id: str,
    *,
    candidate_id: str = "cand-1",
) -> JsonRecord:
    markdown_path = f"{candidate_id}/{source_document_id}.md"
    markdown = {
        "complaint": "Complaint markdown",
        "mtd-memo": "MTD markdown",
        "opposition": (
            "Press report: the motion to dismiss survives as to the core claim."
        ),
        "decision": "Decision markdown",
    }[source_document_id]
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "status": "succeeded",
        "input_path": f"/tmp/{source_document_id}.pdf",
        "markdown_path": markdown_path,
        "metadata_path": f"{markdown_path}.metadata.json",
        "parser_config": {"engine": "fixture"},
        "quality_flags": [],
        "source_sha256": hashlib.sha256(source_document_id.encode()).hexdigest(),
        "source_byte_count": 10,
        "extracted_text": {
            "source_document_id": source_document_id,
            "extracted_at": _GENERATED_AT,
            "extraction_method": "fixture_markdown",
            "text_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "quality_flags": [],
        },
    }


def _packet_input_docket_html() -> str:
    return """
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
          <div class="row odd" id="entry-50">
            <div class="col-xs-1"><p>50</p></div>
            <div class="col-xs-3"><p>May 8, 2026</p></div>
            <div class="col-xs-8"><p>ORDER granting 34 Motion to Dismiss.</p></div>
          </div>
        </div>
      </body>
    </html>
    """


def _adversarial_packet_input_docket_html() -> str:
    return """
    <html>
      <body>
        <div id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1"><p>1</p></div>
            <div class="col-xs-3"><p>Jan 1, 2026</p></div>
            <div class="col-xs-8"><p>COMPLAINT filed by Plaintiff.</p></div>
          </div>
          <div class="row even" id="entry-20">
            <div class="col-xs-1"><p>20</p></div>
            <div class="col-xs-3"><p>March 1, 2026</p></div>
            <div class="col-xs-8">
              <p>Minute order granting the motion to dismiss after hearing.</p>
            </div>
          </div>
          <div class="row odd" id="entry-21">
            <div class="col-xs-1"><p>21</p></div>
            <div class="col-xs-3"><p>March 2, 2026</p></div>
            <div class="col-xs-8">
              <p>
                Report and recommendation recommends granting the motion to dismiss.
              </p>
            </div>
          </div>
          <div class="row even" id="entry-22">
            <div class="col-xs-1"><p>22</p></div>
            <div class="col-xs-3"><p>March 3, 2026</p></div>
            <div class="col-xs-8"><p>Tentative ruling granting the MTD.</p></div>
          </div>
          <div class="row odd" id="entry-34">
            <div class="col-xs-1"><p>34</p></div>
            <div class="col-xs-3"><p>Apr 1, 2026</p></div>
            <div class="col-xs-8"><p>MOTION to Dismiss.</p></div>
          </div>
          <div class="row even" id="entry-50">
            <div class="col-xs-1"><p>50</p></div>
            <div class="col-xs-3"><p>May 8, 2026</p></div>
            <div class="col-xs-8"><p>ORDER on Motion to Dismiss.</p></div>
          </div>
        </div>
      </body>
    </html>
    """


def _provenance(document_id: str, role: str, docket_entry_number: int) -> JsonRecord:
    return {
        "source_provider": "fixture",
        "source_case_id": "case-1",
        "source_document_id": document_id,
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "document_role": role,
        "retrieved_at": _GENERATED_AT,
        "source_url_or_reference": f"fixture://{document_id}",
        "sha256": hashlib.sha256(f"{document_id} source".encode()).hexdigest(),
        "is_predecision_material": True,
        "is_mounted_for_model": True,
        "availability_status": "available",
        "docket_entry_number": docket_entry_number,
        "contains_target_outcome": False,
        "packet_section": "filings",
    }


def _prediction_unit() -> JsonRecord:
    return {
        "unit_id": "count-i-issuer",
        "count": "I",
        "claim_name": "Section 10(b)",
        "defendant_group": "Issuer",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.95,
        "source_citations": [{"document_id": "complaint", "page": 1}],
    }


def _finalized_prediction_unit_record(
    candidate_id: str = "cand-1",
) -> JsonRecord:
    [record] = apply_unitization_reviews(
        prediction_unit_records=[
            {
                "candidate_id": candidate_id,
                "case_id": "case-1",
                "prediction_units": [_prediction_unit()],
            }
        ],
        review_records=(),
        adjudication_records=(),
    )
    return record


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, record: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _write_raw_artifact_manifest(
    raw_html_path: Path,
    *,
    candidate_id: str = "cand-1",
) -> Path:
    payload = raw_html_path.read_bytes()
    manifest_path = raw_html_path.parent / "raw-artifacts.jsonl"
    _write_jsonl(
        manifest_path,
        [
            {
                "candidate_id": candidate_id,
                "path": str(raw_html_path),
                "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        ],
    )
    return manifest_path


def _write_clearance(manifest_path: Path, output_path: Path) -> None:
    _write_jsonl(
        output_path,
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
            for row in _read_jsonl(manifest_path)
        ],
    )


def _read_json(path: Path) -> JsonRecord:
    return cast(JsonRecord, json.loads(path.read_text(encoding="utf-8")))


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [
        cast(JsonRecord, json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


_V2_REPLAY_ROOT_NAMES = (
    "predecessor_root",
    "complete_materialization_root",
    "stipulated_evidence_root",
    "final153_snapshot",
    "wider_plan_root",
    "wider_exclusion_root",
    "historical_packet_root",
)
_V2_TERMINAL_CANDIDATE_ID = "69736298"


def _rename_v2_terminal(value: Any) -> Any:
    if isinstance(value, str):
        return {
            "s000": _V2_TERMINAL_CANDIDATE_ID,
            "s000-decision": f"{_V2_TERMINAL_CANDIDATE_ID}-decision",
        }.get(value, value)
    if isinstance(value, dict):
        return {key: _rename_v2_terminal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rename_v2_terminal(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_rename_v2_terminal(item) for item in value)
    return value


def _v2_authenticated_replay(
    roots: Mapping[str, Path],
) -> tuple[successor_v2_cli.V2InputReplay, Any, Any]:
    """Provide one sealed replay whose terminal case has the production identity."""

    inputs = _v2_fixture()
    base = inputs["base"]
    renamed_base = _mint_verified_exact100_v2_base(
        predecessor_projection_bytes=base.predecessor_projection_bytes,
        selection_rows=cast(list[JsonRecord], _rename_v2_terminal(base.selection)),
        case_relevance_rows=cast(
            list[JsonRecord], _rename_v2_terminal(base.case_relevance)
        ),
        download_manifest_rows=cast(
            list[JsonRecord], _rename_v2_terminal(base.download_manifest)
        ),
        disclosure_rows=cast(
            list[JsonRecord], _rename_v2_terminal(base.disclosure_clearance)
        ),
        restriction_rows=cast(
            list[JsonRecord], _rename_v2_terminal(base.restriction_evidence)
        ),
        core_filter_rows=cast(
            list[JsonRecord], _rename_v2_terminal(base.core_filter_results)
        ),
        source_commitments=base.source_commitments,
    )
    terminal = verify_post_selection_terminal_exclusions(
        selection_bytes=renamed_base.selection_bytes,
        evidence=(
            _mint_terminal_evidence(
                candidate_id=_V2_TERMINAL_CANDIDATE_ID,
                source_document_id=f"{_V2_TERMINAL_CANDIDATE_ID}-decision",
                reason=TerminalExclusionReason.STIPULATED_INELIGIBLE,
                evidence_kind="test_authenticated_v2_terminal_replay",
                evidence_commitments={
                    "selection": "sha256:"
                    + hashlib.sha256(renamed_base.selection_bytes).hexdigest()
                },
            ),
        ),
    )
    expected_roots = tuple(roots[name].absolute() for name in _V2_REPLAY_ROOT_NAMES)

    def replay(args: argparse.Namespace) -> tuple[Any, Any, Any, Any]:
        actual_roots = tuple(
            cast(Path, getattr(args, name)).absolute() for name in _V2_REPLAY_ROOT_NAMES
        )
        if actual_roots != expected_roots:
            raise successor_v2_cli.Exact100SuccessorReplacementV2CliError(
                "authenticated v2 input roots differ"
            )
        return renamed_base, terminal, inputs["repairs"], inputs["wider"]

    return replay, renamed_base, inputs["wider"]


def _run_v2_successor_cli(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> tuple[Path, successor_v2_cli.V2InputReplay, Any, Any]:
    roots = {name: tmp_path / name.replace("_", "-") for name in _V2_REPLAY_ROOT_NAMES}
    replay, base, wider = _v2_authenticated_replay(roots)
    monkeypatch.setattr(cli, "_replay_exact100_successor_replacement_v2_inputs", replay)
    output_root = tmp_path / "exact100-successor-v2"
    command = ["acquisition", "project-exact100-successor-replacement-v2"]
    for name in _V2_REPLAY_ROOT_NAMES:
        command.extend((f"--{name.replace('_', '-')}", str(roots[name])))
    command.extend(("--output-root", str(output_root)))

    assert main(command) == 0
    return output_root, replay, base, wider


def test_exact100_successor_v2_cli_mints_specialized_materializer_authority(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    output_root, _replay, base, wider = _run_v2_successor_cli(tmp_path, monkeypatch)

    projection = cli._verify_materializer_projection(
        target_root=output_root,
        free_clearance_path=output_root / "disclosure-clearance.jsonl",
        preparation_summary_path=tmp_path / "unused-preparation-summary.json",
        preparation_config_path=tmp_path / "unused-preparation-config.json",
        snapshot_manifest_path=tmp_path / "unused-snapshot-manifest.json",
        expected_target_count=100,
    )
    verified = cli._verified_successor_selection_card_from_projection(projection)
    assert verified is not None and verified.is_replay_minted()

    final_ids = {
        cast(str, row["candidate_id"])
        for row in _read_jsonl(output_root / "target-cohort-selection.jsonl")
    }
    predecessor_ids = {cast(str, row["candidate_id"]) for row in base.selection}
    assert predecessor_ids - final_ids == {_V2_TERMINAL_CANDIDATE_ID}
    assert final_ids - predecessor_ids == {wider.selected_candidate_id}

    state = _read_json(output_root / "run-cards/project-target-cohort.json")
    assert state["terminal_candidate_ids"] == [_V2_TERMINAL_CANDIDATE_ID]
    assert state["promoted_candidate_ids"] == [wider.selected_candidate_id]
    for field in (
        "provider_activity_requested",
        "provider_activity_executed",
        "courtlistener_activity_requested",
        "courtlistener_activity_executed",
        "pacer_activity_requested",
        "pacer_activity_executed",
        "recap_fetch_activity_requested",
        "recap_fetch_activity_executed",
        "paid_activity_requested",
        "paid_activity_executed",
        "model_activity_requested",
        "model_activity_executed",
        "evaluation_authorized",
        "freeze_authorized",
        "dispatch_authorized",
    ):
        assert state[field] is False
    assert not any("network" in field for field in state)


def test_exact100_successor_v2_rejects_generic_unattested_projection(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    output_root, replay, _base, _wider = _run_v2_successor_cli(tmp_path, monkeypatch)
    run_card = _read_json(output_root / "run-cards/project-target-cohort.json")
    projection = cli.verify_exact100_successor_replacement_v2_projection(
        output_root,
        replay=replay,
        args=cli._exact100_successor_v2_replay_args(run_card),
    )

    with pytest.raises(
        cli.CommandError,
        match="requires specialized replay attestation",
    ):
        cli._mint_verified_successor_selection_card_from_projection(projection)


def test_exact100_successor_v2_rejects_persisted_input_path_tampering(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    output_root, _replay, _base, _wider = _run_v2_successor_cli(tmp_path, monkeypatch)
    state_path = output_root / "run-cards/project-target-cohort.json"
    state = _read_json(state_path)
    state["input_paths"][0] = str(tmp_path / "forged-predecessor")
    state_path.write_bytes(
        canonical_json_bytes(
            state,
            error_type=ValueError,
            error_message="test state serialization failed",
        )
    )

    with pytest.raises(cli.CommandError, match="authenticated v2 input roots differ"):
        cli.verify_completed_target_cohort_projection_for_purchase_approval(output_root)


def test_exact100_successor_v2_rejects_persisted_state_tampering(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    output_root, _replay, _base, _wider = _run_v2_successor_cli(tmp_path, monkeypatch)
    state_path = output_root / "run-cards/project-target-cohort.json"
    state = _read_json(state_path)
    state["dispatch_authorized"] = True
    state_path.write_bytes(
        canonical_json_bytes(
            state,
            error_type=ValueError,
            error_message="test state serialization failed",
        )
    )

    with pytest.raises(
        cli.CommandError,
        match="completed v2 successor run card differs from replay",
    ):
        cli.verify_completed_target_cohort_projection_for_purchase_approval(output_root)


def test_build_unitizer_terminal_review_bundle_is_provider_free_and_deterministic(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    markdown_root = tmp_path / "markdown"
    document_root = tmp_path / "documents"
    markdown_root.mkdir()
    document_root.mkdir()
    complaint = b"Complaint text\n"
    opposition = b"Opposition text\n"
    (markdown_root / "complaint.md").write_bytes(complaint)
    (markdown_root / "opposition.md").write_bytes(opposition)
    selection_records = (
        {
            "candidate_id": "candidate-b",
            "case_id": "case-b",
            "documents": [
                {
                    "source_document_id": "complaint-b",
                    "document_role": "complaint",
                    "docket_entry_number": 1,
                    "description": "Complaint B",
                    "model_visible": True,
                    "contains_target_outcome": False,
                }
            ],
        },
        {
            "candidate_id": "candidate-a",
            "case_id": "case-a",
            "documents": [
                {
                    "source_document_id": "opposition-a",
                    "document_role": "opposition",
                    "docket_entry_number": 9,
                    "description": "Opposition A",
                    "model_visible": True,
                    "contains_target_outcome": False,
                }
            ],
        },
    )
    parser_records = (
        {
            "candidate_id": "candidate-b",
            "source_document_id": "complaint-b",
            "markdown_path": "complaint.md",
        },
        {
            "candidate_id": "candidate-a",
            "source_document_id": "opposition-a",
            "markdown_path": "opposition.md",
        },
    )
    lineage = SimpleNamespace(
        selection_records=selection_records,
        parser_records=parser_records,
        markdown_root=markdown_root,
        document_root=document_root,
        markdown_bytes={
            "complaint.md": complaint,
            "opposition.md": opposition,
        },
        input_paths=(),
        input_commitments={"selection": {"sha256": "a" * 64}},
        markdown_tree={
            "complaint.md": hashlib.sha256(complaint).hexdigest(),
            "opposition.md": hashlib.sha256(opposition).hexdigest(),
        },
        file_snapshots={},
        document_tree={},
    )
    monkeypatch.setattr(
        cli, "_verify_verified_stage_a_parse_lineage", lambda *args, **kwargs: lineage
    )
    monkeypatch.setattr(
        cli, "_require_stage_a_parse_lineage_unchanged", lambda _lineage: None
    )

    def receipt(
        candidate: str, case: str, source: dict[str, Any], text: bytes
    ) -> JsonRecord:
        prompt = f"unitize {candidate}"
        return {
            "schema_version": (
                "legalforecast.llm_stage_a_unitizer_terminal_escalation.v1"
            ),
            "candidate_id": candidate,
            "case_id": case,
            "unitizer_model_key": "anthropic:unitizer",
            "model_registry_sha256": "b" * 64,
            "provider_attempt_namespace": "claim-ontology-v5",
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "predecision_source_commitments": [
                {
                    "source_document_id": source["source_document_id"],
                    "document_role": source["document_role"],
                    "docket_entry_number": source["docket_entry_number"],
                    "description": source["description"],
                    "markdown_sha256": "sha256:" + hashlib.sha256(text).hexdigest(),
                }
            ],
            "failed_attempts": [
                {
                    "attempt_ordinal": ordinal,
                    "raw_response_sha256": "sha256:" + format(ordinal, "064x"),
                    "normalized_response_sha256": (
                        "sha256:" + format(ordinal + 10, "064x")
                    ),
                    "failure_type": "LlmResponseValidationError",
                    "failure_message": "invalid citation selector",
                }
                for ordinal in (1, 2, 3)
            ],
        }

    receipt_b = tmp_path / "receipt-b.json"
    receipt_a = tmp_path / "receipt-a.json"
    receipt_b.write_text(
        json.dumps(
            receipt(
                "candidate-b", "case-b", selection_records[0]["documents"][0], complaint
            )
        )
        + "\n",
        encoding="utf-8",
    )
    receipt_a.write_text(
        json.dumps(
            receipt(
                "candidate-a",
                "case-a",
                selection_records[1]["documents"][0],
                opposition,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    lineage_inputs = {
        name: tmp_path / name
        for name in (
            "selection",
            "selection-card",
            "download-manifest",
            "clearance",
            "materialization-card",
            "parse-requests",
            "parser-manifest",
            "parser-card",
        )
    }
    for path in lineage_inputs.values():
        path.write_text("{}\n", encoding="utf-8")
    output_root = tmp_path / "terminal-review"
    argv = [
        "acquisition",
        "build-unitizer-terminal-review-bundle",
        "--output-root",
        str(output_root),
        "--selection",
        str(lineage_inputs["selection"]),
        "--selection-run-card",
        str(lineage_inputs["selection-card"]),
        "--download-manifest",
        str(lineage_inputs["download-manifest"]),
        "--disclosure-clearance",
        str(lineage_inputs["clearance"]),
        "--materialization-run-card",
        str(lineage_inputs["materialization-card"]),
        "--document-root",
        str(document_root),
        "--parse-requests",
        str(lineage_inputs["parse-requests"]),
        "--parser-manifest",
        str(lineage_inputs["parser-manifest"]),
        "--parser-run-card",
        str(lineage_inputs["parser-card"]),
        "--markdown-root",
        str(markdown_root),
        "--terminal-receipt",
        str(receipt_b),
        "--terminal-receipt",
        str(receipt_a),
        "--execute",
    ]
    assert main(argv) == 0
    receipts = _read_jsonl(output_root / "unitizer-terminal-receipts.jsonl")
    queue = _read_jsonl(output_root / "unitizer-terminal-review-queue.jsonl")
    bundles = _read_jsonl(output_root / "unitizer-terminal-review-bundle.jsonl")
    assert [row["candidate_id"] for row in receipts] == [
        "candidate-a",
        "candidate-b",
    ]
    assert [row["candidate_id"] for row in queue] == [
        "candidate-a",
        "candidate-b",
    ]
    assert bundles[0]["cited_predecision_markdown"][0]["markdown"] == (
        "Opposition text\n"
    )
    card = _read_json(
        output_root / "run-cards" / "build-unitizer-terminal-review-bundle.json"
    )
    assert card["paid_activity_executed"] is False
    assert card["provider_activity_executed"] is False
    assert card["evaluation_authorized"] is False
    assert card["record_count"] == 2


def test_build_unitizer_terminal_review_bundle_requires_closed_lineage_arguments(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "acquisition",
                "build-unitizer-terminal-review-bundle",
                "--terminal-receipt",
                str(receipt),
            ]
        )


def test_build_successor_attorney_packet_cli_calls_v2_builder_with_exact_bytes(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    inputs = [tmp_path / f"input-{index}.jsonl" for index in range(5)]
    payloads = [f'{{"input":{index}}}\n'.encode() for index in range(5)]
    for path, payload in zip(inputs, payloads, strict=True):
        path.write_bytes(payload)
    calls: list[tuple[bytes, ...]] = []

    def build(*values: bytes) -> SimpleNamespace:
        calls.append(values)
        return SimpleNamespace(
            manifest={
                "schema_version": (
                    "legalforecast.successor_attorney_packet_manifest.v2"
                ),
                "unitizer_terminal_candidate_count": 1,
            },
            attorney_view={
                "schema_version": "legalforecast.successor_attorney_packet_view.v2",
                "candidates": [{"candidate_id": "candidate-terminal"}],
            },
        )

    monkeypatch.setattr(
        cli, "build_successor_attorney_packet_with_unitizer_terminals", build
    )
    output_root = tmp_path / "packet"
    argv = [
        "acquisition",
        "build-successor-attorney-packet",
        "--output-root",
        str(output_root),
        "--unitization-review-bundle",
        str(inputs[0]),
        "--unitization-review-queue-v2",
        str(inputs[1]),
        "--unitizer-terminal-receipts",
        str(inputs[2]),
        "--unitizer-terminal-review-queue",
        str(inputs[3]),
        "--unitizer-terminal-review-bundle",
        str(inputs[4]),
        "--execute",
    ]
    assert main(argv) == 0
    assert calls == [tuple(payloads)]
    manifest = _read_json(output_root / "successor-attorney-packet-manifest.json")
    attorney_view = _read_json(output_root / "successor-attorney-review.json")
    assert manifest["schema_version"] == (
        "legalforecast.successor_attorney_packet_manifest.v2"
    )
    assert attorney_view["candidates"] == [{"candidate_id": "candidate-terminal"}]
    card = _read_json(
        output_root / "run-cards" / "build-successor-attorney-packet.json"
    )
    assert card["record_count"] == 1
    assert card["paid_activity_executed"] is False
    assert card["provider_activity_executed"] is False
    assert card["creates_adjudications"] is False
    assert card["evaluation_authorized"] is False


def test_convert_attorney_worksheet_cli_authenticates_packet_and_writes_outputs(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    packet = tmp_path / "successor-attorney-review.json"
    manifest = tmp_path / "successor-attorney-packet-manifest.json"
    packet_card = tmp_path / "build-successor-attorney-packet.json"
    worksheet = tmp_path / "attorney-decision-worksheet.tsv"
    packet.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.successor_attorney_packet_view.v2",
                "candidates": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": (
                    "legalforecast.successor_attorney_packet_manifest.v2"
                ),
                "review_id_coverage": {"exactly_once": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    worksheet.write_text("surface\n", encoding="utf-8")
    packet_card.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "stage": "build-successor-attorney-packet",
                "status": "completed",
                "dry_run": False,
                "output_commitments": {
                    "attorney_view": {
                        "sha256": "sha256:"
                        + hashlib.sha256(packet.read_bytes()).hexdigest()
                    },
                    "packet_manifest": {
                        "sha256": "sha256:"
                        + hashlib.sha256(manifest.read_bytes()).hexdigest()
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "convert_attorney_worksheet",
        lambda **_kwargs: SimpleNamespace(
            ordinary_adjudications=({"candidate_id": "ordinary"},),
            terminal_adjudications=({"candidate_id": "terminal"},),
        ),
    )
    output_root = tmp_path / "converted"

    assert (
        main(
            [
                "acquisition",
                "convert-unitization-adjudication-worksheet",
                "--output-root",
                str(output_root),
                "--attorney-packet",
                str(packet),
                "--packet-manifest",
                str(manifest),
                "--packet-run-card",
                str(packet_card),
                "--worksheet",
                str(worksheet),
                "--adjudicator-id",
                "attorney-1",
                "--execute",
            ]
        )
        == 0
    )
    assert _read_jsonl(output_root / "ordinary-unitization-adjudications.jsonl") == [
        {"candidate_id": "ordinary"}
    ]
    assert _read_jsonl(output_root / "terminal-unitizer-adjudications.jsonl") == [
        {"candidate_id": "terminal"}
    ]
    card = _read_json(
        output_root / "run-cards" / "convert-unitization-adjudication-worksheet.json"
    )
    assert card["provider_activity_executed"] is False
    assert card["retrieval_activity_executed"] is False
    assert card["creates_adjudications"] is True
    assert card["evaluation_authorized"] is False
    assert card["freeze_authorized"] is False
    assert card["dispatch_authorized"] is False


def _completeness_fixture_pdf(pages: tuple[tuple[str, ...], ...]) -> bytes:
    from io import BytesIO

    from reportlab.pdfgen.canvas import Canvas

    output = BytesIO()
    canvas = Canvas(output)
    for lines in pages:
        offset = 720
        for line in lines:
            canvas.drawString(72, offset, line)
            offset -= 14
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def test_live_mistral_reuse_repairs_a_dropped_page_without_a_provider_call(
    tmp_path: Path,
) -> None:
    """A conversion that dropped a page is superseded and repaired locally.

    This is the whole point of the pairing: the completeness gate turns a row
    that passes every density threshold into a gap, and the gap is filled from
    the PDF's own embedded text layer rather than by re-running the parser,
    which would spend a provider call to reproduce the same defect.
    """

    body = (
        "UNITED STATES DISTRICT COURT",
        "SOUTHERN DISTRICT OF EXAMPLE",
        "MOTION TO DISMISS UNDER RULES 12(b)(5) AND 12(b)(6)",
        "COMES NOW Defendant Example Corporation, by counsel, and moves this",
        "Court to dismiss the First Amended Complaint because it fails to state",
        "a claim upon which relief can be granted under the governing standard.",
        "WHEREFORE Defendant respectfully requests dismissal with prejudice and",
        "such further relief as the Court deems just and proper in the premises.",
    )
    page_two = (
        "SIGNED this day by counsel of record for the moving defendant, whose",
        "name, bar number, address, telephone and electronic mail address are",
        "set out below in the manner required by the local rules of this Court.",
    )
    source_bytes = _completeness_fixture_pdf((body, page_two))
    digest = hashlib.sha256(source_bytes).hexdigest()
    # The frozen conversion kept only page 1's two centred header lines.  It is
    # dense enough to clear every parse-quality threshold for its role.
    gutted = (
        "##### Page 1\n\n# UNITED STATES DISTRICT COURT\n"
        "SOUTHERN DISTRICT OF EXAMPLE\n\n---\n\n"
        "##### Page 2\n\n" + "\n\n".join(page_two) + "\n\n---\n"
    )
    prior_root = tmp_path / "prior"
    markdown_path = prior_root / "cand" / "doc.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(gutted, encoding="utf-8")
    prior_request = {
        "candidate_id": "cand",
        "source_document_id": "doc",
        "input_path": "/old/doc.pdf",
        "expected_sha256": digest,
        "expected_byte_count": len(source_bytes),
    }
    prior_record = {
        "candidate_id": "cand",
        "source_document_id": "doc",
        "status": "succeeded",
        "input_path": "/old/doc.pdf",
        "markdown_path": "cand/doc.md",
        "metadata_path": "cand/doc.metadata.json",
        "parser_config": {
            "engine": "mistral",
            "parser_root": "/parser",
            "parser_revision": cli.EXPECTED_PARSER_REVISION,
            "expected_parser_revision": cli.EXPECTED_PARSER_REVISION,
            "timeout_seconds": 60,
            "debug": False,
            "command": [
                "uv",
                "run",
                "parser-pdf",
                "--file",
                "/old/doc.pdf",
                "--mistral",
                "--no-ocr",
            ],
        },
        "quality_flags": [],
        "extracted_text": {
            "source_document_id": "doc",
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": hashlib.sha256(gutted.encode()).hexdigest(),
            "quality_flags": [],
        },
        "source_sha256": digest,
        "source_byte_count": len(source_bytes),
        "stdout": "",
        "stderr": "",
        "error_message": None,
    }
    _write_json(markdown_path.with_suffix(".metadata.json"), prior_record)
    requests_path = tmp_path / "prior-requests.jsonl"
    manifest_path = tmp_path / "prior-manifest.jsonl"
    _write_jsonl(requests_path, [prior_request])
    _write_jsonl(manifest_path, [prior_record])
    card_path = tmp_path / "prior-card.json"
    _write_json(
        card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "parse-documents",
            "status": "completed",
            "dry_run": False,
            "execute": True,
            "record_count": 1,
            "source_commitments": {
                "requests": {
                    "path": str(requests_path),
                    "sha256": cli._bytes_sha256(requests_path.read_bytes()),
                }
            },
            "output_commitments": {
                "parser_manifest": {
                    "path": str(manifest_path),
                    "sha256": cli._bytes_sha256(manifest_path.read_bytes()),
                }
            },
            "parser_execution": {
                "mode": "live_mistral",
                "engine": "mistral",
                "parser_revision": cli.EXPECTED_PARSER_REVISION,
                "fixture_markdown": False,
            },
        },
    )
    output_root = tmp_path / "out"
    # The current run materialises the same authenticated bytes under its own
    # root, exactly as plan-parse-documents does.
    current_source = tmp_path / "materialized" / "doc.pdf"
    current_source.parent.mkdir(parents=True, exist_ok=True)
    current_source.write_bytes(source_bytes)
    request = cli.MistralMarkdownConversionRequest(
        "cand",
        "doc",
        current_source,
        output_root / "markdown" / "cand" / "doc.md",
        digest,
        len(source_bytes),
        source_bytes,
        "motion_to_dismiss_memorandum",
    )

    plan = cli._reuse_live_mistral_parse_outputs(
        prior_run_card_path=card_path,
        prior_markdown_root=prior_root,
        requests=(request,),
        output_root=output_root,
    )

    assert plan.records_by_key == {}
    assert plan.superseded_keys == frozenset(
        {("cand", "doc", digest, len(source_bytes))}
    )
    (gap,) = plan.gaps
    assert gap.embedded_text_layer_repair is not None
    assert gap.embedded_text_layer_repair.repaired_page_numbers == (1,)

    class _RefusingRunner:
        def run(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("a repaired gap must not start the parser")

    (record,) = cli.convert_documents_to_markdown(
        plan.gaps,
        runner=_RefusingRunner(),
        extracted_at=datetime(2026, 8, 19, tzinfo=UTC),
    )
    published = {
        ("cand", "doc", digest, len(source_bytes)): {
            **record.to_record(),
            "source_sha256": digest,
            "source_byte_count": len(source_bytes),
        }
    }

    cli._require_superseded_gap_parse_meets_current_role(
        superseded_keys=plan.superseded_keys,
        records_by_key=published,
        requests_by_key={("cand", "doc", digest, len(source_bytes)): gap},
    )

    repaired = request.markdown_output_path.read_text(encoding="utf-8")
    assert "MOTION TO DISMISS UNDER RULES 12(b)(5) AND 12(b)(6)" in repaired
    assert "COMES NOW Defendant Example Corporation" in repaired
    assert page_two[0] in repaired


def test_manifest_execution_decisions_cli_has_no_beads_observation_option(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "issue-manifest-execution-decisions-v2", "--help"])

    assert "--beads-observation" not in capsys.readouterr().out
