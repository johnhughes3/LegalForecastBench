from __future__ import annotations

import copy
import hashlib
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion.firecrawl_screening_identity import (
    COMPATIBLE_4D3BA85_SOURCE_MANIFEST_SHA256,
    COMPATIBLE_4D3BA85_SOURCE_SHA256,
    COMPATIBLE_911371F_FINAL153_SOURCE_MANIFEST_SHA256,
    COMPATIBLE_911371F_FINAL153_SOURCE_SHA256,
    COMPATIBLE_FINAL_V3_SOURCE_MANIFEST_SHA256,
    COMPATIBLE_FINAL_V3_SOURCE_SHA256,
    FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
    FIRECRAWL_SCREENING_SOURCE_PATHS,
    LEGACY_32057DE_SOURCE_MANIFEST_SHA256,
    LEGACY_32057DE_SOURCE_SHA256,
    SCREENING_UNION_POLICY_REBIND_IMPLEMENTATION_SCHEMA,
    SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS,
    FirecrawlScreeningIdentityError,
    firecrawl_screening_implementation,
    require_snapshot_firecrawl_screening_implementation,
    snapshot_firecrawl_screening_source_count,
    source_manifest_sha256,
    validate_firecrawl_screening_implementation,
    validate_screening_union_policy_rebind_implementation,
)

_FINAL153_REBIND_SOURCE_SHA256 = {
    "legalforecast/cli.py": (
        "ff12809a8543f1e5d103f1f35abd49063fa5845ee10d05f790019fc977485f66"
    ),
    "legalforecast/ingestion/cycle_acquisition_store.py": (
        "b41449acd68002b892f69faeced636a893ad9a643ba8f94bdcebc4cecbed928f"
    ),
    "legalforecast/ingestion/firecrawl_screening_identity.py": (
        "153e6510b286782ded9ea17bc84507012c0aeb05e0015a8a06c329043c8bbadb"
    ),
    "legalforecast/ingestion/restricted_material.py": (
        "e74b77e817675b58a18a7f4afbdff785ea5669564ccf95f9246023347dc1fbe2"
    ),
    "legalforecast/ingestion/screening_snapshot_union.py": (
        "f9f31c3be0ad11c238777af1cc9a25ba4e0dcb9b305a6874f41e874cb9c1a653"
    ),
    "legalforecast/ingestion/screening_union_policy_rebind.py": (
        "957685400417ed3a3ff0ef95939c72985d0d2281eab95cf48fb79c1b28ffc408"
    ),
    "legalforecast/ingestion/strict_screen_evidence.py": (
        "f12ced3a1b92e5090ce00879ae626d05839a687f6ac4e8c3bbb54839586cc977"
    ),
}
_FINAL153_REBIND_MANIFEST_SHA256 = (
    "8bb54b4ef12e90156725a8ec5e9162acb405ad0b637d8fc46d57ec4f2c83d1f1"
)


def test_historical_compatibility_set_has_frozen_digest() -> None:
    assert set(FIRECRAWL_SCREENING_SOURCE_PATHS) - set(
        LEGACY_32057DE_SOURCE_SHA256
    ) == {
        "legalforecast/ingestion/strict_screen_evidence.py",
        "legalforecast/ingestion/screening_snapshot_union.py",
        "legalforecast/ingestion/firecrawl_screening_identity.py",
    }
    assert (
        source_manifest_sha256(LEGACY_32057DE_SOURCE_SHA256)
        == LEGACY_32057DE_SOURCE_MANIFEST_SHA256
        == "3e1628b1bbeb3d2af682baaa12815a4c631a64a0ca95eadf2d70e9fa9da419c9"
    )


def test_immediately_previous_screening_identity_remains_exactly_compatible() -> None:
    assert set(COMPATIBLE_4D3BA85_SOURCE_SHA256) == set(
        FIRECRAWL_SCREENING_SOURCE_PATHS
    )
    assert (
        source_manifest_sha256(COMPATIBLE_4D3BA85_SOURCE_SHA256)
        == COMPATIBLE_4D3BA85_SOURCE_MANIFEST_SHA256
        == "913e76a76c3d0cd69640e1034bec8c13557cdb03dc5d77f35c5ab82c7e8448c5"
    )
    commitment = {
        "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
        "source_sha256": dict(COMPATIBLE_4D3BA85_SOURCE_SHA256),
        "manifest_sha256": COMPATIBLE_4D3BA85_SOURCE_MANIFEST_SHA256,
    }

    assert (
        validate_firecrawl_screening_implementation(
            commitment,
            require_current=True,
        )
        == commitment
    )


