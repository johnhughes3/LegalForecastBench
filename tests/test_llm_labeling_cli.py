from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
import pytest
from legalforecast import cli
from legalforecast.cli import (
    CommandError,
    _require_complete_registry_panel,
    _require_exact_model_disjoint_judges,
    _require_explicit_unique_model_keys,
    main,
)
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.evals.model_registry import LongContextSurcharge, load_model_registry
from legalforecast.evals.provider_spend_control import AttemptLease, ProviderSpendKey
from legalforecast.evals.provider_spend_dynamodb import DynamoDbAuthorityError
from legalforecast.ingestion import provenance_clearance
from legalforecast.ingestion.mistral_markdown_parser import EXPECTED_PARSER_REVISION
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
)
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation
from legalforecast.unitization.review import apply_unitization_reviews
from legalforecast.unitization.review_queue import (
    review_queue_v2_sidecar_path,
    verify_review_queue_v2_coverage,
)
from pytest import MonkeyPatch, raises

JsonRecord = dict[str, Any]


def test_paid_labeling_reservations_include_registry_long_context_surcharge(
    tmp_path: Path,
) -> None:
    registry_entry = SimpleNamespace(
        provider="openai",
        registry_key="openai:gpt-5.6-sol",
        context_limit=1_050_000,
        max_output_tokens=128_000,
        input_token_price=5.0,
        output_token_price=30.0,
        long_context_surcharge=LongContextSurcharge(
            threshold_input_tokens=272_000,
            input_price_multiplier=2.0,
            output_price_multiplier=1.5,
        ),
    )

    journal = llm_pipeline._provider_attempt_journal(
        path=tmp_path / "provider-attempts.sqlite3",
        stage="llm-label",
        candidate_id="candidate-1",
        prompt="synthetic prompt",
        registry_entry=registry_entry,
        cycle_cap_usd=20.0,
        cycle_id="cycle-1",
        model_registry_sha256="b" * 64,
        provider_cycle_caps_sha256="sha256:" + "a" * 64,
    )
    assert journal is not None
    assert journal.reservation_usd == pytest.approx(14.98)
    journal.close()

    spend_handler = llm_pipeline._combined_attempt_handler(
        journal=None,
        authorities={"openai": object()},
        accounts={"openai": "primary"},
        cycle_id="cycle-1",
        stage="llm-label",
        candidate_id="candidate-1",
        registry_entry=registry_entry,
    )
    assert spend_handler is not None
    assert spend_handler.reservation_microusd == 14_980_000  # type: ignore[attr-defined]


def test_markdown_text_filesystem_rejects_absolute_path_outside_root(
    tmp_path: Path,
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Count I", encoding="utf-8")

    with raises(llm_pipeline.LlmPipelineError, match="outside markdown_root"):
        llm_pipeline._markdown_text(
            {"markdown_path": str(outside)}, markdown_root=markdown_root
        )


def test_markdown_text_filesystem_rejects_symlink(tmp_path: Path) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    target = markdown_root / "target.md"
    target.write_text("Count I", encoding="utf-8")
    link = markdown_root / "link.md"
    link.symlink_to(target.name)

    with raises(llm_pipeline.LlmPipelineError, match="cannot be safely read"):
        llm_pipeline._markdown_text(
            {"markdown_path": link.name}, markdown_root=markdown_root
        )


def test_markdown_text_filesystem_rejects_symlinked_parent_to_outside(
    tmp_path: Path,
) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "decision.md").write_text("Count I", encoding="utf-8")
    (markdown_root / "redirect").symlink_to(outside, target_is_directory=True)

    with raises(llm_pipeline.LlmPipelineError, match="cannot be safely read"):
        llm_pipeline._markdown_text(
            {"markdown_path": "redirect/decision.md"}, markdown_root=markdown_root
        )


def test_markdown_text_filesystem_rejects_hardlink(tmp_path: Path) -> None:
    markdown_root = tmp_path / "markdown"
    markdown_root.mkdir()
    target = markdown_root / "target.md"
    target.write_text("Count I", encoding="utf-8")
    link = markdown_root / "link.md"
    os.link(target, link)

    with raises(llm_pipeline.LlmPipelineError, match="cannot be safely read"):
        llm_pipeline._markdown_text(
            {"markdown_path": link.name}, markdown_root=markdown_root
        )


