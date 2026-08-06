from __future__ import annotations

import hashlib
import json
import os
from argparse import Namespace
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.disclosure_clearance import (
    PDF_SCAN_SCHEMA_VERSION_V1,
    DisclosureClearanceError,
    DisclosurePdfScan,
    scan_disclosure_document_v1,
)
from legalforecast.ingestion.provenance_clearance import (
    build_provenance_clearance_plan as build_plan,
)
from legalforecast.ingestion.provenance_clearance import (
    build_provenance_clearance_plan_v3 as build_plan_v3,
)
from legalforecast.ingestion.public_marker_clearance_policy import (
    generate_public_marker_clearance_policy,
)


class _TTY:
    @staticmethod
    def isatty() -> bool:
        return True


def _jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _inputs(tmp_path: Path) -> dict[str, Path]:
    document_root = tmp_path / "documents"
    document_root.mkdir()
    manifest: list[dict[str, object]] = []
    restrictions: list[dict[str, object]] = []
    relevance_documents: list[dict[str, object]] = []
    for document_id, payload in (
        ("auto", b"auto"),
        ("marker", b"marker"),
        ("sealed", b"sealed"),
    ):
        relative_path = f"case-a/{document_id}.pdf"
        target = document_root / relative_path
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        source_url = f"https://storage.courtlistener.com/recap/case/{document_id}.pdf"
        manifest.append(
            {
                "candidate_id": "case-a",
                "source_document_id": document_id,
                "local_path": relative_path,
                "sha256": digest,
                "byte_count": len(payload),
                "free_or_purchased": "free",
                "source_provider": "courtlistener",
                "source_url": source_url,
            }
        )
        evidence = ["courtlistener_public_download_record_checked"]
        if document_id == "sealed":
            evidence = ["courtlistener_recap_document_is_sealed_true"]
        restrictions.append(
            {
                "candidate_id": "case-a",
                "source_document_id": document_id,
                "restriction_status": "public",
                "restriction_evidence": evidence,
                "is_sealed": None,
                "is_private": None,
            }
        )
        relevance_documents.append(
            {
                "source_document_id": document_id,
                "source_url_or_reference": source_url,
                "model_visible": True,
                "contains_target_outcome": False,
            }
        )
    requests = [
        {
            "schema_version": "legalforecast.disclosure_review_request.v1",
            "candidate_id": source["candidate_id"],
            "source_document_id": source["source_document_id"],
            "sha256": source["sha256"],
            "byte_count": source["byte_count"],
            "free_or_purchased": source["free_or_purchased"],
            "restriction_status": restriction["restriction_status"],
            "restriction_evidence": restriction["restriction_evidence"],
            "required_human_decision": "cleared_or_quarantined",
        }
        for source, restriction in zip(manifest, restrictions, strict=True)
    ]
    paths = {
        "requests": tmp_path / "requests.jsonl",
        "manifest": tmp_path / "manifest.jsonl",
        "restrictions": tmp_path / "restrictions.jsonl",
        "relevance": tmp_path / "case-relevance.jsonl",
        "document_root": document_root,
        "output": tmp_path / "output",
        "private": tmp_path.parent / f"{tmp_path.name}-private",
    }
    _jsonl(paths["requests"], requests)
    _jsonl(paths["manifest"], manifest)
    _jsonl(paths["restrictions"], restrictions)
    _jsonl(
        paths["relevance"],
        [{"candidate_id": "case-a", "documents": relevance_documents}],
    )
    return paths


def _complete_scan(payload: bytes) -> DisclosurePdfScan:
    return DisclosurePdfScan(
        parsed_page_count=1,
        text_scanned_page_numbers=(1,),
        ocr_scanned_page_numbers=(),
        unscanned_page_numbers=(),
        coverage_status="complete",
        diagnostics=(),
        automated_markers=("medical",) if payload == b"marker" else (),
    )


def _legacy_complete_scan(payload: bytes) -> DisclosurePdfScan:
    current = _complete_scan(payload)
    return DisclosurePdfScan(
        parsed_page_count=current.parsed_page_count,
        text_scanned_page_numbers=current.text_scanned_page_numbers,
        ocr_scanned_page_numbers=current.ocr_scanned_page_numbers,
        unscanned_page_numbers=current.unscanned_page_numbers,
        coverage_status=current.coverage_status,
        diagnostics=("legacy_extraction_page_count_mismatch",),
        automated_markers=current.automated_markers,
        schema_version=PDF_SCAN_SCHEMA_VERSION_V1,
        method="pypdf_page_text_v1",
    )


