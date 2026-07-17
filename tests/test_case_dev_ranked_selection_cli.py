from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import cast

import legalforecast.cli as legalforecast_cli
import legalforecast.ingestion.snapshot_replay as snapshot_replay_module
import pytest
from legalforecast.ingestion.budgeted_docket_acquisition import (
    BudgetedDocketAcquisitionError,
    provisional_lineage_flags,
    ranked_docket_targets,
    verify_authenticated_ranked_firecrawl_handoff,
)
from legalforecast.ingestion.case_dev_ranked_selection import (
    CASE_DEV_RANKED_SELECTION_RUN_SCHEMA,
    CASE_DEV_RANKED_SUBSET_SELECTION_RUN_SCHEMA,
    CASE_DEV_RANKED_TRANSFER_SCHEMA,
    _source_bound_bankruptcy_adversary_entry_evidence,
    project_case_dev_opinion_source,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import DiscoveryHit, TermTerminalStatus
from legalforecast.ingestion.recap_api_batch_driver import (
    DirectSearchHitProvenance,
    DirectSearchLead,
    DirectSearchSeedSource,
    RecapApiBatchDriverError,
)


@pytest.mark.parametrize(
    ("entry_text", "expected_number"),
    [
        (
            "Adversary case 25-09086. Complaint by Trustee against PeriGen, Inc.",
            "25-09086",
        ),
        (
            "Adversary case 25-09087. Complaint by Trustee against PeriGen, Inc.",
            None,
        ),
        (
            "Adversary case pending. Complaint by Trustee against PeriGen, Inc.",
            None,
        ),
    ],
)
def test_source_bound_adversary_evidence_requires_exact_docket_number(
    entry_text: str,
    expected_number: str | None,
) -> None:
    evidence = _source_bound_bankruptcy_adversary_entry_evidence(
        {
            "screening_metadata": {
                "court_id": "ianb",
                "docket_number": "25-09086",
            },
            "entries": [
                {
                    "entry_number": "1",
                    "filed_at": "2025-07-25",
                    "entry_text": entry_text,
                }
            ],
        },
        docket_id="555",
        ranked_record_sha256="a" * 64,
    )

    if expected_number is None:
        assert evidence is None
    else:
        assert evidence is not None
        assert evidence["adversary_case_number"] == expected_number


def test_select_case_dev_ranked_materializes_exact_top_n_rest_batch(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    target_store = _target_store(tmp_path)
    run_card = tmp_path / "selection-run-card.json"
    summary = tmp_path / "selection-summary.json"

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=run_card,
                summary=summary,
            )
        )
        == 0
    )

    frozen = json.loads(run_card.read_text())
    assert frozen["schema_version"] == CASE_DEV_RANKED_SELECTION_RUN_SCHEMA
    assert frozen["top_n"] == 1
    assert frozen["leads_selected"] == 1
    assert frozen["selected"][0]["docket_id"] == "102"
    assert frozen["selected"][0]["rank"] == 1
    assert len(frozen["source_candidate_set_sha256"]) == 64
    assert len(frozen["source_projection_sha256"]) == 64
    assert len(frozen["ranked_output_sha256"]) == 64

    with CycleAcquisitionStore(target_store) as store:
        assert store.candidate_ids("ranked-rest") == ("courtlistener-docket-102",)
        config = store.batch_config("ranked-rest")
        assert config["selection_semantics"] == "exact_case_dev_ranked_prefix"
        assert config["selected_candidate_count"] == 1
        [hit] = store.candidate_discovery_hits("ranked-rest")
    provenance = hit.payload["case_dev_ranked_selection_provenance"]
    assert provenance["schema_version"] == CASE_DEV_RANKED_TRANSFER_SCHEMA
    assert provenance["rank"] == 1
    assert provenance["case_dev_returned_courtlistener_url"] == (
        "https://www.courtlistener.com/api/rest/v4/dockets/102/"
    )
    assert "docket_url" not in hit.payload

    # The target batch is replay-safe and the frozen run card is stable.
    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=run_card,
                summary=summary,
            )
        )
        == 0
    )
    resumed = json.loads(summary.read_text())
    assert resumed["already_seeded"] is True
    assert resumed["leads_seeded"] == 0


def test_select_case_dev_ranked_accepts_authenticated_historical_opinion_projection(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    historical_card_sha256 = _rewrite_as_historical_opinion_enrichment(enrichment_root)
    target_store = _target_store(tmp_path)
    run_card = tmp_path / "historical-selection-run-card.json"

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=run_card,
                summary=tmp_path / "historical-selection-summary.json",
                expected_enrichment_run_card_sha256=historical_card_sha256,
            )
        )
        == 0
    )

    # The historical representation is accepted only after reconstruction from
    # the authoritative source store. The new selection upgrades its lineage to
    # the complete current authority commitments.
    selected = json.loads(run_card.read_text())
    assert selected["source_search_type"] == "o"
    assert selected["source_schema_version"] == (
        "legalforecast.courtlistener_opinion_discovery.v1"
    )
    assert selected["source_available_only"] == "absent"
    assert selected["source_query_terms"] == ['"motion to dismiss"']
    assert len(selected["source_query_commitment_sha256"]) == 64
    assert len(selected["source_hit_set_sha256"]) == 64
    with CycleAcquisitionStore(target_store) as store:
        assert store.candidate_ids("ranked-rest") == ("courtlistener-docket-102",)


def test_select_case_dev_ranked_rejects_historical_projection_drift_before_write(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    _rewrite_as_historical_opinion_enrichment(enrichment_root)
    projection_path = (
        enrichment_root / "checkpoints/case-dev-recap-source-projection.jsonl"
    )
    projection = _read_jsonl(projection_path)
    projection[0]["source_lineage"]["source_batch_digest"] = "0" * 64
    _write_jsonl(projection_path, projection)
    run_card_path = enrichment_root / "run-cards/enrich-recap-case-dev.json"
    run_card = json.loads(run_card_path.read_text())
    run_card["source_projection_sha256"] = hashlib.sha256(
        projection_path.read_bytes()
    ).hexdigest()
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    expected_card_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()
    target_store = _target_store(tmp_path)
    target_store_before = target_store.read_bytes()

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=expected_card_sha256,
            )
        )
        == 2
    )
    assert target_store.read_bytes() == target_store_before
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_hybrid_historical_run_card_before_write(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    _rewrite_as_historical_opinion_enrichment(enrichment_root)
    run_card_path = enrichment_root / "run-cards/enrich-recap-case-dev.json"
    run_card = json.loads(run_card_path.read_text())
    run_card["source_schema_version"] = (
        "legalforecast.courtlistener_opinion_discovery.v1"
    )
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    expected_card_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()
    target_store = _target_store(tmp_path)
    target_store_before = target_store.read_bytes()

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=expected_card_sha256,
            )
        )
        == 2
    )
    assert target_store.read_bytes() == target_store_before
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_historical_unrestricted_projection(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path, search_type="r")
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    historical_card_sha256 = _rewrite_as_historical_opinion_enrichment(enrichment_root)
    target_store = _target_store(tmp_path)
    target_store_before = target_store.read_bytes()

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=historical_card_sha256,
            )
        )
        == 2
    )
    assert target_store.read_bytes() == target_store_before
    _assert_no_target_rows(target_store)


def test_promote_terminal_firecrawl_subset_is_exact_and_nonprovisional(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)

    assert legalforecast_cli.main(_promotion_args(fixture)) == 0

    snapshot = cast(Path, fixture["output_root"]) / "snapshots/terminal-promoted"
    manifest = verify_snapshot(
        snapshot,
        expected_cycle_hash=cast(str, fixture["target_cycle_hash"]),
        require_complete=True,
        require_saturated=True,
    )
    assert (
        not {
            "provisional_frontier",
            "final_cohort_eligible",
            "full_source_terminal",
        }
        & manifest.keys()
    )
    commitment = manifest["stage_commitments"]["terminal_subset_promotion"]
    assert commitment["selected_candidate_count"] == 5
    assert commitment["final_cohort_eligible"] is True
    assert commitment["full_source_terminal"] is True
    assert commitment["provider_activity_requested"] is False
    assert commitment["provider_activity_executed"] is False
    accepted = _read_jsonl(snapshot / "screened-cases.jsonl")
    assert {record["candidate_id"] for record in accepted} == {
        f"courtlistener-docket-{docket_id}"
        for docket_id in ("102", "103", "104", "105", "106")
    }
    run_card = json.loads(
        (
            cast(Path, fixture["output_root"])
            / "run-cards/promote-terminal-firecrawl-subset.json"
        ).read_text()
    )
    assert run_card["provider_activity_requested"] is False
    assert run_card["provider_activity_executed"] is False
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False

    assert legalforecast_cli.main(_promotion_args(fixture)) == 0
    resumed_summary = json.loads(
        (
            cast(Path, fixture["output_root"])
            / "terminal-subset-promotion-summary.json"
        ).read_text()
    )
    assert resumed_summary["resumed_existing_snapshot"] is True
    assert resumed_summary["accepted_case_count"] == 5


