"""Committed Stage A provider inputs whose capture root is gone are content-addressed.

The frozen llm-unitize run card's path string can never be rewritten: the lineage
re-emits it and ``verify_stage_a_unitization_run_card`` compares the rebuilt
``input_commitments`` against the frozen ones as whole records, path included. So
the only admissible repair is a read-time substitution gated on the digest the run
card already committed, leaving the frozen path as the emitted identity.

Same shape as ``tests/test_derived_clearance_relocations.py``, one layer down: that
one relocates a cohort policy for the projection verifier, this one relocates the
model registry and provider cycle caps for the Stage A unitization verifier.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.cli import CommandError, _bytes_sha256
from legalforecast.ingestion.stage_a_lineage_verification import (
    _relocated_read_path,
    relocated_stage_a_committed_inputs,
)

# Names of this fixture's own, so the repository's real model_registries/ files are
# never candidates and each case exercises exactly the copies it places.
REGISTRY_NAME = "cycle-1-labeling-relocation-fixture.json"
CAPS_NAME = "cycle-1-provider-caps-base-relocation-fixture.json"
REGISTRY_BYTES = b'{"schema_version": "legalforecast.model_registry.v1"}\n'
CAPS_BYTES = b'{"schema_version": "legalforecast.provider_cycle_caps.v1"}\n'

NAMES = ("model_registry", "provider_cycle_caps")


def commitments(
    frozen_root: Path,
    *,
    registry_sha256: str | None = None,
    caps_sha256: str | None = None,
) -> dict[str, object]:
    """Build the two input commitments an llm-unitize run card freezes."""

    return {
        "model_registry": {
            "path": str(frozen_root / "model_registries" / REGISTRY_NAME),
            "sha256": registry_sha256 or _bytes_sha256(REGISTRY_BYTES),
        },
        "provider_cycle_caps": {
            "path": str(frozen_root / "model_registries" / CAPS_NAME),
            "sha256": caps_sha256 or _bytes_sha256(CAPS_BYTES),
        },
    }


def place_stable_copies(
    tmp_path: Path,
    *,
    registry_payload: bytes = REGISTRY_BYTES,
    caps_payload: bytes = CAPS_BYTES,
) -> Path:
    """Put durable copies at the identical position under an ancestor of the card."""

    stable_root = tmp_path / "artifacts"
    (stable_root / "model_registries").mkdir(parents=True, exist_ok=True)
    (stable_root / "model_registries" / REGISTRY_NAME).write_bytes(registry_payload)
    (stable_root / "model_registries" / CAPS_NAME).write_bytes(caps_payload)
    return stable_root


def search_root(tmp_path: Path) -> Path:
    """The run-card path the production caller passes as the search root."""

    card = tmp_path / "artifacts" / "unitize" / "run-cards" / "llm-unitize.json"
    card.parent.mkdir(parents=True, exist_ok=True)
    return card


def test_dead_capture_paths_bind_the_digest_matching_durable_copies(
    tmp_path: Path,
) -> None:
    frozen_root = tmp_path / "ephemeral-capture-root"
    stable_root = place_stable_copies(tmp_path)

    relocations = relocated_stage_a_committed_inputs(
        commitments(frozen_root), NAMES, search_root=search_root(tmp_path)
    )

    frozen_registry = str(frozen_root / "model_registries" / REGISTRY_NAME)
    frozen_caps = str(frozen_root / "model_registries" / CAPS_NAME)
    assert set(relocations) == {frozen_registry, frozen_caps}

    registry_path, registry_payload = relocations[frozen_registry]
    assert registry_path == stable_root / "model_registries" / REGISTRY_NAME
    assert registry_payload == REGISTRY_BYTES

    caps_path, caps_payload = relocations[frozen_caps]
    assert caps_path == stable_root / "model_registries" / CAPS_NAME
    assert caps_payload == CAPS_BYTES


def test_a_durable_copy_that_fails_the_committed_digest_is_refused(
    tmp_path: Path,
) -> None:
    """Wrong bytes at the committed position refuse loudly, never skip to a pass."""

    frozen_root = tmp_path / "ephemeral-capture-root"
    place_stable_copies(tmp_path, registry_payload=REGISTRY_BYTES + b"tampered\n")

    with pytest.raises(CommandError, match="matches the digest"):
        relocated_stage_a_committed_inputs(
            commitments(frozen_root), NAMES, search_root=search_root(tmp_path)
        )


def test_a_tampered_caps_copy_is_refused(tmp_path: Path) -> None:
    """Both relocated inputs are digest-gated, not just the first one."""

    frozen_root = tmp_path / "ephemeral-capture-root"
    place_stable_copies(tmp_path, caps_payload=CAPS_BYTES + b"tampered\n")

    with pytest.raises(CommandError, match="matches the digest"):
        relocated_stage_a_committed_inputs(
            commitments(frozen_root), NAMES, search_root=search_root(tmp_path)
        )


def test_a_live_committed_path_is_never_relocated(tmp_path: Path) -> None:
    """Relocation is a dead-path repair, not a general path override.

    A live original must keep answering for itself even when a durable copy with
    identical bytes sits at the same relative position under a candidate root.
    """

    frozen_root = tmp_path / "live-capture-root"
    (frozen_root / "model_registries").mkdir(parents=True)
    (frozen_root / "model_registries" / REGISTRY_NAME).write_bytes(REGISTRY_BYTES)
    (frozen_root / "model_registries" / CAPS_NAME).write_bytes(CAPS_BYTES)
    place_stable_copies(tmp_path)

    assert (
        relocated_stage_a_committed_inputs(
            commitments(frozen_root), NAMES, search_root=search_root(tmp_path)
        )
        == {}
    )


def test_only_the_dead_pin_relocates_when_one_input_is_still_live(
    tmp_path: Path,
) -> None:
    frozen_root = tmp_path / "half-live-capture-root"
    (frozen_root / "model_registries").mkdir(parents=True)
    (frozen_root / "model_registries" / CAPS_NAME).write_bytes(CAPS_BYTES)
    place_stable_copies(tmp_path)

    relocations = relocated_stage_a_committed_inputs(
        commitments(frozen_root), NAMES, search_root=search_root(tmp_path)
    )

    assert set(relocations) == {str(frozen_root / "model_registries" / REGISTRY_NAME)}


def test_no_durable_copy_yields_no_relocation(tmp_path: Path) -> None:
    """Nothing is accepted on the strength of its location alone."""

    frozen_root = tmp_path / "ephemeral-capture-root"

    assert (
        relocated_stage_a_committed_inputs(
            commitments(frozen_root), NAMES, search_root=search_root(tmp_path)
        )
        == {}
    )


def test_absent_or_malformed_commitments_yield_no_relocation(tmp_path: Path) -> None:
    frozen_root = tmp_path / "ephemeral-capture-root"
    place_stable_copies(tmp_path)
    malformed: dict[str, object] = {
        "model_registry": "not-a-mapping",
        "provider_cycle_caps": {"path": 17, "sha256": None},
    }

    assert (
        relocated_stage_a_committed_inputs(
            malformed, NAMES, search_root=search_root(tmp_path)
        )
        == {}
    )
    assert (
        relocated_stage_a_committed_inputs({}, NAMES, search_root=search_root(tmp_path))
        == {}
    )
    assert (
        relocated_stage_a_committed_inputs(
            commitments(frozen_root), (), search_root=search_root(tmp_path)
        )
        == {}
    )


def test_a_symlinked_stand_in_is_not_accepted(tmp_path: Path) -> None:
    """A relocation must land on a real regular file, not a link to one."""

    frozen_root = tmp_path / "ephemeral-capture-root"
    stable_root = tmp_path / "artifacts"
    (stable_root / "model_registries").mkdir(parents=True)
    real = tmp_path / "elsewhere.json"
    real.write_bytes(REGISTRY_BYTES)
    (stable_root / "model_registries" / REGISTRY_NAME).symlink_to(real)
    (stable_root / "model_registries" / CAPS_NAME).write_bytes(CAPS_BYTES)

    relocations = relocated_stage_a_committed_inputs(
        commitments(frozen_root), NAMES, search_root=search_root(tmp_path)
    )

    assert str(frozen_root / "model_registries" / REGISTRY_NAME) not in relocations


def test_relocated_read_path_redirects_only_relocated_inputs(tmp_path: Path) -> None:
    """The frozen path stays the identity; only the read is redirected."""

    frozen = tmp_path / "ephemeral" / "model_registries" / REGISTRY_NAME
    durable = tmp_path / "durable" / "model_registries" / REGISTRY_NAME
    untouched = tmp_path / "ephemeral" / "model_registries" / CAPS_NAME

    relocations = {str(frozen): (durable, REGISTRY_BYTES)}

    assert _relocated_read_path(frozen, relocations) == durable
    assert _relocated_read_path(untouched, relocations) == untouched
    assert _relocated_read_path(frozen, {}) == frozen
