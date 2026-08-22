# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion import exact100_successor_replacement_cli as successor_cli
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.disclosure_review_authority import (
    disclosure_authority_identity_from_cohort_policy,
)
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    RECOVERY_RECEIPT_SCHEMA_VERSION,
    RECOVERY_REQUEST_SCHEMA_VERSION,
    RECOVERY_RUN_CARD_SCHEMA_VERSION,
    REST_OBSERVATION_SCHEMA_VERSION,
    REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
    TerminalExclusionReason,
    VerifiedTerminalExclusionEvidence,
    _mint_terminal_evidence,
    _mint_terminal_recovery_evidence_from_producer,
)
from tests.disclosure_review_fixtures import (
    service_disclosure_authority_from_policy_bytes,
)
from tests.recovered_public_capability_helpers import (
    issue_recovered_public_capability,
)
from tests.test_exact100_successor_replacement import (
    _fixture,
    _jsonl,
    _selection_row,
)
from tests.test_target_cohort_projection import (
    _completed_two_case_projection,
    _materialized_two_case_cohort,
)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value, error_type=ValueError, error_message="test serialization failed"
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _allow_test_service_disclosure_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permit the existing signed, provider-free materialization fixture."""

    validate = cli.validate_review_receipt
    validate_lineage = cli.validate_authenticated_clearance_lineage
    monkeypatch.setattr(
        cli,
        "validate_review_receipt",
        lambda *positional, **keywords: validate(
            *positional,
            **{**keywords, "allow_test_service_identity": True},
        ),
    )
    monkeypatch.setattr(
        cli,
        "validate_authenticated_clearance_lineage",
        lambda *positional, **keywords: validate_lineage(
            *positional,
            **{**keywords, "allow_test_service_identity": True},
        ),
    )
    monkeypatch.setattr(
        cli,
        "load_main_disclosure_review_authority",
        lambda cohort, *, reviewer_policy_bytes: (
            service_disclosure_authority_from_policy_bytes(
                reviewer_policy_bytes,
                identity=disclosure_authority_identity_from_cohort_policy(cohort),
            )
        ),
    )


def _write_live_shaped_parser_fixture(
    *,
    parse_root: Path,
    source_document_id: str,
) -> None:
    """Convert test Markdown records into the exact pinned parser wire shape.

    The materialization, parser requests, parse-card commitments, and Markdown
    tree remain real CLI artifacts.  This changes only the isolated fixture
    transport marker so the production verifier exercises its live-output
    acceptance path without a provider call.
    """

    manifest_path = parse_root / "mistral-markdown-conversions.jsonl"
    parser_records = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
    ]
    assert parser_records
    for record in parser_records:
        document_id = str(record["source_document_id"])
        markdown_path = parse_root / str(record["markdown_path"])
        if document_id == source_document_id:
            markdown_path.write_text(
                (
                    "# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n"
                    "The parties submit this synthetic outcome fixture for the "
                    "authenticated replay path and its commitment checks.\n"
                    "This text is intentionally provider-free test material.\n"
                    "The fixture keeps the replay test deterministic and "
                    "self-contained.\n"
                ),
                encoding="utf-8",
            )
        markdown_bytes = markdown_path.read_bytes()
        record["parser_config"] = {
            "engine": "mistral",
            "parser_revision": EXPECTED_PARSER_REVISION,
            "expected_parser_revision": EXPECTED_PARSER_REVISION,
        }
        record["extracted_text"]["extraction_method"] = "mistral_parser_markdown"
        record["extracted_text"]["text_sha256"] = _sha(markdown_bytes)
    manifest_bytes = _jsonl(parser_records)
    manifest_path.write_bytes(manifest_bytes)

    card_path = parse_root / "run-cards/parse-documents.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    card["output_commitments"]["parser_manifest"]["sha256"] = _sha(manifest_bytes)
    card["parser_execution"] = {
        "mode": "live_mistral",
        "engine": "mistral",
        "parser_revision": EXPECTED_PARSER_REVISION,
        "parser_root": "/test/pinned-mistral-parser",
        "fixture_markdown": False,
    }
    card_path.write_bytes(_bytes(card))


def _completed_authenticated_stipulated_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, bytes]:
    """Build one real materialization/parse/audit root with one stipulated MTD."""

    _allow_test_service_disclosure_authority(monkeypatch)
    materialized = _materialized_two_case_cohort(tmp_path / "cohort")
    parse_root = tmp_path / "parse"
    selection = materialized["selection"]
    manifest = materialized["manifest"]
    clearance = materialized["clearance"]
    document_root = materialized["document_root"]
    materialization_card = materialized["run_card"]
    runtime_args = [
        "--purchase-policy",
        str(materialized["purchase_policy"]),
        "--purchase-ledger",
        str(materialized["purchase_ledger"]),
        "--controlled-private-root",
        str(materialized["controlled_private_root"]),
        "--purchase-ledger-initialization-receipt",
        str(materialized["purchase_ledger_initialization_receipt"]),
    ]
    audit_replay_args = [
        "--controlled-private-root",
        str(materialized["controlled_private_root"]),
        "--purchase-ledger-initialization-receipt",
        str(materialized["purchase_ledger_initialization_receipt"]),
    ]
    assert (
        cli.main(
            [
                "acquisition",
                "plan-parse-documents",
                "--selection",
                str(selection),
                "--download-manifest",
                str(manifest),
                "--disclosure-clearance",
                str(clearance),
                "--document-root",
                str(document_root),
                "--materialization-run-card",
                str(materialization_card),
                *runtime_args,
                "--output-root",
                str(parse_root),
                "--execute",
            ]
        )
        == 0
    )
    requests_path = parse_root / "parse-document-requests.jsonl"
    requests = [
        json.loads(line)
        for line in requests_path.read_text(encoding="utf-8").splitlines()
    ]
    selection_records = [
        json.loads(line) for line in selection.read_text(encoding="utf-8").splitlines()
    ]
    target_document_id = next(
        str(document["source_document_id"])
        for record in selection_records
        for document in record["documents"]
        if document["document_role"] == "motion_to_dismiss_memorandum"
    )
    markdown_fixtures = tmp_path / "markdown-fixtures"
    markdown_fixtures.mkdir()
    for request in requests:
        (markdown_fixtures / f"{request['source_document_id']}.md").write_text(
            (
                f"Public filing {request['source_document_id']}\n"
                "This synthetic fixture contains enough substantive filing text "
                "to exercise the authenticated parser and downstream lineage gate.\n"
                "It is provider-free test content and is not a source document.\n"
                "The fixture keeps the replay test deterministic and self-contained."
            ),
            encoding="utf-8",
        )
    assert (
        cli.main(
            [
                "acquisition",
                "parse-documents",
                "--selection",
                str(selection),
                "--requests",
                str(requests_path),
                "--disclosure-clearance",
                str(clearance),
                "--materialization-run-card",
                str(materialization_card),
                *runtime_args,
                "--fixture-markdown-dir",
                str(markdown_fixtures),
                "--output-root",
                str(parse_root),
                "--execute",
            ]
        )
        == 0
    )
    _write_live_shaped_parser_fixture(
        parse_root=parse_root,
        source_document_id=target_document_id,
    )
    audit_root = tmp_path / "completed-eligibility-audit"
    assert (
        cli.main(
            [
                "acquisition",
                "audit-stage-a-target-eligibility",
                "--selection",
                str(selection),
                "--selection-run-card",
                str(selection.parent / "run-cards/project-target-cohort.json"),
                "--download-manifest",
                str(manifest),
                "--disclosure-clearance",
                str(clearance),
                "--materialization-run-card",
                str(materialization_card),
                "--document-root",
                str(document_root),
                "--parse-requests",
                str(requests_path),
                "--parser-manifest",
                str(parse_root / "mistral-markdown-conversions.jsonl"),
                "--parser-run-card",
                str(parse_root / "run-cards/parse-documents.json"),
                "--markdown-root",
                str(parse_root / "markdown"),
                *audit_replay_args,
                "--output-root",
                str(audit_root),
                "--execute",
            ]
        )
        == 0
    )
    return audit_root, selection.read_bytes()


def _audit_predecessor_manifest_bytes(root: Path) -> bytes:
    card = json.loads(
        (root / "run-cards/audit-stage-a-target-eligibility.json").read_text(
            encoding="utf-8"
        )
    )
    return Path(str(card["input_paths"][2])).read_bytes()


def _stipulated_evidence(
    root: Path,
    *,
    candidate_id: str = "C001",
    source_document: bytes = b"authenticated PDF source",
) -> Path:
    root.mkdir()
    document_id = f"{candidate_id}-motion"
    markdown = b"# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n"
    request = {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "input_path": f"/authenticated/{candidate_id}/{document_id}.pdf",
        "expected_sha256": _sha(source_document),
        "expected_byte_count": len(source_document),
        "markdown_output_path": f"/authenticated/{candidate_id}/{document_id}.md",
    }
    requests_bytes = _bytes(request)
    record: dict[str, Any] = {
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "status": "succeeded",
        "input_path": request["input_path"],
        "markdown_path": request["markdown_output_path"],
        "parser_config": {
            "engine": "mistral",
            "parser_revision": EXPECTED_PARSER_REVISION,
            "expected_parser_revision": EXPECTED_PARSER_REVISION,
        },
        "quality_flags": [],
        "source_sha256": _sha(source_document),
        "source_byte_count": len(source_document),
        "extracted_text": {
            "source_document_id": document_id,
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": _sha(markdown),
        },
    }
    manifest_bytes = _bytes(record)
    run_card: dict[str, Any] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "parse-documents",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "record_count": 1,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "source_commitments": {
            "requests": {"path": "parse-requests.jsonl", "sha256": _sha(requests_bytes)}
        },
        "output_commitments": {
            "parser_manifest": {
                "path": "mistral-markdown-conversions.jsonl",
                "sha256": _sha(manifest_bytes),
            }
        },
        "parser_execution": {
            "mode": "live_mistral",
            "engine": "mistral",
            "parser_revision": EXPECTED_PARSER_REVISION,
            "fixture_markdown": False,
        },
    }
    files = {
        "parser-requests.jsonl": requests_bytes,
        "parser-record.json": _bytes(record),
        "parser-manifest.json": manifest_bytes,
        "parser-run-card.json": _bytes(run_card),
        "document.md": markdown,
        "document.pdf": source_document,
    }
    for name, payload in files.items():
        (root / name).write_bytes(payload)
    return root


def _recovery_evidence(root: Path, *, candidate_id: str = "C001") -> Path:
    root.mkdir()
    document_id = f"{candidate_id}-motion"
    docket_id = f"docket-{candidate_id}"
    docket_entry_id = f"entry-{candidate_id}"
    response = b'{"detail":"Not found."}'
    request = {
        "schema_version": RECOVERY_REQUEST_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": docket_id,
        "courtlistener_docket_entry_id": docket_entry_id,
        "recovery_mode": "courtlistener_rest_noncharging_only",
        "paid_permitted": False,
        "pacer_permitted": False,
        "recap_fetch_permitted": False,
        "selection_sha256": "deferred",
    }
    # The sealed predecessor binds the selection at replay time.  Populate the
    # request below once the fixture's deterministic selection is available.
    selection = b"".join(
        _bytes(_selection_row(f"C{number:03d}")) for number in range(1, 101)
    )
    request["selection_sha256"] = _sha(selection)
    request_bytes = _bytes(request)
    transcript = {
        "schema_version": REST_OBSERVATION_TRANSCRIPT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": docket_id,
        "courtlistener_docket_entry_id": docket_entry_id,
        "request_method": "GET",
        "request_path": f"/api/rest/v4/recap-documents/{document_id}/",
        "status_code": 404,
        "response_sha256": _sha(response),
        "terminal_status": "unavailable",
        "terminal": True,
    }
    transcript_bytes = _bytes(transcript)
    observation = {
        "schema_version": REST_OBSERVATION_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "courtlistener_docket_id": docket_id,
        "courtlistener_docket_entry_id": docket_entry_id,
        "request_sha256": _sha(request_bytes),
        "terminal_status": "unavailable",
        "completed": True,
        "retryable": False,
        "recovered": False,
        "transcript_sha256": _sha(transcript_bytes),
        "transcript_record_count": 1,
    }
    observation_bytes = _bytes(observation)
    receipt = {
        "schema_version": RECOVERY_RECEIPT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_document_id": document_id,
        "document_role": "motion_to_dismiss_memorandum",
        "recovery_mode": "courtlistener_rest_noncharging_only",
        "terminal_status": "unavailable",
        "completed": True,
        "retryable": False,
        "recovered": False,
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "fee_acknowledged": False,
        "request_sha256": _sha(request_bytes),
        "rest_observation_sha256": _sha(observation_bytes),
        "rest_observation_transcript_sha256": _sha(transcript_bytes),
    }
    receipt_bytes = _bytes(receipt)
    run_card = {
        "schema_version": RECOVERY_RUN_CARD_SCHEMA_VERSION,
        "stage": "recover-exact100-target-document-zero-cost",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "record_count": 1,
        "provider_activity_requested": True,
        "provider_activity_executed": True,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "fee_acknowledged": False,
        "input_commitments": {
            "request": _sha(request_bytes),
            "selection": _sha(selection),
        },
        "output_commitments": {
            "receipt": _sha(receipt_bytes),
            "rest_observation": _sha(observation_bytes),
            "rest_observation_transcript": _sha(transcript_bytes),
            "rest_observation_response": _sha(response),
        },
    }
    for name, payload in {
        "recovery-request.json": request_bytes,
        "recovery-receipt.json": receipt_bytes,
        "recovery-run-card.json": _bytes(run_card),
        "rest-observation.json": observation_bytes,
        "rest-observation-transcript.jsonl": transcript_bytes,
        "rest-observation-response.bin": response,
    }.items():
        (root / name).write_bytes(payload)
    return root


def _rewrite_recovery_response_self_consistently(
    root: Path, *, response_bytes: bytes
) -> None:
    """Rewrite every caller-owned commitment around a fabricated response."""

    transcript_path = (
        root / successor_cli._RECOVERY_FILES["rest_observation_transcript"]
    )
    transcript = json.loads(transcript_path.read_bytes())
    transcript["response_sha256"] = _sha(response_bytes)
    transcript_bytes = _bytes(transcript)
    transcript_path.write_bytes(transcript_bytes)

    observation_path = root / successor_cli._RECOVERY_FILES["rest_observation"]
    observation = json.loads(observation_path.read_bytes())
    observation["transcript_sha256"] = _sha(transcript_bytes)
    observation_bytes = _bytes(observation)
    observation_path.write_bytes(observation_bytes)

    receipt_path = root / successor_cli._RECOVERY_FILES["receipt"]
    receipt = json.loads(receipt_path.read_bytes())
    receipt["rest_observation_sha256"] = _sha(observation_bytes)
    receipt["rest_observation_transcript_sha256"] = _sha(transcript_bytes)
    receipt_bytes = _bytes(receipt)
    receipt_path.write_bytes(receipt_bytes)

    response_path = root / successor_cli._RECOVERY_FILES["rest_observation_response"]
    response_path.write_bytes(response_bytes)
    run_card_path = root / successor_cli._RECOVERY_FILES["run_card"]
    run_card = json.loads(run_card_path.read_bytes())
    run_card["output_commitments"] = {
        "receipt": _sha(receipt_bytes),
        "rest_observation": _sha(observation_bytes),
        "rest_observation_transcript": _sha(transcript_bytes),
        "rest_observation_response": _sha(response_bytes),
    }
    run_card_path.write_bytes(_bytes(run_card))


@pytest.fixture(autouse=True)
def _fresh_terminal_recovery_test_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replace only the private live-observation dependency in offline tests."""

    calls = 0

    def replay(
        *, selection_bytes: bytes, plan_bytes: bytes
    ) -> VerifiedTerminalExclusionEvidence:
        nonlocal calls
        calls += 1
        record = json.loads(plan_bytes)["records"][0]
        root = _recovery_evidence(
            tmp_path / f"fresh-live-recovery-{calls}",
            candidate_id=str(record["candidate_id"]),
        )
        payloads = {
            name: (root / filename).read_bytes()
            for name, filename in successor_cli._RECOVERY_FILES.items()
        }
        return _mint_terminal_recovery_evidence_from_producer(
            selection_bytes=selection_bytes,
            request=json.loads(payloads["request"]),
            request_bytes=payloads["request"],
            receipt=json.loads(payloads["receipt"]),
            receipt_bytes=payloads["receipt"],
            run_card=json.loads(payloads["run_card"]),
            run_card_bytes=payloads["run_card"],
            rest_observation=json.loads(payloads["rest_observation"]),
            rest_observation_bytes=payloads["rest_observation"],
            rest_observation_transcript_bytes=payloads["rest_observation_transcript"],
            rest_observation_response_bytes=payloads["rest_observation_response"],
        )

    monkeypatch.setattr(cli, "execute_terminal_recovery_for_successor", replay)


