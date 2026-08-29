"""Decide which manifest-run prefix a candidate freeze may occupy.

Kept beside the staging module rather than inside it so one stays about moving
authenticated bytes into S3 and this one stays about the rule that decides
where they may go.  The rule is the load-bearing half: manifest-run objects are
written create-once and neither OIDC role has a delete grant, so a freeze staged
at the wrong prefix is unrecoverable.

The authority is the caller-pinned official freeze bundle, never the
operator-chosen ``--output-dir``: a run record the operator selected cannot
decide whether the freeze beside it is the official one.

The evals stack is reached through entry points, never imports.  The staging
module is loaded when the CLI builds its parser, and a static import would grow
the CLI package's import graph a dependency on the verifier stack -- the
invariant ``legalforecast/cli_commands/corpus_manifest.py`` states for exactly
this reason.
"""

from __future__ import annotations

import importlib.metadata
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from legalforecast.protocol.freeze import FreezeBundle, FrozenArtifactName

if TYPE_CHECKING:
    from legalforecast.publication.manifest_forecast_stage import (
        ManifestForecastStageConfig,
    )

MANIFEST_FORECAST_PREFIX = "cycle-1/manifest-runs"


class ManifestForecastStageError(ValueError):
    """Raised when a manifest forecast cannot be staged safely."""


# The evals stack is reached through entry points, never imports: this module is
# loaded when the CLI builds its parser, and a static import would grow the CLI
# package's import graph a dependency on the verifier stack -- the invariant
# legalforecast/cli_commands/corpus_manifest.py states for exactly this reason.


class _CommittedRegistryKeys(Protocol):
    def __call__(self, committed: Sequence[Any]) -> tuple[str, ...]: ...


class _LoadModelRegistry(Protocol):
    def __call__(self, path: str | Path) -> Any: ...


class _LoadPinnedReferenceFreeze(Protocol):
    def __call__(
        self,
        payload: bytes,
        *,
        cycle_id: str,
        expected_sha256: str,
        error_type: type[Exception],
    ) -> FreezeBundle: ...


class _RequireSiblingIdentity(Protocol):
    def __call__(
        self,
        *,
        sibling: FreezeBundle,
        official: FreezeBundle,
        error_type: type[Exception],
    ) -> None: ...


class _CorpusAnchorFromPacketRows(Protocol):
    def __call__(
        self, rows: Sequence[Mapping[str, Any]], *, error_type: type[Exception]
    ) -> date: ...


class _BuildSupplementaryBinding(Protocol):
    def __call__(
        self,
        *,
        official_freeze_bundle_sha256: str,
        official_model_registry_sha256: str,
        official_evaluation_release_anchor: str,
        corpus_anchor: date,
        supplementary_model_registry_sha256: str,
        supplementary_model_keys: Sequence[str],
    ) -> dict[str, Any]: ...


class _RequireBindingShape(Protocol):
    def __call__(
        self, value: object, *, label: str, error_type: type[Exception]
    ) -> Mapping[str, Any]: ...


def _entry_point(name: str, value: str) -> importlib.metadata.EntryPoint:
    return importlib.metadata.EntryPoint(
        name=name, value=value, group="legalforecast.internal"
    )


_RECORDS = "legalforecast.evals.corpus_manifest.records"
_SUPPLEMENTARY = "legalforecast.evals.corpus_manifest.supplementary_mode"
_COMMITTED_REGISTRY_KEYS = _entry_point(
    "manifest-stage-committed-registry-keys", f"{_RECORDS}:committed_registry_keys"
)
_LOAD_MODEL_REGISTRY = _entry_point(
    "manifest-stage-load-model-registry",
    "legalforecast.evals.model_registry:load_model_registry",
)
_LOAD_PINNED_OFFICIAL_FREEZE = _entry_point(
    "manifest-stage-load-pinned-official-freeze",
    f"{_SUPPLEMENTARY}:load_pinned_reference_freeze_bundle",
)
_REQUIRE_SIBLING_IDENTITY = _entry_point(
    "manifest-stage-require-sibling-identity",
    f"{_SUPPLEMENTARY}:require_sibling_freeze_identity",
)
_CORPUS_ANCHOR = _entry_point(
    "manifest-stage-corpus-anchor", f"{_SUPPLEMENTARY}:corpus_anchor_from_packet_rows"
)
_BUILD_BINDING = _entry_point(
    "manifest-stage-build-binding", f"{_SUPPLEMENTARY}:build_supplementary_binding"
)
_REQUIRE_BINDING_SHAPE = _entry_point(
    "manifest-stage-require-binding-shape", f"{_SUPPLEMENTARY}:require_binding_shape"
)


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestForecastStageError(f"{label} is unreadable: {path}") from exc
    if not isinstance(raw, Mapping):
        raise ManifestForecastStageError(f"{label} must be a JSON object: {path}")
    return dict(cast(Mapping[str, Any], raw))


