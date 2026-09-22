"""Prepare the distinct one-shot Jev benchmark condition."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    PUBLIC_RUN_RECEIPT_V1,
    RAW_BYTES_RAW_SHA256_V1,
)
from legalforecast.evals.model_registry import (
    ModelRegistry,
    load_model_registry,
)
from legalforecast.immutable_io import read_single_link_file, write_file_create_only
from legalforecast.jev.context import estimate_request_context
from legalforecast.jev.packets import (
    JEV_REQUEST_BYTE_BUDGET,
    case_documents,
    case_request,
    request_byte_count,
)
from legalforecast.jev.prepare import prepare_summaries
from legalforecast.release import load_forecast_run_inputs

_SUMMARY_MODELS: Mapping[str, tuple[str, str, str]] = {
    "luna": ("openai", "gpt-5.6-luna", "luna_summaries"),
    "grok": ("vercel_ai_gateway", "spacexai/grok-4.6", "grok_summaries"),
}


def _summary_model_config(summary_model: object) -> tuple[str, str, str]:
    if not isinstance(summary_model, str) or summary_model not in _SUMMARY_MODELS:
        raise ValueError(f"unsupported summary model: {summary_model!r}")
    return _SUMMARY_MODELS[summary_model]


def _validate_summary_cache_model(raw: bytes, *, expected_model: str) -> None:
    """Reject a cache whose persisted records belong to another summarizer."""

    try:
        payload: object = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Jev summary cache is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Jev summary cache must be a JSON object")
    payload_object = cast(dict[str, object], payload)
    records = payload_object.get("records")
    if not isinstance(records, dict):
        raise ValueError("Jev summary cache records must be a JSON object")
    observed: set[str] = set()
    for case_records in cast(dict[object, object], records).values():
        if not isinstance(case_records, dict):
            raise ValueError("Jev summary cache case records must be JSON objects")
        for summary_value in cast(dict[object, object], case_records).values():
            if not isinstance(summary_value, dict):
                raise ValueError("Jev summary cache records require a model")
            summary = cast(dict[object, object], summary_value)
            model = summary.get("model")
            if not isinstance(model, str):
                raise ValueError("Jev summary cache records require a model")
            observed.add(model)
    if observed and observed != {expected_model}:
        found = ", ".join(sorted(observed))
        raise ValueError(
            "Jev summary cache model does not match the selected summary model: "
            f"expected {expected_model!r}, found {found}"
        )


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
                else (
                    "Generate and persist document summaries; cached documents are "
                    "reused."
                )
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
                "--summary-registry",
                "--luna-registry",
                dest="luna_registry",
                type=Path,
                required=True,
                help=(
                    "Frozen summary registry; --luna-registry is the legacy alias. "
                    "The selected model must be openai:gpt-5.6-luna or "
                    "vercel_ai_gateway:spacexai/grok-4.6."
                ),
            )
            child.add_argument(
                "--summary-model",
                choices=tuple(_SUMMARY_MODELS),
                default="luna",
                help="Summary model to use (default: luna).",
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
            child.add_argument(
                "--reconcile-saved-overrun",
                action="store_true",
                help=(
                    "Reconcile saved provider output into the summary ledger without "
                    "making a provider call."
                ),
            )
        child.set_defaults(handler=run_inputs)
    registry = commands.add_parser(
        "registry",
        help="Freeze Jev method and optional summary cache in a model registry.",
    )
    registry.add_argument(
        "--summaries",
        type=Path,
        help="Completed summary cache; omit for full-text mode.",
    )
    registry.add_argument(
        "--summary-model",
        choices=tuple(_SUMMARY_MODELS),
        default="luna",
        help="Summary model used by --summaries (default: luna).",
    )
    registry.add_argument(
        "--predictor",
        choices=("jev", "luna"),
        default="jev",
        help=(
            "One-shot predictor to freeze: Jev (default), or the bounded Luna "
            "summary comparator."
        ),
    )
    registry.add_argument(
        "--reasoning-effort",
        choices=("none", "high"),
        help="Luna comparator reasoning condition; required with --predictor luna.",
    )
    registry.add_argument(
        "--predictor-registry",
        type=Path,
        help=(
            "Existing registry containing the frozen openai:gpt-5.6-luna base "
            "entry used for comparator pricing and provenance."
        ),
    )
    registry.add_argument(
        "--provider",
        choices=("typesafe", "vercel_ai_gateway"),
        default="typesafe",
        help=(
            "Frozen Jev route. The first-party TypeSafe route is the default; "
            "use vercel_ai_gateway only to reproduce the historical Gateway route."
        ),
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
        summary_model = getattr(args, "summary_model", "luna")
        summary_provider, summary_model_id, _summary_mode = _summary_model_config(
            summary_model
        )
        entry = load_model_registry(cast(Path, args.luna_registry)).get(
            summary_provider, summary_model_id
        )
        summary_kwargs: dict[str, object] = {
            "execution": execution,
            "entry": entry,
            "cache_path": cast(Path, args.cache),
            "ledger_path": cast(Path, args.ledger),
            "ceiling_microusd": cast(int, args.ceiling_microusd),
        }
        if getattr(args, "reconcile_saved_overrun", False):
            summary_kwargs["reconcile_saved_overrun"] = True
        result = prepare_summaries(**summary_kwargs)  # type: ignore[arg-type]
        print(json.dumps(result, sort_keys=True))
        return 0
    rows: list[dict[str, object]] = []
    for case in execution.release.cases:
        units = tuple(
            u for u in execution.release.prediction_units if u.case_id == case.case_id
        )
        documents = case_documents(execution, units)
        request = case_request(units, documents)
        size = request_byte_count(request)
        estimate = estimate_request_context(request)
        rows.append(
            {
                "case_id": case.case_id,
                "unit_count": len(units),
                "document_count": len(documents),
                "request_bytes": size,
                "estimated_total_tokens_with_headroom": estimate.total_tokens,
                "estimated_state_question_tokens_with_headroom": (
                    estimate.state_plus_longest_question_tokens
                ),
                "fits_estimated_token_budget": estimate.fits,
            }
        )
    print(
        json.dumps(
            {
                "release_digest": execution.release.release_digest,
                "case_count": len(rows),
                "unit_count": execution.release.unit_count,
                "summary_planning_target_bytes": JEV_REQUEST_BYTE_BUDGET,
                "token_count": "estimated: max(cl100k_base, o200k_base) * 1.5 + 1024; "
                "provider publishes no exact tokenizer",
                "cases": rows,
            },
            sort_keys=True,
        )
    )
    return 0


def run_registry(args: argparse.Namespace) -> int:
    """Freeze one supported Jev route without inventing a model snapshot."""

    path = cast(Path | None, args.summaries)
    provider = cast(str, args.provider)
    summary_model = getattr(args, "summary_model", "luna")
    predictor = cast(str, getattr(args, "predictor", "jev"))
    reasoning_effort = cast(str | None, getattr(args, "reasoning_effort", None))
    _summary_provider, summary_model_id, summary_mode = _summary_model_config(
        summary_model
    )
    if predictor == "luna":
        if summary_model != "luna":
            raise ValueError("the Luna comparator requires --summary-model luna")
        if reasoning_effort is None:
            raise ValueError("--reasoning-effort is required when --predictor is luna")
        if provider != "typesafe":
            raise ValueError("--provider is only configurable for the Jev predictor")
    elif reasoning_effort is not None:
        raise ValueError("--reasoning-effort requires --predictor luna")

    raw_summaries: bytes | None = None
    if path is not None:
        raw_summaries = read_single_link_file(path, label="Jev summaries")
        _validate_summary_cache_model(raw_summaries, expected_model=summary_model_id)
    digest = (
        None
        if path is None
        else str(
            RAW_BYTES_RAW_SHA256_V1.commit(
                cast(bytes, raw_summaries),
                domain=PUBLIC_RUN_RECEIPT_V1,
            ).digest
        )
    )
    if predictor == "luna":
        base_path = cast(Path | None, getattr(args, "predictor_registry", None))
        if base_path is None:
            base_path = Path("model_registries/cycle-1-2026-06-30.json")
        base_entry = load_model_registry(base_path).get("openai", "gpt-5.6-luna")
        record = base_entry.to_record()
        record.update(
            {
                "display_name": (
                    f"Luna (Luna summaries; one shot; reasoning {reasoning_effort})"
                ),
                "max_output_tokens": 16000,
                "context_limit": 64000,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "no_tools",
                "reasoning_effort": reasoning_effort,
                "jev_input_mode": "luna_summaries",
            }
        )
        # The comparator is intentionally bounded to the same summary context
        # budget as Jev. Its standard Luna prices remain those of the frozen
        # base entry; the base long-context surcharge cannot apply at 64K.
        record.pop("long_context_surcharge", None)
    else:
        direct_typesafe = provider == "typesafe"
        record = {
            "provider": provider,
            "model_id": "jev-1.13.0" if direct_typesafe else "typesafe-ai/jev",
            "display_name": (
                "Jev ("
                + ("Grok 4.6" if summary_model == "grok" else "Luna")
                + " summaries; one shot)"
                if path
                else "Jev (full text; one shot)"
            ),
            "model_version_or_snapshot": (
                "jev-1.13.0" if direct_typesafe else "typesafe-ai/jev"
            ),
            "release_timestamp": "2026-09-15T00:00:00Z",
            "release_timestamp_source": "https://vercel.com/ai-gateway/models/jev",
            "provider_training_cutoff_status": "not_disclosed",
            "max_output_tokens": 1,
            "context_limit": 64000,
            "network_disabled": True,
            "search_disabled": True,
            "tool_policy": "no_tools",
            "pricing_source": (
                "https://docs.typesafe.ai/models"
                if direct_typesafe
                else "https://vercel.com/ai-gateway/models/jev"
            ),
            "input_token_price": 0.042,
            "output_token_price": 0.0,
            "known_cutoff_publicity_caveats": [
                (
                    "TypeSafe first-party API route pinned to Jev 1.13.0; "
                    "output tokens "
                    "are free and summary preparation costs are reported separately."
                    if direct_typesafe
                    else (
                        "Provider does not expose a dated Jev snapshot or exact "
                        "tokenizer. One-shot condition; summary preparation costs "
                        "reported separately."
                    )
                )
            ],
            "jev_input_mode": "full_text" if path is None else summary_mode,
        }
    if digest is not None:
        record["jev_summaries_sha256"] = digest
    registry = ModelRegistry.from_records([record])
    write_file_create_only(
        cast(Path, args.output),
        ARTIFACT_CANONICAL_JSON_V1.encode(registry.to_records()),
    )
    return 0