def _install_document_scanner(
    monkeypatch: pytest.MonkeyPatch, *, historical: bool = False
) -> None:
    if historical:
        monkeypatch.setattr(
            cli_module, "scan_disclosure_document", scan_disclosure_document_v1
        )

    def requested_fixture_scanner(
        kwargs: Mapping[str, object],
    ) -> Callable[[bytes], DisclosurePdfScan]:
        requested = kwargs.get("document_scanner")
        if historical and requested is scan_disclosure_document_v1:
            return _legacy_complete_scan
        return _complete_scan

    def deterministic_plan(
        review_requests: Sequence[Mapping[str, object]],
        download_manifest: Sequence[Mapping[str, object]],
        restriction_evidence: Sequence[Mapping[str, object]],
        case_relevance: Sequence[Mapping[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        typed = kwargs
        fixture_scanner = requested_fixture_scanner(cast(Mapping[str, object], typed))
        return build_plan(
            review_requests,
            download_manifest,
            restriction_evidence,
            case_relevance,
            document_root=cast(Path, typed["document_root"]),
            review_requests_bytes=cast(bytes, typed["review_requests_bytes"]),
            download_manifest_bytes=cast(bytes, typed["download_manifest_bytes"]),
            restriction_evidence_bytes=cast(bytes, typed["restriction_evidence_bytes"]),
            case_relevance_bytes=cast(bytes, typed["case_relevance_bytes"]),
            document_scanner=fixture_scanner,
        )

    monkeypatch.setattr(
        cli_module, "build_provenance_clearance_plan", deterministic_plan
    )

    def deterministic_plan_v3(
        review_requests: Sequence[Mapping[str, object]],
        download_manifest: Sequence[Mapping[str, object]],
        restriction_evidence: Sequence[Mapping[str, object]],
        case_relevance: Sequence[Mapping[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        typed = kwargs
        fixture_scanner = requested_fixture_scanner(cast(Mapping[str, object], typed))
        return build_plan_v3(
            review_requests,
            download_manifest,
            restriction_evidence,
            case_relevance,
            document_root=cast(Path, typed["document_root"]),
            review_requests_bytes=cast(bytes, typed["review_requests_bytes"]),
            download_manifest_bytes=cast(bytes, typed["download_manifest_bytes"]),
            restriction_evidence_bytes=cast(bytes, typed["restriction_evidence_bytes"]),
            case_relevance_bytes=cast(bytes, typed["case_relevance_bytes"]),
            document_scanner=fixture_scanner,
            verified_recovery_capability=typed.get("verified_recovery_capability"),
        )

    monkeypatch.setattr(
        cli_module, "build_provenance_clearance_plan_v3", deterministic_plan_v3
    )


def _plan_command(
    paths: Mapping[str, Path],
    *,
    schema_version: str | None = None,
    execute: bool = True,
    resume: bool = False,
) -> list[str]:
    command = [
        "acquisition",
        "plan-disclosure-provenance",
        "--review-requests",
        str(paths["requests"]),
        "--download-manifest",
        str(paths["manifest"]),
        "--case-relevance",
        str(paths["relevance"]),
        "--restriction-evidence",
        str(paths["restrictions"]),
        "--document-root",
        str(paths["document_root"]),
        "--controlled-private-store-root",
        str(paths["private"]),
        "--output-root",
        str(paths["output"]),
    ]
    if execute:
        command.append("--execute")
    if schema_version is not None:
        command.extend(("--schema-version", schema_version))
    command.append("--resume" if resume else "--no-resume")
    return command


def _provider_free_command(
    paths: Mapping[str, Path],
    *,
    cohort_policy: Path,
    clearance_root: Path,
    resume: bool = False,
) -> list[str]:
    return [
        "acquisition",
        "finalize-provenance-quarantine",
        "--review-requests",
        str(paths["requests"]),
        "--download-manifest",
        str(paths["manifest"]),
        "--case-relevance",
        str(paths["relevance"]),
        "--restriction-evidence",
        str(paths["restrictions"]),
        "--document-root",
        str(paths["document_root"]),
        "--routing-plan",
        str(paths["output"] / "disclosure-provenance-plan.json"),
        "--exception-worksheet",
        str(paths["output"] / "disclosure-exception-worksheet.json"),
        "--cohort-policy",
        str(cohort_policy),
        "--quarantine-all-exceptions-without-review",
        "--output-root",
        str(clearance_root),
        "--execute",
        "--resume" if resume else "--no-resume",
    ]


def _no_model_review_command(
    paths: Mapping[str, Path],
    *,
    cohort_policy: Path,
    clearance_root: Path,
) -> list[str]:
    provider_free = _provider_free_command(
        paths,
        cohort_policy=cohort_policy,
        clearance_root=clearance_root,
    )
    provider_free.remove("--quarantine-all-exceptions-without-review")
    return [
        *provider_free,
        "--plan-run-card",
        str(paths["output"] / "run-cards/plan-disclosure-provenance.json"),
        "--require-no-model-review-eligible-exceptions",
    ]


def _public_marker_command(
    paths: Mapping[str, Path],
    *,
    cohort_policy: Path,
    public_marker_policy: Path,
    clearance_root: Path,
    resume: bool = False,
) -> list[str]:
    provider_free = _provider_free_command(
        paths,
        cohort_policy=cohort_policy,
        clearance_root=clearance_root,
        resume=resume,
    )
    provider_free.remove("--quarantine-all-exceptions-without-review")
    return [
        *provider_free,
        "--plan-run-card",
        str(paths["output"] / "run-cards/plan-disclosure-provenance.json"),
        "--public-marker-clearance-policy",
        str(public_marker_policy),
    ]


def test_finalizer_rejects_implicit_provider_free_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)
    command = _provider_free_command(
        paths,
        cohort_policy=cohort_policy,
        clearance_root=tmp_path / "implicit-provider-free",
    )
    command.remove("--quarantine-all-exceptions-without-review")

    assert main(command) == 2
    assert "finalization requires complete model authority" in capsys.readouterr().err


def test_provider_free_schema_documents_both_explicit_modes() -> None:
    schema = (
        Path(__file__).resolve().parents[1]
        / "docs/schemas/provenance-quarantine-clearance-v1.md"
    ).read_text(encoding="utf-8")

    assert "--quarantine-all-exceptions-without-review" in schema
    assert "`quarantine_all_exceptions_without_review`: `true`" in schema
    assert "--plan-run-card" in schema
    assert "--require-no-model-review-eligible-exceptions" in schema
    assert "`model_review_eligible_exception_count`: `0`" in schema
    assert "`no_model_review_eligible_exceptions_required`: `true`" in schema
    assert "`plan_run_card` source commitment" in schema
    assert (
        "Omitting model authority, both empty-set proof flags, and the explicit "
        "compatibility flag fails closed."
    ) in schema


def test_provider_free_failure_metadata_uses_finalizer_stage(tmp_path: Path) -> None:
    paths = _inputs(tmp_path)
    command = _provider_free_command(
        paths,
        cohort_policy=tmp_path / "cohort-policy.json",
        clearance_root=tmp_path / "provider-free-clearance",
    )
    parsed = cli_module.build_parser().parse_args(command)

    context = cli_module._disclosure_failure_context(  # pyright: ignore[reportPrivateUsage]
        parsed, parsed.acquisition_command
    )

    assert context is not None
    assert context[0] == "finalize-provenance-quarantine"


def test_provenance_planner_help_exposes_closed_schema_selector(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["acquisition", "plan-disclosure-provenance", "--help"])

    assert raised.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "--schema-version {v2,v3}" in normalized
    assert "v2 preserves the legacy John-review vocabulary" in normalized
    assert "remains the default" in normalized
    assert "v3 emits the reviewer-neutral" in normalized
    assert "review contract" in normalized


def test_provenance_planner_defaults_to_legacy_v2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)

    assert main(_plan_command(paths)) == 0

    plan = json.loads((paths["output"] / "disclosure-provenance-plan.json").read_text())
    worksheet = json.loads(
        (paths["output"] / "disclosure-exception-worksheet.json").read_text()
    )
    run_card = json.loads(
        (paths["output"] / "run-cards/plan-disclosure-provenance.json").read_text()
    )
    log_record = json.loads(
        (paths["output"] / "logs/plan-disclosure-provenance.jsonl")
        .read_text()
        .splitlines()[-1]
    )
    assert plan["schema_version"] == (
        "legalforecast.disclosure_provenance_routing_plan.v2"
    )
    assert worksheet["schema_version"] == (
        "legalforecast.disclosure_exception_worksheet.v2"
    )
    assert plan["john_review_count"] == 2
    assert "exception_review_count" not in plan
    assert run_card["john_review_count"] == 2
    assert "exception_review_count" not in run_card
    assert "routing_plan_schema_version" not in run_card
    assert "exception_worksheet_schema_version" not in run_card
    assert "routing_plan_schema_version" not in log_record
    assert "exception_worksheet_schema_version" not in log_record
    assert log_record["schema_version"] == "legalforecast.acquisition_stage_log.v1"

    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["output"] / "run-cards/plan-disclosure-provenance.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    snapshots = {path: (path.read_bytes(), path.stat().st_ino) for path in output_paths}
    assert main(_plan_command(paths, schema_version="v2", resume=True)) == 0
    assert snapshots == {
        path: (path.read_bytes(), path.stat().st_ino) for path in output_paths
    }


def test_provenance_planner_v3_emits_reviewer_neutral_artifacts_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    command = _plan_command(paths, schema_version="v3")

    assert main(command) == 0

    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["output"] / "run-cards/plan-disclosure-provenance.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    snapshots = {path: (path.read_bytes(), path.stat().st_ino) for path in output_paths}
    plan = json.loads(output_paths[0].read_text())
    worksheet = json.loads(output_paths[1].read_text())
    run_card = json.loads(output_paths[2].read_text())
    log_record = json.loads(
        (paths["output"] / "logs/plan-disclosure-provenance.jsonl")
        .read_text()
        .splitlines()[-1]
    )
    assert plan["schema_version"] == (
        "legalforecast.disclosure_provenance_routing_plan.v3"
    )
    assert worksheet["schema_version"] == (
        "legalforecast.disclosure_exception_worksheet.v3"
    )
    assert (plan["auto_clear_count"], plan["exception_review_count"]) == (1, 2)
    assert "john_review_count" not in plan
    assert [row["route"] for row in plan["documents"]] == [
        "auto_clear",
        "exception_review",
        "exception_review",
    ]
    assert worksheet["document_count"] == 2
    assert [row["route"] for row in worksheet["documents"]] == [
        "exception_review",
        "exception_review",
    ]
    inspection_rows = [
        json.loads(line)
        for line in output_paths[3].read_text(encoding="utf-8").splitlines()
    ]
    assert [row["source_document_id"] for row in inspection_rows] == [
        "marker",
        "sealed",
    ]
    assert run_card["exception_review_count"] == 2
    assert "john_review_count" not in run_card
    assert run_card["routing_plan_schema_version"] == plan["schema_version"]
    assert run_card["exception_worksheet_schema_version"] == worksheet["schema_version"]
    assert log_record["routing_plan_schema_version"] == plan["schema_version"]
    assert (
        log_record["exception_worksheet_schema_version"] == worksheet["schema_version"]
    )
    assert log_record["schema_version"] == (
        "legalforecast.disclosure_provenance_stage_log.v1"
    )

    assert main(_plan_command(paths, schema_version="v3", resume=True)) == 0
    assert snapshots == {
        path: (path.read_bytes(), path.stat().st_ino) for path in output_paths
    }


def test_recovered_public_marker_policy_flows_through_planner_and_finalizer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    operation_key = "00000000-0000-4000-8000-000000000000"
    fresh_sha = "2" * 64
    manifest = [json.loads(line) for line in paths["manifest"].read_text().splitlines()]
    restrictions = [
        json.loads(line) for line in paths["restrictions"].read_text().splitlines()
    ]
    requests = [json.loads(line) for line in paths["requests"].read_text().splitlines()]
    relevance = json.loads(paths["relevance"].read_text())
    recovered_index = 1
    recovered_document_id = "marker"
    manifest[recovered_index].update(
        {
            "free_or_purchased": "purchased",
            "source_provider": "courtlistener.recap-fetch+pacer",
            "purchase_operation_key": operation_key,
            "fresh_recap_detail_sha256": fresh_sha,
        }
    )
    manifest[recovered_index].pop("source_url")
    restrictions[recovered_index].update(
        {
            "schema_version": "legalforecast.post_recovery_restriction_evidence.v1",
            "source_provider": "courtlistener_recap_fetch_fresh_detail",
            "fresh_recap_detail_sha256": fresh_sha,
            "is_available": True,
            "is_sealed": None,
            "is_private": None,
            "redaction_or_seal_status": "public",
            "restriction_status": "public",
            "restriction_evidence": [
                "courtlistener_recap_fetch_fresh_detail_exact_match",
                "courtlistener_recap_fetch_is_available_true",
                "courtlistener_recap_fetch_is_sealed_unknown",
                "courtlistener_recap_fetch_no_positive_private_marker",
                "courtlistener_recap_fetch_public_download_url_allowlisted",
            ],
        }
    )
    requests[recovered_index].update(
        {
            "free_or_purchased": "purchased",
            "restriction_status": "public",
            "restriction_evidence": restrictions[recovered_index][
                "restriction_evidence"
            ],
        }
    )
    relevance["documents"][recovered_index]["source_url_or_reference"] = (
        f"recap-document:{recovered_document_id}"
    )
    _jsonl(paths["manifest"], manifest)
    _jsonl(paths["restrictions"], restrictions)
    _jsonl(paths["requests"], requests)
    _jsonl(paths["relevance"], [relevance])
    purchase_state_sha256 = "6" * 64
    operation = {
        "candidate_id": "case-a",
        "source_document_id": recovered_document_id,
        "operation_key": operation_key,
        "material_evidence": {"provider_detail_sha256": fresh_sha},
    }
    recovery_root = tmp_path / "recovery"
    recovery_run_card_path = (
        recovery_root / "run-cards/recover-recap-fetch-quarantine.json"
    )
    recovery_run_card_path.parent.mkdir(parents=True)
    recovery_run_card_path.write_text(
        json.dumps(
            {"output_commitments": {"purchase_state_sha256": purchase_state_sha256}},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    selection_path = tmp_path / "selection.jsonl"
    purchase_policy_path = tmp_path / "purchase-policy.json"
    ledger_path = tmp_path / "purchase-ledger.sqlite3"
    initialization_receipt_path = tmp_path / "purchase-ledger-receipt.json"
    cohort_policy = tmp_path / "cohort-policy.json"
    selection_path.write_text("", encoding="utf-8")
    purchase_policy_path.write_text("{}\n", encoding="utf-8")
    ledger_path.write_bytes(b"ledger fixture")
    initialization_receipt_path.write_text("{}\n", encoding="utf-8")
    cohort_policy.write_bytes(
        cli_module.canonical_json_bytes(
            {"policy": {"cycle_id": "cycle-public-marker-test"}}
        )
    )
    recovery = {
        "run_card_path": recovery_run_card_path,
        "manifest_path": paths["manifest"],
        "restriction_path": paths["restrictions"],
        "case_relevance_path": paths["relevance"],
        "review_requests_path": paths["requests"],
        "document_root": paths["document_root"],
        "manifest_records": [manifest[recovered_index]],
        "historical_purchase_operations": (operation,),
        "historical_purchase_state_sha256": purchase_state_sha256,
        "terminal_unavailable_path": None,
        "verified_artifact_bytes": {
            os.path.abspath(
                recovery_run_card_path
            ): recovery_run_card_path.read_bytes(),
            os.path.abspath(paths["manifest"]): paths["manifest"].read_bytes(),
            os.path.abspath(paths["restrictions"]): paths["restrictions"].read_bytes(),
        },
    }

    def verify_recovery(**kwargs: object) -> dict[str, object]:
        if kwargs.get("purchase_operations") != (operation,):
            raise cli_module.CommandError(
                "authenticated current purchase state does not reproduce"
            )
        return recovery

    monkeypatch.setattr(
        cli_module,
        "_verify_materializer_quarantine_recovery",
        verify_recovery,
    )
    monkeypatch.setattr(
        cli_module,
        "_replacement_consolidation_selection_keys",
        lambda _records: {("case-a", recovered_document_id)},
    )
    monkeypatch.setattr(
        cli_module,
        "verify_case_dev_purchase_policy",
        lambda _artifact: Namespace(canonical_ledger_path=ledger_path.resolve()),
    )
    monkeypatch.setattr(
        cli_module, "require_approved_case_dev_purchase_policy", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        cli_module,
        "verify_case_dev_purchase_policy_cohort_binding",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        cli_module,
        "read_case_dev_purchase_snapshot",
        lambda *_a, **_k: Namespace(
            committed_amount_usd="0.00",
            purchase_state_sha256=purchase_state_sha256,
            operations=(operation,),
        ),
    )
    verification_arguments = [
        "--recovery-run-card",
        str(recovery_run_card_path),
        "--selection",
        str(selection_path),
        "--purchase-policy",
        str(purchase_policy_path),
        "--purchase-ledger",
        str(ledger_path),
        "--purchase-ledger-initialization-receipt",
        str(initialization_receipt_path),
        "--controlled-private-root",
        str(paths["private"]),
        "--recovery-cohort-policy",
        str(cohort_policy),
    ]
    _install_document_scanner(monkeypatch)

    assert (
        main(
            [
                *_plan_command(paths, schema_version="v3"),
                *verification_arguments,
            ]
        )
        == 0
    )
    plan = json.loads((paths["output"] / "disclosure-provenance-plan.json").read_text())
    marker_plan = next(
        row
        for row in plan["documents"]
        if row["source_document_id"] == recovered_document_id
    )
    lineage = {
        "candidate_id": "case-a",
        "source_document_id": recovered_document_id,
        "recovery_run_card_sha256": hashlib.sha256(
            recovery_run_card_path.read_bytes()
        ).hexdigest(),
        "recovery_manifest_sha256": hashlib.sha256(
            paths["manifest"].read_bytes()
        ).hexdigest(),
        "recovery_restriction_evidence_sha256": hashlib.sha256(
            paths["restrictions"].read_bytes()
        ).hexdigest(),
        "purchase_state_sha256": purchase_state_sha256,
        "purchase_operation_sha256": hashlib.sha256(
            json.dumps(
                operation,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest(),
        "purchase_operation_key": operation_key,
        "fresh_recap_detail_sha256": fresh_sha,
    }
    assert marker_plan["route"] == "exception_review"
    assert marker_plan["route_reasons"] == ["automated_marker_present"]
    assert marker_plan["recovered_public_lineage"] == lineage

    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)
    monkeypatch.setattr(
        "legalforecast.ingestion.public_marker_clearance_policy.verify_cohort_policy",
        lambda _: "1" * 64,
    )
    public_marker_policy = tmp_path / "public-marker-policy.json"
    public_marker_policy.write_bytes(
        cli_module.canonical_json_bytes(
            generate_public_marker_clearance_policy(
                cycle_id="cycle-public-marker-test",
                cohort_policy_sha256="1" * 64,
            )
        )
    )
    clearance_root = tmp_path / "provider-free-clearance"
    assert (
        main(
            [
                *_public_marker_command(
                    paths,
                    cohort_policy=cohort_policy,
                    public_marker_policy=public_marker_policy,
                    clearance_root=clearance_root,
                    resume=True,
                ),
                *verification_arguments,
            ]
        )
        == 0
    )
    records = [
        json.loads(line)
        for line in (clearance_root / "disclosure-clearance.jsonl")
        .read_text()
        .splitlines()
    ]
    marker = next(
        row for row in records if row["source_document_id"] == recovered_document_id
    )
    assert marker["status"] == "cleared"
    assert marker["automated_markers"] == ["medical"]
    assert marker["clearance_basis"] == "provider_free_recovered_public"
    assert marker["controlled_store_provenance"] == (
        f"courtlistener-rest://recap-documents/{recovered_document_id}"
    )
    assert marker["recovered_public_lineage"] == lineage
    clearance_path = clearance_root / "disclosure-clearance.jsonl"
    clearance_run_card_path = (
        clearance_root / "run-cards/finalize-provenance-quarantine.json"
    )
    run_card = json.loads(clearance_run_card_path.read_text())
    assert run_card["schema_version"] == (
        "legalforecast.provenance_public_marker_clearance_run_card.v1"
    )
    assert run_card["resume"] is True
    assert run_card["disposition_policy"]["kind"] == (
        "v3_authenticated_recovered_public_markers_clear_else_quarantine"
    )
    assert run_card["disposition_policy"]["markers_are_diagnostic_only"] is True
    assert run_card["public_marker_clear_count"] == 1
    assert run_card["disposition_policy"]["public_marker_clear_count"] == 1
    assert "public_marker_clearance_policy" in run_card["source_commitments"]
    assert run_card["human_review_requested"] is False
    assert run_card["human_review_executed"] is False
    authority = run_card["recovered_public_authority"]
    assert authority["kind"] == "verified_recap_fetch_recovery"
    assert authority["document_count"] == 1
    assert authority["recovery_manifest_sha256"] == (
        "sha256:" + lineage["recovery_manifest_sha256"]
    )
    clearance_kwargs, clearance_inputs = (
        cli_module._authenticated_clearance_lineage_inputs(  # pyright: ignore[reportPrivateUsage]
            Namespace(
                clearance_run_card=clearance_run_card_path,
                restriction_evidence=paths["restrictions"],
                reviews=None,
                review_receipt=None,
            ),
            clearance_path=clearance_path,
        )
    )
    assert "_verified_recovery_capability" in clearance_kwargs
    assert clearance_inputs[0] == clearance_run_card_path
    assert paths["manifest"] in clearance_inputs
    assert paths["relevance"] in clearance_inputs
    assert public_marker_policy in clearance_inputs

    routing_plan_path = paths["output"] / "disclosure-provenance-plan.json"
    worksheet_path = paths["output"] / "disclosure-exception-worksheet.json"
    quarantine_path = clearance_root / "disclosure-quarantine.jsonl"
    replay_artifacts = (
        routing_plan_path,
        worksheet_path,
        public_marker_policy,
        clearance_path,
        quarantine_path,
        clearance_run_card_path,
    )
    original_artifacts = {path: path.read_bytes() for path in replay_artifacts}

    def write_tampered_replay_artifacts(field: str, value: str) -> None:
        tampered_plan = cast(
            dict[str, object], json.loads(original_artifacts[routing_plan_path])
        )
        documents = cast(list[dict[str, object]], tampered_plan["documents"])
        recovered_document = next(
            document
            for document in documents
            if document["source_document_id"] == recovered_document_id
        )
        recovered_lineage = cast(
            dict[str, object], recovered_document["recovered_public_lineage"]
        )
        recovered_lineage[field] = value
        tampered_plan["document_set_sha256"] = hashlib.sha256(
            cli_module.canonical_json_bytes(documents)
        ).hexdigest()
        plan_bytes = cli_module.canonical_json_bytes(tampered_plan)
        routing_plan_sha256 = hashlib.sha256(plan_bytes).hexdigest()
        tampered_worksheet = cli_module.exception_review_worksheet_v3(tampered_plan)
        worksheet_bytes = cli_module.canonical_json_bytes(tampered_worksheet)
        records = cli_module.build_provider_free_public_marker_records_v3(
            tampered_plan, routing_plan_sha256=routing_plan_sha256
        )
        clearance_bytes = b"".join(
            cli_module.canonical_json_bytes(record.to_record()) for record in records
        )
        quarantine_bytes = b"".join(
            cli_module.canonical_json_bytes(record.to_record())
            for record in records
            if record.status == "quarantined"
        )
        tampered_run_card = cast(
            dict[str, object],
            json.loads(original_artifacts[clearance_run_card_path]),
        )
        source_commitments = cast(
            dict[str, object], tampered_run_card["source_commitments"]
        )
        cast(dict[str, object], source_commitments["routing_plan"])["sha256"] = (
            "sha256:" + routing_plan_sha256
        )
        cast(dict[str, object], source_commitments["exception_worksheet"])["sha256"] = (
            "sha256:" + hashlib.sha256(worksheet_bytes).hexdigest()
        )
        output_commitments = cast(
            dict[str, object], tampered_run_card["output_commitments"]
        )
        cast(dict[str, object], output_commitments["disclosure_clearance"])[
            "sha256"
        ] = "sha256:" + hashlib.sha256(clearance_bytes).hexdigest()
        cast(dict[str, object], output_commitments["disclosure_quarantine"])[
            "sha256"
        ] = "sha256:" + hashlib.sha256(quarantine_bytes).hexdigest()
        disposition_policy = cast(
            dict[str, object], tampered_run_card["disposition_policy"]
        )
        disposition_policy["routing_plan_sha256"] = "sha256:" + routing_plan_sha256
        disposition_policy["exception_worksheet_sha256"] = (
            "sha256:" + hashlib.sha256(worksheet_bytes).hexdigest()
        )
        routing_plan_path.write_bytes(plan_bytes)
        worksheet_path.write_bytes(worksheet_bytes)
        clearance_path.write_bytes(clearance_bytes)
        quarantine_path.write_bytes(quarantine_bytes)
        clearance_run_card_path.write_bytes(
            cli_module.canonical_json_bytes(tampered_run_card)
        )

    for field, value in (
        ("purchase_operation_sha256", "7" * 64),
        ("purchase_operation_key", "11111111-1111-4111-8111-111111111111"),
    ):
        for artifact_path, payload in original_artifacts.items():
            artifact_path.write_bytes(payload)
        write_tampered_replay_artifacts(field, value)
        with pytest.raises(
            cli_module.CommandError, match="recovered-public routing lineage changed"
        ):
            cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
                clearance_path=clearance_path,
                clearance_run_card_path=clearance_run_card_path,
            )

    for artifact_path, payload in original_artifacts.items():
        artifact_path.write_bytes(payload)
    noncanonical_policy = (
        json.dumps(json.loads(original_artifacts[public_marker_policy]), indent=2)
        + "\n"
    ).encode()
    tampered_run_card = cast(
        dict[str, object],
        json.loads(original_artifacts[clearance_run_card_path]),
    )
    source_commitments = cast(
        dict[str, object], tampered_run_card["source_commitments"]
    )
    cast(dict[str, object], source_commitments["public_marker_clearance_policy"])[
        "sha256"
    ] = cli_module._bytes_sha256(noncanonical_policy)  # pyright: ignore[reportPrivateUsage]
    public_marker_policy.write_bytes(noncanonical_policy)
    clearance_run_card_path.write_bytes(
        cli_module.canonical_json_bytes(tampered_run_card)
    )
    with pytest.raises(cli_module.CommandError, match="canonical serialization"):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=clearance_run_card_path,
        )

    for artifact_path, payload in original_artifacts.items():
        artifact_path.write_bytes(payload)
    changed_operation = {**operation, "authenticated_journal_revision": 2}
    monkeypatch.setattr(
        cli_module,
        "read_case_dev_purchase_snapshot",
        lambda *_a, **_k: Namespace(
            committed_amount_usd="0.00",
            purchase_state_sha256=purchase_state_sha256,
            operations=(changed_operation,),
        ),
    )
    with pytest.raises(cli_module.CommandError, match="purchase state"):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=clearance_run_card_path,
        )


def test_legacy_quarantine_compatibility_rejects_reassembled_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_target_cohort_projection import _completed_two_case_projection

    _install_document_scanner(monkeypatch)
    completed = _completed_two_case_projection(
        tmp_path / "completed-projection",
        provenance_first=True,
        quarantine_all=True,
        monkeypatch=monkeypatch,
    )
    projection_root = completed["projection"]
    cli_module.verify_completed_target_cohort_projection_for_purchase_approval(
        projection_root
    )

    projection_run_card_path = projection_root / "run-cards/project-target-cohort.json"
    projection_run_card = json.loads(projection_run_card_path.read_bytes())
    clearance_run_card_path = Path(projection_run_card["input_paths"][4])
    clearance_run_card = json.loads(clearance_run_card_path.read_bytes())
    assert clearance_run_card["disposition_policy"]["kind"] == (
        "v3_auto_clear_else_quarantine"
    )
    quarantine_all = clearance_run_card.pop("quarantine_all_exceptions_without_review")
    assert quarantine_all is True
    clearance_run_card_path.write_bytes(
        cli_module.canonical_json_bytes(clearance_run_card)
    )
    clearance_digest = cli_module._bytes_sha256(  # pyright: ignore[reportPrivateUsage]
        clearance_run_card_path.read_bytes()
    )

    projection_summary_path = projection_root / "target-cohort-projection.json"
    projection_summary = json.loads(projection_summary_path.read_bytes())
    projection_summary["clearance_run_card_sha256"] = clearance_digest
    projection_summary["input_commitments"][str(clearance_run_card_path.resolve())] = (
        clearance_digest
    )
    projection_summary_path.write_bytes(
        cli_module._projection_json_bytes(projection_summary)  # pyright: ignore[reportPrivateUsage]
    )
    projection_run_card["output_commitments"][str(projection_summary_path)] = (
        cli_module._bytes_sha256(  # pyright: ignore[reportPrivateUsage]
            projection_summary_path.read_bytes()
        )
    )
    projection_run_card_path.write_bytes(
        cli_module._projection_json_bytes(  # pyright: ignore[reportPrivateUsage]
            projection_run_card
        )
    )

    with pytest.raises(cli_module.CommandError, match="invalid provenance clearance"):
        cli_module.verify_completed_target_cohort_projection_for_purchase_approval(
            projection_root
        )


def test_provider_free_v3_finalizer_quarantines_exceptions_and_replays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)
    clearance_root = tmp_path / "provider-free-clearance"
    command = _provider_free_command(
        paths,
        cohort_policy=cohort_policy,
        clearance_root=clearance_root,
    )

    dry_run_command = [argument for argument in command if argument != "--execute"]
    assert main(dry_run_command) == 0
    assert clearance_root.is_dir()
    assert not tuple(clearance_root.iterdir())

    assert main(command) == 0

    clearance_path = clearance_root / "disclosure-clearance.jsonl"
    quarantine_path = clearance_root / "disclosure-quarantine.jsonl"
    run_card_path = clearance_root / "run-cards/finalize-provenance-quarantine.json"
    rows = [json.loads(line) for line in clearance_path.read_text().splitlines()]
    by_id = {row["source_document_id"]: row for row in rows}
    assert by_id["auto"]["status"] == "cleared"
    assert by_id["marker"]["status"] == "quarantined"
    assert by_id["sealed"]["status"] == "quarantined"
    assert by_id["marker"]["clearance_basis"] == ("provider_free_exception_quarantine")
    assert by_id["sealed"]["clearance_basis"] == ("provider_free_exception_quarantine")
    assert by_id["sealed"]["reviewer_id"] is None
    assert by_id["sealed"]["reviewed_at"] is None
    assert [
        json.loads(line)["source_document_id"]
        for line in quarantine_path.read_text().splitlines()
    ] == ["marker", "sealed"]
    run_card = json.loads(run_card_path.read_text())
    assert run_card["schema_version"] == (
        "legalforecast.provenance_quarantine_clearance_run_card.v1"
    )
    assert "generated_at" not in run_card
    assert "clearance_authority" not in run_card
    assert run_card["human_review_requested"] is False
    assert run_card["human_review_executed"] is False
    assert run_card["provider_activity_requested"] is False
    assert run_card["provider_activity_executed"] is False
    assert run_card["disposition_policy"] == {
        "kind": "v3_auto_clear_else_quarantine",
        "routing_plan_schema_version": (
            "legalforecast.disclosure_provenance_routing_plan.v3"
        ),
        "exception_worksheet_schema_version": (
            "legalforecast.disclosure_exception_worksheet.v3"
        ),
        "clearance_schema_version": "legalforecast.disclosure_clearance.v1",
        "routing_plan_sha256": (
            "sha256:"
            + hashlib.sha256(
                (paths["output"] / "disclosure-provenance-plan.json").read_bytes()
            ).hexdigest()
        ),
        "exception_worksheet_sha256": (
            "sha256:"
            + hashlib.sha256(
                (paths["output"] / "disclosure-exception-worksheet.json").read_bytes()
            ).hexdigest()
        ),
        "cohort_policy_sha256": "sha256:" + "1" * 64,
        "auto_clear_count": 1,
        "exception_quarantine_count": 2,
        "human_or_model_override_permitted": False,
    }
    cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
        clearance_path=clearance_path,
        clearance_run_card_path=run_card_path,
        expected_download_manifest_path=paths["manifest"],
        expected_restriction_path=paths["restrictions"],
    )
    original_run_card_bytes = run_card_path.read_bytes()
    implicit_mode_run_card = dict(run_card)
    implicit_mode_run_card.pop("quarantine_all_exceptions_without_review")
    run_card_path.write_bytes(cli_module.canonical_json_bytes(implicit_mode_run_card))
    with pytest.raises(cli_module.CommandError, match="invalid provenance clearance"):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=run_card_path,
            expected_download_manifest_path=paths["manifest"],
            expected_restriction_path=paths["restrictions"],
        )
    run_card_path.write_bytes(original_run_card_bytes)

    run_card_path.write_text(json.dumps(run_card, sort_keys=True), encoding="utf-8")
    with pytest.raises(cli_module.CommandError, match="not canonical"):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=run_card_path,
            expected_download_manifest_path=paths["manifest"],
            expected_restriction_path=paths["restrictions"],
        )
    run_card_path.write_bytes(original_run_card_bytes)

    run_card_path.write_bytes(
        original_run_card_bytes.replace(
            b"{",
            b'{"schema_version":'
            b'"legalforecast.provenance_quarantine_clearance_run_card.v1",',
            1,
        )
    )
    with pytest.raises(cli_module.CommandError, match="not canonical"):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=run_card_path,
            expected_download_manifest_path=paths["manifest"],
            expected_restriction_path=paths["restrictions"],
        )
    run_card_path.write_bytes(original_run_card_bytes)

    boolean_count_run_card = dict(run_card)
    boolean_count_run_card["exception_quarantine_count"] = True
    run_card_path.write_bytes(cli_module.canonical_json_bytes(boolean_count_run_card))
    with pytest.raises(cli_module.CommandError, match="summary mismatch"):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=run_card_path,
            expected_download_manifest_path=paths["manifest"],
            expected_restriction_path=paths["restrictions"],
        )
    run_card_path.write_bytes(original_run_card_bytes)

    for nested_group, nested_field, ambiguous_value, expected_error in (
        (
            "source_commitments",
            "document_count",
            3.0,
            "document-root commitment",
        ),
        ("disposition_policy", "auto_clear_count", 1.0, "disposition policy"),
        (
            "disposition_policy",
            "exception_quarantine_count",
            True,
            "disposition policy",
        ),
    ):
        nested_ambiguous_run_card = json.loads(json.dumps(run_card))
        if nested_group == "source_commitments":
            nested_ambiguous_run_card[nested_group]["document_root"][nested_field] = (
                ambiguous_value
            )
        else:
            nested_ambiguous_run_card[nested_group][nested_field] = ambiguous_value
        run_card_path.write_bytes(
            cli_module.canonical_json_bytes(nested_ambiguous_run_card)
        )
        with pytest.raises(cli_module.CommandError, match=expected_error):
            cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
                clearance_path=clearance_path,
                clearance_run_card_path=run_card_path,
                expected_download_manifest_path=paths["manifest"],
                expected_restriction_path=paths["restrictions"],
            )
        run_card_path.write_bytes(original_run_card_bytes)

    changed_relevance = tmp_path / "changed-case-relevance.jsonl"
    changed_relevance.write_text(
        paths["relevance"]
        .read_text()
        .replace('"model_visible": true', '"model_visible": false')
    )
    with pytest.raises(cli_module.CommandError, match="case_relevance"):
        cli_module._validate_clearance_run_card_commitments(  # pyright: ignore[reportPrivateUsage]
            run_card,
            source_paths={
                "download_manifest": paths["manifest"],
                "case_relevance": changed_relevance,
                "restriction_evidence": paths["restrictions"],
                "disclosure_clearance": clearance_path,
            },
            source_sha256={
                "download_manifest": cli_module._bytes_sha256(  # pyright: ignore[reportPrivateUsage]
                    paths["manifest"].read_bytes()
                ),
                "case_relevance": cli_module._bytes_sha256(  # pyright: ignore[reportPrivateUsage]
                    changed_relevance.read_bytes()
                ),
                "restriction_evidence": cli_module._bytes_sha256(  # pyright: ignore[reportPrivateUsage]
                    paths["restrictions"].read_bytes()
                ),
                "disclosure_clearance": cli_module._bytes_sha256(  # pyright: ignore[reportPrivateUsage]
                    clearance_path.read_bytes()
                ),
            },
        )
    snapshots = {
        path: (path.read_bytes(), path.stat().st_ino)
        for path in (clearance_path, quarantine_path, run_card_path)
    }
    assert (
        main(
            _provider_free_command(
                paths,
                cohort_policy=cohort_policy,
                clearance_root=clearance_root,
                resume=True,
            )
        )
        == 0
    )
    assert snapshots == {
        path: (path.read_bytes(), path.stat().st_ino)
        for path in (clearance_path, quarantine_path, run_card_path)
    }

    tampered_run_card = dict(run_card)
    tampered_run_card["disposition_policy"] = {
        **cast(Mapping[str, object], run_card["disposition_policy"]),
        "human_or_model_override_permitted": True,
    }
    run_card_path.write_bytes(cli_module.canonical_json_bytes(tampered_run_card))
    with pytest.raises(cli_module.CommandError, match="disposition policy"):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=run_card_path,
            expected_download_manifest_path=paths["manifest"],
            expected_restriction_path=paths["restrictions"],
        )
    run_card_path.write_bytes(snapshots[run_card_path][0])


