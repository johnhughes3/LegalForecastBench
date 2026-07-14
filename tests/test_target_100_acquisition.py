from __future__ import annotations

import json
from pathlib import Path

import legalforecast.cli as cli
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    generate_case_dev_purchase_policy,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.ingestion.target_100_acquisition import (
    Target100PreparationConfig,
    build_target_100_stage_commands,
)
from pytest import CaptureFixture


def test_target_100_commands_are_resumable_noncharging_and_exactly_capped(
    tmp_path: Path,
) -> None:
    config = Target100PreparationConfig(
        output_root=tmp_path / "run",
        snapshot=tmp_path / "snapshot",
        expected_cycle_hash="a" * 64,
        candidate_pool_size=200,
        target_case_count=100,
        live_public_download=True,
        live_courtlistener=True,
        request_ledger=tmp_path / "courtlistener-requests.sqlite3",
        use_embedded_entries=True,
        resume=True,
    )

    commands = build_target_100_stage_commands(config)

    assert [command.stage for command in commands] == [
        "plan-public-downloads",
        "download-free",
        "bridge-pacer-gaps",
        "filter-core-documents",
        "plan",
    ]
    flattened = [argument for command in commands for argument in command.argv]
    assert "purchase-missing" not in flattened
    assert "purchase-missing-recap-fetch" not in flattened
    assert "--acknowledge-pacer-fees" not in flattened
    assert "--live-purchase" not in flattened
    assert "--resume" in flattened
    assert commands[-1].argv[-2:] == ("--target-case-count", "100")
    assert "--live-courtlistener" in commands[2].argv
    assert "--request-ledger" in commands[2].argv
    assert "--live-public-download" in commands[1].argv


def test_target_100_cli_help_explains_provider_boundary(
    capsys: CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "prepare-target-100", "--help"])
    output = capsys.readouterr().out
    assert "Complete saturated snapshot" in output
    assert "never purchases" in output
    assert "CourtListener" in output
    assert "Case.dev" in output


def test_target_100_dry_run_writes_a_nonpurchase_stage_plan(tmp_path: Path) -> None:
    output_root = tmp_path / "run"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=100)
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
            ]
        )
        == 0
    )

    summary = json.loads(
        (output_root / "target-100-preparation-summary.json").read_text()
    )
    assert summary["dry_run"] is True
    assert summary["target_case_count"] == 100
    assert summary["paid_activity_requested"] is False
    assert summary["paid_activity_executed"] is False
    assert all(
        row["stage"] != "purchase-missing-recap-fetch"
        for row in summary["stage_commands"]
    )


