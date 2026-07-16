from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from legalforecast import cli
from legalforecast.cli import main
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore
from legalforecast.protocol import sha256_file
from legalforecast.protocol.policy_artifacts import (
    generate_labeling_policy,
    write_labeling_policy,
)
from legalforecast.unitization.review import (
    apply_unitization_reviews,
    canonical_records_sha256,
    canonical_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "model_registries" / "cycle-1-2026-06-30.json"
LABELING_REGISTRY = ROOT / "model_registries" / "cycle-1-labeling-2026-07-12.json"
JUDGE_REGISTRY = ROOT / "model_registries" / "cycle-1-stage-b-judges-2026-07-12.json"
GEMINI_KEY = "google:gemini-3.5-flash"


def test_acquisition_finalize_corpus_writes_complete_ledger_and_readiness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "inputs"
    output_root = tmp_path / "out"
    markdown_root = tmp_path / "markdown"
    inputs.mkdir()
    stage_a_run_card_args = _stub_stage_a_run_card_chain(monkeypatch, inputs)
    markdown_root.mkdir()
    (markdown_root / "decision-1.md").write_text(
        "The Court rules. Count I is dismissed.",
        encoding="utf-8",
    )

    class _Artifact:
        records = (
            {
                "candidate_id": "cand-1",
                "document_id": "decision-1",
                "text": "The Court rules. Count I is dismissed.",
            },
        )

        def verify_stage_b_audit_commitments(self, records: object) -> None:
            del records

    monkeypatch.setattr(
        cli, "verify_decision_text_artifact", lambda **kwargs: _Artifact()
    )
    _write_jsonl(
        inputs / "selection.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "court": "S.D.N.Y.",
                "target_motion_entry_numbers": [5],
                "documents": [
                    {
                        "source_document_id": "complaint-1",
                        "document_role": "operative_complaint",
                        "contains_target_outcome": False,
                    },
                    {
                        "source_document_id": "decision-1",
                        "document_role": "decision",
                        "contains_target_outcome": True,
                    },
                ],
            },
            {
                "candidate_id": "cand-incomplete",
                "case_id": "case-incomplete",
                "court": "D. Del.",
                "target_motion_entry_numbers": [5],
                "documents": [
                    {
                        "source_document_id": "missing-decision",
                        "document_role": "decision",
                        "contains_target_outcome": True,
                    }
                ],
            },
        ],
    )
    _write_jsonl(
        inputs / "parser.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "source_sha256": "0" * 64,
                "source_byte_count": 1,
                "markdown_path": (
                    "decision-1.md" if document_id == "decision-1" else "complaint.md"
                ),
            }
            for document_id in ("complaint-1", "decision-1")
        ],
    )
    _write_jsonl(
        inputs / "clearance.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "sha256": "0" * 64,
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "byte_count": 1,
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["fixture-public-docket"],
                "reviewer_id": "reviewer:test",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": "2026-07-12T18:00:00Z",
            }
            for document_id in ("complaint-1", "decision-1")
        ],
    )
    raw_units = [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "prediction_units": [{"unit_id": "unit-1", "should_score": True}],
        }
    ]
    _write_jsonl(inputs / "raw-units.jsonl", raw_units)
    finalized_units = list(
        apply_unitization_reviews(
            prediction_unit_records=raw_units,
            review_records=(),
            adjudication_records=(),
        )
    )
    _write_jsonl(
        inputs / "units.jsonl",
        finalized_units,
    )
    label = {
        "unit_id": "unit-1",
        "unit_resolution": "fully_dismissed",
        "fully_dismissed": True,
        "amendment_class": ("dismissed_without_express_amendment_opportunity"),
        "ambiguous": False,
        "label_confidence": 0.95,
        "first_written_disposition_id": "decision-1",
        "first_written_disposition_date": "2026-06-30",
        "first_written_disposition_locked": True,
        "later_procedural_changes": [],
        "supporting_citations": [
            {
                "document_id": "decision-1",
                "excerpt": "Count I is dismissed.",
            }
        ],
    }
    _write_jsonl(
        inputs / "labels.jsonl",
        [label],
    )
    judge_registry = load_model_registry(JUDGE_REGISTRY)
    judge_registry_sha = sha256_file(JUDGE_REGISTRY)
    judge_keys = [entry.registry_key for entry in judge_registry.entries]
    _write_jsonl(
        inputs / "label-audit.jsonl",
        [
            {
                "stage": "llm-label",
                "candidate_id": "cand-1",
                "status": "succeeded",
                "consensus_policy": "unanimous",
                "model_keys": judge_keys,
                "model_registry_sha256": judge_registry_sha,
                "consensus_policy_sha256": canonical_sha256(
                    {
                        "consensus_policy": "unanimous",
                        "model_keys": judge_keys,
                        "model_registry_sha256": judge_registry_sha,
                    }
                ),
                "model_outputs": [
                    {
                        "model_key": entry.registry_key,
                        "raw_output_sha256": str(index) * 64,
                        "metadata": {
                            "served_model_version": entry.model_version_or_snapshot
                        },
                        "labels": [label],
                    }
                    for index, entry in enumerate(judge_registry.entries, start=1)
                ],
                "label_audit_gate": {
                    "required": True,
                    "status": "no_unanimous_auto_labels",
                    "sample_unit_ids": [],
                },
            }
        ],
    )
    structural_registry = load_model_registry(LABELING_REGISTRY)
    gemini = next(
        entry
        for entry in structural_registry.entries
        if entry.registry_key == GEMINI_KEY
    )
    structural_registry_sha = sha256_file(LABELING_REGISTRY)
    _write_jsonl(inputs / "original-unitization-review-queue.jsonl", [])
    _write_jsonl(inputs / "stage-a-structural-flags.jsonl", [])
    _write_jsonl(
        inputs / "stage-a-structural-review-audit.jsonl",
        [
            {
                "stage": "llm-review-stage-a",
                "status": "passed",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "model_key": GEMINI_KEY,
                "model_registry_sha256": structural_registry_sha,
                "served_model_version": gemini.model_version_or_snapshot,
                "raw_prediction_units_sha256": canonical_sha256(raw_units[0]),
                "prompt_sha256": "1" * 64,
                "raw_output_sha256": "2" * 64,
                "structural_flags_sha256": canonical_records_sha256([]),
                "flag_count": 0,
                "metadata": {"served_model_version": gemini.model_version_or_snapshot},
            }
        ],
    )
    labeling_policy_path = inputs / "labeling-policy.json"
    write_labeling_policy(
        labeling_policy_path,
        generate_labeling_policy(
            cycle_id="cycle-1",
            judge_registry_path=JUDGE_REGISTRY,
            published_at=datetime(2026, 7, 14, tzinfo=UTC),
            threshold_source="Cycle 1 protocol decision, 2026-07-14",
        ),
    )
    _write_jsonl(
        inputs / "unitization-audit.jsonl",
        [
            {
                "stage": "llm-unitize",
                "candidate_id": "cand-1",
                "status": "succeeded",
                "review_items": [],
            }
        ],
    )
    _write_jsonl(inputs / "unitization-review-queue.jsonl", [])
    _write_jsonl(inputs / "unitization-adjudications.jsonl", [])
    _write_jsonl(inputs / "review-queue.jsonl", [])
    _write_jsonl(inputs / "lawyer-review-audit.jsonl", [])
    _write_jsonl(inputs / "packet-input.jsonl", [{"candidate_id": "cand-1"}])
    _write_jsonl(
        inputs / "packets.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "court": "S.D.N.Y.",
                "related_family_id": "related-fixture",
                "mdl_family_id": "mdl-fixture",
                "metadata": {
                    "nature_of_suit": "Contract",
                    "nos_macro_category": "contract",
                },
            }
        ],
    )
    _write_jsonl(inputs / "public-exclusions.jsonl", [])
    _write_jsonl(inputs / "packet-exclusions.jsonl", [])
    _write_jsonl(
        inputs / "screened-cases.jsonl",
        [
            {"candidate": {"docket_id": "cand-1"}},
            {"candidate": {"docket_id": "cand-incomplete"}},
        ],
    )
    _write_jsonl(inputs / "discovery-exclusions.jsonl", [])
    snapshot_fixture = _write_snapshot_manifest(
        inputs,
        processed_count=2,
        accepted_count=2,
        excluded_count=0,
        target_case_count=1,
    )
    snapshot_manifest = snapshot_fixture.manifest_path
    _stub_verified_preparation(monkeypatch, snapshot_fixture, target_case_count=1)

    assert (
        main(
            [
                "acquisition",
                "finalize-corpus",
                "--selection",
                str(inputs / "selection.jsonl"),
                "--parser-manifest",
                str(inputs / "parser.jsonl"),
                "--decision-texts",
                str(inputs / "selection.jsonl"),
                "--decision-texts-manifest",
                str(inputs / "selection.jsonl"),
                "--decision-texts-run-card",
                str(inputs / "selection.jsonl"),
                "--disclosure-clearance",
                str(inputs / "clearance.jsonl"),
                "--markdown-root",
                str(markdown_root),
                "--prediction-units",
                str(inputs / "units.jsonl"),
                "--raw-prediction-units",
                str(inputs / "raw-units.jsonl"),
                *stage_a_run_card_args,
                "--llm-unitization-audit",
                str(inputs / "unitization-audit.jsonl"),
                "--original-unitization-review-queue",
                str(inputs / "original-unitization-review-queue.jsonl"),
                "--stage-a-structural-flags",
                str(inputs / "stage-a-structural-flags.jsonl"),
                "--stage-a-structural-review-audit",
                str(inputs / "stage-a-structural-review-audit.jsonl"),
                "--stage-a-review-model-registry",
                str(LABELING_REGISTRY),
                "--stage-a-review-model-key",
                GEMINI_KEY,
                "--unitization-review-queue",
                str(inputs / "unitization-review-queue.jsonl"),
                "--unitization-review-adjudications",
                str(inputs / "unitization-adjudications.jsonl"),
                "--labels",
                str(inputs / "labels.jsonl"),
                "--llm-label-audit",
                str(inputs / "label-audit.jsonl"),
                "--stage-b-judge-registry",
                str(JUDGE_REGISTRY),
                "--labeling-policy",
                str(labeling_policy_path),
                "--lawyer-review-queue",
                str(inputs / "review-queue.jsonl"),
                "--lawyer-review-audit",
                str(inputs / "lawyer-review-audit.jsonl"),
                "--packet-build-input",
                str(inputs / "packet-input.jsonl"),
                "--packets",
                str(inputs / "packets.jsonl"),
                "--model-registry",
                str(REGISTRY),
                "--screened-cases",
                str(snapshot_manifest.parent / "screened-cases.jsonl"),
                "--discovery-summary",
                str(snapshot_manifest.parent / "summary.json"),
                "--discovery-exclusions",
                str(snapshot_manifest.parent / "exclusions.jsonl"),
                "--screening-snapshot-manifest",
                str(snapshot_manifest),
                "--screening-cycle-store",
                str(snapshot_fixture.cycle_store_path),
                "--target-cohort-preparation-root",
                str(snapshot_fixture.target_preparation_root),
                "--exclusion-source",
                str(inputs / "public-exclusions.jsonl"),
                "--exclusion-source",
                str(inputs / "packet-exclusions.jsonl"),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    ledger = _read_jsonl(output_root / "complete-exclusion-ledger.jsonl")
    assert len(ledger) == 1
    assert ledger[0]["candidate_id"] == "cand-incomplete"
    assert ledger[0]["primary_exclusion_reason"] == (
        "required_document_parse_incomplete"
    )
    assert ledger[0]["secondary_exclusion_reasons"] == [
        "stage_a_units_missing",
        "stage_a_unitization_audit_missing",
        "label_audit_missing",
        "packet_build_input_missing",
        "built_packet_missing",
    ]
    readiness = json.loads(
        (output_root / "corpus-readiness.json").read_text(encoding="utf-8")
    )
    assert readiness["clean_count"] == 1
    assert readiness["meets_target"] is True
    snapshot_record = json.loads(snapshot_manifest.read_text(encoding="utf-8"))
    assert readiness["screening_snapshot_reconciliation"] == {
        "accepted_count": 2,
        "batch_digest": snapshot_record["batch_digest"],
        "batch_id": "batch-1",
        "cycle_hash": snapshot_record["cycle_hash"],
        "cycle_store_path": str(snapshot_fixture.cycle_store_path.resolve()),
        "excluded_count": 0,
        "manifest_sha256": sha256_file(snapshot_manifest),
        "processed_count": 2,
        "snapshot_id": "snapshot-1",
    }
    assert readiness["case_mix"]["court"] == {"S.D.N.Y.": 1}
    assert readiness["case_mix"]["nature_of_suit"] == {"Contract": 1}
    assert readiness["case_mix"]["nos_macro_category"] == {"contract": 1}
    assert readiness["case_mix"]["related_family_id"] == {"related-fixture": 1}
    assert readiness["case_mix"]["mdl_family_id"] == {"mdl-fixture": 1}
    assert all(
        sum(buckets.values()) == readiness["clean_count"]
        for buckets in readiness["case_mix"].values()
    )


def test_acquisition_finalize_corpus_rejects_unreconciled_screened_candidate(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    stage_a_run_card_args = _stub_stage_a_run_card_chain(monkeypatch, inputs)
    _write_jsonl(
        inputs / "screened-cases.jsonl",
        [
            {"candidate": {"docket_id": "cand-selected"}},
            {"candidate": {"docket_id": "cand-dropped"}},
        ],
    )
    _write_jsonl(inputs / "discovery-exclusions.jsonl", [])
    snapshot_fixture = _write_snapshot_manifest(
        inputs,
        processed_count=2,
        accepted_count=2,
        excluded_count=0,
        target_case_count=1,
    )
    snapshot_manifest = snapshot_fixture.manifest_path
    _stub_verified_preparation(monkeypatch, snapshot_fixture, target_case_count=1)
    _write_jsonl(
        inputs / "selection.jsonl",
        [
            {
                "candidate_id": "cand-selected",
                "case_id": "case-selected",
                "documents": [],
            }
        ],
    )
    for name in (
        "parser",
        "units",
        "unitization-audit",
        "original-unitization-review-queue",
        "stage-a-structural-flags",
        "stage-a-structural-review-audit",
        "unitization-review-queue",
        "unitization-adjudications",
        "labels",
        "label-audit",
        "review-queue",
        "lawyer-review-audit",
        "packet-input",
        "packets",
        "clearance",
    ):
        _write_jsonl(inputs / f"{name}.jsonl", [])
    _write_jsonl(inputs / "raw-units.jsonl", [])
    labeling_policy_path = inputs / "labeling-policy.json"
    write_labeling_policy(
        labeling_policy_path,
        generate_labeling_policy(
            cycle_id="cycle-1",
            judge_registry_path=JUDGE_REGISTRY,
            published_at=datetime(2026, 7, 14, tzinfo=UTC),
            threshold_source="Cycle 1 protocol decision, 2026-07-14",
        ),
    )

    result = main(
        [
            "acquisition",
            "finalize-corpus",
            "--selection",
            str(inputs / "selection.jsonl"),
            "--parser-manifest",
            str(inputs / "parser.jsonl"),
            "--decision-texts",
            str(inputs / "selection.jsonl"),
            "--decision-texts-manifest",
            str(inputs / "selection.jsonl"),
            "--decision-texts-run-card",
            str(inputs / "selection.jsonl"),
            "--disclosure-clearance",
            str(inputs / "clearance.jsonl"),
            "--markdown-root",
            str(tmp_path / "markdown"),
            "--prediction-units",
            str(inputs / "units.jsonl"),
            "--raw-prediction-units",
            str(inputs / "raw-units.jsonl"),
            *stage_a_run_card_args,
            "--llm-unitization-audit",
            str(inputs / "unitization-audit.jsonl"),
            "--original-unitization-review-queue",
            str(inputs / "original-unitization-review-queue.jsonl"),
            "--stage-a-structural-flags",
            str(inputs / "stage-a-structural-flags.jsonl"),
            "--stage-a-structural-review-audit",
            str(inputs / "stage-a-structural-review-audit.jsonl"),
            "--stage-a-review-model-registry",
            str(LABELING_REGISTRY),
            "--stage-a-review-model-key",
            GEMINI_KEY,
            "--unitization-review-queue",
            str(inputs / "unitization-review-queue.jsonl"),
            "--unitization-review-adjudications",
            str(inputs / "unitization-adjudications.jsonl"),
            "--labels",
            str(inputs / "labels.jsonl"),
            "--llm-label-audit",
            str(inputs / "label-audit.jsonl"),
            "--stage-b-judge-registry",
            str(JUDGE_REGISTRY),
            "--labeling-policy",
            str(labeling_policy_path),
            "--lawyer-review-queue",
            str(inputs / "review-queue.jsonl"),
            "--lawyer-review-audit",
            str(inputs / "lawyer-review-audit.jsonl"),
            "--packet-build-input",
            str(inputs / "packet-input.jsonl"),
            "--packets",
            str(inputs / "packets.jsonl"),
            "--model-registry",
            str(REGISTRY),
            "--screened-cases",
            str(snapshot_manifest.parent / "screened-cases.jsonl"),
            "--discovery-summary",
            str(snapshot_manifest.parent / "summary.json"),
            "--discovery-exclusions",
            str(snapshot_manifest.parent / "exclusions.jsonl"),
            "--screening-snapshot-manifest",
            str(snapshot_manifest),
            "--screening-cycle-store",
            str(snapshot_fixture.cycle_store_path),
            "--target-cohort-preparation-root",
            str(snapshot_fixture.target_preparation_root),
            "--target-clean-cases",
            "1",
            "--output-root",
            str(tmp_path / "out"),
            "--execute",
        ]
    )

    assert result == 2
    assert "unreconciled screened candidates: cand-dropped" in capsys.readouterr().err


def test_acquisition_finalize_corpus_rejects_summary_not_bound_to_snapshot_manifest(
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    stage_a_run_card_args = _stub_stage_a_run_card_chain(monkeypatch, inputs)
    _write_jsonl(inputs / "screened-cases.jsonl", [])
    _write_jsonl(inputs / "discovery-exclusions.jsonl", [])
    snapshot_fixture = _write_snapshot_manifest(
        inputs,
        processed_count=0,
        accepted_count=0,
        excluded_count=0,
        target_case_count=0,
    )
    snapshot_manifest = snapshot_fixture.manifest_path
    _stub_verified_preparation(monkeypatch, snapshot_fixture, target_case_count=0)
    (snapshot_manifest.parent / "summary.json").write_text(
        json.dumps(
            {
                "accepted_count": 1,
                "batch_id": "batch-1",
                "excluded_count": 0,
                "processed_count": 1,
                "reconciliation_complete": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    result = main(
        [
            "acquisition",
            "finalize-corpus",
            "--selection",
            str(inputs / "screened-cases.jsonl"),
            "--parser-manifest",
            str(inputs / "screened-cases.jsonl"),
            "--decision-texts",
            str(inputs / "screened-cases.jsonl"),
            "--decision-texts-manifest",
            str(inputs / "screened-cases.jsonl"),
            "--decision-texts-run-card",
            str(inputs / "screened-cases.jsonl"),
            "--disclosure-clearance",
            str(inputs / "screened-cases.jsonl"),
            "--markdown-root",
            str(tmp_path),
            "--raw-prediction-units",
            str(inputs / "screened-cases.jsonl"),
            *stage_a_run_card_args,
            "--prediction-units",
            str(inputs / "screened-cases.jsonl"),
            "--llm-unitization-audit",
            str(inputs / "screened-cases.jsonl"),
            "--original-unitization-review-queue",
            str(inputs / "screened-cases.jsonl"),
            "--stage-a-structural-flags",
            str(inputs / "screened-cases.jsonl"),
            "--stage-a-structural-review-audit",
            str(inputs / "screened-cases.jsonl"),
            "--stage-a-review-model-registry",
            str(LABELING_REGISTRY),
            "--stage-a-review-model-key",
            GEMINI_KEY,
            "--unitization-review-queue",
            str(inputs / "screened-cases.jsonl"),
            "--unitization-review-adjudications",
            str(inputs / "screened-cases.jsonl"),
            "--labels",
            str(inputs / "screened-cases.jsonl"),
            "--llm-label-audit",
            str(inputs / "screened-cases.jsonl"),
            "--stage-b-judge-registry",
            str(JUDGE_REGISTRY),
            "--labeling-policy",
            str(inputs / "screened-cases.jsonl"),
            "--lawyer-review-queue",
            str(inputs / "screened-cases.jsonl"),
            "--lawyer-review-audit",
            str(inputs / "screened-cases.jsonl"),
            "--packet-build-input",
            str(inputs / "screened-cases.jsonl"),
            "--packets",
            str(inputs / "screened-cases.jsonl"),
            "--model-registry",
            str(REGISTRY),
            "--screened-cases",
            str(snapshot_manifest.parent / "screened-cases.jsonl"),
            "--discovery-summary",
            str(snapshot_manifest.parent / "summary.json"),
            "--discovery-exclusions",
            str(snapshot_manifest.parent / "exclusions.jsonl"),
            "--screening-snapshot-manifest",
            str(snapshot_manifest),
            "--screening-cycle-store",
            str(snapshot_fixture.cycle_store_path),
            "--target-cohort-preparation-root",
            str(snapshot_fixture.target_preparation_root),
            "--target-clean-cases",
            "0",
            "--output-root",
            str(tmp_path / "out"),
            "--execute",
        ]
    )

    assert result == 2
    assert "snapshot file commitment mismatch: summary.json" in capsys.readouterr().err


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@dataclass(frozen=True, slots=True)
class _SnapshotFixture:
    manifest_path: Path
    cycle_store_path: Path
    target_preparation_root: Path


def _write_snapshot_manifest(
    inputs: Path,
    *,
    processed_count: int,
    accepted_count: int,
    excluded_count: int,
    target_case_count: int,
) -> _SnapshotFixture:
    assert processed_count == accepted_count + excluded_count
    screened_records = _read_jsonl(inputs / "screened-cases.jsonl")
    assert len(screened_records) == accepted_count
    discovery_exclusions = _read_jsonl(inputs / "discovery-exclusions.jsonl")
    assert len(discovery_exclusions) == excluded_count
    accepted_evidence: list[tuple[str, dict[str, object]]] = []
    for record in screened_records:
        candidate = record["candidate"]
        assert isinstance(candidate, dict)
        accepted_evidence.append(
            (
                str(candidate["docket_id"]),
                {key: value for key, value in record.items() if key != "candidate_id"},
            )
        )
    store_path = inputs / "screening-store" / "cycle-acquisition.sqlite3"
    with CycleAcquisitionStore(store_path) as store:
        store.ensure_cycle(
            {
                "anchor": "2026-06-30T00:00:00Z",
                "query_terms": ["motion to dismiss"],
                "screen_hash": "screen-v1",
                "schema": 1,
            }
        )
        store.ensure_batch("batch-1", {"page_size": max(processed_count, 1)})
        store.ensure_terms("batch-1", ["motion to dismiss"])
        all_ids = [
            *(candidate_id for candidate_id, _ in accepted_evidence),
            *(str(record["candidate_id"]) for record in discovery_exclusions),
        ]
        store.commit_search_page(
            "batch-1",
            "motion to dismiss",
            None,
            [
                {
                    "provider_hit_id": f"hit-{index}",
                    "candidate_id": candidate_id,
                    "payload": {"id": f"hit-{index}"},
                }
                for index, candidate_id in enumerate(all_ids, start=1)
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
        for candidate_id, evidence in accepted_evidence:
            store.record_observation(
                candidate_id,
                batch_id="batch-1",
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence=evidence,
            )
        for record in discovery_exclusions:
            store.record_observation(
                str(record["candidate_id"]),
                batch_id="batch-1",
                state="excluded",
                reason_code="decision_before_release_anchor",
                evidence={
                    key: value for key, value in record.items() if key != "candidate_id"
                },
            )
        snapshot = store.export_snapshot(
            inputs / "screening-snapshots",
            snapshot_id="snapshot-1",
            batch_id="batch-1",
            complete=True,
            stage_commitments={"test_source": {"schema_version": "test.v1"}},
        )
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    preparation_root = inputs / "target-preparation"
    (preparation_root / "run-cards").mkdir(parents=True)
    config: dict[str, object] = {
        "schema_version": "legalforecast.target_cohort_config.v1",
        "snapshot": str(snapshot.resolve()),
        "snapshot_manifest_sha256": "sha256:" + sha256_file(manifest_path),
        "snapshot_screened_cases_sha256": "sha256:"
        + sha256_file(snapshot / "screened-cases.jsonl"),
        "snapshot_cycle_hash": manifest["cycle_hash"],
        "snapshot_batch_digest": manifest["batch_digest"],
        "candidate_pool_size": accepted_count,
        "target_case_count": target_case_count,
        "driver_execute": True,
    }
    config["config_sha256"] = cli._canonical_json_sha256(config)
    (preparation_root / "target-cohort-config.json").write_text(
        json.dumps(config, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (preparation_root / "target-cohort-preparation-summary.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    (preparation_root / "run-cards/prepare-target-cohort.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    return _SnapshotFixture(
        manifest_path=manifest_path,
        cycle_store_path=store_path,
        target_preparation_root=preparation_root,
    )


def _stub_verified_preparation(
    monkeypatch: pytest.MonkeyPatch,
    fixture: _SnapshotFixture,
    *,
    target_case_count: int,
) -> None:
    success_run_card = (
        fixture.target_preparation_root / "run-cards/prepare-target-cohort.json"
    )
    monkeypatch.setattr(
        cli,
        "_verify_completed_preparation_for_frontier",
        lambda **_kwargs: SimpleNamespace(
            target_case_count=target_case_count,
            success_run_card_path=success_run_card,
        ),
    )


def _stub_stage_a_run_card_chain(
    monkeypatch: pytest.MonkeyPatch, inputs: Path
) -> list[str]:
    unitization_card = inputs / "llm-unitize-run-card.json"
    review_card = inputs / "apply-unitization-review-run-card.json"
    unitization_card.write_text("{}\n", encoding="utf-8")
    review_card.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_run_card",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        cli,
        "_verify_unitization_review_run_card",
        lambda *args, **kwargs: None,
    )
    return [
        "--llm-unitization-run-card",
        str(unitization_card),
        "--unitization-review-run-card",
        str(review_card),
    ]
