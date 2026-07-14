from __future__ import annotations

import copy
import json
from argparse import Namespace
from pathlib import Path
from typing import Any, cast

import legalforecast.cli as cli
import legalforecast.ingestion.courtlistener_case_dev_bridge as bridge_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import generate_case_dev_purchase_policy
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads


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
    assert "--live-courtlistener" in output
    assert "--courtlistener-fixture" in output
    assert "never invokes a PACER purchase endpoint" in normalized
    assert "Never invokes RECAP Fetch or PACER" in normalized
    assert "--case-relevance-output" in output
    assert "--public-selection" in output
    assert "--paid-gaps" in output
    assert "--free-download-manifest" in output
    assert "Run download-free" in output
    assert "--checkpoint-dir" in output
    assert "--checkpoint-config-output" in output
    assert "--request-ledger" in output
    assert "--courtlistener-rate-profile" in output
    assert "--request-budget-max-wait-seconds" in output
    assert "resume skips terminal candidates" in normalized


def test_live_courtlistener_bridge_reserves_every_physical_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    args = Namespace(
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
        request_budget_max_wait_seconds=0.0,
        courtlistener_rate_profile="base",
    )

    client, budget = cli._courtlistener_bridge_client(
        args, fixture_path=None, live=True
    )

    assert budget is not None
    assert client.before_request is not None
    client.before_request("GET", "/dockets/123/")
    assert budget.local_reservations == 1
    assert budget.total_reservations() == 1


def test_live_courtlistener_bridge_requires_durable_request_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    args = Namespace(
        request_ledger=None,
        request_budget_max_wait_seconds=0.0,
        courtlistener_rate_profile="base",
    )

    with pytest.raises(cli.CommandError, match="--request-ledger"):
        cli._courtlistener_bridge_client(args, fixture_path=None, live=True)


def test_bridge_pacer_gaps_dry_run_emits_complete_v2_summary(tmp_path: Path) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    _write_jsonl(screened_path, [])

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )

    assert _read_json(output_root / "pacer-gap-bridge-summary.json") == {
        "schema_version": "legalforecast.courtlistener_case_dev_bridge.v2",
        "dry_run": True,
        "screened_case_count": 0,
        "selected_case_count": 0,
        "excluded_case_count": 0,
        "free_download_request_count": 0,
        "paid_document_count": 0,
        "paid_recovery_required_document_count": 0,
        "paid_recovery_required_case_count": 0,
        "identity_resolved_paid_gap_case_count": 0,
        "document_bytes_ready_case_count": 0,
        "identity_policy": (
            "exact court+docket match with caption corroboration; "
            "case.dev document IDs only"
        ),
        "free_first_required": True,
        "public_first_reconciled": False,
    }


