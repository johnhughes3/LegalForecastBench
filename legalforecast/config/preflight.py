"""Selector-versus-evaluation-registry preflight.

Any selection entrypoint must call ``preflight_selector_models`` with the same
``CycleConfig`` that supplied the selector policy. The evaluation registry is
read only from that config's pin — never from a default Cycle 1 path.
"""

from __future__ import annotations

from pathlib import Path

from legalforecast.config.errors import (
    EvaluationRegistryPinError,
    SelectorRegistryCollisionError,
)
from legalforecast.config.registry import repository_root
from legalforecast.config.types import CycleConfig, SelectorModel
from legalforecast.contracts import RAW_BYTES_RAW_SHA256_V1
from legalforecast.contracts.schemas import RAW_BYTES_RAW_SHA256_COMMITMENT_V1
from legalforecast.evals.model_registry import ModelRegistry, load_model_registry_bytes


def preflight_selector_models(
    config: CycleConfig,
    *,
    repository_root_path: Path | None = None,
) -> ModelRegistry:
    """Refuse if any configured selector appears in this cycle's eval registry.

    Both sides come from ``config``. A missing, unreadable, or hash-mismatched
    registry pin fails closed with a legible error.
    """

    registry_path = _resolve_registry_path(
        config, repository_root_path=repository_root_path
    )
    payload = _read_registry_bytes(config, registry_path)
    _require_pin_digest(config, payload, registry_path)
    try:
        registry = load_model_registry_bytes(payload)
    except ValueError as exc:
        raise EvaluationRegistryPinError(
            f"cycle {config.cycle_id!r} evaluation registry pin "
            f"{config.evaluation_registry.path!r} is not a valid model registry: {exc}"
        ) from exc
    collisions = _collisions(config, registry)
    if collisions:
        detail = "; ".join(collisions)
        raise SelectorRegistryCollisionError(
            f"cycle {config.cycle_id!r} selector-model policy is not disjoint "
            f"from pinned evaluation registry {config.evaluation_registry.path!r}. "
            f"Collisions: {detail}. Refuse to run selection; choose a selector "
            "that does not appear in this cycle's evaluation registry. Both "
            "sides were read from this cycle config (no side-channel lookup)."
        )
    return registry


def _resolve_registry_path(
    config: CycleConfig, *, repository_root_path: Path | None
) -> Path:
    raw = Path(config.evaluation_registry.path)
    if raw.is_absolute():
        return raw
    root = (
        repository_root_path if repository_root_path is not None else repository_root()
    )
    return root / raw


def _read_registry_bytes(config: CycleConfig, path: Path) -> bytes:
    try:
        if not path.exists() or path.is_symlink() or not path.is_file():
            raise EvaluationRegistryPinError(
                f"cycle {config.cycle_id!r} evaluation registry pin "
                f"{config.evaluation_registry.path!r} is not a readable regular file "
                f"(resolved {str(path)!r}). Both the selector policy and the "
                "evaluation registry must come from this cycle config; there is "
                "no side-channel registry lookup."
            )
        return path.read_bytes()
    except OSError as exc:
        raise EvaluationRegistryPinError(
            f"cycle {config.cycle_id!r} evaluation registry pin "
            f"{config.evaluation_registry.path!r} could not be read: {exc}"
        ) from exc


def _require_pin_digest(config: CycleConfig, payload: bytes, path: Path) -> None:
    expected = config.evaluation_registry.sha256
    if expected is None:
        return
    actual = str(
        RAW_BYTES_RAW_SHA256_V1.commit(
            payload, domain=RAW_BYTES_RAW_SHA256_COMMITMENT_V1
        ).digest
    )
    if actual != expected:
        raise EvaluationRegistryPinError(
            f"cycle {config.cycle_id!r} evaluation registry pin "
            f"{config.evaluation_registry.path!r} SHA-256 is {actual}, "
            f"expected {expected} (resolved {str(path)!r})."
        )


def _collisions(config: CycleConfig, registry: ModelRegistry) -> tuple[str, ...]:
    evaluated_keys = {entry.registry_key for entry in registry.entries}
    evaluated_ids = {(entry.provider, entry.model_id) for entry in registry.entries}
    evaluated_versions = {
        (entry.provider, entry.model_version_or_snapshot) for entry in registry.entries
    }
    found: list[str] = []
    for index, model in enumerate(config.selector_model_policy.all_models()):
        role = "primary" if index == 0 else f"alternate[{index - 1}]"
        reasons = _match_reasons(
            model,
            evaluated_keys=evaluated_keys,
            evaluated_ids=evaluated_ids,
            evaluated_versions=evaluated_versions,
        )
        if reasons:
            found.append(
                f"{role} {model.registry_key} (model_id={model.model_id!r}, "
                f"version={model.model_version_or_snapshot!r}) matches evaluated "
                f"registry by {', '.join(reasons)}"
            )
    return tuple(found)


def _match_reasons(
    model: SelectorModel,
    *,
    evaluated_keys: set[str],
    evaluated_ids: set[tuple[str, str]],
    evaluated_versions: set[tuple[str, str]],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if model.registry_key in evaluated_keys:
        reasons.append("registry_key")
    identity = (model.provider, model.model_id)
    version = (model.provider, model.model_version_or_snapshot)
    if identity in evaluated_ids:
        reasons.append("model_id")
    if (
        identity in evaluated_versions
        or version in evaluated_ids
        or version in evaluated_versions
    ):
        reasons.append("model_version_or_snapshot")
    return tuple(reasons)
