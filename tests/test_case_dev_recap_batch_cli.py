from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import legalforecast.cli as cli_module
import pytest
from legalforecast.ingestion.case_dev_client import CaseDevRateLimitError
from legalforecast.ingestion.case_dev_recap_batch import (
    RecapDocketRecordError,
    case_dev_recap_lookup_target_from_record,
)
from legalforecast.ingestion.cycle_acquisition_store import CycleAcquisitionStore

_QUERY_EXPRESSION_ABSENT = object()


def test_enrich_recap_case_dev_worker_ceiling_and_help_are_safe_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        cli_module.build_parser().parse_args(
            ["acquisition", "enrich-recap-case-dev", "--help"]
        )
    help_text = " ".join(capsys.readouterr().out.split())
    assert "1-5, default 1" in help_text
    assert "defaults conservatively to 30" in help_text
    assert "cooldown" in help_text
    assert "are also shared" in help_text

    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        json.dumps(
            {
                "candidate_id": "courtlistener-docket-101",
                "docket_id": "101",
                "docket_url": "https://www.courtlistener.com/docket/101/example/",
                "entry_keys": ["entry-101"],
                "matched_terms": ["motion to dismiss"],
                "eligibility_status": "potential_unverified",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(tmp_path / "workers-five"),
                "--dockets",
                str(dockets),
                "--live-case-dev",
                "--workers",
                "5",
            ]
        )
        == 0
    )
    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(tmp_path / "workers-six"),
                "--dockets",
                str(dockets),
                "--live-case-dev",
                "--workers",
                "6",
            ]
        )
        == 2
    )


def test_five_live_workers_share_default_limiter_and_serial_checkpoint_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": f"courtlistener-docket-{docket_id}",
                    "docket_id": docket_id,
                    "docket_url": (
                        f"https://www.courtlistener.com/docket/{docket_id}/example/"
                    ),
                    "entry_keys": [f"entry-{docket_id}"],
                    "matched_terms": ["motion to dismiss"],
                    "eligibility_status": "potential_unverified",
                }
            )
            + "\n"
            for docket_id in ("101", "102", "103", "104", "105")
        ),
        encoding="utf-8",
    )
    barrier = threading.Barrier(5)
    limiter_ids: set[int] = set()
    limiter_rates: set[int | None] = set()

    def fake_enrich(
        *,
        input_index: int,
        rate_limiter: Any,
        **_kwargs: Any,
    ) -> tuple[dict[str, Any], int]:
        limiter_ids.add(id(rate_limiter))
        limiter_rates.add(rate_limiter.rate_limit_per_minute)
        barrier.wait(timeout=5)
        return (
            {
                "input_index": input_index,
                "outcome": "failure",
                "payload": {
                    "input_index": input_index,
                    "reason": "offline_test_terminal",
                },
            },
            0,
        )

    real_append_jsonl = cli_module._append_jsonl
    checkpoint_writer_threads: set[int | None] = set()

    def record_checkpoint_writer(path: Path, records: Any) -> None:
        if path.name == "case-dev-recap-progress.jsonl":
            checkpoint_writer_threads.add(threading.current_thread().ident)
        real_append_jsonl(path, records)

    monkeypatch.setattr(cli_module, "_enrich_case_dev_progress_record", fake_enrich)
    monkeypatch.setattr(cli_module, "_append_jsonl", record_checkpoint_writer)
    monkeypatch.setenv("CASE_DEV_API_KEY", "offline-test-key")
    monkeypatch.delenv("CASE_DEV_RATE_LIMIT_PER_MINUTE", raising=False)

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(tmp_path / "output"),
                "--dockets",
                str(dockets),
                "--live-case-dev",
                "--workers",
                "5",
                "--execute",
            ]
        )
        == 0
    )
    assert len(limiter_ids) == 1
    assert limiter_rates == {30}
    assert checkpoint_writer_threads == {threading.current_thread().ident}


