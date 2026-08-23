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


def _zip_parts(*parts: tuple[str, str | bytes]) -> bytes:
    """Zip named parts with a fixed timestamp.

    Deterministic on purpose: `writestr` stamps entries with the current time,
    so identical logical fixtures produce different bytes from one call to the
    next. That makes any parametrize case carrying these bytes generate a
    different test ID per xdist worker, which fails collection outright.
    """

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in parts:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, body)
    return buffer.getvalue()


def _document_part(*paragraphs: str) -> str:
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )


def _docx_bytes(*paragraphs: str) -> bytes:
    """Build a minimal WordprocessingML package.

    synthetic: true -- hand-authored rather than produced by a word processor,
    because the extraction contract under test is the OOXML element shape, not
    any particular authoring tool's output.
    """

    return _zip_parts(
        ("[Content_Types].xml", "<Types></Types>"),
        ("word/document.xml", _document_part(*paragraphs)),
    )


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
    ) -> JudgeTransportResult:
        del api_key, max_output_tokens
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
    "case",
    ["not-a-zip", "no-paragraphs", "whitespace-only"],
)
def test_docx_extraction_refuses_what_it_cannot_faithfully_render(
    case: str,
) -> None:
    """A partial or empty rendering would be graded as if it were the memo."""

    payloads = {
        "not-a-zip": b"not a zip at all",
        "no-paragraphs": _docx_bytes(),
        "whitespace-only": _docx_bytes("   "),
    }
    with pytest.raises(DeliverableTextError):
        docx_visible_text(payloads[case])


def _docx_with_raw_document(document: bytes) -> bytes:
    """Package an arbitrary document part. synthetic: true."""

    return _zip_parts(
        ("[Content_Types].xml", "<Types></Types>"), ("word/document.xml", document)
    )


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_docx_extraction_refuses_a_dtd_in_any_declared_encoding(
    encoding: str,
) -> None:
    """The DTD refusal must not depend on the part's byte encoding.

    A scan for the literal bytes of `<!DOCTYPE` is not sound: the XML parser
    honours the encoding declared in the prolog, so a UTF-16 part hides those
    bytes from any ASCII substring search while the parser still expands the
    entities the DTD declares -- a billion-laughs expansion from a payload well
    under the size cap, which bounds pre-expansion bytes only.
    """

    entities = "".join(
        f'<!ENTITY l{index} "{f"&l{index - 1};" * 10}">' for index in range(1, 7)
    )
    document = (
        f'<?xml version="1.0" encoding="{encoding.upper()}"?>'
        f'<!DOCTYPE w:document [<!ENTITY l0 "AAAAAAAAAA">{entities}]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>&l6;</w:t>'
        "</w:r></w:p></w:body></w:document>"
    )
    with pytest.raises(DeliverableTextError, match="declares a DTD"):
        docx_visible_text(_docx_with_raw_document(document.encode(encoding)))


def test_docx_extraction_still_reads_a_legitimate_utf16_part() -> None:
    """Refusing DTDs must not mean refusing every non-UTF-8 document."""

    document = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Valid UTF-16 memo.'
        "</w:t></w:r></w:p></w:body></w:document>"
    )
    payload = _docx_with_raw_document(document.encode("utf-16"))
    assert docx_visible_text(payload) == "Valid UTF-16 memo."


def _docx_with_note_part(part_name: str, note_text: str) -> bytes:
    """A package whose footnote/endnote part carries `note_text`.

    synthetic: true -- hand-authored OOXML, matching the shape Word emits.
    """

    note = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main">'
        f"<w:footnote><w:p><w:r><w:t>{note_text}</w:t></w:r></w:p></w:footnote>"
        "</w:footnotes>"
    )
    return _zip_parts(
        ("[Content_Types].xml", "<Types></Types>"),
        ("word/document.xml", _document_part("Body paragraph.")),
        (part_name, note),
    )


@pytest.mark.parametrize("part_name", ["word/footnotes.xml", "word/endnotes.xml"])
def test_docx_extraction_refuses_notes_it_would_silently_drop(
    part_name: str,
) -> None:
    """Footnote prose lives outside the document part and is never rendered.

    A memo that argues in its footnotes would otherwise be graded without that
    argument -- a confident, billed verdict on partial input, which is the same
    failure class as sending no deliverable at all.
    """

    payload = _docx_with_note_part(part_name, "The limitations period was tolled.")
    with pytest.raises(DeliverableTextError):
        docx_visible_text(payload)


@pytest.mark.parametrize("part_name", ["word/footnotes.xml", "word/endnotes.xml"])
def test_docx_extraction_tolerates_word_s_empty_note_separators(
    part_name: str,
) -> None:
    """Word writes a note part into ordinary documents; empty stubs are fine."""

    payload = _docx_with_note_part(part_name, "   ")
    assert docx_visible_text(payload) == "Body paragraph."


def test_docx_extraction_refuses_a_document_part_declaring_a_dtd() -> None:
    payload = _zip_parts(
        ("[Content_Types].xml", "<Types></Types>"),
        (
            "word/document.xml",
            '<!DOCTYPE w:document [<!ENTITY a "boom">]><w:document/>',
        ),
    )
    with pytest.raises(DeliverableTextError):
        docx_visible_text(payload)


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


def test_installing_the_supported_factory_binds_the_reviewed_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The paid CLI path auto-installs a factory; prove which one it installs.

    `tier0 run` previously refused when no reviewed factory was injected and
    now installs the in-tree one instead. That is this branch's single
    gate-behavior change, so the identity of the installed factory is a
    contract worth pinning rather than assuming.
    """

    from legalforecast.multiharness import cli as multiharness_cli
    from legalforecast.multiharness.tier0_production_factory import (
        install_supported_production_factory,
    )

    monkeypatch.setattr(
        multiharness_cli, "_tier0_production_evaluator_factory", None, raising=False
    )
    install_supported_production_factory()
    installed = multiharness_cli._tier0_production_evaluator_factory
    assert installed is build_production_evaluator


def test_boundary_reservations_cover_every_criterion_of_a_real_run(
    tmp_path: Path,
) -> None:
    """One reservation per criterion, driven by the runner rather than a stub."""

    transport = _CapturingTransport()
    run_spec, projected = _evaluator_run_spec(
        tmp_path / "run", deliverable_text="Body text."
    )
    runner = _production_runner(tmp_path / "run", projected, transport)
    boundary = _RecordingBoundary()
    runner(cast(Any, None), run_spec, boundary)
    assert len(boundary.calls) == 23
    assert [ordinal for ordinal, _id, _attempt in boundary.calls] == list(range(1, 24))
