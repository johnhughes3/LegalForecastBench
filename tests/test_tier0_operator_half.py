# pyright: reportPrivateUsage=false

"""Provider-free proofs for the Tier-0 operator half.

Covers the three pieces that turned the frozen-spec contract from
enforcement-only into enforcement-plus-issuance: the installed evaluator
wrapper, the deterministic spec/sidecar mint, and the supported production
evaluator factory. No test resolves a credential or contacts a provider.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.multiharness import tier0_mint
from legalforecast.multiharness.deliverable_text import (
    DeliverableTextError,
    docx_visible_text,
)
from legalforecast.multiharness.deliverables import single_artifact_tree_sha256
from legalforecast.multiharness.harvey_lab_evaluator import (
    EVALUATION_INPUT_SCHEMA_VERSION,
    HarveyLabEvaluationHosts,
    HarveyLabJudgeRequest,
    HarveyLabJudgeRequestBoundary,
    build_contained_evaluator_run_spec,
)
from legalforecast.multiharness.harvey_lab_production_runner import (
    JudgeDeliverable,
    ProductionEvaluatorRunnerError,
    ProductionJudgeCall,
    ProductionJudgeResponse,
)
from legalforecast.multiharness.harvey_lab_projection import ISSUE_196_LAB_TASK_ID
from legalforecast.multiharness.spend import PricingRate, PricingSnapshot
from legalforecast.multiharness.tier0_evaluator_wrapper import (
    HARVEY_LAB_EVAL_WRAPPER_SOURCE,
    EvaluatorWrapperInstallError,
    install_evaluator_wrapper,
    wrapper_source_sha256,
    wrapper_source_version,
)
from legalforecast.multiharness.tier0_mint import (
    NativeThinArmInput,
    Tier0MintError,
    build_pricing_snapshot,
    criterion_ids_from_private_task,
    judge_max_cost_usd,
    mint_tier0_artifacts,
)
from legalforecast.multiharness.tier0_production_factory import (
    AnthropicMessagesJudgeAdapter,
    JudgeTransportResult,
    ProductionFactoryError,
    build_production_evaluator,
    infisical_tier0_judge_secret_loader,
    judge_max_prompt_bytes,
)
from legalforecast.multiharness.tier0_runner import (
    load_executable_spec,
    load_spend_artifacts,
)
from tests.test_harvey_lab_evaluator import _identity, _project, _seal_deliverable

CRITERION_IDS = tuple(f"criterion-{index:02d}" for index in range(1, 24))
DELIVERABLE_BASENAME = "issue-identification-memo.docx"


def _docx_bytes(*paragraphs: str) -> bytes:
    """Build a minimal WordprocessingML package.

    synthetic: true -- hand-authored rather than produced by a word processor,
    because the extraction contract under test is the OOXML element shape, not
    any particular authoring tool's output.
    """

    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def _native_thin(budget_argument: str = "--max-cost-usd") -> NativeThinArmInput:
    return NativeThinArmInput(
        executable="harvey-lab-thin",
        executable_sha256="sha256:" + "a" * 64,
        executable_version="harvey-lab-thin 1.0.0",
        version_probe_args=("--version",),
        command=(
            "harvey-lab-thin",
            "--task",
            tier0_mint.PINNED_TASK_ID,
            budget_argument,
            "{max_cost_usd}",
            "{sandbox_root}",
        ),
        budget_argument=budget_argument,
    )


def _run_wrapper(args: list[str], stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARVEY_LAB_EVAL_WRAPPER_SOURCE), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def _evaluation_input(tmp_path: Path, **overrides: object) -> dict[str, object]:
    deliverable = tmp_path / "issue-identification-memo.docx"
    deliverable.write_bytes(b"docx")
    private = tmp_path / "task.json"
    private.write_text("{}", encoding="utf-8")
    record: dict[str, object] = {
        # Taken from the producer, never retyped: the wrapper and the producer
        # disagreeing on this string is exactly the defect a hand-written
        # spelling hid, because the suite then only ever fed the wrapper its
        # own dialect.
        "schema_version": EVALUATION_INPUT_SCHEMA_VERSION,
        "lab_task_id": tier0_mint.PINNED_TASK_ID,
        "expected_deliverable_basename": "issue-identification-memo.docx",
        "deliverable_manifest_sha256": "sha256:" + "1" * 64,
        "deliverable_tree_sha256": "sha256:" + "2" * 64,
        "task_sha256": "sha256:" + "3" * 64,
        "projection_manifest_sha256": "sha256:" + "4" * 64,
        "private_material_sha256": "sha256:" + "5" * 64,
        "deliverable_path": str(deliverable),
        "private_task_json_path": str(private),
        "scores_output_path": str(tmp_path / "scores.json"),
    }
    record.update(overrides)
    return record


# --------------------------------------------------------------------------
# Installed wrapper
# --------------------------------------------------------------------------


def test_wrapper_version_matches_the_pinned_probe_line() -> None:
    """The probe extracts a semantic version line, so --version must emit one."""

    result = _run_wrapper(["--version"])
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"harvey-lab-eval {wrapper_source_version()}"


def test_wrapper_help_lists_flags_and_rejects_unknown_arguments() -> None:
    helped = _run_wrapper(["--help"])
    assert helped.returncode == 0
    assert "--version" in helped.stdout
    unknown = _run_wrapper(["--lab-root", "/tmp"])
    assert unknown.returncode == 2


def test_wrapper_refuses_the_unaccounted_aggregate_path(tmp_path: Path) -> None:
    """A well-formed input still refuses: the aggregate path cannot be capped."""

    record = _evaluation_input(tmp_path)
    result = _run_wrapper([], stdin=json.dumps(record))
    assert result.returncode == 3
    assert "per-criterion" in result.stderr
    assert not (tmp_path / "scores.json").exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": EVALUATION_INPUT_SCHEMA_VERSION + "9"},
        {"deliverable_path": "relative/path.docx"},
    ],
)
def test_wrapper_rejects_malformed_evaluation_input(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    record = _evaluation_input(tmp_path, **overrides)
    result = _run_wrapper([], stdin=json.dumps(record))
    assert result.returncode == 4


def test_install_copies_committed_bytes_and_passes_the_probe(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    installed = install_evaluator_wrapper(bin_dir, scratch_root=tmp_path / "scratch")
    assert installed.wrapper_sha256 == wrapper_source_sha256()
    assert installed.probe.pin_digest_match
    assert installed.probe.pin_version_match
    record = installed.to_record()
    # The record is committed next to freeze material in a public repository.
    assert str(bin_dir) not in json.dumps(record)


def test_install_refuses_to_silently_replace_an_existing_entrypoint(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "harvey-lab-eval").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    with pytest.raises(EvaluatorWrapperInstallError):
        install_evaluator_wrapper(bin_dir, scratch_root=tmp_path / "scratch")


# --------------------------------------------------------------------------
# Deterministic mint
# --------------------------------------------------------------------------


def test_mint_is_byte_reproducible_across_output_directories(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    left = mint_tier0_artifacts(
        first, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    right = mint_tier0_artifacts(
        second, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    assert left.spec_path.read_bytes() == right.spec_path.read_bytes()
    assert left.policy_path.read_bytes() == right.policy_path.read_bytes()
    assert left.pricing_path.read_bytes() == right.pricing_path.read_bytes()
    assert left.spec_sha256 == right.spec_sha256


def test_minted_artifacts_load_through_the_runner_contract(tmp_path: Path) -> None:
    """The mint must satisfy the exact loader the paid command uses."""

    minted = mint_tier0_artifacts(
        tmp_path, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    spec, spec_sha256 = load_executable_spec(minted.spec_path, minted.spec_sha256)
    assert spec_sha256 == minted.spec_sha256
    policy, pricing = load_spend_artifacts(minted.spec_path, spec)
    assert policy.policy_sha256 == minted.spend_policy_sha256
    assert pricing.snapshot_sha256 == minted.pricing_snapshot_sha256
    assert len(policy.judge_ceilings) == 46
    assert [item.criterion_id for item in policy.judge_ceilings[:23]] == list(
        CRITERION_IDS
    )


def test_spec_digest_covers_the_exact_file_bytes(tmp_path: Path) -> None:
    minted = mint_tier0_artifacts(
        tmp_path, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    observed = "sha256:" + sha256(minted.spec_path.read_bytes()).hexdigest()
    assert observed == minted.spec_sha256


def test_judge_ceiling_covers_one_worst_case_call_at_the_dated_rates() -> None:
    pricing = build_pricing_snapshot()
    rate = pricing.rate_for("anthropic", "claude-sonnet-4-6")
    worst_case = rate.worst_case_microusd(
        input_tokens=tier0_mint.JUDGE_MAX_INPUT_TOKENS,
        output_tokens=tier0_mint.JUDGE_MAX_OUTPUT_TOKENS,
    )
    cap_microusd = round(float(judge_max_cost_usd(pricing)) * 1_000_000)
    assert cap_microusd >= worst_case


@pytest.mark.parametrize(
    "criterion_ids",
    [CRITERION_IDS[:22], (*CRITERION_IDS[:22], "criterion-01")],
)
def test_mint_refuses_a_criterion_set_the_evaluator_cannot_match(
    tmp_path: Path, criterion_ids: tuple[str, ...]
) -> None:
    with pytest.raises(Tier0MintError):
        mint_tier0_artifacts(
            tmp_path, criterion_ids=criterion_ids, native_thin=_native_thin()
        )


def test_native_thin_arm_requires_a_real_enforced_budget_flag() -> None:
    """A turn limit is not a dollar ceiling; the mint must not accept one."""

    with pytest.raises(Tier0MintError):
        NativeThinArmInput(
            executable="harvey-lab-thin",
            executable_sha256="sha256:" + "a" * 64,
            executable_version="harvey-lab-thin 1.0.0",
            version_probe_args=("--version",),
            command=("harvey-lab-thin", "--max-turns", "8"),
            budget_argument="--max-turns",
        )


def test_private_task_material_is_hash_verified_before_it_is_parsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = tmp_path / "task.json"
    payload = json.dumps(
        {"criteria": [{"id": value} for value in CRITERION_IDS]}
    ).encode("utf-8")
    task.write_bytes(payload)
    with pytest.raises(Tier0MintError):
        criterion_ids_from_private_task(task)
    monkeypatch.setattr(tier0_mint, "PINNED_TASK_SHA256", sha256(payload).hexdigest())
    assert criterion_ids_from_private_task(task) == CRITERION_IDS


# --------------------------------------------------------------------------
# Production evaluator factory
# --------------------------------------------------------------------------


class _RecordingBoundary(HarveyLabJudgeRequestBoundary):
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, int]] = []

    def before_judge_call(self, request: HarveyLabJudgeRequest) -> object:
        self.calls.append(
            (request.ordinal, request.criterion_id, request.attempt_index)
        )
        return request

    def after_judge_call(
        self, request: HarveyLabJudgeRequest, reservation: object, observation: object
    ) -> None:
        del request, reservation, observation


class _CapturingTransport:
    """A fake provider that records exactly what would have been billed."""

    def __init__(
        self, verdict: str = "pass", resolved_model: str | None = None
    ) -> None:
        self.verdict = verdict
        self.resolved_model = resolved_model
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def __call__(
        self,
        *,
        api_key: str,
        model: str,
        system: str,
        prompt: str,
        max_output_tokens: int,
        temperature: float,
    ) -> JudgeTransportResult:
        del api_key, max_output_tokens, temperature
        self.prompts.append(prompt)
        self.systems.append(system)
        return JudgeTransportResult(
            verdict_text=self.verdict,
            resolved_model=self.resolved_model or model,
            input_tokens=1200,
            output_tokens=1,
            raw_response=b'{"stub":true}',
        )


def _transport(verdict: str = "pass") -> object:
    return _CapturingTransport(verdict=verdict)


def _deliverable(
    text: str = "The memo identifies the tolling issue.",
) -> JudgeDeliverable:
    payload = _docx_bytes(text)
    return JudgeDeliverable(
        basename=DELIVERABLE_BASENAME,
        text=text,
        sha256="sha256:" + sha256(payload).hexdigest(),
    )


def _judge_call(
    criterion_id: str,
    attempt_index: int = 0,
    deliverable: JudgeDeliverable | None = None,
) -> ProductionJudgeCall:
    return ProductionJudgeCall(
        request=HarveyLabJudgeRequest(
            ordinal=1, criterion_id=criterion_id, attempt_index=attempt_index
        ),
        run_spec=None,  # type: ignore[arg-type]
        criterion={"id": criterion_id, "title": "t", "match_criteria": "requirement"},
        deliverable=deliverable or _deliverable(),
    )


def test_judge_adapter_reports_allocable_usage_and_the_resolved_model() -> None:
    pricing = build_pricing_snapshot()
    adapter = AnthropicMessagesJudgeAdapter(
        pricing_snapshot=pricing,
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=_transport(),  # type: ignore[arg-type]
        max_prompt_bytes=100_000,
    )
    response = adapter(_judge_call("criterion-01"))
    assert isinstance(response, ProductionJudgeResponse)
    assert response.verdict == "pass"
    assert response.usage.basis == "estimated_from_pricing_snapshot"
    assert response.usage.input_tokens == 1200
    assert response.judge_resolved_identity != "fixture/stub@local"


def test_unparseable_verdict_is_retryable_rather_than_silently_dropped() -> None:
    adapter = AnthropicMessagesJudgeAdapter(
        pricing_snapshot=build_pricing_snapshot(),
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=_transport(verdict="maybe"),  # type: ignore[arg-type]
        max_prompt_bytes=100_000,
    )
    response = adapter(_judge_call("criterion-01"))
    assert response.retryable is True
    assert response.verdict is None


def test_judge_credential_loader_refuses_coordinates_outside_the_namespace() -> None:
    with pytest.raises(ProductionFactoryError):
        infisical_tier0_judge_secret_loader(
            "prod",
            "/agents/sandbox/legalforecastbench/harness-runtime/tier0-judge",
            "TIER0_JUDGE_ANTHROPIC_API_KEY",
        )
    with pytest.raises(ProductionFactoryError):
        infisical_tier0_judge_secret_loader(
            "dev", "/agents/sandbox/other/path", "TIER0_JUDGE_ANTHROPIC_API_KEY"
        )


def test_production_factory_refuses_a_pricing_snapshot_it_cannot_price(
    tmp_path: Path,
) -> None:
    """Strip the priced model and the paid seam refuses before any call."""

    minted = mint_tier0_artifacts(
        tmp_path, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    spec, _ = load_executable_spec(minted.spec_path, minted.spec_sha256)
    policy, pricing = load_spend_artifacts(minted.spec_path, spec)
    unpriced = _unpriced_snapshot(pricing)
    with pytest.raises(ProductionFactoryError):
        build_production_evaluator(
            spec,
            minted.spec_path,
            tmp_path / "private",
            policy,
            unpriced,
            secret_loader=lambda _e, _p, _n: "stub-key",
            transport=_transport(),  # type: ignore[arg-type]
        )


def _unpriced_snapshot(pricing: PricingSnapshot) -> PricingSnapshot:
    del pricing
    return PricingSnapshot(
        snapshot_id="tier0-unpriced",
        as_of_date=tier0_mint.PRICING_AS_OF_DATE,
        rates=(
            PricingRate(
                provider="anthropic",
                model="some-other-model",
                input_microusd_per_token=3,
                output_microusd_per_token=15,
            ),
        ),
    )


def test_attempt_retention_keeps_every_billed_attempt(tmp_path: Path) -> None:
    """A retry must never overwrite the evidence of the attempt it replaced."""

    mint_dir = tmp_path / "mint"
    mint_dir.mkdir()
    minted = mint_tier0_artifacts(
        mint_dir, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    spec, _ = load_executable_spec(minted.spec_path, minted.spec_sha256)
    policy, pricing = load_spend_artifacts(minted.spec_path, spec)
    private_root = tmp_path / "private"
    private_root.mkdir()
    _, _provenance = build_production_evaluator(
        spec,
        minted.spec_path,
        private_root,
        policy,
        pricing,
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=_transport(),  # type: ignore[arg-type]
    )
    from legalforecast.multiharness.tier0_production_factory import (
        JudgeAttemptWriter,
    )

    writer = JudgeAttemptWriter(private_root / "evaluator" / "judge-attempts")
    adapter = AnthropicMessagesJudgeAdapter(
        pricing_snapshot=pricing,
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=_transport(),  # type: ignore[arg-type]
        max_prompt_bytes=100_000,
    )
    first = _judge_call("criterion-01", attempt_index=0)
    second = _judge_call("criterion-01", attempt_index=1)
    writer(first, adapter(first))
    writer(second, adapter(second))
    attempts = sorted(
        (private_root / "evaluator" / "judge-attempts" / "criterion-01").glob(
            "attempt-*.json"
        )
    )
    assert [path.name for path in attempts] == [
        "attempt-0.json",
        "attempt-1.json",
    ]


def test_provenance_configuration_is_never_fixture(tmp_path: Path) -> None:
    minted = mint_tier0_artifacts(
        tmp_path, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    spec, _ = load_executable_spec(minted.spec_path, minted.spec_sha256)
    policy, pricing = load_spend_artifacts(minted.spec_path, spec)
    _, provenance = build_production_evaluator(
        spec,
        minted.spec_path,
        tmp_path / "private",
        policy,
        pricing,
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=_transport(),  # type: ignore[arg-type]
    )
    configuration = provenance.configuration
    assert configuration.is_fixture is False
    assert configuration.cost_basis == "estimated_from_pricing_snapshot"
    assert configuration.pricing_snapshot_sha256 == pricing.snapshot_sha256


def test_recording_boundary_sees_every_criterion_attempt() -> None:
    """The boundary contract the production runner drives, exercised directly."""

    boundary = _RecordingBoundary()
    for ordinal in range(1, 24):
        request = HarveyLabJudgeRequest(ordinal=ordinal, criterion_id=f"c{ordinal}")
        reservation = boundary.before_judge_call(request)
        boundary.after_judge_call(request, reservation, object())
    assert len(boundary.calls) == 23


def test_cli_mint_writes_the_three_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI handler must reach the generator, not just import it."""

    import argparse

    from legalforecast.multiharness.cli import _cmd_tier0_mint

    task = tmp_path / "task.json"
    payload = json.dumps(
        {
            "criteria": [
                {"id": value, "title": "t", "match_criteria": "m"}
                for value in CRITERION_IDS
            ]
        }
    ).encode("utf-8")
    task.write_bytes(payload)
    monkeypatch.setattr(tier0_mint, "PINNED_TASK_SHA256", sha256(payload).hexdigest())
    manifest = tmp_path / "native-thin.json"
    native = _native_thin()
    manifest.write_text(
        json.dumps(
            {
                "executable": native.executable,
                "executable_sha256": native.executable_sha256,
                "executable_version": native.executable_version,
                "version_probe_args": list(native.version_probe_args),
                "command": list(native.command),
                "budget_argument": native.budget_argument,
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "mint"
    output_dir.mkdir()
    exit_code = _cmd_tier0_mint(
        argparse.Namespace(
            output_dir=output_dir,
            private_task_json=task,
            native_thin_manifest=manifest,
            evaluator_wrapper_sha256=None,
        )
    )
    assert exit_code == 0
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "tier0-executable-spec.json",
        "tier0-executable-spec.pricing-snapshot.json",
        "tier0-executable-spec.spend-policy.json",
    ]
    # The operator must be told these bytes are private before they move them.
    assert "evaluator-private" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Candidate deliverable: extraction, authentication, and delivery to the judge
# --------------------------------------------------------------------------


def test_docx_extraction_returns_visible_text_in_document_order() -> None:
    payload = _docx_bytes("First paragraph.", "Second paragraph.")
    assert docx_visible_text(payload) == "First paragraph.\nSecond paragraph."


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (b"not a zip at all", "not a zip container"),
        (_docx_bytes(), "renders to no text"),
        (_docx_bytes("   "), "renders to whitespace only"),
    ],
)
def test_docx_extraction_refuses_what_it_cannot_faithfully_render(
    payload: bytes, reason: str
) -> None:
    """A partial or empty rendering would be graded as if it were the memo."""

    with pytest.raises(DeliverableTextError):
        docx_visible_text(payload)