def _command(
    *, predecessor: Path, evidence: Path, output: Path, stipulated: bool = False
) -> list[str]:
    return [
        "acquisition",
        "project-exact100-successor-replacement",
        "--predecessor-root",
        str(predecessor),
        "--stipulated-evidence-root" if stipulated else "--recovery-evidence-root",
        str(evidence),
        "--output-root",
        str(output),
    ]


def _test_only_replay(root: Path) -> tuple[Any, Any]:
    inputs = _fixture()
    return inputs["predecessor"], inputs["promotion_pool"]


def _write_legacy_hash_consistent_forgery(
    root: Path,
    *,
    predecessor_config: dict[str, Any],
    predecessor_output_bytes: dict[str, bytes],
    reserve: list[dict[str, Any]],
    reserve_selection: list[dict[str, Any]],
    reserve_artifacts: dict[str, list[dict[str, Any]]],
) -> None:
    """Write the retired self-authenticating predecessor shape for rejection."""

    root.joinpath("predecessor-config.json").write_bytes(_bytes(predecessor_config))
    for name, payload in predecessor_output_bytes.items():
        root.joinpath(f"predecessor-{name}").write_bytes(payload)
    promotion_bytes = {
        "ranked_reserve": _jsonl(reserve),
        "source_selection": _jsonl(reserve_selection),
        **{name: _jsonl(rows) for name, rows in reserve_artifacts.items()},
    }
    commitments = {name: _sha(payload) for name, payload in promotion_bytes.items()}
    authority = {
        "provider_activity_permitted": False,
        "paid_activity_permitted": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    producer_config = {
        "schema_version": (
            "legalforecast.exact100_successor_replacement_inputs_config.v1"
        ),
        "status": "completed",
        "source_commitments": commitments,
        **authority,
    }
    producer_config_bytes = _bytes(producer_config)
    producer_run_card = {
        "schema_version": (
            "legalforecast.exact100_successor_replacement_inputs_run_card.v1"
        ),
        "stage": "replay-exact100-successor-replacement-inputs",
        "status": "completed",
        "config_sha256": _sha(producer_config_bytes),
        "source_commitments": commitments,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    producer_run_card_bytes = _bytes(producer_run_card)
    producer_root = {
        "schema_version": "legalforecast.exact100_successor_replacement_inputs_root.v1",
        "producer_config_sha256": _sha(producer_config_bytes),
        "producer_run_card_sha256": _sha(producer_run_card_bytes),
        "source_commitments": commitments,
        **authority,
    }
    root.joinpath("promotion-producer-config.json").write_bytes(producer_config_bytes)
    root.joinpath("promotion-producer-run-card.json").write_bytes(
        producer_run_card_bytes
    )
    root.joinpath("promotion-producer-root.json").write_bytes(_bytes(producer_root))
    for name, payload in promotion_bytes.items():
        file_name = {
            "ranked_reserve": "ranked-reserve.jsonl",
            "source_selection": "source-selection.jsonl",
            "case_relevance": "case-relevance.jsonl",
            "download_manifest": "document-downloads-merged.jsonl",
            "disclosure_clearance": "disclosure-clearance.jsonl",
            "restriction_evidence": "restriction-evidence.jsonl",
            "core_filter_results": "core-filter-results.jsonl",
        }[name]
        root.joinpath(f"promotion-{file_name}").write_bytes(payload)


def test_successor_cli_replays_sealed_input_and_materializer_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"

    monkeypatch.setattr(
        cli,
        "_replay_exact100_successor_inputs",
        _test_only_replay,
    )
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0
    verified = cli.verify_completed_target_cohort_projection_for_purchase_approval(
        output
    )

    selection_records = cast(list[dict[str, object]], verified["selection_records"])
    assert [record["candidate_id"] for record in selection_records][-1] == "R2"
    assert len(selection_records) == 100
    assert (output / "successor-terminal-exclusions.jsonl").is_file()
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0


def _write_cache_test_projection_root(
    root: Path, *, input_count: int = 9
) -> tuple[Path, Path]:
    config_path = root.parent / f"{root.name}-config.json"
    config_path.write_bytes(_bytes({"target_case_count": 1}))
    run_card_path = root / "run-cards/project-target-cohort.json"
    run_card_path.parent.mkdir(parents=True)
    run_card_path.write_bytes(
        _bytes(
            {
                "schema_version": "legalforecast.acquisition_run_card.v1",
                "input_paths": [str(config_path)] * input_count,
            }
        )
    )
    artifact_path = root / "target-cohort-selection.jsonl"
    artifact_path.write_bytes(b'{"candidate_id":"case-1"}\n')
    return artifact_path, config_path


def _cache_test_projection_evidence(
    root: Path,
    artifact_path: Path,
    *,
    operation: cli._VerifiedProjectionOperation | None = None,
) -> dict[str, object]:
    run_card_path = root / "run-cards/project-target-cohort.json"
    run_card = json.loads(run_card_path.read_bytes())
    config_path = Path(cast(list[str], run_card["input_paths"])[7])
    result: dict[str, object] = {
        "verified_artifact_bytes": {
            str(run_card_path.absolute()): run_card_path.read_bytes(),
            str(artifact_path.absolute()): artifact_path.read_bytes(),
            str(config_path.absolute()): config_path.read_bytes(),
        }
    }
    if operation is not None:
        operation.record_byte_closure(
            target_root=root,
            run_card_bytes=run_card_path.read_bytes(),
            snapshots=cast(Mapping[str, bytes], result["verified_artifact_bytes"]),
        )
    return result


def test_projection_verifier_reuses_only_one_byte_closed_root_per_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer_root = tmp_path / "outer"
    original_root = tmp_path / "original"
    outer_artifact, _ = _write_cache_test_projection_root(outer_root)
    original_artifact, _ = _write_cache_test_projection_root(original_root)
    invocation_counts: Counter[Path] = Counter()
    read_counts: Counter[Path] = Counter()
    read_input = cli._read_singly_linked_regular_input

    def counted_read(path: Path, *, label: str) -> bytes:
        read_counts[path.absolute()] += 1
        return read_input(path, label=label)

    monkeypatch.setattr(cli, "_read_singly_linked_regular_input", counted_read)

    def verify_projection(*, target_root: Path, **_kwargs: object) -> dict[str, object]:
        invocation_counts[target_root] += 1
        artifact_path = (
            outer_artifact if target_root == outer_root else original_artifact
        )
        result = _cache_test_projection_evidence(
            target_root,
            artifact_path,
            operation=cast(
                cli._VerifiedProjectionOperation,
                _kwargs["_verified_projection_operation"],
            ),
        )
        if target_root == outer_root:
            first = cli.verify_completed_target_cohort_projection_for_purchase_approval(
                original_root
            )
            first["consumer_mutation"] = True
            second = (
                cli.verify_completed_target_cohort_projection_for_purchase_approval(
                    original_root
                )
            )
            assert "consumer_mutation" not in second
            assert second is not first
        return result

    monkeypatch.setattr(cli, "_verify_materializer_projection", verify_projection)

    cli.verify_completed_target_cohort_projection_for_purchase_approval(outer_root)

    assert invocation_counts == Counter({outer_root: 1, original_root: 1})
    assert read_counts[original_artifact.absolute()] == 1
    # Three verification reads plus one to derive the content-addressed
    # relocation for a committed input whose capture directory may be gone.
    # The derivation is memoized per target root, so re-entry does not add
    # more; the property under test -- one byte-closed root per operation --
    # is unchanged.
    assert (
        read_counts[(original_root / "run-cards/project-target-cohort.json").absolute()]
        == 4
    )

    cli.verify_completed_target_cohort_projection_for_purchase_approval(outer_root)

    assert invocation_counts == Counter({outer_root: 2, original_root: 2})
    assert read_counts[original_artifact.absolute()] == 2


def test_projection_verifier_rechecks_cached_exact_bytes_before_reuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer_root = tmp_path / "outer"
    original_root = tmp_path / "original"
    outer_artifact, _ = _write_cache_test_projection_root(outer_root)
    original_artifact, _ = _write_cache_test_projection_root(original_root)
    invocation_counts: Counter[Path] = Counter()

    def verify_projection(*, target_root: Path, **_kwargs: object) -> dict[str, object]:
        invocation_counts[target_root] += 1
        artifact_path = (
            outer_artifact if target_root == outer_root else original_artifact
        )
        result = _cache_test_projection_evidence(
            target_root,
            artifact_path,
            operation=cast(
                cli._VerifiedProjectionOperation,
                _kwargs["_verified_projection_operation"],
            ),
        )
        if target_root == outer_root:
            cli.verify_completed_target_cohort_projection_for_purchase_approval(
                original_root
            )
            original_artifact.write_bytes(b'{"candidate_id":"mutated"}\n')
            cli.verify_completed_target_cohort_projection_for_purchase_approval(
                original_root
            )
        return result

    monkeypatch.setattr(cli, "_verify_materializer_projection", verify_projection)

    with pytest.raises(cli.CommandError, match="changed during execution"):
        cli.verify_completed_target_cohort_projection_for_purchase_approval(outer_root)

    assert invocation_counts == Counter({outer_root: 1, original_root: 1})


def test_projection_verifier_propagates_cached_bytes_to_enclosing_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "projection"
    artifact, _ = _write_cache_test_projection_root(root)
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )

    def verify_projection(*, target_root: Path, **kwargs: object) -> dict[str, object]:
        return _cache_test_projection_evidence(
            target_root,
            artifact,
            operation=cast(
                cli._VerifiedProjectionOperation,
                kwargs["_verified_projection_operation"],
            ),
        )

    monkeypatch.setattr(cli, "_verify_materializer_projection", verify_projection)
    try:
        cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=operation
        )
        enclosing: dict[str, bytes] = {}
        token = cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.set(enclosing)
        try:
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=operation
            )
        finally:
            cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.reset(token)
        assert enclosing[os.path.abspath(artifact)] == artifact.read_bytes()
    finally:
        operation.invalidate()