def test_promote_terminal_firecrawl_subset_dry_run_writes_only_completion_metadata(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    args = _promotion_args(fixture)
    args.remove("--execute")

    assert legalforecast_cli.main(args) == 0

    output_root = cast(Path, fixture["output_root"])
    summary = json.loads(
        (output_root / "terminal-subset-promotion-summary.json").read_text()
    )
    run_card = json.loads(
        (output_root / "run-cards/promote-terminal-firecrawl-subset.json").read_text()
    )
    assert summary["dry_run"] is True
    assert summary["reconciled"] is False
    assert summary["provider_activity_executed"] is False
    assert run_card["status"] == "completed"
    assert run_card["dry_run"] is True
    assert run_card["provider_activity_executed"] is False
    assert not (output_root / "snapshots").exists()
    assert not (output_root / "raw-docket-html").exists()


def test_promote_terminal_firecrawl_subset_rejects_rewritten_selection_card(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    selection_card = cast(Path, fixture["selection_card"])
    rewritten = json.loads(selection_card.read_text())
    rewritten["selected_docket_ids"] = ["101"]
    selection_card.write_text(json.dumps(rewritten, sort_keys=True) + "\n")
    fixture["selection_card_sha256"] = hashlib.sha256(
        selection_card.read_bytes()
    ).hexdigest()

    assert legalforecast_cli.main(_promotion_args(fixture)) == 2
    assert not (cast(Path, fixture["output_root"]) / "snapshots").exists()


@pytest.mark.parametrize("mutation", ["manifest", "screen-input", "raw"])
def test_promote_terminal_firecrawl_subset_rejects_source_commitment_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    if mutation == "manifest":
        manifest_path = cast(Path, fixture["source_snapshot"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["created_at"] = "2026-07-16T00:00:00Z"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    elif mutation == "screen-input":
        successes = cast(Path, fixture["source_successes"])
        records = _read_jsonl(successes)
        records[0]["retrieved_at"] = "2026-07-15T00:00:00+00:00"
        _write_jsonl(successes, records)
    else:
        raw = cast(Path, fixture["source_raw"])
        raw.write_text(raw.read_text() + "<!-- changed -->")

    assert legalforecast_cli.main(_promotion_args(fixture)) == 2
    assert not (cast(Path, fixture["output_root"]) / "snapshots").exists()


def test_promote_terminal_firecrawl_subset_rejects_source_accepted_set_drift(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path, source_docket_id="101")

    assert legalforecast_cli.main(_promotion_args(fixture)) == 2
    assert not (cast(Path, fixture["output_root"]) / "snapshots").exists()


def test_promote_terminal_firecrawl_subset_rejects_contradictory_success_count(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path, provisional_success_count=4)

    assert legalforecast_cli.main(_promotion_args(fixture)) == 2
    assert not (cast(Path, fixture["output_root"]) / "snapshots").exists()


def test_promote_terminal_firecrawl_subset_publishes_buffered_raw_after_source_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    source_raw = cast(Path, fixture["source_raw"])
    original_raw = source_raw.read_bytes()
    original_verify = legalforecast_cli.verify_terminal_subset_promotion_source

    def mutate_after_verification(*args: object, **kwargs: object) -> object:
        bundle = original_verify(*args, **kwargs)
        source_raw.write_bytes(b"mutated after authenticated source verification")
        return bundle

    monkeypatch.setattr(
        legalforecast_cli,
        "verify_terminal_subset_promotion_source",
        mutate_after_verification,
    )

    assert legalforecast_cli.main(_promotion_args(fixture)) == 0
    output_raw = (
        cast(Path, fixture["output_root"]) / "raw-docket-html/102.html"
    ).read_bytes()
    assert output_raw == original_raw


def test_promote_terminal_firecrawl_subset_uses_exact_pinned_manifest_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    manifest_path = cast(Path, fixture["source_snapshot"]) / "manifest.json"
    pinned_manifest = json.loads(manifest_path.read_text())
    pinned_manifest.update(
        {
            "provisional_frontier": False,
            "final_cohort_eligible": True,
            "full_source_terminal": True,
        }
    )
    manifest_path.write_text(json.dumps(pinned_manifest, sort_keys=True) + "\n")
    fixture["source_snapshot_manifest_sha256"] = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    real_verify_snapshot = snapshot_replay_module.verify_snapshot

    def verify_different_manifest(path: str | Path, **kwargs: object) -> object:
        private_manifest_path = Path(path) / "manifest.json"
        exact_bytes = private_manifest_path.read_bytes()
        different = json.loads(exact_bytes)
        different.update(
            {
                "provisional_frontier": True,
                "final_cohort_eligible": False,
                "full_source_terminal": False,
            }
        )
        private_manifest_path.write_text(json.dumps(different, sort_keys=True) + "\n")
        try:
            return real_verify_snapshot(path, **kwargs)
        finally:
            private_manifest_path.write_bytes(exact_bytes)

    monkeypatch.setattr(
        snapshot_replay_module,
        "verify_snapshot",
        verify_different_manifest,
    )

    assert legalforecast_cli.main(_promotion_args(fixture)) == 2
    assert not (cast(Path, fixture["output_root"]) / "snapshots").exists()


def test_promote_terminal_firecrawl_subset_rejects_outputs_inside_source_bundle(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    fixture["output_root"] = cast(Path, fixture["source_bundle_root"]) / "bad-output"

    assert legalforecast_cli.main(_promotion_args(fixture)) == 2
    assert not cast(Path, fixture["output_root"]).exists()


@pytest.mark.parametrize(
    ("flag", "tree", "name"),
    [
        ("--screened-cases-output", "snapshot", "screened-cases.jsonl"),
        ("--exclusions-output", "snapshot", "exclusions.jsonl"),
        ("--summary-output", "snapshot", "summary.json"),
        ("--run-card-output", "snapshot", "run-card.json"),
        ("--log-output", "snapshot", "log.jsonl"),
        ("--screened-cases-output", "raw", "screened-cases.jsonl"),
        ("--exclusions-output", "raw", "exclusions.jsonl"),
        ("--summary-output", "raw", "summary.json"),
        ("--run-card-output", "raw", "run-card.json"),
        ("--log-output", "raw", "log.jsonl"),
    ],
)
def test_promote_terminal_firecrawl_subset_rejects_writable_files_in_output_trees(
    tmp_path: Path,
    flag: str,
    tree: str,
    name: str,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    output_root = cast(Path, fixture["output_root"])
    tree_path = (
        output_root / "snapshots/terminal-promoted"
        if tree == "snapshot"
        else output_root / "raw-docket-html"
    )
    args = [*_promotion_args(fixture), flag, str(tree_path / name)]

    assert legalforecast_cli.main(args) == 2
    assert not (output_root / "snapshots").exists()
    assert not (output_root / "raw-docket-html").exists()


def test_promote_terminal_firecrawl_subset_rejects_cycle_store_sidecar_in_raw_tree(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    output_root = cast(Path, fixture["output_root"])
    raw_html_dir = output_root / "raw-docket-html"
    raw_html_dir.mkdir(parents=True)
    lock_target = raw_html_dir / "cycle-store.lock"
    lock_target.write_text("immutable snapshot-adjacent evidence")
    cycle_store_lock = Path(f"{fixture['target_store']}.lock")
    cycle_store_lock.unlink(missing_ok=True)
    cycle_store_lock.symlink_to(lock_target)

    assert legalforecast_cli.main(_promotion_args(fixture)) == 2
    assert lock_target.read_text() == "immutable snapshot-adjacent evidence"
    assert not (output_root / "snapshots").exists()


def test_promote_terminal_firecrawl_subset_resume_cannot_overwrite_output_trees(
    tmp_path: Path,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    assert legalforecast_cli.main(_promotion_args(fixture)) == 0
    output_root = cast(Path, fixture["output_root"])
    snapshot = output_root / "snapshots/terminal-promoted"
    snapshot_summary = snapshot / "summary.json"
    original_summary = snapshot_summary.read_bytes()
    raw_html_dir = output_root / "raw-docket-html"
    original_raw_files = {
        path: path.read_bytes() for path in raw_html_dir.iterdir() if path.is_file()
    }

    for flag, path in (
        ("--summary-output", snapshot_summary),
        ("--screened-cases-output", raw_html_dir / "screened-cases.jsonl"),
    ):
        assert legalforecast_cli.main([*_promotion_args(fixture), flag, str(path)]) == 2
        assert snapshot_summary.read_bytes() == original_summary
        assert {
            raw_path: raw_path.read_bytes()
            for raw_path in raw_html_dir.iterdir()
            if raw_path.is_file()
        } == original_raw_files
        verify_snapshot(
            snapshot,
            expected_cycle_hash=cast(str, fixture["target_cycle_hash"]),
            require_complete=True,
            require_saturated=True,
        )


def test_promote_terminal_firecrawl_subset_resume_publishes_verified_snapshot_buffers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _terminal_promotion_fixture(tmp_path)
    assert legalforecast_cli.main(_promotion_args(fixture)) == 0
    output_root = cast(Path, fixture["output_root"])
    snapshot = output_root / "snapshots/terminal-promoted"
    expected_screened = json.loads(
        "["
        + ",".join((snapshot / "screened-cases.jsonl").read_text().splitlines())
        + "]"
    )
    original_resume = CycleAcquisitionStore.existing_complete_snapshot_evidence

    def mutate_after_verification(
        store: CycleAcquisitionStore,
        *args: object,
        **kwargs: object,
    ) -> object:
        evidence = original_resume(store, *args, **kwargs)
        if evidence is not None:
            (evidence.path / "screened-cases.jsonl").write_text(
                '{"candidate_id":"tampered-candidate"}\n'
            )
            (evidence.path / "exclusions.jsonl").write_text(
                '{"case_id":"tampered-candidate"}\n'
            )
            (evidence.path / "summary.json").write_text(
                '{"reconciliation_complete":false}\n'
            )
        return evidence

    monkeypatch.setattr(
        CycleAcquisitionStore,
        "existing_complete_snapshot_evidence",
        mutate_after_verification,
    )

    assert legalforecast_cli.main(_promotion_args(fixture)) == 0
    published_screened = [
        json.loads(line)
        for line in (output_root / "terminal-promoted-screened-cases.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]
    assert published_screened == expected_screened
    assert (
        output_root / "terminal-promoted-screening-exclusions.jsonl"
    ).read_text() == ""
    assert (
        json.loads(
            (output_root / "terminal-subset-promotion-summary.json").read_text()
        )["reconciled"]
        is True
    )


def test_select_case_dev_ranked_accepts_authenticated_unrestricted_recap_source(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path, search_type="r")
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    target_store = _target_store(tmp_path)
    run_card = tmp_path / "selection-run-card.json"

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=run_card,
                summary=tmp_path / "selection-summary.json",
            )
        )
        == 0
    )

    frozen = json.loads(run_card.read_text())
    assert frozen["source_search_type"] == "r"
    assert frozen["source_schema_version"] == (
        "legalforecast.courtlistener_unrestricted_recap.v1"
    )
    assert frozen["source_available_only"] == "omitted"
    assert frozen["source_query_terms"] == ['"motion to dismiss"']
    assert len(frozen["source_query_commitment_sha256"]) == 64
    assert len(frozen["source_hit_set_sha256"]) == 64
    with CycleAcquisitionStore(target_store) as store:
        config = store.batch_config("ranked-rest")
        assert config["source_search_type"] == "r"
        assert config["source_available_only"] == "omitted"
        [hit] = store.candidate_discovery_hits("ranked-rest")
    provenance = hit.payload["case_dev_ranked_selection_provenance"]
    assert provenance["source_search_type"] == "r"
    assert (
        provenance["source_query_commitment_sha256"]
        == (frozen["source_query_commitment_sha256"])
    )


def test_select_case_dev_ranked_authenticates_terminal_pagination_exclusion(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_terminal_exclusion_enrichment(
        tmp_path,
        source_store=source_store,
    )
    [failure] = _read_jsonl(
        enrichment_root / "checkpoints" / "case-dev-recap-failures.jsonl"
    )
    assert failure["reason"] == "case_dev_pagination_exhaustion_unproven"

    target_store = _target_store(tmp_path)
    selection_card = tmp_path / "selection-run-card.json"
    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=selection_card,
                summary=tmp_path / "selection-summary.json",
            )
        )
        == 0
    )

    frozen = json.loads(selection_card.read_text())
    assert frozen["ranked_candidate_count"] == 1
    assert frozen["source_candidate_count"] == 2
    assert frozen["terminal_exclusion_count"] == 1
    assert frozen["terminal_exclusion_reason_counts"] == {
        "case_dev_pagination_exhaustion_unproven": 1
    }
    assert len(frozen["terminal_exclusion_output_sha256"]) == 64
    assert len(frozen["terminal_excluded_candidate_set_sha256"]) == 64
    assert frozen["selected"][0]["docket_id"] == "102"
    with CycleAcquisitionStore(target_store) as store:
        assert store.candidate_ids("ranked-rest") == ("courtlistener-docket-102",)


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    [("docket_id", "999"), ("reason", [])],
)
def test_select_case_dev_ranked_rejects_rehashed_terminal_exclusion_tamper(
    tmp_path: Path,
    field_name: str,
    forged_value: object,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_terminal_exclusion_enrichment(
        tmp_path,
        source_store=source_store,
    )
    failures_path = enrichment_root / "checkpoints" / "case-dev-recap-failures.jsonl"
    [forged] = _read_jsonl(failures_path)
    forged[field_name] = forged_value
    _write_jsonl(failures_path, [forged])
    enrichment_run_card = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    run_card = json.loads(enrichment_run_card.read_text())
    run_card["failures_output_sha256"] = hashlib.sha256(
        failures_path.read_bytes()
    ).hexdigest()
    enrichment_run_card.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=hashlib.sha256(
                    enrichment_run_card.read_bytes()
                ).hexdigest(),
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_source_type_substitution(
    tmp_path: Path,
) -> None:
    unrestricted_source = _opinion_source_store(
        tmp_path,
        search_type="r",
        name="unrestricted.sqlite3",
    )
    enrichment_root = _run_enrichment(
        tmp_path,
        source_store=unrestricted_source,
    )
    opinion_source = _opinion_source_store(
        tmp_path,
        search_type="o",
        name="opinion.sqlite3",
    )
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=opinion_source,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_subset_materializes_exact_noncontiguous_dockets(
    tmp_path: Path,
) -> None:
    docket_ids = ("101", "102", "103")
    source_store = _opinion_source_store(tmp_path, docket_ids=docket_ids)
    enrichment_root = _run_enrichment(
        tmp_path,
        source_store=source_store,
        docket_ids=docket_ids,
    )
    target_store = _target_store(tmp_path)
    run_card = tmp_path / "subset-run-card.json"
    summary = tmp_path / "subset-summary.json"
    args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=target_store,
        run_card=run_card,
        summary=summary,
        docket_ids=("103", "102"),
    )

    assert legalforecast_cli.main(args) == 0

    frozen = json.loads(run_card.read_text())
    assert frozen["schema_version"] == CASE_DEV_RANKED_SUBSET_SELECTION_RUN_SCHEMA
    assert "top_n" not in frozen
    assert frozen["selection_semantics"] == "exact_case_dev_ranked_subset"
    assert frozen["selected_docket_ids"] == ["102", "103"]
    assert [row["docket_id"] for row in frozen["selected"]] == ["102", "103"]
    assert [row["rank"] for row in frozen["selected"]] == [1, 3]

    with CycleAcquisitionStore(target_store) as store:
        assert store.candidate_ids("ranked-subset-rest") == (
            "courtlistener-docket-102",
            "courtlistener-docket-103",
        )
        config = store.batch_config("ranked-subset-rest")
        assert config["selection_semantics"] == "exact_case_dev_ranked_subset"
        assert config["selected_candidate_count"] == 2

    assert legalforecast_cli.main(args) == 0
    assert json.loads(summary.read_text())["already_seeded"] is True


def test_sealed_unresolved_manifest_authorizes_only_fresh_unresolved_subset(
    tmp_path: Path,
) -> None:
    docket_ids = ("101", "102", "103")
    source_store = _opinion_source_store(tmp_path, docket_ids=docket_ids)
    enrichment_root = _run_enrichment(
        tmp_path,
        source_store=source_store,
        docket_ids=docket_ids,
    )
    firecrawl_store = _target_store(tmp_path, name="firecrawl-source.sqlite3")
    original_card = tmp_path / "original-subset-card.json"
    assert (
        legalforecast_cli.main(
            _subset_selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=firecrawl_store,
                run_card=original_card,
                summary=tmp_path / "original-subset-summary.json",
                docket_ids=("102", "103"),
            )
        )
        == 0
    )
    ranked_path = enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    original_card_sha256 = hashlib.sha256(original_card.read_bytes()).hexdigest()
    source_raw_root = tmp_path / "source-pages"
    source_raw_root.mkdir()
    with CycleAcquisitionStore(firecrawl_store) as store:
        selected_records = verify_authenticated_ranked_firecrawl_handoff(
            store=store,
            parent_batch_id="ranked-subset-rest",
            ranked_path=ranked_path,
            selection_run_card_path=original_card,
            expected_selection_run_card_sha256=original_card_sha256,
            max_candidates=2,
        )
        targets = ranked_docket_targets(selected_records, limit=2)
        config = {
            "purpose": "ranked-complete-docket-acquisition",
            "decision_anchor": "2026-06-30",
            "max_pages_per_docket": 2,
            "raw_artifact_root": str(source_raw_root.resolve()),
            "firecrawl_proxy": "enhanced",
            "firecrawl_force_browser": False,
            "firecrawl_max_credits_per_scrape": 5,
            "workers": 10,
            "max_attempts_per_page": 3,
            "provider_breaker_threshold": 5,
            "target_http_pressure_policy_version": (
                "courtlistener-target-http-202-aimd-v1"
            ),
        }
        run_digest = store.ensure_firecrawl_run(
            "budget-exhausted",
            batch_id="ranked-subset-rest",
            config=config,
            credit_cap=10,
            reserved_credits_per_attempt=5,
        )
        for target in targets:
            source_url = f"{target.docket_url}?order_by=desc&page=1"
            target_id = (
                "docket-"
                + hashlib.sha256(f"{target.docket_id}:1".encode()).hexdigest()[:24]
            )
            store.ensure_firecrawl_target(
                "budget-exhausted",
                target_id=target_id,
                target_kind="docket",
                source_url=source_url,
                ordinal=target.rank,
            )
            attempt = store.authorize_firecrawl_attempt(
                "budget-exhausted",
                target_id=target_id,
                page_number=1,
                request_url=source_url,
            )
            if target.docket_id == "102":
                store.finalize_firecrawl_attempt(
                    attempt.attempt_id,
                    status="target_error",
                    reported_credits=5,
                    proxy_used="stealth",
                    provider_http_status=200,
                    target_http_status=404,
                    failure_code="target_http_status_invalid",
                    failure_message="terminal 404",
                    failure_transient=False,
                    failure_response_sha256="a" * 64,
                )
                store.set_firecrawl_target_status(
                    "budget-exhausted", target_id, "terminal_error"
                )
            else:
                store.finalize_firecrawl_attempt(
                    attempt.attempt_id,
                    status="provider_error",
                    provider_http_status=500,
                    failure_code="provider_server_error",
                    failure_message="provider unavailable",
                    failure_transient=True,
                    failure_response_sha256="b" * 64,
                )
                store.set_firecrawl_target_status(
                    "budget-exhausted", target_id, "in_progress"
                )
        cycle_hash = store.cycle_hash

    seal_root = tmp_path / "seal"
    seal_args = [
        "acquisition",
        "seal-ranked-firecrawl-run",
        "--source-cycle-store",
        str(firecrawl_store),
        "--run-id",
        "budget-exhausted",
        "--ranked",
        str(ranked_path),
        "--ranked-selection-run-card",
        str(original_card),
        "--expected-ranked-selection-run-card-sha256",
        original_card_sha256,
        "--max-candidates",
        "2",
        "--max-pages-per-docket",
        "2",
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--expected-cycle-hash",
        cycle_hash,
        "--expected-run-config-sha256",
        run_digest,
        "--expected-credit-cap",
        "10",
        "--expected-total-prior-authorized-firecrawl-credits",
        "10",
        "--authorized-fresh-recovery-credit-cap",
        "10",
        "--output-root",
        str(seal_root),
        "--execute",
    ]
    assert legalforecast_cli.main(seal_args) == 0
    unresolved_manifest = seal_root / "firecrawl-unresolved-partition.jsonl"
    seal_card = seal_root / "run-cards" / "seal-ranked-firecrawl-run.json"

    zero_seal_root = tmp_path / "zero-authority-seal"
    zero_seal_args = list(seal_args)
    zero_seal_args[zero_seal_args.index(str(seal_root))] = str(zero_seal_root)
    fresh_cap_index = zero_seal_args.index("--authorized-fresh-recovery-credit-cap")
    zero_seal_args[fresh_cap_index + 1] = "0"
    assert legalforecast_cli.main(zero_seal_args) == 0
    zero_manifest = zero_seal_root / "firecrawl-unresolved-partition.jsonl"
    zero_card = zero_seal_root / "run-cards" / "seal-ranked-firecrawl-run.json"
    zero_target = _target_store(tmp_path, name="zero-authority-target.sqlite3")
    zero_args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=zero_target,
        run_card=tmp_path / "zero-authority-card.json",
        summary=tmp_path / "zero-authority-summary.json",
        docket_ids=(),
    )
    zero_args.extend(
        (
            "--sealed-unresolved-manifest",
            str(zero_manifest),
            "--expected-sealed-unresolved-manifest-sha256",
            hashlib.sha256(zero_manifest.read_bytes()).hexdigest(),
            "--recovery-seal-run-card",
            str(zero_card),
            "--expected-recovery-seal-run-card-sha256",
            hashlib.sha256(zero_card.read_bytes()).hexdigest(),
            "--recovery-source-cycle-store",
            str(firecrawl_store),
        )
    )
    assert legalforecast_cli.main(zero_args) == 2
    _assert_no_target_rows(zero_target)

    hardlinked_target = tmp_path / "hardlinked-recovery-target.sqlite3"
    hardlinked_target_lock = Path(f"{hardlinked_target}.lock")
    hardlinked_target.hardlink_to(firecrawl_store)
    hardlinked_target_lock.hardlink_to(Path(f"{firecrawl_store}.lock"))
    hardlinked_args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=hardlinked_target,
        run_card=tmp_path / "hardlinked-recovery-card.json",
        summary=tmp_path / "hardlinked-recovery-summary.json",
        docket_ids=(),
    )
    hardlinked_args.extend(
        (
            "--sealed-unresolved-manifest",
            str(unresolved_manifest),
            "--expected-sealed-unresolved-manifest-sha256",
            hashlib.sha256(unresolved_manifest.read_bytes()).hexdigest(),
            "--recovery-seal-run-card",
            str(seal_card),
            "--expected-recovery-seal-run-card-sha256",
            hashlib.sha256(seal_card.read_bytes()).hexdigest(),
            "--recovery-source-cycle-store",
            str(firecrawl_store),
        )
    )
    source_before = firecrawl_store.read_bytes()
    assert legalforecast_cli.main(hardlinked_args) == 2
    assert firecrawl_store.read_bytes() == source_before
    hardlinked_target.unlink()
    hardlinked_target_lock.unlink()

    recovery_target = _target_store(tmp_path, name="recovery-target.sqlite3")
    recovery_card = tmp_path / "recovery-subset-card.json"
    args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=recovery_target,
        run_card=recovery_card,
        summary=tmp_path / "recovery-subset-summary.json",
        docket_ids=(),
    )
    args.extend(
        (
            "--sealed-unresolved-manifest",
            str(unresolved_manifest),
            "--expected-sealed-unresolved-manifest-sha256",
            hashlib.sha256(unresolved_manifest.read_bytes()).hexdigest(),
            "--recovery-seal-run-card",
            str(seal_card),
            "--expected-recovery-seal-run-card-sha256",
            hashlib.sha256(seal_card.read_bytes()).hexdigest(),
            "--recovery-source-cycle-store",
            str(firecrawl_store),
        )
    )

    assert legalforecast_cli.main(args) == 0
    frozen = json.loads(recovery_card.read_text())
    assert frozen["selected_docket_ids"] == ["103"]
    assert frozen["recovery_authority"]["terminal_dockets_reauthorized"] == 0
    with CycleAcquisitionStore(recovery_target) as store:
        assert store.candidate_ids("ranked-subset-rest") == (
            "courtlistener-docket-103",
        )
        authority = store.batch_config("ranked-subset-rest")[
            "ranked_recovery_authority"
        ]
    assert authority["selected_docket_ids"] == ["103"]
    assert authority["terminal_dockets_reauthorized"] == 0
    empty_firecrawl_fixture = tmp_path / "empty-firecrawl.jsonl"
    empty_firecrawl_fixture.write_text("")
    recovery_acquire_args = [
        "acquisition",
        "acquire-ranked-firecrawl-dockets",
        "--output-root",
        str(tmp_path / "recovery-acquire-plan"),
        "--cycle-store",
        str(recovery_target),
        "--parent-batch-id",
        "ranked-subset-rest",
        "--selected-batch-id",
        "recovery-firecrawl",
        "--run-id",
        "recovery-firecrawl-run",
        "--ranked",
        str(ranked_path),
        "--ranked-selection-run-card",
        str(recovery_card),
        "--expected-ranked-selection-run-card-sha256",
        hashlib.sha256(recovery_card.read_bytes()).hexdigest(),
        "--max-candidates",
        "1",
        "--max-pages-per-docket",
        "2",
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--firecrawl-fixture",
        str(empty_firecrawl_fixture),
        "--credit-cap",
        "11",
    ]
    assert legalforecast_cli.main(recovery_acquire_args) == 2
    recovery_acquire_args[-1] = "10"
    assert legalforecast_cli.main(recovery_acquire_args) == 0

    terminal_manifest = seal_root / "firecrawl-terminal-partition.jsonl"
    terminal_target = _target_store(tmp_path, name="terminal-target.sqlite3")
    terminal_card = tmp_path / "terminal-screening-card.json"
    terminal_args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=terminal_target,
        run_card=terminal_card,
        summary=tmp_path / "terminal-screening-summary.json",
        docket_ids=(),
    )
    terminal_args.extend(
        (
            "--sealed-terminal-manifest",
            str(terminal_manifest),
            "--expected-sealed-terminal-manifest-sha256",
            hashlib.sha256(terminal_manifest.read_bytes()).hexdigest(),
            "--recovery-seal-run-card",
            str(seal_card),
            "--expected-recovery-seal-run-card-sha256",
            hashlib.sha256(seal_card.read_bytes()).hexdigest(),
            "--recovery-source-cycle-store",
            str(firecrawl_store),
        )
    )
    assert legalforecast_cli.main(terminal_args) == 0
    with CycleAcquisitionStore(terminal_target) as store:
        assert store.candidate_ids("ranked-subset-rest") == (
            "courtlistener-docket-102",
        )
        with pytest.raises(
            BudgetedDocketAcquisitionError,
            match="terminal or zero-cap recovery partitions",
        ):
            verify_authenticated_ranked_firecrawl_handoff(
                store=store,
                parent_batch_id="ranked-subset-rest",
                ranked_path=ranked_path,
                selection_run_card_path=terminal_card,
                expected_selection_run_card_sha256=hashlib.sha256(
                    terminal_card.read_bytes()
                ).hexdigest(),
                max_candidates=1,
            )

    rejected_target = _target_store(tmp_path, name="terminal-rejected.sqlite3")
    rejected_args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=rejected_target,
        run_card=tmp_path / "terminal-rejected-card.json",
        summary=tmp_path / "terminal-rejected-summary.json",
        docket_ids=(),
    )
    rejected_args.extend(
        (
            "--sealed-unresolved-manifest",
            str(terminal_manifest),
            "--expected-sealed-unresolved-manifest-sha256",
            hashlib.sha256(terminal_manifest.read_bytes()).hexdigest(),
            "--recovery-seal-run-card",
            str(seal_card),
            "--expected-recovery-seal-run-card-sha256",
            hashlib.sha256(seal_card.read_bytes()).hexdigest(),
            "--recovery-source-cycle-store",
            str(firecrawl_store),
        )
    )
    assert legalforecast_cli.main(rejected_args) == 2
    _assert_no_target_rows(rejected_target)

    unresolved_manifest.write_text(
        unresolved_manifest.read_text().replace(
            '"docket_id": "103"', '"docket_id": "102"'
        )
    )
    tampered_manifest_target = _target_store(
        tmp_path, name="tampered-manifest-target.sqlite3"
    )
    tampered_manifest_args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=tampered_manifest_target,
        run_card=tmp_path / "tampered-manifest-card.json",
        summary=tmp_path / "tampered-manifest-summary.json",
        docket_ids=(),
    )
    tampered_manifest_args.extend(
        (
            "--sealed-unresolved-manifest",
            str(unresolved_manifest),
            "--expected-sealed-unresolved-manifest-sha256",
            hashlib.sha256(unresolved_manifest.read_bytes()).hexdigest(),
            "--recovery-seal-run-card",
            str(seal_card),
            "--expected-recovery-seal-run-card-sha256",
            hashlib.sha256(seal_card.read_bytes()).hexdigest(),
            "--recovery-source-cycle-store",
            str(firecrawl_store),
        )
    )
    assert legalforecast_cli.main(tampered_manifest_args) == 2
    _assert_no_target_rows(tampered_manifest_target)

    tampered_seal_card = tmp_path / "tampered-seal-card.json"
    tampered_card_payload = json.loads(seal_card.read_text())
    tampered_card_payload["unresolved_count"] = 99
    tampered_seal_card.write_text(
        json.dumps(tampered_card_payload, indent=2, sort_keys=True) + "\n"
    )
    tampered_card_target = _target_store(tmp_path, name="tampered-card-target.sqlite3")
    tampered_card_args = _subset_selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=tampered_card_target,
        run_card=tmp_path / "tampered-card-selection.json",
        summary=tmp_path / "tampered-card-summary.json",
        docket_ids=(),
    )
    tampered_card_args.extend(
        (
            "--sealed-terminal-manifest",
            str(terminal_manifest),
            "--expected-sealed-terminal-manifest-sha256",
            hashlib.sha256(terminal_manifest.read_bytes()).hexdigest(),
            "--recovery-seal-run-card",
            str(tampered_seal_card),
            "--expected-recovery-seal-run-card-sha256",
            hashlib.sha256(tampered_seal_card.read_bytes()).hexdigest(),
            "--recovery-source-cycle-store",
            str(firecrawl_store),
        )
    )
    assert legalforecast_cli.main(tampered_card_args) == 2
    _assert_no_target_rows(tampered_card_target)


