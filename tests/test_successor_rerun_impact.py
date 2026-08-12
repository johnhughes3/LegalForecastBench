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
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    SUCCESSOR_RERUN_IMPACT_V1,
)
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
    successor_derived_output_paths,
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
    parser_evidence = current.parser_reuse_by_document[("candidate-a", "document-a")]
    parser_payload = {
        "source_key": list(parser_evidence.source_key),
        "markdown_path": parser_evidence.markdown_path,
        "metadata_path": parser_evidence.metadata_path,
        "record_sha256": parser_evidence.record_sha256,
        "markdown_sha256": parser_evidence.markdown_sha256,
        "metadata_sha256": parser_evidence.metadata_sha256,
        "output_markdown_sha256": parser_evidence.output_markdown_sha256,
    }
    reusable_parser_outputs = cast(
        list[dict[str, object]], first.record["reusable_parser_outputs"]
    )
    [reusable_parser_output] = reusable_parser_outputs
    named_digest = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            parser_payload,
            domain=SUCCESSOR_RERUN_IMPACT_V1,
        ).digest
    )
    legacy_digest = hashlib.sha256(
        json.dumps(
            parser_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert reusable_parser_output["parser_reuse_identity_sha256"] == named_digest
    assert named_digest != legacy_digest
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

    cli._validate_successor_rerun_commands(  # pyright: ignore[reportPrivateUsage]
        report.record
    )
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
    first = failed_successor_rerun_impact("active lineage is ambiguous")
    second = failed_successor_rerun_impact("active lineage is ambiguous")
    stages = cast(list[dict[str, object]], first.record["stages"])
    assert [node["status"] for node in stages] == [
        "FAILED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
    ]
    assert first.ok is False
    assert first.json_text() == second.json_text()


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("model_key", "openai:successor-unitizer"),
        ("model_provider", "anthropic"),
        ("provider_account", "secondary"),
        ("provider_attempt_namespace", "claim-ontology-v5"),
        ("model_registry_sha256", "c" * 64),
        ("policy_sha256", "d" * 64),
    ],
)
def test_global_provider_drift_reuses_authenticated_parser_inputs(
    tmp_path: Path, field: str, replacement: str
) -> None:
    current, proposal = _fixture(tmp_path, replace_document=False)
    successor = replace(proposal.require_inputs(), **{field: replacement})
    proposal_updates: dict[str, object] = {"inputs": successor}
    if field in {"model_key", "provider_attempt_namespace"}:
        proposal_updates[field] = replacement
    proposal = replace(proposal, **proposal_updates)
    before = _tree_bytes(tmp_path)

    report = plan_successor_rerun_impact(current=current, proposed=proposal)

    assert report.ok is True
    assert report.record["first_invalidated_stage"] == "llm-unitize"
    stages = cast(list[dict[str, object]], report.record["stages"])
    assert stages[1] == {"stage": "parse-documents", "status": "REUSABLE"}
    assert report.record["provider_logical_call_gaps"] == [
        {
            "candidate_id": "candidate-a",
            "reason": "model_prompt_or_policy_commitment_changed",
        },
        {
            "candidate_id": "candidate-b",
            "reason": "model_prompt_or_policy_commitment_changed",
        },
    ]
    commands = cast(list[dict[str, object]], report.record["next_commands"])
    assert [command["stage"] for command in commands] == ["llm-unitize"]
    if field != "provider_attempt_namespace":
        cli._validate_successor_rerun_commands(  # pyright: ignore[reportPrivateUsage]
            report.record
        )
    argv = cast(list[str], commands[0]["argv"])
    assert "plan-parse-documents" not in argv
    assert "parse-documents" not in argv
    assert _flag_value(argv, "--parse-requests") == str(current.parse_requests_path)
    assert _flag_value(argv, "--parser-manifest") == str(current.parser_manifest_path)
    assert _flag_value(argv, "--parser-run-card") == str(current.parser_run_card_path)
    assert _flag_value(argv, "--markdown-root") == str(current.markdown_root)
    assert _flag_value(argv, "--selection") == str(current.selection_path)
    assert _flag_value(argv, "--selection-run-card") == str(
        current.selection_run_card_path
    )
    assert _flag_value(argv, "--download-manifest") == str(
        current.download_manifest_path
    )
    assert _flag_value(argv, "--disclosure-clearance") == str(
        current.disclosure_clearance_path
    )
    assert _flag_value(argv, "--materialization-run-card") == str(
        current.materialization_run_card_path
    )
    assert _flag_value(argv, "--document-root") == str(current.document_root)
    assert current.selection_path != proposal.selection_path
    if field == "policy_sha256":
        successor_journal = proposal.successor_output_root / "provider-attempts.sqlite3"
        assert _flag_value(argv, "--provider-journal") == str(successor_journal)
        assert str(current.provider_journal_path) not in argv
        assert not successor_journal.exists()
    else:
        assert _flag_value(argv, "--provider-journal") == str(
            current.provider_journal_path
        )
    assert commands[0]["advisory_execution"] == "dry_run_only"
    assert "--execute" not in argv
    assert "--provider-spend-authority" not in argv
    assert _flag_value(argv, "--target-eligibility-audit") == str(
        current.target_eligibility_audit_path
    )
    assert _flag_value(argv, "--target-eligibility-audit-run-card") == str(
        current.target_eligibility_audit_run_card_path
    )
    assert _tree_bytes(tmp_path) == before