class _FakeSpendAuthority:
    """Minimal remote authority used by paid-labeling CLI fixtures."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        identity = kwargs.get("authority_identity_sha256", "a" * 64)
        assert isinstance(identity, str)
        self.authority_identity_sha256 = identity
        self.leases: dict[str, AttemptLease] = {}

    def authorize_attempt(
        self,
        key: ProviderSpendKey,
        *,
        reservation_microusd: int,
    ) -> AttemptLease:
        lease = AttemptLease(
            attempt_id=hashlib.sha256(
                f"fixture\0{key.logical_call_key}".encode()
            ).hexdigest(),
            authority_identity_sha256=self.authority_identity_sha256,
            logical_call_key=key.logical_call_key,
            attempt_ordinal=1,
            reservation_microusd=reservation_microusd,
        )
        self.leases[key.logical_call_key] = lease
        return lease

    def adopt_attempt(
        self,
        key: ProviderSpendKey,
        *,
        attempt_ordinal: int | None = None,
    ) -> AttemptLease:
        del attempt_ordinal
        return self.leases[key.logical_call_key]

    def record_response(self, lease: AttemptLease, **kwargs: object) -> None:
        del lease, kwargs

    def record_failure(self, lease: AttemptLease, **kwargs: object) -> None:
        del lease, kwargs

    def reconcile_ambiguous(self, lease: AttemptLease, **kwargs: object) -> None:
        del lease, kwargs

    def snapshot(self) -> object:
        raise AssertionError("snapshot is not used by labeling CLI fixtures")


def _journaled_fixture_completion(
    completion: Callable[..., SolverResponse],
) -> Callable[..., SolverResponse]:
    """Make a provider stub preserve the production attempt-journal contract."""

    def wrapped(*args: Any, **kwargs: Any) -> SolverResponse:
        response = completion(*args, **kwargs)
        journal = kwargs["attempt_handler"]
        journal.run_attempt(1, lambda: {"fixture": "provider-response"})
        journal.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    return wrapped


def _stub_downstream_decision_artifact(
    monkeypatch: MonkeyPatch,
    decision_texts_path: Path,
    *,
    replace_after_verification: bool = False,
) -> list[str]:
    monkeypatch.setattr(cli, "require_finalized_envelopes", lambda records: records)
    authenticated_records = tuple(_read_jsonl(decision_texts_path))

    class _Artifact:
        records = authenticated_records

        def verify_stage_b_audit_commitments(self, records: object) -> None:
            del records

    def verify(**kwargs: object) -> _Artifact:
        del kwargs
        if replace_after_verification:
            _write_jsonl(
                decision_texts_path,
                [
                    {
                        "document_id": "decision",
                        "entered_date": "2026-05-18",
                        "text": "The authenticated decision was replaced.",
                    }
                ],
            )
        return _Artifact()

    monkeypatch.setattr(
        cli, "_verify_decision_text_artifact_with_materialization", verify
    )
    return [
        "--selection",
        str(decision_texts_path),
        "--parser-manifest",
        str(decision_texts_path),
        "--prediction-units",
        str(decision_texts_path),
        "--decision-texts-manifest",
        str(decision_texts_path),
        "--decision-texts-run-card",
        str(decision_texts_path),
        "--markdown-root",
        str(decision_texts_path.parent),
    ]


def _provider_caps_path(root: Path) -> Path:
    path = root / "provider-cycle-caps.json"
    if not path.exists():
        _write_json(
            path,
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "test-cycle",
                "spend_authority": {
                    "backend": "dynamodb",
                    "resource_identity_sha256": "a" * 64,
                    "ledger_scope_fields": ["cycle_id", "provider", "account"],
                    "max_billable_attempts": 3,
                    "failure_threshold": 3,
                    "failure_window_seconds": 300,
                },
                "providers": [
                    {
                        "provider": "openai",
                        "account": "primary",
                        "cycle_reservation_cap_usd": "10.00",
                        "external_spend_limit_usd": "20.00",
                        "external_limit_scope": "test account",
                        "external_limit_source": "test fixture",
                        "verified_at": "2026-07-12T16:00:00Z",
                    }
                ],
            },
        )
    return path


def _local_provider_caps_path(root: Path) -> Path:
    path = root / "local-provider-cycle-caps.json"
    if not path.exists():
        _write_json(
            path,
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "test-cycle",
                "providers": [
                    {
                        "provider": "openai",
                        "cycle_reservation_cap_usd": "10.00",
                    }
                ],
            },
        )
    return path


def _evaluated_registry_path(root: Path) -> Path:
    path = root / "evaluated-registry.json"
    if not path.exists():
        record = _registry_record()
        record["model_id"] = "gpt-evaluated"
        record["model_version_or_snapshot"] = "gpt-evaluated-2026-06-30"
        _write_json(path, [record])
    return path


def test_remote_authority_initialization_error_is_a_controlled_cli_error(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    class _FailingAuthority:
        def __init__(self, **kwargs: object) -> None:
            del kwargs
            raise DynamoDbAuthorityError(
                "remote authority unavailable; provider details were suppressed"
            )

    caps_path = _provider_caps_path(tmp_path)
    caps = cli.load_provider_cycle_caps(caps_path)
    monkeypatch.setattr(cli, "DynamoDbProviderSpendAuthority", _FailingAuthority)
    args = argparse.Namespace(
        provider_authority_table="fixture-authority",
        provider_authority_region="us-east-1",
    )

    with pytest.raises(CommandError, match="provider details were suppressed"):
        cli._remote_provider_spend_authorities(
            args,
            provider_caps=caps,
            provider_caps_sha256="sha256:"
            + hashlib.sha256(caps_path.read_bytes()).hexdigest(),
            cycle_id="test-cycle",
            providers=("openai",),
        )


def test_provider_authority_modes_are_mutually_exclusive() -> None:
    parser = argparse.ArgumentParser()
    cli._add_provider_spend_authority_arguments(parser)

    local_args = parser.parse_args(["--local-provider-journal-only"])
    assert local_args.local_provider_journal_only is True
    assert local_args.provider_authority_table is None

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--local-provider-journal-only",
                "--provider-authority-table",
                "fixture-authority",
            ]
        )


def test_unitization_recovery_exposes_closed_attempt_namespace() -> None:
    parser = argparse.ArgumentParser()
    cli._add_acquisition_recover_llm_unitize_arguments(parser)

    [action] = [
        action
        for action in parser._actions
        if action.dest == "provider_attempt_namespace"
    ]
    assert action.choices == (
        "claim-ontology-v2",
        "claim-ontology-v3",
        "claim-ontology-v4",
        "claim-ontology-v5",
    )


def test_unitizer_terminalization_exposes_explicit_v5_candidate_surface() -> None:
    parser = argparse.ArgumentParser()
    cli._add_acquisition_terminalize_llm_unitize_arguments(parser)

    args = parser.parse_args(
        [
            "--output-root",
            "terminal",
            "--selection",
            "selection.jsonl",
            "--parser-manifest",
            "parser.jsonl",
            "--model-registry",
            "registry.json",
            "--model-key",
            "anthropic:unitizer",
            "--candidate-id",
            "70754103",
            "--provider-attempt-namespace",
            "claim-ontology-v5",
        ]
    )

    assert args.candidate_id == "70754103"
    assert args.provider_attempt_namespace == "claim-ontology-v5"
    assert args.handler is cli._cmd_acquisition_terminalize_llm_unitize_reconstruction


def test_llm_unitize_accepts_repeatable_terminal_escalation_receipts() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "acquisition",
            "llm-unitize",
            "--output-root",
            "out",
            "--selection",
            "selection.jsonl",
            "--parser-manifest",
            "parser.jsonl",
            "--model-registry",
            "registry.json",
            "--model-key",
            "anthropic:unitizer",
            "--terminal-escalation",
            "first.json",
            "--terminal-escalation",
            "second.json",
        ]
    )

    assert args.terminal_escalation == [Path("first.json"), Path("second.json")]


def test_unitizer_terminalization_requires_execute_and_v5_before_lineage(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    lineage_opened = False

    def open_lineage(*args: object, **kwargs: object) -> object:
        nonlocal lineage_opened
        del args, kwargs
        lineage_opened = True
        raise AssertionError("terminal preflight must reject before lineage")

    monkeypatch.setattr(cli, "_verify_stage_a_unitization_lineage", open_lineage)
    common = {
        "output_root": tmp_path / "terminal",
        "provider_authority_table": None,
        "provider_attempt_namespace": "claim-ontology-v5",
    }
    with pytest.raises(
        CommandError,
        match="terminalize-llm-unitize-reconstruction requires --execute",
    ):
        cli._cmd_acquisition_terminalize_llm_unitize_reconstruction(
            argparse.Namespace(execute=False, **common)
        )
    with pytest.raises(
        CommandError,
        match="requires --provider-attempt-namespace claim-ontology-v5",
    ):
        cli._cmd_acquisition_terminalize_llm_unitize_reconstruction(
            argparse.Namespace(
                execute=True,
                **{**common, "provider_attempt_namespace": "claim-ontology-v4"},
            )
        )
    assert lineage_opened is False


def test_unitizer_terminalization_writes_provider_free_replayable_receipt(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_root = tmp_path / "terminal"
    receipt_path = output_root / "receipt.json"
    journal_path = tmp_path / "provider-attempts.sqlite3"
    journal_path.write_bytes(b"unchanged journal")
    input_path = tmp_path / "selection.jsonl"
    input_path.write_text("{}\n", encoding="utf-8")
    candidate_id = "70754103"
    selection = {"candidate_id": candidate_id, "case_id": "case-1"}
    input_commitments = {"selection": {"sha256": "1" * 64}}
    lineage = SimpleNamespace(
        selection_records=(selection,),
        parser_records=(),
        registry_entry=SimpleNamespace(
            registry_key="anthropic:unitizer", provider="anthropic"
        ),
        registry_sha256="2" * 64,
        provider_caps=SimpleNamespace(
            cap_usd=lambda provider: 100.0,
            providers={"anthropic": SimpleNamespace(account=None)},
        ),
        provider_caps_sha256="3" * 64,
        provider_journal_path=journal_path,
        cohort_cycle_id="cycle-1",
        input_paths=(input_path, journal_path),
        input_commitments=input_commitments,
        markdown_bytes={},
    )
    provider_rows = (
        {
            "stage": "llm-unitize",
            "candidate_id": candidate_id,
            "attempt_ordinal": ordinal,
            "status": "reconstruction_failed",
        }
        for ordinal in (1, 2, 3)
    )
    frozen_rows = tuple(provider_rows)
    receipt: JsonRecord = {
        "schema_version": "legalforecast.llm_stage_a_unitizer_terminal_escalation.v1",
        "candidate_id": candidate_id,
    }
    completion_calls: list[dict[str, Any]] = []
    builder_calls = 0

    monkeypatch.setattr(
        cli, "_verify_stage_a_unitization_lineage", lambda *args, **kwargs: lineage
    )
    monkeypatch.setattr(
        cli, "verify_provider_journal_identity", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", lambda value: None)
    monkeypatch.setattr(
        cli,
        "_provider_stage_attempt_rows",
        lambda path, *, stage: frozen_rows,
    )

    def build(**kwargs: object) -> object:
        nonlocal builder_calls
        builder_calls += 1
        assert kwargs["selection_record"] == selection
        assert kwargs["provider_attempt_namespace"] == "claim-ontology-v5"
        return SimpleNamespace(to_record=lambda: receipt)

    monkeypatch.setattr(cli, "build_llm_stage_a_unitizer_terminal_escalation", build)
    monkeypatch.setattr(
        cli,
        "_write_or_verify_immutable_recovery_completion",
        lambda args, **kwargs: completion_calls.append(kwargs),
    )
    args = argparse.Namespace(
        execute=True,
        provider_authority_table=None,
        provider_attempt_namespace="claim-ontology-v5",
        output_root=output_root,
        terminal_escalation_output=receipt_path,
        resume=False,
        markdown_root=tmp_path / "markdown",
        candidate_id=candidate_id,
    )

    assert cli._cmd_acquisition_terminalize_llm_unitize_reconstruction(args) == 0
    first_receipt = receipt_path.read_bytes()
    args.resume = True
    assert cli._cmd_acquisition_terminalize_llm_unitize_reconstruction(args) == 0

    assert receipt_path.read_bytes() == first_receipt
    assert journal_path.read_bytes() == b"unchanged journal"
    assert builder_calls == 2
    assert completion_calls == [
        {
            "stage": "terminalize-llm-unitize-reconstruction",
            "input_paths": (input_path, journal_path),
            "output_paths": (receipt_path,),
            "extra": {
                "source_commitments": input_commitments,
                "unitizer_terminal_escalation": receipt,
            },
        },
        {
            "stage": "terminalize-llm-unitize-reconstruction",
            "input_paths": (input_path, journal_path),
            "output_paths": (receipt_path,),
            "extra": {
                "source_commitments": input_commitments,
                "unitizer_terminal_escalation": receipt,
            },
        },
    ]


def test_unitizer_terminalization_rejects_provider_journal_mutation(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    candidate_id = "70754103"
    journal_path = tmp_path / "provider-attempts.sqlite3"
    journal_path.write_bytes(b"journal")
    lineage = SimpleNamespace(
        selection_records=({"candidate_id": candidate_id, "case_id": "case-1"},),
        parser_records=(),
        registry_entry=SimpleNamespace(
            registry_key="anthropic:unitizer", provider="anthropic"
        ),
        registry_sha256="2" * 64,
        provider_caps=SimpleNamespace(
            cap_usd=lambda provider: 100.0,
            providers={"anthropic": SimpleNamespace(account=None)},
        ),
        provider_caps_sha256="3" * 64,
        provider_journal_path=journal_path,
        cohort_cycle_id="cycle-1",
        input_paths=(journal_path,),
        input_commitments={},
        markdown_bytes={},
    )
    snapshots = iter(
        (
            ({"attempt_ordinal": 1, "status": "reconstruction_failed"},),
            ({"attempt_ordinal": 1, "status": "settled"},),
        )
    )
    monkeypatch.setattr(
        cli, "_verify_stage_a_unitization_lineage", lambda *args, **kwargs: lineage
    )
    monkeypatch.setattr(
        cli, "verify_provider_journal_identity", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(cli, "_require_stage_a_lineage_unchanged", lambda value: None)
    monkeypatch.setattr(
        cli,
        "_provider_stage_attempt_rows",
        lambda path, *, stage: next(snapshots),
    )
    monkeypatch.setattr(
        cli,
        "build_llm_stage_a_unitizer_terminal_escalation",
        lambda **kwargs: SimpleNamespace(
            to_record=lambda: {"candidate_id": candidate_id}
        ),
    )

    with pytest.raises(CommandError, match="changed the provider journal"):
        cli._cmd_acquisition_terminalize_llm_unitize_reconstruction(
            argparse.Namespace(
                execute=True,
                provider_authority_table=None,
                provider_attempt_namespace="claim-ontology-v5",
                output_root=tmp_path / "terminal",
                terminal_escalation_output=None,
                resume=False,
                markdown_root=tmp_path / "markdown",
                candidate_id=candidate_id,
            )
        )


@pytest.mark.parametrize(
    "add_arguments",
    (
        cli._add_acquisition_recover_llm_review_stage_a_arguments,
        cli._add_acquisition_terminalize_llm_review_stage_a_arguments,
    ),
)
def test_structural_recovery_accepts_optional_review_namespace(
    add_arguments: Any,
) -> None:
    parser = argparse.ArgumentParser()
    add_arguments(parser)

    [action] = [
        action
        for action in parser._actions
        if action.dest == "provider_attempt_namespace"
    ]
    assert action.choices == (
        "claim-ontology-v2",
        "claim-ontology-v3",
        "claim-ontology-v4",
        "claim-ontology-v5",
    )
    assert action.default is None


def test_structural_recovery_namespace_can_supersede_unitization_contract(
    tmp_path: Path,
) -> None:
    unitization_card = tmp_path / "llm-unitize.json"
    _write_json(
        unitization_card,
        {"model_execution": {"provider_attempt_namespace": "claim-ontology-v2"}},
    )

    assert (
        cli._stage_a_structural_review_provider_attempt_namespace(
            argparse.Namespace(), unitization_card
        )
        == "claim-ontology-v2"
    )
    assert (
        cli._stage_a_structural_review_provider_attempt_namespace(
            argparse.Namespace(provider_attempt_namespace="claim-ontology-v3"),
            unitization_card,
        )
        == "claim-ontology-v3"
    )
    legacy_unitization_card = tmp_path / "legacy-llm-unitize.json"
    _write_json(legacy_unitization_card, {})
    assert (
        cli._stage_a_structural_review_provider_attempt_namespace(
            argparse.Namespace(), legacy_unitization_card
        )
        is None
    )


@pytest.mark.parametrize(
    ("unitization_namespace", "review_namespace"),
    (
        (None, None),
        ("claim-ontology-v2", "claim-ontology-v2"),
        ("claim-ontology-v2", "claim-ontology-v3"),
        ("claim-ontology-v4", "claim-ontology-v4"),
        ("claim-ontology-v5", "claim-ontology-v4"),
    ),
)
def test_structural_review_accepts_only_closed_namespace_pairs(
    unitization_namespace: str | None,
    review_namespace: str | None,
) -> None:
    cli._require_stage_a_structural_review_namespace_pair(
        unitization_namespace=unitization_namespace,
        review_namespace=review_namespace,
    )


@pytest.mark.parametrize(
    ("unitization_namespace", "review_namespace"),
    (
        (None, "claim-ontology-v2"),
        (None, "claim-ontology-v3"),
        (None, "claim-ontology-v4"),
        (None, "claim-ontology-v5"),
        ("claim-ontology-v2", None),
        ("claim-ontology-v4", None),
        ("claim-ontology-v5", None),
        ("claim-ontology-v3", "claim-ontology-v2"),
        ("claim-ontology-v3", "claim-ontology-v3"),
        ("claim-ontology-v4", "claim-ontology-v2"),
        ("claim-ontology-v4", "claim-ontology-v3"),
        ("claim-ontology-v2", "claim-ontology-v4"),
        ("claim-ontology-v3", "claim-ontology-v4"),
        ("claim-ontology-v4", "claim-ontology-v5"),
        ("claim-ontology-v5", "claim-ontology-v2"),
        ("claim-ontology-v5", "claim-ontology-v3"),
        ("claim-ontology-v5", "claim-ontology-v5"),
    ),
)
def test_structural_review_rejects_unreviewed_namespace_pairs(
    unitization_namespace: str | None,
    review_namespace: str | None,
) -> None:
    with raises(
        CommandError,
        match=(
            r"not an approved Stage A structural-review pair|"
            r"not accepted for llm-review-stage-a"
        ),
    ):
        cli._require_stage_a_structural_review_namespace_pair(
            unitization_namespace=unitization_namespace,
            review_namespace=review_namespace,
        )


def test_local_provider_journal_only_accepts_legacy_caps(
    tmp_path: Path,
) -> None:
    caps_path = _local_provider_caps_path(tmp_path)
    caps = cli.load_provider_cycle_caps(caps_path)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    args = argparse.Namespace(
        local_provider_journal_only=True,
        provider_authority_table=None,
        provider_authority_region="us-east-1",
        provider_journal=journal_path,
    )

    authorities, accounts = cli._provider_spend_authorities(
        args,
        provider_caps=caps,
        provider_caps_sha256="sha256:"
        + hashlib.sha256(caps_path.read_bytes()).hexdigest(),
        cycle_id="test-cycle",
        providers=("openai",),
    )

    assert authorities is None
    assert accounts == {"openai": "default"}


def test_local_provider_journal_only_preserves_committed_account_alias(
    tmp_path: Path,
) -> None:
    caps_path = _provider_caps_path(tmp_path)
    caps = cli.load_provider_cycle_caps(caps_path)
    args = argparse.Namespace(
        local_provider_journal_only=True,
        provider_authority_table=None,
        provider_authority_region="us-east-1",
        provider_journal=tmp_path / "provider-attempts.sqlite3",
    )

    authorities, accounts = cli._provider_spend_authorities(
        args,
        provider_caps=caps,
        provider_caps_sha256="sha256:"
        + hashlib.sha256(caps_path.read_bytes()).hexdigest(),
        cycle_id="test-cycle",
        providers=("openai",),
    )

    assert authorities is None
    assert accounts == {"openai": "primary"}


def test_local_provider_journal_only_requires_explicit_journal(
    tmp_path: Path,
) -> None:
    caps_path = _local_provider_caps_path(tmp_path)
    caps = cli.load_provider_cycle_caps(caps_path)
    args = argparse.Namespace(
        local_provider_journal_only=True,
        provider_authority_table=None,
        provider_authority_region="us-east-1",
        provider_journal=None,
    )

    with pytest.raises(
        CommandError,
        match="--local-provider-journal-only requires --provider-journal",
    ):
        cli._provider_spend_authorities(
            args,
            provider_caps=caps,
            provider_caps_sha256="sha256:"
            + hashlib.sha256(caps_path.read_bytes()).hexdigest(),
            cycle_id="test-cycle",
            providers=("openai",),
        )


def test_provider_spend_authorities_requires_explicit_mode(
    tmp_path: Path,
) -> None:
    caps_path = _provider_caps_path(tmp_path)
    caps = cli.load_provider_cycle_caps(caps_path)
    args = argparse.Namespace(
        local_provider_journal_only=False,
        provider_authority_table=None,
        provider_authority_region="us-east-1",
        provider_journal=tmp_path / "provider-attempts.sqlite3",
    )

    with pytest.raises(
        CommandError,
        match=(
            "requires exactly one of --provider-authority-table or "
            "--local-provider-journal-only"
        ),
    ):
        cli._provider_spend_authorities(
            args,
            provider_caps=caps,
            provider_caps_sha256="sha256:"
            + hashlib.sha256(caps_path.read_bytes()).hexdigest(),
            cycle_id="test-cycle",
            providers=("openai",),
        )


def test_provider_spend_authorities_preserve_dynamodb_mode(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    caps_path = _provider_caps_path(tmp_path)
    caps = cli.load_provider_cycle_caps(caps_path)
    monkeypatch.setattr(cli, "DynamoDbProviderSpendAuthority", _FakeSpendAuthority)
    args = argparse.Namespace(
        local_provider_journal_only=False,
        provider_authority_table="fixture-authority",
        provider_authority_region="us-east-1",
        provider_journal=tmp_path / "provider-attempts.sqlite3",
    )

    authorities, accounts = cli._provider_spend_authorities(
        args,
        provider_caps=caps,
        provider_caps_sha256="sha256:"
        + hashlib.sha256(caps_path.read_bytes()).hexdigest(),
        cycle_id="test-cycle",
        providers=("openai",),
    )

    assert isinstance(authorities, dict)
    assert isinstance(authorities["openai"], _FakeSpendAuthority)
    assert accounts == {"openai": "primary"}


def _stub_authenticated_stage_a_lineage(
    monkeypatch: MonkeyPatch,
    *,
    selection_path: Path,
    parser_path: Path,
    markdown_root: Path,
    registry_path: Path,
    caps_path: Path,
    provider_journal_path: Path,
) -> list[str]:
    monkeypatch.setattr(cli, "DynamoDbProviderSpendAuthority", _FakeSpendAuthority)
    fixture_lineage_paths = {
        name: selection_path.parent / f"fixture-{name.replace('_', '-')}.json"
        for name in (
            "selection_run_card",
            "download_manifest",
            "disclosure_clearance",
            "materialization_run_card",
            "parse_requests",
            "parser_run_card",
        )
    }
    for path in fixture_lineage_paths.values():
        _write_json(path, {})
    entry, registry_sha256 = cli._registry_entry_for_key(
        registry_path, "openai:gpt-test"
    )
    caps = cli.load_provider_cycle_caps(caps_path)
    selection_records = tuple(_read_jsonl(selection_path))
    parser_records = tuple(_read_jsonl(parser_path))
    markdown_bytes = {
        path.relative_to(markdown_root).as_posix(): path.read_bytes()
        for path in sorted(markdown_root.rglob("*.md"))
    }
    markdown_tree = {
        relative_path: {
            "path": str(markdown_root / relative_path),
            "sha256": cli._bytes_sha256(payload),
            "byte_count": len(payload),
        }
        for relative_path, payload in markdown_bytes.items()
    }
    document_tree = cli._materializer_tree_snapshot(markdown_root)
    captured_files = (
        selection_path,
        parser_path,
        registry_path,
        caps_path,
        *fixture_lineage_paths.values(),
    )
    lineage = cli._StageAUnitizationLineage(
        selection_records=selection_records,
        parser_records=parser_records,
        registry_entry=entry,
        registry_sha256=registry_sha256,
        provider_caps=caps,
        provider_caps_sha256=cli._path_sha256(caps_path),
        provider_journal_path=provider_journal_path,
        document_root=markdown_root,
        markdown_root=markdown_root,
        cohort_cycle_id=caps.cycle_id,
        input_paths=(
            selection_path,
            parser_path,
            markdown_root,
            registry_path,
            caps_path,
            provider_journal_path,
        ),
        input_commitments={
            "selection": cli._stage_a_file_commitment(selection_path),
            **{
                name: cli._stage_a_file_commitment(path)
                for name, path in fixture_lineage_paths.items()
            },
            "parser_manifest": cli._stage_a_file_commitment(parser_path),
            "model_registry": cli._stage_a_file_commitment(registry_path),
            "provider_cycle_caps": cli._stage_a_file_commitment(caps_path),
            "document_tree": {
                path: cli._bytes_sha256(payload)
                for path, payload in document_tree.items()
            },
            "markdown_tree": markdown_tree,
        },
        markdown_tree=markdown_tree,
        file_snapshots={path: path.read_bytes() for path in captured_files},
        document_tree=document_tree,
        markdown_bytes=markdown_bytes,
    )
    parse_lineage = cli._VerifiedStageAParseLineage(
        selection_records=selection_records,
        selection_bytes=selection_path.read_bytes(),
        parser_records=parser_records,
        parser_manifest_bytes=parser_path.read_bytes(),
        document_root=markdown_root,
        markdown_root=markdown_root,
        cohort_cycle_id=caps.cycle_id,
        input_paths=lineage.input_paths,
        input_commitments=lineage.input_commitments,
        markdown_tree=markdown_tree,
        file_snapshots=lineage.file_snapshots,
        document_tree=document_tree,
        markdown_bytes=markdown_bytes,
    )
    eligibility_audit_path = selection_path.parent / "fixture-eligibility.jsonl"
    eligibility_card_path = selection_path.parent / "fixture-eligibility-card.json"
    _write_jsonl(eligibility_audit_path, [])
    _write_json(eligibility_card_path, {})
    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_lineage",
        lambda *args, **kwargs: lineage,
    )
    monkeypatch.setattr(
        cli,
        "_verify_verified_stage_a_parse_lineage",
        lambda *args, **kwargs: parse_lineage,
    )
    monkeypatch.setattr(
        cli,
        "_require_clean_v4_target_document_eligibility_audit",
        lambda **kwargs: {
            "audit": cli._stage_a_file_commitment(eligibility_audit_path),
            "run_card": cli._stage_a_file_commitment(eligibility_card_path),
        },
    )
    return [
        "--provider-journal",
        str(provider_journal_path),
        "--provider-authority-table",
        "fixture-provider-authority",
        "--provider-attempt-namespace",
        "claim-ontology-v5",
        "--target-eligibility-audit",
        str(eligibility_audit_path),
        "--target-eligibility-audit-run-card",
        str(eligibility_card_path),
    ]


def test_stage_a_lineage_reuses_identical_authenticated_pdf_scans(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """One Stage A preflight must not re-extract the same PDF for each replay."""

    calls = 0
    scan = object()

    def expensive_scan(data: bytes) -> object:
        nonlocal calls
        assert data == b"production-shaped-pdf-bytes"
        calls += 1
        return scan

    scanner_plan = {
        "documents": [
            {
                "disclosure_pdf_scan": {
                    "schema_version": provenance_clearance.PDF_SCAN_SCHEMA_VERSION,
                    "method": "pypdf_page_text_v2",
                }
            }
        ]
    }
    monkeypatch.setattr(
        provenance_clearance,
        "scan_disclosure_document",
        expensive_scan,
    )

    def replay_four_authority_boundaries(
        _args: argparse.Namespace,
        *,
        markdown_root: Path,
        parse_lineage: object | None = None,
        relocations: object | None = None,
    ) -> object:
        assert markdown_root == tmp_path
        assert parse_lineage is None
        # Nothing is relocated in this fixture, so the scan-reuse path under
        # test is exercised exactly as it is in production.
        assert not relocations
        for _ in range(4):
            assert (
                provenance_clearance.document_scanner_for_plan(scanner_plan)(
                    b"production-shaped-pdf-bytes"
                )
                is scan
            )
        return scan

    monkeypatch.setattr(
        cli,
        "_verify_stage_a_unitization_lineage_uncached",
        replay_four_authority_boundaries,
    )

    assert (
        cli._verify_stage_a_unitization_lineage(
            argparse.Namespace(), markdown_root=tmp_path
        )
        is scan
    )
    assert calls == 1


def _stub_authenticated_finalized_provider_chain(
    monkeypatch: MonkeyPatch,
    *,
    selection_path: Path,
    parser_path: Path,
    markdown_root: Path,
    registry_path: Path,
    caps_path: Path,
    provider_journal_path: Path,
    finalized_units_path: Path,
) -> list[str]:
    monkeypatch.setattr(cli, "DynamoDbProviderSpendAuthority", _FakeSpendAuthority)
    entry = load_model_registry(registry_path).entries[0]
    caps = cli.load_provider_cycle_caps(caps_path)
    registry_sha = cli._path_sha256(registry_path).removeprefix("sha256:")
    if not provider_journal_path.exists():
        ProviderAttemptJournal(
            provider_journal_path,
            identity=ProviderCallIdentity(
                stage="fixture-bootstrap",
                candidate_id="fixture",
                model_key=entry.registry_key,
                prompt="fixture",
                model_registry_sha256=registry_sha,
            ),
            provider=entry.provider,
            reservation_usd=0.0,
            cycle_cap_usd=caps.cap_usd(entry.provider),
            cycle_id=caps.cycle_id,
            provider_cycle_caps_sha256=cli._path_sha256(caps_path),
        ).close()
    unit_card = finalized_units_path.parent / "fixture-unitization-run-card.json"
    structural_card = (
        finalized_units_path.parent / "fixture-structural-review-run-card.json"
    )
    apply_card = finalized_units_path.parent / "fixture-apply-run-card.json"
    review_queue = finalized_units_path.parent / "fixture-review-queue.jsonl"
    for path in (unit_card, structural_card, apply_card):
        _write_json(path, {})
    _write_jsonl(review_queue, [])
    selection_records = tuple(_read_jsonl(selection_path))
    parser_records = tuple(_read_jsonl(parser_path))
    markdown_tree, markdown_bytes = cli._stage_a_markdown_tree_snapshot(
        parser_records,
        markdown_root=markdown_root,
    )
    lineage = cli._StageAUnitizationLineage(
        selection_records=selection_records,
        parser_records=parser_records,
        registry_entry=entry,
        registry_sha256=registry_sha,
        provider_caps=caps,
        provider_caps_sha256=cli._path_sha256(caps_path),
        provider_journal_path=provider_journal_path,
        document_root=markdown_root,
        markdown_root=markdown_root,
        cohort_cycle_id=caps.cycle_id,
        input_paths=(),
        input_commitments={
            "document_tree": {
                path: cli._bytes_sha256(payload)
                for path, payload in cli._materializer_tree_snapshot(
                    markdown_root
                ).items()
            },
            "markdown_tree": markdown_tree,
        },
        markdown_tree=markdown_tree,
        file_snapshots={
            path: path.read_bytes()
            for path in (selection_path, parser_path, registry_path, caps_path)
        },
        document_tree=cli._materializer_tree_snapshot(markdown_root),
        markdown_bytes=markdown_bytes,
    )
    monkeypatch.setattr(
        cli,
        "_verify_finalized_stage_a_provider_chain",
        lambda *args, **kwargs: (lineage, unit_card, review_queue),
    )
    monkeypatch.setattr(cli, "_verify_stage_a_review_run_card", lambda *a, **k: None)
    return [
        "--llm-unitization-run-card",
        str(unit_card),
        "--llm-review-stage-a-run-card",
        str(structural_card),
        "--unitization-review-run-card",
        str(apply_card),
        "--provider-journal",
        str(provider_journal_path),
        "--provider-authority-table",
        "fixture-provider-authority",
    ]


def _settle_fixture_unitization_attempt(
    response: SolverResponse, kwargs: Mapping[str, Any]
) -> SolverResponse:
    journal = kwargs["attempt_handler"]
    journal.run_attempt(1, lambda: {"fixture": "provider-response"})
    journal.settle_attempt(
        1,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        actual_cost_usd=response.estimated_cost,
        raw_output=response.raw_output,
    )
    return response


def test_llm_label_requires_iso_first_written_disposition_date() -> None:
    selection = _selection_record()
    del selection["decision_date"]
    with raises(
        llm_pipeline.LlmPipelineError,
        match="missing the first written MTD disposition",
    ):
        llm_pipeline._decision_date(selection)

    selection["decision_date"] = "docket-entry-16"
    with raises(llm_pipeline.LlmPipelineError, match="must be an ISO date"):
        llm_pipeline._decision_date(selection)


def test_stage_b_judges_must_be_exact_model_disjoint_from_evaluated_registry(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.json"
    _write_json(registry_path, [_registry_record()])
    [judge] = load_model_registry(registry_path).entries

    with raises(CommandError, match="not exact-model disjoint"):
        _require_exact_model_disjoint_judges(
            [judge], evaluated_model_registry_path=registry_path
        )


@pytest.mark.parametrize("keys", [("   ",), ("openai:gpt-test", "openai:gpt-test")])
def test_stage_b_judge_keys_must_be_explicit_and_unique(keys: tuple[str, ...]) -> None:
    with raises(CommandError):
        _require_explicit_unique_model_keys(keys)


def test_stage_b_must_select_complete_dedicated_judge_registry(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.json"
    first = _registry_record()
    second = {**first, "model_id": "gpt-b", "model_version_or_snapshot": "gpt-b"}
    _write_json(registry_path, [first, second])
    [selected, _] = load_model_registry(registry_path).entries

    with raises(CommandError, match="every judge"):
        _require_complete_registry_panel([selected], model_registry_path=registry_path)


def test_acquisition_llm_unitize_and_label_validate_registry_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "The motion to dismiss Count I is granted without leave to amend.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
            _parser_record("decision", "decision.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    provider_calls = 0

    def journaled_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        nonlocal provider_calls
        provider_calls += 1
        response = _fake_completion(*args, **kwargs)
        journal = kwargs["attempt_handler"]
        journal.run_attempt(1, lambda: {"fixture": "provider-response"})
        journal.settle_attempt(
            1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            actual_cost_usd=response.estimated_cost,
            raw_output=response.raw_output,
        )
        return response

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", journaled_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    units = _read_jsonl(output_root / "prediction-units.jsonl")
    assert units[0]["candidate_id"] == "cand-1"
    assert units[0]["prediction_units"][0]["unit_id"] == "unit-1"
    unit_audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert unit_audit["model_key"] == "openai:gpt-test"
    assert unit_audit["status"] == "adjudication_pending"
    assert unit_audit["human_verified"] is False
    assert unit_audit["estimated_cost"] > 0
    unitization_queue = _read_jsonl(output_root / "unitization-review-queue.jsonl")
    assert unitization_queue == [
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "review_id": "cand-1:unit-1:stage-a-review",
            "review_item": {
                "notes": "Stage A unit requires blinded pre-decision review.",
                "reason": "low_confidence",
                "source_document_ids": ["complaint", "mtd"],
                "unit_id": "unit-1",
            },
            "route_reason": "low_confidence",
            "schema_version": "legalforecast.unitization_review_queue.v1",
            "status": "pending_adjudication",
            "unit_id": "unit-1",
        }
    ]
    unitization_card = output_root / "run-cards" / "llm-unitize.json"
    provider_journal = output_root / "provider-attempts.sqlite3"
    review_root = tmp_path / "structural-review-output"
    review_args = [
        "acquisition",
        "llm-review-stage-a",
        "--selection",
        str(selection_path),
        "--parser-manifest",
        str(parser_path),
        "--markdown-root",
        str(markdown_root),
        "--prediction-units",
        str(output_root / "prediction-units.jsonl"),
        "--llm-unitization-run-card",
        str(unitization_card),
        "--unitization-review-queue",
        str(output_root / "unitization-review-queue.jsonl"),
        "--model-registry",
        str(registry_path),
        "--model-key",
        "openai:gpt-test",
        "--provider-cycle-caps",
        str(caps_path),
        "--provider-journal",
        str(provider_journal),
        "--provider-attempt-namespace",
        "claim-ontology-v4",
        "--provider-authority-table",
        "fixture-provider-authority",
        "--output-root",
        str(review_root),
        "--execute",
    ]
    assert main(review_args) == 0
    assert provider_calls == 2

    reviewed_queue_path = review_root / "unitization-review-queue-reviewed.jsonl"
    reviewed_queue = [
        json.loads(line)
        for line in reviewed_queue_path.read_text().splitlines()
        if line
    ]
    sidecar_path = review_queue_v2_sidecar_path(reviewed_queue_path)
    sidecar = [
        json.loads(line) for line in sidecar_path.read_text().splitlines() if line
    ]
    # The sidecar is a projection of the same review work, and the run card
    # still commits only to the authenticated v1 outputs.
    verify_review_queue_v2_coverage(reviewed_queue, sidecar)
    assert {record["schema_version"] for record in sidecar} == {
        "legalforecast.unitization_review_queue.v2"
    }
    structural_card_payload = json.loads(
        (review_root / "run-cards" / "llm-review-stage-a.json").read_text()
    )
    # Positive control first: the v1 queue is recorded in exactly the form the
    # negative assertion below tests for, so a future change to how output paths
    # or commitments are serialized fails here instead of making the exclusion
    # vacuously true.
    assert str(reviewed_queue_path) in structural_card_payload["output_paths"]
    assert str(sidecar_path) not in structural_card_payload["output_paths"]
    output_commitments = structural_card_payload["output_commitments"]
    review_queue_digest = (
        f"sha256:{hashlib.sha256(reviewed_queue_path.read_bytes()).hexdigest()}"
    )
    assert output_commitments["review_queue"] == {
        "path": str(reviewed_queue_path.resolve()),
        "sha256": review_queue_digest,
    }
    assert "review_queue_v2" not in output_commitments
    sidecar_digest = f"sha256:{hashlib.sha256(sidecar_path.read_bytes()).hexdigest()}"
    assert sidecar_digest not in {
        commitment["sha256"] for commitment in output_commitments.values()
    }

    provider_calls_before_bad_journal = provider_calls
    bad_journal_args = list(review_args)
    bad_journal_args[bad_journal_args.index(str(provider_journal))] = str(
        tmp_path / "different-output-root" / "provider-attempts.sqlite3"
    )
    bad_journal_args[bad_journal_args.index(str(review_root))] = str(
        tmp_path / "different-output-root"
    )
    assert main(bad_journal_args) == 2
    assert provider_calls == provider_calls_before_bad_journal

    provider_calls_before_mutated_caps = provider_calls
    mutated_caps = tmp_path / "mutated-provider-caps.json"
    mutated_caps.write_text(caps_path.read_text() + "\n", encoding="utf-8")
    mutated_caps_args = list(review_args)
    mutated_caps_args[mutated_caps_args.index(str(caps_path))] = str(mutated_caps)
    mutated_caps_args[mutated_caps_args.index(str(review_root))] = str(
        tmp_path / "mutated-caps-output"
    )
    assert main(mutated_caps_args) == 2
    assert provider_calls == provider_calls_before_mutated_caps

    provider_calls_before_wrong_cycle = provider_calls
    wrong_cycle_caps = tmp_path / "wrong-cycle-provider-caps.json"
    wrong_cycle_payload = json.loads(caps_path.read_text())
    wrong_cycle_payload["cycle_id"] = "different-cycle"
    _write_json(wrong_cycle_caps, wrong_cycle_payload)
    wrong_cycle_args = list(review_args)
    wrong_cycle_args[wrong_cycle_args.index(str(caps_path))] = str(wrong_cycle_caps)
    wrong_cycle_args[wrong_cycle_args.index(str(review_root))] = str(
        tmp_path / "wrong-cycle-output"
    )
    assert main(wrong_cycle_args) == 2
    assert provider_calls == provider_calls_before_wrong_cycle

    adjudications_path = tmp_path / "unitization-adjudications.jsonl"
    _write_jsonl(
        adjudications_path,
        [
            {
                "schema_version": "legalforecast.unitization_adjudication.v1",
                "adjudication_id": "adj-cand-1",
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "review_ids": ["cand-1:unit-1:stage-a-review"],
                "source_unit_ids": ["unit-1"],
                "disposition": "ACCEPT",
                "finalized_units": [],
                "adjudicator_id": "john-hughes",
                "adjudication_notes": "Accepted after blinded review.",
            }
        ],
    )
    apply_root = tmp_path / "apply-review-output"
    assert (
        main(
            [
                "acquisition",
                "apply-unitization-review",
                "--prediction-units",
                str(output_root / "prediction-units.jsonl"),
                "--llm-unitization-run-card",
                str(unitization_card),
                "--llm-review-stage-a-run-card",
                str(review_root / "run-cards" / "llm-review-stage-a.json"),
                "--provider-cycle-caps",
                str(caps_path),
                "--provider-journal",
                str(provider_journal),
                "--unitization-review-queue",
                str(review_root / "unitization-review-queue-reviewed.jsonl"),
                "--adjudications",
                str(adjudications_path),
                "--output-root",
                str(apply_root),
                "--execute",
            ]
        )
        == 0
    )
    finalized_units_path = apply_root / "finalized-prediction-units.jsonl"
    provider_chain_args = [
        "--llm-unitization-run-card",
        str(unitization_card),
        "--llm-review-stage-a-run-card",
        str(review_root / "run-cards" / "llm-review-stage-a.json"),
        "--unitization-review-run-card",
        str(apply_root / "run-cards" / "apply-unitization-review.json"),
        "--provider-journal",
        str(provider_journal),
        "--provider-authority-table",
        "fixture-provider-authority",
    ]

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(finalized_units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(_provider_caps_path(tmp_path)),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )
    assert provider_calls == 3
    with sqlite3.connect(provider_journal) as connection:
        journal_accounts = connection.execute(
            "SELECT stage, account FROM provider_attempts ORDER BY stage"
        ).fetchall()
        ledger_accounts = connection.execute(
            "SELECT provider, account FROM provider_ledgers"
        ).fetchall()
    assert journal_accounts == [
        ("llm-label", "primary"),
        ("llm-review-stage-a", "primary"),
        ("llm-unitize", "primary"),
    ]
    assert ledger_accounts == [("openai", "primary")]

    provider_calls_before_bad_label_chain = provider_calls
    bad_label_chain_args = list(provider_chain_args)
    bad_label_chain_args[bad_label_chain_args.index(str(provider_journal))] = str(
        tmp_path / "label-different-root" / "provider-attempts.sqlite3"
    )
    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(finalized_units_path),
                *stage_b_args,
                "--output-root",
                str(tmp_path / "label-different-root"),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *bad_label_chain_args,
                "--execute",
            ]
        )
        == 2
    )
    assert provider_calls == provider_calls_before_bad_label_chain

    labels = _read_jsonl(output_root / "labels.jsonl")
    assert labels[0]["unit_id"] == "unit-1"
    assert labels[0]["fully_dismissed"] is True
    assert labels[0]["first_written_disposition_date"] == "2026-06-30"
    label_audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert label_audit["consensus_policy"] == "unanimous"
    assert label_audit["status"] == "succeeded"
    assert label_audit["human_verified"] is False
    assert label_audit["model_outputs"][0]["model_key"] == "openai:gpt-test"
    commitments = label_audit["decision_text_commitment"]
    assert commitments["decision_texts_sha256"] == _sha256_path(
        tmp_path / "stage-b" / "decision-texts.jsonl"
    )
    assert commitments["finalized_prediction_units_sha256"] == _sha256_path(
        finalized_units_path
    )
    assert commitments["finalized_unit_envelope_sha256"].startswith("sha256:")
    prompt_sha256 = label_audit["model_outputs"][0]["provider_prompt_sha256"]
    with sqlite3.connect(output_root / "provider-attempts.sqlite3") as connection:
        prompt_text, journal_prompt_sha256, reconstructed = connection.execute(
            "SELECT prompt_text, prompt_sha256, reconstructed_result_json "
            "FROM provider_attempts WHERE stage = 'llm-label'"
        ).fetchone()
    prompt = json.loads(prompt_text)
    assert prompt["decision_text"]["commitment"] == commitments
    assert prompt["decision_text"]["text"] == (
        "The motion to dismiss Count I is granted without leave to amend."
    )
    assert prompt_sha256 == "sha256:" + journal_prompt_sha256
    assert json.loads(reconstructed)["decision_text_commitment"] == commitments
    label_run_card = json.loads(
        (output_root / "run-cards" / "llm-label.json").read_text()
    )
    structural_run_card = json.loads(
        (review_root / "run-cards" / "llm-review-stage-a.json").read_text()
    )
    for card, stage in (
        (structural_run_card, "llm-review-stage-a"),
        (label_run_card, "llm-label"),
    ):
        assert card["provider_chain"] == {
            "schema_version": "legalforecast.provider_attempt_journal.v3",
            "cycle_id": "test-cycle",
            "provider_cycle_caps_sha256": _sha256_path(caps_path),
            "provider_journal": str(provider_journal.resolve()),
            "stage_attempts": {
                "stage": stage,
                "call_count": 1,
                "attempt_count": 1,
                "attempts_sha256": card["provider_chain"]["stage_attempts"][
                    "attempts_sha256"
                ],
                **(
                    {"provider_attempt_namespace": "claim-ontology-v4"}
                    if stage == "llm-review-stage-a"
                    else {}
                ),
            },
        }
        assert card["provider_chain"]["stage_attempts"]["attempts_sha256"].startswith(
            "sha256:"
        )
    assert label_run_card["stage_a_lineage"]["llm_review_stage_a_run_card"] == (
        cli._stage_a_file_commitment(
            review_root / "run-cards" / "llm-review-stage-a.json"
        )
    )
    assert label_run_card["decision_text_commitments"] == {
        "decision_texts_sha256": commitments["decision_texts_sha256"],
        "decision_texts_manifest_sha256": commitments["decision_texts_manifest_sha256"],
        "decision_texts_run_card_sha256": commitments["decision_texts_run_card_sha256"],
        "finalized_prediction_units_sha256": commitments[
            "finalized_prediction_units_sha256"
        ],
    }
    assert label_audit["label_audit_gate"]["status"] == "awaiting_cycle_level_plan"
    assert _read_jsonl(output_root / "lawyer-review-queue.jsonl") == []

    lineage = cli._verify_stage_a_unitization_run_card(
        unitization_card,
        expected_prediction_units_path=output_root / "prediction-units.jsonl",
        expected_review_queue_path=output_root / "unitization-review-queue.jsonl",
        expected_audit_path=output_root / "llm-unitization-audit.jsonl",
    )
    label_run_card_path = output_root / "run-cards" / "llm-label.json"
    cli._verify_llm_label_run_card(
        label_run_card_path,
        lineage=lineage,
        selection_path=selection_path,
        parser_manifest_path=parser_path,
        decision_texts_path=tmp_path / "stage-b" / "decision-texts.jsonl",
        decision_texts_manifest_path=(
            tmp_path / "stage-b" / "decision-texts-manifest.json"
        ),
        decision_texts_run_card_path=(
            tmp_path / "stage-b" / "build-decision-texts.json"
        ),
        finalized_prediction_units_path=finalized_units_path,
        llm_unitization_run_card_path=unitization_card,
        llm_review_stage_a_run_card_path=(
            review_root / "run-cards" / "llm-review-stage-a.json"
        ),
        unitization_review_run_card_path=(
            apply_root / "run-cards" / "apply-unitization-review.json"
        ),
        model_registry_path=registry_path,
        evaluated_model_registry_path=_evaluated_registry_path(tmp_path),
        provider_cycle_caps_path=caps_path,
        labels_path=output_root / "labels.jsonl",
        audit_path=output_root / "llm-label-audit.jsonl",
    )
    substituted_labels = _read_jsonl(output_root / "labels.jsonl")
    substituted_labels[0]["fully_dismissed"] = False
    _write_jsonl(output_root / "labels.jsonl", substituted_labels)
    label_run_card["output_commitments"]["labels"] = cli._stage_a_file_commitment(
        output_root / "labels.jsonl"
    )
    _write_json(label_run_card_path, label_run_card)
    with pytest.raises(cli.CommandError, match="selected labels do not reproduce"):
        cli._verify_llm_label_run_card(
            label_run_card_path,
            lineage=lineage,
            selection_path=selection_path,
            parser_manifest_path=parser_path,
            decision_texts_path=tmp_path / "stage-b" / "decision-texts.jsonl",
            decision_texts_manifest_path=(
                tmp_path / "stage-b" / "decision-texts-manifest.json"
            ),
            decision_texts_run_card_path=(
                tmp_path / "stage-b" / "build-decision-texts.json"
            ),
            finalized_prediction_units_path=finalized_units_path,
            llm_unitization_run_card_path=unitization_card,
            llm_review_stage_a_run_card_path=(
                review_root / "run-cards" / "llm-review-stage-a.json"
            ),
            unitization_review_run_card_path=(
                apply_root / "run-cards" / "apply-unitization-review.json"
            ),
            model_registry_path=registry_path,
            evaluated_model_registry_path=_evaluated_registry_path(tmp_path),
            provider_cycle_caps_path=caps_path,
            labels_path=output_root / "labels.jsonl",
            audit_path=output_root / "llm-label-audit.jsonl",
        )

    flags_path = review_root / "stage-a-structural-flags.jsonl"
    fabricated_flag = {
        "schema_version": "legalforecast.stage_a_structural_flag.v1",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "flag_sha256": "sha256:fabricated",
    }
    _write_jsonl(flags_path, [fabricated_flag])
    structural_card_path = review_root / "run-cards" / "llm-review-stage-a.json"
    structural_run_card["output_commitments"]["structural_flags"] = (
        cli._stage_a_file_commitment(flags_path)
    )
    _write_json(structural_card_path, structural_run_card)
    with pytest.raises(cli.CommandError, match="flags do not reproduce"):
        cli._verify_stage_a_review_run_card(
            structural_card_path,
            lineage=lineage,
            llm_unitization_run_card_path=unitization_card,
            expected_review_queue_path=(
                review_root / "unitization-review-queue-reviewed.jsonl"
            ),
            expected_structural_flags_path=flags_path,
            expected_audit_path=review_root / "stage-a-structural-review-audit.jsonl",
            expected_registry_path=registry_path,
            expected_model_key="openai:gpt-test",
        )


def test_executed_llm_unitize_requires_authenticated_lineage_before_provider(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("complaint", "complaint.md")])
    _write_json(registry_path, [_registry_record()])
    provider_calls = 0

    def forbidden_provider_call(*args: Any, **kwargs: Any) -> SolverResponse:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", forbidden_provider_call)
    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(_provider_caps_path(tmp_path)),
                "--provider-journal",
                str(tmp_path / "shared-provider-attempts.sqlite3"),
                "--provider-attempt-namespace",
                "claim-ontology-v5",
                "--output-root",
                str(tmp_path / "out"),
                "--execute",
            ]
        )
        == 2
    )
    assert provider_calls == 0
    assert "authenticated Stage A lineage requires" in capsys.readouterr().err


def test_stage_a_packet_authority_rejects_self_consistent_forged_output(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        _journaled_fixture_completion(_fake_completion),
    )
    caps_path = _provider_caps_path(tmp_path)
    provider_journal_path = output_root / "provider-attempts.sqlite3"
    lineage_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=provider_journal_path,
    )

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *lineage_args,
                "--execute",
            ]
        )
        == 0
    )

    units_path = output_root / "prediction-units.jsonl"
    forged_units = _read_jsonl(units_path)
    forged_units[0]["prediction_units"][0]["claim_name"] = "Forged claim"
    _write_jsonl(units_path, forged_units)
    unitize_card_path = output_root / "run-cards/llm-unitize.json"
    unitize_card = json.loads(unitize_card_path.read_text(encoding="utf-8"))
    unitize_card["output_commitments"]["prediction_units"] = (
        cli._materializer_file_commitment(units_path)
    )
    _write_json(unitize_card_path, unitize_card)

    with raises(CommandError, match="do not reproduce from journal"):
        cli._verify_stage_a_unitization_run_card(
            unitize_card_path,
            expected_prediction_units_path=units_path,
            expected_review_queue_path=(output_root / "unitization-review-queue.jsonl"),
            expected_audit_path=output_root / "llm-unitization-audit.jsonl",
        )


def test_acquisition_llm_label_persists_lawyer_review_queue_with_partial_success(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "Count I is dismissed. Count II is dismissed.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    _prediction_unit_record("unit-auto", "Count I"),
                    _prediction_unit_record("unit-review", "Count II"),
                ],
            }
        ],
    )
    _write_json(
        registry_path,
        [
            _registry_record(model_id="gpt-a", display_name="GPT A"),
            _registry_record(model_id="gpt-b", display_name="GPT B"),
            _registry_record(model_id="gpt-c", display_name="GPT C"),
        ],
    )

    def partial_review_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        entry = args[0]
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-auto",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "Count I is dismissed.",
                            "labeler_confidence": 0.93,
                        },
                        {
                            "unit_id": "unit-review",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "Count II is dismissed.",
                            "labeler_confidence": 0.7,
                        },
                    ],
                    "missing_unit_flags": [],
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": entry.model_id},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", partial_review_completion)
    _rewrite_as_finalized(units_path)
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    provider_chain_args = _stub_authenticated_finalized_provider_chain(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
        finalized_units_path=units_path,
    )

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-a",
                "--model-key",
                "openai:gpt-b",
                "--model-key",
                "openai:gpt-c",
                "--provider-cycle-caps",
                str(caps_path),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )

    labels = _read_jsonl(output_root / "labels.jsonl")
    assert [label["unit_id"] for label in labels] == ["unit-auto"]
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "adjudication_pending"
    assert audit["human_verified"] is False
    assert audit["pending_adjudication_unit_ids"] == ["unit-review"]
    assert audit["pending_adjudication_count"] == 1
    assert audit["label_count"] == 1
    assert audit["unit_count"] == 2
    assert audit["label_audit_gate"]["status"] == "awaiting_cycle_level_plan"

    queue = _read_jsonl(output_root / "lawyer-review-queue.jsonl")
    assert len(queue) == 1
    queue_by_unit = {record["unit_id"]: record for record in queue}
    assert queue_by_unit["unit-review"]["status"] == "pending_adjudication"
    assert queue_by_unit["unit-review"]["case_id"] == "case-1"
    assert queue_by_unit["unit-review"]["route_reason"] == "low_confidence"
    assert queue_by_unit["unit-review"]["packet"]["review_reason"] == ("low_confidence")
    assert "unit-auto" not in queue_by_unit


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("artifact_date", "decision text date mismatch"),
        ("restricted", "sealed/private/restricted"),
        ("duplicate", "duplicate decision text candidate"),
        ("fixture_parser", "pinned live Mistral revision"),
        ("source_sha", "decision source hash mismatch"),
        ("source_bytes", "decision source byte-count mismatch"),
        ("quality_flags", "decision parser record has quality flags"),
        ("finalized_case", "finalized prediction-units case mismatch"),
        ("finalized_provenance", "automatic finalized-unit provenance"),
        ("markdown_drift", "extracted text hash mismatch"),
        ("manifest_drift", "manifest eligibility anchor drift"),
    ],
)
def test_llm_label_rejects_unauthenticated_decision_text_before_provider_call(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mutation: str,
    message: str,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    decision_path = markdown_root / "cand-1" / "decision.md"
    _write_markdown(decision_path, "Count I is dismissed.")
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [_prediction_unit_record("unit-1", "Count I")],
            }
        ],
    )
    _rewrite_as_finalized(units_path)
    _write_json(registry_path, [_registry_record()])
    stage_root = tmp_path / "stage-b"
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=stage_root,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    decision_texts_path = stage_root / "decision-texts.jsonl"
    manifest_path = stage_root / "decision-texts-manifest.json"
    if mutation == "artifact_date":
        rows = _read_jsonl(decision_texts_path)
        rows[0]["entered_date"] = "2026-07-01"
        _write_jsonl(decision_texts_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "restricted":
        rows = _read_jsonl(decision_texts_path)
        rows[0]["clearance"]["restriction_status"] = "sealed"
        _write_jsonl(decision_texts_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "duplicate":
        rows = _read_jsonl(decision_texts_path)
        rows.append(dict(rows[0]))
        _write_jsonl(decision_texts_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "fixture_parser":
        rows = _read_jsonl(parser_path)
        rows[0]["parser_config"]["fixture_markdown"] = True
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "source_sha":
        rows = _read_jsonl(parser_path)
        rows[0]["source_sha256"] = "2" * 64
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "source_bytes":
        rows = _read_jsonl(parser_path)
        rows[0]["source_byte_count"] = 43
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "quality_flags":
        rows = _read_jsonl(parser_path)
        rows[0]["quality_flags"] = ["manual_review_required"]
        _write_jsonl(parser_path, rows)
        _reseal_stage_b_bundle(stage_root, selection_path, parser_path)
    elif mutation == "finalized_case":
        rows = _read_jsonl(units_path)
        rows[0]["case_id"] = "wrong-case"
        _write_jsonl(units_path, rows)
    elif mutation == "finalized_provenance":
        rows = _read_jsonl(units_path)
        rows[0]["prediction_units"][0]["source_unit_sha256s"] = ["3" * 64]
        _write_jsonl(units_path, rows)
    elif mutation == "markdown_drift":
        decision_path.write_text("Count I survives.", encoding="utf-8")
    elif mutation == "manifest_drift":
        manifest = json.loads(manifest_path.read_text())
        manifest["eligibility_anchor"] = "2026-07-01"
        _write_json(manifest_path, manifest)
    else:  # pragma: no cover - parametrization is exhaustive
        raise AssertionError(mutation)

    provider_calls = 0

    def forbidden_provider_call(*args: Any, **kwargs: Any) -> SolverResponse:
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider must not be called")

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", forbidden_provider_call)
    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(_provider_caps_path(tmp_path)),
                "--execute",
            ]
        )
        == 2
    )
    assert message in capsys.readouterr().err
    assert provider_calls == 0
    assert not (output_root / "provider-attempts.sqlite3").exists()
    assert not (output_root / "labels.jsonl").exists()


def test_acquisition_apply_lawyer_review_uses_verified_bytes_after_source_replacement(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    labels_path = tmp_path / "labels.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    decision_texts_path = _write_decision_texts(tmp_path / "decision-texts.jsonl")
    decision_artifact_args = _stub_downstream_decision_artifact(
        monkeypatch,
        decision_texts_path,
        replace_after_verification=True,
    )
    llm_label_audit_path = tmp_path / "llm-label-audit.jsonl"
    auto_label = _label_record(
        "unit-auto",
        dismissed=False,
        excerpt="Count I survives.",
    )
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    _write_jsonl(labels_path, [auto_label])
    _write_jsonl(
        llm_label_audit_path,
        [
            _llm_label_audit_record(
                auto_label=auto_label,
                review_label=adjudicated_label,
            )
        ],
    )
    _write_jsonl(
        adjudications_path,
        [
            _adjudication_record(
                "cand-1:unit-auto:label-audit",
                "unit-auto",
                auto_label,
            ),
            _adjudication_record(
                "cand-1:unit-review:lawyer-adjudication",
                "unit-review",
                adjudicated_label,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "apply-lawyer-review",
                "--labels",
                str(labels_path),
                "--adjudications",
                str(adjudications_path),
                "--decision-texts",
                str(decision_texts_path),
                *decision_artifact_args,
                "--llm-label-audit",
                str(llm_label_audit_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    labels_by_unit = {
        record["unit_id"]: record
        for record in _read_jsonl(output_root / "labels-adjudicated.jsonl")
    }
    assert sorted(labels_by_unit) == ["unit-auto", "unit-review"]
    assert labels_by_unit["unit-review"]["fully_dismissed"] is True

    audit_records = _read_jsonl(output_root / "lawyer-review-resume-audit.jsonl")
    audit = audit_records[0]
    assert audit["stage"] == "lawyer-review-resume"
    assert audit["status"] == "succeeded"
    assert audit["human_verified"] is True
    assert audit["adjudicated_review"]["disagreement_state"] == "single_reviewer"
    gate = next(
        record for record in audit_records if record["stage"] == "label-audit-gate"
    )
    assert gate["status"] == "passed"
    assert gate["audited_label_error_rate"] == 0.0
    assert gate["sample_unit_ids"] == ["unit-auto"]
    assert gate["label_audit_gate"]["audit_summary"]["passes_acceptance"] is True


def test_apply_adjudicated_reviews_rejects_nonverbatim_excerpt() -> None:
    # A lawyer-adjudicated label whose citation excerpt is not present verbatim in
    # the first written disposition must be rejected, exactly like an LLM Stage B
    # finding excerpt, so no published label ships an uncheckable citation.
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    adjudication = _adjudication_record(
        "cand-1:unit-review:lawyer-adjudication",
        "unit-review",
        adjudicated_label,
    )
    decision_texts = {
        "decision": llm_pipeline.StageBDecisionText(
            document_id="decision",
            entered_date="2026-05-18",
            text="The Court denies the motion in full. No count was dismissed.",
        )
    }

    with raises(ValueError, match="must appear verbatim"):
        llm_pipeline.apply_adjudicated_reviews(
            label_records=[adjudicated_label],
            adjudication_records=[adjudication],
            decision_texts=decision_texts,
        )


def test_apply_adjudicated_reviews_rejects_label_without_excerpt() -> None:
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt=None,
    )
    adjudication = _adjudication_record(
        "cand-1:unit-review:lawyer-adjudication",
        "unit-review",
        adjudicated_label,
    )
    decision_texts = {
        "decision": llm_pipeline.StageBDecisionText(
            document_id="decision",
            entered_date="2026-05-18",
            text="Count II is dismissed.",
        )
    }

    with raises(ValueError, match="at least one non-empty supporting excerpt"):
        llm_pipeline.apply_adjudicated_reviews(
            label_records=[adjudicated_label],
            adjudication_records=[adjudication],
            decision_texts=decision_texts,
        )


def test_apply_adjudicated_reviews_rejects_uncited_document() -> None:
    # Fail-closed: an adjudicated citation whose document has no decision text to
    # verify against is an error, not a silent skip.
    adjudicated_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    adjudication = _adjudication_record(
        "cand-1:unit-review:lawyer-adjudication",
        "unit-review",
        adjudicated_label,
    )

    with raises(ValueError, match="no decision text"):
        llm_pipeline.apply_adjudicated_reviews(
            label_records=[adjudicated_label],
            adjudication_records=[adjudication],
            decision_texts={},
        )


def test_acquisition_apply_lawyer_review_fails_without_audited_auto_label(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    labels_path = tmp_path / "labels.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    decision_texts_path = _write_decision_texts(tmp_path / "decision-texts.jsonl")
    decision_artifact_args = _stub_downstream_decision_artifact(
        monkeypatch, decision_texts_path
    )
    llm_label_audit_path = tmp_path / "llm-label-audit.jsonl"
    auto_label = _label_record(
        "unit-auto",
        dismissed=False,
        excerpt="Count I survives.",
    )
    review_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    _write_jsonl(labels_path, [auto_label])
    _write_jsonl(
        llm_label_audit_path,
        [_llm_label_audit_record(auto_label=auto_label, review_label=review_label)],
    )
    _write_jsonl(
        adjudications_path,
        [
            _adjudication_record(
                "cand-1:unit-review:lawyer-adjudication",
                "unit-review",
                review_label,
            )
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "apply-lawyer-review",
                "--labels",
                str(labels_path),
                "--adjudications",
                str(adjudications_path),
                "--decision-texts",
                str(decision_texts_path),
                *decision_artifact_args,
                "--llm-label-audit",
                str(llm_label_audit_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert not (output_root / "labels-adjudicated.jsonl").exists()


def test_acquisition_apply_lawyer_review_fails_closed_on_audit_error(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    labels_path = tmp_path / "labels.jsonl"
    adjudications_path = tmp_path / "adjudications.jsonl"
    decision_texts_path = _write_decision_texts(tmp_path / "decision-texts.jsonl")
    decision_artifact_args = _stub_downstream_decision_artifact(
        monkeypatch, decision_texts_path
    )
    llm_label_audit_path = tmp_path / "llm-label-audit.jsonl"
    auto_label = _label_record(
        "unit-auto",
        dismissed=False,
        excerpt="Count I survives.",
    )
    conflicting_audit_label = _label_record(
        "unit-auto",
        dismissed=True,
        excerpt="Count I is dismissed.",
    )
    review_label = _label_record(
        "unit-review",
        dismissed=True,
        excerpt="Count II is dismissed.",
    )
    _write_jsonl(labels_path, [auto_label])
    _write_jsonl(
        llm_label_audit_path,
        [_llm_label_audit_record(auto_label=auto_label, review_label=review_label)],
    )
    _write_jsonl(
        adjudications_path,
        [
            _adjudication_record(
                "cand-1:unit-auto:label-audit",
                "unit-auto",
                conflicting_audit_label,
            ),
            _adjudication_record(
                "cand-1:unit-review:lawyer-adjudication",
                "unit-review",
                review_label,
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "apply-lawyer-review",
                "--labels",
                str(labels_path),
                "--adjudications",
                str(adjudications_path),
                "--decision-texts",
                str(decision_texts_path),
                *decision_artifact_args,
                "--llm-label-audit",
                str(llm_label_audit_path),
                "--human-blind-disagreement-rate",
                "0.05",
                "--audit-sample-size",
                "1",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    assert not (output_root / "labels-adjudicated.jsonl").exists()


def _v5_source_citations() -> list[JsonRecord]:
    return [
        {
            "source_document_id": "complaint",
            "start_line": 1,
            "line_count": 1,
        },
        {
            "source_document_id": "mtd",
            "start_line": 1,
            "line_count": 1,
        },
    ]


def test_acquisition_llm_unitize_accepts_singleton_string_list_fields(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
            _parser_record("decision", "decision.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": "Issuer",
                            "source_citations": _v5_source_citations(),
                            "challenged_by_motion": True,
                            "scope": {"kind": "entire_claim"},
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                        }
                    ]
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        _journaled_fixture_completion(fake_completion),
    )

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert [citation["document_id"] for citation in unit["source_citations"]] == [
        "complaint",
        "mtd",
    ]
    assert unit["defendant_group"] == "Issuer"


def test_acquisition_llm_unitize_accepts_top_level_seed_array(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_names": ["Issuer"],
                        "source_citations": _v5_source_citations(),
                        "challenged_by_motion": True,
                        "scope": {"kind": "entire_claim"},
                        "unit_confidence": 0.92,
                        "grouping": "individual",
                    }
                ]
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        _journaled_fixture_completion(fake_completion),
    )

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["unit_id"] == "unit-1"


def test_acquisition_llm_unitize_rejects_missing_required_unit_fields(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def incomplete_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": ["Issuer"],
                            "source_citations": _v5_source_citations(),
                            "scope": {"kind": "entire_claim"},
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                        }
                    ]
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        _journaled_fixture_completion(incomplete_completion),
    )

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "prediction-units.jsonl") == []
    audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert "challenged_by_motion" in audit["error_message"]
    assert audit["exclusion_ledger_entries"][0]["stage"] == "labeling"


def test_acquisition_llm_unitize_accepts_first_balanced_json_object(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    payload = {
        "unit_seeds": [
            {
                "unit_id": "unit-1",
                "count": "Count I",
                "claim_name": "Section 10(b)",
                "defendant_names": ["Issuer"],
                "source_citations": _v5_source_citations(),
                "challenged_by_motion": True,
                "scope": {"kind": "entire_claim"},
                "unit_confidence": 0.92,
                "grouping": "individual",
            }
        ]
    }

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=f'{json.dumps(payload)}\n{{"debug": true}}',
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        _journaled_fixture_completion(fake_completion),
    )

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["unit_id"] == "unit-1"


def test_llm_label_excerpt_coercion_uses_verbatim_near_match() -> None:
    decision_text = (
        "Defendants' Motion as to Claim One is GRANTED, and the Claim is "
        "DISMISSED WITH LEAVE TO AMEND."
    )

    coerce_excerpt = cast(Any, llm_pipeline)._coerced_excerpt
    excerpt = coerce_excerpt(
        decision_text,
        "Defendants Motion as to Claim One is granted and the claim is dismissed "
        "with leave to amend.",
    )

    assert excerpt == decision_text


def test_labeling_prompt_explains_not_addressed_resolution() -> None:
    prompt = json.loads(
        cast(Any, llm_pipeline)._labeling_prompt(
            _selection_record(),
            llm_pipeline.StageBDecisionText(
                document_id="decision",
                entered_date="2026-05-18",
                text="The motion is granted as to Count I.",
            ),
            (_prediction_unit(),),
            decision_text_commitment={
                "decision_texts_sha256": "sha256:" + "a" * 64,
            },
        )
    )

    rules = "\n".join(prompt["rules"])

    assert "not_addressed_by_this_disposition" in rules
    assert "amendment_signal not_applicable" in rules
    assert "do not infer an outcome from silence" in rules


def test_labeling_failure_ledger_uses_specific_reason_codes() -> None:
    response = SolverResponse(
        raw_output='{"unit_findings": "bad"}',
        input_tokens=1,
        output_tokens=1,
        estimated_cost=0.01,
    )
    cases = [
        (
            llm_pipeline.LlmResponseValidationError(
                "unit_findings must be a list",
                response=response,
            ),
            "parse_error",
        ),
        (
            llm_pipeline.LlmPipelineError(
                "LLM labels require lawyer adjudication for units: ['unit-1']"
            ),
            "adjudication_pending",
        ),
        (
            llm_pipeline.LlmPipelineError("LLM judges were not unanimous for unit-1"),
            "judge_disagreement",
        ),
        (
            llm_pipeline.LlmPipelineError(
                "LLM-only labels include ambiguous units: ['unit-1']"
            ),
            "ambiguous",
        ),
    ]

    entries_for = cast(Any, llm_pipeline)._labeling_exclusion_entries

    for error, reason in cases:
        [entry] = entries_for(_selection_record(), error)
        assert entry["primary_exclusion_reason"] == reason
        assert entry["reason"] == reason


def test_acquisition_llm_unitize_failure_audit_keeps_model_accounting(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])
    caps_path = _provider_caps_path(tmp_path)
    stage_a_args = _stub_authenticated_stage_a_lineage(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
    )

    def invalid_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": ["Issuer"],
                            "source_citations": {"document_id": "mtd"},
                            "challenged_by_motion": True,
                            "scope": {"kind": "entire_claim"},
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                        }
                    ]
                }
            ),
            input_tokens=123,
            output_tokens=45,
            estimated_cost=0.12,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(
        llm_pipeline,
        "complete_live_prompt",
        _journaled_fixture_completion(invalid_completion),
    )

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--provider-cycle-caps",
                str(caps_path),
                *stage_a_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "prediction-units.jsonl") == []
    audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["estimated_cost"] == 0.12
    assert audit["input_tokens"] == 123
    assert audit["output_tokens"] == 45
    assert str(audit["raw_output_sha256"]).startswith("sha256:")
    assert audit["metadata"]["model_id"] == "gpt-test"


def test_acquisition_llm_label_failure_audit_keeps_model_accounting(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "decision.md", "Count I is dismissed.")
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_group": "Issuer",
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.9,
                        "source_citations": [{"document_id": "mtd"}],
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": None,
                        "uncertainty_notes": None,
                    }
                ],
            }
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def invalid_label_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-1",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "The motion is granted.",
                            "labeler_confidence": 0.91,
                        }
                    ],
                    "missing_unit_flags": [],
                }
            ),
            input_tokens=234,
            output_tokens=56,
            estimated_cost=0.23,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", invalid_label_completion)
    _rewrite_as_finalized(units_path)
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    provider_chain_args = _stub_authenticated_finalized_provider_chain(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
        finalized_units_path=units_path,
    )

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--provider-cycle-caps",
                str(caps_path),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "labels.jsonl") == []
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["estimated_cost"] == 0.23
    assert audit["input_tokens"] == 234
    assert audit["output_tokens"] == 56
    assert str(audit["raw_output_sha256"]).startswith("sha256:")
    assert audit["metadata"]["model_id"] == "gpt-test"
    assert audit["model_outputs"] == [
        {
            "status": "validation_failed",
            "model_key": "openai:gpt-test",
            "provider_prompt_sha256": audit["model_outputs"][0][
                "provider_prompt_sha256"
            ],
            "input_tokens": 234,
            "output_tokens": 56,
            "estimated_cost": 0.23,
            "raw_output_sha256": audit["raw_output_sha256"],
            "metadata": {"provider": "openai", "model_id": "gpt-test"},
            "error_type": "LlmResponseValidationError",
            "error_message": audit["error_message"],
        }
    ]
    provider_chain = json.loads(
        (output_root / "run-cards" / "llm-label.json").read_text(encoding="utf-8")
    )["provider_chain"]
    assert provider_chain["stage_attempts"]["call_count"] == 1
    assert provider_chain["stage_attempts"]["attempt_count"] == 1


def test_acquisition_llm_label_missing_unit_flags_gate_frozen_unit_workflow(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "Count I is dismissed. The court also dismisses Count II.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_group": "Issuer",
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.9,
                        "source_citations": [{"document_id": "mtd"}],
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": None,
                        "uncertainty_notes": None,
                    }
                ],
            }
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def missing_unit_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        response = SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-1",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "Count I is dismissed.",
                            "labeler_confidence": 0.91,
                        }
                    ],
                    "missing_unit_flags": [
                        {
                            "missing_unit_description": (
                                "Decision resolved Count II, which was absent from "
                                "frozen Stage A units."
                            ),
                            "supporting_excerpt": (
                                "The court also dismisses Count II."
                            ),
                        }
                    ],
                }
            ),
            input_tokens=345,
            output_tokens=67,
            estimated_cost=0.34,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )
        return _settle_fixture_unitization_attempt(response, kwargs)

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", missing_unit_completion)
    _rewrite_as_finalized(units_path)
    stage_b_args = _write_authenticated_stage_b_inputs(
        root=tmp_path / "stage-b",
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
    )
    caps_path = _provider_caps_path(tmp_path)
    provider_chain_args = _stub_authenticated_finalized_provider_chain(
        monkeypatch,
        selection_path=selection_path,
        parser_path=parser_path,
        markdown_root=markdown_root,
        registry_path=registry_path,
        caps_path=caps_path,
        provider_journal_path=output_root / "provider-attempts.sqlite3",
        finalized_units_path=units_path,
    )

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                *stage_b_args,
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--evaluated-model-registry",
                str(_evaluated_registry_path(tmp_path)),
                "--provider-cycle-caps",
                str(caps_path),
                *provider_chain_args,
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "labels.jsonl") == []
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["error_type"] == "FrozenUnitWorkflowRequiredError"
    assert audit["requires_frozen_unit_workflow"] is True
    assert audit["missing_unit_flag_count"] == 1
    assert audit["frozen_unit_excluded_count"] == 1
    assert audit["frozen_unit_repaired_count"] == 0
    assert audit["frozen_unit_workflow"]["frozen_unit_status"] == "excluded"
    assert audit["estimated_cost"] == 0.34
    [entry] = audit["exclusion_ledger_entries"]
    assert entry["stage"] == "unitization"
    assert entry["primary_exclusion_reason"] == "unit_missing_from_stage_a"


def _fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
    prompt = cast(str, args[1])
    if "Construct frozen Stage A" in prompt:
        raw_output = {
            "unit_seeds": [
                {
                    "unit_id": "unit-1",
                    "count": "Count I",
                    "claim_name": "Section 10(b)",
                    "defendant_names": ["Issuer"],
                    "source_citations": [
                        {
                            "source_document_id": "complaint",
                            "start_line": 1,
                            "line_count": 1,
                        },
                        {
                            "source_document_id": "mtd",
                            "start_line": 1,
                            "line_count": 1,
                        },
                    ],
                    "challenged_by_motion": True,
                    "scope": {"kind": "entire_claim"},
                    "unit_confidence": 0.42,
                    "grouping": "individual",
                }
            ]
        }
    elif "Create Stage B outcome labels" in prompt:
        raw_output = {
            "unit_findings": [
                {
                    "unit_id": "unit-1",
                    "resolution": "fully_dismissed",
                    "amendment_signal": "express_denial_of_leave",
                    "supporting_excerpt": (
                        "motion to dismiss Count I is granted without leave"
                    ),
                    "labeler_confidence": 0.91,
                    "notes": "The court dismissed the only challenged claim.",
                }
            ],
            "missing_unit_flags": [],
        }
    elif "Review frozen Stage A units" in prompt:
        raw_output = {"structural_flags": []}
    else:
        raise AssertionError("unexpected prompt")
    return SolverResponse(
        raw_output=json.dumps(raw_output),
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.01,
        metadata={"provider": "openai", "model_id": "gpt-test"},
    )


def _selection_record() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "decision_date": "2026-06-30",
        "case_name": "Example v. Issuer",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "target_motion_entry_numbers": [5],
        "decision_entry_numbers": [16],
        "selected": True,
        "documents": [
            _selection_document("complaint", "complaint", 1, True, False),
            _selection_document("mtd", "motion_to_dismiss_notice", 5, True, False),
            _selection_document("decision", "decision", 16, False, True),
        ],
    }


def _selection_document(
    source_document_id: str,
    role: str,
    docket_entry_number: int,
    model_visible: bool,
    contains_target_outcome: bool,
) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "description": role,
        "model_visible": model_visible,
        "contains_target_outcome": contains_target_outcome,
        "is_sealed": False,
        "is_private": False,
        "restriction_status": "public",
    }


def _prediction_unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="unit-1",
        count="Count I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.9,
        source_citations=(
            SourceCitation(
                document_id="mtd",
                docket_entry_number=5,
                excerpt="Defendants move to dismiss Count I.",
            ),
        ),
    )


def _prediction_unit_record(unit_id: str, count: str) -> JsonRecord:
    return {
        "unit_id": unit_id,
        "count": count,
        "claim_name": "Section 10(b)",
        "defendant_group": "Issuer",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.9,
        "source_citations": [{"document_id": "mtd"}],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
    }


def _parser_record(source_document_id: str, filename: str) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "status": "succeeded",
        "markdown_path": f"cand-1/{filename}",
    }


def _registry_record(
    *,
    model_id: str = "gpt-test",
    display_name: str | None = None,
) -> JsonRecord:
    return {
        "provider": "openai",
        "model_id": model_id,
        "display_name": display_name or "GPT Test",
        "model_version_or_snapshot": model_id,
        "release_timestamp": "2026-05-18T00:00:00Z",
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-04-01",
        "temperature": 0,
        "top_p": 1,
        "max_output_tokens": 4096,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "controlled_docket_tool_only",
        "context_limit": 200000,
        "pricing_source": "fixture",
        "input_token_price": 1.0,
        "output_token_price": 2.0,
        "known_cutoff_publicity_caveats": [],
    }


def test_resume_and_lawyer_deserialization_preserve_false_label_resolution() -> None:
    labels = []
    for resolution in ("partial_dismissal_only", "survives_in_material_respect"):
        label = _label_record("unit-1", dismissed=False, excerpt="Count I survives.")
        label["unit_resolution"] = resolution
        labels.append(label)

    reconstructed_votes = [
        llm_pipeline._ensemble_label_vote(
            {
                "model_id": f"judge-{index}",
                "unit_id": "unit-1",
                "label": label,
                "confidence": 0.9,
                "rationale": "Fixture.",
                "raw_response_id": f"response-{index}",
            }
        )
        for index, label in enumerate(labels)
    ]
    reconstructed_responses = [
        llm_pipeline._lawyer_review_response(
            {
                "review_id": "review-1",
                "reviewer_id": f"lawyer-{index}",
                "reviewer_expertise": "senior_litigator",
                "proposed_label": label,
                "confidence": 0.9,
                "minutes_spent": 10.0,
                "notes": "Fixture.",
            }
        )
        for index, label in enumerate(labels)
    ]

    assert {
        vote.label.canonical_unit_resolution.value for vote in reconstructed_votes
    } == {"partial_dismissal_only", "survives_in_material_respect"}
    assert {
        response.proposed_label.canonical_unit_resolution.value
        for response in reconstructed_responses
    } == {"partial_dismissal_only", "survives_in_material_respect"}


def _label_record(
    unit_id: str,
    *,
    dismissed: bool,
    excerpt: str | None,
) -> JsonRecord:
    return {
        "unit_id": unit_id,
        "unit_resolution": (
            "fully_dismissed" if dismissed else "survives_in_material_respect"
        ),
        "fully_dismissed": dismissed,
        "primary_outcome": 1 if dismissed else 0,
        "amendment_class": (
            "dismissed_with_express_denial_of_leave"
            if dismissed
            else "not_fully_dismissed"
        ),
        "amendment_target_applicable": dismissed,
        "conditional_amendment_target": False if dismissed else None,
        "ambiguous": False,
        "label_confidence": 0.97,
        "supporting_citations": [
            {
                "document_id": "decision",
                "page": None,
                "paragraph": None,
                "excerpt": excerpt,
            }
        ],
        "first_written_disposition_id": "decision",
        "first_written_disposition_date": "2026-05-18",
        "first_written_disposition_locked": True,
        "later_procedural_changes": [],
        "notes": None,
    }


def _adjudication_record(
    review_id: str,
    unit_id: str,
    label: JsonRecord,
) -> JsonRecord:
    return {
        "review_id": review_id,
        "candidate_id": "cand-1",
        "unit_id": unit_id,
        "reviewer_responses": [
            {
                "review_id": review_id,
                "reviewer_id": "reviewer-a",
                "reviewer_expertise": "senior_litigator",
                "proposed_label": label,
                "confidence": 0.96,
                "minutes_spent": 12.5,
                "notes": "Checked against the first written disposition.",
            }
        ],
        "adjudicated_label": label,
        "adjudicator_id": "john-hughes",
        "adjudication_notes": "Accepted the reviewer label.",
    }


def _llm_label_audit_record(
    *,
    auto_label: JsonRecord,
    review_label: JsonRecord,
) -> JsonRecord:
    return {
        "stage": "llm-label",
        "status": "adjudication_pending",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "ensemble": {
            "high_confidence_threshold": 0.85,
            "required_model_count": 3,
            "unit_count": 2,
            "auto_label_count": 1,
            "lawyer_adjudicated_share": 0.5,
            "ambiguous_unit_count": 0,
            "ambiguous_exclusion_count": 0,
            "decisions": [
                _ensemble_decision_record(
                    unit_id="unit-auto",
                    status="auto_label",
                    route_reason="unanimous_high_confidence",
                    label=auto_label,
                    confidence=0.93,
                    unanimous_label=auto_label,
                ),
                _ensemble_decision_record(
                    unit_id="unit-review",
                    status="lawyer_adjudication",
                    route_reason="low_confidence",
                    label=review_label,
                    confidence=0.7,
                    unanimous_label=None,
                ),
            ],
        },
    }


def _ensemble_decision_record(
    *,
    unit_id: str,
    status: str,
    route_reason: str,
    label: JsonRecord,
    confidence: float,
    unanimous_label: JsonRecord | None,
) -> JsonRecord:
    votes = [
        _ensemble_vote_record(f"openai:gpt-{suffix}", unit_id, label, confidence)
        for suffix in ("a", "b", "c")
    ]
    return {
        "unit_id": unit_id,
        "status": status,
        "route_reason": route_reason,
        "model_ids": [vote["model_id"] for vote in votes],
        "mean_confidence": confidence,
        "min_confidence": confidence,
        "unanimous_label": unanimous_label,
        "votes": votes,
    }


def _ensemble_vote_record(
    model_id: str,
    unit_id: str,
    label: JsonRecord,
    confidence: float,
) -> JsonRecord:
    return {
        "model_id": model_id,
        "unit_id": unit_id,
        "confidence": confidence,
        "rationale": "Fixture label rationale.",
        "raw_response_id": f"sha256:{model_id}:{unit_id}",
        "label": label,
        "signature": [
            label["fully_dismissed"],
            label["amendment_class"],
            label["ambiguous"],
            label["primary_outcome"],
            label["conditional_amendment_target"],
        ],
    }


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_authenticated_stage_b_inputs(
    *,
    root: Path,
    selection_path: Path,
    parser_path: Path,
    markdown_root: Path,
) -> list[str]:
    selection = _read_jsonl(selection_path)
    parser_rows = _read_jsonl(parser_path)
    [decision_document] = [
        document
        for document in selection[0]["documents"]
        if document["source_document_id"] == "decision"
    ]
    [decision_parser] = [
        record for record in parser_rows if record["source_document_id"] == "decision"
    ]
    markdown_path = markdown_root / decision_parser["markdown_path"]
    text = markdown_path.read_text(encoding="utf-8")
    text_sha256 = hashlib.sha256(text.encode()).hexdigest()
    decision_parser.update(
        {
            "source_sha256": "a" * 64,
            "source_byte_count": 42,
            "quality_flags": [],
            "parser_config": {
                "engine": "mistral",
                "parser_revision": EXPECTED_PARSER_REVISION,
                "expected_parser_revision": EXPECTED_PARSER_REVISION,
                "fixture_markdown": False,
            },
            "extracted_text": {
                "source_document_id": "decision",
                "extraction_method": "mistral_parser_markdown",
                "text_sha256": text_sha256,
            },
        }
    )
    _write_jsonl(parser_path, parser_rows)
    commitments = {
        "clearance_run_card_sha256": "sha256:" + "b" * 64,
        "disclosure_clearance_sha256": "sha256:" + "c" * 64,
        "download_manifest_sha256": "sha256:" + "d" * 64,
        "parser_manifest_sha256": _sha256_path(parser_path),
        "parser_run_card_sha256": "sha256:" + "e" * 64,
        "restriction_evidence_sha256": "sha256:" + "f" * 64,
        "selection_sha256": _sha256_path(selection_path),
        "selection_run_card_sha256": "sha256:" + "1" * 64,
    }
    record = {
        "schema_version": "legalforecast.decision_text.v1",
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "document_id": "decision",
        "entered_date": "2026-06-30",
        "text": text,
        "is_first_written_disposition": True,
        "contains_target_outcome": True,
        "model_visible": False,
        "document_role": decision_document["document_role"],
        "docket_entry_number": decision_document["docket_entry_number"],
        "source_sha256": "a" * 64,
        "source_byte_count": 42,
        "text_sha256": text_sha256,
        "markdown_sha256": text_sha256,
        "extraction_method": "mistral_parser_markdown",
        "parser_revision": EXPECTED_PARSER_REVISION,
        "clearance": {
            "status": "cleared",
            "restriction_status": "public",
            "reviewer_id": "reviewer:test",
            "controlled_store_provenance": "private-store://test/decision",
            "reviewed_at": "2026-07-15T12:00:00Z",
        },
        "input_commitments": commitments,
    }
    decision_texts = root / "decision-texts.jsonl"
    manifest_path = root / "decision-texts-manifest.json"
    run_card_path = root / "build-decision-texts.json"
    _write_jsonl(decision_texts, [record])
    manifest = {
        "schema_version": "legalforecast.decision_text_manifest.v1",
        "eligibility_anchor": "2026-06-30",
        "record_count": 1,
        "candidate_ids_sha256": _canonical_sha256(["cand-1"]),
        "decision_texts_sha256": _sha256_path(decision_texts),
        "input_commitments": commitments,
        "outcome_material_model_visible": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
    }
    _write_json(manifest_path, manifest)
    _write_json(
        run_card_path,
        {
            "schema_version": "legalforecast.acquisition_run_card.v1",
            "stage": "build-decision-texts",
            "status": "completed",
            "execute": True,
            "dry_run": False,
            "record_count": 1,
            "eligibility_anchor": "2026-06-30",
            "decision_texts_sha256": _sha256_path(decision_texts),
            "decision_texts_manifest_sha256": _sha256_path(manifest_path),
            "input_commitments": commitments,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "input_paths": [],
            "output_paths": [str(decision_texts), str(manifest_path)],
        },
    )
    return [
        "--decision-texts",
        str(decision_texts),
        "--decision-texts-manifest",
        str(manifest_path),
        "--decision-texts-run-card",
        str(run_card_path),
        "--markdown-root",
        str(markdown_root),
    ]


def _sha256_path(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _reseal_stage_b_bundle(
    root: Path,
    selection_path: Path,
    parser_path: Path,
) -> None:
    decision_texts_path = root / "decision-texts.jsonl"
    manifest_path = root / "decision-texts-manifest.json"
    run_card_path = root / "build-decision-texts.json"
    rows = _read_jsonl(decision_texts_path)
    manifest = json.loads(manifest_path.read_text())
    run_card = json.loads(run_card_path.read_text())
    commitments = dict(rows[0]["input_commitments"])
    commitments["selection_sha256"] = _sha256_path(selection_path)
    commitments["parser_manifest_sha256"] = _sha256_path(parser_path)
    for row in rows:
        row["input_commitments"] = commitments
    _write_jsonl(decision_texts_path, rows)
    manifest.update(
        {
            "record_count": len(rows),
            "candidate_ids_sha256": _canonical_sha256(
                [row["candidate_id"] for row in rows]
            ),
            "decision_texts_sha256": _sha256_path(decision_texts_path),
            "input_commitments": commitments,
        }
    )
    _write_json(manifest_path, manifest)
    run_card.update(
        {
            "record_count": len(rows),
            "decision_texts_sha256": _sha256_path(decision_texts_path),
            "decision_texts_manifest_sha256": _sha256_path(manifest_path),
            "input_commitments": commitments,
        }
    )
    _write_json(run_card_path, run_card)


_DECISION_TEXT = (
    "The Court rules as follows. Count I survives. Count I is dismissed. "
    "Count II is dismissed."
)


def _write_decision_texts(path: Path, *, text: str = _DECISION_TEXT) -> Path:
    _write_jsonl(
        path,
        [
            {
                "document_id": "decision",
                "entered_date": "2026-05-18",
                "text": text,
                "is_first_written_disposition": True,
            }
        ],
    )
    return path


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, record: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _rewrite_as_finalized(path: Path) -> None:
    finalized = apply_unitization_reviews(
        prediction_unit_records=_read_jsonl(path),
        review_records=(),
        adjudication_records=(),
    )
    _write_jsonl(path, list(finalized))


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [
        cast(JsonRecord, json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
