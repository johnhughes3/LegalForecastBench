# pyright: reportPrivateUsage=false

"""Synthetic tests for authenticated manifest freeze-input issuance."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest.commands import (
    build_manifest_forecast_command,
)
from legalforecast.evals.corpus_manifest.freeze_inputs import (
    ManifestFreezeInputsError,
    ManifestFreezeInputsRequest,
    issue_manifest_freeze_inputs,
    verify_manifest_freeze_inputs,
)
from legalforecast.evals.corpus_manifest.schema import (
    BoundSource,
    CorpusManifest,
    ManifestCase,
    ManifestDocument,
)
from legalforecast.evals.inspect_task import render_model_prompt
from legalforecast.evals.per_case_runner import _model_packet_from_record
from legalforecast.ingestion.provenance import DocumentRole, sha256_text

_ROOT = Path(__file__).resolve().parents[1]
_GENERATED_AT = datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
_RUNTIME_PATHS = (
    "legalforecast/evals/corpus_manifest/forecast_entry.py",
    "legalforecast/evals/inspect_task.py",
    "legalforecast/evals/per_case_runner.py",
    "legalforecast/evals/live_model_solver.py",
    "legalforecast/publication/official_aggregate.py",
    ".github/workflows/run-benchmark.yaml",
    ".github/workflows/official-provider-cell.yaml",
)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in rows)
    )


def _unit_row(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "prediction_units": [
            {
                "unit_id": f"{candidate_id}-unit-1",
                "count": "Count I",
                "claim_name": "Synthetic contract claim",
                "defendant_group": "Synthetic Defendant",
                "challenged_by_motion": True,
                "challenge_scope": "entire_claim",
                "unit_confidence": 1.0,
                "should_score": True,
                "source_citations": [
                    {
                        "document_id": f"{candidate_id}-complaint",
                        "excerpt": "Count I",
                    }
                ],
            }
        ],
    }


def _ledger_row(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "court": None,
        "decision_date": None,
        "stage": "eligibility",
        "primary_exclusion_reason": "synthetic_ineligible",
        "reason": "synthetic_ineligible",
        "secondary_exclusion_reasons": [],
        "source_entry_ids": [],
        "source_document_ids": [],
        "related_family_id": None,
        "notes": "Synthetic exclusion fixture.",
    }


def _terminal_row(candidate_id: str, *, schema: str, field: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        field: "synthetic_terminal",
        "schema_version": schema,
        "source_document_id": f"{candidate_id}-document",
    }


def _fake_release(root: Path) -> str:
    for relative in _RUNTIME_PATHS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_ROOT / relative, target)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "synthetic-fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "synthetic-fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "synthetic release"],
        check=True,
        env=env,
    )
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class _Fixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.repository = root / "release"
        self.release_sha = _fake_release(self.repository)
        self.units = root / "prediction-units.jsonl"
        self.selection = root / "selection.jsonl"
        self.manifest = root / "manifest.json"
        self.forecast = root / "forecast"
        self.screened = root / "screened-cases.jsonl"
        self.historical_ledger = root / "historical-exclusions.jsonl"
        self.historical_card = root / "historical-card.json"
        self.v2_root = root / "v2"
        self.v3_roots = (root / "v3-a", root / "v3-b", root / "v3-c")
        self.output = root / "freeze-inputs"
        self.historical_rows: list[dict[str, Any]] = []
        self._build_forecast()
        self._build_exclusions()

    def _build_forecast(self) -> None:
        selected = [f"candidate-{index:03d}" for index in range(96)] + [
            f"outside-{index}" for index in range(4)
        ]
        unit_rows = [_unit_row(candidate) for candidate in selected]
        _write_jsonl(self.units, unit_rows)
        _write_jsonl(
            self.selection,
            [{"candidate_id": candidate, "selected": True} for candidate in selected],
        )
        cases: list[ManifestCase] = []
        for index, candidate in enumerate(selected):
            documents: list[ManifestDocument] = []
            for suffix, role, entry in (
                ("complaint", DocumentRole.COMPLAINT, 1),
                ("motion", DocumentRole.MTD_MEMORANDUM, 2),
            ):
                document_id = f"{candidate}-{suffix}"
                markdown = self.root / "markdown" / candidate / f"{document_id}.md"
                markdown.parent.mkdir(parents=True, exist_ok=True)
                markdown.write_text(
                    f"# Synthetic {suffix}\n\nCount I for {candidate}.\n",
                    encoding="utf-8",
                )
                documents.append(
                    ManifestDocument(
                        source_document_id=document_id,
                        document_role=role,
                        model_visible=True,
                        pdf_path=str(self.root / "pdf" / f"{document_id}.pdf"),
                        pdf_sha256=hashlib.sha256(document_id.encode()).hexdigest(),
                        source_url=f"https://example.invalid/{document_id}",
                        markdown_path=str(markdown),
                        markdown_sha256=hashlib.sha256(
                            markdown.read_bytes()
                        ).hexdigest(),
                        docket_entry_number=entry,
                        byte_role_verdict="match",
                        validation_basis="synthetic_fixture",
                    )
                )
            cases.append(
                ManifestCase(
                    candidate_id=candidate,
                    case_id=candidate,
                    court="D. Example",
                    docket_number=f"1:26-cv-{index:05d}",
                    documents=tuple(documents),
                    decision_date="2026-07-01",
                    target_motion_entry_numbers=(2,),
                )
            )
        manifest = CorpusManifest(
            cycle_id="cycle-1",
            generated_at="2026-08-22T08:00:00Z",
            selection_source=BoundSource(
                path=str(self.selection),
                sha256=hashlib.sha256(self.selection.read_bytes()).hexdigest(),
            ),
            prediction_units_source=BoundSource(
                path=str(self.units),
                sha256=hashlib.sha256(self.units.read_bytes()).hexdigest(),
            ),
            cases=tuple(cases),
        )
        _write_json(self.manifest, manifest.to_signed_record())
        digest = manifest.digest()
        registry = self.root / "registry.json"
        _write_json(
            registry,
            [
                {
                    "provider": "synthetic-provider",
                    "model_id": f"synthetic-model-{index}",
                    "display_name": f"Synthetic Model {index}",
                    "model_version_or_snapshot": f"synthetic-model-{index}-2026-01-01",
                    "release_timestamp": "2026-01-01T00:00:00Z",
                    "release_timestamp_source": "synthetic fixture",
                    "provider_training_cutoff_status": "not_disclosed",
                    "temperature": 0,
                    "top_p": 1,
                    "max_output_tokens": 4096,
                    "network_disabled": True,
                    "search_disabled": True,
                    "tool_policy": "controlled_docket_tool_only",
                    "context_limit": 200000,
                    "pricing_source": "synthetic fixture",
                    "input_token_price": 1.0,
                    "output_token_price": 2.0,
                }
                for index in range(4)
            ],
        )
        build_manifest_forecast_command(
            manifest=self.manifest,
            expected_manifest_digest=digest,
            owner_signature_bead="synthetic-bead",
            owner_approval_line=(
                f"I approve corpus manifest {digest} as the frozen Cycle 1 "
                "forecast corpus."
            ),
            model_registry=registry,
            output_dir=self.forecast,
            generated_at=_GENERATED_AT,
        )

    def _build_exclusions(self) -> None:
        screened = [f"candidate-{index:03d}" for index in range(153)]
        _write_jsonl(
            self.screened,
            [{"candidate": {"docket_id": candidate}} for candidate in screened],
        )
        retained = [_ledger_row(candidate) for candidate in screened[96:147]]
        selected_again = [_ledger_row(candidate) for candidate in screened[:2]]
        self.historical_rows = [*retained, *selected_again]
        _write_jsonl(self.historical_ledger, self.historical_rows)
        _write_json(self.historical_card, {"synthetic": True})
        terminal = screened[147:153]
        distributions = (
            [
                _terminal_row(
                    terminal[0],
                    schema="legalforecast.exact100_successor_terminal_exclusion.v1",
                    field="reason",
                )
            ],
            [
                _terminal_row(
                    candidate,
                    schema="legalforecast.exact100_successor_terminal_exclusion.v2",
                    field="ground",
                )
                for candidate in terminal[1:4]
            ],
            [
                _terminal_row(
                    terminal[4],
                    schema="legalforecast.exact100_successor_terminal_exclusion.v2",
                    field="ground",
                )
            ],
            [
                _terminal_row(
                    terminal[5],
                    schema="legalforecast.exact100_successor_terminal_exclusion.v3",
                    field="ground",
                )
            ],
        )
        for root, rows in zip(
            (self.v2_root, *self.v3_roots), distributions, strict=True
        ):
            _write_jsonl(root / "successor-terminal-exclusions.jsonl", rows)

    def request(self, **changes: Any) -> ManifestFreezeInputsRequest:
        request = ManifestFreezeInputsRequest(
            cycle_id="cycle-1",
            release_sha=self.release_sha,
            repository_root=self.repository,
            owner_manifest=self.manifest,
            forecast_output_dir=self.forecast,
            screened_pool=self.screened,
            historical_exclusion_ledger=self.historical_ledger,
            historical_exclusion_run_card=self.historical_card,
            v2_root=self.v2_root,
            v3_roots=self.v3_roots,
            output_root=self.output,
        )
        return replace(request, **changes)

    def authenticate_historical(
        self, _card: Path, _ledger: Path, _screened: Path
    ) -> list[dict[str, Any]]:
        return self.historical_rows

    @staticmethod
    def authenticate_successor(root: Path) -> dict[str, Any]:
        path = root / "successor-terminal-exclusions.jsonl"
        return {"verified_artifact_bytes": {str(path.absolute()): path.read_bytes()}}

    def issue(self) -> None:
        issue_manifest_freeze_inputs(
            self.request(),
            authenticate_historical=self.authenticate_historical,
            authenticate_v2=self.authenticate_successor,
            authenticate_v3=self.authenticate_successor,
        )


@pytest.fixture
def fixture(tmp_path: Path) -> _Fixture:
    return _Fixture(tmp_path)


def test_issue_and_verify_replay_all_outputs(fixture: _Fixture) -> None:
    fixture.issue()

    build = verify_manifest_freeze_inputs(
        fixture.output,
        authenticate_historical=fixture.authenticate_historical,
        authenticate_v2=fixture.authenticate_successor,
        authenticate_v3=fixture.authenticate_successor,
    )

    assert build.run_card["packet_count"] == 200
    assert build.run_card["selected_candidate_count"] == 100
    assert build.run_card["excluded_candidate_count"] == 57
    assert build.run_card["provider_calls_made"] == 0
    assert set(
        path.relative_to(fixture.output).as_posix()
        for path in fixture.output.rglob("*")
        if path.is_file()
    ) == {
        "prompt-contract.json",
        "scorer-contract.json",
        "harness-contract.json",
        "no-baselines.json",
        "complete-exclusion-ledger.jsonl",
        "run-cards/issue-manifest-freeze-inputs.json",
    }


def test_issue_refuses_existing_output_root(fixture: _Fixture) -> None:
    fixture.output.mkdir()
    with pytest.raises(ManifestFreezeInputsError, match="create-only"):
        fixture.issue()


def test_issue_refuses_prompt_commitment_drift(fixture: _Fixture) -> None:
    path = fixture.forecast / "run-inputs.json"
    record = json.loads(path.read_bytes())
    record["model_packets"][0]["prompt_sha256"] = "0" * 64
    _write_json(path, record)
    with pytest.raises(ManifestFreezeInputsError, match="prompt commitment"):
        fixture.issue()


def test_issue_refuses_paraphrased_owner_manifest_approval(fixture: _Fixture) -> None:
    path = fixture.forecast / "manifest-mode-run-record.json"
    record = json.loads(path.read_bytes())
    digest = record["manifest_sha256"]
    record["owner_signature_reference"]["approval_line"] = (
        f"I generally approve manifest {digest}."
    )
    _write_json(path, record)
    with pytest.raises(ManifestFreezeInputsError, match="not verbatim"):
        fixture.issue()


def test_issue_refuses_self_consistent_packet_not_derived_from_manifest(
    fixture: _Fixture,
) -> None:
    inputs_path = fixture.forecast / "run-inputs.json"
    record_path = fixture.forecast / "manifest-mode-run-record.json"
    run_inputs = json.loads(inputs_path.read_bytes())
    run_record = json.loads(record_path.read_bytes())
    row = run_inputs["model_packets"][0]
    packet_path = fixture.forecast / row["packet_object_key"]
    packet_record = json.loads(packet_path.read_bytes())
    packet_record["court"] = "D. Different"
    packet_bytes = _json_bytes(packet_record)
    packet_path.write_bytes(packet_bytes)
    packet = _model_packet_from_record(packet_record)
    prompt_sha = sha256_text(render_model_prompt(packet, use_docket_tool=False))
    row["packet_sha256"] = hashlib.sha256(packet_bytes).hexdigest()
    row["packet_size_bytes"] = len(packet_bytes)
    row["prompt_sha256"] = prompt_sha
    pair = f"{row['candidate_id']}:{row['ablation']}"
    run_record["prompt_commitments"][pair] = prompt_sha
    _write_json(inputs_path, run_inputs)
    _write_json(record_path, run_record)
    with pytest.raises(ManifestFreezeInputsError, match="signed manifest"):
        fixture.issue()


def test_issue_refuses_packet_byte_drift(fixture: _Fixture) -> None:
    run_inputs = json.loads((fixture.forecast / "run-inputs.json").read_bytes())
    packet = fixture.forecast / run_inputs["model_packets"][0]["packet_object_key"]
    packet.write_bytes(packet.read_bytes() + b" ")
    with pytest.raises(ManifestFreezeInputsError, match="packet bytes"):
        fixture.issue()


def test_issue_refuses_runtime_source_different_from_release(fixture: _Fixture) -> None:
    path = fixture.repository / _RUNTIME_PATHS[0]
    path.write_bytes(path.read_bytes() + b"\n# drift\n")
    with pytest.raises(ManifestFreezeInputsError, match="release bytes"):
        fixture.issue()


def test_issue_refuses_incomplete_historical_ledger(fixture: _Fixture) -> None:
    fixture.historical_rows.pop()
    _write_jsonl(fixture.historical_ledger, fixture.historical_rows)
    with pytest.raises(ManifestFreezeInputsError, match="must have 53 rows"):
        fixture.issue()


def test_issue_refuses_selected_terminal_exclusion(fixture: _Fixture) -> None:
    path = fixture.v3_roots[-1] / "successor-terminal-exclusions.jsonl"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["candidate_id"] = "candidate-000"
    _write_jsonl(path, [row])
    with pytest.raises(ManifestFreezeInputsError, match="do not reconcile"):
        fixture.issue()


@pytest.mark.parametrize("root_index", [0, 3])
def test_issue_refuses_unauthenticated_successor_terminal_bytes(
    fixture: _Fixture, root_index: int
) -> None:
    roots = (fixture.v2_root, *fixture.v3_roots)

    def unauthenticated(root: Path) -> dict[str, Any]:
        if root == roots[root_index]:
            return {"verified_artifact_bytes": {}}
        return fixture.authenticate_successor(root)

    with pytest.raises(ManifestFreezeInputsError, match="lacks terminal bytes"):
        issue_manifest_freeze_inputs(
            fixture.request(),
            authenticate_historical=fixture.authenticate_historical,
            authenticate_v2=unauthenticated,
            authenticate_v3=unauthenticated,
        )


def test_verify_refuses_unexpected_output_path(fixture: _Fixture) -> None:
    fixture.issue()
    (fixture.output / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(ManifestFreezeInputsError, match="unexpected paths"):
        verify_manifest_freeze_inputs(
            fixture.output,
            authenticate_historical=fixture.authenticate_historical,
            authenticate_v2=fixture.authenticate_successor,
            authenticate_v3=fixture.authenticate_successor,
        )