def test_docx_extraction_refuses_a_document_part_declaring_a_dtd() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr(
            "word/document.xml",
            '<!DOCTYPE w:document [<!ENTITY a "boom">]><w:document/>',
        )
    with pytest.raises(DeliverableTextError):
        docx_visible_text(buffer.getvalue())


def test_single_artifact_tree_digest_matches_the_sealing_commitment(
    tmp_path: Path,
) -> None:
    """The recompute must equal what seal_deliverable actually committed."""

    projected = _project(tmp_path)
    payload = _docx_bytes("Sealed memo body.")
    _sealed_root, manifest = _seal_deliverable(tmp_path, projected, payload=payload)
    assert (
        single_artifact_tree_sha256(DELIVERABLE_BASENAME, payload)
        == manifest.tree_sha256
    )


def _real_criterion_ids(projected: Any) -> tuple[str, ...]:
    task = (
        Path(projected.evaluator_private_root)
        / "tasks"
        / ISSUE_196_LAB_TASK_ID
        / "task.json"
    )
    record = json.loads(task.read_text(encoding="utf-8"))
    return tuple(str(item["id"]) for item in record["criteria"])


def _evaluator_run_spec(root: Path, *, deliverable_text: str) -> tuple[Any, Any]:
    """Build a real evaluator RunSpec through the production producer path."""

    root.mkdir(parents=True, exist_ok=True)
    projected = _project(root)
    sealed_root, sealed = _seal_deliverable(
        root, projected, payload=_docx_bytes(deliverable_text)
    )
    hosts = HarveyLabEvaluationHosts(
        sealed_deliverable_root=sealed_root,
        evaluator_private_root=projected.evaluator_private_root,
        overlay_root=root / "overlay",
        working_directory=root / "work",
        solver_projection_root=projected.solver_root,
    )
    spec, _record = build_contained_evaluator_run_spec(
        hosts=hosts, sealed_manifest=sealed, identity=_identity(projected, root)
    )
    return spec, projected


