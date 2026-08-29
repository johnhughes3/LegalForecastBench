"""Explicit supplementary (post-anchor) mode for the pre-dispatch chain.

PR #1003 inverted the release-anchor gate from the provider cell forward.  This
module is the same inversion one stage earlier, for the authorization chain that
runs *before* dispatch: cost projection and execution-scope issuance.  Nothing
here is a waiver.  Every check either stays exactly as it is in official mode or
is replaced by its mirror image, so both modes fail closed.

The comparability property the supplementary lane rests on is that a post-anchor
model runs against byte-identical corpus and prompt bytes.  That property is
*verified* here rather than assumed: a sibling freeze must agree with the
official freeze on every frozen artifact except the three the lane exists to
replace -- the model registry, its provider caps, and its execution policy -- and
must disagree on the registry.  A supplementary artifact therefore records both
bindings explicitly: which official contract it reuses, and which registry it
evaluates.

The official freeze is a *reference commitment*, so it is pinned by an
independently supplied digest rather than trusted for being self-consistent.
Without that pin a fabricated bundle could copy its shared-artifact digests from
the sibling itself and satisfy every identity check, since the sibling's own
prompt bytes would be doing the grounding.

Classification is never restated here.  Which lane a model belongs to comes from
``legalforecast.reporting.result_class``, the same module the aggregate uses, so
the pre-dispatch chain and the aggregate cannot drift into disagreeing about it.
Mode itself is carried as a plain ``supplementary: bool`` -- the convention PR
#1003 set on ``PerCaseRunnerConfig``, ``ForecastBuildRequest``, ``FanInConfig``
and ``OfficialAggregationConfig``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Final, cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FreezeProtocolError,
    FrozenArtifactName,
    load_freeze_bundle_bytes,
)
from legalforecast.reporting.result_class import (
    ResultClass,
    ResultClassError,
    corpus_anchor_from_decision_rows,
    require_lane_result_classes,
)

SUPPLEMENTARY_MODE: Final = ResultClass.SUPPLEMENTARY_POST_ANCHOR.value

SIBLING_REPLACEABLE_ARTIFACTS: Final = frozenset(
    {
        FrozenArtifactName.MODEL_REGISTRY,
        FrozenArtifactName.PROVIDER_CYCLE_CAPS,
        FrozenArtifactName.EXECUTION_POLICY,
    }
)
"""The only frozen artifacts a sibling freeze may replace.