def test_public_first_bridge_checkpoints_429_and_resumes_without_repeat_lookups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    first = _screened_case()
    second = _screened_case_variant(
        candidate_id="cl-456",
        docket_number="1:26-cv-00002",
        case_name="Second v. Example",
    )
    plan = plan_public_packet_downloads(
        (first, second),
        use_embedded_entries=True,
        target_clean_cases=2,
    )
    assert len(plan.paid_gap_cases) == 2
    _write_jsonl(screened_path, [first, second])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record() for gap in plan.paid_gap_cases])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": (
                    f"{request.candidate_id}/courtlistener/"
                    f"{request.source_document_id}.pdf"
                ),
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    rate_limit = {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {"type": "search", "query": "1:26-cv-00001", "limit": 20},
        "status_code": 429,
        "payload": {"error": "slow down"},
    }
    second_docket = {
        **_case_dev_docket(),
        "id": "case-dev-888",
        "docketNumber": "1:26-cv-00002",
        "caseName": "Second v. Example",
    }
    _write_jsonl(
        fixture_path,
        [
            rate_limit,
            rate_limit,
            rate_limit,
            _response(
                params={
                    "type": "search",
                    "query": "1:26-cv-00002",
                    "limit": 20,
                },
                payload={"dockets": [second_docket]},
            ),
            _response(
                params={
                    "type": "lookup",
                    "docketId": "case-dev-888",
                    "includeEntries": True,
                    "limit": 100,
                },
                payload={
                    "docket": {
                        **second_docket,
                        "entries": [
                            _case_dev_entry(5, "Motion to Dismiss", "second-mtd")
                        ],
                    }
                },
            ),
        ],
    )
    monkeypatch.setenv("CASE_DEV_RATE_LIMIT_PER_MINUTE", "20")
    monkeypatch.setattr(
        "legalforecast.ingestion.case_dev_client.CaseDevClient._throttle_if_needed",
        lambda self: None,
    )
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--case-dev-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_selection_path),
        "--paid-gaps",
        str(paid_gaps_path),
        "--free-download-manifest",
        str(free_downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    assert main(command) == 2

    assert not (output_root / "public-packet-selection-reconciled.jsonl").exists()
    assert not (output_root / "pacer-gap-bridge-exclusions.jsonl").exists()
    checkpoint_records = sorted(
        (
            _read_json(path)
            for path in (output_root / "checkpoints" / "pacer-gap-bridge").glob(
                "*.json"
            )
        ),
        key=lambda record: cast(int, record["input_index"]),
    )
    assert [record["outcome"] for record in checkpoint_records] == [
        "retryable",
        "success",
    ]
    first_run_card = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert first_run_card["status"] == "failed"
    assert first_run_card["case_dev_request_count"] == 5
    assert first_run_card["case_dev_rate_limit_per_minute"] == 20
    assert first_run_card["case_dev_max_http_attempts_per_request"] == 3
    assert first_run_card["checkpoint_terminal_candidate_count"] == 1
    assert first_run_card["resumed_terminal_candidate_count"] == 0
    assert first_run_card["retryable_candidate_count"] == 1
    assert first_run_card["input_route_count"] == 2
    assert first_run_card["reconciled"] is False

    # Simulate the durable progress emitted before bridge summary v2. Resume
    # must preserve this terminal success without preserving its stale claim
    # that paid bytes were already recovered.
    checkpoint_dir = output_root / "checkpoints" / "pacer-gap-bridge"
    success_checkpoint_path = next(
        path
        for path in checkpoint_dir.glob("*.json")
        if _read_json(path)["outcome"] == "success"
    )
    success_checkpoint = _read_json(success_checkpoint_path)
    success_checkpoint["schema_version"] = (
        "legalforecast.pacer_gap_bridge_candidate_checkpoint.v1"
    )
    success_payload = cast(dict[str, object], success_checkpoint["payload"])
    success_selection = cast(dict[str, object], success_payload["selection_record"])
    success_selection["paid_recovery_required"] = False
    success_selection["planning_status"] = "selected_after_paid_recovery"
    success_selection.pop("identity_resolution_status")
    success_selection.pop("document_recovery_status")
    _write_json(success_checkpoint_path, success_checkpoint)
    config_path = output_root / "checkpoints" / "pacer-gap-bridge-progress-config.json"
    progress_config = _read_json(config_path)
    progress_config["schema_version"] = (
        "legalforecast.pacer_gap_bridge_progress_config.v1"
    )
    _write_json(config_path, progress_config)

    _write_jsonl(
        fixture_path,
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
                    "limit": 100,
                },
                payload={
                    "docket": {
                        **_case_dev_docket(),
                        "entries": [
                            _case_dev_entry(5, "Motion to Dismiss", "first-mtd")
                        ],
                    }
                },
            ),
        ],
    )

    assert main(command) == 0

    resumed_selections = _read_jsonl(
        output_root / "public-packet-selection-reconciled.jsonl"
    )
    assert {record["candidate_id"] for record in resumed_selections} == {
        "cl-123",
        "cl-456",
    }
    resumed_legacy = next(
        record for record in resumed_selections if record["candidate_id"] == "cl-456"
    )
    assert resumed_legacy["paid_recovery_required"] is True
    assert resumed_legacy["planning_status"] == (
        "identity_resolved_paid_recovery_required"
    )
    assert _read_jsonl(output_root / "pacer-gap-bridge-exclusions.jsonl") == []
    resumed_run_card = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert resumed_run_card["case_dev_request_count"] == 2
    assert resumed_run_card["resumed_terminal_candidate_count"] == 1
    assert resumed_run_card["checkpoint_terminal_candidate_count"] == 2
    assert resumed_run_card["retryable_candidate_count"] == 0
    assert resumed_run_card["reconciled"] is True