def _production_runner(root: Path, projected: Any, transport: Any) -> Any:
    mint_dir = root / "mint"
    mint_dir.mkdir()
    minted = mint_tier0_artifacts(
        mint_dir,
        criterion_ids=_real_criterion_ids(projected),
        native_thin=_native_thin(),
    )
    spec, _ = load_executable_spec(minted.spec_path, minted.spec_sha256)
    policy, pricing = load_spend_artifacts(minted.spec_path, spec)
    archive_root = root / "private-archive"
    archive_root.mkdir()
    runner, _provenance = build_production_evaluator(
        spec,
        minted.spec_path,
        archive_root,
        policy,
        pricing,
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=transport,
    )
    return runner


def _run_production_evaluation(
    root: Path, *, deliverable_text: str, transport: _CapturingTransport
) -> Any:
    run_spec, projected = _evaluator_run_spec(root, deliverable_text=deliverable_text)
    runner = _production_runner(root, projected, transport)
    return runner(cast(Any, None), run_spec, _RecordingBoundary())


def test_changing_the_deliverable_changes_the_judge_input_bytes(
    tmp_path: Path,
) -> None:
    """The bug this proves absent: verdicts independent of the work product.

    Two runs differing only in the candidate's memo must send different bytes
    to the provider. Before the deliverable reached the prompt, these were
    byte-identical for every candidate.
    """

    first = _CapturingTransport()
    second = _CapturingTransport()
    _run_production_evaluation(
        tmp_path / "first",
        deliverable_text="The memo identifies the statute of limitations defect.",
        transport=first,
    )
    _run_production_evaluation(
        tmp_path / "second",
        deliverable_text="The memo argues the arbitration clause is unenforceable.",
        transport=second,
    )
    assert len(first.prompts) == 23
    assert len(second.prompts) == 23
    assert first.prompts != second.prompts
    assert "statute of limitations defect" in first.prompts[0]
    assert "arbitration clause is unenforceable" in second.prompts[0]
    # The criterion still reaches the judge alongside the work product.
    assert "EVALUATOR_PRIVATE_CANARY" in first.prompts[0]