def test_resume_can_raise_worker_count_without_changing_checkpoint_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": f"courtlistener-docket-{docket_id}",
                    "docket_id": docket_id,
                    "docket_url": (
                        f"https://www.courtlistener.com/docket/{docket_id}/example/"
                    ),
                    "entry_keys": [f"entry-{docket_id}"],
                    "matched_terms": ["motion to dismiss"],
                    "eligibility_status": "potential_unverified",
                }
            )
            + "\n"
            for docket_id in ("101", "102", "103", "104", "105", "106")
        ),
        encoding="utf-8",
    )
    phase = "initial"
    resumed_indices: set[int] = set()

    def fake_enrich(*, input_index: int, **_kwargs: Any) -> tuple[dict[str, Any], int]:
        if phase == "initial" and input_index == 1:
            raise CaseDevRateLimitError("offline terminal breaker")
        if phase == "resumed":
            resumed_indices.add(input_index)
        return (
            {
                "input_index": input_index,
                "outcome": "failure",
                "payload": {
                    "input_index": input_index,
                    "reason": "offline_test_terminal",
                },
            },
            0,
        )

    monkeypatch.setattr(cli_module, "_enrich_case_dev_progress_record", fake_enrich)
    monkeypatch.setenv("CASE_DEV_API_KEY", "offline-test-key")
    output_root = tmp_path / "output"
    base_args = [
        "acquisition",
        "enrich-recap-case-dev",
        "--output-root",
        str(output_root),
        "--dockets",
        str(dockets),
        "--live-case-dev",
        "--execute",
    ]

    assert cli_module.main([*base_args, "--workers", "1"]) == 2
    progress_config = json.loads(
        (
            output_root / "checkpoints" / "case-dev-recap-progress-config.json"
        ).read_text()
    )
    assert "workers" not in progress_config

    phase = "resumed"
    assert cli_module.main([*base_args, "--workers", "5", "--resume"]) == 0
    assert resumed_indices == {1, 2, 3, 4, 5}
    failures = _read_jsonl(
        output_root / "checkpoints" / "case-dev-recap-failures.jsonl"
    )
    assert [record["input_index"] for record in failures] == list(range(6))