def test_v4_namespace_upgrade_creates_eligibility_before_unitization(
    tmp_path: Path,
) -> None:
    current, proposal = _fixture(tmp_path, replace_document=False)
    v3_reuse = {
        candidate_id: replace(
            evidence,
            logical_call_key=ProviderCallIdentity(
                stage=evidence.stage,
                candidate_id=evidence.candidate_id,
                model_key=evidence.model_key,
                prompt=evidence.prompt_text,
                model_registry_sha256=evidence.model_registry_sha256,
                account=evidence.account,
                prompt_contract="claim-ontology-v3",
            ).logical_call_key,
        )
        for candidate_id, evidence in current.provider_reuse_by_candidate.items()
    }
    current = replace(
        current,
        provider_attempt_namespace="claim-ontology-v3",
        provider_reuse_by_candidate=v3_reuse,
        target_eligibility_audit_path=None,
        target_eligibility_audit_run_card_path=None,
    )

    report = plan_successor_rerun_impact(current=current, proposed=proposal)

    assert report.record["first_invalidated_stage"] == "llm-unitize"
    commands = cast(list[dict[str, object]], report.record["next_commands"])
    assert [command["stage"] for command in commands] == [
        "audit-stage-a-target-eligibility",
        "llm-unitize",
    ]
    eligibility_argv = cast(list[str], commands[0]["argv"])
    unitize_argv = cast(list[str], commands[1]["argv"])
    assert _flag_value(eligibility_argv, "--parse-requests") == str(
        current.parse_requests_path
    )
    assert _flag_value(unitize_argv, "--target-eligibility-audit") == str(
        proposal.successor_output_root / "target-document-eligibility-audit.jsonl"
    )
    assert "plan-parse-documents" not in eligibility_argv
    assert "parse-documents" not in eligibility_argv


def test_v5_namespace_emits_eligibility_audit_and_unitize_arguments(
    tmp_path: Path,
) -> None:
    current, proposal = _fixture(tmp_path, replace_document=True)
    v5_inputs = replace(
        proposal.require_inputs(), provider_attempt_namespace="claim-ontology-v5"
    )
    proposal = replace(
        proposal,
        provider_attempt_namespace="claim-ontology-v5",
        inputs=v5_inputs,
    )

    report = plan_successor_rerun_impact(current=current, proposed=proposal)

    commands = cast(list[dict[str, object]], report.record["next_commands"])
    assert [command["stage"] for command in commands] == [
        "plan-parse-documents",
        "parse-documents",
        "audit-stage-a-target-eligibility",
        "llm-unitize",
    ]
    eligibility_argv = cast(list[str], commands[-2]["argv"])
    unitize_argv = cast(list[str], commands[-1]["argv"])
    expected_audit = (
        proposal.successor_output_root / "target-document-eligibility-audit.jsonl"
    )
    expected_card = (
        proposal.successor_output_root
        / "run-cards"
        / "audit-stage-a-target-eligibility.json"
    )
    assert _flag_value(eligibility_argv, "--target-eligibility-audit-output") == str(
        expected_audit
    )
    assert _flag_value(unitize_argv, "--target-eligibility-audit") == str(
        expected_audit
    )
    assert _flag_value(unitize_argv, "--target-eligibility-audit-run-card") == str(
        expected_card
    )


def test_nonfinite_proposal_is_a_typed_deterministic_failure(tmp_path: Path) -> None:
    _proposal_fixture(tmp_path, replace_document=False)
    proposal_path = tmp_path / "proposal.json"
    record = json.loads(proposal_path.read_bytes())
    record["model_key"] = float("nan")
    proposal_path.write_bytes(
        (
            json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=True)
            + "\n"
        ).encode()
    )

    messages: list[str] = []
    for _ in range(2):
        with pytest.raises(SuccessorRerunProposalError) as raised:
            load_successor_proposal(proposal_path)
        messages.append(str(raised.value))
    assert messages == [messages[0], messages[0]]
    assert "canonical artifact JSON" in messages[0]


