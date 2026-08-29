"""GitHub Actions adapter for the provider-free manifest cost projector."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.corpus_manifest.cost_projector import (
    PROVIDER_LANES,
    ManifestCostProjectionError,
    ManifestCostProjectionRequest,
    issue_manifest_cost_projection,
)


def issue_manifest_cost_projection_from_workflow_environment(
    environment: Mapping[str, str],
) -> dict[str, Any]:
    """Delegate the official workflow environment to the shared issuer."""

    supplementary = _optional_environment_bool(environment, "SUPPLEMENTARY")
    official_freeze_bundle = environment.get("OFFICIAL_FREEZE_BUNDLE_PATH", "").strip()
    if supplementary and not official_freeze_bundle:
        raise ManifestCostProjectionError(
            "OFFICIAL_FREEZE_BUNDLE_PATH is required when SUPPLEMENTARY is true"
        )
    if not supplementary and official_freeze_bundle:
        raise ManifestCostProjectionError(
            "OFFICIAL_FREEZE_BUNDLE_PATH is only valid when SUPPLEMENTARY is true"
        )
    request = ManifestCostProjectionRequest(
        freeze_bundle=Path(_required_env(environment, "FREEZE_BUNDLE_PATH")),
        freeze_root=Path(_required_env(environment, "FREEZE_ROOT")),
        manifest_run_root=Path(_required_env(environment, "MANIFEST_RUN_ROOT")),
        amendment_bundles=tuple(
            Path(value)
            for value in environment.get("FREEZE_AMENDMENT_BUNDLES", "").splitlines()
            if value.strip()
        ),
        cycle_id=_required_env(environment, "CYCLE_ID"),
        model_keys=tuple(_split_csv(_required_env(environment, "MODEL_KEYS"))),
        ablations=tuple(_split_csv(_required_env(environment, "ABLATIONS"))),
        repeat_count=_environment_int(environment, "REPEAT_COUNT"),
        repeat_sample_case_ids=tuple(
            _split_csv(environment.get("REPEAT_SAMPLE_CASE_IDS", ""))
        ),
        max_projected_model_cost_usd=(
            environment.get("MAX_PROJECTED_MODEL_COST_USD", "").strip() or None
        ),
        matrix_limit=_environment_int(environment, "MATRIX_LIMIT"),
        shard_only=_environment_bool(environment, "SHARD_ONLY"),
        output=Path(_required_env(environment, "COST_PROJECTION_RECEIPT_PATH")),
        supplementary=supplementary,
        official_freeze_bundle=(
            Path(official_freeze_bundle) if official_freeze_bundle else None
        ),
    )
    receipt = issue_manifest_cost_projection(request)
    _append_github_outputs(Path(_required_env(environment, "GITHUB_OUTPUT")), receipt)
    _append_step_summary(
        Path(_required_env(environment, "GITHUB_STEP_SUMMARY")), receipt
    )
    return receipt


def _required_env(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ManifestCostProjectionError(f"{name} is required")
    return value


def _environment_int(environment: Mapping[str, str], name: str) -> int:
    raw = _required_env(environment, name)
    try:
        return int(raw)
    except ValueError as exc:
        raise ManifestCostProjectionError(f"{name} must be an integer") from exc


def _environment_bool(environment: Mapping[str, str], name: str) -> bool:
    raw = _required_env(environment, name)
    if raw not in {"true", "false"}:
        raise ManifestCostProjectionError(f"{name} must be true or false")
    return raw == "true"


def _optional_environment_bool(environment: Mapping[str, str], name: str) -> bool:
    """Read a Boolean whose absence means the official lane.

    Fail-closed by omission: a workflow that never sets the variable, and every
    caller written before this lane existed, projects officially.
    """

    raw = environment.get(name, "").strip()
    if not raw:
        return False
    if raw not in {"true", "false"}:
        raise ManifestCostProjectionError(f"{name} must be true or false")
    return raw == "true"


def _split_csv(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _append_github_outputs(path: Path, receipt: Mapping[str, Any]) -> None:
    shard_only = receipt.get("shard_only") is True
    lines: list[str] = []
    for provider in PROVIDER_LANES:
        lines.append(f"{provider}_count={receipt[f'{provider}_count']}")
        if shard_only:
            lines.append(
                f"{provider}_matrix="
                + json.dumps(
                    receipt[f"{provider}_matrix"],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
    if shard_only:
        lines.insert(
            0,
            "matrix="
            + json.dumps(receipt["matrix"], ensure_ascii=False, separators=(",", ":")),
        )
    for name in (
        "case_count",
        "packet_count",
        "cell_count",
        "matrix_row_count",
        "shard_matrix_row_count",
        "request_count",
        "attempt_count",
        "model_count",
        "long_context_surcharge_packet_count",
        "long_context_surcharge_packets_json",
        "projected_model_cost_usd",
        "recommended_max_projected_model_cost_usd",
    ):
        lines.append(f"{name}={receipt[name]}")
    with path.open("a", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")


def _append_step_summary(path: Path, receipt: Mapping[str, Any]) -> None:
    projected = cast(str, receipt["projected_model_cost_usd"])
    ceiling = cast(str, receipt["recommended_max_projected_model_cost_usd"])
    lines = [
        "## Official evaluation cost preflight",
        "",
        f"- Projected model cost: ${float(projected):.2f}",
        "- Recommended max_projected_model_cost_usd (2x projection): "
        f"${float(ceiling):.2f}",
        "- The dispatch ceiling is an early-warning control, not a provider "
        "or account cap.",
    ]
    long_context = cast(list[dict[str, Any]], receipt["long_context_surcharge_packets"])
    if long_context:
        lines.extend(
            [
                "",
                "### Long-context surcharge packet warning",
                "",
                "Packets above 272,000 estimated input tokens require deliberate "
                "pricing or exclusion before a live run.",
                "",
                "```json",
                json.dumps(long_context, indent=2),
                "```",
            ]
        )
    with path.open("a", encoding="utf-8") as summary:
        summary.write("\n".join(lines) + "\n")