def test_no_model_review_finalizer_rejects_model_eligible_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)
    clearance_root = tmp_path / "no-model-clearance"

    assert (
        main(
            _no_model_review_command(
                paths,
                cohort_policy=cohort_policy,
                clearance_root=clearance_root,
            )
        )
        == 2
    )

    assert "model-review-eligible exceptions" in capsys.readouterr().err
    assert not (clearance_root / "disclosure-clearance.jsonl").exists()
    assert not (clearance_root / "disclosure-quarantine.jsonl").exists()


def test_no_model_review_finalizer_quarantines_positive_restriction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _inputs(tmp_path)
    for name in ("requests", "manifest", "restrictions"):
        rows = [json.loads(line) for line in paths[name].read_text().splitlines()]
        _jsonl(
            paths[name],
            [row for row in rows if row["source_document_id"] in {"auto", "sealed"}],
        )
    relevance = json.loads(paths["relevance"].read_text())
    relevance["documents"] = [
        row
        for row in relevance["documents"]
        if row["source_document_id"] in {"auto", "sealed"}
    ]
    _jsonl(paths["relevance"], [relevance])
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)
    monkeypatch.setattr(
        cli_module,
        "replay_authenticated_disclosure_model_review",
        lambda **_kwargs: pytest.fail("empty eligible set must not use model replay"),
    )
    clearance_root = tmp_path / "no-model-clearance"

    assert (
        main(
            _no_model_review_command(
                paths,
                cohort_policy=cohort_policy,
                clearance_root=clearance_root,
            )
        )
        == 0
    )

    rows = [
        json.loads(line)
        for line in (clearance_root / "disclosure-clearance.jsonl")
        .read_text()
        .splitlines()
    ]
    by_id = {row["source_document_id"]: row for row in rows}
    assert by_id["auto"]["status"] == "cleared"
    assert by_id["sealed"]["status"] == "quarantined"
    assert by_id["sealed"]["clearance_basis"] == ("provider_free_exception_quarantine")
    run_card = json.loads(
        (
            clearance_root / "run-cards" / "finalize-provenance-quarantine.json"
        ).read_text()
    )
    assert run_card["provider_activity_requested"] is False
    assert run_card["provider_activity_executed"] is False
    assert run_card["model_review_eligible_exception_count"] == 0
    assert run_card["no_model_review_eligible_exceptions_required"] is True
    assert "plan_run_card" in run_card["source_commitments"]
    cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
        clearance_path=clearance_root / "disclosure-clearance.jsonl",
        clearance_run_card_path=(
            clearance_root / "run-cards/finalize-provenance-quarantine.json"
        ),
        expected_download_manifest_path=paths["manifest"],
        expected_restriction_path=paths["restrictions"],
    )