def test_public_first_bridge_bounds_resumable_5xx_as_terminal_exclusion(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": f"cl-123/{request.source_document_id}.pdf",
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    failure = {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {"type": "search", "query": "1:26-cv-00001", "limit": 20},
        "status_code": 503,
        "payload": {"error": "temporary upstream failure"},
    }
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--case-dev-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_selection_path),
        "--paid-gaps",
        str(paid_gaps_path),
        "--free-download-manifest",
        str(free_downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    for expected_exit in (2, 2, 0):
        _write_jsonl(fixture_path, [failure, failure, failure])
        assert main(command) == expected_exit

    [checkpoint_path] = list(
        (output_root / "checkpoints" / "pacer-gap-bridge").glob("*.json")
    )
    checkpoint = _read_json(checkpoint_path)
    assert checkpoint["outcome"] == "exclusion"
    assert checkpoint["resumable_attempt_count"] == 3
    assert checkpoint["cumulative_case_dev_request_count"] == 9
    [exclusion] = _read_jsonl(output_root / "pacer-gap-bridge-exclusions.jsonl")
    assert exclusion["candidate_id"] == "cl-123"
    assert exclusion["exclusion_reasons"] == ["case_dev_server_error_retries_exhausted"]
    run_card = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert run_card["status"] == "completed"
    assert run_card["cumulative_case_dev_request_count"] == 9
    assert run_card["retryable_candidate_count"] == 0
    assert run_card["reconciled"] is True


def test_public_first_bridge_rejects_shared_manifest_corruption_before_checkpoint(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    downloads = [
        {
            **request.to_record(),
            "local_path": f"cl-123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    ]
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(free_downloads_path, [*downloads, downloads[0]])
    _write_jsonl(fixture_path, [])

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--case-dev-fixture",
                str(fixture_path),
                "--public-selection",
                str(public_selection_path),
                "--paid-gaps",
                str(paid_gaps_path),
                "--free-download-manifest",
                str(free_downloads_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    assert not (
        output_root / "checkpoints" / "pacer-gap-bridge-progress-config.json"
    ).exists()
    assert not (output_root / "checkpoints" / "pacer-gap-bridge").exists()


@pytest.mark.parametrize("selected_entries", [None, {}, [], "not-a-list"])
def test_bridge_source_commitments_reject_invalid_embedded_entries(
    selected_entries: object,
) -> None:
    screened = _screened_case()
    if selected_entries is None:
        screened.pop("selected_entries")
    else:
        screened["selected_entries"] = selected_entries

    with pytest.raises(cli.CommandError, match="selected_entries"):
        cli._bridge_source_commitments(
            screened_records=[screened],
            routed_candidate_ids=["cl-123"],
            raw_html_dir=None,
            use_embedded_entries=True,
        )


def test_candidate_bridge_accepts_candidate_key_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    candidate = cast(dict[str, object], screened["candidate"])
    candidate.pop("docket_id")
    called = False

    def bridge_candidate(*args: object, **kwargs: object) -> object:
        nonlocal called
        called = True
        raise RuntimeError("identity matched")

    monkeypatch.setattr(bridge_module, "_bridge_candidate", bridge_candidate)

    with pytest.raises(RuntimeError, match="identity matched"):
        bridge_module.bridge_public_plan_paid_gap_candidate(
            screened,
            paid_gap_record=gap.to_record(),
            free_download_records=(),
            client=cast(Any, None),
            use_embedded_entries=True,
            validate_free_downloads=False,
        )
    assert called is True


@pytest.mark.parametrize("outcome", ["success", "exclusion"])
def test_bridge_checkpoint_payload_is_bound_to_candidate(outcome: str) -> None:
    payload: dict[str, object]
    if outcome == "success":
        payload = {
            "selection_record": {"candidate_id": "other"},
            "case_relevance_record": {"candidate_id": "cl-123"},
        }
    else:
        payload = {"exclusion_record": {"candidate_id": "other"}}
    checkpoint = {
        "schema_version": "legalforecast.pacer_gap_bridge_candidate_checkpoint.v2",
        "input_index": 0,
        "candidate_id": "cl-123",
        "candidate_input_sha256": "sha256:input",
        "outcome": outcome,
        "resumable_attempt_count": 1,
        "cumulative_case_dev_request_count": 0,
        "payload": payload,
    }

    with pytest.raises(cli.CommandError, match="invalid for cl-123"):
        cli._validate_bridge_checkpoint(
            checkpoint,
            input_index=0,
            candidate_id="cl-123",
            candidate_input_sha256="sha256:input",
        )


def _legacy_v1_terminal_success_checkpoint() -> dict[str, object]:
    paid_document = {
        "source_document_id": "case-dev-mtd",
        "availability_status": "unavailable",
        "requires_paid_recovery": True,
    }
    return {
        "schema_version": "legalforecast.pacer_gap_bridge_candidate_checkpoint.v1",
        "input_index": 0,
        "candidate_id": "cl-123",
        "candidate_input_sha256": "sha256:input",
        "outcome": "success",
        "resumable_attempt_count": 1,
        "cumulative_case_dev_request_count": 2,
        "payload": {
            "selection_record": {
                "candidate_id": "cl-123",
                "selected": True,
                "paid_recovery_required": False,
                "paid_gap_reasons": [],
                "resolved_paid_gap_reasons": ["no_free_target_mtd_document"],
                "planning_status": "selected_after_paid_recovery",
                "identity_resolution": {"matched_by": "exact"},
                "documents": [paid_document],
            },
            "case_relevance_record": {
                "candidate_id": "cl-123",
                "documents": [paid_document],
            },
        },
    }


def test_bridge_resume_normalizes_legacy_v1_terminal_success_checkpoint() -> None:
    checkpoint = _legacy_v1_terminal_success_checkpoint()

    cli._validate_bridge_checkpoint(
        checkpoint,
        input_index=0,
        candidate_id="cl-123",
        candidate_input_sha256="sha256:input",
    )
    normalized = cli._normalize_bridge_checkpoint(checkpoint)

    assert normalized["schema_version"] == (
        "legalforecast.pacer_gap_bridge_candidate_checkpoint.v2"
    )
    payload = cast(dict[str, object], normalized["payload"])
    selection = cast(dict[str, object], payload["selection_record"])
    assert selection["paid_recovery_required"] is True
    assert selection["planning_status"] == ("identity_resolved_paid_recovery_required")
    assert selection["identity_resolution_status"] == "resolved"
    assert selection["document_recovery_status"] == "paid_recovery_required"


def test_bridge_resume_rejects_v2_success_with_stale_recovery_status() -> None:
    normalized = cli._normalize_bridge_checkpoint(
        _legacy_v1_terminal_success_checkpoint()
    )
    payload = cast(dict[str, object], normalized["payload"])
    selection = cast(dict[str, object], payload["selection_record"])
    selection["paid_recovery_required"] = False

    with pytest.raises(cli.CommandError, match="v2 success checkpoint is ambiguous"):
        cli._normalize_bridge_checkpoint(normalized)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("hash_mismatch", "invalid for cl-123"),
        ("missing_documents", "malformed selection documents"),
        ("mismatched_pending_ids", "ambiguous for cl-123"),
    ],
)
def test_bridge_resume_fails_closed_on_unverifiable_legacy_v1_success(
    mutation: str,
    match: str,
) -> None:
    checkpoint = _legacy_v1_terminal_success_checkpoint()
    if mutation == "hash_mismatch":
        with pytest.raises(cli.CommandError, match=match):
            cli._validate_bridge_checkpoint(
                checkpoint,
                input_index=0,
                candidate_id="cl-123",
                candidate_input_sha256="sha256:different",
            )
        return
    payload = cast(dict[str, object], checkpoint["payload"])
    if mutation == "missing_documents":
        selection = cast(dict[str, object], payload["selection_record"])
        selection.pop("documents")
    else:
        relevance = cast(dict[str, object], payload["case_relevance_record"])
        relevance["documents"] = [
            {
                "source_document_id": "different-document",
                "availability_status": "unavailable",
                "requires_paid_recovery": True,
            }
        ]

    cli._validate_bridge_checkpoint(
        checkpoint,
        input_index=0,
        candidate_id="cl-123",
        candidate_input_sha256="sha256:input",
    )
    with pytest.raises(cli.CommandError, match=match):
        cli._normalize_bridge_checkpoint(checkpoint)


def test_bridge_resume_accepts_only_semantically_identical_v1_config() -> None:
    current = {
        "schema_version": "legalforecast.pacer_gap_bridge_progress_config.v2",
        "screened_cases_sha256": "sha256:screened",
        "paid_gap_count": 3,
    }
    legacy = {
        **current,
        "schema_version": "legalforecast.pacer_gap_bridge_progress_config.v1",
    }

    assert cli._bridge_progress_config_matches(legacy, current) is True
    assert (
        cli._bridge_progress_config_matches({**legacy, "paid_gap_count": 4}, current)
        is False
    )


def test_bridge_resume_rejects_unrecognized_checkpoint_schema() -> None:
    checkpoint = {
        "schema_version": "legalforecast.pacer_gap_bridge_candidate_checkpoint.v0",
        "input_index": 0,
        "candidate_id": "cl-123",
        "candidate_input_sha256": "sha256:input",
        "outcome": "success",
        "resumable_attempt_count": 1,
        "cumulative_case_dev_request_count": 2,
        "payload": {"reason": "retryable"},
    }

    with pytest.raises(cli.CommandError, match="invalid for cl-123"):
        cli._validate_bridge_checkpoint(
            checkpoint,
            input_index=0,
            candidate_id="cl-123",
            candidate_input_sha256="sha256:input",
        )


@pytest.mark.parametrize("alias_kind", ["direct", "symlink", "hardlink"])
def test_public_first_bridge_rejects_checkpoint_config_input_alias_before_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    alias_kind: str,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": f"cl-123/{request.source_document_id}.pdf",
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    _write_jsonl(fixture_path, [])
    checkpoint_config_path = screened_path
    if alias_kind != "direct":
        checkpoint_config_path = tmp_path / f"config-{alias_kind}.json"
        if alias_kind == "symlink":
            checkpoint_config_path.symlink_to(screened_path)
        else:
            checkpoint_config_path.hardlink_to(screened_path)
    screened_before = screened_path.read_bytes()

    def client_must_not_be_created(*args: object, **kwargs: object) -> object:
        raise AssertionError("client must not be created")

    monkeypatch.setattr(cli, "_case_dev_client", client_must_not_be_created)

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--case-dev-fixture",
                str(fixture_path),
                "--public-selection",
                str(public_selection_path),
                "--paid-gaps",
                str(paid_gaps_path),
                "--free-download-manifest",
                str(free_downloads_path),
                "--checkpoint-config-output",
                str(checkpoint_config_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )
    assert screened_path.read_bytes() == screened_before


def test_public_first_bridge_rejects_orphan_checkpoint_before_candidate_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "bridge"
    screened_path = tmp_path / "screened.jsonl"
    public_selection_path = tmp_path / "public-selection.jsonl"
    paid_gaps_path = tmp_path / "paid-gaps.jsonl"
    free_downloads_path = tmp_path / "free-downloads.jsonl"
    fixture_path = tmp_path / "case-dev.jsonl"
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,),
        use_embedded_entries=True,
        target_clean_cases=1,
    )
    [gap] = plan.paid_gap_cases
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_selection_path, [])
    _write_jsonl(paid_gaps_path, [gap.to_record()])
    _write_jsonl(
        free_downloads_path,
        [
            {
                **request.to_record(),
                "local_path": f"cl-123/{request.source_document_id}.pdf",
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    rate_limit = {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {"type": "search", "query": "1:26-cv-00001", "limit": 20},
        "status_code": 429,
        "payload": {"error": "slow down"},
    }
    _write_jsonl(fixture_path, [rate_limit, rate_limit, rate_limit])
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--case-dev-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_selection_path),
        "--paid-gaps",
        str(paid_gaps_path),
        "--free-download-manifest",
        str(free_downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]
    assert main(command) == 2
    checkpoint_dir = output_root / "checkpoints" / "pacer-gap-bridge"
    [checkpoint_path] = list(checkpoint_dir.glob("*.json"))
    checkpoint_before = checkpoint_path.read_bytes()
    _write_json(checkpoint_dir / "orphan.json", {"unexpected": True})

    def candidate_attempt(*args: object, **kwargs: object) -> object:
        raise AssertionError("candidate bridge must not run")

    monkeypatch.setattr(cli, "bridge_public_plan_paid_gap_candidate", candidate_attempt)

    assert main(command) == 2
    assert checkpoint_path.read_bytes() == checkpoint_before


def test_fixture_pacer_gap_flow_reaches_merged_parser_manifest(tmp_path: Path) -> None:
    output_root = tmp_path / "acquisition"
    common_document_root = output_root / "documents"
    purchase_policy, purchase_ledger, cohort_policy = _purchase_policy(tmp_path)
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
                    "limit": 100,
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
    paid_selection = next(
        record for record in selections if record["candidate_id"] == "cl-123"
    )
    assert paid_selection["paid_recovery_required"] is True
    assert (
        paid_selection["planning_status"] == "identity_resolved_paid_recovery_required"
    )
    bridge_summary = _read_json(output_root / "pacer-gap-bridge-summary.json")
    assert bridge_summary["schema_version"] == (
        "legalforecast.courtlistener_case_dev_bridge.v2"
    )
    assert bridge_summary["identity_resolved_paid_gap_case_count"] == 1
    assert bridge_summary["paid_recovery_required_case_count"] == 1
    assert bridge_summary["document_bytes_ready_case_count"] == 1
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
    paid_case = next(
        record for record in budget["case_plans"] if record["candidate_id"] == "cl-123"
    )
    assert paid_case["purchase_document_ids"] == ["case-dev-mtd"]

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
                "init-purchase-ledger",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--output-root",
                str(tmp_path / "purchase-ledger-initialization"),
                "--execute",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "purchase-missing",
                "--budget-plan",
                str(output_root / "missing-core-budget-plan.json"),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
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
        "cl-free-entry-1-complaint",
        "cl-free-entry-5-motion-to-dismiss-memorandum",
        "cl-free-entry-16-decision",
        "cl-123-entry-1-complaint",
        "cl-123-entry-16-decision",
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


def _screened_case_variant(
    *,
    candidate_id: str,
    docket_number: str,
    case_name: str,
) -> dict[str, object]:
    record = copy.deepcopy(_screened_case())
    candidate = cast(dict[str, object], record["candidate"])
    candidate["docket_id"] = candidate_id
    candidate["candidate_key"] = candidate_id
    candidate["url"] = f"https://www.courtlistener.com/docket/456/{candidate_id}/"
    metadata = cast(dict[str, object], candidate["metadata"])
    metadata["case_id"] = candidate_id
    metadata["docket_number"] = docket_number
    metadata["case_name"] = case_name
    return record


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


def _purchase_policy(tmp_path: Path) -> tuple[Path, Path, Path]:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    path = tmp_path / "purchase-policy.json"
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
        path,
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
    return path, ledger, cohort_path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