def test_successor_rerun_public_contract_is_linked_and_load_bearing(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    contract_path = root / "docs/schemas/successor-rerun-impact-v1.md"
    contract = contract_path.read_text(encoding="utf-8")
    index = (root / "docs/README.md").read_text(encoding="utf-8")

    assert "legalforecast.successor_rerun_proposal.v1" in contract
    assert "legalforecast.successor_rerun_impact.v1" in contract
    assert "no execution, provider, purchase, freeze, dispatch, publication" in (
        contract
    )
    assert "requires_separate_authorization" in contract
    assert "legalforecast.commitment.artifact-canonical-json.raw-sha256.v1" in contract
    assert "domain-separated by `legalforecast.successor_rerun_impact.v1`" in contract
    assert "profile codec's single trailing newline" in contract
    assert "`successor_output_root` is an absolute alias" in contract
    assert "canonical resolved root is the path exposed" in contract
    assert "alias is resolved again after planning" in contract
    assert "[successor-rerun-impact-v1.md](schemas/successor-rerun-impact-v1.md)" in (
        index
    )

    current, proposal = _fixture(tmp_path, replace_document=True)
    successful = plan_successor_rerun_impact(current=current, proposed=proposal).record
    assert set(successful) == {
        "schema_version",
        "advisory",
        "authority",
        "warning",
        "cycle_id",
        "proposal_sha256",
        "proposed_global_commitments",
        "first_invalidated_stage",
        "stages",
        "affected_cases",
        "affected_candidates",
        "affected_documents",
        "reusable_documents",
        "reusable_parser_outputs",
        "reusable_exact_byte_output_count",
        "reusable_logical_calls",
        "provider_logical_call_gaps",
        "next_commands",
    }
    assert set(cast(Mapping[str, object], successful["authority"])) == {
        "artifact",
        "dispatch",
        "execution",
        "freeze",
        "provider",
        "publication",
        "purchase",
    }
    assert set(
        cast(Mapping[str, object], successful["proposed_global_commitments"])
    ) == {
        "model_key",
        "model_provider",
        "model_registry_sha256",
        "policy_sha256",
        "provider_account",
        "provider_attempt_namespace",
    }
    parser_output = cast(
        list[Mapping[str, object]], successful["reusable_parser_outputs"]
    )[0]
    assert set(parser_output) == {
        "candidate_id",
        "source_document_id",
        "markdown_sha256",
        "parser_reuse_identity_sha256",
    }
    reusable_call = cast(
        list[Mapping[str, object]], successful["reusable_logical_calls"]
    )[0]
    assert set(reusable_call) == {
        "candidate_id",
        "logical_call_key",
        "attempt_ordinal",
    }
    gap = cast(list[Mapping[str, object]], successful["provider_logical_call_gaps"])[0]
    assert set(gap) == {"candidate_id", "reason"}
    commands = cast(list[Mapping[str, object]], successful["next_commands"])
    assert set(commands[0]) == {
        "stage",
        "argv",
        "execution_authority",
        "requires_separate_authorization",
    }
    assert set(commands[-1]) == {
        "stage",
        "argv",
        "execution_authority",
        "requires_separate_authorization",
        "advisory_execution",
    }

    failed = failed_successor_rerun_impact("invalid evidence").record
    assert set(failed) == set(successful) - {
        "cycle_id",
        "proposal_sha256",
        "proposed_global_commitments",
    }
    failed_stages = cast(list[Mapping[str, object]], failed["stages"])
    assert set(failed_stages[0]) == {"stage", "status", "diagnostics"}
    diagnostic = cast(list[Mapping[str, object]], failed_stages[0]["diagnostics"])[0]
    assert set(diagnostic) == {"code", "message"}
    assert set(failed_stages[1]) == {"stage", "status", "blocked_by"}


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
    assert cli.main(argv) == 1
    first = capsys.readouterr().out
    assert cli.main(argv) == 1
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
    assert cli.main(argv) == 0
    first = capsys.readouterr().out
    assert cli.main(argv) == 0
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
    assert cli.main(argv) == 1
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
    assert cli.main(argv) == 1
    failed = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    failed_stages = cast(list[dict[str, Any]], failed["stages"])
    assert "failed current" in failed_stages[0]["diagnostics"][0]["message"]

    def ambiguous(*_args: object) -> tuple[dict[str, str], ...]:
        head = {"run_card_path": str(run_card), "stage": "llm-unitize"}
        return head, dict(head)

    monkeypatch.setattr(cli, "_active_head_chain", ambiguous)
    assert cli.main(argv) == 1
    ambiguous_report = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    ambiguous_stages = cast(list[dict[str, Any]], ambiguous_report["stages"])
    assert "not unique" in ambiguous_stages[0]["diagnostics"][0]["message"]


def test_cli_v4_eligibility_requires_semantic_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)

    def reject_semantic_replay(**_kwargs: object) -> object:
        raise SuccessorRerunImpactError("eligibility semantic replay rejected")

    monkeypatch.setattr(
        cli, "_authenticate_current_v4_eligibility", reject_semantic_replay
    )

    assert cli.main(argv) == 1
    assert "eligibility semantic replay rejected" in _failure_message(capsys)


