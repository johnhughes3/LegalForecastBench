"""Prepare the distinct one-shot Jev benchmark condition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.model_registry import ModelRegistry, load_model_registry
from legalforecast.immutable_io import read_single_link_file, write_file_create_only
from legalforecast.jev.packets import (
    JEV_REQUEST_BYTE_BUDGET,
    case_documents,
    case_request,
    request_byte_count,
)
from legalforecast.jev.prepare import prepare_summaries
from legalforecast.release import load_forecast_run_inputs


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:  # pyright: ignore[reportPrivateUsage]
    """Register provider-free sizing, persisted summaries, and a frozen registry."""

    parser = subparsers.add_parser(
        "jev",
        help="Prepare a distinct one-shot Jev condition using unchanged release units.",
    )
    commands = parser.add_subparsers(dest="jev_command", metavar="COMMAND")
    for command in ("inspect", "prepare"):
        child = commands.add_parser(
            command,
            help=(
                "Measure all full-text requests without provider calls."
                if command == "inspect"
                else "Generate and persist Luna summaries; cached documents are reused."
            ),
        )
        child.add_argument(
            "--manifest",
            type=Path,
            required=True,
            help="Original locked Cycle 1 run manifest.",
        )
        child.add_argument(
            "--forecast",
            type=Path,
            required=True,
            help="Original outcome-blinded forecast release.",
        )
        child.add_argument(
            "--artifact-root",
            type=Path,
            required=True,
            help="Original release artifact directory.",
        )
        if command == "prepare":
            child.add_argument(
                "--luna-registry",
                type=Path,
                required=True,
                help="Frozen registry containing openai:gpt-5.6-luna and token prices.",
            )
            child.add_argument(
                "--cache",
                type=Path,
                required=True,
                help="Reusable summary JSON; matching summaries are not repurchased.",
            )
            child.add_argument(
                "--ledger",
                type=Path,
                required=True,
                help="Durable spend SQLite file; retain with the cache on resume.",
            )
            child.add_argument(
                "--ceiling-microusd",
                type=int,
                required=True,
                help="Total summary run ceiling in millionths of one US dollar.",
            )
        child.set_defaults(handler=run_inputs)
    registry = commands.add_parser(
        "registry",
        help="Freeze Jev method and optional summary cache in a model registry.",
    )
    registry.add_argument(
        "--summaries",
        type=Path,
        help="Completed Luna summary cache; omit for full-text mode.",
    )
    registry.add_argument(
        "--output", type=Path, required=True, help="Create-only registry JSON output."
    )
    registry.set_defaults(handler=run_registry)


def run_inputs(args: argparse.Namespace) -> int:
    """Read only outcome-blinded inputs and dispatch the selected operation."""

    execution = load_forecast_run_inputs(
        cast(Path, args.manifest),
        cast(Path, args.forecast),
        artifact_root=cast(Path, args.artifact_root),
    ).execution
    if args.jev_command == "prepare":
        entry = load_model_registry(cast(Path, args.luna_registry)).get(
            "openai", "gpt-5.6-luna"
        )
        result = prepare_summaries(
            execution,
            entry=entry,
            cache_path=cast(Path, args.cache),
            ledger_path=cast(Path, args.ledger),
            ceiling_microusd=cast(int, args.ceiling_microusd),
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    rows: list[dict[str, object]] = []
    for case in execution.release.cases:
        units = tuple(
            u for u in execution.release.prediction_units if u.case_id == case.case_id
        )
        documents = case_documents(execution, units)
        size = request_byte_count(case_request(units, documents))
        rows.append(
            {
                "case_id": case.case_id,
                "unit_count": len(units),
                "document_count": len(documents),
                "request_bytes": size,
                "fits_conservative_budget": size <= JEV_REQUEST_BYTE_BUDGET,
            }
        )
    print(
        json.dumps(
            {
                "release_digest": execution.release.release_digest,
                "case_count": len(rows),
                "unit_count": execution.release.unit_count,
                "request_byte_budget": JEV_REQUEST_BYTE_BUDGET,
                "token_count": "unavailable: provider publishes no tokenizer",
                "cases": rows,
            },
            sort_keys=True,
        )
    )
    return 0


def run_registry(args: argparse.Namespace) -> int:
    """Use the provider's real route; do not invent a dated model snapshot."""

    path = cast(Path | None, args.summaries)
    digest = (
        None
        if path is None
        else str(
            RAW_BYTES_RAW_SHA256_V1.commit(
                read_single_link_file(path, label="Jev summaries"),
                domain=PUBLIC_RUN_RECEIPT_V1,
            ).digest
        )
    )
    record: dict[str, object] = {
        "provider": "vercel_ai_gateway",
        "model_id": "typesafe-ai/jev",
        "display_name": "Jev (Luna summaries; one shot)"
        if path
        else "Jev (full text; one shot)",
        "model_version_or_snapshot": "typesafe-ai/jev",
        "release_timestamp": "2026-09-15T00:00:00Z",
        "release_timestamp_source": "https://vercel.com/ai-gateway/models/jev",
        "provider_training_cutoff_status": "not_disclosed",
        "max_output_tokens": 1,
        "context_limit": 32000,
        "network_disabled": True,
        "search_disabled": True,
        "tool_policy": "no_tools",
        "pricing_source": "https://vercel.com/ai-gateway/models/jev",
        "input_token_price": 0.042,
        "output_token_price": 0.0,
        "known_cutoff_publicity_caveats": [
            "Provider does not expose a dated Jev snapshot or exact tokenizer. "
            "One-shot condition; summary preparation costs reported separately."
        ],
        "jev_input_mode": "full_text" if path is None else "luna_summaries",
    }
    if digest is not None:
        record["jev_summaries_sha256"] = digest
    registry = ModelRegistry.from_records([record])
    write_file_create_only(
        cast(Path, args.output),
        ARTIFACT_CANONICAL_JSON_V1.encode(registry.to_records()),
    )
    return 0