def test_enrich_recap_case_dev_projects_saturated_opinion_source_without_invented_url(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")
    output_root = tmp_path / "output"

    assert (
        cli_module.main(
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

    projection_path = (
        output_root / "checkpoints" / "case-dev-recap-source-projection.jsonl"
    )
    [projected] = _read_jsonl(projection_path)
    assert projected["schema_version"] == (
        "legalforecast.case_dev_recap_source_docket.v1"
    )
    assert projected["docket_id"] == "101"
    assert "docket_url" not in projected
    assert projected["source_lineage"]["source_batch_id"] == "opinion-source"

    [ranked] = _read_jsonl(output_root / "checkpoints" / "case-dev-recap-ranked.jsonl")
    assert ranked["identity"]["courtlistener_docket_id"] == "101"
    assert ranked["identity"]["courtlistener_url"] == (
        "https://www.courtlistener.com/api/rest/v4/dockets/101/"
    )
    assert ranked["ranking_policy_version"] == "eligibility-aware-v2"
    assert ranked["eligibility_anchor"] == "2026-06-30"
    assert ranked["entries"] == []
    assert ranked["source_lineage"] == projected["source_lineage"]


def test_source_bound_projection_rejects_noncanonical_search_window_spelling(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path)
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")
    output_root = tmp_path / "output"
    assert (
        cli_module.main(
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
    [projected] = _read_jsonl(
        output_root / "checkpoints" / "case-dev-recap-source-projection.jsonl"
    )
    lineage = projected["source_lineage"]
    lineage["source_search_window_start"] = "20260630"
    query_commitment = {
        "source_schema_version": lineage["source_schema_version"],
        "source_search_type": lineage["source_search_type"],
        "source_available_only": lineage["source_available_only"],
        "source_query_expression": lineage["source_query_expression"],
        "source_query_terms": lineage["source_query_terms"],
        "source_search_window_start": "2026-06-30",
        "source_search_window_end": "2026-07-15",
    }
    lineage["source_query_commitment_sha256"] = hashlib.sha256(
        json.dumps(
            query_commitment,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    with pytest.raises(RecapDocketRecordError, match="canonical search window"):
        case_dev_recap_lookup_target_from_record(
            projected,
            allow_source_bound=True,
        )

    summary = json.loads(
        (output_root / "checkpoints" / "case-dev-recap-summary.json").read_text()
    )
    assert summary["source_batch_id"] == "opinion-source"
    assert len(summary["source_batch_digest"]) == 64
    assert len(summary["source_candidate_set_sha256"]) == 64
    assert summary["source_search_type"] == "o"
    assert summary["ranking_policy_version"] == "eligibility-aware-v2"
    assert summary["eligibility_anchor"] == "2026-06-30"
    assert len(summary["source_projection_sha256"]) == 64
    run_card = json.loads(
        (output_root / "run-cards" / "enrich-recap-case-dev.json").read_text()
    )
    assert run_card["source_batch_digest"] == summary["source_batch_digest"]
    assert (
        run_card["source_candidate_set_sha256"]
        == (summary["source_candidate_set_sha256"])
    )
    assert run_card["source_projection_sha256"] == (summary["source_projection_sha256"])


def test_enrich_recap_case_dev_projects_saturated_unrestricted_recap_source(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path, search_type="r")
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")
    output_root = tmp_path / "output"

    assert (
        cli_module.main(
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

    [projected] = _read_jsonl(
        output_root / "checkpoints" / "case-dev-recap-source-projection.jsonl"
    )
    lineage = projected["source_lineage"]
    assert lineage["source_search_type"] == "r"
    assert lineage["source_schema_version"] == (
        "legalforecast.courtlistener_unrestricted_recap.v1"
    )
    assert lineage["source_available_only"] == "omitted"
    assert lineage["source_query_terms"] == ['"motion to dismiss"']
    assert lineage["source_search_window_start"] == "2026-06-30"
    assert lineage["source_search_window_end"] == "2026-07-15"
    assert len(lineage["source_hit_set_sha256"]) == 64

    summary = json.loads(
        (output_root / "run-cards" / "enrich-recap-case-dev.json").read_text()
    )
    assert summary["source_search_type"] == "r"
    assert summary["source_available_only"] == "omitted"
    assert summary["source_query_terms"] == ['"motion to dismiss"']
    assert summary["free_lookup_only"] is True
    assert summary["pacer_fee_acknowledgment_allowed"] is False


@pytest.mark.parametrize(
    ("search_type", "schema_version", "available_only"),
    [
        ("rd", "legalforecast.courtlistener_unrestricted_recap.v1", "omitted"),
        ("r", "legalforecast.courtlistener_opinion_discovery.v1", "omitted"),
        ("r", "legalforecast.courtlistener_unrestricted_recap.v1", "on"),
    ],
)
def test_enrich_recap_case_dev_rejects_unsupported_or_substituted_source_schema(
    tmp_path: Path,
    search_type: str,
    schema_version: str,
    available_only: str,
) -> None:
    source_store = _opinion_source_store(
        tmp_path,
        search_type=search_type,
        schema_version=schema_version,
        available_only=available_only,
    )
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(tmp_path / "output"),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "opinion-source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 2
    )


@pytest.mark.parametrize(
    "query_expression",
    [
        None,
        "",
        " {term} AND entry_date_filed:[{start} TO {end}]",
        "{term} AND entry_date_filed:[{start} TO {end}]",
        7,
    ],
)
def test_enrich_recap_case_dev_rejects_present_opinion_query_expression(
    tmp_path: Path,
    query_expression: object,
) -> None:
    source_store = _opinion_source_store(
        tmp_path,
        query_expression=query_expression,
    )
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(tmp_path / "output"),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "opinion-source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 2
    )


def test_enrich_recap_case_dev_rejects_noncanonical_numeric_source_identity(
    tmp_path: Path,
) -> None:
    source_store = _opinion_source_store(tmp_path, docket_id="001")
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("1")) + "\n")

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(tmp_path / "output"),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "opinion-source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 2
    )


def test_enrich_recap_case_dev_rejected_resume_preserves_source_projection(
    tmp_path: Path,
) -> None:
    first_source = _opinion_source_store(tmp_path)
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")
    output_root = tmp_path / "output"
    first_args = [
        "acquisition",
        "enrich-recap-case-dev",
        "--output-root",
        str(output_root),
        "--source-store",
        str(first_source),
        "--source-batch-id",
        "opinion-source",
        "--case-dev-fixture",
        str(fixture),
        "--execute",
        "--resume",
    ]
    assert cli_module.main(first_args) == 0
    projection_path = (
        output_root / "checkpoints" / "case-dev-recap-source-projection.jsonl"
    )
    original_projection = projection_path.read_bytes()

    second_source = _opinion_source_store(
        tmp_path,
        name="second-opinion-source.sqlite3",
        docket_id="102",
    )
    second_args = list(first_args)
    second_args[second_args.index(str(first_source))] = str(second_source)
    assert cli_module.main(second_args) == 2
    assert projection_path.read_bytes() == original_projection


def test_enrich_recap_case_dev_rejects_ambiguous_input_modes(tmp_path: Path) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text("", encoding="utf-8")
    source_store = _opinion_source_store(tmp_path)
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(tmp_path / "output"),
                "--dockets",
                str(dockets),
                "--source-store",
                str(source_store),
                "--source-batch-id",
                "opinion-source",
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 2
    )


def test_enrich_recap_case_dev_rejects_fabricated_source_schema_from_dockets(
    tmp_path: Path,
) -> None:
    dockets = tmp_path / "fabricated-source.jsonl"
    fake_hash = "0" * 64
    fake_hit = {
        "provider_hit_id": "fake-opinion",
        "query_term": '"motion to dismiss"',
        "payload_sha256": fake_hash,
    }
    dockets.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.case_dev_recap_source_docket.v1",
                "candidate_id": "courtlistener-docket-101",
                "docket_id": "101",
                "entry_keys": ["fake-opinion"],
                "matched_terms": ['"motion to dismiss"'],
                "eligibility_status": "potential_unverified",
                "source_lineage": {
                    "source_batch_id": "fabricated",
                    "source_batch_digest": fake_hash,
                    "source_cycle_hash": fake_hash,
                    "source_search_type": "o",
                    "source_candidate_set_sha256": fake_hash,
                    "docket_id": "101",
                    "lead_commitment": {
                        "docket_id": "101",
                        "source_hits": [fake_hit],
                    },
                    "source_hits": [fake_hit],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(json.dumps(_case_dev_response("101")) + "\n")
    output_root = tmp_path / "output"

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 2
    )
    assert not (output_root / "checkpoints" / "case-dev-recap-progress.jsonl").exists()


def test_enrich_recap_case_dev_ranks_free_lookups_without_fee_flags(
    tmp_path: Path,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        json.dumps(
            {
                "candidate_id": "courtlistener-docket-101",
                "docket_id": "101",
                "docket_url": "https://www.courtlistener.com/docket/101/example/",
                "entry_keys": ["entry-10"],
                "matched_terms": ["motion to dismiss"],
                "eligibility_status": "potential_unverified",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    fixture = tmp_path / "case-dev.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "method": "POST",
                "path": "/legal/v1/docket",
                "params": {
                    "type": "lookup",
                    "docketId": "101",
                    "includeEntries": True,
                    "limit": 100,
                },
                "status_code": 200,
                "payload": {
                    "docket": {
                        "id": "101",
                        "url": (
                            "https://www.courtlistener.com/api/rest/v4/dockets/101/"
                        ),
                        "entries": [
                            {
                                "id": "entry-10",
                                "entryNumber": 10,
                                "date": "2026-07-01",
                                "description": "Order denying Motion to Dismiss",
                                "documents": [
                                    {
                                        "id": "doc-10",
                                        "description": "Decision",
                                        "type": "main_document",
                                        "pdfUrl": (
                                            "https://storage.courtlistener.com/"
                                            "decision.pdf"
                                        ),
                                        "isAvailable": True,
                                    }
                                ],
                            }
                        ],
                    }
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    output_root = tmp_path / "output"

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(fixture),
                "--execute",
            ]
        )
        == 0
    )

    [ranked] = _read_jsonl(output_root / "checkpoints" / "case-dev-recap-ranked.jsonl")
    assert ranked["identity"]["courtlistener_docket_id"] == "101"
    assert ranked["actual_free_required_document_count"] == 1
    assert ranked["missing_required_document_count"] == 2
    summary = json.loads(
        (output_root / "checkpoints" / "case-dev-recap-summary.json").read_text()
    )
    assert summary["case_dev_request_count"] == 1
    assert summary["successful_docket_count"] == 1
    assert summary["reconciled"] is True
    assert summary["free_lookup_only"] is True
    assert summary["pacer_fee_acknowledgment_allowed"] is False
    assert summary["pacer_spend_usd"] == "0.00"
    assert (
        output_root / "checkpoints" / "case-dev-recap-failures.jsonl"
    ).read_text() == ""


def test_enrich_recap_case_dev_resumes_after_transient_provider_abort(
    tmp_path: Path,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": f"courtlistener-docket-{docket_id}",
                    "docket_id": docket_id,
                    "docket_url": (
                        f"https://www.courtlistener.com/docket/{docket_id}/example/"
                    ),
                    "entry_keys": [f"entry-{docket_id}"],
                    "matched_terms": ["motion to dismiss"],
                    "eligibility_status": "potential_unverified",
                }
            )
            + "\n"
            for docket_id in ("101", "102")
        )
    )
    first_fixture = tmp_path / "first.jsonl"
    first_fixture.write_text(
        json.dumps(_case_dev_response("101"))
        + "\n"
        + "\n".join(json.dumps(_timeout_response("102")) for _ in range(3))
        + "\n"
    )
    output_root = tmp_path / "output"

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(first_fixture),
                "--execute",
                "--resume",
            ]
        )
        == 2
    )
    progress = _read_jsonl(
        output_root / "checkpoints" / "case-dev-recap-progress.jsonl"
    )
    assert [(record["input_index"], record["outcome"]) for record in progress] == [
        (0, "success"),
        (1, "transient"),
    ]

    second_fixture = tmp_path / "second.jsonl"
    second_fixture.write_text(json.dumps(_case_dev_response("102")) + "\n")
    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(second_fixture),
                "--execute",
                "--resume",
            ]
        )
        == 0
    )
    ranked = _read_jsonl(output_root / "checkpoints" / "case-dev-recap-ranked.jsonl")
    assert {record["identity"]["courtlistener_docket_id"] for record in ranked} == {
        "101",
        "102",
    }


