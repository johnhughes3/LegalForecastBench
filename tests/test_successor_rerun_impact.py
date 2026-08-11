"""Focused tests for the provider-free successor rerun impact planner."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.cli as cli
import pytest
from legalforecast.cli import (
    _validate_successor_rerun_commands,  # pyright: ignore[reportPrivateUsage]
    main,
)
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.ingestion.successor_rerun_impact import (
    ADVISORY_WARNING,
    SuccessorRerunImpactError,
    failed_successor_rerun_impact,
    plan_successor_rerun_impact,
)
from legalforecast.ingestion.successor_rerun_proposal import (
    PROPOSAL_SCHEMA_VERSION,
    DocumentInput,
    ParserReuseEvidence,
    ProviderReuseEvidence,
    RerunInputs,
    SuccessorProposal,
    SuccessorRerunProposalError,
    bind_verified_successor_proposal,
    load_successor_proposal,
)
from legalforecast.labeling.provider_journal import ProviderCallIdentity


def test_one_document_replacement_reuses_only_fully_authenticated_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current, proposal = _fixture(tmp_path, replace_document=True)
    before = _tree_bytes(tmp_path)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("planner constructed a writer or provider")

    monkeypatch.setattr(
        "legalforecast.labeling.provider_journal.ProviderAttemptJournal.__init__",
        forbidden,
    )
    monkeypatch.setattr("legalforecast.cli._write_jsonl", forbidden)
    monkeypatch.setattr("legalforecast.cli._write_immutable_bytes", forbidden)

    first = plan_successor_rerun_impact(current=current, proposed=proposal)
    second = plan_successor_rerun_impact(current=current, proposed=proposal)

    assert first.json_text() == second.json_text()
    assert first.text() == second.text()
    assert first.record["first_invalidated_stage"] == "parse-documents"
    assert first.record["affected_cases"] == ["case-b"]
    assert first.record["affected_candidates"] == ["candidate-b"]
    assert first.record["affected_documents"] == ["candidate-b/document-b"]
    assert first.record["reusable_documents"] == ["candidate-a/document-a"]
    reusable_calls = cast(
        list[dict[str, object]], first.record["reusable_logical_calls"]
    )
    assert [item["candidate_id"] for item in reusable_calls] == ["candidate-a"]
    assert first.record["provider_logical_call_gaps"] == [
        {"candidate_id": "candidate-b", "reason": "candidate_inputs_changed"}
    ]
    assert first.record["advisory"] is True
    assert first.text().startswith(ADVISORY_WARNING)
    assert _tree_bytes(tmp_path) == before


def test_commands_are_derived_complete_and_never_caller_supplied(
    tmp_path: Path,
) -> None:
    current, proposal = _fixture(tmp_path, replace_document=True)
    report = plan_successor_rerun_impact(current=current, proposed=proposal)

    _validate_successor_rerun_commands(report.record)
    commands = cast(list[dict[str, object]], report.record["next_commands"])
    assert [command["stage"] for command in commands] == [
        "plan-parse-documents",
        "parse-documents",
        "audit-stage-a-target-eligibility",
        "llm-unitize",
    ]
    for command in commands:
        argv = cast(list[str], command["argv"])
        assert argv[4] == command["stage"]
        assert command["execution_authority"] is False
        assert command["requires_separate_authorization"] is True
        if command["stage"] == "llm-unitize":
            assert "--execute" not in argv
            assert command["advisory_execution"] == "dry_run_only"
            assert "--provider-attempt-namespace" in argv
            assert "--target-eligibility-audit" in argv
        else:
            assert "--execute" in argv
        assert not {"freeze", "dispatch", "publish", "finalize-corpus"} & set(argv)
    assert "--reuse-live-mistral-run-card" in cast(list[str], commands[1]["argv"])
    assert "--reuse-markdown-root" in cast(list[str], commands[1]["argv"])

    proposal_path = tmp_path / "proposal.json"
    raw = json.loads(proposal_path.read_text(encoding="utf-8"))
    raw["next_commands"] = [{"stage": "freeze", "argv": ["--execute"]}]
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(raw))
    with pytest.raises(
        SuccessorRerunProposalError, match="fields, schema, or advisory marker"
    ):
        load_successor_proposal(proposal_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("orphan", "coverage has orphan"),
        ("missing", "coverage has missing"),
        ("role", "document role differs"),
        ("candidate", "document candidate differs"),
        ("visibility", "model visibility is invalid"),
    ],
)
def test_proposal_semantic_or_coverage_drift_is_typed_and_deterministic(
    tmp_path: Path, mutation: str, message: str
) -> None:
    envelope, selections, downloads = _proposal_fixture(
        tmp_path, replace_document=False
    )
    if mutation == "orphan":
        extra = dict(downloads[0])
        extra["candidate_id"] = "orphan"
        downloads.append(extra)
    elif mutation == "missing":
        downloads.pop()
    elif mutation == "role":
        downloads[0]["document_role"] = "decision"
    elif mutation == "candidate":
        selections[0]["documents"][0]["candidate_id"] = "wrong"
    else:
        selections[0]["documents"][0]["model_visible"] = "yes"
    _rewrite_verified_bytes(envelope, selections, downloads)

    diagnostics: list[str] = []
    for _ in range(2):
        with pytest.raises(SuccessorRerunProposalError) as raised:
            bind_verified_successor_proposal(
                envelope,
                cycle_id="cycle-1",
                selection_records=selections,
                download_records=downloads,
                model_provider="openai",
                provider_account="primary",
                model_registry_sha256="a" * 64,
                policy_sha256="b" * 64,
            )
        diagnostics.append(str(raised.value))
    assert diagnostics == [diagnostics[0], diagnostics[0]]
    assert message in diagnostics[0]
    assert "KeyError" not in diagnostics[0]


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("provider", "provider evidence identity differs"),
        ("account", "provider evidence identity differs"),
        ("prompt_text", "provider evidence identity differs"),
        ("model_key", "provider evidence identity differs"),
        ("model_registry_sha256", "provider evidence identity differs"),
    ],
)
def test_provider_identity_drift_is_never_reusable(
    tmp_path: Path, field: str, message: str
) -> None:
    current, proposal = _fixture(tmp_path, replace_document=False)
    evidence = current.provider_reuse_by_candidate["candidate-a"]
    replacement: object = "different"
    if field == "model_registry_sha256":
        replacement = "f" * 64
    mutated = replace(evidence, **{field: replacement})
    current = replace(
        current,
        provider_reuse_by_candidate={
            **current.provider_reuse_by_candidate,
            "candidate-a": mutated,
        },
    )
    with pytest.raises(SuccessorRerunImpactError, match=message):
        plan_successor_rerun_impact(current=current, proposed=proposal)


def test_full_parser_source_identity_drift_becomes_gap(tmp_path: Path) -> None:
    current, proposal = _fixture(tmp_path, replace_document=False)
    evidence = current.parser_reuse_by_document[("candidate-a", "document-a")]
    drifted = replace(
        evidence,
        source_key=("candidate-a", "document-a", "f" * 64, len(b"source-a")),
    )
    current = replace(
        current,
        parser_reuse_by_document={
            **current.parser_reuse_by_document,
            ("candidate-a", "document-a"): drifted,
        },
    )
    report = plan_successor_rerun_impact(current=current, proposed=proposal)
    assert report.record["affected_documents"] == ["candidate-a/document-a"]
    assert report.record["reusable_documents"] == ["candidate-b/document-b"]


def test_invalid_prerequisite_blocks_every_descendant_deterministically() -> None:
    report = failed_successor_rerun_impact("active lineage is ambiguous")
    stages = cast(list[dict[str, object]], report.record["stages"])
    assert [node["status"] for node in stages] == [
        "FAILED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
    ]
    assert report.json_text() == report.json_text()


def test_cli_missing_or_ambiguous_lineage_is_stable_json_and_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "acquisition",
        "explain-successor-rerun",
        "--index",
        str(tmp_path / "missing-index.json"),
        "--cycle-id",
        "cycle-1",
        "--llm-unitize-run-card",
        str(tmp_path / "missing-card.json"),
        "--proposed-inputs",
        str(tmp_path / "missing-proposal.json"),
        "--format",
        "json",
    ]
    assert main(argv) == 1
    first = capsys.readouterr().out
    assert main(argv) == 1
    second = capsys.readouterr().out
    assert first == second
    failed = cast(dict[str, Any], json.loads(first))
    stages = cast(list[dict[str, object]], failed["stages"])
    assert [node["status"] for node in stages] == [
        "FAILED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
    ]


def test_successful_cli_is_byte_identical_and_journal_mutation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    before = _tree_bytes(tmp_path)
    assert main(argv) == 0
    first = capsys.readouterr().out
    assert main(argv) == 0
    second = capsys.readouterr().out
    assert first == second
    assert json.loads(first)["advisory"] is True

    states: Iterator[tuple[bytes, dict[str, bytes]]] = iter(
        [(b"before", dict[str, bytes]()), (b"after", dict[str, bytes]())]
    )

    def changing_journal_state(_path: Path) -> tuple[bytes, dict[str, bytes]]:
        return next(states)

    monkeypatch.setattr(
        cli,
        "_provider_journal_durable_bytes",
        changing_journal_state,
    )
    assert main(argv) == 1
    failed = json.loads(capsys.readouterr().out)
    assert failed["stages"][0]["status"] == "FAILED"
    assert (
        "provider journal changed" in failed["stages"][0]["diagnostics"][0]["message"]
    )
    assert _tree_bytes(tmp_path) == before


def test_cli_failed_current_card_and_ambiguous_lineage_are_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    run_card = Path(argv[argv.index("--llm-unitize-run-card") + 1])

    def failed_card(*_args: object, **_kwargs: object) -> object:
        raise cli.CommandError("failed current llm-unitize card")

    monkeypatch.setattr(cli, "_verify_stage_a_unitization_run_card", failed_card)
    assert main(argv) == 1
    failed = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    failed_stages = cast(list[dict[str, Any]], failed["stages"])
    assert "failed current" in failed_stages[0]["diagnostics"][0]["message"]

    def ambiguous(*_args: object) -> tuple[dict[str, str], ...]:
        head = {"run_card_path": str(run_card), "stage": "llm-unitize"}
        return head, dict(head)

    monkeypatch.setattr(cli, "_active_head_chain", ambiguous)
    assert main(argv) == 1
    ambiguous_report = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    ambiguous_stages = cast(list[dict[str, Any]], ambiguous_report["stages"])
    assert "not unique" in ambiguous_stages[0]["diagnostics"][0]["message"]


def _install_successful_cli_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list[str]:
    current, proposal = _fixture(tmp_path, replace_document=True)
    run_card = tmp_path / "llm-card.json"
    raw = tmp_path / "units.jsonl"
    audit = tmp_path / "audit.jsonl"
    queue = tmp_path / "queue.jsonl"
    journal = tmp_path / "provider.sqlite3"
    current_parser_card = current.parser_run_card_path
    current_parser_card.write_bytes(b'{"parser":"card"}')
    current.markdown_root.mkdir()
    for path in (raw, audit, queue):
        path.write_bytes(b"{}\n")
    journal.write_bytes(b"journal")
    run_card.write_bytes(
        json.dumps(
            {
                "output_commitments": {
                    "prediction_units": {"path": str(raw)},
                    "llm_unitization_audit": {"path": str(audit)},
                    "unitization_review_queue": {"path": str(queue)},
                },
                "lineage_roots": {"provider_journal": str(journal)},
                "model_execution": {"provider_attempt_namespace": "claim-ontology-v4"},
            },
            sort_keys=True,
        ).encode()
    )
    current_root = tmp_path / "current-documents"
    current_root.mkdir()
    current_downloads: list[dict[str, Any]] = []
    for document in current.documents:
        relative = Path(document.candidate_id) / f"{document.source_document_id}.pdf"
        path = current_root / relative
        path.parent.mkdir()
        payload = f"source-{document.candidate_id[-1]}".encode()
        path.write_bytes(payload)
        current_downloads.append(
            {
                "candidate_id": document.candidate_id,
                "source_document_id": document.source_document_id,
                "document_role": document.document_role,
                "local_path": relative.as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_count": len(payload),
            }
        )
    registry_entry = SimpleNamespace(
        registry_key=current.model_key,
        provider=current.model_provider,
    )

    def provider_account(_provider: str) -> str:
        return current.provider_account

    caps = SimpleNamespace(
        cycle_id=current.cycle_id,
        account=provider_account,
    )
    lineage = SimpleNamespace(
        selection_records=current.selection_records,
        download_records=tuple(current_downloads),
        registry_entry=registry_entry,
        registry_sha256=current.model_registry_sha256,
        provider_caps=caps,
        provider_caps_sha256=current.policy_sha256,
        provider_journal_path=journal,
        document_root=current_root,
        markdown_root=current.markdown_root,
        cohort_cycle_id=current.cycle_id,
        input_commitments={"parser_run_card": {"path": str(current_parser_card)}},
        verified_provider_attempt_rows=(),
    )
    verified_proposal = SimpleNamespace(
        artifact_bytes={
            str(proposal.selection_path.absolute()): (
                proposal.selection_path.read_bytes()
            )
        },
        selection_records=proposal.require_inputs().selection_records,
        manifest_records=tuple(
            json.loads(line)
            for line in proposal.download_manifest_path.read_text().splitlines()
        ),
        verified_successor_selection_card=None,
    )
    parser_authentication = SimpleNamespace(artifacts_by_key={}, source={})
    snapshot = SimpleNamespace(close=lambda: None)

    def locate(**_kwargs: object) -> dict[str, bool]:
        return {"ok": True}

    def active_chain(*_args: object) -> tuple[dict[str, str], ...]:
        return ({"run_card_path": str(run_card), "stage": "llm-unitize"},)

    def stable_journal_state(_path: Path) -> tuple[bytes, dict[str, bytes]]:
        return b"stable", {}

    def open_snapshot(_path: Path) -> object:
        return snapshot

    def return_lineage(*_args: object, **_kwargs: object) -> object:
        return lineage

    def return_parser_authentication(**_kwargs: object) -> object:
        return parser_authentication

    def return_proposed_materialization(**_kwargs: object) -> object:
        return verified_proposal

    def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    def registry_entries(*_args: object) -> tuple[tuple[object, ...], str]:
        return (registry_entry,), current.model_registry_sha256

    def return_caps(_path: Path) -> object:
        return caps

    def cycle_id(*_args: object, **_kwargs: object) -> str:
        return "cycle-1"

    def parser_evidence(
        _artifacts: Mapping[object, object],
    ) -> Mapping[tuple[str, str], ParserReuseEvidence]:
        return current.parser_reuse_by_document

    def provider_evidence(
        _rows: object,
    ) -> Mapping[str, ProviderReuseEvidence]:
        return current.provider_reuse_by_candidate

    def forbidden_writer(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("advisory CLI constructed a provider or artifact writer")

    monkeypatch.setattr(cli, "locate_cycle_lineage", locate)
    monkeypatch.setattr(
        cli,
        "_active_head_chain",
        active_chain,
    )
    monkeypatch.setattr(cli, "_provider_journal_durable_bytes", stable_journal_state)
    monkeypatch.setattr(cli, "open_provider_journal_snapshot", open_snapshot)
    monkeypatch.setattr(cli, "_verify_stage_a_unitization_run_card", return_lineage)
    monkeypatch.setattr(
        cli,
        "_authenticate_live_mistral_parse_reuse",
        return_parser_authentication,
    )
    monkeypatch.setattr(
        cli,
        "_verify_materialized_downstream_lineage",
        return_proposed_materialization,
    )
    monkeypatch.setattr(cli, "_validate_selection_run_card_commitment", no_op)
    monkeypatch.setattr(
        cli,
        "_registry_entries_for_keys_bytes",
        registry_entries,
    )
    monkeypatch.setattr(cli, "load_provider_cycle_caps", return_caps)
    monkeypatch.setattr(cli, "_materialization_cohort_cycle_id", cycle_id)
    monkeypatch.setattr(
        cli,
        "parser_reuse_evidence_from_authenticated_artifacts",
        parser_evidence,
    )
    monkeypatch.setattr(
        cli,
        "provider_reuse_evidence_from_verified_rows",
        provider_evidence,
    )
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", no_op)
    monkeypatch.setattr(
        cli,
        "_require_materialized_downstream_lineage_unchanged",
        no_op,
    )
    monkeypatch.setattr(
        "legalforecast.labeling.provider_journal.ProviderAttemptJournal.__init__",
        forbidden_writer,
    )
    monkeypatch.setattr(cli, "_write_jsonl", forbidden_writer)
    monkeypatch.setattr(cli, "_write_immutable_bytes", forbidden_writer)
    return [
        "acquisition",
        "explain-successor-rerun",
        "--index",
        str(tmp_path / "index.json"),
        "--cycle-id",
        "cycle-1",
        "--llm-unitize-run-card",
        str(run_card),
        "--proposed-inputs",
        str(tmp_path / "proposal.json"),
        "--format",
        "json",
    ]


def _fixture(
    tmp_path: Path, *, replace_document: bool
) -> tuple[RerunInputs, SuccessorProposal]:
    envelope, selections, downloads = _proposal_fixture(
        tmp_path, replace_document=replace_document
    )
    proposal = bind_verified_successor_proposal(
        envelope,
        cycle_id="cycle-1",
        selection_records=selections,
        download_records=downloads,
        model_provider="openai",
        provider_account="primary",
        model_registry_sha256="a" * 64,
        policy_sha256="b" * 64,
    )
    current_documents: list[DocumentInput] = []
    parser_reuse: dict[tuple[str, str], ParserReuseEvidence] = {}
    provider_reuse: dict[str, ProviderReuseEvidence] = {}
    for suffix in ("a", "b"):
        candidate = f"candidate-{suffix}"
        document = f"document-{suffix}"
        payload = f"source-{suffix}".encode()
        digest = hashlib.sha256(payload).hexdigest()
        proposed_document = proposal.require_inputs().documents[
            0 if suffix == "a" else 1
        ]
        current_documents.append(
            replace(proposed_document, sha256=digest, byte_count=len(payload))
        )
        parser_reuse[(candidate, document)] = ParserReuseEvidence(
            source_key=(candidate, document, digest, len(payload)),
            markdown_path=f"{candidate}/{document}.md",
            metadata_path=f"{candidate}/{document}.metadata.json",
            record_sha256=hashlib.sha256(f"record-{suffix}".encode()).hexdigest(),
            markdown_sha256=hashlib.sha256(f"markdown-{suffix}".encode()).hexdigest(),
            metadata_sha256=hashlib.sha256(f"metadata-{suffix}".encode()).hexdigest(),
            output_markdown_sha256=hashlib.sha256(
                f"markdown-{suffix}".encode()
            ).hexdigest(),
        )
        prompt = f"prompt-{suffix}"
        identity = ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id=candidate,
            model_key="openai:unitizer",
            prompt=prompt,
            model_registry_sha256="a" * 64,
            prompt_contract="claim-ontology-v4",
        )
        provider_reuse[candidate] = ProviderReuseEvidence(
            candidate_id=candidate,
            stage="llm-unitize",
            logical_call_key=identity.logical_call_key,
            attempt_ordinal=1,
            provider="openai",
            account="primary",
            prompt_text=prompt,
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            model_key="openai:unitizer",
            model_registry_sha256="a" * 64,
            raw_response_json='{"raw":"ok"}',
            normalized_response_json='{"normalized":"ok"}',
            reconstructed_result_json='{"prediction_units":[]}',
            attempt_record_sha256=hashlib.sha256(
                f"attempt-{suffix}".encode()
            ).hexdigest(),
        )
    current = RerunInputs(
        cycle_id="cycle-1",
        selection_records=tuple(selections),
        documents=tuple(current_documents),
        provider_attempt_namespace="claim-ontology-v4",
        model_key="openai:unitizer",
        model_provider="openai",
        provider_account="primary",
        model_registry_sha256="a" * 64,
        policy_sha256="b" * 64,
        parser_reuse_by_document=parser_reuse,
        provider_reuse_by_candidate=provider_reuse,
        parser_run_card_path=tmp_path / "current-parse-card.json",
        markdown_root=tmp_path / "current-markdown",
        provider_journal_path=tmp_path / "provider.sqlite3",
    )
    return current, proposal


def _proposal_fixture(
    tmp_path: Path, *, replace_document: bool
) -> tuple[SuccessorProposal, list[dict[str, Any]], list[dict[str, Any]]]:
    selections: list[dict[str, Any]] = []
    downloads: list[dict[str, Any]] = []
    document_root = tmp_path / "documents"
    document_root.mkdir()
    for suffix in ("a", "b"):
        candidate = f"candidate-{suffix}"
        document = f"document-{suffix}"
        selections.append(
            {
                "candidate_id": candidate,
                "case_id": f"case-{suffix}",
                "documents": [
                    {
                        "candidate_id": candidate,
                        "source_document_id": document,
                        "document_role": "motion_to_dismiss_memorandum",
                        "model_visible": True,
                    }
                ],
            }
        )
        payload = (
            b"replacement-b"
            if replace_document and suffix == "b"
            else f"source-{suffix}".encode()
        )
        relative = Path(candidate) / f"{document}.pdf"
        path = document_root / relative
        path.parent.mkdir()
        path.write_bytes(payload)
        downloads.append(
            {
                "candidate_id": candidate,
                "source_document_id": document,
                "document_role": "motion_to_dismiss_memorandum",
                "local_path": relative.as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "byte_count": len(payload),
            }
        )
    selection_path = tmp_path / "selection.jsonl"
    download_path = tmp_path / "downloads.jsonl"
    selection_card = tmp_path / "selection-card.json"
    clearance = tmp_path / "clearance.jsonl"
    materialization_card = tmp_path / "materialization-card.json"
    registry = tmp_path / "registry.json"
    policy = tmp_path / "policy.json"
    selection_path.write_bytes(_jsonl_bytes(selections))
    download_path.write_bytes(_jsonl_bytes(downloads))
    for path, payload in (
        (selection_card, b'{"card":"selection"}'),
        (clearance, b'{"clearance":true}\n'),
        (materialization_card, b'{"card":"materialization"}'),
        (registry, b'{"models":[]}'),
        (policy, b'{"policy":"frozen"}'),
    ):
        path.write_bytes(payload)
    paths = {
        "selection": selection_path,
        "selection_run_card": selection_card,
        "download_manifest": download_path,
        "disclosure_clearance": clearance,
        "materialization_run_card": materialization_card,
        "model_registry": registry,
        "policy": policy,
    }
    record: dict[str, object] = {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "cycle_id": "cycle-1",
        "document_root": str(document_root),
        "provider_attempt_namespace": "claim-ontology-v4",
        "model_key": "openai:unitizer",
        "successor_output_root": str(tmp_path / "successor"),
        "non_authoritative": True,
    }
    for name, path in paths.items():
        record[f"{name}_path"] = str(path)
        record[f"{name}_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))
    return load_successor_proposal(proposal_path), selections, downloads


def _rewrite_verified_bytes(
    envelope: SuccessorProposal,
    selections: list[dict[str, Any]],
    downloads: list[dict[str, Any]],
) -> None:
    envelope.selection_path.write_bytes(_jsonl_bytes(selections))
    envelope.download_manifest_path.write_bytes(_jsonl_bytes(downloads))


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
