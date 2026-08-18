"""A committed input whose capture directory is gone is content-addressed.

The frozen run card's path string can never be rewritten -- the replay re-emits
it and the immutable-output gate demands byte equality -- so the only admissible
repair is a read-time substitution gated on the digest the disclosure-clearance
run card already committed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.cli import (
    CommandError,
    _bytes_sha256,
    _derived_clearance_relocations,
)

# A name of this fixture's own, so the repository's real cohort policy is
# never a candidate and each case exercises exactly the copies it places.
POLICY_NAME = "cohort-policy-derived-relocation-fixture.json"
POLICY_BYTES = b'{"schema_version": "legalforecast.cohort_policy.v1"}\n'


def build_lineage(
    tmp_path: Path, *, frozen_root: Path, committed_sha256: str | None = None
) -> Path:
    """Write a target-cohort run card that names a clearance card, and return it."""

    target_root = tmp_path / "artifacts" / "cycle-1" / "target"
    (target_root / "run-cards").mkdir(parents=True)
    clearance_card_path = tmp_path / "clearance" / "finalize-provenance-quarantine.json"
    clearance_card_path.parent.mkdir(parents=True)
    clearance_card_path.write_text(
        json.dumps(
            {
                "source_commitments": {
                    "cohort_policy": {
                        "path": str(frozen_root / "docs" / POLICY_NAME),
                        "sha256": committed_sha256 or _bytes_sha256(POLICY_BYTES),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (target_root / "run-cards" / "project-target-cohort.json").write_text(
        json.dumps(
            {
                "input_paths": [f"/input/{index}" for index in range(7)]
                + [str(clearance_card_path)]
            }
        ),
        encoding="utf-8",
    )
    return target_root


def place_stable_copy(tmp_path: Path, payload: bytes) -> Path:
    """Put a durable copy at the same position under an ancestor of the target."""

    stable_root = tmp_path / "artifacts"
    (stable_root / "docs").mkdir(parents=True, exist_ok=True)
    (stable_root / "docs" / POLICY_NAME).write_bytes(payload)
    return stable_root


def test_a_dead_capture_path_binds_the_digest_matching_durable_copy(
    tmp_path: Path,
) -> None:
    frozen_root = tmp_path / "ephemeral-capture-root"
    target_root = build_lineage(tmp_path, frozen_root=frozen_root)
    stable_root = place_stable_copy(tmp_path, POLICY_BYTES)

    relocations, source_roots = _derived_clearance_relocations(target_root)

    assert relocations is not None and source_roots is not None
    frozen_path = str(frozen_root / "docs" / POLICY_NAME)
    stable_path, payload = relocations[frozen_path]
    assert stable_path == stable_root / "docs" / POLICY_NAME
    assert payload == POLICY_BYTES
    assert source_roots == {str(frozen_root): stable_root}


def test_a_durable_copy_that_fails_the_committed_digest_is_refused(
    tmp_path: Path,
) -> None:
    frozen_root = tmp_path / "ephemeral-capture-root"
    target_root = build_lineage(tmp_path, frozen_root=frozen_root)
    place_stable_copy(tmp_path, POLICY_BYTES + b"tampered\n")

    with pytest.raises(CommandError, match="matches the digest"):
        _derived_clearance_relocations(target_root)


def test_a_live_committed_path_is_never_relocated(tmp_path: Path) -> None:
    """Relocation is a dead-path repair, not a general path override."""

    frozen_root = tmp_path / "live-capture-root"
    (frozen_root / "docs").mkdir(parents=True)
    (frozen_root / "docs" / POLICY_NAME).write_bytes(POLICY_BYTES)
    target_root = build_lineage(tmp_path, frozen_root=frozen_root)
    place_stable_copy(tmp_path, POLICY_BYTES)

    assert _derived_clearance_relocations(target_root) == (None, None)


def test_no_durable_copy_yields_no_relocation(tmp_path: Path) -> None:
    """Nothing is accepted on the strength of its location alone."""

    frozen_root = tmp_path / "ephemeral-capture-root"
    target_root = build_lineage(tmp_path, frozen_root=frozen_root)

    assert _derived_clearance_relocations(target_root) == (None, None)


def test_a_missing_run_card_yields_no_relocation(tmp_path: Path) -> None:
    assert _derived_clearance_relocations(tmp_path / "absent") == (None, None)