def test_cli_malformed_committed_v4_eligibility_card_is_typed_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    authenticate_current_v4_eligibility = (
        cli._authenticate_current_v4_eligibility  # pyright: ignore[reportPrivateUsage]
    )
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cli,
        "_authenticate_current_v4_eligibility",
        authenticate_current_v4_eligibility,
    )
    (tmp_path / "current-eligibility-card.json").write_bytes(b"{not-json")

    assert cli.main(argv) == 1
    assert "eligibility audit run card is invalid" in _failure_message(capsys)


@pytest.mark.parametrize(
    ("relative_path", "message"),
    [
        ("current-parse-card.json", "authenticated Stage A input changed"),
        (
            "current-eligibility-audit.jsonl",
            "authenticated v4 eligibility changed",
        ),
        (
            "current-eligibility-card.json",
            "authenticated v4 eligibility changed",
        ),
        (
            "current-documents/candidate-a/document-a.pdf",
            "authenticated Stage A document tree changed",
        ),
        (
            "current-markdown/candidate-a/document-a.md",
            "authenticated Stage A Markdown changed",
        ),
    ],
)
def test_cli_current_authenticated_lineage_mutation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    relative_path: str,
    message: str,
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    _mutate_after_planning(monkeypatch, tmp_path / relative_path)
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert message in _failure_message(capsys)
    _assert_only_path_changed(before, _tree_bytes(tmp_path), relative_path)


def test_cli_parser_reauthentication_change_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    states: Iterator[object] = iter(
        (
            SimpleNamespace(artifacts_by_key={}, source={"snapshot": "before"}),
            SimpleNamespace(artifacts_by_key={}, source={"snapshot": "after"}),
        )
    )

    def next_parser_authentication(**_kwargs: object) -> object:
        return next(states)

    monkeypatch.setattr(
        cli,
        "_authenticate_live_mistral_parse_reuse",
        next_parser_authentication,
    )
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert "authenticated parser reuse changed during planning" in _failure_message(
        capsys
    )
    assert _tree_bytes(tmp_path) == before


@pytest.mark.parametrize(
    "relative_path",
    ["llm-card.json", "units.jsonl", "audit.jsonl", "queue.jsonl"],
)
def test_cli_terminal_snapshot_mutation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    relative_path: str,
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    _mutate_after_planning(monkeypatch, tmp_path / relative_path)
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert "llm-unitize terminal replay changed" in _failure_message(capsys)
    _assert_only_path_changed(before, _tree_bytes(tmp_path), relative_path)


@pytest.mark.parametrize(
    ("relative_path", "message"),
    [
        (
            "materialization-card.json",
            "materialization downstream lineage artifact changed",
        ),
        (
            "documents/candidate-a/document-a.pdf",
            "materialization document tree changed",
        ),
    ],
)
def test_cli_proposed_authenticated_lineage_mutation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    relative_path: str,
    message: str,
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    _mutate_after_planning(monkeypatch, tmp_path / relative_path)
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert message in _failure_message(capsys)
    _assert_only_path_changed(before, _tree_bytes(tmp_path), relative_path)


def test_cli_provider_policy_is_parsed_and_hashed_from_one_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    policy_path = tmp_path / "policy.json"
    expected = policy_path.read_bytes()
    parse_snapshot = cli.load_provider_cycle_caps_bytes

    def swap_after_parse(payload: bytes, *, source: Path) -> object:
        assert payload == expected
        result = parse_snapshot(payload, source=source)
        policy_path.write_bytes(b'{"policy":"swapped"}')
        return result

    monkeypatch.setattr(cli, "load_provider_cycle_caps_bytes", swap_after_parse)
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert "authenticated proposed provider policy changed" in _failure_message(capsys)
    _assert_only_path_changed(before, _tree_bytes(tmp_path), "policy.json")


@pytest.mark.parametrize("target", ["proposal", "registry"])
def test_cli_proposal_or_committed_input_mutation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    target: str,
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    path = tmp_path / ("proposal.json" if target == "proposal" else "registry.json")
    _mutate_after_planning(monkeypatch, path)
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    message = _failure_message(capsys)
    assert (
        "successor proposal changed during planning" in message
        if target == "proposal"
        else "proposed model_registry_path bytes differ from proposal" in message
    )
    _assert_only_path_changed(before, _tree_bytes(tmp_path), path.name)