@pytest.mark.parametrize(
    "docket_ids",
    [
        ("102", "102"),
        ("102", "999"),
    ],
)
def test_select_case_dev_ranked_subset_rejects_invalid_exact_set_before_write(
    tmp_path: Path,
    docket_ids: tuple[str, ...],
) -> None:
    source_ids = ("101", "102", "103")
    source_store = _opinion_source_store(tmp_path, docket_ids=source_ids)
    enrichment_root = _run_enrichment(
        tmp_path,
        source_store=source_store,
        docket_ids=source_ids,
    )
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _subset_selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "subset-run-card.json",
                summary=tmp_path / "subset-summary.json",
                docket_ids=docket_ids,
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


def test_case_dev_enrichment_uses_frozen_anchor_for_narrower_source_window(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(
        tmp_path,
        search_window_start="2026-07-10",
    )
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)

    ranked = _read_jsonl(
        enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    )
    run_card = json.loads(
        (enrichment_root / "run-cards" / "enrich-recap-case-dev.json").read_text()
    )
    assert {record["eligibility_anchor"] for record in ranked} == {"2026-06-30"}
    assert run_card["eligibility_anchor"] == "2026-06-30"


def test_select_case_dev_ranked_rejects_ranked_tamper_before_target_write(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    ranked_path = enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    ranked = _read_jsonl(ranked_path)
    ranked[0]["missing_required_document_count"] = 99
    _write_jsonl(ranked_path, ranked)
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_legacy_ranking_policy(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    ranked_path = enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    run_card_path = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    ranked = _read_jsonl(ranked_path)
    ranked[0].pop("ranking_policy_version")
    _write_jsonl(ranked_path, ranked)
    run_card = json.loads(run_card_path.read_text())
    run_card["ranked_output_sha256"] = hashlib.sha256(
        ranked_path.read_bytes()
    ).hexdigest()
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    expected_run_card_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=expected_run_card_sha256,
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_forged_rank_and_recomputed_run_card(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    ranked_path = enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    run_card_path = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    ranked = _read_jsonl(ranked_path)
    ranked.reverse()
    ranked[0].update(
        {
            "structural_priority_tier": 0,
            "decision_signal_priority_tier": 0,
            "missing_required_document_count": 0,
            "ranking_key": [0, 0, 0, 3, "101"],
        }
    )
    ranked[1].update(
        {
            "structural_priority_tier": 2,
            "decision_signal_priority_tier": 3,
            "ranking_key": [2, 3, 0, 3, "102"],
        }
    )
    _write_jsonl(ranked_path, ranked)
    forged_run_card = json.loads(run_card_path.read_text())
    forged_run_card["ranked_output_sha256"] = hashlib.sha256(
        ranked_path.read_bytes()
    ).hexdigest()
    run_card_path.write_text(json.dumps(forged_run_card, sort_keys=True) + "\n")
    expected_run_card_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=expected_run_card_sha256,
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    [
        ("ranking_policy_version", "legacy-cost-only-v1"),
        ("eligibility_anchor", "2026-07-01"),
    ],
)
def test_select_case_dev_ranked_rejects_forged_run_card_semantics(
    tmp_path: Path,
    field_name: str,
    forged_value: str,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    run_card_path = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    run_card = json.loads(run_card_path.read_text())
    run_card[field_name] = forged_value
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    expected_run_card_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=expected_run_card_sha256,
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_source_metadata_forgery(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    ranked_path = enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    run_card_path = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    ranked = _read_jsonl(ranked_path)
    forged = next(
        record
        for record in ranked
        if record["identity"]["courtlistener_docket_id"] == "102"
    )
    forged["screening_metadata"]["court_id"] = "ca9"
    forged["structural_priority_tier"] = 2
    forged["structural_priority_reason"] = "hard_structural_exclusion_metadata"
    forged["ranking_key"][0] = 2
    ranked.sort(key=lambda record: record["ranking_key"])
    _write_jsonl(ranked_path, ranked)
    run_card = json.loads(run_card_path.read_text())
    run_card["ranked_output_sha256"] = hashlib.sha256(
        ranked_path.read_bytes()
    ).hexdigest()
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    expected_run_card_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
                expected_enrichment_run_card_sha256=expected_run_card_sha256,
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_existing_card_before_target_mutation(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    first_target = _target_store(tmp_path, name="first-target.sqlite3")
    run_card = tmp_path / "selection-run-card.json"
    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=first_target,
                run_card=run_card,
                summary=tmp_path / "first-summary.json",
            )
        )
        == 0
    )
    tampered = json.loads(run_card.read_text())
    tampered["target_cycle_hash"] = "0" * 64
    run_card.write_text(json.dumps(tampered, sort_keys=True) + "\n")
    fresh_target = _target_store(tmp_path, name="fresh-target.sqlite3")

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=fresh_target,
                run_card=run_card,
                summary=tmp_path / "second-summary.json",
            )
        )
        == 2
    )
    _assert_no_target_rows(fresh_target)


