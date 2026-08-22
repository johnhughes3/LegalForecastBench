"""Shared request and row contracts for manifest cost projection."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")


class ManifestCostProjectionError(ValueError):
    """Raised when cost inputs or issuance fail closed."""


@dataclass(frozen=True, slots=True)
class ManifestCostProjectionRequest:
    """Inputs to one deterministic provider-free cost projection."""

    freeze_bundle: Path
    freeze_root: Path
    manifest_run_root: Path
    amendment_bundles: tuple[Path, ...]
    cycle_id: str
    model_keys: tuple[str, ...]
    ablations: tuple[str, ...]
    repeat_count: int
    repeat_sample_case_ids: tuple[str, ...]
    max_projected_model_cost_usd: str | None
    matrix_limit: int
    output: Path

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ManifestCostProjectionError("cycle_id is required")
        if not 1 <= self.repeat_count <= 10:
            raise ManifestCostProjectionError(
                "repeat_count must be an integer from 1 through 10"
            )
        if self.matrix_limit < 1:
            raise ManifestCostProjectionError("matrix_limit must be positive")


def packet_sha256_from_row(packet: Mapping[str, Any]) -> str:
    """Return one unambiguous lowercase packet digest from a run-input row."""

    sha256_value = packet.get("sha256")
    packet_sha256_value = packet.get("packet_sha256")
    for field_name, value in (
        ("sha256", sha256_value),
        ("packet_sha256", packet_sha256_value),
    ):
        if value is not None and (
            not isinstance(value, str) or _SHA256.fullmatch(value) is None
        ):
            raise ManifestCostProjectionError(
                f"each matrix row {field_name} must be a lowercase SHA-256"
            )
    if sha256_value is None and packet_sha256_value is None:
        raise ManifestCostProjectionError(
            "each matrix row requires sha256 or packet_sha256"
        )
    if (
        sha256_value is not None
        and packet_sha256_value is not None
        and sha256_value != packet_sha256_value
    ):
        raise ManifestCostProjectionError(
            "matrix row has conflicting sha256 and packet_sha256"
        )
    return cast(str, sha256_value or packet_sha256_value)


def packet_object_key_from_row(packet: Mapping[str, Any]) -> str:
    """Return a packet key bounded to the immutable model-packets prefix."""

    value = (
        packet.get("packet_object_key") or packet.get("object_key") or packet.get("key")
    )
    if not isinstance(value, str) or not value.startswith("model-packets/"):
        raise ManifestCostProjectionError(
            "each matrix row requires model-packets/ packet_object_key"
        )
    parts = Path(value).parts
    if (
        Path(value).is_absolute()
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ManifestCostProjectionError(
            "packet_object_key is not a safe relative path"
        )
    return value


def required_nonnegative_int(
    record: Mapping[str, Any], field_name: str, *, label: str = "model registry"
) -> int:
    """Return one strict non-negative integer field."""

    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ManifestCostProjectionError(
            f"{label} {field_name} must be a non-negative integer"
        )
    return value