def test_cli_active_lineage_status_mutation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    statuses: Iterator[dict[str, bool]] = iter(({"ok": True}, {"ok": False}))

    def next_lineage_status(**_kwargs: object) -> dict[str, bool]:
        return next(statuses)

    monkeypatch.setattr(cli, "locate_cycle_lineage", next_lineage_status)
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert "active lineage changed during successor planning" in _failure_message(
        capsys
    )
    assert _tree_bytes(tmp_path) == before


@pytest.mark.parametrize(
    "overlap",
    ["ancestor", "document-descendant", "artifact-descendant"],
)
def test_successor_root_rejects_ancestor_and_descendant_input_overlap(
    tmp_path: Path,
    overlap: str,
) -> None:
    _proposal_fixture(tmp_path, replace_document=False)
    proposal_path = tmp_path / "proposal.json"
    record = json.loads(proposal_path.read_bytes())
    successor_root = {
        "ancestor": tmp_path,
        "document-descendant": tmp_path / "documents" / "successor",
        "artifact-descendant": tmp_path / "selection.jsonl" / "successor",
    }[overlap]
    record["successor_output_root"] = str(successor_root)
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))

    with pytest.raises(
        SuccessorRerunProposalError,
        match="successor derived output overlaps committed input",
    ):
        load_successor_proposal(proposal_path)


def test_successor_root_must_be_new_and_derived_paths_are_complete(
    tmp_path: Path,
) -> None:
    _proposal_fixture(tmp_path, replace_document=False)
    successor = tmp_path / "successor"
    successor.mkdir()
    with pytest.raises(
        SuccessorRerunProposalError, match="must be a new isolated path"
    ):
        load_successor_proposal(tmp_path / "proposal.json")

    relative_outputs = {
        path.relative_to(successor).as_posix()
        for path in successor_derived_output_paths(successor)
    }
    assert relative_outputs == {
        ".",
        "parse-document-requests.jsonl",
        "mistral-markdown-conversions.jsonl",
        "markdown",
        "target-document-eligibility-audit.jsonl",
        "provider-attempts.sqlite3",
        "provider-attempts.sqlite3-journal",
        "provider-attempts.sqlite3-shm",
        "provider-attempts.sqlite3-wal",
        "prediction-units.jsonl",
        "llm-unitization-audit.jsonl",
        "unitization-review-queue.jsonl",
        "run-cards/plan-parse-documents.json",
        "run-cards/parse-documents.json",
        "run-cards/audit-stage-a-target-eligibility.json",
        "run-cards/llm-unitize.json",
        "logs/plan-parse-documents.jsonl",
        "logs/parse-documents.jsonl",
        "logs/audit-stage-a-target-eligibility.jsonl",
        "logs/llm-unitize.jsonl",
    }


@pytest.mark.parametrize(
    ("relative_root", "message"),
    [
        (
            "current-markdown/successor",
            "successor derived output overlaps authenticated current input",
        ),
        (
            "current-documents/successor",
            "successor derived output overlaps authenticated current input",
        ),
        ("units.jsonl/successor", "successor output root parent is unavailable"),
        (
            "provider.sqlite3-wal",
            "successor derived output overlaps authenticated current input",
        ),
        (
            "provider.sqlite3-journal",
            "successor derived output overlaps authenticated current input",
        ),
    ],
)
def test_cli_successor_outputs_reject_current_input_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    relative_root: str,
    message: str,
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    proposal_path = tmp_path / "proposal.json"
    record = json.loads(proposal_path.read_bytes())
    record["successor_output_root"] = str(tmp_path / relative_root)
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert message in _failure_message(capsys)
    assert _tree_bytes(tmp_path) == before


def test_cli_successor_outputs_reject_proposed_lineage_root_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    authenticated_root = tmp_path / "proposed-authenticated-root"
    authenticated_root.mkdir()
    argv = _install_successful_cli_fixture(
        tmp_path,
        monkeypatch,
        proposed_authenticated_paths=(authenticated_root,),
    )
    proposal_path = tmp_path / "proposal.json"
    record = json.loads(proposal_path.read_bytes())
    record["successor_output_root"] = str(authenticated_root / "successor")
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 1
    assert "successor derived output overlaps authenticated proposed input" in (
        _failure_message(capsys)
    )
    assert _tree_bytes(tmp_path) == before