def test_select_case_dev_ranked_rejects_completed_enrichment_with_failure(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    fixture = tmp_path / "case-dev-with-permanent-failure.jsonl"
    invalid = _case_dev_response("101", entries=[])
    invalid["payload"] = {
        "docket": {
            "id": "999",
            "url": "https://www.courtlistener.com/api/rest/v4/dockets/999/",
            "entries": [],
        }
    }
    _write_jsonl(
        fixture,
        [
            invalid,
            _case_dev_response("102", entries=[]),
        ],
    )
    enrichment_root = tmp_path / "enrichment-with-failure"
    assert (
        legalforecast_cli.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(enrichment_root),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "opinion-source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=tmp_path / "selection-run-card.json",
                summary=tmp_path / "selection-summary.json",
            )
        )
        == 2
    )
    _assert_no_target_rows(target_store)


@pytest.mark.parametrize(
    ("run_card_locator", "summary_locator"),
    [
        ("shared-output", "shared-output"),
        ("source-store", "fresh-summary"),
        ("source-store-lock", "fresh-summary"),
        ("fresh-card", "source-projection"),
        ("cycle-store", "fresh-summary"),
        ("fresh-card", "cycle-store-lock"),
    ],
)
def test_select_case_dev_ranked_rejects_output_aliases_before_target_mutation(
    tmp_path: Path,
    run_card_locator: str,
    summary_locator: str,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    source_projection = (
        enrichment_root / "checkpoints" / "case-dev-recap-source-projection.jsonl"
    )
    target_store = _target_store(tmp_path)
    paths = {
        "shared-output": tmp_path / "shared-output.json",
        "source-store": source_store,
        "source-store-lock": Path(f"{source_store}.lock"),
        "source-projection": source_projection,
        "cycle-store": target_store,
        "cycle-store-lock": Path(f"{target_store}.lock"),
        "fresh-card": tmp_path / "fresh-card.json",
        "fresh-summary": tmp_path / "fresh-summary.json",
    }
    protected_bytes = {
        path: path.read_bytes()
        for path in (
            source_store,
            Path(f"{source_store}.lock"),
            source_projection,
            target_store,
            Path(f"{target_store}.lock"),
        )
        if path.exists()
    }

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=paths[run_card_locator],
                summary=paths[summary_locator],
            )
        )
        == 2
    )
    assert all(
        path.read_bytes() == payload for path, payload in protected_bytes.items()
    )
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_rejects_hardlinked_output_before_target_mutation(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    ranked_path = enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    ranked_bytes = ranked_path.read_bytes()
    hardlinked_run_card = tmp_path / "hardlinked-run-card.json"
    hardlinked_run_card.hardlink_to(ranked_path)
    target_store = _target_store(tmp_path)

    assert (
        legalforecast_cli.main(
            _selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=hardlinked_run_card,
                summary=tmp_path / "selection-summary.json",
            )
        )
        == 2
    )
    assert ranked_path.read_bytes() == ranked_bytes
    _assert_no_target_rows(target_store)


