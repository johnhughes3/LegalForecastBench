"""Command implementations behind the corpus-manifest CLI adapter.

These functions own the operator-facing shape of the two commands — what is
written, what is printed, and which exit path a refusal takes — while the
freeze and build modules own the rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from legalforecast._json_io import write_json_object
from legalforecast.evals.corpus_manifest.forecast_entry import (
    ForecastBuildRequest,
    OwnerSignatureReference,
    build_manifest_mode_forecast,
)
from legalforecast.evals.corpus_manifest.freeze import (
    CorpusFreezeRefused,
    FreezeInputs,
    freeze_corpus_manifest,
)


def freeze_corpus_manifest_command(
    *,
    selection: Path,
    prediction_units: Path,
    document_store_roots: Sequence[Path],
    verdict_sources: Sequence[Path],
    cycle_id: str,
    output: Path,
    generated_at: datetime,
) -> tuple[dict[str, Any], bool]:
    """Freeze the corpus, or report every blocker without writing a manifest.

    A refused freeze writes nothing, so no unsignable instrument is ever left
    next to a refusal.
    """

    inputs = FreezeInputs(
        selection_path=selection,
        prediction_units_path=prediction_units,
        document_store_roots=tuple(document_store_roots),
        verdict_sources=tuple(verdict_sources),
        cycle_id=cycle_id,
        generated_at=generated_at.isoformat().replace("+00:00", "Z"),
    )
    try:
        manifest = freeze_corpus_manifest(inputs)
    except CorpusFreezeRefused as refusal:
        output.unlink(missing_ok=True)
        return (
            {
                "blocker_count": len(refusal.violations),
                "blockers": list(refusal.violations),
                "status": "refused",
            },
            False,
        )
    record = manifest.to_signed_record()
    write_json_object(output, record)
    digest = str(record["manifest_sha256"])
    return (
        {
            "case_count": len(manifest.cases),
            "document_count": sum(len(case.documents) for case in manifest.cases),
            "manifest_path": str(output),
            "manifest_sha256": digest,
            "model_visible_document_count": sum(
                len(case.model_visible_documents) for case in manifest.cases
            ),
            "owner_signs_this_digest": digest,
            "status": "frozen",
        },
        True,
    )


def build_manifest_forecast_command(
    *,
    manifest: Path,
    expected_manifest_digest: str,
    owner_signature_bead: str,
    owner_approval_line: str,
    model_registry: Path,
    output_dir: Path,
    generated_at: datetime,
) -> dict[str, Any]:
    """Build the manifest-mode forecast inputs and report what was written."""

    result = build_manifest_mode_forecast(
        ForecastBuildRequest(
            manifest_path=manifest,
            expected_manifest_digest=expected_manifest_digest,
            owner_signature=OwnerSignatureReference(
                bead_id=owner_signature_bead,
                approval_line=owner_approval_line,
            ),
            model_registry_path=model_registry,
            output_dir=output_dir,
            generated_at=generated_at,
        )
    )
    return {
        "manifest_sha256": result.manifest_digest,
        "model_ids": list(result.model_ids),
        "packet_count": result.packet_count,
        "packet_store_root": str(result.packet_store_root),
        "provider_calls_made": 0,
        "run_inputs_manifest": str(result.run_inputs_manifest_path),
        "run_record": str(result.run_record_path),
        "status": "built",
    }