def test_projection_verifier_rechecks_recovered_public_transitive_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = _completed_two_case_projection(
        tmp_path / "completed-projection",
        provenance_first=True,
        monkeypatch=monkeypatch,
    )
    target_root = completed["projection"]
    recovery_source = tmp_path / "authenticated-recovery-source.json"
    recovery_source.write_bytes(b'{"status":"completed"}\n')
    capability = issue_recovered_public_capability(
        monkeypatch,
        [],
        source_snapshots={recovery_source.resolve(): recovery_source.read_bytes()},
    )
    verify_clearance = cli._verify_materializer_clearance_lineage

    def recovered_public_lineage(**kwargs: object) -> dict[str, object]:
        return {
            **verify_clearance(**kwargs),  # type: ignore[arg-type]
            "lineage_kind": "provider_free_recovered_public",
            "authenticated_recovery_capability": capability,
        }

    monkeypatch.setattr(
        cli, "_verify_materializer_clearance_lineage", recovered_public_lineage
    )
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )
    try:
        first = cli._verify_completed_target_cohort_projection_in_operation(
            target_root, operation=operation
        )
        recovery_source.write_bytes(b'{"status":"mutated"}\n')
        with pytest.raises(cli.CommandError, match="changed during execution"):
            cli._verify_completed_target_cohort_projection_in_operation(
                target_root, operation=operation
            )
    finally:
        operation.invalidate()

    assert first["selection_records"]