def test_select_case_dev_ranked_replays_terminal_page_commitment(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    target_store = _target_store(tmp_path)
    run_card = tmp_path / "selection-run-card.json"
    summary = tmp_path / "selection-summary.json"
    args = _selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=target_store,
        run_card=run_card,
        summary=summary,
    )
    assert legalforecast_cli.main(args) == 0
    with sqlite3.connect(target_store) as connection:
        connection.execute(
            "UPDATE search_pages SET response_hash = ? WHERE batch_id = ?",
            ("0" * 64, "ranked-rest"),
        )
        connection.commit()

    assert legalforecast_cli.main(args) == 2


def test_select_case_dev_ranked_rejects_wrong_terminal_materialization(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    target_store = _target_store(tmp_path)
    run_card = tmp_path / "selection-run-card.json"
    summary = tmp_path / "selection-summary.json"
    args = _selection_args(
        source_store=source_store,
        enrichment_root=enrichment_root,
        target_store=target_store,
        run_card=run_card,
        summary=summary,
    )
    assert legalforecast_cli.main(args) == 0
    with sqlite3.connect(target_store) as connection:
        connection.execute(
            "INSERT INTO candidates(candidate_id, first_batch_id, discovered_at) "
            "VALUES (?, ?, ?)",
            ("courtlistener-docket-999", "ranked-rest", "2026-07-15T00:00:00Z"),
        )
        connection.execute(
            "UPDATE discovery_hits SET candidate_id = ?, payload_json = ? "
            "WHERE batch_id = ?",
            ("courtlistener-docket-999", "{}", "ranked-rest"),
        )
        connection.commit()

    assert legalforecast_cli.main(args) == 2


def test_project_case_dev_opinion_source_rejects_malformed_docket_id() -> None:
    hit = DirectSearchHitProvenance(
        provider_hit_id="cluster-501",
        query_term='"motion to dismiss"',
        payload_sha256="0" * 64,
    )
    lead = DirectSearchLead(
        docket_id=cast(str, None),
        source_provider_hit_id=hit.provider_hit_id,
        source_query_term=hit.query_term,
        source_payload_sha256=hit.payload_sha256,
        source_hits=(hit,),
        court_id="dcd",
        docket_number="1:25-cv-00101",
        case_name="Example v. Example",
        decision_entry_evidence=None,
    )
    source = DirectSearchSeedSource(
        source_batch_id="opinion-source",
        source_batch_digest="1" * 64,
        source_cycle_hash="2" * 64,
        source_schema_version="legalforecast.courtlistener_opinion_discovery.v1",
        source_search_type="o",
        source_available_only_present=False,
        source_available_only=None,
        source_query_expression_present=False,
        source_query_expression=None,
        source_query_terms=(hit.query_term,),
        source_candidate_set_sha256=_canonical_sha256([lead.commitment_record()]),
        source_hit_set_sha256=_canonical_sha256(
            [{"docket_id": lead.docket_id, "source_hit": hit.to_record()}]
        ),
        source_eligibility_anchor="2026-06-30",
        search_window_start=date(2026, 6, 30),
        search_window_end=date(2026, 7, 15),
        leads=(lead,),
    )

    with pytest.raises(RecapApiBatchDriverError, match="invalid docket identity"):
        project_case_dev_opinion_source(source)


def _selection_args(
    *,
    source_store: Path,
    enrichment_root: Path,
    target_store: Path,
    run_card: Path,
    summary: Path,
    expected_enrichment_run_card_sha256: str | None = None,
) -> list[str]:
    enrichment_run_card = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    expected_digest = (
        expected_enrichment_run_card_sha256
        or hashlib.sha256(enrichment_run_card.read_bytes()).hexdigest()
    )
    return [
        "batch-002",
        "select-case-dev-ranked",
        "--source-store",
        str(source_store),
        "--source-batch-id",
        "opinion-source",
        "--source-projection",
        str(enrichment_root / "checkpoints" / "case-dev-recap-source-projection.jsonl"),
        "--ranked",
        str(enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"),
        "--failures",
        str(enrichment_root / "checkpoints" / "case-dev-recap-failures.jsonl"),
        "--enrichment-run-card",
        str(enrichment_run_card),
        "--expected-enrichment-run-card-sha256",
        expected_digest,
        "--cycle-store",
        str(target_store),
        "--batch-id",
        "ranked-rest",
        "--top-n",
        "1",
        "--run-card-output",
        str(run_card),
        "--summary-output",
        str(summary),
    ]


def _subset_selection_args(
    *,
    source_store: Path,
    enrichment_root: Path,
    target_store: Path,
    run_card: Path,
    summary: Path,
    docket_ids: tuple[str, ...],
) -> list[str]:
    enrichment_run_card = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    args = [
        "batch-002",
        "select-case-dev-ranked-subset",
        "--source-store",
        str(source_store),
        "--source-batch-id",
        "opinion-source",
        "--source-projection",
        str(enrichment_root / "checkpoints" / "case-dev-recap-source-projection.jsonl"),
        "--ranked",
        str(enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"),
        "--failures",
        str(enrichment_root / "checkpoints" / "case-dev-recap-failures.jsonl"),
        "--enrichment-run-card",
        str(enrichment_run_card),
        "--expected-enrichment-run-card-sha256",
        hashlib.sha256(enrichment_run_card.read_bytes()).hexdigest(),
        "--cycle-store",
        str(target_store),
        "--batch-id",
        "ranked-subset-rest",
        "--run-card-output",
        str(run_card),
        "--summary-output",
        str(summary),
    ]
    for docket_id in docket_ids:
        args.extend(("--docket-id", docket_id))
    return args


def _run_enrichment(
    tmp_path: Path,
    *,
    source_store: Path,
    docket_ids: tuple[str, ...] = ("101", "102"),
    eligible_docket_ids: tuple[str, ...] = ("102",),
) -> Path:
    fixture = tmp_path / "case-dev.jsonl"
    responses = [
        _case_dev_response(
            docket_id,
            entries=(
                [
                    _entry("entry-1", 1, "Complaint", "doc-1"),
                    _entry("entry-5", 5, "Motion to Dismiss", "doc-5"),
                    _entry(
                        "entry-10",
                        10,
                        "Order denying Motion to Dismiss",
                        "doc-10",
                    ),
                ]
                if docket_id in eligible_docket_ids
                else []
            ),
        )
        for docket_id in docket_ids
    ]
    _write_jsonl(fixture, responses)
    output_root = tmp_path / "enrichment"
    assert (
        legalforecast_cli.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "opinion-source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )
    return output_root


def _run_terminal_exclusion_enrichment(
    tmp_path: Path,
    *,
    source_store: Path,
) -> Path:
    fixture = tmp_path / "case-dev-with-terminal-exclusion.jsonl"
    full_page = [
        _entry(f"entry-{number}", number, f"Entry {number}", f"doc-{number}")
        for number in range(1, 101)
    ]
    _write_jsonl(
        fixture,
        [
            _case_dev_response("101", entries=full_page),
            _case_dev_response("102", entries=[]),
        ],
    )
    output_root = tmp_path / "enrichment-with-terminal-exclusion"
    assert (
        legalforecast_cli.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "opinion-source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )
    return output_root


def _rewrite_as_historical_opinion_enrichment(enrichment_root: Path) -> str:
    """Reproduce the authenticated pre-35a5fe1 type-o artifact representation."""

    historical_authority_fields = {
        "source_batch_id",
        "source_batch_digest",
        "source_cycle_hash",
        "source_search_type",
        "source_candidate_set_sha256",
        "source_hits",
    }
    projection_path = (
        enrichment_root / "checkpoints/case-dev-recap-source-projection.jsonl"
    )
    ranked_path = enrichment_root / "checkpoints/case-dev-recap-ranked.jsonl"
    run_card_path = enrichment_root / "run-cards/enrich-recap-case-dev.json"
    projection = _read_jsonl(projection_path)
    ranked = _read_jsonl(ranked_path)
    for record in [*projection, *ranked]:
        lineage = cast(dict[str, object], record["source_lineage"])
        for field_name in tuple(lineage):
            if field_name.startswith("source_") and (
                field_name not in historical_authority_fields
            ):
                lineage.pop(field_name)
    _write_jsonl(projection_path, projection)
    _write_jsonl(ranked_path, ranked)
    run_card = json.loads(run_card_path.read_text())
    for field_name in tuple(run_card):
        if field_name.startswith("source_") and (
            field_name not in historical_authority_fields
        ):
            run_card.pop(field_name)
    run_card["source_projection_sha256"] = hashlib.sha256(
        projection_path.read_bytes()
    ).hexdigest()
    run_card["ranked_output_sha256"] = hashlib.sha256(
        ranked_path.read_bytes()
    ).hexdigest()
    run_card_path.write_text(json.dumps(run_card, sort_keys=True) + "\n")
    return hashlib.sha256(run_card_path.read_bytes()).hexdigest()


def _opinion_source_store(
    tmp_path: Path,
    *,
    search_window_start: str = "2026-06-30",
    docket_ids: tuple[str, ...] = ("101", "102"),
    search_type: str = "o",
    name: str = "source.sqlite3",
    cycle_policy: dict[str, object] | None = None,
) -> Path:
    path = tmp_path / name
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(cycle_policy or _cycle_policy())
        term = '"motion to dismiss"'
        config: dict[str, object] = {
            "schema_version": (
                "legalforecast.courtlistener_unrestricted_recap.v1"
                if search_type == "r"
                else "legalforecast.courtlistener_opinion_discovery.v1"
            ),
            "provider": "courtlistener",
            "search_type": search_type,
            "query_terms": [term],
            "search_window_start": search_window_start,
            "search_window_end": "2026-07-15",
        }
        if search_type == "r":
            config.update(
                {
                    "available_only": "omitted",
                    "query_expression": (
                        "{term} AND entry_date_filed:[{start} TO {end}]"
                    ),
                    "search_page_size": 20,
                }
            )
        store.ensure_batch(
            "opinion-source",
            config,
        )
        store.ensure_terms("opinion-source", (term,))
        store.commit_search_page(
            "opinion-source",
            term,
            None,
            [
                _opinion_hit(docket_id, str(400 + int(docket_id)))
                for docket_id in docket_ids
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
    return path


def _target_store(tmp_path: Path, *, name: str = "target.sqlite3") -> Path:
    path = tmp_path / name
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(
            legalforecast_cli._cycle_acquisition_policy(anchor=_anchor())
        )
    return path


def _cycle_policy() -> dict[str, object]:
    return {"schema_version": "test", "eligibility_anchor": "2026-06-30"}


def _anchor() -> date:
    return date(2026, 6, 30)


def _opinion_hit(docket_id: str, cluster_id: str) -> dict[str, object]:
    return {
        "provider_hit_id": cluster_id,
        "candidate_id": docket_id,
        "payload": {
            "docket_id": docket_id,
            "court_id": "dcd",
            "docket_number": f"1:25-cv-{int(docket_id):05d}",
            "case_name": f"Example {docket_id} v. Example",
            "opinion_discovery_evidence": {
                "cluster_id": cluster_id,
                "absolute_url": f"/opinion/{cluster_id}/example/",
                "date_filed": "2026-07-14",
            },
        },
    }


def _case_dev_response(
    docket_id: str, *, entries: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "method": "POST",
        "path": "/legal/v1/docket",
        "params": {
            "type": "lookup",
            "docketId": docket_id,
            "includeEntries": True,
            "limit": 100,
        },
        "status_code": 200,
        "payload": {
            "docket": {
                "id": docket_id,
                "url": (
                    f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/"
                ),
                "caseName": f"Example {docket_id} v. Example",
                "courtId": "dcd",
                "docketNumber": f"1:25-cv-{int(docket_id):05d}",
                "entries": entries,
            }
        },
    }


def _entry(
    entry_id: str, entry_number: int, description: str, document_id: str
) -> dict[str, object]:
    return {
        "id": entry_id,
        "entryNumber": entry_number,
        "date": "2026-07-14",
        "description": description,
        "documents": [
            {
                "id": document_id,
                "description": description,
                "pdfUrl": f"https://storage.courtlistener.com/{document_id}.pdf",
                "isAvailable": True,
            }
        ],
    }


def _terminal_promotion_fixture(
    tmp_path: Path,
    *,
    source_docket_id: str | None = None,
    provisional_success_count: int | None = None,
) -> dict[str, object]:
    selected_docket_ids = ("102", "103", "104", "105", "106")
    terminal_source_docket_ids = ("101", *selected_docket_ids)
    source_success_docket_ids = (
        selected_docket_ids if source_docket_id is None else (source_docket_id,)
    )
    bundle_root = tmp_path / "source-bundle"
    bundle_root.mkdir()
    source_policy = legalforecast_cli._cycle_acquisition_policy(anchor=_anchor())
    source_policy["fixture_generation"] = "provisional-source"
    source_store = _opinion_source_store(
        bundle_root,
        cycle_policy=source_policy,
        docket_ids=terminal_source_docket_ids,
    )
    enrichment_root = _run_enrichment(
        bundle_root,
        source_store=source_store,
        docket_ids=terminal_source_docket_ids,
        eligible_docket_ids=selected_docket_ids,
    )
    target_store = _target_store(tmp_path)
    selection_card = tmp_path / "selection-run-card.json"
    assert (
        legalforecast_cli.main(
            _subset_selection_args(
                source_store=source_store,
                enrichment_root=enrichment_root,
                target_store=target_store,
                run_card=selection_card,
                summary=tmp_path / "selection-summary.json",
                docket_ids=selected_docket_ids,
            )
        )
        == 0
    )
    selection = json.loads(selection_card.read_text())
    source_root = bundle_root / "provisional-source"
    source_raw_dir = source_root / "raw-docket-html"
    source_raw_dir.mkdir(parents=True)
    raw_by_docket = {
        docket_id: _promotion_docket_html(docket_id)
        for docket_id in source_success_docket_ids
    }
    raw_paths = {
        docket_id: source_raw_dir / f"{docket_id}.html"
        for docket_id in source_success_docket_ids
    }
    for docket_id, raw_path in raw_paths.items():
        raw_path.write_text(raw_by_docket[docket_id])
    success_count = (
        len(source_success_docket_ids)
        if provisional_success_count is None
        else provisional_success_count
    )
    provisional_config: dict[str, object] = {
        "stage": "authenticated_case_dev_provisional_frontier",
        "provisional_frontier": True,
        "final_cohort_eligible": False,
        "full_source_terminal": False,
        "source_candidate_count": selection["source_candidate_count"],
        "source_candidate_set_sha256": selection["source_candidate_set_sha256"],
        "source_projection_sha256": selection["source_projection_sha256"],
        "progress_config_sha256": "a" * 64,
        "progress_sha256": "b" * 64,
        "success_count": success_count,
        "terminal_exclusion_count": 0,
        "pending_count": (selection["source_candidate_count"] - success_count),
        "success_candidate_set_sha256": "c" * 64,
        "terminal_excluded_candidate_set_sha256": "d" * 64,
        "pending_candidate_set_sha256": "e" * 64,
    }
    with CycleAcquisitionStore(source_store) as store:
        store.ensure_batch("provisional-batch", provisional_config)
        store.ensure_terms("provisional-batch", ("provisional",))
        store.commit_search_page(
            "provisional-batch",
            "provisional",
            None,
            tuple(
                DiscoveryHit(
                    provider_hit_id=f"provisional-{docket_id}",
                    candidate_id=f"courtlistener-docket-{docket_id}",
                    payload={"case_id": f"courtlistener-docket-{docket_id}"},
                )
                for docket_id in source_success_docket_ids
            ),
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        source_cycle_hash = store.cycle_hash
    lineage = provisional_lineage_flags(provisional_config)
    source_successes = source_root / "firecrawl-docket-successes.jsonl"
    _write_jsonl(
        source_successes,
        [
            {
                "case_id": f"courtlistener-docket-{docket_id}",
                "candidate_id": f"courtlistener-docket-{docket_id}",
                "source_url": (
                    f"https://www.courtlistener.com/docket/{docket_id}/fixture/"
                ),
                "docket_id": docket_id,
                "raw_html_path": str(raw_paths[docket_id]),
                "raw_html_sha256": (
                    "sha256:"
                    + hashlib.sha256(raw_by_docket[docket_id].encode()).hexdigest()
                ),
                "raw_html_bytes": len(raw_by_docket[docket_id].encode()),
                "retrieved_at": "2026-07-15T12:00:00+00:00",
                "pagination_complete_for_anchor_window": True,
                "page_count": 1,
                "case_metadata": {
                    "case_id": f"courtlistener-docket-{docket_id}",
                    "court_id": "dcd",
                    "docket_number": f"1:25-cv-{int(docket_id):05d}",
                    "case_name": f"Example {docket_id} v. Example",
                    "source_url": (
                        f"https://www.courtlistener.com/docket/{docket_id}/fixture/"
                    ),
                },
                **lineage,
            }
            for docket_id in source_success_docket_ids
        ],
    )
    source_exclusions = source_root / "firecrawl-docket-exclusions.jsonl"
    _write_jsonl(source_exclusions, [])
    screen_root = source_root / "screen"
    assert (
        legalforecast_cli.main(
            [
                "acquisition",
                "screen-firecrawl-dockets",
                "--output-root",
                str(screen_root),
                "--cycle-store",
                str(source_store),
                "--batch-id",
                "provisional-batch",
                "--successes",
                str(source_successes),
                "--fetch-exclusions",
                str(source_exclusions),
                "--raw-html-dir",
                str(source_raw_dir),
                "--decision-filed-on-or-after",
                "2026-06-30",
                "--snapshot-id",
                "provisional-screened",
                "--execute",
            ]
        )
        == 0
    )
    source_snapshot = screen_root / "snapshots/provisional-screened"
    source_screen_card = screen_root / "run-cards/screen-firecrawl-dockets.json"
    with CycleAcquisitionStore(target_store) as store:
        target_cycle_hash = store.cycle_hash
    return {
        "source_store": source_store,
        "source_batch_id": "opinion-source",
        "source_projection": (
            enrichment_root / "checkpoints/case-dev-recap-source-projection.jsonl"
        ),
        "ranked": enrichment_root / "checkpoints/case-dev-recap-ranked.jsonl",
        "failures": enrichment_root / "checkpoints/case-dev-recap-failures.jsonl",
        "enrichment_run_card": (
            enrichment_root / "run-cards/enrich-recap-case-dev.json"
        ),
        "selection_card": selection_card,
        "selection_card_sha256": hashlib.sha256(
            selection_card.read_bytes()
        ).hexdigest(),
        "target_store": target_store,
        "target_cycle_hash": target_cycle_hash,
        "source_cycle_hash": source_cycle_hash,
        "source_bundle_root": bundle_root,
        "source_snapshot": source_snapshot,
        "source_snapshot_manifest_sha256": hashlib.sha256(
            (source_snapshot / "manifest.json").read_bytes()
        ).hexdigest(),
        "source_screen_card": source_screen_card,
        "source_screen_card_sha256": hashlib.sha256(
            source_screen_card.read_bytes()
        ).hexdigest(),
        "source_successes": source_successes,
        "source_raw": raw_paths[source_success_docket_ids[0]],
        "output_root": tmp_path / "promotion-output",
    }


def _promotion_args(fixture: dict[str, object]) -> list[str]:
    return [
        "acquisition",
        "promote-terminal-firecrawl-subset",
        "--output-root",
        str(fixture["output_root"]),
        "--source-store",
        str(fixture["source_store"]),
        "--source-batch-id",
        str(fixture["source_batch_id"]),
        "--source-projection",
        str(fixture["source_projection"]),
        "--ranked",
        str(fixture["ranked"]),
        "--failures",
        str(fixture["failures"]),
        "--enrichment-run-card",
        str(fixture["enrichment_run_card"]),
        "--expected-enrichment-run-card-sha256",
        hashlib.sha256(
            cast(Path, fixture["enrichment_run_card"]).read_bytes()
        ).hexdigest(),
        "--selection-run-card",
        str(fixture["selection_card"]),
        "--expected-selection-run-card-sha256",
        str(fixture["selection_card_sha256"]),
        "--cycle-store",
        str(fixture["target_store"]),
        "--batch-id",
        "ranked-subset-rest",
        "--expected-target-cycle-hash",
        str(fixture["target_cycle_hash"]),
        "--source-snapshot",
        str(fixture["source_snapshot"]),
        "--expected-source-snapshot-manifest-sha256",
        str(fixture["source_snapshot_manifest_sha256"]),
        "--source-screen-run-card",
        str(fixture["source_screen_card"]),
        "--expected-source-screen-run-card-sha256",
        str(fixture["source_screen_card_sha256"]),
        "--source-bundle-root",
        str(fixture["source_bundle_root"]),
        "--expected-source-cycle-hash",
        str(fixture["source_cycle_hash"]),
        "--decision-filed-on-or-after",
        "2026-06-30",
        "--snapshot-id",
        "terminal-promoted",
        "--execute",
    ]


def _promotion_docket_html(docket_id: str) -> str:
    def entry(number: int, filed_at: str, text: str, description: str) -> str:
        return (
            f'<div class="row" id="entry-{number}">'
            f'<div class="col-xs-1">{number}</div>'
            f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
            f'<div class="col-xs-8">{text}'
            '<div class="recap-documents"><div>Main Document</div>'
            f"<div>{description}</div>"
            f'<a href="https://storage.courtlistener.com/{docket_id}-{number}.pdf">'
            "Download PDF</a></div></div></div>"
        )

    return (
        f"<html><head><title>Example {docket_id} v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + entry(1, "January 2, 2026", "COMPLAINT filed", "Complaint")
        + entry(5, "February 2, 2026", "MOTION to Dismiss", "Motion to Dismiss")
        + entry(
            16,
            "July 14, 2026",
            "ORDER granting Motion to Dismiss",
            "Order on Motion to Dismiss",
        )
        + "</div></body></html>"
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _assert_no_target_rows(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM batches").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM term_progress").fetchone() == (
            0,
        )
        assert connection.execute("SELECT count(*) FROM discovery_hits").fetchone() == (
            0,
        )
