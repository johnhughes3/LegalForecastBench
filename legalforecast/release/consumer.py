"""Consumers for the locked public benchmark-run boundary.

The corpus producer owns the run manifest, while the public repository owns
the outcome-blinded forecast release and the separate labels release.  This
module is the small join between those contracts.  It deliberately validates
only the locked manifest structure and its selected case membership; document
bytes and their commitments remain the responsibility of the forecast
release validator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

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
class ForecastRunInputs:
    """Outcome-blinded inputs admitted to a public forecast worker."""

    manifest: BenchmarkRunManifest
    manifest_sha256: str
    execution: ForecastExecution


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
    """Require the locked selection and the public forecast release to agree."""

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
    return ForecastRunInputs(
        manifest=loaded_manifest.manifest,
        manifest_sha256=loaded_manifest.sha256,
        execution=execution,
    )