def test_projection_verifier_cache_preserves_permitted_sidecar_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = _completed_two_case_projection(
        tmp_path / "completed-projection",
        provenance_first=True,
        monkeypatch=monkeypatch,
    )
    target_root = completed["projection"]
    (target_root / "projection-diagnostics.json").write_bytes(b"{}\n")
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )
    try:
        first = cli._verify_completed_target_cohort_projection_in_operation(
            target_root, operation=operation
        )
        cached = cli._verify_completed_target_cohort_projection_in_operation(
            target_root, operation=operation
        )
    finally:
        operation.invalidate()

    assert cached == first


def test_projection_verifier_rereads_replacement_ledger_in_existing_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer_root = tmp_path / "outer"
    replacement_root = tmp_path / "replacement"
    outer_artifact, _ = _write_cache_test_projection_root(outer_root)
    replacement_artifact, replacement_config = _write_cache_test_projection_root(
        replacement_root, input_count=19
    )
    ledger_path = tmp_path / "purchase-ledger.sqlite3"
    ledger_path.write_bytes(b"initial ledger")
    replacement_card_path = replacement_root / "run-cards/project-target-cohort.json"
    replacement_card = json.loads(replacement_card_path.read_bytes())
    replacement_card["input_paths"][-1] = str(ledger_path)
    replacement_card_path.write_bytes(_bytes(replacement_card))
    events: list[str] = []
    ledger_reads: list[bytes] = []
    read_input = cli._read_singly_linked_regular_input

    def counted_read(path: Path, *, label: str) -> bytes:
        if path.absolute() in {
            (replacement_root / "run-cards/project-target-cohort.json").absolute(),
            replacement_config.absolute(),
            ledger_path.absolute(),
        }:
            events.append(label)
        return read_input(path, label=label)

    monkeypatch.setattr(cli, "_read_singly_linked_regular_input", counted_read)

    def verify_projection(*, target_root: Path, **_kwargs: object) -> dict[str, object]:
        if target_root == outer_root:
            cli.verify_completed_target_cohort_projection_for_purchase_approval(
                replacement_root
            )
            ledger_path.write_bytes(b"mutated ledger")
            cli.verify_completed_target_cohort_projection_for_purchase_approval(
                replacement_root
            )
            return _cache_test_projection_evidence(outer_root, outer_artifact)
        payload = cli._read_singly_linked_regular_input(
            ledger_path, label="replacement purchase ledger"
        )
        ledger_reads.append(payload)
        if payload != b"initial ledger":
            raise cli.CommandError("purchase ledger changed during replacement replay")
        return _cache_test_projection_evidence(replacement_root, replacement_artifact)

    monkeypatch.setattr(cli, "_verify_materializer_projection", verify_projection)

    with pytest.raises(cli.CommandError, match="purchase ledger changed"):
        cli.verify_completed_target_cohort_projection_for_purchase_approval(outer_root)

    assert ledger_reads == [b"initial ledger", b"mutated ledger"]
    # The first two reads derive the content-addressed relocation for a
    # committed input whose capture directory may be gone; it is memoized per
    # target root, so it happens once rather than at every re-entry. What this
    # test guards is unchanged: the ledger is re-read in order on each replay
    # rather than served from a cache.
    assert events == [
        "target projection run card",
        "zero-cost successor clearance run card",
        "target projection run card",
        "preparation config",
        "replacement purchase ledger",
        "target projection run card",
        "preparation config",
        "replacement purchase ledger",
    ]


