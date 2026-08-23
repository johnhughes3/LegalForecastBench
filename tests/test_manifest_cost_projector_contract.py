from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.evals.corpus_manifest import cost_projector_contract as contract
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FreezeProtocolError,
    FrozenArtifact,
    FrozenArtifactName,
)


def _base_bundle(tmp_path: Path) -> FreezeBundle:
    artifacts = tuple(
        FrozenArtifact(
            name=name,
            path=tmp_path / f"{name.value}.json",
            sha256=hashlib.sha256(name.value.encode()).hexdigest(),
            size_bytes=0,
        )
        for name in FrozenArtifactName
    )
    return FreezeBundle(
        cycle_id="cycle-1",
        freeze_timestamp=datetime(2026, 8, 22, tzinfo=UTC),
        artifacts=artifacts,
    )


def _amended_bundle(parent: FreezeBundle) -> FreezeBundle:
    return FreezeBundle(
        cycle_id=parent.cycle_id,
        freeze_timestamp=parent.freeze_timestamp,
        artifacts=parent.artifacts,
        amends_bundle_sha256=parent.bundle_sha256,
    )


def test_exact_amendment_chain_accepts_every_referenced_ancestor_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _base_bundle(tmp_path)
    parent = _amended_bundle(base)
    current = _amended_bundle(parent)
    paths = (tmp_path / "base.freeze.json", tmp_path / "parent.freeze.json")
    bundles = {paths[0]: base, paths[1]: parent}
    monkeypatch.setattr(
        contract,
        "load_freeze_bundle",
        lambda path, **_kwargs: bundles[Path(path)],
    )

    contract.require_exact_amendment_chain(
        current, amendment_bundles=paths, freeze_root=tmp_path
    )


@pytest.mark.parametrize("failure", ["invalid", "duplicate", "missing", "extra"])
def test_exact_amendment_chain_rejects_nonexact_supplied_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    base = _base_bundle(tmp_path)
    parent = _amended_bundle(base)
    current = _amended_bundle(parent)
    first = tmp_path / "first.freeze.json"
    second = tmp_path / "second.freeze.json"

    if failure == "invalid":
        monkeypatch.setattr(
            contract,
            "load_freeze_bundle",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                FreezeProtocolError("invalid amendment")
            ),
        )
        amendment_paths = (first,)
    elif failure == "duplicate":
        monkeypatch.setattr(
            contract, "load_freeze_bundle", lambda *_args, **_kwargs: parent
        )
        amendment_paths = (first, second)
    elif failure == "missing":
        monkeypatch.setattr(
            contract, "load_freeze_bundle", lambda *_args, **_kwargs: base
        )
        amendment_paths = (first,)
    else:
        monkeypatch.setattr(
            contract, "load_freeze_bundle", lambda *_args, **_kwargs: base
        )
        current = base
        amendment_paths = (first,)

    with pytest.raises(FreezeProtocolError):
        contract.require_exact_amendment_chain(
            current, amendment_bundles=amendment_paths, freeze_root=tmp_path
        )