def test_enrich_recap_case_dev_bounds_resumable_server_failures(
    tmp_path: Path,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        json.dumps(
            {
                "candidate_id": "courtlistener-docket-101",
                "docket_id": "101",
                "docket_url": "https://www.courtlistener.com/docket/101/example/",
                "entry_keys": ["entry-101"],
                "matched_terms": ["motion to dismiss"],
                "eligibility_status": "potential_unverified",
            }
        )
        + "\n"
    )
    output_root = tmp_path / "output"

    for attempt in range(3):
        fixture = tmp_path / f"timeout-{attempt}.jsonl"
        fixture.write_text(
            "\n".join(json.dumps(_timeout_response("101")) for _ in range(3)) + "\n"
        )
        exit_code = cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--case-dev-fixture",
                str(fixture),
                "--execute",
                "--resume",
            ]
        )
        assert exit_code == (2 if attempt < 2 else 0)

    [failure] = _read_jsonl(
        output_root / "checkpoints" / "case-dev-recap-failures.jsonl"
    )
    assert failure["reason"] == "case_dev_server_error_retries_exhausted"


def test_parallel_enrichment_checkpoints_completed_sibling_before_rate_limit_abort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": f"courtlistener-docket-{docket_id}",
                    "docket_id": docket_id,
                    "docket_url": (
                        f"https://www.courtlistener.com/docket/{docket_id}/example/"
                    ),
                    "entry_keys": [f"entry-{docket_id}"],
                    "matched_terms": ["motion to dismiss"],
                    "eligibility_status": "potential_unverified",
                }
            )
            + "\n"
            for docket_id in ("101", "102", "103", "104", "105", "106")
        ),
        encoding="utf-8",
    )

    sibling_started = threading.Event()
    release_sibling = threading.Event()
    started_indices: list[int] = []

    def fake_enrich(*, input_index: int, **_kwargs: Any) -> tuple[dict[str, Any], int]:
        started_indices.append(input_index)
        if input_index == 0:
            assert sibling_started.wait(timeout=5)
            raise CaseDevRateLimitError("organization rate limit")
        if input_index == 5:
            raise AssertionError("fatal provider error must prevent replacement work")
        sibling_started.set()
        assert release_sibling.wait(timeout=5)
        return (
            {
                "input_index": input_index,
                "outcome": "success",
                "payload": {"completed": True},
            },
            1,
        )

    real_as_completed = cli_module.as_completed
    completion_pass = 0

    def fatal_then_active_sibling(futures: set[Any]) -> Any:
        nonlocal completion_pass
        completion_pass += 1
        if completion_pass == 1:
            assert sibling_started.wait(timeout=5)
            yield next(real_as_completed(futures))
            return
        release_sibling.set()
        yield from real_as_completed(futures)

    monkeypatch.setattr(
        cli_module,
        "_enrich_case_dev_progress_record",
        fake_enrich,
    )
    monkeypatch.setattr(cli_module, "as_completed", fatal_then_active_sibling)
    monkeypatch.setenv("CASE_DEV_API_KEY", "offline-test-key")
    monkeypatch.setenv("CASE_DEV_RATE_LIMIT_PER_MINUTE", "5")
    output_root = tmp_path / "output"

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--live-case-dev",
                "--workers",
                "5",
                "--execute",
            ]
        )
        == 2
    )
    progress = _read_jsonl(
        output_root / "checkpoints" / "case-dev-recap-progress.jsonl"
    )
    assert {record["input_index"] for record in progress} == {1, 2, 3, 4}
    assert all(record["outcome"] == "success" for record in progress)
    assert set(started_indices) == {0, 1, 2, 3, 4}