def test_projection_verifier_never_caches_zero_cost_ledger_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer_root = tmp_path / "outer"
    zero_cost_root = tmp_path / "zero-cost"
    outer_artifact, _ = _write_cache_test_projection_root(outer_root)
    zero_cost_card_path = zero_cost_root / "run-cards/project-target-cohort.json"
    zero_cost_card_path.parent.mkdir(parents=True)
    zero_cost_card_path.write_bytes(
        _bytes(
            {
                "schema_version": cli.ZERO_COST_SUCCESSOR_STATE_SCHEMA,
                "selected_case_count": 1,
            }
        )
    )
    zero_cost_artifact = zero_cost_root / "target-cohort-selection.jsonl"
    zero_cost_artifact.write_bytes(b'{"candidate_id":"case-1"}\n')
    ledger_path = tmp_path / "purchase-ledger.sqlite3"
    ledger_path.write_bytes(b"initial ledger")
    ledger_reads: list[bytes] = []

    def verify_projection(*, target_root: Path, **_kwargs: object) -> dict[str, object]:
        cli.verify_completed_target_cohort_projection_for_purchase_approval(
            zero_cost_root
        )
        ledger_path.write_bytes(b"mutated ledger")
        cli.verify_completed_target_cohort_projection_for_purchase_approval(
            zero_cost_root
        )
        return _cache_test_projection_evidence(target_root, outer_artifact)

    def verify_zero_cost(**_kwargs: object) -> dict[str, object]:
        payload = cli._read_singly_linked_regular_input(
            ledger_path, label="zero-cost purchase ledger"
        )
        ledger_reads.append(payload)
        if payload != b"initial ledger":
            raise cli.CommandError("purchase ledger changed during zero-cost replay")
        return {
            "verified_artifact_bytes": {
                str(zero_cost_card_path.absolute()): zero_cost_card_path.read_bytes(),
                str(zero_cost_artifact.absolute()): zero_cost_artifact.read_bytes(),
            }
        }

    monkeypatch.setattr(cli, "_verify_materializer_projection", verify_projection)
    monkeypatch.setattr(cli, "_verify_zero_cost_successor_projection", verify_zero_cost)

    with pytest.raises(cli.CommandError, match="purchase ledger changed"):
        cli.verify_completed_target_cohort_projection_for_purchase_approval(outer_root)

    assert ledger_reads == [b"initial ledger", b"mutated ledger"]


def test_projection_cache_isolated_from_inherited_tasks_and_threads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outer_root = tmp_path / "outer"
    original_root = tmp_path / "original"
    outer_artifact, _ = _write_cache_test_projection_root(outer_root)
    original_artifact, _ = _write_cache_test_projection_root(original_root)
    invocation_counts: Counter[Path] = Counter()
    task_holder: list[asyncio.Task[dict[str, object]]] = []

    async def scenario() -> None:
        release_child = asyncio.Event()

        async def inherited_child() -> dict[str, object]:
            await release_child.wait()
            return cli.verify_completed_target_cohort_projection_for_purchase_approval(
                original_root
            )

        def verify_projection(
            *, target_root: Path, **_kwargs: object
        ) -> dict[str, object]:
            invocation_counts[target_root] += 1
            artifact_path = (
                outer_artifact if target_root == outer_root else original_artifact
            )
            result = _cache_test_projection_evidence(
                target_root,
                artifact_path,
                operation=cast(
                    cli._VerifiedProjectionOperation,
                    _kwargs["_verified_projection_operation"],
                ),
            )
            if target_root == outer_root:
                cli.verify_completed_target_cohort_projection_for_purchase_approval(
                    original_root
                )
                task_holder.append(asyncio.create_task(inherited_child()))
                inherited_context = copy_context()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(
                        inherited_context.run,
                        cli.verify_completed_target_cohort_projection_for_purchase_approval,
                        original_root,
                    ).result()
            return result

        monkeypatch.setattr(cli, "_verify_materializer_projection", verify_projection)
        cli.verify_completed_target_cohort_projection_for_purchase_approval(outer_root)
        release_child.set()
        await task_holder[0]

    asyncio.run(scenario())

    assert invocation_counts == Counter({original_root: 3, outer_root: 1})


def test_projection_operation_rejects_live_inherited_task() -> None:
    async def scenario() -> None:
        owner_task = asyncio.current_task()
        assert owner_task is not None
        operation = cli._VerifiedProjectionOperation(
            owner_thread_id=get_ident(),
            owner_task_id=id(owner_task),
            cache={},
            byte_closures={},
        )

        async def inherited() -> bool:
            return operation.is_live_owner()

        try:
            assert operation.is_live_owner()
            assert await asyncio.create_task(inherited()) is False
        finally:
            operation.invalidate()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mutated_class",
    [
        "successor_output",
        "plan",
        "bridge",
        "supplemental_pdf",
        "promoted_pdf",
        "v2_output",
        "v2_transitive_source",
        "purchase_initialization_receipt",
        "purchase_ledger_db",
        "purchase_ledger_wal",
        "purchase_ledger_journal",
    ],
)
def test_supporting_projection_cache_reuses_complete_closure_and_deep_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutated_class: str,
) -> None:
    root = tmp_path / "supporting"
    card = root / "run-cards/project-exact100-supporting-document-successor.json"
    card.parent.mkdir(parents=True)
    card.write_bytes(
        _bytes(
            {
                "schema_version": str(cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION),
                "selected_case_count": 100,
            }
        )
    )
    closure_paths = {
        name: tmp_path / name
        for name in (
            "successor_output",
            "plan",
            "bridge",
            "supplemental_pdf",
            "promoted_pdf",
            "v2_output",
            "v2_transitive_source",
            "purchase_initialization_receipt",
            "purchase_ledger_db",
            "purchase_ledger_wal",
            "purchase_ledger_journal",
        )
    }
    for name, path in closure_paths.items():
        path.write_bytes(f"authenticated {name}".encode())
    calls = 0

    def verify(**kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        closure = cast(dict[str, bytes], kwargs["_verified_byte_closure"])
        for name in (
            "plan",
            "bridge",
            "supplemental_pdf",
            "promoted_pdf",
            "purchase_initialization_receipt",
            "purchase_ledger_db",
            "purchase_ledger_wal",
            "purchase_ledger_journal",
        ):
            path = closure_paths[name]
            closure[os.path.abspath(path)] = path.read_bytes()
        return {
            "selection_records": [{"candidate_id": "case-1"}],
            "verified_artifact_bytes": {
                os.path.abspath(card): card.read_bytes(),
                os.path.abspath(closure_paths["successor_output"]): closure_paths[
                    "successor_output"
                ].read_bytes(),
            },
            "base_v2_projection": {
                "verified_artifact_bytes": {
                    os.path.abspath(closure_paths[name]): closure_paths[
                        name
                    ].read_bytes()
                    for name in ("v2_output", "v2_transitive_source")
                }
            },
        }

    monkeypatch.setattr(
        cli, "_verify_supporting_document_downstream_projection", verify
    )
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )
    try:
        first = cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=operation
        )
        first["selection_records"] = []
        (root / "permitted-sidecar.json").write_bytes(b"{}\n")
        second = cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=operation
        )
        assert second["selection_records"] == [{"candidate_id": "case-1"}]
        assert calls == 1
        closure_paths[mutated_class].write_bytes(b"mutated")
        with pytest.raises(cli.CommandError, match="changed during execution"):
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=operation
            )
    finally:
        operation.invalidate()