The registry is the point of the lane; its provider caps and execution policy
follow mechanically from it.  Everything else -- manifest, units, labels, prompt,
scorer, harness, baselines, exclusion ledger, labeling policy, cohort policy --
must be the official bytes, which is what makes the supplementary row comparable
to the official four rather than merely adjacent to them.
"""

SUPPLEMENTARY_BINDING_FIELDS: Final = frozenset(
    {
        "execution_mode",
        "official_freeze_bundle_sha256",
        "official_model_registry_sha256",
        "official_evaluation_release_anchor",
        "corpus_anchor",
        "supplementary_model_registry_sha256",
        "supplementary_model_keys",
    }
)


class SupplementaryModeError(ValueError):
    """Raised when a supplementary or official mode binding does not hold."""


def load_pinned_reference_freeze_bundle(
    payload: bytes,
    *,
    cycle_id: str,
    expected_sha256: str,
    error_type: type[Exception] = SupplementaryModeError,
) -> FreezeBundle:
    """Parse an official freeze bundle from caller-pinned bytes.

    The caller supplies bytes it has already snapshotted, and the digest it
    expects them to have.  Hashing and parsing the same bytes is what stops an
    A->B->A replacement from recording a digest the identity checks never
    validated, and the independent digest is what stops a fabricated bundle from
    passing merely by being internally consistent.

    Only the bundle's own recorded artifact digests are read, so the official
    artifact *bytes* need not be present.  That keeps the identity check to one
    small JSON file rather than a second copy of the corpus.
    """

    if not is_lowercase_sha256(expected_sha256):
        raise error_type(
            "official freeze bundle digest must be a lowercase SHA-256 hex digest"
        )
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise error_type(
            "official freeze bundle bytes do not match the supplied digest pin"
        )
    try:
        bundle = load_freeze_bundle_bytes(payload)
    except (FreezeProtocolError, ValueError) as exc:
        raise error_type(f"official freeze bundle is not valid: {exc}") from exc
    if bundle.cycle_id != cycle_id:
        raise error_type(
            "official freeze bundle cycle_id does not match dispatch input"
        )
    return bundle


def require_sibling_freeze_identity(
    *,
    sibling: FreezeBundle,
    official: FreezeBundle,
    error_type: type[Exception] = SupplementaryModeError,
) -> None:
    """Require a sibling freeze to reuse the official contract byte for byte.

    Fails closed in both directions: a shared artifact that drifted is refused,
    and so is a "sibling" that binds the official registry, because that freeze
    is the official run and must not travel the supplementary lane.
    """

    if sibling.cycle_id != official.cycle_id:
        raise error_type("sibling freeze cycle_id differs from the official freeze")
    sibling_artifacts = {artifact.name: artifact for artifact in sibling.artifacts}
    official_artifacts = {artifact.name: artifact for artifact in official.artifacts}
    if set(sibling_artifacts) != set(official_artifacts):
        missing = sorted(
            name.value for name in set(official_artifacts) - set(sibling_artifacts)
        )
        extra = sorted(
            name.value for name in set(sibling_artifacts) - set(official_artifacts)
        )
        raise error_type(
            "sibling freeze artifact roles differ from the official freeze: "
            f"missing={missing}, unknown={extra}"
        )
    drifted = sorted(
        name.value
        for name, artifact in sibling_artifacts.items()
        if name not in SIBLING_REPLACEABLE_ARTIFACTS
        and (
            artifact.sha256 != official_artifacts[name].sha256
            or artifact.size_bytes != official_artifacts[name].size_bytes
        )
    )
    if drifted:
        replaceable = sorted(name.value for name in SIBLING_REPLACEABLE_ARTIFACTS)
        raise error_type(
            "sibling freeze must reuse the official frozen bytes for every "
            f"artifact except {replaceable}; differs: {drifted}"
        )
    if (
        sibling_artifacts[FrozenArtifactName.MODEL_REGISTRY].sha256
        == official_artifacts[FrozenArtifactName.MODEL_REGISTRY].sha256
    ):
        raise error_type(
            "supplementary mode requires a model registry distinct from the "
            "official frozen registry"
        )


def require_supplementary_registry(
    entries: Sequence[ModelRegistryEntry],
    *,
    corpus_anchor: date,
    error_type: type[Exception] = SupplementaryModeError,
) -> None:
    """Refuse a supplementary registry whose models classify official."""

    try:
        require_lane_result_classes(
            entries, corpus_anchor=corpus_anchor, supplementary=True
        )
    except ResultClassError as exc:
        raise error_type(str(exc)) from exc


def corpus_anchor_from_packet_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    error_type: type[Exception] = SupplementaryModeError,
) -> date:
    """Derive the corpus anchor from authenticated run-input packet rows.

    Delegates to the shared derivation the aggregate uses, so the two cannot
    disagree about the anchor or about which dating states are refused.
    """

    try:
        anchor = corpus_anchor_from_decision_rows(
            (
                (
                    str(row.get("packet_object_key", row.get("case_id", "<unknown>"))),
                    row,
                )
                for row in rows
            ),
            required=True,
        )
    except ResultClassError as exc:
        raise error_type(str(exc)) from exc
    if anchor is None:  # pragma: no cover - required=True never returns None
        raise error_type("corpus anchor could not be derived")
    return anchor


def build_supplementary_binding(
    *,
    official_freeze_bundle_sha256: str,
    official_model_registry_sha256: str,
    official_evaluation_release_anchor: str,
    corpus_anchor: date,
    supplementary_model_registry_sha256: str,
    supplementary_model_keys: Sequence[str],
) -> dict[str, Any]:
    """Record both bindings explicitly rather than leaving either inferable."""

    return {
        "execution_mode": SUPPLEMENTARY_MODE,
        "official_freeze_bundle_sha256": official_freeze_bundle_sha256,
        "official_model_registry_sha256": official_model_registry_sha256,
        "official_evaluation_release_anchor": official_evaluation_release_anchor,
        "corpus_anchor": corpus_anchor.isoformat(),
        "supplementary_model_registry_sha256": supplementary_model_registry_sha256,
        "supplementary_model_keys": sorted(supplementary_model_keys),
    }


def require_binding_shape(
    value: object,
    *,
    label: str,
    error_type: type[Exception] = SupplementaryModeError,
) -> Mapping[str, Any]:
    """Validate a recorded supplementary binding without its source bytes."""

    if not isinstance(value, Mapping):
        raise error_type(f"{label} must be an object")
    record = cast(Mapping[str, Any], value)
    missing = sorted(SUPPLEMENTARY_BINDING_FIELDS - set(record))
    unknown = sorted(set(record) - SUPPLEMENTARY_BINDING_FIELDS)
    if missing or unknown:
        raise error_type(
            f"{label} fields mismatch: missing={missing}, unknown={unknown}"
        )
    if record.get("execution_mode") != SUPPLEMENTARY_MODE:
        raise error_type(f"{label}.execution_mode must be {SUPPLEMENTARY_MODE}")
    for field in (
        "official_freeze_bundle_sha256",
        "official_model_registry_sha256",
        "supplementary_model_registry_sha256",
    ):
        digest = record.get(field)
        if not isinstance(digest, str) or not is_lowercase_sha256(digest):
            raise error_type(f"{label}.{field} must be a lowercase SHA-256 digest")
    if (
        record["official_model_registry_sha256"]
        == record["supplementary_model_registry_sha256"]
    ):
        raise error_type(
            f"{label} must bind a supplementary registry distinct from the official one"
        )
    for field in ("official_evaluation_release_anchor", "corpus_anchor"):
        _require_canonical_iso_date(
            record.get(field), label=f"{label}.{field}", error_type=error_type
        )
    keys = record.get("supplementary_model_keys")
    if (
        not isinstance(keys, list)
        or not keys
        or not all(isinstance(key, str) and ":" in key for key in cast(list[Any], keys))
        or list(cast(list[str], keys)) != sorted(cast(list[str], keys))
    ):
        raise error_type(
            f"{label}.supplementary_model_keys must be a sorted, non-empty list of "
            "provider:model_id keys"
        )
    return record


def _require_canonical_iso_date(
    value: object, *, label: str, error_type: type[Exception]
) -> date:
    """Require the exact canonical ``YYYY-MM-DD`` spelling, not merely parseable.

    ``date.fromisoformat`` also accepts compact and week-date forms on the pinned
    Python, and every comparison against these recorded fields elsewhere is plain
    string equality -- so a non-canonical spelling would compare unequal to the
    same date written canonically.
    """

    if not isinstance(value, str):
        raise error_type(f"{label} must be an ISO date string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise error_type(f"{label} must be an ISO date string") from exc
    if parsed.isoformat() != value:
        raise error_type(f"{label} must use the canonical YYYY-MM-DD spelling")
    return parsed