def test_parallel_enrichment_checks_completed_fatal_before_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dockets = tmp_path / "dockets.jsonl"
    dockets.write_text(
        "".join(
            json.dumps(
                {
                    "candidate_id": f"courtlistener-docket-{docket_id}",
                    "docket_id": docket_id,
                    "docket_url": (
                        f"https://www.courtlistener.com/docket/{docket_id}/example/"
                    ),
                    "entry_keys": [f"entry-{docket_id}"],
                    "matched_terms": ["motion to dismiss"],
                    "eligibility_status": "potential_unverified",
                }
            )
            + "\n"
            for docket_id in ("101", "102", "103", "104", "105", "106")
        ),
        encoding="utf-8",
    )
    initial_workers_finished = tuple(threading.Event() for _ in range(5))
    started_indices: list[int] = []

    def fake_enrich(*, input_index: int, **_kwargs: Any) -> tuple[dict[str, Any], int]:
        started_indices.append(input_index)
        if input_index == 0:
            initial_workers_finished[0].set()
            raise CaseDevRateLimitError("organization rate limit")
        if input_index < 5:
            initial_workers_finished[input_index].set()
        return (
            {
                "input_index": input_index,
                "outcome": "success",
                "payload": {"completed": True},
            },
            1,
        )

    real_as_completed = cli_module.as_completed
    completion_pass = 0

    def initial_success_first(futures: set[Any]) -> Any:
        nonlocal completion_pass
        completion_pass += 1
        if completion_pass == 1:
            assert all(event.wait(timeout=5) for event in initial_workers_finished)
            completed = list(real_as_completed(futures))

            def succeeded(future: Any) -> bool:
                try:
                    future.result()
                except CaseDevRateLimitError:
                    return False
                return True

            yield from sorted(completed, key=succeeded, reverse=True)
            return
        yield from real_as_completed(futures)

    monkeypatch.setattr(
        cli_module,
        "_enrich_case_dev_progress_record",
        fake_enrich,
    )
    monkeypatch.setattr(cli_module, "as_completed", initial_success_first)
    monkeypatch.setenv("CASE_DEV_API_KEY", "offline-test-key")
    monkeypatch.setenv("CASE_DEV_RATE_LIMIT_PER_MINUTE", "5")
    output_root = tmp_path / "output"

    assert (
        cli_module.main(
            [
                "acquisition",
                "enrich-recap-case-dev",
                "--output-root",
                str(output_root),
                "--dockets",
                str(dockets),
                "--live-case-dev",
                "--workers",
                "5",
                "--execute",
            ]
        )
        == 2
    )
    assert set(started_indices) == {0, 1, 2, 3, 4}