def test_supporting_projection_cache_rejects_conflicting_closure_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "supporting"
    card = root / "run-cards/project-exact100-supporting-document-successor.json"
    card.parent.mkdir(parents=True)
    card.write_bytes(
        _bytes(
            {
                "schema_version": str(cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION),
                "selected_case_count": 100,
            }
        )
    )
    shared = tmp_path / "shared"
    shared.write_bytes(b"first")

    def verify(**kwargs: object) -> dict[str, object]:
        closure = cast(dict[str, bytes], kwargs["_verified_byte_closure"])
        closure[os.path.abspath(shared)] = b"first"
        return {
            "verified_artifact_bytes": {os.path.abspath(shared): b"second"},
        }

    monkeypatch.setattr(
        cli, "_verify_supporting_document_downstream_projection", verify
    )
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )
    try:
        with pytest.raises(cli.CommandError, match="evidence conflicts"):
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=operation
            )
    finally:
        operation.invalidate()


def test_supporting_projection_cache_rechecks_absence_and_propagates_hit_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "supporting"
    card = root / "run-cards/project-exact100-supporting-document-successor.json"
    card.parent.mkdir(parents=True)
    card.write_bytes(
        _bytes(
            {
                "schema_version": str(cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION),
                "selected_case_count": 100,
            }
        )
    )
    authority = tmp_path / "authority"
    authority.write_bytes(b"authority")
    absent_wal = tmp_path / "purchase.sqlite3-wal"
    calls = 0

    def verify(**kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        closure = cast(dict[str, bytes], kwargs["_verified_byte_closure"])
        closure[os.path.abspath(authority)] = authority.read_bytes()
        absence_collector = cli._VERIFIED_PROJECTION_ABSENCE_COLLECTOR.get()
        assert absence_collector is not None
        absence_collector.add(os.path.abspath(absent_wal))
        return {
            "verified_artifact_bytes": {os.path.abspath(card): card.read_bytes()},
            "base_v2_projection": {"verified_artifact_bytes": {}},
        }

    monkeypatch.setattr(
        cli, "_verify_supporting_document_downstream_projection", verify
    )
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )
    outer: dict[str, bytes] = {}
    outer_absences: set[str] = set()
    token = cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.set(outer)
    absence_token = cli._VERIFIED_PROJECTION_ABSENCE_COLLECTOR.set(outer_absences)
    try:
        cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=operation
        )
        assert os.path.abspath(absent_wal) in outer_absences
        outer.clear()
        outer_absences.clear()
        cli._verify_completed_target_cohort_projection_in_operation(
            root, operation=operation
        )
        assert calls == 1
        assert outer[os.path.abspath(authority)] == b"authority"
        assert os.path.abspath(absent_wal) in outer_absences
        absent_wal.write_bytes(b"new authority")
        with pytest.raises(cli.CommandError, match="changed during execution"):
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=operation
            )
    finally:
        cli._VERIFIED_PROJECTION_ABSENCE_COLLECTOR.reset(absence_token)
        cli._VERIFIED_PROJECTION_BYTE_COLLECTOR.reset(token)
        operation.invalidate()


def test_supporting_projection_cache_rechecks_absence_before_first_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "supporting"
    card = root / "run-cards/project-exact100-supporting-document-successor.json"
    card.parent.mkdir(parents=True)
    card.write_bytes(
        _bytes(
            {
                "schema_version": str(cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION),
                "selected_case_count": 100,
            }
        )
    )
    appeared = tmp_path / "purchase.sqlite3-wal"

    def verify(**_kwargs: object) -> dict[str, object]:
        absence_collector = cli._VERIFIED_PROJECTION_ABSENCE_COLLECTOR.get()
        assert absence_collector is not None
        absence_collector.add(os.path.abspath(appeared))
        appeared.write_bytes(b"new authority")
        return {
            "verified_artifact_bytes": {os.path.abspath(card): card.read_bytes()},
            "base_v2_projection": {"verified_artifact_bytes": {}},
        }

    monkeypatch.setattr(
        cli, "_verify_supporting_document_downstream_projection", verify
    )
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )
    try:
        with pytest.raises(cli.CommandError, match="changed during execution"):
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=operation
            )
        assert operation.cache == {}
    finally:
        operation.invalidate()


def test_supporting_projection_cache_rechecks_bytes_before_first_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "supporting"
    card = root / "run-cards/project-exact100-supporting-document-successor.json"
    card.parent.mkdir(parents=True)
    card.write_bytes(
        _bytes(
            {
                "schema_version": str(cli.SUPPORTING_DOCUMENT_SUCCESSOR_SCHEMA_VERSION),
                "selected_case_count": 100,
            }
        )
    )
    authority = tmp_path / "authority"
    authority.write_bytes(b"verified")

    def verify(**kwargs: object) -> dict[str, object]:
        closure = cast(dict[str, bytes], kwargs["_verified_byte_closure"])
        closure[os.path.abspath(authority)] = authority.read_bytes()
        authority.write_bytes(b"changed")
        return {
            "verified_artifact_bytes": {os.path.abspath(card): card.read_bytes()},
            "base_v2_projection": {"verified_artifact_bytes": {}},
        }

    monkeypatch.setattr(
        cli, "_verify_supporting_document_downstream_projection", verify
    )
    operation = cli._VerifiedProjectionOperation(
        owner_thread_id=get_ident(), cache={}, byte_closures={}
    )
    try:
        with pytest.raises(cli.CommandError, match="changed during execution"):
            cli._verify_completed_target_cohort_projection_in_operation(
                root, operation=operation
            )
        assert operation.cache == {}
    finally:
        operation.invalidate()


def test_saved_recovery_root_alone_cannot_mint_successor_authority(
    tmp_path: Path,
) -> None:
    evidence = _recovery_evidence(tmp_path / "saved-recovery")
    args = SimpleNamespace(
        predecessor_root=tmp_path / "predecessor",
        stipulated_evidence_root=[],
        recovery_evidence_root=[evidence],
        output_root=tmp_path / "successor",
        _replay_inputs=_test_only_replay,
    )

    with pytest.raises(
        successor_cli.Exact100SuccessorReplacementCliError,
        match="requires fresh producer replay",
    ):
        successor_cli.run(args)


