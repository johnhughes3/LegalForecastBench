# pyright: reportPrivateUsage=false

"""Issue the generic freeze inputs for an owner-signed manifest forecast.

The official workflow still consumes the original thirteen-artifact freeze.
Manifest mode supplies the corpus, units, packets, and model registry through a
different producer, so this module closes the five remaining observational
artifacts without pretending that fixtures or prose are executable authority.
Every output is reproduced from authenticated lineage and the exact release
bytes that will execute the forecast.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.contracts.schemas import (
    EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1,
    MANIFEST_FREEZE_INPUTS_RUN_CARD_V1,
    MANIFEST_FREEZE_RUNTIME_CONTRACT_V1,
    MANIFEST_MODE_FORECAST_RUN_RECORD_V1,
    NO_BASELINES_V1,
)
from legalforecast.evals.corpus_manifest.forecast_entry import (
    _case_packet,
    _model_packet,
    _prediction_units_from_bytes,
    _require_release_anchor,
    _verified_case_texts_from_bytes,
)
from legalforecast.evals.corpus_manifest.freeze_input_surfaces import (
    snapshot_verified_artifacts,
)
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.corpus_manifest.schema import load_signed_manifest_bytes
from legalforecast.evals.inspect_task import render_model_prompt
from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry_bytes,
    require_official_registry_entries,
)
from legalforecast.evals.per_case_runner import _model_packet_from_record
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_v3.cli import (
    authenticate_exact100_successor_v3_root_with_snapshot,
)
from legalforecast.ingestion.exact100_successor_v3.downstream import (
    AuthenticatedV3Root,
    verify_exact100_successor_replacement_v3_projection,
)
from legalforecast.ingestion.provenance import sha256_text
from legalforecast.selection.exclusion_ledger import merge_exclusion_ledger_records

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE_SHA = re.compile(r"[0-9a-f]{40}\Z")
_STAGE: Final = "issue-manifest-freeze-inputs"
_OUTPUTS: Final[Mapping[str, str]] = {
    "prompt": "prompt-contract.json",
    "scorer": "scorer-contract.json",
    "harness": "harness-contract.json",
    "baselines": "no-baselines.json",
    "exclusions": "complete-exclusion-ledger.jsonl",
    "run_card": "run-cards/issue-manifest-freeze-inputs.json",
}
_RUNTIME_PATHS: Final[Mapping[str, tuple[str, ...]]] = {
    "prompt": (
        "legalforecast/evals/corpus_manifest/forecast_entry.py",
        "legalforecast/evals/inspect_task.py",
        "legalforecast/evals/per_case_runner.py",
        "legalforecast/evals/live_model_solver.py",
        "legalforecast/evals/model_registry.py",
    ),
    "scorer": ("legalforecast/publication/official_aggregate.py",),
    "harness": (
        "legalforecast/cli.py",
        "legalforecast/evals/per_case_runner.py",
        "legalforecast/evals/live_model_solver.py",
        "legalforecast/evals/model_registry.py",
        ".github/workflows/run-benchmark.yaml",
        ".github/workflows/official-provider-cell.yaml",
    ),
}

V2Authenticator = Callable[[Path], Mapping[str, Any]]
V3Authenticator = Callable[[Path], Mapping[str, Any]]
LegacyHistoricalAuthenticator = Callable[..., Sequence[Mapping[str, Any]]]
LegacyV2Verifier = Callable[..., Mapping[str, Any]]
LegacyV2ReplayArgs = Callable[[Mapping[str, object]], Any]
LegacyV2Replay = Callable[[Any], Any]


class ManifestFreezeInputsError(ValueError):
    """Raised when generic manifest freeze inputs cannot be authenticated."""


HistoricalExclusionAuthenticator = Callable[
    [Path, Path, Path, bytes, bytes, bytes], Sequence[Mapping[str, Any]]
]


@dataclass(frozen=True, slots=True)
class ManifestFreezeInputsRequest:
    """All external inputs to one deterministic issuance."""

    cycle_id: str
    release_sha: str
    repository_root: Path
    owner_manifest: Path
    model_registry: Path
    forecast_output_dir: Path
    screened_pool: Path
    historical_exclusion_ledger: Path
    historical_exclusion_run_card: Path
    v2_root: Path
    v3_roots: tuple[Path, ...]
    output_root: Path

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ManifestFreezeInputsError("cycle_id is required")
        if _RELEASE_SHA.fullmatch(self.release_sha) is None:
            raise ManifestFreezeInputsError(
                "release_sha must be a lowercase 40-character git SHA"
            )
        if len(self.v3_roots) != 3:
            raise ManifestFreezeInputsError("exactly three v3 roots are required")


@dataclass(frozen=True, slots=True)
class ManifestFreezeInputsBuild:
    """Reproducible output payloads plus their completed run card."""

    payloads: Mapping[str, bytes]
    run_card: Mapping[str, Any]
    input_snapshots: Mapping[Path, bytes]


def issue_manifest_freeze_inputs_command(
    *,
    cycle_id: str,
    release_sha: str,
    repository_root: Path,
    owner_manifest: Path,
    model_registry: Path,
    forecast_output_dir: Path,
    screened_pool: Path,
    historical_exclusion_ledger: Path,
    historical_exclusion_run_card: Path,
    v2_root: Path,
    v3_roots: tuple[Path, ...],
    output_root: Path,
    legacy_historical_authenticator: LegacyHistoricalAuthenticator,
    legacy_v2_verifier: LegacyV2Verifier,
    legacy_v2_replay_args: LegacyV2ReplayArgs,
    legacy_v2_replay: LegacyV2Replay,
) -> ManifestFreezeInputsBuild:
    """CLI boundary for create-only issuance through legacy lineage replay."""

    authenticate_historical, authenticate_v2 = _legacy_authenticators(
        legacy_historical_authenticator=legacy_historical_authenticator,
        legacy_v2_verifier=legacy_v2_verifier,
        legacy_v2_replay_args=legacy_v2_replay_args,
        legacy_v2_replay=legacy_v2_replay,
    )
    return issue_manifest_freeze_inputs(
        ManifestFreezeInputsRequest(
            cycle_id=cycle_id,
            release_sha=release_sha,
            repository_root=repository_root,
            owner_manifest=owner_manifest,
            model_registry=model_registry,
            forecast_output_dir=forecast_output_dir,
            screened_pool=screened_pool,
            historical_exclusion_ledger=historical_exclusion_ledger,
            historical_exclusion_run_card=historical_exclusion_run_card,
            v2_root=v2_root,
            v3_roots=v3_roots,
            output_root=output_root,
        ),
        authenticate_historical=authenticate_historical,
        authenticate_v2=authenticate_v2,
    )


def verify_manifest_freeze_inputs_command(
    *,
    output_root: Path,
    legacy_historical_authenticator: LegacyHistoricalAuthenticator,
    legacy_v2_verifier: LegacyV2Verifier,
    legacy_v2_replay_args: LegacyV2ReplayArgs,
    legacy_v2_replay: LegacyV2Replay,
) -> ManifestFreezeInputsBuild:
    """CLI boundary for full replay verification through legacy lineage."""

    authenticate_historical, authenticate_v2 = _legacy_authenticators(
        legacy_historical_authenticator=legacy_historical_authenticator,
        legacy_v2_verifier=legacy_v2_verifier,
        legacy_v2_replay_args=legacy_v2_replay_args,
        legacy_v2_replay=legacy_v2_replay,
    )
    return verify_manifest_freeze_inputs(
        output_root,
        authenticate_historical=authenticate_historical,
        authenticate_v2=authenticate_v2,
    )


def issue_manifest_freeze_inputs(
    request: ManifestFreezeInputsRequest,
    *,
    authenticate_historical: HistoricalExclusionAuthenticator,
    authenticate_v2: V2Authenticator,
    authenticate_v3: V3Authenticator | None = None,
) -> ManifestFreezeInputsBuild:
    """Authenticate, reproduce, and create-only publish all six outputs."""

    if request.output_root.exists():
        raise ManifestFreezeInputsError(
            f"output_root already exists; refusing create-only issuance: "
            f"{request.output_root}"
        )
    build = build_manifest_freeze_inputs(
        request,
        authenticate_historical=authenticate_historical,
        authenticate_v2=authenticate_v2,
        authenticate_v3=authenticate_v3,
    )
    _require_snapshots_unchanged(build.input_snapshots)
    _publish_create_only(request.output_root, build.payloads)
    _verify_published(request.output_root, build.payloads)
    _require_snapshots_unchanged(build.input_snapshots)
    return build


def verify_manifest_freeze_inputs(
    output_root: Path,
    *,
    authenticate_historical: HistoricalExclusionAuthenticator,
    authenticate_v2: V2Authenticator,
    authenticate_v3: V3Authenticator | None = None,
) -> ManifestFreezeInputsBuild:
    """Replay one completed issuance from its run card and exact input paths."""

    card_path = output_root / _OUTPUTS["run_card"]
    card_bytes = _read_regular(card_path, "manifest freeze-input run card")
    card = _json_object(card_bytes, card_path)
    if (
        card.get("schema_version") != str(MANIFEST_FREEZE_INPUTS_RUN_CARD_V1)
        or card.get("stage") != _STAGE
        or card.get("status") != "completed"
        or card.get("provider_calls_made") != 0
        or card.get("paid_activity_executed") is not False
    ):
        raise ManifestFreezeInputsError("invalid completed freeze-input run card")
    inputs = _mapping(card.get("input_paths"), "run-card input_paths")
    roots = _string_sequence(inputs.get("v3_roots"), "v3_roots")
    request = ManifestFreezeInputsRequest(
        cycle_id=_required_str(card, "cycle_id"),
        release_sha=_required_str(card, "release_sha"),
        repository_root=Path(_required_str(inputs, "repository_root")),
        owner_manifest=Path(_required_str(inputs, "owner_manifest")),
        model_registry=Path(_required_str(inputs, "model_registry")),
        forecast_output_dir=Path(_required_str(inputs, "forecast_output_dir")),
        screened_pool=Path(_required_str(inputs, "screened_pool")),
        historical_exclusion_ledger=Path(
            _required_str(inputs, "historical_exclusion_ledger")
        ),
        historical_exclusion_run_card=Path(
            _required_str(inputs, "historical_exclusion_run_card")
        ),
        v2_root=Path(_required_str(inputs, "v2_root")),
        v3_roots=tuple(Path(value) for value in roots),
        output_root=output_root,
    )
    build = build_manifest_freeze_inputs(
        request,
        authenticate_historical=authenticate_historical,
        authenticate_v2=authenticate_v2,
        authenticate_v3=authenticate_v3,
    )
    expected_card = build.payloads[_OUTPUTS["run_card"]]
    if card_bytes != expected_card:
        raise ManifestFreezeInputsError("freeze-input run card does not reproduce")
    _verify_published(output_root, build.payloads)
    _require_snapshots_unchanged(build.input_snapshots)
    return build


def build_manifest_freeze_inputs(
    request: ManifestFreezeInputsRequest,
    *,
    authenticate_historical: HistoricalExclusionAuthenticator,
    authenticate_v2: V2Authenticator,
    authenticate_v3: V3Authenticator | None = None,
) -> ManifestFreezeInputsBuild:
    """Build exact output bytes in memory without publishing them."""

    snapshots: dict[Path, bytes] = {}
    runtime = _runtime_snapshots(request, snapshots)
    prompt_replay, selected_ids = _prompt_replay(request, snapshots)
    exclusions = _exclusion_payload(
        request,
        selected_ids=selected_ids,
        snapshots=snapshots,
        authenticate_historical=authenticate_historical,
        authenticate_v2=authenticate_v2,
        authenticate_v3=authenticate_v3,
    )
    contracts = {
        role: canonical_json_bytes(
            {
                "schema_version": str(MANIFEST_FREEZE_RUNTIME_CONTRACT_V1),
                "artifact_role": role,
                "cycle_id": request.cycle_id,
                "release_sha": request.release_sha,
                "runtime_files": [runtime[path] for path in paths],
                "required_eval_run_case_flags": ["--no-docket-tool"],
                "use_docket_tool": False,
                "prompt_replay": prompt_replay,
            },
            error_type=ManifestFreezeInputsError,
            error_message=f"{role} runtime contract is not canonical JSON",
        )
        for role, paths in _RUNTIME_PATHS.items()
    }
    payloads: dict[str, bytes] = {
        _OUTPUTS["prompt"]: contracts["prompt"],
        _OUTPUTS["scorer"]: contracts["scorer"],
        _OUTPUTS["harness"]: contracts["harness"],
        _OUTPUTS["baselines"]: canonical_json_bytes(
            {
                "schema_version": str(NO_BASELINES_V1),
                "cycle_id": request.cycle_id,
                "status": "unavailable",
                "reason": "No frozen historical baseline corpus exists for Cycle 1.",
            },
            error_type=ManifestFreezeInputsError,
            error_message="no-baselines sentinel is not canonical JSON",
        ),
        _OUTPUTS["exclusions"]: exclusions,
    }
    output_commitments = {
        name: _sha(payload) for name, payload in sorted(payloads.items())
    }
    input_paths = _request_input_paths(request)
    run_card = {
        "schema_version": str(MANIFEST_FREEZE_INPUTS_RUN_CARD_V1),
        "stage": _STAGE,
        "status": "completed",
        "cycle_id": request.cycle_id,
        "release_sha": request.release_sha,
        "input_paths": input_paths,
        "input_commitments": {
            str(path.absolute()): _sha(payload)
            for path, payload in sorted(
                snapshots.items(), key=lambda item: str(item[0])
            )
        },
        "output_paths": {
            name: str((request.output_root / name).absolute())
            for name in sorted(payloads)
        },
        "output_commitments": output_commitments,
        "selected_candidate_count": len(selected_ids),
        "excluded_candidate_count": 57,
        "packet_count": 200,
        "provider_calls_made": 0,
        "paid_activity_executed": False,
    }
    payloads[_OUTPUTS["run_card"]] = canonical_json_bytes(
        run_card,
        error_type=ManifestFreezeInputsError,
        error_message="manifest freeze-input run card is not canonical JSON",
    )
    return ManifestFreezeInputsBuild(
        payloads=payloads,
        run_card=run_card,
        input_snapshots=snapshots,
    )


def _runtime_snapshots(
    request: ManifestFreezeInputsRequest, snapshots: dict[Path, bytes]
) -> dict[str, dict[str, Any]]:
    if request.repository_root.is_symlink():
        raise ManifestFreezeInputsError("repository_root must not be a symlink")
    root = request.repository_root.resolve()
    if not root.is_dir():
        raise ManifestFreezeInputsError("repository_root must be a real directory")
    head = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    if head != request.release_sha:
        raise ManifestFreezeInputsError(
            f"repository HEAD {head} differs from release_sha {request.release_sha}"
        )
    result: dict[str, dict[str, Any]] = {}
    for relative in sorted(
        {path for paths in _RUNTIME_PATHS.values() for path in paths}
    ):
        path = root / relative
        payload = _snapshot(path, snapshots, f"runtime source {relative}")
        committed = _git(root, "show", f"{request.release_sha}:{relative}")
        if payload != committed:
            raise ManifestFreezeInputsError(
                f"runtime source differs from release bytes: {relative}"
            )
        result[relative] = {
            "path": relative,
            "sha256": _sha(payload),
            "size_bytes": len(payload),
        }
    return result


def _prompt_replay(
    request: ManifestFreezeInputsRequest, snapshots: dict[Path, bytes]
) -> tuple[dict[str, Any], frozenset[str]]:
    run_record_path = request.forecast_output_dir / "manifest-mode-run-record.json"
    run_inputs_path = request.forecast_output_dir / "run-inputs.json"
    run_record_bytes = _snapshot(run_record_path, snapshots, "manifest run record")
    run_inputs_bytes = _snapshot(run_inputs_path, snapshots, "run-inputs manifest")
    manifest_bytes = _snapshot(request.owner_manifest, snapshots, "owner manifest")
    registry_bytes = _snapshot(request.model_registry, snapshots, "model registry")
    run_record = _json_object(run_record_bytes, run_record_path)
    run_inputs = _json_object(run_inputs_bytes, run_inputs_path)
    digest = _required_sha(run_record, "manifest_sha256")
    manifest = load_signed_manifest_bytes(manifest_bytes, expected_digest=digest)
    registry = load_model_registry_bytes(registry_bytes)
    entries = require_official_registry_entries(registry.entries)
    release_anchor = earliest_eligible_decision_date(entries)
    if (
        manifest.cycle_id != request.cycle_id
        or run_inputs.get("cycle_id") != request.cycle_id
    ):
        raise ManifestFreezeInputsError("manifest forecast cycle_id differs")
    signature = _mapping(
        run_record.get("owner_signature_reference"), "owner_signature_reference"
    )
    expected_approval = (
        f"I approve corpus manifest {digest} as the frozen Cycle 1 forecast corpus."
    )
    bead_id = _required_str(signature, "bead_id")
    if _required_str(signature, "approval_line") != expected_approval:
        raise ManifestFreezeInputsError("owner manifest approval line is not verbatim")
    if (
        run_record.get("schema_version") != str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1)
        or run_record.get("entry_mode") != "owner_signed_manifest"
        or run_record.get("packet_ablations") != ["full_packet", "metadata_only"]
        or run_record.get("case_count") != 100
        or run_record.get("packet_count") != 200
        or run_record.get("provider_calls_made") != 0
        or run_record.get("docket_tool_enabled") is not False
        or run_record.get("required_eval_run_case_flags") != ["--no-docket-tool"]
    ):
        raise ManifestFreezeInputsError(
            "manifest run record is not the 100x2 no-tool build"
        )
    if (
        run_record.get("evaluation_models") != registry_record(entries)
        or run_record.get("evaluation_release_anchor") != release_anchor.isoformat()
        or run_record.get("prediction_units_source")
        != manifest.prediction_units_source.to_record()
        or run_record.get("selection_source") != manifest.selection_source.to_record()
    ):
        raise ManifestFreezeInputsError(
            "manifest run record differs from authenticated registry or sources"
        )
    generated_at_text = _required_str(run_record, "generated_at")
    if run_inputs.get("generated_at") != generated_at_text:
        raise ManifestFreezeInputsError("run-inputs generated_at differs")
    try:
        generated_at = datetime.fromisoformat(generated_at_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ManifestFreezeInputsError("manifest run generated_at is invalid") from exc
    if generated_at.tzinfo is None:
        raise ManifestFreezeInputsError("manifest run generated_at lacks timezone")

    units_path = Path(manifest.prediction_units_source.path)
    units_bytes = _snapshot(units_path, snapshots, "manifest prediction units")
    units = _prediction_units_from_bytes(manifest, units_bytes)
    cases = {case.candidate_id: case for case in manifest.cases}
    case_inputs: dict[str, tuple[Mapping[str, str], Any]] = {}
    for case in manifest.cases:
        _require_release_anchor(case, release_anchor=release_anchor)
        document_bytes: dict[str, bytes] = {}
        for document in case.model_visible_documents:
            if document.markdown_path is None:
                raise ManifestFreezeInputsError(
                    f"{case.candidate_id}: visible document lacks markdown path"
                )
            document_bytes[document.source_document_id] = _snapshot(
                Path(document.markdown_path),
                snapshots,
                f"manifest markdown {case.candidate_id}/{document.source_document_id}",
            )
        texts = _verified_case_texts_from_bytes(case, document_bytes)
        case_inputs[case.candidate_id] = (
            texts,
            _case_packet(case, texts=texts, generated_at=generated_at),
        )
    rows = _record_sequence(run_inputs.get("model_packets"), "model_packets")
    if len(rows) != 200:
        raise ManifestFreezeInputsError("run-inputs must contain exactly 200 packets")
    commitments: dict[str, str] = {}
    seen_pairs: set[tuple[str, str]] = set()
    selected: set[str] = set()
    for row in rows:
        key = _required_str(row, "packet_object_key")
        packet_path = (request.forecast_output_dir / key).resolve()
        try:
            packet_path.relative_to(request.forecast_output_dir.resolve())
        except ValueError as exc:
            raise ManifestFreezeInputsError(
                f"packet escapes output root: {key}"
            ) from exc
        payload = _snapshot(packet_path, snapshots, f"packet {key}")
        if _sha(payload) != _required_sha(row, "packet_sha256"):
            raise ManifestFreezeInputsError(
                f"packet bytes differ from run-inputs: {key}"
            )
        if row.get("packet_size_bytes") != len(payload):
            raise ManifestFreezeInputsError(
                f"packet size differs from run-inputs: {key}"
            )
        packet_record = _json_object(payload, packet_path)
        packet = _model_packet_from_record(packet_record)
        case = cases.get(packet.candidate_id)
        if case is None:
            raise ManifestFreezeInputsError(
                "packet candidate is absent from signed manifest: "
                f"{packet.candidate_id}"
            )
        texts, case_packet = case_inputs[packet.candidate_id]
        expected_packet = _model_packet(
            case,
            case_packet=case_packet,
            texts=texts,
            units=units.get(packet.candidate_id, ()),
            ablation=packet.ablation,
        )
        if packet_record != expected_packet.to_record():
            raise ManifestFreezeInputsError(
                f"packet does not replay from signed manifest: {key}"
            )
        expected_row = {
            "ablation": packet.ablation.value,
            "candidate_id": packet.candidate_id,
            "case_id": packet.case_id,
            "decision_date": packet.decision_date,
            "source_document_ids": sorted(packet.source_hashes),
            "source_hashes": dict(packet.source_hashes),
        }
        if any(row.get(name) != value for name, value in expected_row.items()):
            raise ManifestFreezeInputsError(
                f"run-input row differs from packet identity: {key}"
            )
        prompt_sha = sha256_text(render_model_prompt(packet, use_docket_tool=False))
        if prompt_sha != _required_sha(row, "prompt_sha256"):
            raise ManifestFreezeInputsError(f"prompt commitment does not replay: {key}")
        pair = (packet.candidate_id, packet.ablation.value)
        if pair in seen_pairs:
            raise ManifestFreezeInputsError(
                f"duplicate candidate/ablation packet: {pair}"
            )
        seen_pairs.add(pair)
        selected.add(packet.candidate_id)
        commitments[f"{pair[0]}:{pair[1]}"] = prompt_sha
    expected_pairs = {
        (candidate, ablation)
        for candidate in selected
        for ablation in ("full_packet", "metadata_only")
    }
    manifest_ids = {case.candidate_id for case in manifest.cases}
    if len(selected) != 100 or seen_pairs != expected_pairs or selected != manifest_ids:
        raise ManifestFreezeInputsError(
            "packet matrix differs from signed 100-case manifest"
        )
    if run_record.get("prompt_commitments") != commitments:
        raise ManifestFreezeInputsError("run-record prompt commitments differ")
    return (
        {
            "manifest_sha256": digest,
            "owner_manifest_bytes_sha256": _sha(manifest_bytes),
            "model_registry_sha256": _sha(registry_bytes),
            "owner_signature_reference": {
                "approval_line": expected_approval,
                "bead_id": bead_id,
            },
            "evaluation_models": registry_record(entries),
            "evaluation_release_anchor": release_anchor.isoformat(),
            "run_inputs_sha256": _sha(run_inputs_bytes),
            "run_record_sha256": _sha(run_record_bytes),
            "packet_count": 200,
            "candidate_count": 100,
            "prompt_commitments": dict(sorted(commitments.items())),
        },
        frozenset(selected),
    )


def _exclusion_payload(
    request: ManifestFreezeInputsRequest,
    *,
    selected_ids: frozenset[str],
    snapshots: dict[Path, bytes],
    authenticate_historical: HistoricalExclusionAuthenticator,
    authenticate_v2: V2Authenticator,
    authenticate_v3: V3Authenticator | None,
) -> bytes:
    screened_bytes = _snapshot(request.screened_pool, snapshots, "screened pool")
    screened_rows = _jsonl(screened_bytes, request.screened_pool)
    screened_ids = frozenset(_screened_candidate_id(row) for row in screened_rows)
    if (
        len(screened_rows) != 153
        or len(screened_ids) != 153
        or len(selected_ids & screened_ids) != 96
    ):
        raise ManifestFreezeInputsError(
            "Cycle 1 screened/selected partition must be 153 and 96"
        )
    historical_card_bytes = _snapshot(
        request.historical_exclusion_run_card,
        snapshots,
        "historical exclusion run card",
    )
    historical_ledger_bytes = _snapshot(
        request.historical_exclusion_ledger,
        snapshots,
        "historical exclusion ledger",
    )
    if not historical_card_bytes:
        raise ManifestFreezeInputsError("historical exclusion run card is empty")
    historical = tuple(
        authenticate_historical(
            request.historical_exclusion_run_card,
            request.historical_exclusion_ledger,
            request.screened_pool,
            historical_card_bytes,
            historical_ledger_bytes,
            screened_bytes,
        )
    )
    _snapshot(
        request.historical_exclusion_run_card,
        snapshots,
        "historical exclusion run card",
    )
    _snapshot(
        request.historical_exclusion_ledger,
        snapshots,
        "historical exclusion ledger",
    )
    _snapshot(request.screened_pool, snapshots, "screened pool")
    if tuple(_jsonl(historical_ledger_bytes, request.historical_exclusion_ledger)) != (
        historical
    ):
        raise ManifestFreezeInputsError(
            "historical exclusion bytes differ from authenticated rows"
        )
    if len(historical) != 53:
        raise ManifestFreezeInputsError("historical exclusion ledger must have 53 rows")
    retained = tuple(
        row
        for row in historical
        if _required_str(row, "candidate_id") not in selected_ids
    )
    if len(retained) != 51:
        raise ManifestFreezeInputsError("historical ledger must retain exactly 51 rows")
    terminal_records: list[Mapping[str, Any]] = []
    v2 = authenticate_v2(request.v2_root)
    terminal_records.extend(_terminal_records(request.v2_root, v2, snapshots))
    v2_selection_path = request.v2_root / "target-cohort-selection.jsonl"
    v2_selection_bytes = snapshots.get(v2_selection_path.absolute())
    if not isinstance(v2_selection_bytes, bytes):
        raise ManifestFreezeInputsError(
            "authenticated v2 projection lacks its selection receipt"
        )
    if authenticate_v3 is None:
        # The real v3 authenticator recursively replays every predecessor.  Do
        # that once for the final root, retain the bytes it read, then project
        # the earlier roots against the chain proof it established.  The
        # retained bytes are rechecked before publication, while
        # snapshot_verified_artifacts keeps every projection byte stable.
        v3_projections = _authenticate_v3_chain(request.v3_roots, snapshots=snapshots)
    else:
        v3_projections = tuple(
            (root, authenticate_v3(root)) for root in request.v3_roots
        )
    final_v3: Mapping[str, Any] | None = None
    expected_predecessor: Path | None = None
    authenticated_anchor: Path | None = None
    anchor_digest: str | None = None
    for root, projection in v3_projections:
        final_v3 = projection
        terminal_records.extend(_terminal_records(root, final_v3, snapshots))
        card_path = root / "run-cards/project-exact100-successor-replacement-v3.json"
        card_bytes = snapshots.get(card_path.absolute())
        if not isinstance(card_bytes, bytes):
            raise ManifestFreezeInputsError(
                "authenticated v3 projection lacks its run-card receipt"
            )
        card = _json_object(card_bytes, card_path)
        receipt_anchor = final_v3.get("anchor_root")
        if not isinstance(receipt_anchor, Path) or (
            authenticated_anchor is not None
            and receipt_anchor.absolute() != authenticated_anchor.absolute()
        ):
            raise ManifestFreezeInputsError(
                "supplied v3 roots do not share one authenticated anchor"
            )
        authenticated_anchor = receipt_anchor
        recorded_anchor_digest = _required_sha(card, "predecessor_anchor_sha256")
        if anchor_digest is not None and recorded_anchor_digest != anchor_digest:
            raise ManifestFreezeInputsError(
                "supplied v3 roots disagree on predecessor anchor commitment"
            )
        anchor_digest = recorded_anchor_digest
        input_roots = _mapping(card.get("input_roots"), "authenticated v3 input_roots")
        predecessor = Path(_required_str(input_roots, "predecessor_root"))
        required_predecessor = expected_predecessor or authenticated_anchor
        if predecessor.absolute() != required_predecessor.absolute():
            raise ManifestFreezeInputsError(
                "supplied v3 roots are not one authenticated predecessor chain"
            )
        expected_predecessor = root
    if authenticated_anchor is None or anchor_digest is None:
        raise ManifestFreezeInputsError("authenticated v3 anchor receipt is missing")
    anchor_card_path = (
        authenticated_anchor
        / "run-cards/project-exact100-supporting-document-successor.json"
    )
    anchor_card_bytes = _snapshot(
        anchor_card_path, snapshots, "authenticated v3 anchor run card"
    )
    anchor_card = _json_object(anchor_card_bytes, anchor_card_path)
    anchor_inputs = _string_sequence(
        anchor_card.get("input_paths"), "authenticated v3 anchor inputs"
    )
    anchor_commitments = _mapping(
        anchor_card.get("input_commitments"),
        "authenticated v3 anchor input commitments",
    )
    if (
        _sha(anchor_card_bytes) != anchor_digest
        or anchor_card.get("schema_version")
        != str(EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1)
        or anchor_card.get("stage") != "project-exact100-supporting-document-successor"
        or anchor_card.get("status") != "completed"
        or anchor_card.get("selected_case_count") != 100
        or not anchor_inputs
        or Path(anchor_inputs[0]).absolute() != request.v2_root.absolute()
        or anchor_commitments.get("v2_selection_sha256")
        != f"sha256:{_sha(v2_selection_bytes)}"
    ):
        raise ManifestFreezeInputsError(
            "authenticated v3 anchor does not bind the supplied v2 root"
        )
    if final_v3 is None:
        raise ManifestFreezeInputsError("final v3 successor projection is missing")
    final_selection = _record_sequence(
        final_v3.get("selection_records"), "final v3 selection_records"
    )
    final_selected_ids = tuple(
        _required_str(row, "candidate_id") for row in final_selection
    )
    if (
        len(final_selected_ids) != 100
        or len(set(final_selected_ids)) != 100
        or frozenset(final_selected_ids) != selected_ids
    ):
        raise ManifestFreezeInputsError(
            "final v3 authenticated selection differs from signed manifest"
        )
    if len(terminal_records) != 6:
        raise ManifestFreezeInputsError("successor roots must supply six terminal rows")
    normalized_terminal = tuple(
        _terminal_exclusion_record(row) for row in terminal_records
    )
    ledger = merge_exclusion_ledger_records(retained, normalized_terminal)
    records = tuple(ledger.to_records())
    excluded_ids = frozenset(_required_str(row, "candidate_id") for row in records)
    expected = screened_ids - selected_ids
    if (
        len(records) != 57
        or excluded_ids != expected
        or excluded_ids & selected_ids
        or selected_ids | excluded_ids != selected_ids | screened_ids
    ):
        raise ManifestFreezeInputsError(
            "57-row exclusions do not reconcile screened pool"
        )
    return b"".join(
        canonical_json_bytes(
            row,
            error_type=ManifestFreezeInputsError,
            error_message="complete exclusion ledger row is not canonical JSON",
        )
        for row in records
    )


def _legacy_authenticators(
    *,
    legacy_historical_authenticator: LegacyHistoricalAuthenticator,
    legacy_v2_verifier: LegacyV2Verifier,
    legacy_v2_replay_args: LegacyV2ReplayArgs,
    legacy_v2_replay: LegacyV2Replay,
) -> tuple[HistoricalExclusionAuthenticator, V2Authenticator]:
    """Adapt the established CLI-facade replays without importing the facade."""

    def authenticate_historical(
        run_card_path: Path,
        output_path: Path,
        screened_cases_path: Path,
        run_card_bytes: bytes,
        output_bytes: bytes,
        screened_cases_bytes: bytes,
    ) -> Sequence[Mapping[str, Any]]:
        card = _json_object(run_card_bytes, run_card_path)
        for path, expected, label in (
            (run_card_path, run_card_bytes, "historical exclusion run card"),
            (output_path, output_bytes, "historical exclusion ledger"),
            (screened_cases_path, screened_cases_bytes, "screened pool"),
        ):
            if _read_regular(path, label) != expected:
                raise ManifestFreezeInputsError(
                    f"{label} changed before authenticated replay"
                )
        raw_inputs = _string_sequence(card.get("input_paths"), "historical inputs")
        if len(raw_inputs) < 2:
            raise ManifestFreezeInputsError(
                "historical exclusion run card lacks selection path"
            )
        records = legacy_historical_authenticator(
            run_card_path=run_card_path,
            output_path=output_path,
            selection_path=Path(raw_inputs[1]),
            screened_cases_path=screened_cases_path,
            _captured_run_card_bytes=run_card_bytes,
            _captured_output_bytes=output_bytes,
            _captured_screened_cases_bytes=screened_cases_bytes,
        )
        return records

    def authenticate_v2(root: Path) -> Mapping[str, Any]:
        card_path = root / "run-cards/project-target-cohort.json"
        card = _json_object(
            _read_regular(card_path, "v2 successor run card"), card_path
        )
        replay_args = legacy_v2_replay_args(card)
        return legacy_v2_verifier(
            root,
            replay=legacy_v2_replay,
            args=replay_args,
        )

    return authenticate_historical, authenticate_v2


def _authenticate_v3_chain(
    roots: tuple[Path, ...],
    *,
    snapshots: dict[Path, bytes] | None = None,
) -> tuple[tuple[Path, Mapping[str, Any]], ...]:
    """Authenticate one v3 chain and reuse its proof for sibling projections.

    The final root's normal replay authenticates every predecessor recursively.
    Earlier roots are then read through the same downstream verifier with
    receipts minted from that already-authenticated chain.  The caller retains
    and rechecks the recursive replay's exact bytes, so this optimization does
    not turn a changed root into trusted output.
    """

    if len(roots) != 3:
        raise ManifestFreezeInputsError("exactly three v3 roots are required")
    final_root = roots[-1]
    final_projection, authenticated_bytes = _authenticate_v3_with_snapshot(final_root)
    if snapshots is not None:
        for path, payload in authenticated_bytes.items():
            if _snapshot(path, snapshots, "authenticated v3 chain input") != payload:
                raise ManifestFreezeInputsError(
                    "authenticated v3 chain bytes changed after replay"
                )
    anchor_root = final_projection.get("anchor_root")
    if not isinstance(anchor_root, Path):
        raise ManifestFreezeInputsError("authenticated v3 anchor receipt is missing")
    chain = _v3_chain_roots(final_root)
    expected = tuple(reversed(chain[:-1]))
    if tuple(root.absolute() for root in expected) != tuple(
        root.absolute() for root in roots
    ):
        raise ManifestFreezeInputsError(
            "supplied v3 roots are not the authenticated predecessor chain"
        )
    if anchor_root.absolute() != chain[-1].absolute():
        raise ManifestFreezeInputsError(
            "authenticated v3 anchor differs from the predecessor chain"
        )

    projections: list[tuple[Path, Mapping[str, Any]]] = []
    for root in roots:
        if root.absolute() == final_root.absolute():
            projections.append((root, final_projection))
            continue
        receipt = AuthenticatedV3Root(root=root, anchor_root=anchor_root)

        def reuse_receipt(
            target: Path,
            *,
            expected_root: Path = root,
            cached_receipt: AuthenticatedV3Root = receipt,
        ) -> object:
            if target.absolute() != expected_root.absolute():
                raise ManifestFreezeInputsError(
                    "v3 verifier requested an unexpected cached predecessor"
                )
            return cached_receipt

        projections.append(
            (
                root,
                verify_exact100_successor_replacement_v3_projection(
                    root, authenticate=reuse_receipt
                ),
            )
        )
    return tuple(projections)


def _authenticate_v3_with_snapshot(
    root: Path,
) -> tuple[Mapping[str, Any], Mapping[Path, bytes]]:
    """Authenticate one final root and retain its recursive byte evidence."""

    captured: dict[Path, bytes] = {}

    def authenticate(target: Path) -> object:
        receipt, replayed = authenticate_exact100_successor_v3_root_with_snapshot(
            target
        )
        for path, payload in replayed.items():
            previous = captured.get(path)
            if previous is not None and previous != payload:
                raise ManifestFreezeInputsError(
                    "authenticated v3 chain replay read inconsistent bytes"
                )
            captured[path] = payload
        return receipt

    projection = verify_exact100_successor_replacement_v3_projection(
        root, authenticate=authenticate
    )
    return projection, captured


def _v3_chain_roots(final_root: Path) -> tuple[Path, ...]:
    """Return ``final -> ... -> sealed anchor`` from v3 run-card paths."""

    chain = [final_root]
    seen = {final_root.absolute()}
    for _ in range(256):
        current = chain[-1]
        anchor_card = (
            current / "run-cards/project-exact100-supporting-document-successor.json"
        )
        if anchor_card.is_file():
            return tuple(chain)
        card_path = current / "run-cards/project-exact100-successor-replacement-v3.json"
        card = _json_object(
            _read_regular(card_path, "authenticated v3 run card"), card_path
        )
        input_roots = _mapping(card.get("input_roots"), "authenticated v3 input_roots")
        predecessor = Path(_required_str(input_roots, "predecessor_root"))
        if predecessor.absolute() in seen:
            raise ManifestFreezeInputsError(
                "authenticated v3 predecessor chain contains a cycle"
            )
        chain.append(predecessor)
        seen.add(predecessor.absolute())
    raise ManifestFreezeInputsError("authenticated v3 predecessor chain is too deep")


def _terminal_records(
    root: Path,
    projection: Mapping[str, Any],
    snapshots: dict[Path, bytes],
) -> tuple[Mapping[str, Any], ...]:
    path = root / "successor-terminal-exclusions.jsonl"
    verified = snapshot_verified_artifacts(
        root,
        projection,
        snapshots,
        snapshot=_snapshot,
        error_type=ManifestFreezeInputsError,
    )
    payload = verified.get(str(path.absolute()))
    if not isinstance(payload, bytes):
        raise ManifestFreezeInputsError(
            f"authenticated root lacks terminal bytes: {root}"
        )
    return _jsonl(payload, path)


def _terminal_exclusion_record(record: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = _required_str(record, "candidate_id")
    raw_reason = record.get("reason", record.get("ground"))
    if not isinstance(raw_reason, str) or not raw_reason.strip():
        raise ManifestFreezeInputsError("terminal exclusion reason/ground is required")
    reason = raw_reason
    document = record.get("source_document_id")
    if document is not None and (not isinstance(document, str) or not document):
        raise ManifestFreezeInputsError("terminal source_document_id is invalid")
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "stage": "eligibility",
        "reason": reason,
        "primary_exclusion_reason": reason,
        "secondary_exclusion_reasons": [],
        "source_entry_ids": [],
        "source_document_ids": [document] if isinstance(document, str) else [],
        "notes": (
            "Authenticated exact-100 successor terminal exclusion; source schema "
            f"{_required_str(record, 'schema_version')}."
        ),
    }


def _request_input_paths(request: ManifestFreezeInputsRequest) -> dict[str, Any]:
    return {
        "repository_root": str(request.repository_root.absolute()),
        "owner_manifest": str(request.owner_manifest.absolute()),
        "model_registry": str(request.model_registry.absolute()),
        "forecast_output_dir": str(request.forecast_output_dir.absolute()),
        "screened_pool": str(request.screened_pool.absolute()),
        "historical_exclusion_ledger": str(
            request.historical_exclusion_ledger.absolute()
        ),
        "historical_exclusion_run_card": str(
            request.historical_exclusion_run_card.absolute()
        ),
        "v2_root": str(request.v2_root.absolute()),
        "v3_roots": [str(root.absolute()) for root in request.v3_roots],
    }


def _publish_create_only(root: Path, payloads: Mapping[str, bytes]) -> None:
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir()
    for relative, payload in sorted(payloads.items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)


def _verify_published(root: Path, payloads: Mapping[str, bytes]) -> None:
    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    if actual_paths != set(payloads):
        raise ManifestFreezeInputsError("freeze-input output root has unexpected paths")
    for relative, payload in payloads.items():
        if _read_regular(root / relative, f"published {relative}") != payload:
            raise ManifestFreezeInputsError(f"published output changed: {relative}")


def _snapshot(path: Path, snapshots: dict[Path, bytes], label: str) -> bytes:
    absolute = path.absolute()
    payload = _read_regular(absolute, label)
    previous = snapshots.get(absolute)
    if previous is not None and previous != payload:
        raise ManifestFreezeInputsError(f"input changed during replay: {path}")
    snapshots[absolute] = payload
    return payload


def _require_snapshots_unchanged(snapshots: Mapping[Path, bytes]) -> None:
    for path, payload in snapshots.items():
        if _read_regular(path, "freeze-input source recheck") != payload:
            raise ManifestFreezeInputsError(f"input changed before publication: {path}")


def _read_regular(path: Path, label: str) -> bytes:
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ManifestFreezeInputsError(f"{label} is unreadable: {path}") from exc
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise ManifestFreezeInputsError(f"{label} is not a regular file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    except OSError as exc:
        raise ManifestFreezeInputsError(f"{label} is unreadable: {path}") from exc
    finally:
        os.close(descriptor)


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise ManifestFreezeInputsError(f"git {' '.join(args)} failed: {stderr}")
    return result.stdout


def _json_object(payload: bytes, source: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestFreezeInputsError(f"invalid JSON: {source}") from exc
    if not isinstance(value, Mapping):
        raise ManifestFreezeInputsError(f"JSON must be an object: {source}")
    return dict(cast(Mapping[str, Any], value))


def _jsonl(payload: bytes, source: Path) -> tuple[Mapping[str, Any], ...]:
    records: list[Mapping[str, Any]] = []
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ManifestFreezeInputsError(f"invalid UTF-8 JSONL: {source}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManifestFreezeInputsError(
                f"invalid JSONL at {source}:{line_number}"
            ) from exc
        if not isinstance(value, Mapping):
            raise ManifestFreezeInputsError(f"JSONL row must be an object: {source}")
        records.append(cast(Mapping[str, Any], value))
    return tuple(records)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ManifestFreezeInputsError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _record_sequence(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ManifestFreezeInputsError(f"{label} must be a list")
    return tuple(
        _mapping(item, f"{label} item") for item in cast(Sequence[object], value)
    )


def _string_sequence(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ManifestFreezeInputsError(f"{label} must be a list")
    items = tuple(cast(Sequence[object], value))
    if not all(isinstance(item, str) and item for item in items):
        raise ManifestFreezeInputsError(f"{label} must contain non-empty strings")
    return tuple(cast(str, item) for item in items)


def _required_str(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ManifestFreezeInputsError(f"{name} must be a non-empty string")
    return value


def _required_sha(record: Mapping[str, Any], name: str) -> str:
    value = _required_str(record, name).removeprefix("sha256:")
    if _SHA256.fullmatch(value) is None:
        raise ManifestFreezeInputsError(f"{name} must be a lowercase SHA-256")
    return value


def _screened_candidate_id(record: Mapping[str, Any]) -> str:
    candidate = _mapping(record.get("candidate"), "screened candidate")
    return _required_str(candidate, "docket_id")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
