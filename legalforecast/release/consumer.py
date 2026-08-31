"""Consumers for the locked public benchmark-run boundary.

The corpus producer owns the run manifest, while the public repository owns
the outcome-blinded forecast release and the separate labels release.  This
module is the small join between those contracts.  It deliberately validates
the complete manifest identity binding and its selected case membership;
document bytes and their commitments remain the responsibility of the
forecast release validator.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from legalforecast.immutable_io import read_single_link_file

from .models import ForecastRelease
from .run_manifest import (
    BenchmarkRunManifest,
    RunManifestError,
    serialize_run_manifest,
    validate_run_manifest_structure,
)

if TYPE_CHECKING:
    from .service import ForecastExecution


@dataclass(frozen=True, slots=True)
class LoadedRunManifest:
    """A locked manifest and its canonical local commitment."""

    manifest: BenchmarkRunManifest
    sha256: str


@dataclass(frozen=True, slots=True)
class ForecastWorkerInput:
    """One outcome-blinded artifact declared by a forecast release."""

    relative_path: str
    kind: Literal["document", "packet", "prompt"]
    case_id: str
    unit_id: str | None = None


@dataclass(frozen=True, slots=True)
class ForecastRunInputs:
    """Outcome-blinded inputs admitted to a public forecast worker."""

    manifest: BenchmarkRunManifest
    manifest_sha256: str
    execution: ForecastExecution
    worker_inputs: tuple[ForecastWorkerInput, ...]


def load_run_manifest(path: Path) -> LoadedRunManifest:
    """Read and validate one canonical locked public run manifest.

    ``read_single_link_file`` gives the same no-follow-link and regular-file
    guarantees used by release validation.  The structure validator is public
    and intentionally does not inspect private corpus state.
    """

    payload = read_single_link_file(path, label="run manifest")
    manifest = validate_run_manifest_structure(payload)
    canonical_payload = serialize_run_manifest(manifest)
    return LoadedRunManifest(
        manifest=manifest,
        sha256=hashlib.sha256(canonical_payload).hexdigest(),
    )


def validate_manifest_against_forecast(
    manifest: BenchmarkRunManifest,
    forecast: ForecastRelease,
) -> None:
    """Require every locked manifest identity to bind the forecast release."""

    binding = forecast.run_manifest_binding
    if binding is None:
        raise RunManifestError("forecast release lacks its locked run-manifest binding")
    if binding.schema_version != manifest.schema_version:
        raise RunManifestError("forecast release and run manifest schemas differ")
    if binding.release_id != forecast.release_id:
        raise RunManifestError(
            "forecast release identity differs from manifest binding"
        )
    if binding.run_id != manifest.run_id:
        raise RunManifestError("forecast release and run manifest run IDs differ")
    if binding.policy_version != manifest.policy_version:
        raise RunManifestError(
            "forecast release and run manifest policy versions differ"
        )
    if binding.code_revision != manifest.code_revision:
        raise RunManifestError(
            "forecast release and run manifest code revisions differ"
        )
    manifest_sha256 = hashlib.sha256(serialize_run_manifest(manifest)).hexdigest()
    if binding.manifest_sha256 != manifest_sha256:
        raise RunManifestError("forecast release and run manifest bytes differ")

    manifest_case_ids = {case.case_id for case in manifest.selected_cases}
    forecast_case_ids = {case.case_id for case in forecast.cases}
    if manifest_case_ids != forecast_case_ids:
        missing_from_forecast = sorted(manifest_case_ids - forecast_case_ids)
        unselected_forecast_cases = sorted(forecast_case_ids - manifest_case_ids)
        raise RunManifestError(
            "run manifest selected cases do not match forecast release cases: "
            f"missing_from_forecast={missing_from_forecast!r}, "
            f"unselected_forecast_cases={unselected_forecast_cases!r}"
        )


def enumerate_forecast_worker_inputs(
    forecast: ForecastRelease,
    *,
    requested_paths: Sequence[str] | None = None,
) -> tuple[ForecastWorkerInput, ...]:
    """Enumerate only paths declared by an outcome-blinded forecast release.

    ``requested_paths`` is an optional checked handoff for a materializer.  If
    supplied, it must be the exact declared path set; arbitrary extras,
    traversal paths, and label/outcome paths are refused.  This helper only
    returns documents, packets, and prompts from ``ForecastRelease`` and has no
    labels API or output-bearing input.
    """

    inputs: list[ForecastWorkerInput] = []
    for case in forecast.cases:
        for document in case.documents:
            inputs.append(
                ForecastWorkerInput(
                    relative_path=document.path,
                    kind="document",
                    case_id=case.case_id,
                )
            )
    for unit in forecast.prediction_units:
        inputs.extend(
            (
                ForecastWorkerInput(
                    relative_path=unit.packet_path,
                    kind="packet",
                    case_id=unit.case_id,
                    unit_id=unit.unit_id,
                ),
                ForecastWorkerInput(
                    relative_path=unit.prompt_path,
                    kind="prompt",
                    case_id=unit.case_id,
                    unit_id=unit.unit_id,
                ),
            )
        )
    result = tuple(inputs)
    expected_paths = tuple(item.relative_path for item in result)
    if any(not _is_safe_worker_path(path) for path in expected_paths):
        raise RunManifestError("forecast release contains an unsafe worker path")
    if any(not _is_outcome_blind_worker_path(path) for path in expected_paths):
        raise RunManifestError(
            "forecast release worker paths must not name labels or outcomes"
        )
    if len(expected_paths) != len(set(expected_paths)):
        raise RunManifestError("forecast release worker paths are not unique")
    if requested_paths is not None:
        requested = tuple(requested_paths)
        if len(requested) != len(set(requested)):
            raise RunManifestError("worker input paths contain duplicates")
        if any(not _is_safe_worker_path(path) for path in requested):
            raise RunManifestError(
                "worker input paths must be safe relative POSIX paths"
            )
        if set(requested) != set(expected_paths):
            raise RunManifestError(
                "worker input paths are not exactly release-declared"
            )
    return result


def _is_safe_worker_path(path: object) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and not path.startswith("/")
        and not path.startswith("~")
        and not (len(path) >= 2 and path[1] == ":")
        and "://" not in path
        and "\\" not in path
        and "\x00" not in path
        and not any(part in {"", ".", ".."} for part in path.split("/"))
    )


def _is_outcome_blind_worker_path(path: str) -> bool:
    """Keep known labels/outcome artifact names outside worker inputs."""

    parts = tuple(part.lower() for part in path.split("/"))
    return not any(
        part in {"label", "labels", "outcome", "outcomes"}
        or part.startswith(("label-", "labels-", "outcome-", "outcomes-"))
        for part in parts
    )


def load_forecast_run_inputs(
    manifest_path: Path,
    forecast_path: Path,
    *,
    artifact_root: Path,
) -> ForecastRunInputs:
    """Load manifest plus outcome-blinded forecast inputs for a worker.

    There is intentionally no labels path or labels object in this return
    value.  Label-consuming scoring belongs to the fan-in/reporting side.
    """

    loaded_manifest = load_run_manifest(manifest_path)
    from .service import load_forecast_execution

    execution = load_forecast_execution(
        forecast_path,
        artifact_root=artifact_root,
    )
    validate_manifest_against_forecast(loaded_manifest.manifest, execution.release)
    worker_inputs = enumerate_forecast_worker_inputs(execution.release)
    return ForecastRunInputs(
        manifest=loaded_manifest.manifest,
        manifest_sha256=loaded_manifest.sha256,
        execution=execution,
        worker_inputs=worker_inputs,
    )