def test_successor_rejects_self_consistent_fabricated_recovery_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "fabricated-recovery")
    _rewrite_recovery_response_self_consistently(
        evidence, response_bytes=_bytes({"detail": "fabricated terminal response"})
    )
    output = tmp_path / "successor"
    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)

    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 2
    assert not output.exists()


def test_successor_rejects_saved_404_after_fresh_nonterminal_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "saved-404")
    output = tmp_path / "successor"
    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)

    def reject_nonterminal(**_kwargs: object) -> VerifiedTerminalExclusionEvidence:
        raise ValueError("fresh CourtListener observation returned a public document")

    monkeypatch.setattr(
        cli, "execute_terminal_recovery_for_successor", reject_nonterminal
    )

    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 2
    assert not output.exists()


def test_successor_materializer_rejects_tampered_immutable_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"
    monkeypatch.setattr(
        cli,
        "_replay_exact100_successor_inputs",
        _test_only_replay,
    )
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0

    output.joinpath("case-relevance.jsonl").write_bytes(b"{}\n")
    with pytest.raises(cli.CommandError, match="output changed after replay"):
        cli.verify_completed_target_cohort_projection_for_purchase_approval(output)


def test_successor_state_rejects_invalid_input_path_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"
    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 0

    state_path = output / "run-cards/project-target-cohort.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["input_paths"][0] = 1
    with pytest.raises(
        successor_cli.Exact100SuccessorReplacementCliError,
        match="invalid completed exact100 successor run card",
    ):
        successor_cli._verify_state(
            state, target_root=output, expected_target_count=100
        )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["recovery_evidence_root_count"] = 2
    with pytest.raises(
        successor_cli.Exact100SuccessorReplacementCliError,
        match="invalid completed exact100 successor run card",
    ):
        successor_cli._verify_state(
            state, target_root=output, expected_target_count=100
        )