@dataclass(frozen=True, slots=True)
class _StageLane:
    """The lane a candidate freeze was classified into, and its binding."""

    model_keys: tuple[str, ...]
    binding: Mapping[str, Any] | None


def classify_stage_lane(
    *,
    bundle: FreezeBundle,
    source_freeze_digest: str,
    run_inputs: Mapping[str, Any],
    config: ManifestForecastStageConfig,
) -> _StageLane:
    """Decide which prefix a freeze may occupy, from the pinned official freeze.

    The bare ``cycle-1/manifest-runs/<manifest_digest>`` prefix is keyed by the
    corpus alone, so every sibling freeze over one corpus maps to it.  Objects
    are written create-once and no role can delete, so a wrong prefix is
    unrecoverable and the decision has to be made before the first upload.

    The authority is the caller-pinned official freeze, not the operator-chosen
    ``--output-dir``: official mode requires the candidate to *be* that bundle,
    and supplementary mode requires a sibling whose models are disjoint from it.
    Neither refusal recommends the other mode, because following such a
    recommendation is precisely how a sibling would reach the official prefix.
    """

    load_pinned = cast(_LoadPinnedReferenceFreeze, _LOAD_PINNED_OFFICIAL_FREEZE.load())
    try:
        official_bytes = config.official_freeze_bundle.read_bytes()
    except OSError as exc:
        raise ManifestForecastStageError(
            f"official freeze bundle is unreadable: {config.official_freeze_bundle}"
        ) from exc
    official = load_pinned(
        official_bytes,
        cycle_id=bundle.cycle_id,
        expected_sha256=config.official_freeze_bundle_sha256,
        error_type=ManifestForecastStageError,
    )
    official_registry_sha256 = official.artifact(
        FrozenArtifactName.MODEL_REGISTRY
    ).sha256
    candidate_keys, candidate_registry_sha256 = _candidate_registry_identity(bundle)
    prompt_replay = _prompt_replay(bundle)
    committed_keys = cast(_CommittedRegistryKeys, _COMMITTED_REGISTRY_KEYS.load())
    official_keys = committed_keys(
        cast(Sequence[Any], prompt_replay.get("evaluation_models") or ())
    )
    if not official_keys:
        raise ManifestForecastStageError(
            "frozen prompt contract records no evaluation_models, so "
            "stage-manifest-forecast cannot identify the official registry"
        )
    if prompt_replay.get("model_registry_sha256") != official_registry_sha256:
        # Without this the pinned bundle could share the ten identical artifacts
        # yet bind some third registry, and every key comparison below would be
        # made against a registry the shared prompt contract does not commit.
        raise ManifestForecastStageError(
            "official freeze bundle does not bind the registry the frozen prompt "
            "contract commits"
        )
    if set(candidate_keys) == set(official_keys) and (
        candidate_registry_sha256 != official_registry_sha256
    ):
        # Same models, different registry bytes: neither the official freeze nor
        # a post-anchor sibling.  Refused in both modes rather than routed to
        # either prefix, because whichever one it took would be wrong.
        raise ManifestForecastStageError(
            "stage-manifest-forecast refuses a freeze whose model registry names "
            f"the official models ({', '.join(sorted(official_keys))}) with "
            "different bytes: it is neither the official freeze nor a "
            "supplementary sibling, and belongs in no manifest-run prefix"
        )
    if not config.supplementary:
        if source_freeze_digest != config.official_freeze_bundle_sha256:
            raise ManifestForecastStageError(
                "stage-manifest-forecast refuses to stage a freeze that is not "
                "the pinned official freeze bundle into the shared "
                f"{MANIFEST_FORECAST_PREFIX}/<manifest_digest> prefix, which "
                "already backs dispatched official shards and cannot be pruned. "
                f"--freeze-bundle hashes to {source_freeze_digest}; "
                "--official-freeze-bundle-sha256 pins "
                f"{config.official_freeze_bundle_sha256}"
            )
        return _StageLane(model_keys=candidate_keys, binding=None)
    require_sibling = cast(_RequireSiblingIdentity, _REQUIRE_SIBLING_IDENTITY.load())
    require_sibling(
        sibling=bundle, official=official, error_type=ManifestForecastStageError
    )
    shared = sorted(set(candidate_keys) & set(official_keys))
    if shared:
        raise ManifestForecastStageError(
            "supplementary staging requires model keys disjoint from the pinned "
            f"official registry; both bind {', '.join(shared)}"
        )
    return _StageLane(
        model_keys=candidate_keys,
        binding=_supplementary_binding(
            bundle=bundle,
            run_inputs=run_inputs,
            prompt_replay=prompt_replay,
            official_registry_sha256=official_registry_sha256,
            official_freeze_bundle_sha256=config.official_freeze_bundle_sha256,
            candidate_keys=candidate_keys,
            candidate_registry_sha256=candidate_registry_sha256,
        ),
    )