def test_final_v3_screening_identity_remains_exactly_compatible() -> None:
    assert set(COMPATIBLE_FINAL_V3_SOURCE_SHA256) == set(
        FIRECRAWL_SCREENING_SOURCE_PATHS
    )
    assert (
        source_manifest_sha256(COMPATIBLE_FINAL_V3_SOURCE_SHA256)
        == COMPATIBLE_FINAL_V3_SOURCE_MANIFEST_SHA256
        == "9e076e7f488f60e7f8308af4f27db7f38b9418383c53ccd1e9d652c6236a955c"
    )
    commitment = {
        "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
        "source_sha256": dict(COMPATIBLE_FINAL_V3_SOURCE_SHA256),
        "manifest_sha256": COMPATIBLE_FINAL_V3_SOURCE_MANIFEST_SHA256,
    }

    assert (
        validate_firecrawl_screening_implementation(
            commitment,
            require_current=True,
        )
        == commitment
    )


def test_final153_screening_identity_remains_exactly_compatible() -> None:
    assert set(COMPATIBLE_911371F_FINAL153_SOURCE_SHA256) == set(
        FIRECRAWL_SCREENING_SOURCE_PATHS
    )
    assert (
        source_manifest_sha256(COMPATIBLE_911371F_FINAL153_SOURCE_SHA256)
        == COMPATIBLE_911371F_FINAL153_SOURCE_MANIFEST_SHA256
        == "f651ba73ebb0162f292be8b2d18adfd5397037c18ce93704bd67003a2e63be11"
    )
    commitment = {
        "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
        "source_sha256": dict(COMPATIBLE_911371F_FINAL153_SOURCE_SHA256),
        "manifest_sha256": (COMPATIBLE_911371F_FINAL153_SOURCE_MANIFEST_SHA256),
    }

    assert (
        validate_firecrawl_screening_implementation(
            commitment,
            require_current=True,
        )
        == commitment
    )


def test_current_commitment_has_exact_twenty_one_file_key_set() -> None:
    commitment = firecrawl_screening_implementation()

    assert commitment["schema_version"] == (FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA)
    assert tuple(_sources(commitment)) == FIRECRAWL_SCREENING_SOURCE_PATHS
    assert len(_sources(commitment)) == 21
    assert (
        validate_firecrawl_screening_implementation(
            commitment,
            require_current=True,
        )
        == commitment
    )


def test_final153_policy_rebind_identity_remains_exactly_compatible() -> None:
    commitment = _final153_rebind_commitment()

    assert tuple(_FINAL153_REBIND_SOURCE_SHA256) == (
        SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS
    )
    assert _policy_rebind_manifest_sha256(_FINAL153_REBIND_SOURCE_SHA256) == (
        _FINAL153_REBIND_MANIFEST_SHA256
    )
    assert (
        validate_screening_union_policy_rebind_implementation(
            commitment,
            require_current=True,
        )
        == commitment
    )


def test_unknown_policy_rebind_identity_still_fails_current_validation() -> None:
    commitment = _final153_rebind_commitment()
    sources = cast(dict[str, str], commitment["source_sha256"])
    sources[SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS[0]] = "0" * 64
    commitment["manifest_sha256"] = _policy_rebind_manifest_sha256(sources)

    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="policy-rebind sources do not match current code",
    ):
        validate_screening_union_policy_rebind_implementation(
            commitment,
            require_current=True,
        )


def test_final153_policy_rebind_is_admitted_through_snapshot_validation() -> None:
    implementation = firecrawl_screening_implementation()
    manifest = _union_manifest(
        (
            {"courtlistener_rest_screen_inputs": {}},
            {
                "firecrawl_screen_inputs": {},
                "firecrawl_screening_implementation": implementation,
            },
        ),
        firecrawl_source_count=1,
        implementation=implementation,
    )
    stage_commitments = cast(dict[str, object], manifest["stage_commitments"])
    stage_commitments["screening_union_policy_rebind"] = {
        "implementation": _final153_rebind_commitment()
    }

    assert (
        snapshot_firecrawl_screening_source_count(
            manifest,
            require_current=True,
        )
        == 1
    )