def test_successor_overlap_resolves_symlinked_paths(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    alias = tmp_path / "input-alias"
    alias.symlink_to(input_root, target_is_directory=True)

    assert successor_cli._overlaps(alias / "output", input_root)


def test_successor_cli_exposes_no_manual_candidate_or_provider_switches(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["acquisition", "project-exact100-successor-replacement", "--help"])
    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    assert "--predecessor-root" in help_text
    assert "--inputs-root" not in help_text
    assert "--stipulated-evidence-root" in help_text
    assert "--recovery-evidence-root" in help_text
    for forbidden in ("--candidate-id", "--drop-id", "--replacement-id", "--provider"):
        assert forbidden not in help_text


def test_successor_rejects_unexpected_output_before_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"
    output.mkdir()
    output.joinpath("unrelated.txt").write_text("no", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "_replay_exact100_successor_inputs",
        _test_only_replay,
    )
    assert cli.main(_command(predecessor=inputs, evidence=evidence, output=output)) == 2


def test_successor_cli_rejects_fabricated_hash_consistent_input_root(
    tmp_path: Path,
) -> None:
    fabricated = tmp_path / "fabricated-inputs"
    fabricated.mkdir()
    inputs = _fixture()
    _write_legacy_hash_consistent_forgery(
        fabricated,
        predecessor_config=inputs["predecessor"].projection,
        predecessor_output_bytes=inputs["predecessor_output_bytes"],
        reserve=inputs["reserve"],
        reserve_selection=inputs["reserve_selection"],
        reserve_artifacts=inputs["reserve_artifacts"],
    )
    evidence = _recovery_evidence(tmp_path / "recovery")
    output = tmp_path / "successor"

    assert (
        cli.main(_command(predecessor=fabricated, evidence=evidence, output=output))
        == 2
    )
    assert not output.exists()


def test_successor_cli_rejects_self_consistent_invented_stipulated_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    evidence = _stipulated_evidence(
        tmp_path / "invented-stipulated",
        source_document=b"invented PDF bytes with a fabricated dismissal",
    )
    output = tmp_path / "successor"

    monkeypatch.setattr(cli, "_replay_exact100_successor_inputs", _test_only_replay)

    assert (
        cli.main(
            _command(
                predecessor=inputs, evidence=evidence, output=output, stipulated=True
            )
        )
        == 2
    )
    assert not output.exists()


def test_successor_accepts_stipulated_root_only_after_authenticated_callback(
    tmp_path: Path,
) -> None:
    """The generic projector accepts only a verifier-owned stipulated capability."""

    inputs = tmp_path / "sealed-inputs"
    inputs.mkdir()
    _fixture()
    root = tmp_path / "completed-eligibility-audit"
    root.joinpath("run-cards").mkdir(parents=True)
    root.joinpath("target-document-eligibility-audit.jsonl").write_bytes(b"audit\n")
    root.joinpath("run-cards/audit-stage-a-target-eligibility.json").write_bytes(
        b"card\n"
    )
    output = tmp_path / "successor"
    calls: list[bytes] = []

    def replay(
        root_arg: Path,
        selection_bytes: bytes,
        predecessor_download_manifest_bytes: bytes,
    ) -> VerifiedTerminalExclusionEvidence:
        assert root_arg == root
        assert predecessor_download_manifest_bytes
        calls.append(selection_bytes)
        return _mint_terminal_evidence(
            candidate_id="C001",
            source_document_id="C001-motion",
            reason=TerminalExclusionReason.STIPULATED_INELIGIBLE,
            evidence_kind="test_authenticated_eligibility_replay",
            evidence_commitments={"selection": _sha(selection_bytes)},
        )

    args = SimpleNamespace(
        predecessor_root=inputs,
        stipulated_evidence_root=[root],
        recovery_evidence_root=[],
        output_root=output,
        resume=True,
        _replay_inputs=_test_only_replay,
        _replay_stipulated_eligibility=replay,
    )

    assert successor_cli.run(args) == 0
    assert len(calls) == 2
    verified = successor_cli.verify_materializer_projection(
        target_root=output,
        free_clearance_path=output / "disclosure-clearance.jsonl",
        expected_target_count=100,
        replay_inputs=_test_only_replay,
        recovery_replay=None,
        stipulated_replay=replay,
    )
    assert len(verified["selection_records"]) == 100
    assert len(calls) == 4
    records = [
        json.loads(line)
        for line in output.joinpath("successor-terminal-exclusions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert records[0]["reason"] == "stipulated_ineligible"


def test_stipulated_eligibility_replay_rejects_selection_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit's reconstructed selection cannot be substituted for the predecessor."""

    root = tmp_path / "completed-eligibility-audit"
    root.joinpath("run-cards").mkdir(parents=True)
    root.joinpath("target-document-eligibility-audit.jsonl").write_bytes(b"audit\n")
    input_paths = [str(tmp_path / f"input-{index}") for index in range(10)]
    root.joinpath("run-cards/audit-stage-a-target-eligibility.json").write_bytes(
        _bytes(
            {
                "input_paths": input_paths,
                "replay_paths": {
                    "controlled_private_root": None,
                    "purchase_ledger_initialization_receipt": None,
                },
            }
        )
    )
    monkeypatch.setattr(
        cli,
        "_verify_verified_stage_a_parse_lineage",
        lambda *_args, **_kwargs: SimpleNamespace(
            selection_bytes=b"different selection"
        ),
    )

    with pytest.raises(ValueError, match="selection differs from exact100 predecessor"):
        cli._replay_exact100_stipulated_eligibility(
            root, b"sealed predecessor", b"{}\n"
        )


def test_production_stipulated_replay_accepts_completed_authenticated_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real materializer/parser/audit chain can mint stipulated authority."""

    root, selection_bytes = _completed_authenticated_stipulated_audit(
        tmp_path, monkeypatch
    )
    predecessor_manifest = _audit_predecessor_manifest_bytes(root)

    evidence = cli._replay_exact100_stipulated_eligibility(
        root, selection_bytes, predecessor_manifest
    )
    successor_evidence = successor_cli._stipulated(
        root,
        selection_bytes,
        {},
        stipulated_replay=cli._replay_exact100_stipulated_eligibility,
        predecessor_download_manifest_bytes=predecessor_manifest,
    )

    assert evidence.reason is TerminalExclusionReason.STIPULATED_INELIGIBLE
    assert evidence.evidence_kind == "authenticated_stage_a_target_eligibility_replay"
    assert evidence.evidence_commitments["selection"] == _sha(selection_bytes)
    assert successor_evidence == evidence

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert (
        cli._replay_exact100_stipulated_eligibility(
            root, selection_bytes, predecessor_manifest
        )
        == evidence
    )


def test_production_stipulated_replay_rejects_fabricated_card_after_root_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exact100 root snapshots are insufficient without materialization replay."""

    root, selection_bytes = _completed_authenticated_stipulated_audit(
        tmp_path, monkeypatch
    )
    fabricated = tmp_path / "fabricated-eligibility-audit"
    fabricated.joinpath("run-cards").mkdir(parents=True)
    audit_path = root / "target-document-eligibility-audit.jsonl"
    card = json.loads(
        root.joinpath("run-cards/audit-stage-a-target-eligibility.json").read_text(
            encoding="utf-8"
        )
    )
    fake_selection = tmp_path / "fabricated-selection.jsonl"
    fake_selection.write_bytes(selection_bytes)
    card["input_paths"][0] = str(fake_selection)
    fabricated.joinpath("target-document-eligibility-audit.jsonl").write_bytes(
        audit_path.read_bytes()
    )
    fabricated.joinpath("run-cards/audit-stage-a-target-eligibility.json").write_bytes(
        _bytes(card)
    )

    payloads = successor_cli._root_payloads(
        fabricated,
        {
            "audit": "target-document-eligibility-audit.jsonl",
            "run_card": "run-cards/audit-stage-a-target-eligibility.json",
        },
        {},
    )
    assert payloads["audit"] == audit_path.read_bytes()
    assert (
        payloads["run_card"]
        == fabricated.joinpath(
            "run-cards/audit-stage-a-target-eligibility.json"
        ).read_bytes()
    )

    with pytest.raises(ValueError, match=r"target selection|selection"):
        cli._replay_exact100_stipulated_eligibility(
            fabricated, selection_bytes, _audit_predecessor_manifest_bytes(root)
        )


def test_production_replay_derives_both_capabilities_from_verified_snapshots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture()
    predecessor_root = tmp_path / "predecessor"
    predecessor_root.mkdir()
    predecessor_state_path = predecessor_root / "run-cards/project-target-cohort.json"
    predecessor_state_path.parent.mkdir()
    original_root = tmp_path / "original"
    original_root.mkdir()
    predecessor_state = {
        "schema_version": cli.ZERO_COST_SUCCESSOR_STATE_SCHEMA,
        "selected_case_count": 100,
        "input_paths": [
            str(original_root),
            *[str(tmp_path / f"unused-{i}") for i in range(14)],
        ],
    }
    predecessor_state_path.write_bytes(_bytes(predecessor_state))
    predecessor_summary_path = predecessor_root / "target-cohort-projection.json"
    predecessor_summary_path.write_bytes(_bytes(fixture["predecessor"].projection))
    predecessor_selection_path = predecessor_root / "target-cohort-selection.jsonl"
    predecessor_selection_path.write_bytes(fixture["selection_bytes"])
    predecessor_snapshots = {
        os.path.abspath(predecessor_state_path): predecessor_state_path.read_bytes(),
        os.path.abspath(
            predecessor_summary_path
        ): predecessor_summary_path.read_bytes(),
        **{
            os.path.abspath(predecessor_root / name): payload
            for name, payload in fixture["predecessor_output_bytes"].items()
        },
    }
    monkeypatch.setattr(
        cli,
        "_verify_zero_cost_successor_projection",
        lambda **_kwargs: {
            "run_card": predecessor_state,
            "run_card_path": predecessor_state_path,
            "summary": fixture["predecessor"].projection,
            "summary_path": predecessor_summary_path,
            "selection_path": predecessor_selection_path,
            "verified_artifact_bytes": predecessor_snapshots,
        },
    )

    original_inputs = tuple(original_root / f"input-{index}" for index in range(9))
    original_summary_path = original_root / "target-cohort-projection.json"
    original_run_card_path = original_root / "run-cards/project-target-cohort.json"
    original_run_card = {"input_paths": [str(path) for path in original_inputs]}
    original_payloads = {
        original_inputs[0]: _jsonl(fixture["reserve_selection"]),
        original_inputs[1]: _jsonl(fixture["reserve_artifacts"]["case_relevance"]),
        original_inputs[2]: _jsonl(fixture["reserve_artifacts"]["download_manifest"]),
        original_inputs[3]: _jsonl(
            fixture["reserve_artifacts"]["disclosure_clearance"]
        ),
        original_inputs[4]: b"{}\n",
        original_inputs[5]: _jsonl(
            fixture["reserve_artifacts"]["restriction_evidence"]
        ),
        original_inputs[6]: b"{}\n",
        original_inputs[7]: b"{}\n",
        original_inputs[8]: b"{}\n",
        original_root / "target-cohort-ranked-reserve.jsonl": _jsonl(
            fixture["reserve"]
        ),
        original_root / "core-filter-results.jsonl": _jsonl(
            fixture["reserve_artifacts"]["core_filter_results"]
        ),
        original_summary_path: b"{}\n",
        original_run_card_path: _bytes(original_run_card),
    }
    monkeypatch.setattr(
        cli,
        "verify_completed_target_cohort_projection_for_purchase_approval",
        lambda _root: {
            "run_card": original_run_card,
            "run_card_path": original_run_card_path,
            "summary_path": original_summary_path,
            "authenticated_input_paths": {
                "selection": original_inputs[0],
                "case_relevance": original_inputs[1],
                "download_manifest": original_inputs[2],
                "disclosure_clearance": original_inputs[3],
                "restriction_evidence": original_inputs[5],
                "snapshot_manifest": original_inputs[8],
            },
            "verified_artifact_bytes": {
                os.path.abspath(path): payload
                for path, payload in original_payloads.items()
            },
        },
    )
    monkeypatch.setattr(
        cli,
        "filter_core_documents",
        lambda _records: tuple(
            SimpleNamespace(to_record=lambda row=row: row)
            for row in fixture["reserve_artifacts"]["core_filter_results"]
        ),
    )

    predecessor, promotion_pool = cli._replay_exact100_successor_inputs(
        predecessor_root
    )

    assert len(predecessor.selection) == 100
    assert promotion_pool.promotable_candidate_ids == ("R2", "R3")

    original_payloads[original_root / "core-filter-results.jsonl"] = b"{}\n"
    with pytest.raises(cli.CommandError, match="core-filter results do not reproduce"):
        cli._replay_exact100_successor_inputs(predecessor_root)

    del predecessor_snapshots[
        os.path.abspath(predecessor_root / "core-filter-results.jsonl")
    ]
    with pytest.raises(
        cli.CommandError,
        match="authenticated projection lacks exact100 predecessor output",
    ):
        cli._replay_exact100_successor_inputs(predecessor_root)