def test_no_model_review_relative_plan_paths_replay_from_clearance_commitments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    absolute_paths = _inputs(tmp_path)
    for name in ("requests", "manifest", "restrictions"):
        rows = [
            json.loads(line) for line in absolute_paths[name].read_text().splitlines()
        ]
        _jsonl(
            absolute_paths[name],
            [row for row in rows if row["source_document_id"] == "auto"],
        )
    relevance = json.loads(absolute_paths["relevance"].read_text())
    relevance["documents"] = [
        row for row in relevance["documents"] if row["source_document_id"] == "auto"
    ]
    _jsonl(absolute_paths["relevance"], [relevance])
    _install_document_scanner(monkeypatch)
    monkeypatch.chdir(tmp_path)
    paths = {
        name: Path(os.path.relpath(path, tmp_path))
        for name, path in absolute_paths.items()
    }
    paths["private"] = absolute_paths["private"]
    assert main(_plan_command(paths, schema_version="v3")) == 0
    cohort_policy = Path("cohort-policy.json")
    cohort_policy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)
    clearance_root = Path("relative-no-model-clearance")

    assert (
        main(
            _no_model_review_command(
                paths,
                cohort_policy=cohort_policy,
                clearance_root=clearance_root,
            )
        )
        == 0
    )

    cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
        clearance_path=(clearance_root / "disclosure-clearance.jsonl").resolve(),
        clearance_run_card_path=(
            clearance_root / "run-cards/finalize-provenance-quarantine.json"
        ).resolve(),
        expected_download_manifest_path=absolute_paths["manifest"],
        expected_restriction_path=absolute_paths["restrictions"],
    )