def _opinion_source_store(
    tmp_path: Path,
    *,
    search_type: str = "o",
    schema_version: str | None = None,
    available_only: str | None = None,
    query_expression: object = _QUERY_EXPRESSION_ABSENT,
    name: str = "opinion-source.sqlite3",
    docket_id: str = "101",
) -> Path:
    path = tmp_path / name
    with CycleAcquisitionStore(path) as store:
        store.ensure_cycle(
            {"schema_version": "test", "eligibility_anchor": "2026-06-30"}
        )
        term = '"motion to dismiss"'
        if schema_version is None:
            schema_version = (
                "legalforecast.courtlistener_unrestricted_recap.v1"
                if search_type == "r"
                else "legalforecast.courtlistener_opinion_discovery.v1"
            )
        config: dict[str, object] = {
            "schema_version": schema_version,
            "provider": "courtlistener",
            "search_type": search_type,
            "query_terms": [term],
            "search_window_start": "2026-06-30",
            "search_window_end": "2026-07-15",
        }
        if search_type == "r" or available_only is not None:
            config["available_only"] = (
                "omitted" if available_only is None else available_only
            )
            config["search_page_size"] = 20
        if search_type == "r" and query_expression is _QUERY_EXPRESSION_ABSENT:
            config["query_expression"] = (
                "{term} AND entry_date_filed:[{start} TO {end}]"
            )
        elif query_expression is not _QUERY_EXPRESSION_ABSENT:
            config["query_expression"] = query_expression
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
                {
                    "provider_hit_id": "cluster-501",
                    "candidate_id": docket_id,
                    "payload": {
                        "docket_id": docket_id,
                        "court_id": "dcd",
                        "docket_number": f"1:25-cv-{int(docket_id):05d}",
                        "case_name": "Example v. Example",
                        "opinion_discovery_evidence": {
                            "schema_version": (
                                "legalforecast.courtlistener_opinion_hit.v1"
                            ),
                            "cluster_id": "501",
                            "absolute_url": "/opinion/501/example-v-example/",
                            "date_filed": "2026-07-14",
                        },
                    },
                }
            ],
            next_cursor=None,
            terminal_status="exhausted",
        )
    return path


def _case_dev_response(docket_id: str) -> dict[str, object]:
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
                "url": f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/",
                "entries": [],
            }
        },
    }


def _timeout_response(docket_id: str) -> dict[str, object]:
    response = _case_dev_response(docket_id)
    response["status_code"] = 504
    response["payload"] = {"error": "case.dev request timed out"}
    return response


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]
