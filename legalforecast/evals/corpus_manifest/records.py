"""Run-record assembly and stable serialization for the manifest-mode build.

Kept beside the entry rather than inside it so the entry module stays about the
rules and this one stays about what gets written.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts.schemas import MANIFEST_MODE_FORECAST_RUN_RECORD_V1
from legalforecast.evals.corpus_manifest.coercion import CorpusManifestError
from legalforecast.evals.corpus_manifest.schema import CorpusManifest
from legalforecast.evals.model_registry import model_registry_entry_sha256


def registry_record(entries: Sequence[Any]) -> list[dict[str, str]]:
    return [
        {
            "model_entry_sha256": model_registry_entry_sha256(entry),
            "model_id": entry.model_id,
            "provider": entry.provider,
        }
        for entry in entries
    ]


def committed_registry_keys(committed: Sequence[Any]) -> tuple[str, ...]:
    """Read ``provider:model_id`` keys back out of a recorded registry record.

    The inverse of the identifying half of :func:`registry_record`, kept beside
    it so the round trip is defined once.  Callers compare these keys across
    lanes and print them in refusals, so a row missing either half is dropped
    rather than guessed at: the identity checks are digest equality on the whole
    record, and this is only the human-readable projection of it.
    """

    keys: list[str] = []
    for raw in committed:
        if not isinstance(raw, Mapping):
            continue
        record = cast(Mapping[str, Any], raw)
        provider = record.get("provider")
        model_id = record.get("model_id")
        if isinstance(provider, str) and isinstance(model_id, str):
            keys.append(f"{provider}:{model_id}")
    return tuple(keys)


def run_record(
    *,
    manifest: CorpusManifest,
    digest: str,
    generated_at: datetime,
    owner_signature: Mapping[str, Any],
    docket_tool_enabled: bool,
    ablations: Sequence[str],
    required_run_case_flags: Sequence[str],
    entries_record: Sequence[Mapping[str, str]],
    prompt_commitments: Mapping[str, str],
    packet_rows: Sequence[Mapping[str, Any]],
    release_anchor: str,
    run_inputs_path: Path,
) -> dict[str, Any]:
    return {
        "case_count": len(manifest.cases),
        "cycle_id": manifest.cycle_id,
        "docket_tool_enabled": docket_tool_enabled,
        "entry_mode": "owner_signed_manifest",
        "evaluation_models": list(entries_record),
        "evaluation_release_anchor": release_anchor,
        "generated_at": isoformat_utc(generated_at),
        "manifest_sha256": digest,
        "owner_signature_reference": dict(owner_signature),
        "packet_ablations": list(ablations),
        "packet_count": len(packet_rows),
        "prediction_units_source": manifest.prediction_units_source.to_record(),
        "prompt_commitments": dict(prompt_commitments),
        "provider_calls_made": 0,
        "required_eval_run_case_flags": list(required_run_case_flags),
        "run_inputs_manifest": str(run_inputs_path),
        "schema_version": str(MANIFEST_MODE_FORECAST_RUN_RECORD_V1),
        "selection_source": manifest.selection_source.to_record(),
    }


def write_indented_json(path: Path, payload: Mapping[str, Any]) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(encoded)
    return encoded


def isoformat_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in value
    ).strip("-")
    if not cleaned:
        raise CorpusManifestError(f"cannot form a safe path component from {value!r}")
    return cleaned