@pytest.mark.parametrize(
    ("drift", "expected_error"),
    [
        ("output_commitment", "routing_plan commitment mismatch"),
        ("input_paths", "exact completed v3 plan run card"),
        ("noncanonical", "exact producer serialization"),
    ],
)
def test_no_model_review_finalizer_rejects_plan_run_card_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    drift: str,
    expected_error: str,
) -> None:
    paths = _inputs(tmp_path)
    for name in ("requests", "manifest", "restrictions"):
        rows = [json.loads(line) for line in paths[name].read_text().splitlines()]
        _jsonl(
            paths[name],
            [row for row in rows if row["source_document_id"] == "auto"],
        )
    relevance = json.loads(paths["relevance"].read_text())
    relevance["documents"] = [
        row for row in relevance["documents"] if row["source_document_id"] == "auto"
    ]
    _jsonl(paths["relevance"], [relevance])
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    plan_run_card_path = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    plan_run_card = json.loads(plan_run_card_path.read_text())
    if drift == "output_commitment":
        plan_run_card["output_commitments"]["routing_plan"]["sha256"] = (
            "sha256:" + "0" * 64
        )
        plan_run_card_path.write_text(
            json.dumps(
                plan_run_card,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    elif drift == "input_paths":
        plan_run_card["input_paths"] = [*plan_run_card["input_paths"], "/extra"]
        plan_run_card_path.write_text(
            json.dumps(
                plan_run_card,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        plan_run_card_path.write_text(
            json.dumps(plan_run_card, indent=4, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)

    assert (
        main(
            _no_model_review_command(
                paths,
                cohort_policy=cohort_policy,
                clearance_root=tmp_path / "no-model-clearance",
            )
        )
        == 2
    )
    assert expected_error in capsys.readouterr().err


def test_provider_free_v3_finalizer_replays_v1_scanner_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch, historical=True)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(cli_module, "verify_cohort_policy", lambda _: "1" * 64)
    clearance_root = tmp_path / "historical-provider-free-clearance"

    assert (
        main(
            _provider_free_command(
                paths,
                cohort_policy=cohort_policy,
                clearance_root=clearance_root,
            )
        )
        == 0
    )

    cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
        clearance_path=clearance_root / "disclosure-clearance.jsonl",
        clearance_run_card_path=(
            clearance_root / "run-cards/finalize-provenance-quarantine.json"
        ),
        expected_download_manifest_path=paths["manifest"],
        expected_restriction_path=paths["restrictions"],
    )


@pytest.mark.parametrize(
    ("link_kind", "expected_error"),
    (
        ("symlink", "not a regular file"),
        ("hardlink", "hard-link aliases"),
    ),
)
def test_provider_free_v3_finalizer_rejects_unsafe_routing_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    link_kind: str,
    expected_error: str,
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    plan_path = paths["output"] / "disclosure-provenance-plan.json"
    alias_path = tmp_path / "routing-plan-alias.json"
    if link_kind == "symlink":
        plan_path.rename(alias_path)
        plan_path.symlink_to(alias_path)
    else:
        alias_path.hardlink_to(plan_path)
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")

    assert (
        main(
            _provider_free_command(
                paths,
                cohort_policy=cohort_policy,
                clearance_root=tmp_path / "provider-free-clearance",
            )
        )
        == 2
    )

    assert expected_error in capsys.readouterr().err
    clearance_root = tmp_path / "provider-free-clearance"
    assert not (clearance_root / "disclosure-clearance.jsonl").exists()
    assert not (clearance_root / "disclosure-quarantine.jsonl").exists()


def test_disclosure_artifact_publish_rejects_parent_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_parent = tmp_path / "output"
    output_parent.mkdir()
    output_path = output_parent / "clearance.jsonl"
    detached_parent = tmp_path / "detached-output"
    attacker_payload = b"replacement directory sentinel"
    original_link = os.link

    def link_then_replace_parent(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        original_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        output_parent.rename(detached_parent)
        output_parent.mkdir()
        output_path.write_bytes(attacker_payload)

    monkeypatch.setattr(cli_module.os, "link", link_then_replace_parent)

    with pytest.raises(cli_module.CommandError, match="parent path binding changed"):
        cli_module._ensure_disclosure_review_artifact(  # pyright: ignore[reportPrivateUsage]
            output_path, b"intended payload", resume=False
        )

    assert output_path.read_bytes() == attacker_payload
    assert not (detached_parent / output_path.name).exists()
    assert not list(output_parent.glob(f".{output_path.name}.*.tmp"))
    assert not list(detached_parent.glob(f".{output_path.name}.*.tmp"))


def test_disclosure_artifact_read_rejects_same_parent_entry_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_parent = tmp_path / "output"
    output_parent.mkdir()
    output_path = output_parent / "clearance.jsonl"
    detached_path = output_parent / "detached-clearance.jsonl"
    output_path.write_bytes(b"intended payload")
    original_read = os.read
    rebound = False

    def read_after_rebinding(file_fd: int, byte_count: int) -> bytes:
        nonlocal rebound
        if not rebound:
            rebound = True
            output_path.rename(detached_path)
            output_path.write_bytes(b"replacement payload")
        return original_read(file_fd, byte_count)

    monkeypatch.setattr(cli_module.os, "read", read_after_rebinding)
    directory_fd = cli_module._open_disclosure_review_parent(  # pyright: ignore[reportPrivateUsage]
        output_parent, create=False
    )
    try:
        with pytest.raises(cli_module.CommandError, match="changed while being read"):
            cli_module._read_disclosure_review_artifact_at(  # pyright: ignore[reportPrivateUsage]
                directory_fd, output_path.name
            )
    finally:
        os.close(directory_fd)

    assert detached_path.read_bytes() == b"intended payload"
    assert output_path.read_bytes() == b"replacement payload"


def test_disclosure_artifact_read_rejects_rename_away_and_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_parent = tmp_path / "output"
    output_parent.mkdir()
    output_path = output_parent / "clearance.jsonl"
    detached_path = output_parent / "detached-clearance.jsonl"
    output_path.write_bytes(b"intended payload")
    baseline = output_path.stat()
    original_read = os.read
    rebound = False

    def read_after_rename_cycle(file_fd: int, byte_count: int) -> bytes:
        nonlocal rebound
        if not rebound:
            rebound = True
            output_path.rename(detached_path)
            detached_path.rename(output_path)
            # A rename cycle is not required to update the file inode's ctime
            # on every supported filesystem. Restore a permission-bit cycle so
            # ctime is the only remaining stable-identity field that differs.
            permissions = baseline.st_mode & 0o7777
            for _ in range(1_000):
                os.chmod(output_path, permissions ^ 0o100)
                os.chmod(output_path, permissions)
                if output_path.stat().st_ctime_ns != baseline.st_ctime_ns:
                    break
            else:
                pytest.fail("filesystem did not advance ctime for metadata cycle")
        return original_read(file_fd, byte_count)

    monkeypatch.setattr(cli_module.os, "read", read_after_rename_cycle)
    directory_fd = cli_module._open_disclosure_review_parent(  # pyright: ignore[reportPrivateUsage]
        output_parent, create=False
    )
    try:
        with pytest.raises(cli_module.CommandError, match="changed while being read"):
            cli_module._read_disclosure_review_artifact_at(  # pyright: ignore[reportPrivateUsage]
                directory_fd, output_path.name
            )
    finally:
        os.close(directory_fd)

    after = output_path.stat()
    assert (
        baseline.st_dev,
        baseline.st_ino,
        baseline.st_mode,
        baseline.st_size,
        baseline.st_mtime_ns,
        baseline.st_nlink,
    ) == (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_nlink,
    )
    assert baseline.st_ctime_ns != after.st_ctime_ns
    assert output_path.read_bytes() == b"intended payload"


def test_provenance_planner_resume_rejects_schema_version_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0

    run_card = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    run_card_snapshot = (run_card.read_bytes(), run_card.stat().st_ino)
    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    for path in output_paths:
        path.unlink()
    assert main(_plan_command(paths, schema_version="v3", resume=True)) == 2
    assert "requires a frozen routing plan" in capsys.readouterr().err
    assert all(not path.exists() for path in output_paths)
    assert run_card_snapshot == (run_card.read_bytes(), run_card.stat().st_ino)


def test_provenance_planner_execute_rejects_opposite_schema_dry_run_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v2", execute=False)) == 0
    run_card = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    run_card_snapshot = (run_card.read_bytes(), run_card.stat().st_ino)

    assert main(_plan_command(paths, schema_version="v3", resume=True)) == 2
    assert "requires a frozen routing plan" in capsys.readouterr().err
    assert not (paths["output"] / "disclosure-provenance-plan.json").exists()
    assert not (paths["output"] / "disclosure-exception-worksheet.json").exists()
    assert not (paths["private"] / "private-document-inspection-map.jsonl").exists()
    assert run_card_snapshot == (run_card.read_bytes(), run_card.stat().st_ino)


@pytest.mark.parametrize(
    ("execute", "remove_outputs"),
    ((False, False), (True, True)),
)
@pytest.mark.parametrize(
    ("source_schema", "target_schema"), (("v2", "v3"), ("v3", "v2"))
)
def test_provenance_planner_rejects_opposite_completed_schema_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    execute: bool,
    remove_outputs: bool,
    source_schema: str,
    target_schema: str,
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version=source_schema)) == 0
    run_card = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    log = paths["output"] / "logs/plan-disclosure-provenance.jsonl"
    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    metadata_snapshots = {
        path: (path.read_bytes(), path.stat().st_ino) for path in (run_card, log)
    }
    if remove_outputs:
        for path in output_paths:
            path.unlink()
    output_snapshots = {
        path: (path.read_bytes(), path.stat().st_ino)
        for path in output_paths
        if path.exists()
    }

    assert (
        main(
            _plan_command(
                paths,
                schema_version=target_schema,
                execute=execute,
                resume=False,
            )
        )
        == 2
    )
    assert "completed resume" in capsys.readouterr().err
    assert metadata_snapshots == {
        path: (path.read_bytes(), path.stat().st_ino) for path in (run_card, log)
    }
    assert output_snapshots == {
        path: (path.read_bytes(), path.stat().st_ino)
        for path in output_paths
        if path.exists()
    }
    if remove_outputs:
        assert all(not path.exists() for path in output_paths)


@pytest.mark.parametrize(
    ("source_schema", "target_schema"), (("v2", "v3"), ("v3", "v2"))
)
def test_provenance_planner_rejects_schema_change_from_completed_log_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source_schema: str,
    target_schema: str,
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version=source_schema)) == 0
    run_card = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    log = paths["output"] / "logs/plan-disclosure-provenance.jsonl"
    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    run_card.unlink()
    for path in output_paths:
        path.unlink()
    log_snapshot = (log.read_bytes(), log.stat().st_ino)

    assert main(_plan_command(paths, schema_version=target_schema, resume=True)) == 2
    assert "requires a frozen routing plan" in capsys.readouterr().err
    assert all(not path.exists() for path in output_paths)
    assert not run_card.exists()
    assert log_snapshot == (log.read_bytes(), log.stat().st_ino)