def test_target_100_real_five_stage_courtlistener_fixture_e2e(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "run"
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=101)
    )
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )

    summary = json.loads(
        (output_root / "target-100-preparation-summary.json").read_text()
    )
    assert summary["selected_case_count"] == 100
    assert summary["candidate_pool_size"] == 101
    assert summary["next_stage"] == "purchase-missing-recap-fetch"
    assert summary["paid_activity_executed"] is False
    assert summary["total_missing_core_documents"] == 100
    assert summary["total_estimated_cost_usd"] == "305.00"
    assert summary["config_sha256"].startswith("sha256:")
    assert summary["selected_candidate_ids_sha256"].startswith("sha256:")
    assert summary["frontier_sha256"].startswith("sha256:")
    assert set(summary["stage_commitments"]) == {
        "01-public-plan",
        "02-free-download",
        "03-gap-bridge",
        "04-core-filter",
        "05-budget",
    }
    bridge_card = json.loads(
        (output_root / "03-gap-bridge/run-cards/bridge-pacer-gaps.json").read_text()
    )
    assert bridge_card["bridge_provider"] == "courtlistener_rest"
    assert bridge_card["paid_activity_executed"] is False

    budget_plan = output_root / "05-budget/missing-core-budget-plan.json"
    selection = output_root / "03-gap-bridge/public-packet-selection-reconciled.jsonl"
    purchase_policy, cohort_policy, purchase_ledger = _purchase_policies(tmp_path)
    broker_policy = tmp_path / "recap-fetch-broker-policy.json"
    assert (
        main(
            [
                "acquisition",
                "generate-recap-fetch-broker-policy",
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--output",
                str(broker_policy),
            ]
        )
        == 0
    )
    broker = json.loads(broker_policy.read_text())
    allowed_document_ids = [
        record["recap_document"] for record in broker["allowed_documents"]
    ]
    assert len(allowed_document_ids) == 100
    assert all(str(document_id).isdigit() for document_id in allowed_document_ids)

    purchase_cl_fixture, purchase_broker_fixture = _purchase_fixtures(
        tmp_path, allowed_document_ids
    )
    purchase_output = tmp_path / "offline-purchase"
    assert (
        main(
            [
                "acquisition",
                "purchase-missing-recap-fetch",
                "--output-root",
                str(purchase_output),
                "--budget-plan",
                str(budget_plan),
                "--selection",
                str(selection),
                "--purchase-policy",
                str(purchase_policy),
                "--cohort-policy",
                str(cohort_policy),
                "--purchase-ledger",
                str(purchase_ledger),
                "--courtlistener-fixture",
                str(purchase_cl_fixture),
                "--purchase-broker-fixture",
                str(purchase_broker_fixture),
                "--execute",
                "--acknowledge-pacer-fees",
            ]
        )
        == 0
    )
    purchase_card = json.loads(
        (purchase_output / "run-cards/purchase-missing-recap-fetch.json").read_text()
    )
    assert purchase_card["paid_activity_requested"] is False
    assert purchase_card["paid_activity_executed"] is False


def test_target_100_resume_rejects_changed_cost_provider_fixture_and_snapshot(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path / "base", case_count=100)
    )

    def command(output_root: Path) -> list[str]:
        return [
            "acquisition",
            "prepare-target-100",
            "--output-root",
            str(output_root),
            "--snapshot",
            str(snapshot),
            "--expected-cycle-hash",
            cycle_hash,
            "--fixture-documents",
            str(fixture_documents),
            "--courtlistener-fixture",
            str(courtlistener_fixture),
            "--use-embedded-entries",
        ]

    mutations = (
        ("cost", ["--cost-per-document-usd", "4.00"]),
        (
            "provider",
            [
                "--live-courtlistener",
                "--request-ledger",
                str(tmp_path / "requests.sqlite3"),
            ],
        ),
    )
    for name, extra in mutations:
        output_root = tmp_path / f"run-{name}"
        assert main(command(output_root)) == 0
        changed = command(output_root)
        if name == "provider":
            fixture_index = changed.index("--courtlistener-fixture")
            del changed[fixture_index : fixture_index + 2]
        changed.extend(extra)
        assert main(changed) == 2
        assert "changed-config resume" in capsys.readouterr().err

    fixture_output = tmp_path / "run-fixture"
    assert main(command(fixture_output)) == 0
    courtlistener_fixture.write_text(
        courtlistener_fixture.read_text() + "\n", encoding="utf-8"
    )
    assert main(command(fixture_output)) == 2
    assert "changed-config resume" in capsys.readouterr().err

    other_snapshot, other_hash, other_documents, other_courtlistener = (
        _target_100_fixture(tmp_path / "other", case_count=100)
    )
    snapshot_output = tmp_path / "run-snapshot"
    assert main(command(snapshot_output)) == 0
    changed_snapshot = command(snapshot_output)
    replacements = {
        str(snapshot): str(other_snapshot),
        cycle_hash: other_hash,
        str(fixture_documents): str(other_documents),
        str(courtlistener_fixture): str(other_courtlistener),
    }
    changed_snapshot = [replacements.get(value, value) for value in changed_snapshot]
    assert main(changed_snapshot) == 2
    assert "changed-config resume" in capsys.readouterr().err