def test_run_refuses_before_any_billable_call_when_the_deliverable_is_missing(
    tmp_path: Path,
) -> None:
    """An unreadable work product must stop the run, not grade an absence."""

    transport = _CapturingTransport()
    run_spec, projected = _evaluator_run_spec(
        tmp_path / "run", deliverable_text="Body text."
    )
    runner = _production_runner(tmp_path / "run", projected, transport)
    record = json.loads(run_spec.stdin_bytes.decode("utf-8"))
    Path(str(record["deliverable_path"])).unlink()
    boundary = _RecordingBoundary()
    with pytest.raises(ProductionEvaluatorRunnerError):
        runner(cast(Any, None), run_spec, boundary)
    # Nothing was sent and nothing was even reserved: the refusal lands before
    # the run touches the spend boundary, not after the first criterion.
    assert transport.prompts == []
    assert boundary.calls == []


def test_run_refuses_a_deliverable_that_does_not_match_the_sealed_commitment(
    tmp_path: Path,
) -> None:
    """Substituted bytes must not be gradeable just because the path is right."""

    transport = _CapturingTransport()
    run_spec, projected = _evaluator_run_spec(
        tmp_path / "run", deliverable_text="Body text."
    )
    runner = _production_runner(tmp_path / "run", projected, transport)
    record = json.loads(run_spec.stdin_bytes.decode("utf-8"))
    overlay_copy = Path(str(record["deliverable_path"]))
    # The overlay copy lands read-only; anyone able to swap it would have
    # cleared that first, so the test does too.
    overlay_copy.chmod(0o644)
    overlay_copy.write_bytes(_docx_bytes("A different memo entirely."))
    with pytest.raises(ProductionEvaluatorRunnerError):
        runner(cast(Any, None), run_spec, _RecordingBoundary())
    assert transport.prompts == []