def test_provenance_planner_rejects_malformed_matching_v3_run_card_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    run_card = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    record = json.loads(run_card.read_text())
    record["record_count"] = 999
    run_card.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    for path in output_paths:
        path.unlink()
    run_card_snapshot = run_card.read_bytes()

    assert main(_plan_command(paths, schema_version="v3", resume=True)) == 2
    assert "requires a frozen routing plan" in capsys.readouterr().err
    assert all(not path.exists() for path in output_paths)
    assert run_card.read_bytes() == run_card_snapshot


def test_provenance_planner_rejects_malformed_matching_v3_log_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version="v3")) == 0
    run_card = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    log = paths["output"] / "logs/plan-disclosure-provenance.jsonl"
    record = json.loads(log.read_text())
    record["unexpected"] = True
    log.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    run_card.unlink()
    for path in output_paths:
        path.unlink()
    log_snapshot = log.read_bytes()

    assert main(_plan_command(paths, schema_version="v3", resume=True)) == 2
    assert "requires a frozen routing plan" in capsys.readouterr().err
    assert all(not path.exists() for path in output_paths)
    assert not run_card.exists()
    assert log.read_bytes() == log_snapshot


@pytest.mark.parametrize("schema_version", ("v2", "v3"))
def test_provenance_planner_log_only_resume_fails_without_scanner_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema_version: str,
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths, schema_version=schema_version)) == 0
    run_card = paths["output"] / "run-cards/plan-disclosure-provenance.json"
    log = paths["output"] / "logs/plan-disclosure-provenance.jsonl"
    output_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        paths["private"] / "private-document-inspection-map.jsonl",
    )
    log_snapshot = (log.read_bytes(), log.stat().st_ino)
    run_card.unlink()
    for path in output_paths:
        path.unlink()

    assert main(_plan_command(paths, schema_version=schema_version, resume=True)) == 2
    assert all(not path.exists() for path in output_paths)
    assert not run_card.exists()
    assert log_snapshot == (log.read_bytes(), log.stat().st_ino)