@pytest.mark.parametrize("relative_path", FIRECRAWL_SCREENING_SOURCE_PATHS)
def test_one_byte_drift_in_every_source_changes_commitment(
    tmp_path: Path,
    relative_path: str,
) -> None:
    source_root = Path(__file__).resolve().parents[2]
    for source in FIRECRAWL_SCREENING_SOURCE_PATHS:
        destination = tmp_path / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / source, destination)
    baseline = firecrawl_screening_implementation(source_root=tmp_path)
    changed = tmp_path / relative_path
    changed.write_bytes(changed.read_bytes() + b"\x00")

    drifted = firecrawl_screening_implementation(source_root=tmp_path)

    assert drifted["manifest_sha256"] != baseline["manifest_sha256"]
    assert _sources(drifted)[relative_path] != _sources(baseline)[relative_path]


@pytest.mark.parametrize("mutation", ("missing", "extra"))
def test_source_key_set_drift_fails_closed(mutation: str) -> None:
    commitment = firecrawl_screening_implementation()
    sources = dict(_sources(commitment))
    if mutation == "missing":
        sources.pop(FIRECRAWL_SCREENING_SOURCE_PATHS[0])
    elif mutation == "extra":
        sources["legalforecast/ingestion/not-load-bearing.py"] = "0" * 64
    commitment["source_sha256"] = sources
    commitment["manifest_sha256"] = source_manifest_sha256(sources)

    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="source key set changed",
    ):
        validate_firecrawl_screening_implementation(
            commitment,
            require_current=False,
        )


def test_manifest_tamper_fails_closed() -> None:
    commitment = firecrawl_screening_implementation()
    commitment["manifest_sha256"] = "0" * 64

    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="manifest commitment mismatch",
    ):
        validate_firecrawl_screening_implementation(
            commitment,
            require_current=False,
        )


def test_snapshot_without_implementation_commitment_fails_closed() -> None:
    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="lacks firecrawl_screening_implementation",
    ):
        require_snapshot_firecrawl_screening_implementation(
            {"stage_commitments": {"firecrawl_screen_inputs": {}}},
            require_current=True,
        )


def test_snapshot_source_drift_fails_current_validation() -> None:
    commitment = firecrawl_screening_implementation()
    historical = copy.deepcopy(commitment)
    sources = _sources(historical)
    first = FIRECRAWL_SCREENING_SOURCE_PATHS[0]
    sources[first] = "0" * 64
    historical["manifest_sha256"] = source_manifest_sha256(sources)

    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="do not match the committed implementation",
    ):
        require_snapshot_firecrawl_screening_implementation(
            {"stage_commitments": {"firecrawl_screening_implementation": historical}},
            require_current=True,
        )


def test_direct_rest_snapshot_has_zero_firecrawl_sources() -> None:
    assert (
        snapshot_firecrawl_screening_source_count(
            {"stage_commitments": {"courtlistener_rest_screen_inputs": {}}},
            require_current=True,
        )
        == 0
    )


def test_named_rest_rebind_snapshot_has_zero_firecrawl_sources() -> None:
    assert (
        snapshot_firecrawl_screening_source_count(
            {
                "stage_commitments": {
                    "stage": "rebind-terminal-rest-observations",
                    "source_snapshot_manifest_sha256": "a" * 64,
                }
            },
            require_current=True,
        )
        == 0
    )


@pytest.mark.parametrize(
    "manifest",
    (
        {},
        {"stage_commitments": None},
        {"stage_commitments": {}},
    ),
)
def test_snapshot_without_affirmative_stage_commitments_fails_closed(
    manifest: Mapping[str, object],
) -> None:
    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="lacks affirmative stage commitments",
    ):
        snapshot_firecrawl_screening_source_count(
            manifest,
            require_current=True,
        )


def test_unrecognized_source_neutral_stage_fails_closed() -> None:
    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="lacks recognized source-neutral lineage",
    ):
        snapshot_firecrawl_screening_source_count(
            {"stage_commitments": {"unrecognized_stage": {}}},
            require_current=True,
        )


def test_null_union_commitment_fails_closed() -> None:
    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="union commitment must be an object",
    ):
        snapshot_firecrawl_screening_source_count(
            {"stage_commitments": {"screening_snapshot_union_inputs": None}},
            require_current=True,
        )


def test_direct_firecrawl_snapshot_requires_current_implementation() -> None:
    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="lacks firecrawl_screening_implementation",
    ):
        snapshot_firecrawl_screening_source_count(
            {"stage_commitments": {"firecrawl_screen_inputs": {}}},
            require_current=True,
        )

    implementation = firecrawl_screening_implementation()
    assert (
        snapshot_firecrawl_screening_source_count(
            {
                "stage_commitments": {
                    "firecrawl_screen_inputs": {},
                    "firecrawl_screening_implementation": implementation,
                }
            },
            require_current=True,
        )
        == 1
    )


