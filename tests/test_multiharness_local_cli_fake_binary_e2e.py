"""Fake-binary end-to-end acceptance for Claude Code and Codex CLI adapters.

Pipeline: LFB task load → generic registry lookup → auth profile fixture-none
→ contained execution of tests/fixtures/local_cli_fake_cli.py → terminal
receipt classification. Zero real binaries and zero provider spend.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast._json_io import write_jsonl_objects
from legalforecast.evals.packet_builder import PacketText, build_model_packet
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.multiharness.adapter_registry import (
    CLAUDE_CODE_REGISTRY_NAME,
    CODEX_CLI_REGISTRY_NAME,
    builtin_adapter_registry,
)
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.local_cli_runtime import LocalCliExecutionService
from legalforecast.multiharness.solver_inputs import (
    SOLVER_INPUT_ENTRY_PATH,
    SolverInputStore,
)
from legalforecast.multiharness.spec import (
    CanonicalTask,
    RunRequest,
    SandboxPolicy,
)
from legalforecast.multiharness.task_loaders import LfbTaskLoader
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)

ROOT = Path(__file__).resolve().parents[1]
FAKE_CLI = ROOT / "tests" / "fixtures" / "local_cli_fake_cli.py"
_SHA256 = "sha256:" + "1" * 64
_OUTCOMES = (
    "success",
    "refusal",
    "timeout",
    "crash",
    "sandbox_denial",
    "unknown-envelope",
)
_ADAPTERS = (
    (
        CLAUDE_CODE_REGISTRY_NAME,
        "claude",
        "anthropic:claude-sonnet-4-6",
    ),
    (
        CODEX_CLI_REGISTRY_NAME,
        "codex",
        "codex:gpt-5.1",
    ),
)


@pytest.mark.parametrize("adapter_name,basename,model_key", _ADAPTERS)
@pytest.mark.parametrize("outcome", _OUTCOMES)
def test_fake_binary_pipeline_classifies_terminal_receipt(
    tmp_path: Path,
    adapter_name: str,
    basename: str,
    model_key: str,
    outcome: str,
) -> None:
    workspace = tmp_path / "workspace"
    try:
        result = _run_pipeline(
            tmp_path,
            adapter_name=adapter_name,
            basename=basename,
            model_key=model_key,
            outcome=outcome,
        )
    finally:
        _make_writable(workspace)

    expected = _expected_failure_class(adapter_name, outcome)
    if expected is None:
        assert result.status == "succeeded"
        assert "failure_class" not in result.public_summary
        return
    assert result.status == "failed"
    assert result.public_summary["failure_class"] == expected


def test_unknown_envelope_is_never_empty_success(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    try:
        result = _run_pipeline(
            tmp_path,
            adapter_name=CLAUDE_CODE_REGISTRY_NAME,
            basename="claude",
            model_key="anthropic:claude-sonnet-4-6",
            outcome="unknown-envelope",
        )
    finally:
        _make_writable(workspace)

    assert result.status != "succeeded" or "failure_class" in result.public_summary
    assert result.public_summary.get("failure_class") == "crash"


def _run_pipeline(
    tmp_path: Path,
    *,
    adapter_name: str,
    basename: str,
    model_key: str,
    outcome: str,
):
    packet_path = tmp_path / "packets.jsonl"
    solver_root = tmp_path / "solver-inputs"
    write_jsonl_objects(packet_path, (_model_packet().to_record(),))
    index = LfbTaskLoader(suite_version="fixture-suite").load_packet_jsonl(
        packet_path,
        solver_input_root=solver_root,
    )
    task = _bind_solver_prompt(index.tasks[0], solver_root)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / SOLVER_INPUT_ENTRY_PATH).write_text(
        str(task.metadata["solver_prompt"]),
        encoding="utf-8",
    )
    bin_dir = tmp_path / "bin"
    _install_fake_binary(
        bin_dir,
        basename=basename,
        adapter=_envelope_adapter(basename),
        outcome=outcome,
    )
    timeout_seconds = 1 if outcome == "timeout" else 30
    adapter = builtin_adapter_registry().get(
        adapter_name,
        execution_service=LocalCliExecutionService(
            auth_profile=FIXTURE_NONE,
            parent_env=_parent_env(bin_dir),
        ),
    )
    request = RunRequest(
        request_id=f"request-{adapter_name}-{outcome}",
        task=task,
        adapter=adapter.manifest,
        model_key=model_key,
        sandbox_policy=SandboxPolicy(
            policy_id="offline-fake-binary",
            backend="none",
            image="none",
            network_policy="none",
            timeout_seconds=timeout_seconds,
            allowed_provider_env_vars=(),
        ),
        request_sha256=_SHA256,
    )
    return adapter.run(request, workspace)


def _expected_failure_class(adapter_name: str, outcome: str) -> str | None:
    if outcome == "success":
        return None
    if outcome == "unknown-envelope":
        if adapter_name == CLAUDE_CODE_REGISTRY_NAME:
            return "crash"
        return "schema_violation"
    return outcome


def _envelope_adapter(basename: str) -> str:
    if basename == "claude":
        return "claude"
    return "codex"


def _bind_solver_prompt(task: CanonicalTask, solver_root: Path) -> CanonicalTask:
    store = SolverInputStore.load(solver_root)
    entry = next(item for item in store.index.entries if item.task_id == task.task_id)
    prompt_file = next(
        item for item in entry.files if item.destination_path == SOLVER_INPUT_ENTRY_PATH
    )
    prompt = (solver_root / prompt_file.source_path).read_text(encoding="utf-8")
    metadata = dict(task.metadata)
    metadata["solver_prompt"] = prompt
    metadata["prompt"] = prompt
    return replace(task, metadata=metadata)


def _install_fake_binary(
    bin_dir: Path,
    *,
    basename: str,
    adapter: str,
    outcome: str,
) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / basename
    path.write_text(
        "#!"
        + sys.executable
        + "\n"
        + "import os\n"
        + "import sys\n"
        + "os.execv(sys.executable, [sys.executable, "
        + repr(str(FAKE_CLI))
        + ", '--adapter', "
        + repr(adapter)
        + ", '--outcome', "
        + repr(outcome)
        + ", *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _parent_env(bin_dir: Path) -> dict[str, str]:
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin')}",
        "LC_CTYPE": "C.UTF-8",
        "HOME": "/private/operator-home",
        "OPENAI_API_KEY": "ambient-openai-canary",
        "ANTHROPIC_API_KEY": "ambient-anthropic-canary",
    }


def _make_writable(path: Path) -> None:
    if not path.exists():
        return
    for item in [path, *path.rglob("*")]:
        item.chmod(item.stat().st_mode | 0o200)


def _model_packet():
    return build_model_packet(
        case_packet=CasePacketSchema(
            candidate_id="cand-1",
            case_id="case-1",
            court="S.D.N.Y.",
            docket_number="1:26-cv-1",
            generated_at=datetime(2026, 5, 14, tzinfo=UTC),
            documents=(
                _document("complaint", DocumentRole.COMPLAINT, 1),
                _document("mtd-memo", DocumentRole.MTD_MEMORANDUM, 34),
            ),
        ),
        prediction_units=(_unit(),),
        texts=(
            PacketText(source_document_id="complaint", text="complaint text"),
            PacketText(source_document_id="mtd-memo", text="motion text"),
        ),
        metadata={"judge": "Judge Example", "nos_macro_category": "securities"},
    )


def _document(
    document_id: str,
    role: DocumentRole,
    docket_entry_number: int,
) -> SourceDocumentProvenance:
    return SourceDocumentProvenance(
        source_provider="case.dev",
        source_case_id="case-dev-1",
        source_document_id=document_id,
        court="S.D.N.Y.",
        docket_number="1:26-cv-1",
        document_role=role,
        retrieved_at=datetime(2026, 5, 14, tzinfo=UTC),
        source_url_or_reference=f"case.dev://{document_id}",
        sha256=sha256_text(f"{document_id} source"),
        is_predecision_material=True,
        is_mounted_for_model=True,
        docket_entry_number=docket_entry_number,
        contains_target_outcome=False,
        packet_section="filings",
    )


def _unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="count_i_issuer",
        count="I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.95,
        source_citations=(SourceCitation(document_id="complaint", page=1),),
    )