def test_provenance_planner_default_resume_allows_fresh_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    command = _plan_command(paths)
    command.remove("--no-resume")

    assert main(command) == 0
    assert (paths["output"] / "disclosure-provenance-plan.json").is_file()


@pytest.mark.parametrize("schema_version", ("v2", "v3"))
def test_provenance_planner_resumes_immutable_v1_scan_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema_version: str,
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch, historical=True)
    assert main(_plan_command(paths, schema_version=schema_version)) == 0
    plan_path = paths["output"] / "disclosure-provenance-plan.json"
    worksheet_path = paths["output"] / "disclosure-exception-worksheet.json"
    snapshots = {
        path: (path.read_bytes(), path.stat().st_ino)
        for path in (plan_path, worksheet_path)
    }

    assert main(_plan_command(paths, schema_version=schema_version, resume=True)) == 0
    assert snapshots == {
        path: (path.read_bytes(), path.stat().st_ino)
        for path in (plan_path, worksheet_path)
    }


def test_provenance_planner_and_interactive_exception_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0

    plan = json.loads((paths["output"] / "disclosure-provenance-plan.json").read_text())
    assert (plan["auto_clear_count"], plan["john_review_count"]) == (1, 2)
    marker_plan = next(
        row for row in plan["documents"] if row["source_document_id"] == "marker"
    )
    assert marker_plan["automated_markers"] == ["medical"]
    assert marker_plan["route"] == "john_exception_review"
    assert "automated_marker_present" in marker_plan["route_reasons"]
    run_card = json.loads(
        (paths["output"] / "run-cards/plan-disclosure-provenance.json").read_text()
    )
    document_tree_sha256 = run_card["source_commitments"]["document_root"][
        "tree_sha256"
    ]
    assert document_tree_sha256.startswith("sha256:")
    assert not document_tree_sha256.startswith("sha256:sha256:")
    worksheet = json.loads(
        (paths["output"] / "disclosure-exception-worksheet.json").read_text()
    )
    digests = {
        str(row["source_document_id"]): str(row["sha256"])
        for row in worksheet["documents"]
    }
    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    digest_iterator = iter(digests.values())
    decision_iterator = iter(("cleared", "quarantined"))

    def ordered_answer(prompt: str) -> str:
        if prompt.startswith("Type the full inspected"):
            return next(digest_iterator)
        if prompt.startswith("Decision"):
            return next(decision_iterator)
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr("builtins.input", ordered_answer)
    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--private-inspection-map",
                str(paths["private"] / "private-document-inspection-map.jsonl"),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(paths["private"]),
                "--output-root",
                str(paths["private"] / "metadata"),
                "--execute",
            ]
        )
        == 0
    )
    decisions = paths["private"] / "disclosure-review-decisions.jsonl"
    decision_rows = [json.loads(line) for line in decisions.read_text().splitlines()]
    assert [row["status"] for row in decision_rows] == ["cleared", "quarantined"]
    recorder_card = paths["private"] / (
        "metadata/run-cards/record-disclosure-review-decisions.json"
    )
    recorder = json.loads(recorder_card.read_text())
    assert recorder["authentication_claim"] == "interactive_hash_confirmation_only"
    assert recorder["routing_plan_sha256"] == worksheet["routing_plan_sha256"]

    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")

    def verify_fixture_policy(_policy: Mapping[str, object]) -> str:
        return "1" * 64

    monkeypatch.setattr(cli_module, "verify_cohort_policy", verify_fixture_policy)
    assert (
        main(
            [
                "acquisition",
                "clear-provenance-disclosures",
                "--review-requests",
                str(paths["requests"]),
                "--download-manifest",
                str(paths["manifest"]),
                "--case-relevance",
                str(paths["relevance"]),
                "--restriction-evidence",
                str(paths["restrictions"]),
                "--document-root",
                str(paths["document_root"]),
                "--routing-plan",
                str(paths["output"] / "disclosure-provenance-plan.json"),
                "--exception-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--exception-decisions",
                str(decisions),
                "--exception-review-run-card",
                str(recorder_card),
                "--cohort-policy",
                str(cohort_policy),
                "--output-root",
                str(tmp_path / "clearance"),
                "--execute",
            ]
        )
        == 0
    )
    clearance_rows = [
        json.loads(line)
        for line in (tmp_path / "clearance/disclosure-clearance.jsonl")
        .read_text()
        .splitlines()
    ]
    by_id = {row["source_document_id"]: row for row in clearance_rows}
    assert by_id["auto"]["clearance_basis"] == "affirmative_public_provenance"
    assert by_id["marker"]["clearance_basis"] == "john_exception_review"
    assert by_id["marker"]["status"] == "cleared"
    assert by_id["sealed"]["status"] == "quarantined"
    clearance_path = tmp_path / "clearance/disclosure-clearance.jsonl"
    clearance_card = tmp_path / "clearance/run-cards/clear-disclosures.json"
    cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
        clearance_path=clearance_path,
        clearance_run_card_path=clearance_card,
        expected_download_manifest_path=paths["manifest"],
        expected_restriction_path=paths["restrictions"],
    )

    tamper_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        decisions,
        recorder_card,
        cohort_policy,
        clearance_path,
    )
    for tamper_path in tamper_paths:
        original = tamper_path.read_bytes()
        tamper_path.write_bytes(original + b" ")
        with pytest.raises(cli_module.CommandError):
            cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
                clearance_path=clearance_path,
                clearance_run_card_path=clearance_card,
                expected_download_manifest_path=paths["manifest"],
                expected_restriction_path=paths["restrictions"],
            )
        tamper_path.write_bytes(original)

    marker_path = paths["document_root"] / "case-a/marker.pdf"
    marker_before = marker_path.read_bytes()
    marker_path.write_bytes(b"changed")
    with pytest.raises(cli_module.CommandError):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=clearance_card,
        )
    marker_path.write_bytes(marker_before)


