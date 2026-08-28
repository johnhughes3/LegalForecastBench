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
from legalforecast.evals.corpus_manifest import freeze_inputs as freeze_inputs_module
from legalforecast.evals.corpus_manifest.commands import (
    build_manifest_forecast_command,
)
from legalforecast.evals.corpus_manifest.freeze_inputs import (
    ManifestFreezeInputsError,
    ManifestFreezeInputsRequest,
    issue_manifest_freeze_inputs,
    verify_manifest_freeze_inputs,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.schema import (
    BoundSource,
    CorpusManifest,
    ManifestCase,
    ManifestDocument,
    load_signed_manifest_bytes,
)
from legalforecast.evals.inspect_task import render_model_prompt
from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.evals.per_case_runner import _model_packet_from_record
from legalforecast.ingestion import stage_a_lineage_verification
from legalforecast.ingestion.authenticated_read_observer import (
    authenticated_read_scope,
)
from legalforecast.ingestion.provenance import DocumentRole, sha256_text

_ROOT = Path(__file__).resolve().parents[1]
_GENERATED_AT = datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
_RUNTIME_PATHS = (
    "legalforecast/cli.py",
    "legalforecast/evals/corpus_manifest/forecast_entry.py",
    "legalforecast/evals/inspect_task.py",
    "legalforecast/evals/per_case_runner.py",
    "legalforecast/evals/live_model_solver.py",
    "legalforecast/evals/model_registry.py",
    "legalforecast/publication/official_aggregate.py",
    ".github/workflows/run-benchmark.yaml",
    ".github/actions/official-provider-cell/action.yml",
)


def test_runtime_contracts_bind_model_registry_parser() -> None:
    assert all(
        "legalforecast/evals/model_registry.py" in paths
        for role, paths in freeze_inputs_module._RUNTIME_PATHS.items()
        if role in {"prompt", "harness"}
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
        self.anchor_root = root / "v3-anchor"
        self.v3_roots = (root / "v3-a", root / "v3-b", root / "v3-c")
        self.output = root / "freeze-inputs"
        self.historical_rows: list[dict[str, Any]] = []
        self._build_forecast()
        self._build_exclusions()

    def _build_forecast(self) -> None:
        selected = [f"candidate-{index:03d}" for index in range(96)] + [
            f"outside-{index}" for index in range(4)
        ]
        self.selected = selected
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
        self.corpus_manifest = manifest
        _write_json(self.manifest, manifest.to_signed_record())
        digest = manifest.digest()
        self.registry = self.root / "registry.json"
        _write_json(
            self.registry,
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
            model_registry=self.registry,
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
            _write_jsonl(
                root / "target-cohort-selection.jsonl",
                [{"candidate_id": candidate} for candidate in self.selected],
            )
        anchor_card = (
            self.anchor_root
            / "run-cards/project-exact100-supporting-document-successor.json"
        )
        _write_json(
            anchor_card,
            {
                "schema_version": (
                    "legalforecast.exact100_supporting_document_successor.v1"
                ),
                "stage": "project-exact100-supporting-document-successor",
                "status": "completed",
                "selected_case_count": 100,
                "input_paths": [str(self.v2_root.absolute())],
                "input_commitments": {
                    "v2_selection_sha256": (
                        "sha256:"
                        + hashlib.sha256(
                            (
                                self.v2_root / "target-cohort-selection.jsonl"
                            ).read_bytes()
                        ).hexdigest()
                    )
                },
            },
        )
        anchor_digest = hashlib.sha256(anchor_card.read_bytes()).hexdigest()
        for root, predecessor in zip(
            self.v3_roots,
            (self.anchor_root, *self.v3_roots[:-1]),
            strict=True,
        ):
            _write_json(
                root / "run-cards/project-exact100-successor-replacement-v3.json",
                {
                    "predecessor_anchor_sha256": anchor_digest,
                    "input_roots": {"predecessor_root": str(predecessor.absolute())},
                },
            )

    def request(self, **changes: Any) -> ManifestFreezeInputsRequest:
        request = ManifestFreezeInputsRequest(
            cycle_id="cycle-1",
            release_sha=self.release_sha,
            repository_root=self.repository,
            owner_manifest=self.manifest,
            model_registry=self.registry,
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
        self,
        _card: Path,
        _ledger: Path,
        _screened: Path,
        card_bytes: bytes,
        ledger_bytes: bytes,
        screened_bytes: bytes,
    ) -> list[dict[str, Any]]:
        assert card_bytes == self.historical_card.read_bytes()
        assert ledger_bytes == self.historical_ledger.read_bytes()
        assert screened_bytes == self.screened.read_bytes()
        return self.historical_rows

    @staticmethod
    def authenticate_successor(root: Path) -> dict[str, Any]:
        terminal = root / "successor-terminal-exclusions.jsonl"
        selection = root / "target-cohort-selection.jsonl"
        projection: dict[str, Any] = {
            "selection_path": selection,
            "selection_bytes": selection.read_bytes(),
            "selection_records": tuple(
                json.loads(line) for line in selection.read_text().splitlines()
            ),
            "verified_artifact_bytes": {
                str(terminal.absolute()): terminal.read_bytes(),
                str(selection.absolute()): selection.read_bytes(),
            },
        }
        card = root / "run-cards/project-exact100-successor-replacement-v3.json"
        if card.exists():
            projection["anchor_root"] = root.parent / "v3-anchor"
            projection["run_card_path"] = card
            projection["run_card_bytes"] = card.read_bytes()
            projection["verified_artifact_bytes"][str(card.absolute())] = (
                card.read_bytes()
            )
        return projection

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
    assert build.run_card["input_paths"]["model_registry"] == str(
        fixture.registry.absolute()
    )
    assert build.run_card["input_commitments"][
        str((fixture.v3_roots[-1] / "target-cohort-selection.jsonl").absolute())
    ]
    assert build.run_card["output_commitments"]["prompt-contract.json"]
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


def test_issue_refuses_missing_owner_signature_bead(fixture: _Fixture) -> None:
    path = fixture.forecast / "manifest-mode-run-record.json"
    record = json.loads(path.read_bytes())
    record["owner_signature_reference"].pop("bead_id")
    _write_json(path, record)

    with pytest.raises(ManifestFreezeInputsError, match="bead_id"):
        fixture.issue()


def test_issue_replays_registry_release_anchor(fixture: _Fixture) -> None:
    records = json.loads(fixture.registry.read_bytes())
    for record in records:
        record["release_timestamp"] = "2027-01-01T00:00:00Z"
    _write_json(fixture.registry, records)
    entries = require_official_registry_entries(
        load_model_registry_bytes(fixture.registry.read_bytes()).entries
    )
    run_record_path = fixture.forecast / "manifest-mode-run-record.json"
    run_record = json.loads(run_record_path.read_bytes())
    run_record["evaluation_models"] = registry_record(entries)
    run_record["evaluation_release_anchor"] = earliest_eligible_decision_date(
        entries
    ).isoformat()
    _write_json(run_record_path, run_record)

    with pytest.raises(ValueError, match="precedes the evaluation-registry"):
        fixture.issue()


def test_issue_refuses_model_registry_different_from_run_record(
    fixture: _Fixture,
) -> None:
    records = json.loads(fixture.registry.read_bytes())
    records[0]["display_name"] = "Different authenticated model"
    _write_json(fixture.registry, records)

    with pytest.raises(ManifestFreezeInputsError, match="authenticated registry"):
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


def test_issue_refuses_historical_bytes_changed_during_authentication(
    fixture: _Fixture,
) -> None:
    def mutate_historical(
        _card: Path,
        _ledger: Path,
        _screened: Path,
        _card_bytes: bytes,
        _ledger_bytes: bytes,
        _screened_bytes: bytes,
    ) -> list[dict[str, Any]]:
        _write_json(fixture.historical_card, {"mutated": True})
        return fixture.historical_rows

    with pytest.raises(ManifestFreezeInputsError, match="changed during replay"):
        issue_manifest_freeze_inputs(
            fixture.request(),
            authenticate_historical=mutate_historical,
            authenticate_v2=fixture.authenticate_successor,
            authenticate_v3=fixture.authenticate_successor,
        )


def test_issue_refuses_selected_terminal_exclusion(fixture: _Fixture) -> None:
    path = fixture.v3_roots[-1] / "successor-terminal-exclusions.jsonl"
    row = json.loads(path.read_text(encoding="utf-8"))
    row["candidate_id"] = "candidate-000"
    _write_jsonl(path, [row])
    with pytest.raises(ManifestFreezeInputsError, match="do not reconcile"):
        fixture.issue()


def test_issue_refuses_authenticated_successor_surface_changed_after_replay(
    fixture: _Fixture,
) -> None:
    def mutate_surface(root: Path) -> dict[str, Any]:
        projection = fixture.authenticate_successor(root)
        if root == fixture.v3_roots[-1]:
            selection = root / "target-cohort-selection.jsonl"
            selection.write_bytes(selection.read_bytes() + b"\n")
        return projection

    with pytest.raises(ManifestFreezeInputsError, match="successor bytes changed"):
        issue_manifest_freeze_inputs(
            fixture.request(),
            authenticate_historical=fixture.authenticate_historical,
            authenticate_v2=mutate_surface,
            authenticate_v3=mutate_surface,
        )


def test_stage_a_registry_read_is_rechecked_after_nested_verifier_returns(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "model-registry.json"
    registry.write_bytes(b'{"model": "synthetic"}\n')
    commitment = {
        "model_registry": {
            "path": str(registry.absolute()),
            "sha256": "sha256:" + hashlib.sha256(registry.read_bytes()).hexdigest(),
        }
    }
    captured: dict[Path, bytes] = {}

    with authenticated_read_scope(captured):
        stage_a_lineage_verification.capture_stage_a_committed_file(
            commitment, "model_registry"
        )

    registry.write_bytes(b'{"model": "mutated after replay"}\n')
    assert registry.absolute() in captured
    with pytest.raises(
        ManifestFreezeInputsError,
        match="input changed before publication",
    ):
        freeze_inputs_module._require_snapshots_unchanged(captured)


def test_issue_refuses_v3_root_outside_final_predecessor_chain(
    fixture: _Fixture,
) -> None:
    card = (
        fixture.v3_roots[1] / "run-cards/project-exact100-successor-replacement-v3.json"
    )
    state = json.loads(card.read_bytes())
    state["input_roots"]["predecessor_root"] = str(fixture.v2_root.absolute())
    _write_json(card, state)

    with pytest.raises(ManifestFreezeInputsError, match="predecessor chain"):
        fixture.issue()


def test_issue_refuses_reordered_authenticated_v3_roots(fixture: _Fixture) -> None:
    with pytest.raises(ManifestFreezeInputsError, match="predecessor chain"):
        issue_manifest_freeze_inputs(
            fixture.request(
                v3_roots=(
                    fixture.v3_roots[0],
                    fixture.v3_roots[2],
                    fixture.v3_roots[1],
                )
            ),
            authenticate_historical=fixture.authenticate_historical,
            authenticate_v2=fixture.authenticate_successor,
            authenticate_v3=fixture.authenticate_successor,
        )


def test_issue_refuses_v3_anchor_not_binding_authenticated_v2_selection(
    fixture: _Fixture,
) -> None:
    anchor_card = (
        fixture.anchor_root
        / "run-cards/project-exact100-supporting-document-successor.json"
    )
    record = json.loads(anchor_card.read_bytes())
    record["input_commitments"]["v2_selection_sha256"] = "sha256:" + "0" * 64
    _write_json(anchor_card, record)
    anchor_digest = hashlib.sha256(anchor_card.read_bytes()).hexdigest()
    for root in fixture.v3_roots:
        card = root / "run-cards/project-exact100-successor-replacement-v3.json"
        state = json.loads(card.read_bytes())
        state["predecessor_anchor_sha256"] = anchor_digest
        _write_json(card, state)

    with pytest.raises(ManifestFreezeInputsError, match="bind the supplied v2"):
        fixture.issue()


def test_legacy_historical_adapter_consumes_captured_bytes_during_aba(
    fixture: _Fixture,
) -> None:
    selection = fixture.root / "historical-selection.jsonl"
    _write_jsonl(selection, [{"candidate_id": "synthetic"}])
    _write_json(
        fixture.historical_card,
        {"input_paths": [str(fixture.root / "unused"), str(selection)]},
    )
    card_bytes = fixture.historical_card.read_bytes()
    ledger_bytes = fixture.historical_ledger.read_bytes()
    screened_bytes = fixture.screened.read_bytes()

    def legacy(**kwargs: Any) -> list[dict[str, Any]]:
        assert kwargs["_captured_run_card_bytes"] == card_bytes
        assert kwargs["_captured_output_bytes"] == ledger_bytes
        assert kwargs["_captured_screened_cases_bytes"] == screened_bytes
        _write_json(fixture.historical_card, {"attacker": True})
        fixture.historical_ledger.write_text("attacker\n", encoding="utf-8")
        fixture.screened.write_text("attacker\n", encoding="utf-8")
        fixture.historical_card.write_bytes(card_bytes)
        fixture.historical_ledger.write_bytes(ledger_bytes)
        fixture.screened.write_bytes(screened_bytes)
        return fixture.historical_rows

    authenticate, _authenticate_v2 = freeze_inputs_module._legacy_authenticators(
        legacy_historical_authenticator=legacy,
        legacy_v2_verifier=lambda *_args, **_kwargs: {},
        legacy_v2_replay_args=lambda _card: object(),
        legacy_v2_replay=lambda _args: object(),
    )

    assert tuple(
        authenticate(
            fixture.historical_card,
            fixture.historical_ledger,
            fixture.screened,
            card_bytes,
            ledger_bytes,
            screened_bytes,
        )
    ) == tuple(fixture.historical_rows)


def test_issue_refuses_final_successor_selection_different_from_manifest(
    fixture: _Fixture,
) -> None:
    selection = fixture.v3_roots[-1] / "target-cohort-selection.jsonl"
    _write_jsonl(
        selection,
        [{"candidate_id": candidate} for candidate in fixture.selected[:-1]],
    )

    with pytest.raises(ManifestFreezeInputsError, match="selection differs"):
        fixture.issue()


def test_default_v3_chain_authenticates_once_and_reuses_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The final recursive replay is reused for the two earlier roots."""

    anchor = tmp_path / "anchor"
    roots = tuple(tmp_path / name for name in ("v3-a", "v3-b", "v3-c"))
    (anchor / "run-cards").mkdir(parents=True)
    anchor_card = (
        anchor / "run-cards/project-exact100-supporting-document-successor.json"
    )
    anchor_card.write_bytes(b"{}")
    for root, predecessor in zip(
        roots,
        (anchor, roots[0], roots[1]),
        strict=True,
    ):
        card = root / "run-cards/project-exact100-successor-replacement-v3.json"
        _write_json(
            card,
            {"input_roots": {"predecessor_root": str(predecessor.absolute())}},
        )

    recursive_replays: list[Path] = []
    cached_projections: list[Path] = []

    def authenticate_final_with_snapshot(
        root: Path,
    ) -> tuple[dict[str, Any], dict[Path, bytes]]:
        recursive_replays.append(root)
        return {"anchor_root": anchor}, {}

    def project_cached(root: Path, *, authenticate: Any) -> dict[str, Any]:
        cached_projections.append(root)
        receipt = authenticate(root)
        assert isinstance(receipt, freeze_inputs_module.AuthenticatedV3Root)
        return {"anchor_root": receipt.anchor_root}

    monkeypatch.setattr(
        freeze_inputs_module,
        "_authenticate_v3_with_snapshot",
        authenticate_final_with_snapshot,
    )
    monkeypatch.setattr(
        freeze_inputs_module,
        "verify_exact100_successor_replacement_v3_projection",
        project_cached,
    )

    result = freeze_inputs_module._authenticate_v3_chain(roots)

    assert recursive_replays == [roots[-1]]
    assert cached_projections == [roots[0], roots[1]]
    assert tuple(root for root, _projection in result) == roots


def test_default_v3_chain_refuses_a_root_outside_authenticated_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cached receipts cannot authorize a supplied root outside the chain."""

    anchor = tmp_path / "anchor"
    roots = tuple(tmp_path / name for name in ("v3-a", "v3-b", "v3-c"))
    wrong = tmp_path / "wrong"
    (anchor / "run-cards").mkdir(parents=True)
    anchor_card = (
        anchor / "run-cards/project-exact100-supporting-document-successor.json"
    )
    anchor_card.write_bytes(b"{}")
    for root, predecessor in zip(
        roots,
        (anchor, roots[0], wrong),
        strict=True,
    ):
        _write_json(
            root / "run-cards/project-exact100-successor-replacement-v3.json",
            {"input_roots": {"predecessor_root": str(predecessor.absolute())}},
        )
    _write_json(
        wrong / "run-cards/project-exact100-successor-replacement-v3.json",
        {"input_roots": {"predecessor_root": str(anchor.absolute())}},
    )

    monkeypatch.setattr(
        freeze_inputs_module,
        "_authenticate_v3_with_snapshot",
        lambda _root: ({"anchor_root": anchor}, {}),
    )

    with pytest.raises(
        ManifestFreezeInputsError, match="authenticated predecessor chain"
    ):
        freeze_inputs_module._authenticate_v3_chain(roots)


def test_prediction_units_are_parsed_from_the_captured_bytes(fixture: _Fixture) -> None:
    captured = fixture.units.read_bytes()
    _write_jsonl(fixture.units, [_unit_row("attacker-candidate")])

    units = freeze_inputs_module._prediction_units_from_bytes(
        fixture.corpus_manifest,
        captured,
    )

    assert set(units) == set(fixture.selected)


def test_manifest_and_markdown_are_parsed_from_captured_bytes(
    fixture: _Fixture,
) -> None:
    manifest_bytes = fixture.manifest.read_bytes()
    manifest = load_signed_manifest_bytes(
        manifest_bytes,
        expected_digest=fixture.corpus_manifest.digest(),
    )
    case = manifest.cases[0]
    captured_markdown = {
        document.source_document_id: Path(document.markdown_path).read_bytes()
        for document in case.model_visible_documents
        if document.markdown_path is not None
    }
    fixture.manifest.write_text("{}", encoding="utf-8")
    for document in case.model_visible_documents:
        assert document.markdown_path is not None
        Path(document.markdown_path).write_text("attacker text", encoding="utf-8")

    texts = freeze_inputs_module._verified_case_texts_from_bytes(
        case,
        captured_markdown,
    )

    assert tuple(case.candidate_id for case in manifest.cases) == tuple(
        case.candidate_id for case in fixture.corpus_manifest.cases
    )
    assert all("Synthetic" in text for text in texts.values())


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
