"""Fail-closed entrypoint for protected paid-labeling workflow jobs."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.model_registry import load_model_registry
from legalforecast.labeling.provider_journal import load_provider_cycle_caps

SCHEMA_VERSION = "legalforecast.official_paid_labeling_job.v1"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_STAGE_PROVIDERS = {
    "llm-unitize": frozenset({"anthropic"}),
    "llm-review-stage-a": frozenset({"google"}),
    "llm-label-provider-shard": frozenset({"google", "openai"}),
}
_COMMAND_BY_STAGE = {
    "llm-unitize": "llm-unitize",
    "llm-review-stage-a": "llm-review-stage-a",
    "llm-label-provider-shard": "llm-label",
}
_COMMON_ARGUMENTS = frozenset(
    {
        "audit-output",
        "continue-on-error",
        "log-output",
        "markdown-root",
        "model-key",
        "model-registry",
        "no-resume",
        "output-root",
        "parser-manifest",
        "provider-cycle-caps",
        "provider-journal",
        "run-card-output",
        "selection",
        "timeout-seconds",
    }
)
_STAGE_ARGUMENTS = {
    "llm-unitize": _COMMON_ARGUMENTS
    | {
        "disclosure-clearance",
        "document-root",
        "download-manifest",
        "materialization-run-card",
        "parse-requests",
        "parser-run-card",
        "prediction-units-output",
        "selection-run-card",
        "unitization-review-queue-output",
    },
    "llm-review-stage-a": _COMMON_ARGUMENTS
    | {
        "llm-unitization-run-card",
        "prediction-units",
        "review-queue-output",
        "structural-flags-output",
        "unitization-review-queue",
    },
    "llm-label-provider-shard": _COMMON_ARGUMENTS
    | {
        "consensus-policy",
        "decision-texts",
        "decision-texts-manifest",
        "decision-texts-run-card",
        "evaluated-model-registry",
        "high-confidence-threshold",
        "labels-output",
        "lawyer-review-queue-output",
        "llm-review-stage-a-run-card",
        "llm-unitization-run-card",
        "prediction-units",
        "unitization-review-run-card",
    },
}
_PATH_ARGUMENTS = frozenset(
    {
        "audit-output",
        "decision-texts",
        "decision-texts-manifest",
        "decision-texts-run-card",
        "disclosure-clearance",
        "document-root",
        "download-manifest",
        "evaluated-model-registry",
        "labels-output",
        "lawyer-review-queue-output",
        "llm-review-stage-a-run-card",
        "llm-unitization-run-card",
        "log-output",
        "markdown-root",
        "materialization-run-card",
        "model-registry",
        "output-root",
        "parse-requests",
        "parser-manifest",
        "parser-run-card",
        "prediction-units",
        "prediction-units-output",
        "provider-cycle-caps",
        "provider-journal",
        "review-queue-output",
        "run-card-output",
        "selection",
        "selection-run-card",
        "structural-flags-output",
        "unitization-review-queue",
        "unitization-review-queue-output",
        "unitization-review-run-card",
    }
)
_BOOLEAN_ARGUMENTS = frozenset({"continue-on-error", "no-resume"})
_REPEATABLE_ARGUMENTS = frozenset({"model-key"})


class OfficialPaidLabelingJobError(ValueError):
    """Raised before a protected job can cross its reviewed boundary."""


def run_official_paid_labeling_job(
    *,
    job_manifest_path: Path,
    job_root: Path,
    release_sha: str,
    stage: str,
    provider: str,
    provider_authority_table: str,
    provider_authority_region: str,
    expected_provider_account_alias: str,
) -> int:
    """Validate a sealed job manifest and invoke the normal acquisition CLI."""

    manifest_path = _within_root(job_manifest_path, job_root, must_exist=True)
    payload = _json_object(manifest_path)
    if set(payload) != {
        "schema_version",
        "release_sha",
        "stage",
        "provider",
        "arguments",
    }:
        raise OfficialPaidLabelingJobError(
            "official paid-labeling job manifest keys differ from the exact schema"
        )
    normalized_stage = _choice(stage, _STAGE_PROVIDERS, "stage")
    normalized_provider = _choice(
        provider,
        _STAGE_PROVIDERS[normalized_stage],
        "provider",
    )
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("stage") != normalized_stage
        or payload.get("provider") != normalized_provider
        or payload.get("release_sha") != release_sha
        or _SHA.fullmatch(release_sha) is None
    ):
        raise OfficialPaidLabelingJobError(
            "official paid-labeling job identity differs from protected inputs"
        )
    if not provider_authority_table.strip() or not provider_authority_region.strip():
        raise OfficialPaidLabelingJobError(
            "protected provider authority table and region are required"
        )
    raw_arguments = payload.get("arguments")
    if not isinstance(raw_arguments, Mapping):
        raise OfficialPaidLabelingJobError(
            "official paid-labeling arguments must be an object"
        )
    arguments = cast(Mapping[str, object], raw_arguments)
    unknown = set(arguments) - _STAGE_ARGUMENTS[normalized_stage]
    if unknown:
        raise OfficialPaidLabelingJobError(
            f"official paid-labeling arguments are not allowlisted: {sorted(unknown)}"
        )

    cli_arguments: list[str] = [
        "acquisition",
        _COMMAND_BY_STAGE[normalized_stage],
    ]
    resolved_paths: dict[str, Path] = {}
    for name in sorted(arguments):
        value = arguments[name]
        if name in _BOOLEAN_ARGUMENTS:
            if not isinstance(value, bool):
                raise OfficialPaidLabelingJobError(
                    f"official paid-labeling {name} must be boolean"
                )
            if value:
                cli_arguments.append(f"--{name}")
            continue
        values: Sequence[object]
        if name in _REPEATABLE_ARGUMENTS:
            if not isinstance(value, list) or not value:
                raise OfficialPaidLabelingJobError(
                    f"official paid-labeling {name} must be a non-empty array"
                )
            values = cast(list[object], value)
        else:
            values = (value,)
        for raw_value in values:
            if not isinstance(raw_value, (str, int, float)) or isinstance(
                raw_value, bool
            ):
                raise OfficialPaidLabelingJobError(
                    f"official paid-labeling {name} has an invalid value"
                )
            rendered = str(raw_value)
            if not rendered.strip():
                raise OfficialPaidLabelingJobError(
                    f"official paid-labeling {name} must not be empty"
                )
            if name in _PATH_ARGUMENTS:
                path = _within_root(
                    job_root / rendered,
                    job_root,
                    must_exist=False,
                )
                resolved_paths[name] = path
                rendered = str(path)
            cli_arguments.extend((f"--{name}", rendered))

    caps_path = resolved_paths.get("provider-cycle-caps")
    registry_path = resolved_paths.get("model-registry")
    if caps_path is None or registry_path is None:
        raise OfficialPaidLabelingJobError(
            "provider-cycle-caps and model-registry are required"
        )
    caps = load_provider_cycle_caps(caps_path)
    if caps.account(normalized_provider) != expected_provider_account_alias:
        raise OfficialPaidLabelingJobError(
            "protected provider account alias differs from provider-cycle-caps"
        )
    registry = load_model_registry(registry_path)
    raw_model_keys = arguments.get("model-key")
    model_keys = (
        tuple(cast(list[str], raw_model_keys))
        if isinstance(raw_model_keys, list)
        else (cast(str, raw_model_keys),)
    )
    selected_entries = tuple(
        entry for entry in registry.entries if entry.registry_key in model_keys
    )
    if len(selected_entries) != len(set(model_keys)):
        raise OfficialPaidLabelingJobError(
            "job model keys do not resolve uniquely in the frozen registry"
        )
    if normalized_stage == "llm-label-provider-shard":
        if {entry.registry_key for entry in selected_entries} != {
            entry.registry_key for entry in registry.entries
        }:
            raise OfficialPaidLabelingJobError(
                "Stage B provider shard must receive the complete frozen judge panel"
            )
        if not any(
            entry.provider.lower() == normalized_provider for entry in selected_entries
        ):
            raise OfficialPaidLabelingJobError(
                "Stage B provider shard has no model for its provider"
            )
        cli_arguments.extend(("--execution-provider", normalized_provider))
    elif len(selected_entries) != 1 or (
        selected_entries[0].provider.lower() != normalized_provider
    ):
        raise OfficialPaidLabelingJobError(
            "paid-labeling model does not match the protected stage/provider"
        )
    cli_arguments.extend(
        (
            "--provider-authority-table",
            provider_authority_table,
            "--provider-authority-region",
            provider_authority_region,
            "--execute",
        )
    )
    from legalforecast.cli import main

    return main(cli_arguments)


def _within_root(path: Path, root: Path, *, must_exist: bool) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=must_exist)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise OfficialPaidLabelingJobError(
            "official paid-labeling path escapes the sealed job root"
        )
    return resolved


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialPaidLabelingJobError(
            "official paid-labeling job manifest is unreadable"
        ) from exc
    if not isinstance(value, dict):
        raise OfficialPaidLabelingJobError(
            "official paid-labeling job manifest must be an object"
        )
    return cast(dict[str, Any], value)


def _choice(
    value: str, choices: Mapping[str, object] | frozenset[str], field: str
) -> str:
    normalized = value.strip().lower()
    if normalized not in choices:
        raise OfficialPaidLabelingJobError(
            f"official paid-labeling {field} is outside the reviewed allowlist"
        )
    return normalized


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one protected, provider-isolated paid-labeling job."
    )
    parser.add_argument("--job-manifest", type=Path, required=True)
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--provider-authority-table", required=True)
    parser.add_argument("--provider-authority-region", required=True)
    parser.add_argument("--expected-provider-account-alias", required=True)
    args = parser.parse_args(argv)
    try:
        return run_official_paid_labeling_job(
            job_manifest_path=args.job_manifest,
            job_root=args.job_root,
            release_sha=args.release_sha,
            stage=args.stage,
            provider=args.provider,
            provider_authority_table=args.provider_authority_table,
            provider_authority_region=args.provider_authority_region,
            expected_provider_account_alias=args.expected_provider_account_alias,
        )
    except OfficialPaidLabelingJobError as exc:
        parser.error(str(exc))


if __name__ == "__main__":  # pragma: no cover - exercised through protected workflow
    raise SystemExit(main())