def test_recorder_reports_document_context_for_invalid_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0
    worksheet_path = paths["output"] / "disclosure-exception-worksheet.json"
    worksheet = json.loads(worksheet_path.read_text())
    worksheet["documents"][0]["disclosure_pdf_scan"]["text_scanned_page_numbers"] = (
        "not-a-list"
    )
    worksheet_path.write_bytes(cli_module.canonical_json_bytes(worksheet))

    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(worksheet_path),
                "--private-inspection-map",
                str(paths["private"] / "private-document-inspection-map.jsonl"),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(paths["private"]),
                "--output-root",
                str(paths["private"] / "metadata"),
                "--execute",
            ]
        )
        == 2
    )
    assert (
        "provenance exception worksheet is invalid: "
        "text_scanned_page_numbers must be a list: ('case-a', 'marker')"
        in capsys.readouterr().err
    )


def test_recorder_rejects_broad_private_root_and_public_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0
    broad_inspection_map = tmp_path / "private-document-inspection-map.jsonl"
    broad_inspection_map.write_bytes(
        (paths["private"] / "private-document-inspection-map.jsonl").read_bytes()
    )

    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--private-inspection-map",
                str(broad_inspection_map),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(tmp_path),
                "--output-root",
                str(paths["output"] / "public-recorder-metadata"),
                "--decisions-output",
                str(paths["output"] / "public-decisions.jsonl"),
                "--checkpoint-dir",
                str(paths["output"] / "public-checkpoints"),
                "--execute",
            ]
        )
        == 2
    )
    assert "separate from the review worksheet tree" in capsys.readouterr().err
    assert not (paths["output"] / "public-decisions.jsonl").exists()


def test_provenance_finalizer_rejects_hand_authored_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0
    decisions = paths["private"] / "hand-authored.jsonl"
    _jsonl(decisions, [])
    fake_run_card = paths["private"] / "fake-run-card.json"
    fake_run_card.write_text("{}\n", encoding="utf-8")
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")

    def verify_fixture_policy(_policy: Mapping[str, object]) -> str:
        return "1" * 64

    monkeypatch.setattr(cli_module, "verify_cohort_policy", verify_fixture_policy)

    assert (
        main(
            [
                "acquisition",
                "clear-provenance-disclosures",
                "--review-requests",
                str(paths["requests"]),
                "--download-manifest",
                str(paths["manifest"]),
                "--case-relevance",
                str(paths["relevance"]),
                "--restriction-evidence",
                str(paths["restrictions"]),
                "--document-root",
                str(paths["document_root"]),
                "--routing-plan",
                str(paths["output"] / "disclosure-provenance-plan.json"),
                "--exception-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--exception-decisions",
                str(decisions),
                "--exception-review-run-card",
                str(fake_run_card),
                "--cohort-policy",
                str(cohort_policy),
                "--output-root",
                str(tmp_path / "clearance"),
                "--execute",
            ]
        )
        == 2
    )
    assert not (tmp_path / "clearance/disclosure-clearance.jsonl").exists()


def test_zero_exception_cohort_completes_without_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    for name in ("requests", "manifest", "restrictions"):
        rows = [json.loads(line) for line in paths[name].read_text().splitlines()]
        _jsonl(
            paths[name],
            [row for row in rows if row["source_document_id"] == "auto"],
        )
    relevance = json.loads(paths["relevance"].read_text())
    relevance["documents"] = [
        row for row in relevance["documents"] if row["source_document_id"] == "auto"
    ]
    _jsonl(paths["relevance"], [relevance])
    assert main(_plan_command(paths)) == 0
    worksheet = paths["output"] / "disclosure-exception-worksheet.json"
    assert json.loads(worksheet.read_text())["document_count"] == 0

    def reject_prompt(_prompt: str) -> str:
        pytest.fail("zero exceptions must not prompt")

    monkeypatch.setattr("builtins.input", reject_prompt)
    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(worksheet),
                "--private-inspection-map",
                str(paths["private"] / "private-document-inspection-map.jsonl"),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(paths["private"]),
                "--output-root",
                str(paths["private"] / "metadata"),
                "--execute",
            ]
        )
        == 0
    )
    assert (paths["private"] / "disclosure-review-decisions.jsonl").read_bytes() == b""


@pytest.mark.parametrize("private_kind", ["relative", "nested"])
def test_provenance_planner_rejects_private_root_inside_source_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    private_kind: str,
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    paths["private"] = (
        Path(f"relative-private-{tmp_path.name}")
        if private_kind == "relative"
        else tmp_path / "nested-private"
    )
    assert main(_plan_command(paths)) == 2
    assert not (paths["private"] / "private-document-inspection-map.jsonl").exists()


def test_provenance_planner_rejects_symlinked_source_and_document_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_document_scanner(monkeypatch)
    original_requests = paths["requests"]
    requests_target = tmp_path / "requests-target.jsonl"
    original_requests.replace(requests_target)
    original_requests.symlink_to(requests_target)
    assert main(_plan_command(paths)) == 2
    assert not (paths["output"] / "disclosure-provenance-plan.json").exists()

    original_requests.unlink()
    requests_target.replace(original_requests)
    real_documents = paths["document_root"]
    moved_documents = tmp_path / "real-documents"
    real_documents.replace(moved_documents)
    real_documents.symlink_to(moved_documents, target_is_directory=True)
    assert main(_plan_command(paths)) == 2
    assert not (paths["output"] / "disclosure-provenance-plan.json").exists()


def test_provenance_snapshot_reread_translates_unsafe_path_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unsafe_path(_root: Path, _relative: str) -> Path:
        raise DisclosureClearanceError("document became symlinked")

    monkeypatch.setattr(cli_module, "safe_disclosure_document_path", unsafe_path)

    with pytest.raises(
        cli_module.CommandError,
        match="disclosure document became unsafe during execution",
    ):
        cli_module._require_provenance_document_snapshot_unchanged(
            {"case/document.pdf": b"captured"}, document_root=tmp_path
        )