def _supplementary_binding(
    *,
    bundle: FreezeBundle,
    run_inputs: Mapping[str, Any],
    prompt_replay: Mapping[str, Any],
    official_registry_sha256: str,
    official_freeze_bundle_sha256: str,
    candidate_keys: Sequence[str],
    candidate_registry_sha256: str,
) -> Mapping[str, Any]:
    """Record the same binding the dispatch chain records, from one builder."""

    del bundle
    anchor_from_rows = cast(_CorpusAnchorFromPacketRows, _CORPUS_ANCHOR.load())
    build_binding = cast(_BuildSupplementaryBinding, _BUILD_BINDING.load())
    require_shape = cast(_RequireBindingShape, _REQUIRE_BINDING_SHAPE.load())
    raw_rows = run_inputs.get("model_packets")
    rows = [
        cast(Mapping[str, Any], row)
        for row in cast(list[object], raw_rows if isinstance(raw_rows, list) else [])
        if isinstance(row, Mapping)
    ]
    official_anchor = prompt_replay.get("evaluation_release_anchor")
    if not isinstance(official_anchor, str):
        raise ManifestForecastStageError(
            "frozen prompt contract has no evaluation_release_anchor"
        )
    binding = build_binding(
        official_freeze_bundle_sha256=official_freeze_bundle_sha256,
        official_model_registry_sha256=official_registry_sha256,
        official_evaluation_release_anchor=official_anchor,
        corpus_anchor=anchor_from_rows(rows, error_type=ManifestForecastStageError),
        supplementary_model_registry_sha256=candidate_registry_sha256,
        supplementary_model_keys=list(candidate_keys),
    )
    return require_shape(
        binding,
        label="supplementary stage binding",
        error_type=ManifestForecastStageError,
    )


def _candidate_registry_identity(bundle: FreezeBundle) -> tuple[tuple[str, ...], str]:
    """Read the verified freeze's own registry keys and artifact digest."""

    try:
        artifact = bundle.artifact(FrozenArtifactName.MODEL_REGISTRY)
    except KeyError as exc:
        raise ManifestForecastStageError(
            "freeze bundle has no model_registry artifact"
        ) from exc
    load_registry = cast(_LoadModelRegistry, _LOAD_MODEL_REGISTRY.load())
    try:
        registry = load_registry(artifact.path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ManifestForecastStageError(
            f"frozen model registry is not valid: {exc}"
        ) from exc
    return (
        tuple(entry.registry_key for entry in registry.entries),
        artifact.sha256,
    )


def _prompt_replay(bundle: FreezeBundle) -> Mapping[str, Any]:
    """Read the frozen prompt contract's replay block from the verified freeze.

    A sibling freeze reuses the official prompt bytes, so this block names the
    official registry and anchor no matter which lane the candidate is in.
    """

    try:
        artifact = bundle.artifact(FrozenArtifactName.PROMPT)
    except KeyError as exc:
        raise ManifestForecastStageError(
            "freeze bundle has no prompt artifact"
        ) from exc
    prompt = load_json_object(artifact.path, "frozen prompt contract")
    replay = prompt.get("prompt_replay")
    if not isinstance(replay, Mapping):
        raise ManifestForecastStageError(
            "frozen prompt contract is missing prompt_replay"
        )
    return cast(Mapping[str, Any], replay)
