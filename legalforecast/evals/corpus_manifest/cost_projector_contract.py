"""Shared request and row contracts for manifest cost projection."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.protocol.freeze import (
    FreezeBundle,
    FreezeProtocolError,
    load_freeze_bundle,
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
AGGREGATE_MATRIX_LIMIT: Final = 800
OFFICIAL_SHARD_MATRIX_LIMIT: Final = 256


class ManifestCostProjectionError(ValueError):
    """Raised when cost inputs or issuance fail closed."""


def raw_commitment(payload: bytes) -> dict[str, int | str]:
    """Commit exact input bytes by digest and length."""

    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def required_sha256(record: Mapping[str, Any], field_name: str, label: str) -> str:
    """Return one required lowercase SHA-256 field."""

    value = record.get(field_name)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ManifestCostProjectionError(
            f"{label} {field_name} must be a lowercase SHA-256"
        )
    return value


def required_mapping(value: object, label: str) -> Mapping[str, Any]:
    """Return one required object mapping."""

    if not isinstance(value, Mapping):
        raise ManifestCostProjectionError(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def require_exact_amendment_chain(
    bundle: FreezeBundle,
    *,
    amendment_bundles: Sequence[Path],
    freeze_root: Path,
) -> None:
    """Require supplied ancestors to equal the complete referenced chain."""

    ancestors: dict[str, FreezeBundle] = {}
    for path in amendment_bundles:
        ancestor = load_freeze_bundle(path, root_path=freeze_root)
        if ancestor.bundle_sha256 in ancestors:
            raise FreezeProtocolError(
                "freeze amendment bundle list contains duplicate bundle commitments"
            )
        ancestors[ancestor.bundle_sha256] = ancestor

    referenced: set[str] = set()
    current = bundle
    while current.amends_bundle_sha256 is not None:
        parent_hash = current.amends_bundle_sha256
        parent = ancestors.get(parent_hash)
        if parent is None:
            raise FreezeProtocolError(
                "amendment ancestor bundle is missing from the exact committed chain: "
                f"{parent_hash}"
            )
        if parent_hash in referenced:
            raise FreezeProtocolError("freeze amendment chain contains a cycle")
        referenced.add(parent_hash)
        current = parent

    extras = sorted(set(ancestors) - referenced)
    if extras:
        raise FreezeProtocolError(
            "unreferenced amendment bundles are not part of the exact committed chain: "
            f"{extras}"
        )


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
    shard_only: bool
    output: Path
    supplementary: bool = False
    """Project a post-anchor supplementary shard.

    The release-anchor gate inverts rather than switching off: the sibling freeze
    must reuse the official prompt and corpus bytes and replace only the model
    registry, and every model it names must classify post-anchor.  An official
    projection leaves every input and every receipt byte exactly as before.
    """

    official_freeze_bundle: Path | None = None
    """Official freeze bundle the sibling freeze must match, byte for byte.

    Required in supplementary mode and refused in official mode.  It is read only
    for its recorded artifact digests, so the official artifact bytes need not be
    present -- the comparability claim is verified, not waived.
    """

    official_freeze_bundle_sha256: str | None = None
    """Independent digest pin for ``official_freeze_bundle``.

    Without it the reference bundle would be trusted for being self-consistent,
    and a fabricated bundle copying its shared-artifact digests from the sibling
    would satisfy every identity check -- the sibling's own prompt bytes would be
    doing the grounding.  The operator supplies this at dispatch from the staged
    official freeze's recorded digest.
    """

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ManifestCostProjectionError("cycle_id is required")
        supplied = (self.official_freeze_bundle, self.official_freeze_bundle_sha256)
        if self.supplementary and None in supplied:
            raise ManifestCostProjectionError(
                "supplementary projection requires --official-freeze-bundle and "
                "--official-freeze-bundle-sha256"
            )
        if not self.supplementary and supplied != (None, None):
            raise ManifestCostProjectionError(
                "official projection does not accept --official-freeze-bundle or "
                "--official-freeze-bundle-sha256"
            )
        if not 1 <= self.repeat_count <= 10:
            raise ManifestCostProjectionError(
                "repeat_count must be an integer from 1 through 10"
            )
        if self.matrix_limit < 1:
            raise ManifestCostProjectionError("matrix_limit must be positive")
        if not self.shard_only and self.matrix_limit < AGGREGATE_MATRIX_LIMIT:
            raise ManifestCostProjectionError(
                "aggregate matrix_limit must be at least 800 rows"
            )
        if self.shard_only and self.matrix_limit > OFFICIAL_SHARD_MATRIX_LIMIT:
            raise ManifestCostProjectionError(
                "shard-only matrix_limit must not exceed 256 rows"
            )


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
