from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

from legalforecast.cli import _cycle_acquisition_policy, main
from legalforecast.ingestion.case_dev_ranked_selection import (
    CASE_DEV_RANKED_SELECTION_RUN_SCHEMA,
    CASE_DEV_RANKED_TRANSFER_SCHEMA,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore


def test_select_case_dev_ranked_materializes_exact_top_n_rest_batch(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    target_store = _target_store(tmp_path)
    run_card = tmp_path / "selection-run-card.json"
    summary = tmp_path / "selection-summary.json"

    assert (
        main(
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
        main(
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
        main(
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


def test_select_case_dev_ranked_rejects_forged_rank_and_recomputed_run_card(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    enrichment_root = _run_enrichment(tmp_path, source_store=source_store)
    ranked_path = enrichment_root / "checkpoints" / "case-dev-recap-ranked.jsonl"
    run_card_path = enrichment_root / "run-cards" / "enrich-recap-case-dev.json"
    expected_run_card_sha256 = hashlib.sha256(run_card_path.read_bytes()).hexdigest()
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
    target_store = _target_store(tmp_path)

    assert (
        main(
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
        main(
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
        main(
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


def _run_enrichment(tmp_path: Path, *, source_store: Path) -> Path:
    fixture = tmp_path / "case-dev.jsonl"
    _write_jsonl(
        fixture,
        [
            _case_dev_response("101", entries=[]),
            _case_dev_response(
                "102",
                entries=[
                    _entry("entry-1", 1, "Complaint", "doc-1"),
                    _entry("entry-5", 5, "Motion to Dismiss", "doc-5"),
                    _entry(
                        "entry-10",
                        10,
                        "Order denying Motion to Dismiss",
                        "doc-10",
                    ),
                ],
            ),
        ],
    )
    output_root = tmp_path / "enrichment"
    assert (
        main(
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


def _opinion_source_store(tmp_path: Path) -> Path:
    path = tmp_path / "source.sqlite3"
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(_cycle_policy())
        term = '"motion to dismiss"'
        store.ensure_batch(
            "opinion-source",
            {
                "provider": "courtlistener",
                "search_type": "o",
                "query_terms": [term],
                "search_window_start": "2026-06-30",
                "search_window_end": "2026-07-15",
            },
        )
        store.ensure_terms("opinion-source", (term,))
        store.commit_search_page(
            "opinion-source",
            term,
            None,
            [
                _opinion_hit("101", "501"),
                _opinion_hit("102", "502"),
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
    return path


def _target_store(tmp_path: Path, *, name: str = "target.sqlite3") -> Path:
    path = tmp_path / name
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(_cycle_acquisition_policy(anchor=_anchor()))
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


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _assert_no_target_rows(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM batches").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM term_progress").fetchone() == (
            0,
        )
        assert connection.execute("SELECT count(*) FROM discovery_hits").fetchone() == (
            0,
        )