def test_cli_rechecks_proposed_lineage_root_alias_before_reporting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    safe_input_root = tmp_path / "safe-proposed-input"
    safe_input_root.mkdir()
    output_parent = tmp_path / "successor-parent"
    output_parent.mkdir()
    authenticated_alias = tmp_path / "proposed-input-alias"
    authenticated_alias.symlink_to(safe_input_root, target_is_directory=True)
    argv = _install_successful_cli_fixture(
        tmp_path,
        monkeypatch,
        proposed_authenticated_paths=(authenticated_alias,),
    )

    def retarget_after_planning(*_args: object, **_kwargs: object) -> None:
        authenticated_alias.unlink()
        authenticated_alias.symlink_to(output_parent, target_is_directory=True)

    monkeypatch.setattr(
        cli,
        "_require_materialized_downstream_lineage_unchanged",
        retarget_after_planning,
    )
    proposal_path = tmp_path / "proposal.json"
    record = json.loads(proposal_path.read_bytes())
    record["successor_output_root"] = str(output_parent / "successor")
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))

    assert cli.main(argv) == 1
    assert "successor derived output overlaps authenticated proposed input" in (
        _failure_message(capsys)
    )


def test_cli_replays_legacy_local_account_as_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(
        tmp_path, monkeypatch, legacy_default_account=True
    )

    assert cli.main(argv) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["proposed_global_commitments"]["provider_account"] == "default"


def test_cli_canonicalizes_successor_root_and_rejects_parent_symlink_retarget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = _install_successful_cli_fixture(tmp_path, monkeypatch)
    safe_parent = tmp_path / "safe-output-parent"
    safe_parent.mkdir()
    alias_parent = tmp_path / "output-alias"
    alias_parent.symlink_to(safe_parent, target_is_directory=True)
    alias_root = alias_parent / "successor"
    canonical_root = safe_parent / "successor"
    proposal_path = tmp_path / "proposal.json"
    record = json.loads(proposal_path.read_bytes())
    record["successor_output_root"] = str(alias_root)
    proposal_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))
    before = _tree_bytes(tmp_path)

    assert cli.main(argv) == 0
    report_text = capsys.readouterr().out
    assert str(canonical_root) in report_text
    assert str(alias_root) not in report_text
    assert _tree_bytes(tmp_path) == before

    calls = 0

    def retarget_before_final_isolation(**_kwargs: object) -> dict[str, bool]:
        nonlocal calls
        calls += 1
        if calls == 2:
            alias_parent.unlink()
            alias_parent.symlink_to(
                tmp_path / "current-markdown", target_is_directory=True
            )
        return {"ok": True}

    monkeypatch.setattr(cli, "locate_cycle_lineage", retarget_before_final_isolation)

    assert cli.main(argv) == 1
    assert "successor output root alias changed during planning" in _failure_message(
        capsys
    )


