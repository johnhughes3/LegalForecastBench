"""Tests for the verifier-owned Stage A target-document eligibility audit."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from legalforecast import cli
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    PostSelectionTerminalExclusionError,
    TerminalExclusionReason,
    _mint_stipulated_terminal_evidence_from_verified_eligibility_audit,
    require_verified_terminal_exclusion_evidence,
)
from legalforecast.ingestion.target_document_eligibility_audit import (
    AUDIT_SCHEMA_VERSION,
    TargetDocumentEligibilityAuditError,
    TargetDocumentEligibilityStatus,
    _mint_verified_target_document_eligibility_audit,
    _replay_verified_target_document_eligibility_audit,
    require_verified_target_document_eligibility_audit,
)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=ValueError,
        error_message="test serialization failed",
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _inputs(
    *, candidate_count: int = 2, stipulated_candidate: str = "C001"
) -> dict[str, Any]:
    selection: list[dict[str, Any]] = []
    parser_records: list[dict[str, Any]] = []
    markdown_by_document: dict[tuple[str, str], bytes] = {}
    for number in range(1, candidate_count + 1):
        candidate_id = f"C{number:03d}"
        source_document_id = f"D{number:03d}"
        markdown = (
            b"# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n"
            if candidate_id == stipulated_candidate
            else b"# Memorandum in Support of Motion to Dismiss\n"
        )
        selection.append(
            {
                "candidate_id": candidate_id,
                "documents": [
                    {
                        "source_document_id": source_document_id,
                        "document_role": "motion_to_dismiss_memorandum",
                    }
                ],
            }
        )
        parser_records.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": source_document_id,
                "extracted_text": {"text_sha256": _sha(markdown)},
            }
        )
        markdown_by_document[(candidate_id, source_document_id)] = markdown
    selection_bytes = b"".join(_bytes(record) for record in selection)
    parser_manifest_bytes = b"".join(_bytes(record) for record in parser_records)
    return {
        "selection_bytes": selection_bytes,
        "parser_manifest_bytes": parser_manifest_bytes,
        "parser_records": parser_records,
        "markdown_by_document": markdown_by_document,
    }


def test_live_v5_unitizer_replays_eligibility_before_provider_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def verified_parse_lineage(*args: object, **kwargs: object) -> object:
        calls.append("parse-lineage")
        return object()

    def blocked_eligibility(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append("eligibility")
        raise cli.CommandError("fixture eligibility rejection")

    def forbidden_provider_lineage(*args: object, **kwargs: object) -> object:
        calls.append("provider-lineage")
        raise AssertionError("provider lineage must remain unopened")

    monkeypatch.setattr(
        cli,
        "_verify_verified_stage_a_parse_lineage",
        verified_parse_lineage,
    )
    monkeypatch.setattr(
        cli,
        "_require_clean_v4_target_document_eligibility_audit",
        blocked_eligibility,
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_lineage",
        forbidden_provider_lineage,
    )
    output_root = tmp_path / "must-not-exist"
    args = Namespace(
        output_root=output_root,
        provider_journal=tmp_path / "provider.sqlite3",
        selection=tmp_path / "selection.jsonl",
        parser_manifest=tmp_path / "parser.jsonl",
        markdown_root=tmp_path / "markdown",
        model_registry=tmp_path / "registry.json",
        provider_cycle_caps=tmp_path / "caps.json",
        provider_attempt_namespace="claim-ontology-v5",
        target_eligibility_audit=tmp_path / "eligibility.jsonl",
        target_eligibility_audit_run_card=tmp_path / "eligibility-card.json",
        execute=True,
    )

    with pytest.raises(cli.CommandError, match="fixture eligibility rejection"):
        cli._cmd_acquisition_llm_unitize(args)

    assert calls == ["parse-lineage", "eligibility"]
    assert not output_root.exists()


@pytest.mark.parametrize(
    "unitization_namespace",
    (None, "claim-ontology-v2", "claim-ontology-v3", "claim-ontology-v4"),
)
def test_live_unitizer_rejects_non_v5_namespace_before_eligibility_or_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unitization_namespace: str | None,
) -> None:
    calls: list[str] = []

    def forbidden(name: str) -> object:
        calls.append(name)
        raise AssertionError(f"{name} must remain unopened")

    monkeypatch.setattr(
        cli,
        "_verify_verified_stage_a_parse_lineage",
        lambda *args, **kwargs: forbidden("eligibility"),
    )
    monkeypatch.setattr(
        cli,
        "_require_clean_v4_target_document_eligibility_audit",
        lambda *args, **kwargs: forbidden("eligibility-audit"),
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_lineage",
        lambda *args, **kwargs: forbidden("unitization-lineage"),
    )
    monkeypatch.setattr(
        cli,
        "_provider_spend_authorities",
        lambda *args, **kwargs: forbidden("provider-authority"),
    )
    output_root = tmp_path / "must-not-exist"
    args = Namespace(
        output_root=output_root,
        provider_journal=tmp_path / "provider.sqlite3",
        selection=tmp_path / "selection.jsonl",
        parser_manifest=tmp_path / "parser.jsonl",
        markdown_root=tmp_path / "markdown",
        model_registry=tmp_path / "registry.json",
        provider_cycle_caps=tmp_path / "caps.json",
        provider_attempt_namespace=unitization_namespace,
        target_eligibility_audit=tmp_path / "eligibility.jsonl",
        target_eligibility_audit_run_card=tmp_path / "eligibility-card.json",
        execute=True,
    )

    with pytest.raises(
        cli.CommandError,
        match="requires --provider-attempt-namespace claim-ontology-v5",
    ):
        cli._cmd_acquisition_llm_unitize(args)

    assert calls == []
    assert not output_root.exists()


def test_live_v5_unitizer_rejects_lineage_changed_after_clean_eligibility_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common = {
        "selection_records": ({"candidate_id": "cand-1"},),
        "parser_records": ({"source_document_id": "motion"},),
        "document_root": tmp_path / "documents",
        "markdown_root": tmp_path / "markdown",
        "cohort_cycle_id": "cycle-1",
        "input_commitments": {"selection": {"sha256": "sha256:" + "a" * 64}},
        "markdown_tree": {"cand-1/motion.md": "sha256:" + "b" * 64},
        "document_tree": {"cand-1/motion.pdf": b"pdf"},
        "file_snapshots": {tmp_path / "selection.jsonl": b"selection"},
    }
    eligibility_lineage = SimpleNamespace(
        **common,
        markdown_bytes={"cand-1/motion.md": b"clean motion"},
    )
    unitization_lineage = SimpleNamespace(
        **common,
        markdown_bytes={"cand-1/motion.md": b"mutated motion"},
    )
    monkeypatch.setattr(
        cli,
        "_verify_verified_stage_a_parse_lineage",
        lambda *args, **kwargs: eligibility_lineage,
    )
    monkeypatch.setattr(
        cli,
        "_require_clean_v4_target_document_eligibility_audit",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        cli,
        "_require_stage_a_parse_lineage_unchanged",
        lambda lineage: None,
    )
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_lineage",
        lambda *args, **kwargs: unitization_lineage,
    )
    monkeypatch.setattr(
        cli,
        "_provider_spend_authorities",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("provider authority must remain unopened")
        ),
    )
    output_root = tmp_path / "must-not-exist"
    args = Namespace(
        output_root=output_root,
        provider_journal=tmp_path / "provider.sqlite3",
        selection=tmp_path / "selection.jsonl",
        parser_manifest=tmp_path / "parser.jsonl",
        markdown_root=tmp_path / "markdown",
        model_registry=tmp_path / "registry.json",
        provider_cycle_caps=tmp_path / "caps.json",
        provider_attempt_namespace="claim-ontology-v5",
        target_eligibility_audit=tmp_path / "eligibility.jsonl",
        target_eligibility_audit_run_card=tmp_path / "eligibility-card.json",
        execute=True,
    )

    with pytest.raises(cli.CommandError, match="eligibility lineage differs"):
        cli._cmd_acquisition_llm_unitize(args)

    assert not output_root.exists()


def test_audit_is_canonical_deterministic_and_replayable() -> None:
    inputs = _inputs()

    audit = _mint_verified_target_document_eligibility_audit(**inputs)
    replay = _replay_verified_target_document_eligibility_audit(
        persisted_audit_bytes=audit.records_bytes,
        **inputs,
    )

    require_verified_target_document_eligibility_audit(audit)
    assert replay.records_bytes == audit.records_bytes
    assert audit.records == (
        {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "candidate_id": "C001",
            "source_document_id": "D001",
            "document_role": "motion_to_dismiss_memorandum",
            "status": TargetDocumentEligibilityStatus.STIPULATED_INELIGIBLE.value,
            "markdown_sha256": _sha(
                b"# [PROPOSED] STIPULATION FOR AND ORDER OF DISMISSAL\n"
            ),
        },
        {
            "schema_version": AUDIT_SCHEMA_VERSION,
            "candidate_id": "C002",
            "source_document_id": "D002",
            "document_role": "motion_to_dismiss_memorandum",
            "status": TargetDocumentEligibilityStatus.ELIGIBLE.value,
            "markdown_sha256": _sha(b"# Memorandum in Support of Motion to Dismiss\n"),
        },
    )
    assert audit.input_commitments["selection"] == _sha(inputs["selection_bytes"])
    assert audit.input_commitments["parser_manifest"] == _sha(
        inputs["parser_manifest_bytes"]
    )


def test_audit_replay_rejects_any_persisted_byte_drift() -> None:
    inputs = _inputs()
    audit = _mint_verified_target_document_eligibility_audit(**inputs)

    with pytest.raises(
        TargetDocumentEligibilityAuditError,
        match="differs from authenticated replay",
    ):
        _replay_verified_target_document_eligibility_audit(
            persisted_audit_bytes=audit.records_bytes + b"\n", **inputs
        )


def test_audit_rejects_markdown_not_committed_by_parser_record() -> None:
    inputs = _inputs()
    inputs["markdown_by_document"][("C001", "D001")] = b"invented body\n"

    with pytest.raises(TargetDocumentEligibilityAuditError, match="hash differs"):
        _mint_verified_target_document_eligibility_audit(**inputs)


def test_audit_rejects_missing_target_parser_output() -> None:
    inputs = _inputs()
    inputs["parser_records"] = inputs["parser_records"][1:]
    inputs["parser_manifest_bytes"] = b"".join(
        _bytes(record) for record in inputs["parser_records"]
    )
    inputs["markdown_by_document"].pop(("C001", "D001"))

    with pytest.raises(
        TargetDocumentEligibilityAuditError,
        match="lacks authenticated parser output",
    ):
        _mint_verified_target_document_eligibility_audit(**inputs)


def test_opaque_audit_mints_stipulated_terminal_evidence() -> None:
    inputs = _inputs(candidate_count=100)
    audit = _mint_verified_target_document_eligibility_audit(**inputs)

    evidence = _mint_stipulated_terminal_evidence_from_verified_eligibility_audit(
        audit=audit,
        candidate_id="C001",
        source_document_id="D001",
    )

    require_verified_terminal_exclusion_evidence(evidence)
    assert evidence.reason is TerminalExclusionReason.STIPULATED_INELIGIBLE
    assert evidence.evidence_kind == "authenticated_stage_a_target_eligibility_replay"
    assert evidence.evidence_commitments["selection"] == audit.selection_sha256
    assert (
        evidence.evidence_commitments["target_eligibility_audit"]
        == audit.commitment_sha256
    )


def test_opaque_audit_cannot_mint_an_eligible_target() -> None:
    audit = _mint_verified_target_document_eligibility_audit(**_inputs())

    with pytest.raises(
        PostSelectionTerminalExclusionError,
        match="does not prove stipulated",
    ):
        _mint_stipulated_terminal_evidence_from_verified_eligibility_audit(
            audit=audit,
            candidate_id="C002",
            source_document_id="D002",
        )


def test_altered_opaque_audit_cannot_mint_terminal_evidence() -> None:
    audit = _mint_verified_target_document_eligibility_audit(**_inputs())
    object.__setattr__(audit, "records_bytes", audit.records_bytes + b"\n")

    with pytest.raises(
        PostSelectionTerminalExclusionError,
        match="was not produced by verified replay",
    ):
        _mint_stipulated_terminal_evidence_from_verified_eligibility_audit(
            audit=audit,
            candidate_id="C001",
            source_document_id="D001",
        )
