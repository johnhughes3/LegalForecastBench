"""Explicit supplementary (post-anchor) mode for the pre-dispatch chain.

PR #1003 inverted the release-anchor gate from the provider cell forward.  This
module is the same inversion one stage earlier, for the authorization chain that
runs *before* dispatch: cost projection, execution-scope issuance, and immutable
staging.  Nothing here is a waiver.  Every check either stays exactly as it is in
official mode or is replaced by its mirror image, so both modes fail closed.

The comparability property the supplementary lane rests on is that a post-anchor
model runs against byte-identical corpus and prompt bytes.  That property is
*verified* here rather than assumed: a sibling freeze must agree with the
official freeze on every frozen artifact except the three the lane exists to
replace -- the model registry, its provider caps, and its execution policy -- and
must disagree on the registry.  A supplementary artifact therefore records both
bindings explicitly: which official contract it reuses, and which registry it
evaluates.

Mode is carried as a plain ``supplementary: bool`` (the convention PR #1003 set
on ``PerCaseRunnerConfig``, ``ForecastBuildRequest``, ``FanInConfig`` and
``OfficialAggregationConfig``), and never as a claim about a model: which class a
model belongs to is always derived from its frozen ``release_timestamp`` against
a corpus-derived anchor.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.evals.model_registry import ModelRegistryEntry
from legalforecast.protocol.freeze import (
    REQUIRED_FREEZE_ARTIFACTS,
    FreezeBundle,
    FreezeProtocolError,
    FrozenArtifactName,
    load_freeze_bundle,
)
from legalforecast.reporting.result_class import (
    ResultClass,
    corpus_anchor_from_decision_dates,
    expected_result_class,
    supplementary_model_ids,
)

SUPPLEMENTARY_MODE: Final = ResultClass.SUPPLEMENTARY_POST_ANCHOR.value
OFFICIAL_MODE: Final = ResultClass.OFFICIAL.value

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


def execution_mode(*, supplementary: bool) -> str:
    """Return the mode name one execution declares."""

    return expected_result_class(supplementary=supplementary).value


def load_reference_freeze_bundle(
    path: Path,
    *,
    cycle_id: str,
    error_type: type[Exception] = SupplementaryModeError,
) -> FreezeBundle:
    """Load an official freeze bundle used purely as a reference commitment.

    Only the bundle's own recorded artifact digests are read, so the official
    artifact *bytes* are not required to be present.  That is what keeps the
    identity check cheap enough to run inside a provider cell's preflight: one
    small JSON file, not a second copy of the corpus.
    """

    try:
        bundle = load_freeze_bundle(path)
    except (FreezeProtocolError, OSError, ValueError) as exc:
        raise error_type(f"official freeze bundle is not valid: {exc}") from exc
    if bundle.cycle_id != cycle_id:
        raise error_type(
            "official freeze bundle cycle_id does not match dispatch input"
        )
    missing = sorted(
        name.value
        for name in REQUIRED_FREEZE_ARTIFACTS
        if name not in {artifact.name for artifact in bundle.artifacts}
    )
    if missing:
        raise error_type(f"official freeze bundle is missing artifacts: {missing}")
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
    """Refuse a supplementary registry whose models classify official.

    This mirrors ``official_aggregate._require_result_class_separation`` so the
    pre-dispatch chain and the aggregate cannot disagree about which set a model
    belongs to.  A caller chooses which lane it is dispatching; it does not get
    to choose how a model classifies.
    """

    if not entries:
        raise error_type("supplementary mode requires a model registry to classify")
    supplementary = set(supplementary_model_ids(entries, corpus_anchor=corpus_anchor))
    official = sorted(
        entry.registry_key
        for entry in entries
        if entry.registry_key not in supplementary
    )
    if official:
        raise error_type(
            "supplementary mode refuses models released on or before the corpus "
            f"anchor {corpus_anchor.isoformat()}: {official}"
        )


def corpus_anchor_from_packet_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    error_type: type[Exception] = SupplementaryModeError,
) -> date:
    """Derive the corpus anchor from authenticated run-input packet rows.

    Deriving it from the corpus rather than from the registry under evaluation is
    what makes the classification non-vacuous: a registry containing only
    post-anchor models would otherwise supply its own anchor and certify itself.
    Partial dating is refused rather than tolerated, because an anchor taken from
    the dated rows alone can only be later than the true earliest decision, and a
    later anchor can only under-report supplementary models.
    """

    dates: list[date] = []
    undated: list[str] = []
    for row in rows:
        raw = row.get("decision_date")
        label = str(row.get("packet_object_key", row.get("case_id", "<unknown>")))
        if raw is None:
            undated.append(label)
            continue
        if not isinstance(raw, str) or not raw.strip():
            raise error_type("run-input decision_date must be an ISO date string")
        try:
            dates.append(date.fromisoformat(raw))
        except ValueError as exc:
            raise error_type(
                f"run-input decision_date is not an ISO date: {raw}"
            ) from exc
    if undated and dates:
        raise error_type(
            "run-input rows disagree on decision_date presence; the corpus anchor "
            f"cannot be derived from a partial set: {sorted(undated)}"
        )
    if not dates:
        raise error_type(
            "supplementary mode requires run-input decision dates to derive the "
            "corpus anchor"
        )
    return corpus_anchor_from_decision_dates(dates)


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
        if not isinstance(digest, str) or not _is_sha256(digest):
            raise error_type(f"{label}.{field} must be a lowercase SHA-256 digest")
    if (
        record["official_model_registry_sha256"]
        == record["supplementary_model_registry_sha256"]
    ):
        raise error_type(
            f"{label} must bind a supplementary registry distinct from the official one"
        )
    for field in ("official_evaluation_release_anchor", "corpus_anchor"):
        raw = record.get(field)
        if not isinstance(raw, str):
            raise error_type(f"{label}.{field} must be an ISO date string")
        try:
            date.fromisoformat(raw)
        except ValueError as exc:
            raise error_type(f"{label}.{field} must be an ISO date string") from exc
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


def require_mode_match(
    record: Mapping[str, Any],
    *,
    field: str,
    supplementary: bool,
    label: str,
    error_type: type[Exception] = SupplementaryModeError,
) -> Mapping[str, Any] | None:
    """Require a recorded mode to be exactly the mode the caller is executing.

    An official artifact never carries the binding block, so its bytes are
    unchanged by this lane; presence of the block *is* the supplementary
    declaration.  Refusing in both directions is what stops a supplementary scope
    from authorizing an official shard, and an official scope from authorizing a
    supplementary one.
    """

    present = field in record
    if supplementary and not present:
        raise error_type(
            f"{label} was issued in official mode and cannot authorize a "
            "supplementary execution"
        )
    if not supplementary and present:
        raise error_type(
            f"{label} was issued in supplementary mode and cannot authorize an "
            "official execution"
        )
    if not present:
        return None
    return require_binding_shape(
        record[field], label=f"{label}.{field}", error_type=error_type
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