def _install_successful_cli_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    legacy_default_account: bool = False,
    proposed_authenticated_paths: tuple[Path, ...] = (),
) -> list[str]:
    current, proposal = _fixture(tmp_path, replace_document=True)
    if legacy_default_account:
        current = replace(
            current,
            provider_account="default",
            provider_reuse_by_candidate={
                candidate_id: replace(evidence, account="default")
                for candidate_id, evidence in (
                    current.provider_reuse_by_candidate.items()
                )
            },
        )
    authenticated_parser_artifacts: dict[
        tuple[str, str, str, int], tuple[Mapping[str, Any], bytes, bytes]
    ] = {}
    for source_key, evidence in current.parser_reuse_by_document.items():
        markdown_bytes = f"authenticated-{source_key[0]}".encode()
        authenticated_parser_artifacts[evidence.source_key] = (
            {
                "markdown_path": evidence.markdown_path,
                "metadata_path": evidence.metadata_path,
                "extracted_text": {
                    "text_sha256": hashlib.sha256(markdown_bytes).hexdigest()
                },
            },
            markdown_bytes,
            f"metadata-{source_key[0]}".encode(),
        )
    parser_reuse = cli.parser_reuse_evidence_from_authenticated_artifacts(
        authenticated_parser_artifacts
    )
    provider_rows = tuple(
        {
            "candidate_id": evidence.candidate_id,
            "stage": evidence.stage,
            "status": "settled",
            "logical_call_key": evidence.logical_call_key,
            "attempt_ordinal": evidence.attempt_ordinal,
            "provider": evidence.provider,
            "account": evidence.account,
            "prompt_text": evidence.prompt_text,
            "prompt_sha256": evidence.prompt_sha256,
            "model_key": evidence.model_key,
            "model_registry_sha256": evidence.model_registry_sha256,
            "raw_response_json": evidence.raw_response_json,
            "normalized_response_json": evidence.normalized_response_json,
            "reconstructed_result_json": evidence.reconstructed_result_json,
        }
        for evidence in current.provider_reuse_by_candidate.values()
    )
    provider_reuse = cli.provider_reuse_evidence_from_verified_rows(provider_rows)
    current = replace(
        current,
        parser_reuse_by_document=parser_reuse,
        provider_reuse_by_candidate=provider_reuse,
    )
    run_card = tmp_path / "llm-card.json"
    raw = tmp_path / "units.jsonl"
    audit = tmp_path / "audit.jsonl"
    queue = tmp_path / "queue.jsonl"
    journal = tmp_path / "provider.sqlite3"
    current_parse_requests = current.parse_requests_path
    current_parser_manifest = current.parser_manifest_path
    current_parser_card = current.parser_run_card_path
    current_eligibility_audit = current.target_eligibility_audit_path
    current_eligibility_card = current.target_eligibility_audit_run_card_path
    assert current_eligibility_audit is not None
    assert current_eligibility_card is not None
    current.selection_path.write_bytes(
        _jsonl_bytes([dict(record) for record in current.selection_records])
    )
    current.selection_run_card_path.write_bytes(
        proposal.selection_run_card_path.read_bytes()
    )
    current.disclosure_clearance_path.write_bytes(
        proposal.disclosure_clearance_path.read_bytes()
    )
    current.materialization_run_card_path.write_bytes(
        proposal.materialization_run_card_path.read_bytes()
    )
    current_parse_requests.write_bytes(b'{"request":"current"}\n')
    current_parser_manifest.write_bytes(b'{"parser":"current"}\n')
    current_parser_card.write_bytes(b'{"parser":"card"}')
    current_eligibility_audit.write_bytes(b'{"eligible":true}\n')
    current_eligibility_card.write_bytes(b'{"eligibility":"card"}')
    current.markdown_root.mkdir()
    current_markdown = current.markdown_root / "candidate-a" / "document-a.md"
    current_markdown.parent.mkdir()
    current_markdown.write_bytes(b"authenticated markdown")
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
                "target_document_eligibility_audit": {
                    "audit": {
                        "path": str(current_eligibility_audit),
                        "sha256": "sha256:"
                        + hashlib.sha256(
                            current_eligibility_audit.read_bytes()
                        ).hexdigest(),
                    },
                    "run_card": {
                        "path": str(current_eligibility_card),
                        "sha256": "sha256:"
                        + hashlib.sha256(
                            current_eligibility_card.read_bytes()
                        ).hexdigest(),
                    },
                    "audit_sha256": "e" * 64,
                },
            },
            sort_keys=True,
        ).encode()
    )
    current_root = current.document_root
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
    current.download_manifest_path.write_bytes(_jsonl_bytes(current_downloads))
    registry_entry = SimpleNamespace(
        registry_key=current.model_key,
        provider=current.model_provider,
    )

    def provider_account(_provider: str) -> str:
        if legacy_default_account:
            raise AssertionError("legacy local replay must not require caps.account()")
        return current.provider_account

    caps = SimpleNamespace(
        cycle_id=current.cycle_id,
        account=provider_account,
        providers={
            current.model_provider: SimpleNamespace(
                account=None if legacy_default_account else current.provider_account
            )
        },
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
        input_paths=(
            current.selection_path,
            current.selection_run_card_path,
            current.download_manifest_path,
            current.disclosure_clearance_path,
            current.materialization_run_card_path,
            current_parse_requests,
            current_parser_manifest,
            current_parser_card,
        ),
        input_commitments={
            "selection": {"path": str(current.selection_path)},
            "selection_run_card": {"path": str(current.selection_run_card_path)},
            "download_manifest": {"path": str(current.download_manifest_path)},
            "disclosure_clearance": {"path": str(current.disclosure_clearance_path)},
            "materialization_run_card": {
                "path": str(current.materialization_run_card_path)
            },
            "parse_requests": {"path": str(current_parse_requests)},
            "parser_manifest": {"path": str(current_parser_manifest)},
            "parser_run_card": {"path": str(current_parser_card)},
        },
        verified_provider_attempt_rows=provider_rows,
        file_snapshots={
            current.selection_path: current.selection_path.read_bytes(),
            current.selection_run_card_path: (
                current.selection_run_card_path.read_bytes()
            ),
            current.download_manifest_path: current.download_manifest_path.read_bytes(),
            current.disclosure_clearance_path: (
                current.disclosure_clearance_path.read_bytes()
            ),
            current.materialization_run_card_path: (
                current.materialization_run_card_path.read_bytes()
            ),
            current_parse_requests: current_parse_requests.read_bytes(),
            current_parser_manifest: current_parser_manifest.read_bytes(),
            current_parser_card: current_parser_card.read_bytes(),
        },
        document_tree=_relative_tree_bytes(current_root),
        markdown_bytes={
            current_markdown.relative_to(current.markdown_root).as_posix(): (
                current_markdown.read_bytes()
            )
        },
    )
    verified_proposal = SimpleNamespace(
        artifact_bytes={
            str(path.absolute()): path.read_bytes()
            for path in (
                proposal.selection_path,
                proposal.selection_run_card_path,
                proposal.download_manifest_path,
                proposal.disclosure_clearance_path,
                proposal.materialization_run_card_path,
            )
        },
        selection_records=proposal.require_inputs().selection_records,
        manifest_records=tuple(
            json.loads(line)
            for line in proposal.download_manifest_path.read_text().splitlines()
        ),
        verified_successor_selection_card=None,
        document_tree=_relative_tree_bytes(proposal.document_root),
        fresh_ledger_namespace=None,
        docket_decision_authority=None,
        authenticated_paths=cli._authenticated_path_aliases(  # pyright: ignore[reportPrivateUsage]
            proposed_authenticated_paths
        ),
        paths=(),
    )
    parser_authentication = SimpleNamespace(
        artifacts_by_key=authenticated_parser_artifacts,
        source={"authenticated": True},
    )
    snapshot = SimpleNamespace(close=lambda: None)

    def locate(**_kwargs: object) -> dict[str, bool]:
        return {"ok": True}

    def active_chain(*_args: object) -> tuple[dict[str, str], ...]:
        return ({"run_card_path": str(run_card), "stage": "llm-unitize"},)

    def stable_journal_state(path: Path) -> tuple[bytes, dict[str, bytes]]:
        wal_path = Path(f"{path}-wal")
        sidecars = {"-wal": wal_path.read_bytes()} if wal_path.is_file() else {}
        return b"stable", sidecars

    def open_snapshot(_path: Path) -> object:
        return snapshot

    def return_lineage(*_args: object, **_kwargs: object) -> object:
        return lineage

    def return_parser_authentication(**_kwargs: object) -> object:
        return parser_authentication

    def return_eligibility_authentication(**_kwargs: object) -> object:
        return (
            current_eligibility_audit,
            current_eligibility_card,
            {
                current_eligibility_audit: current_eligibility_audit.read_bytes(),
                current_eligibility_card: current_eligibility_card.read_bytes(),
            },
        )

    def return_proposed_materialization(**_kwargs: object) -> object:
        return verified_proposal

    def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    def registry_entries(*_args: object) -> tuple[tuple[object, ...], str]:
        return (registry_entry,), current.model_registry_sha256

    def return_caps(_payload: bytes, *, source: Path) -> object:
        assert source == proposal.policy_path
        return caps

    def cycle_id(*_args: object, **_kwargs: object) -> str:
        return "cycle-1"

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
        "_authenticate_current_v4_eligibility",
        return_eligibility_authentication,
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
    monkeypatch.setattr(cli, "load_provider_cycle_caps_bytes", return_caps)
    monkeypatch.setattr(cli, "_materialization_cohort_cycle_id", cycle_id)
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
        selection_path=tmp_path / "current-selection.jsonl",
        selection_run_card_path=tmp_path / "current-selection-card.json",
        download_manifest_path=tmp_path / "current-downloads.jsonl",
        disclosure_clearance_path=tmp_path / "current-clearance.jsonl",
        materialization_run_card_path=tmp_path / "current-materialization-card.json",
        document_root=tmp_path / "current-documents",
        parse_requests_path=tmp_path / "current-parse-requests.jsonl",
        parser_manifest_path=tmp_path / "current-parser-manifest.jsonl",
        parser_run_card_path=tmp_path / "current-parse-card.json",
        markdown_root=tmp_path / "current-markdown",
        target_eligibility_audit_path=tmp_path / "current-eligibility-audit.jsonl",
        target_eligibility_audit_run_card_path=(
            tmp_path / "current-eligibility-card.json"
        ),
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


def _mutate_after_planning(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
) -> None:
    original = cli.plan_successor_rerun_impact

    def mutate(*args: object, **kwargs: object) -> object:
        report = original(*args, **kwargs)
        if path.name == "proposal.json":
            record = json.loads(path.read_bytes())
            record["successor_output_root"] = str(path.parent / "changed-successor")
            path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))
        else:
            path.write_bytes(path.read_bytes() + b"\nmutated")
        return report

    monkeypatch.setattr(cli, "plan_successor_rerun_impact", mutate)


def _failure_message(capsys: pytest.CaptureFixture[str]) -> str:
    report = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    stages = cast(list[dict[str, Any]], report["stages"])
    return cast(str, stages[0]["diagnostics"][0]["message"])


def _assert_only_path_changed(
    before: Mapping[str, bytes], after: Mapping[str, bytes], relative_path: str
) -> None:
    assert before.keys() == after.keys()
    assert before[relative_path] != after[relative_path]
    assert {
        path: payload for path, payload in before.items() if path != relative_path
    } == {path: payload for path, payload in after.items() if path != relative_path}


def _flag_value(argv: list[str], flag: str) -> str:
    return argv[argv.index(flag) + 1]


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


def _relative_tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