def test_identity_aware_union_recomputes_firecrawl_source_count() -> None:
    implementation = firecrawl_screening_implementation()
    rest_stage: dict[str, object] = {"courtlistener_rest_screen_inputs": {}}
    firecrawl_stage: dict[str, object] = {
        "firecrawl_screen_inputs": {},
        "firecrawl_screening_implementation": implementation,
    }
    manifest = _union_manifest(
        (rest_stage, firecrawl_stage),
        firecrawl_source_count=1,
        implementation=implementation,
    )

    assert (
        snapshot_firecrawl_screening_source_count(
            manifest,
            require_current=True,
        )
        == 1
    )
    nested = _union_manifest(
        (
            cast(dict[str, object], manifest["stage_commitments"]),
            rest_stage,
        ),
        firecrawl_source_count=1,
        implementation=implementation,
    )
    assert (
        snapshot_firecrawl_screening_source_count(
            nested,
            require_current=True,
        )
        == 1
    )


@pytest.mark.parametrize("mutation", ("missing", "wrong"))
def test_union_firecrawl_source_count_tamper_fails_closed(mutation: str) -> None:
    implementation = firecrawl_screening_implementation()
    manifest = _union_manifest(
        (
            {"courtlistener_rest_screen_inputs": {}},
            {
                "source_bound_replay": {},
                "firecrawl_screening_implementation": implementation,
            },
        ),
        firecrawl_source_count=1,
        implementation=implementation,
    )
    union = cast(
        dict[str, object],
        cast(dict[str, object], manifest["stage_commitments"])[
            "screening_snapshot_union_inputs"
        ],
    )
    if mutation == "missing":
        union.pop("firecrawl_screening_source_count")
    else:
        union["firecrawl_screening_source_count"] = 0

    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match=r"exact Firecrawl count|Firecrawl count mismatch",
    ):
        snapshot_firecrawl_screening_source_count(
            manifest,
            require_current=True,
        )


def test_rest_only_union_rejects_orphan_firecrawl_implementation() -> None:
    manifest = _union_manifest(
        (
            {"courtlistener_rest_screen_inputs": {}},
            {"courtlistener_rest_screen_inputs": {}},
        ),
        firecrawl_source_count=0,
        implementation=firecrawl_screening_implementation(),
    )

    with pytest.raises(
        FirecrawlScreeningIdentityError,
        match="REST-only union",
    ):
        snapshot_firecrawl_screening_source_count(
            manifest,
            require_current=True,
        )


def _union_manifest(
    source_stage_commitments: tuple[Mapping[str, object], ...],
    *,
    firecrawl_source_count: int,
    implementation: Mapping[str, object] | None,
) -> dict[str, object]:
    union: dict[str, object] = {
        "schema_version": "legalforecast.screening_snapshot_union_inputs.v2",
        "source_count": len(source_stage_commitments),
        "sources": [
            {"stage_commitments": stage_commitments}
            for stage_commitments in source_stage_commitments
        ],
        "firecrawl_screening_source_count": firecrawl_source_count,
    }
    stage_commitments: dict[str, object] = {"screening_snapshot_union_inputs": union}
    if implementation is not None:
        stage_commitments["firecrawl_screening_implementation"] = dict(implementation)
    return {"stage_commitments": stage_commitments}


def _sources(commitment: Mapping[str, object]) -> dict[str, str]:
    value = commitment["source_sha256"]
    assert isinstance(value, dict)
    return cast(dict[str, str], value)


def _final153_rebind_commitment() -> dict[str, object]:
    return {
        "schema_version": SCREENING_UNION_POLICY_REBIND_IMPLEMENTATION_SCHEMA,
        "source_sha256": dict(_FINAL153_REBIND_SOURCE_SHA256),
        "manifest_sha256": _FINAL153_REBIND_MANIFEST_SHA256,
    }


def _policy_rebind_manifest_sha256(source_sha256: Mapping[str, str]) -> str:
    payload = b"".join(
        f"{path}\0{source_sha256[path]}\n".encode()
        for path in SCREENING_UNION_POLICY_REBIND_SOURCE_PATHS
    )
    return hashlib.sha256(payload).hexdigest()