def test_target_100_underfilled_snapshot_writes_durable_failure_only(
    tmp_path: Path,
) -> None:
    snapshot, cycle_hash, fixture_documents, courtlistener_fixture = (
        _target_100_fixture(tmp_path, case_count=99)
    )
    output_root = tmp_path / "run"
    assert (
        main(
            [
                "acquisition",
                "prepare-target-100",
                "--output-root",
                str(output_root),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 2
    )
    run_card = json.loads(
        (output_root / "run-cards/prepare-target-100.json").read_text()
    )
    assert run_card["status"] == "failed"
    assert run_card["paid_activity_executed"] is False
    assert not (output_root / "target-100-preparation-summary.json").exists()
    assert not (output_root / "01-public-plan").exists()


def _target_100_fixture(
    tmp_path: Path,
    *,
    case_count: int,
) -> tuple[Path, str, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store_path = tmp_path / f"cycle-{case_count}.sqlite3"
    snapshot_root = tmp_path / f"snapshots-{case_count}"
    records = [_screened_case(index) for index in range(case_count)]
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        store.ensure_batch("batch-002", {"provider": "courtlistener-recap-rest-v4"})
        store.ensure_terms("batch-002", ("motion to dismiss",))
        store.commit_search_page(
            "batch-002",
            "motion to dismiss",
            None,
            [
                {
                    "provider_hit_id": f"hit-{index}",
                    "candidate_id": f"courtlistener-docket-{1000 + index}",
                    "payload": {"docket_id": str(1000 + index)},
                }
                for index in range(case_count)
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        for index, record in enumerate(records):
            store.record_observation(
                f"courtlistener-docket-{1000 + index}",
                batch_id="batch-002",
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence=record,
            )
        snapshot = store.export_snapshot(
            snapshot_root,
            snapshot_id=f"target-100-{case_count}",
            batch_id="batch-002",
            complete=True,
        )
        cycle_hash = store.cycle_hash

    fixture_documents = tmp_path / f"free-documents-{case_count}.json"
    fixture_documents.write_text(
        json.dumps(
            {
                url: "%PDF-1.7\nfixture\n%%EOF"
                for index in range(case_count)
                for url in (
                    f"https://storage.courtlistener.com/{1000 + index}-complaint.pdf",
                    f"https://storage.courtlistener.com/{1000 + index}-decision.pdf",
                )
            }
        )
    )
    courtlistener_fixture = tmp_path / f"courtlistener-{case_count}.jsonl"
    responses: list[dict[str, object]] = []
    for index in range(case_count):
        docket_id = 1000 + index
        entry_id = 7000 + index
        document_id = 9000 + index
        responses.extend(
            (
                {
                    "method": "GET",
                    "path": f"/dockets/{docket_id}/",
                    "params": {},
                    "status_code": 200,
                    "payload": {
                        "id": docket_id,
                        "court": "nysd",
                        "docket_number": f"1:26-cv-{index + 1:05d}",
                        "case_name": f"Fixture {index} v. Example",
                    },
                },
                {
                    "method": "GET",
                    "path": "/docket-entries/",
                    "params": {"docket": str(docket_id), "page_size": 100},
                    "status_code": 200,
                    "payload": {
                        "results": [
                            {
                                "id": entry_id,
                                "docket": docket_id,
                                "entry_number": 5,
                                "description": "MOTION to Dismiss filed by Defendant.",
                                "date_filed": "2026-01-01",
                                "recap_documents": [{"id": document_id}],
                            }
                        ],
                        "next": None,
                    },
                },
                {
                    "method": "GET",
                    "path": f"/recap-documents/{document_id}/",
                    "params": {},
                    "status_code": 200,
                    "payload": {
                        "id": document_id,
                        "docket_entry": entry_id,
                        "document_number": "5",
                        "attachment_number": None,
                        "description": "Motion to Dismiss",
                        "is_available": False,
                        "is_sealed": False,
                        "is_private": False,
                    },
                },
            )
        )
    courtlistener_fixture.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in responses)
    )
    return snapshot, cycle_hash, fixture_documents, courtlistener_fixture


def _purchase_policies(tmp_path: Path) -> tuple[Path, Path, Path]:
    ledger = (tmp_path / "cycle-purchases.sqlite3").resolve()
    decisions = cli._fixture_cohort_policy_decisions()
    decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "2250.00",
        "max_per_case_usd": "73.20",
        "reservation_headroom_required": True,
    }
    cohort = cli.generate_cohort_policy(decisions)
    cohort_path = tmp_path / "cohort-policy.json"
    cohort_path.write_text(json.dumps(cohort, sort_keys=True))
    purchase = generate_case_dev_purchase_policy(
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
                "source_citation": "https://www.courtlistener.com/help/coverage/recap/",
                "verified_at_utc": "2026-07-14T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    purchase_path = tmp_path / "purchase-policy.json"
    purchase_path.write_text(json.dumps(purchase, sort_keys=True))
    return purchase_path, cohort_path, ledger


def _purchase_fixtures(
    tmp_path: Path,
    document_ids: list[str],
) -> tuple[Path, Path]:
    courtlistener = tmp_path / "purchase-courtlistener.jsonl"
    broker = tmp_path / "purchase-broker.json"
    courtlistener_records: list[dict[str, object]] = []
    broker_records: list[dict[str, object]] = []
    for index, document_id in enumerate(document_ids):
        queue_id = str(50000 + index)
        courtlistener_records.extend(
            (
                {
                    "method": "GET",
                    "path": f"/recap-documents/{document_id}/",
                    "status_code": 200,
                    "payload": {"id": int(document_id)},
                },
                {
                    "method": "GET",
                    "path": f"/recap-fetch/{queue_id}/",
                    "status_code": 200,
                    "payload": {"status": 2},
                },
                {
                    "method": "GET",
                    "path": f"/recap-documents/{document_id}/",
                    "status_code": 200,
                    "payload": {
                        "id": int(document_id),
                        "is_available": True,
                        "filepath_local": (
                            f"https://storage.courtlistener.com/{document_id}.pdf"
                        ),
                    },
                },
            )
        )
        broker_records.append(
            {"reservation_id": f"reservation-{index}", "id": queue_id}
        )
    courtlistener.write_text(
        "".join(
            json.dumps(record, sort_keys=True) + "\n"
            for record in courtlistener_records
        )
    )
    broker.write_text(json.dumps(broker_records, sort_keys=True))
    return courtlistener, broker


def _screened_case(index: int) -> dict[str, object]:
    docket_id = 1000 + index
    return {
        "provider": "courtlistener-recap-rest-v4",
        "canonical_rest_screen_complete": True,
        "nature_of_suit": "440 Civil Rights",
        "nos_macro_category": "civil_rights",
        "candidate": {
            "docket_id": str(docket_id),
            "candidate_key": str(docket_id),
            "metadata": {
                "case_id": str(docket_id),
                "case_name": f"Fixture {index} v. Example",
                "court": "nysd",
                "docket_number": f"1:26-cv-{index + 1:05d}",
            },
            "url": f"https://www.courtlistener.com/docket/{docket_id}/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _entry(
                docket_id,
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                f"https://storage.courtlistener.com/{docket_id}-complaint.pdf",
                pacer_only=False,
            ),
            _entry(
                docket_id,
                5,
                "MOTION to Dismiss filed by Defendant.",
                "Motion to Dismiss",
                f"https://ecf.nysd.uscourts.gov/doc1/{docket_id}",
                pacer_only=True,
            ),
            _entry(
                docket_id,
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                f"https://storage.courtlistener.com/{docket_id}-decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _entry(
    docket_id: int,
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{docket_id}-{number}",
        "entry_number": str(number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "source_document_id": f"{docket_id}{number}",
                "kind": "main_document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }
