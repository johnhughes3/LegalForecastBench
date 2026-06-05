from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast._json_io import read_jsonl_objects
from legalforecast.evals.inspect_task import HarnessSolver, OfflineMockSolver
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketText,
    build_model_packet,
)
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)
from legalforecast.multiharness.command_adapter import CommandAdapter
from legalforecast.multiharness.lfb_native import LfbNativeAdapter
from legalforecast.multiharness.runner import (
    ModelConfig,
    MultiHarnessRunConfig,
    run_multi_harness,
)
from legalforecast.multiharness.sandbox import sandbox_policy
from legalforecast.multiharness.selection import TaskSelection
from legalforecast.multiharness.spec import (
    AdapterManifest,
    CanonicalTask,
    ContributorCredit,
    TaskIndex,
)
from legalforecast.multiharness.task_loaders import LfbTaskLoader
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)

SHA256 = "sha256:" + "a" * 64


def test_runner_writes_deterministic_artifacts_and_lfb_projection(
    tmp_path: Path,
) -> None:
    packet = _model_packet()
    task = LfbTaskLoader(suite_version="fixture-suite").task_from_record(
        packet.to_record()
    )
    adapter = LfbNativeAdapter()
    solver = OfflineMockSolver(
        solver_id="offline-fixture",
        raw_output=_raw_output(probability=0.7),
        input_tokens=5,
        output_tokens=3,
        estimated_cost=0.01,
    )

    first = run_multi_harness(
        _native_config(
            output_dir=tmp_path / "run-a",
            task=task,
            adapter=adapter,
            packet=packet,
            solver=solver,
        )
    )
    second = run_multi_harness(
        _native_config(
            output_dir=tmp_path / "run-b",
            task=task,
            adapter=adapter,
            packet=packet,
            solver=solver,
        )
    )

    assert first.manifest.request_ids == second.manifest.request_ids
    row = first.rows[0]
    row_dir = first.output_dir / "rows" / row.row_id
    request_record = json.loads((row_dir / "request.json").read_text(encoding="utf-8"))
    assert request_record["request_sha256"] == row.request.request_sha256
    assert (row_dir / "sandbox.plan.json").is_file()
    assert (row_dir / "result.json").is_file()
    assert (row_dir / "private-logs").is_dir()
    assert row.result.status == "succeeded"

    canonical_rows = _jsonl(first.output_dir / "canonical-runs.jsonl")
    lfb_rows = _jsonl(first.output_dir / "lfb" / "runs.jsonl")
    artifact_index = json.loads(
        (first.output_dir / "artifact-index.json").read_text(encoding="utf-8")
    )
    artifact_records = cast(list[dict[str, object]], artifact_index["artifacts"])
    artifact_paths = {artifact["path"] for artifact in artifact_records}
    assert canonical_rows[0]["result_id"] == row.result.result_id
    assert lfb_rows[0]["raw_output"] == _raw_output(probability=0.7)
    assert lfb_rows[0]["model_id"] == "lfb-native:fixture-model"
    assert "lfb/runs.jsonl" in artifact_paths
    assert "canonical-runs.jsonl" in artifact_paths
    assert f"rows/{row.row_id}/request.json" in artifact_paths


def test_runner_resumes_matching_request_hash(tmp_path: Path) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("lfb:case-1:full_packet", "legalforecast_mtd", "lfb_brier")
    output_dir = tmp_path / "run"

    first = run_multi_harness(
        _command_config(output_dir=output_dir, task=task, adapter=adapter)
    )
    second = run_multi_harness(
        _command_config(output_dir=output_dir, task=task, adapter=adapter, resume=True)
    )

    assert second.rows[0].resumed is True
    assert first.rows[0].result.result_id == second.rows[0].result.result_id
    assert first.manifest.run_config_sha256 == second.manifest.run_config_sha256
    assert (first.rows[0].workspace / "run-count.txt").read_text(
        encoding="utf-8"
    ) == "1"


def test_runner_records_failures_and_keeps_lab_outputs_separate(
    tmp_path: Path,
) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("harvey_lab",),
        supported_scoring_modes=("lab_native",),
        fail_run=True,
    )
    task = _task("harvey_lab:module/task", "harvey_lab", "lab_native")

    run = run_multi_harness(
        _command_config(output_dir=tmp_path / "run", task=task, adapter=adapter)
    )

    assert run.rows[0].result.status == "failed"
    assert (run.rows[0].workspace / "private-logs" / "error.txt").is_file()
    lab_rows = _jsonl(run.output_dir / "lab" / "task-results.jsonl")
    assert lab_rows[0]["task_id"] == "harvey_lab:module/task"
    assert lab_rows[0]["result"]["status"] == "failed"
    assert not (run.output_dir / "lfb" / "runs.jsonl").exists()


def test_runner_validates_compatibility_before_row_execution(tmp_path: Path) -> None:
    adapter = _command_adapter(
        tmp_path,
        supported_families=("legalforecast_mtd",),
        supported_scoring_modes=("lfb_brier",),
    )
    task = _task("harvey_lab:module/task", "harvey_lab", "lab_native")
    output_dir = tmp_path / "run"

    with pytest.raises(ValueError, match="no compatible adapter"):
        run_multi_harness(
            _command_config(output_dir=output_dir, task=task, adapter=adapter)
        )

    assert not (output_dir / "rows").exists()


def _native_config(
    *,
    output_dir: Path,
    task: CanonicalTask,
    adapter: LfbNativeAdapter,
    packet: ModelPacket,
    solver: HarnessSolver,
) -> MultiHarnessRunConfig:
    return MultiHarnessRunConfig(
        task_index=_task_index(task),
        selection=TaskSelection.full(),
        adapters=(adapter,),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="fixture-model",
                lfb_packet=packet,
                lfb_solver=solver,
            ),
        ),
        sandbox_policy=_sandbox(),
        output_dir=output_dir,
    )


def _command_config(
    *,
    output_dir: Path,
    task: CanonicalTask,
    adapter: CommandAdapter,
    resume: bool = False,
) -> MultiHarnessRunConfig:
    return MultiHarnessRunConfig(
        task_index=_task_index(task),
        adapters=(adapter,),
        model_configs=(
            ModelConfig(
                adapter_id=adapter.manifest.adapter_id,
                model_key="fixture-model",
            ),
        ),
        sandbox_policy=_sandbox(),
        output_dir=output_dir,
        resume=resume,
    )


def _command_adapter(
    tmp_path: Path,
    *,
    supported_families: tuple[str, ...],
    supported_scoring_modes: tuple[str, ...],
    fail_run: bool = False,
) -> CommandAdapter:
    script = tmp_path / f"adapter_{len(list(tmp_path.glob('adapter_*.py')))}.py"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "import argparse, json, sys",
                f"SUPPORTED_FAMILIES = {supported_families!r}",
                f"SUPPORTED_SCORING_MODES = {supported_scoring_modes!r}",
                f"FAIL_RUN = {fail_run!r}",
                "parser = argparse.ArgumentParser()",
                "sub = parser.add_subparsers(dest='command', required=True)",
                "cap = sub.add_parser('capabilities')",
                "cap.add_argument('--output', required=True)",
                "run = sub.add_parser('run')",
                "run.add_argument('--request', required=True)",
                "run.add_argument('--output', required=True)",
                "run.add_argument('--workspace', required=True)",
                "args = parser.parse_args()",
                "if args.command == 'capabilities':",
                "    payload = {",
                "        'schema_version': (",
                "            'legalforecast.multiharness.adapter_capabilities.v1'",
                "        ),",
                "        'adapter_id': 'command-fixture',",
                "        'adapter_version': '0.1.0',",
                "        'supported_families': list(SUPPORTED_FAMILIES),",
                "        'supported_scoring_modes': list(SUPPORTED_SCORING_MODES),",
                "        'supports_sandbox_policy': True,",
                "        'capabilities_sha256': 'sha256:' + 'a' * 64,",
                "    }",
                "    open(args.output, 'w', encoding='utf-8').write(",
                "        json.dumps(payload)",
                "    )",
                "else:",
                "    if FAIL_RUN:",
                "        print('fixture failure', file=sys.stderr)",
                "        raise SystemExit(2)",
                "    request = json.load(open(args.request, encoding='utf-8'))",
                "    count_path = f'{args.workspace}/run-count.txt'",
                "    try:",
                "        count = int(open(count_path, encoding='utf-8').read()) + 1",
                "    except FileNotFoundError:",
                "        count = 1",
                "    open(count_path, 'w', encoding='utf-8').write(str(count))",
                "    result = {",
                "        'schema_version': 'legalforecast.multiharness.run_result.v1',",
                "        'result_id': request['request_id'] + ':result',",
                "        'request_id': request['request_id'],",
                "        'status': 'succeeded',",
                "        'result_sha256': 'sha256:' + 'b' * 64,",
                "        'artifacts': [],",
                "        'public_summary': {'run_count': count},",
                "    }",
                "    open(args.output, 'w', encoding='utf-8').write(",
                "        json.dumps(result)",
                "    )",
            ]
        ),
        encoding="utf-8",
    )
    manifest = AdapterManifest(
        adapter_id="command-fixture",
        display_name="Command Fixture",
        adapter_version="0.1.0",
        command=(sys.executable, str(script)),
        contributors=(ContributorCredit(role="adapter_author", name="Fixture"),),
    )
    return CommandAdapter(manifest=manifest)


def _task_index(task: CanonicalTask) -> TaskIndex:
    return TaskIndex(
        index_id="fixture-index",
        selection_namespace="fixture",
        tasks=(task,),
        index_sha256=SHA256,
    )


def _task(task_id: str, family: str, scoring_mode: str) -> CanonicalTask:
    return CanonicalTask(
        task_id=task_id,
        family=family,
        scoring_mode=scoring_mode,
        suite_version="fixture-suite",
        source_id=task_id,
        task_sha256=SHA256,
        metadata={},
    )


def _sandbox():
    return sandbox_policy(
        policy_id="fixture",
        backend="docker",
        image="python:3.12-slim",
        mounts=(),
        timeout_seconds=30,
    )


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


def _raw_output(*, probability: float) -> str:
    return json.dumps(
        {
            "case_assessment": "The count is likely dismissed.",
            "predictions": [
                {
                    "unit_id": "count_i_issuer",
                    "probability_fully_dismissed": probability,
                }
            ],
        },
        sort_keys=True,
    )


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl_objects(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"missing JSONL: {item}",
        non_object_message=lambda item, line: f"bad JSONL row {line} in {item}",
    )