def test_run_refuses_a_substituted_judge_model(tmp_path: Path) -> None:
    """Costing is pinned to Sonnet 4.6, so the resolved identity must be too."""

    transport = _CapturingTransport(resolved_model="claude-opus-4-6")
    with pytest.raises(ProductionEvaluatorRunnerError):
        _run_production_evaluation(
            tmp_path / "run", deliverable_text="Body text.", transport=transport
        )


def test_judge_prompt_over_the_reserved_input_budget_refuses() -> None:
    """Refuse rather than truncate: a clipped memo yields a confident wrong verdict."""

    adapter = AnthropicMessagesJudgeAdapter(
        pricing_snapshot=build_pricing_snapshot(),
        secret_loader=lambda _e, _p, _n: "stub-key",
        transport=_transport(),  # type: ignore[arg-type]
        max_prompt_bytes=256,
    )
    call = _judge_call("criterion-01", deliverable=_deliverable("x" * 4096))
    with pytest.raises(ProductionFactoryError):
        adapter(call)


def test_judge_prompt_budget_comes_from_the_minted_spend_policy(
    tmp_path: Path,
) -> None:
    """The bound is spec-covered, not a loose constant beside the adapter."""

    minted = mint_tier0_artifacts(
        tmp_path, criterion_ids=CRITERION_IDS, native_thin=_native_thin()
    )
    spec, _ = load_executable_spec(minted.spec_path, minted.spec_sha256)
    policy, _pricing = load_spend_artifacts(minted.spec_path, spec)
    budget = judge_max_prompt_bytes(policy)
    assert budget == tier0_mint.JUDGE_MAX_INPUT_TOKENS - 256
    assert budget < tier0_mint.JUDGE_MAX_INPUT_TOKENS


def test_wrapper_refuses_output_the_real_producer_actually_emits(
    tmp_path: Path,
) -> None:
    """Feed the wrapper the producer's own record, not the suite's dialect.

    The suite previously only ever fed the wrapper a hand-written record using
    the wrapper's own schema spelling, so a producer/wrapper mismatch scored
    exit 4 (malformed) on every real input while the tests stayed green.
    """

    run_spec, _projected = _evaluator_run_spec(
        tmp_path / "run", deliverable_text="Body text."
    )
    result = subprocess.run(
        [sys.executable, str(HARVEY_LAB_EVAL_WRAPPER_SOURCE)],
        input=run_spec.stdin_bytes,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 3, result.stderr.decode("utf-8", "replace")
    assert b"per-criterion" in result.stderr
