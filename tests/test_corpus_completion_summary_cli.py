"""CLI contract tests for provider-free corpus completion summaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast import cli
from legalforecast.ingestion.corpus_completion_summary import (
    RUN_CARD_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
    CorpusCompletionSummaryInputs,
)
from tests.test_corpus_completion_summary import build_completion_inputs


def _argv(
    inputs: CorpusCompletionSummaryInputs,
    output_root: Path,
) -> list[str]:
    return [
        "acquisition",
        "summarize-corpus",
        "--finalize-run-card",
        str(inputs.finalize_run_card),
        "--corpus-readiness",
        str(inputs.corpus_readiness),
        "--complete-exclusion-ledger",
        str(inputs.complete_exclusion_ledger),
        "--materialization-summary",
        str(inputs.materialization_summary),
        "--materialization-run-card",
        str(inputs.materialization_run_card),
        "--purchase-policy",
        str(inputs.purchase_policy),
        "--cohort-policy",
        str(inputs.cohort_policy),
        "--purchase-ledger",
        str(inputs.purchase_ledger),
        "--purchase-ledger-initialization-receipt",
        str(inputs.purchase_ledger_initialization_receipt),
        "--model-registry",
        str(inputs.model_registry),
        "--unitization-review-queue",
        str(inputs.unitization_review_queue),
        "--unitization-adjudications",
        str(inputs.unitization_adjudications),
        "--lawyer-review-queue",
        str(inputs.lawyer_review_queue),
        "--lawyer-review-audit",
        str(inputs.lawyer_review_audit),
        "--output-root",
        str(output_root),
    ]


def test_help_declares_provider_free_fail_closed_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        cli.main(["acquisition", "summarize-corpus", "--help"])

    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    assert "--execute" in help_text
    assert "Without this flag" in help_text
    assert "no provider, PACER, AWS, evaluation, freeze, or dispatch" in help_text


def test_dry_run_writes_nothing_and_execute_is_exactly_resumable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    output_root = tmp_path / "completion-output"
    argv = _argv(inputs, output_root)

    assert cli.main(argv) == 0
    dry_summary = json.loads(capsys.readouterr().out)
    assert dry_summary["schema_version"] == SUMMARY_SCHEMA_VERSION
    assert not output_root.exists()

    assert cli.main([*argv, "--execute", "--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    summary_path = output_root / "corpus-completion-summary.json"
    run_card_path = output_root / "run-cards" / "summarize-corpus.json"
    first_summary_bytes = summary_path.read_bytes()
    first_run_card_bytes = run_card_path.read_bytes()
    assert printed == json.loads(first_summary_bytes)
    run_card = json.loads(first_run_card_bytes)
    assert run_card["schema_version"] == RUN_CARD_SCHEMA_VERSION
    assert run_card["status"] == "completed"
    assert run_card["execute"] is True
    assert run_card["dry_run"] is False
    assert run_card["zero_provider_activity_evidence"] is True
    assert set(run_card["activity"].values()) == {False}

    assert cli.main([*argv, "--execute"]) == 0
    capsys.readouterr()
    assert summary_path.read_bytes() == first_summary_bytes
    assert run_card_path.read_bytes() == first_run_card_bytes


def test_execute_rejects_unexpected_output_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    output_root = tmp_path / "completion-output"
    output_root.mkdir()
    (output_root / "unowned.txt").write_text("not owned\n")

    assert cli.main([*_argv(inputs, output_root), "--execute"]) == 2
    assert not (output_root / "corpus-completion-summary.json").exists()


@pytest.mark.parametrize(
    ("alias_parent", "alias_target"),
    [
        (".", "corpus-completion-summary.json"),
        ("run-cards", "summarize-corpus.json"),
    ],
)
def test_execute_rejects_symlink_aliases_to_owned_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    alias_parent: str,
    alias_target: str,
) -> None:
    inputs = build_completion_inputs(tmp_path, monkeypatch=monkeypatch)
    output_root = tmp_path / "completion-output"
    argv = [*_argv(inputs, output_root), "--execute"]
    assert cli.main(argv) == 0

    alias_root = output_root / alias_parent
    (alias_root / "alias").symlink_to(alias_target)

    assert cli.main(argv) == 2
