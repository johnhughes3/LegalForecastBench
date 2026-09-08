# pyright: reportPrivateUsage=false

"""Restore one completed managed transcript into the normal runner replay path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    model_registry_entry_sha256,
    model_registry_sha256,
)
from legalforecast.immutable_io import read_single_link_file
from legalforecast.runner.ledger import RunnerLedger, RunValidationError
from legalforecast.runner.managed_transcript_recovery import (
    recover_managed_transcript,
)


def main() -> int:
    """Validate and restore one transcript without provider access."""

    parser = argparse.ArgumentParser(
        description=(
            "Restore a successful managed SDK transcript into a runner ledger; "
            "this command never calls a model provider."
        )
    )
    parser.add_argument(
        "--ledger", type=Path, required=True, help="runner SQLite ledger"
    )
    parser.add_argument(
        "--registry", type=Path, required=True, help="frozen model registry bytes"
    )
    parser.add_argument(
        "--transcript", type=Path, required=True, help="successful SDK transcript JSON"
    )
    parser.add_argument("--cell-id", required=True, help="exact ledger cell ID")
    args = parser.parse_args()

    registry_bytes = read_single_link_file(args.registry, label="model registry")
    registry_sha256 = model_registry_sha256(registry_bytes)
    registry = load_model_registry_bytes(registry_bytes)
    with RunnerLedger(
        args.ledger,
        state_only_provider_attempts=True,
    ) as ledger:
        binding = ledger.read_run_binding()
        if binding.model_registry_sha256 != registry_sha256:
            raise RunValidationError("model registry differs from frozen run binding")
        try:
            provider, model_id = binding.model_key.split(":", 1)
            entry = registry.get(provider, model_id)
        except (KeyError, ValueError) as exc:
            raise RunValidationError(
                "frozen model key is absent from registry"
            ) from exc
        if model_registry_entry_sha256(entry) != binding.model_registry_entry_sha256:
            raise RunValidationError(
                "model registry entry differs from frozen run binding"
            )
        if entry.model_version_or_snapshot != binding.served_model_version:
            raise RunValidationError("served model differs from frozen run binding")
        cell = ledger.read_cell_for_recovery(args.cell_id)
        if cell.status == "completed":
            print(
                json.dumps(
                    {"cell_id": args.cell_id, "status": "already_completed"},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0
        recovered = recover_managed_transcript(
            ledger,
            entry=entry,
            transcript_path=args.transcript,
            cell_id=args.cell_id,
        )
    print(
        json.dumps(
            {
                "cell_id": recovered.cell_id,
                "provider_attempt_id": recovered.provider_attempt_id,
                "response_payload_sha256": recovered.payload_sha256,
                "response_sha256": recovered.response_sha256,
                "request_count": recovered.result.request_count,
                "input_tokens": recovered.result.input_tokens,
                "output_tokens": recovered.result.output_tokens,
                "served_model": recovered.result.served_model,
                "finish_reason": recovered.result.finish_reason,
                "service_tier": recovered.result.service_tier,
                "thoughts_tokens": recovered.result.thoughts_tokens,
                "estimated_cost_usd": recovered.estimated_cost_usd,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    main()
