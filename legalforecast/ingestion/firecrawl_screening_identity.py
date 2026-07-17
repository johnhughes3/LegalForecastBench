"""Fail-closed source identity for the provider-free Firecrawl screen.

The global cycle identity intentionally covers only the source-neutral strict
screen.  Firecrawl replay and promotion execute additional parsing,
orchestration, and storage code.  This module commits that closed transitive
set without changing the identity of independent CourtListener REST snapshots.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Final, cast

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA: Final = (
    "legalforecast.firecrawl_screening_implementation.v1"
)
SCREENING_SNAPSHOT_UNION_INPUTS_SCHEMA: Final = (
    "legalforecast.screening_snapshot_union_inputs.v2"
)
FIRECRAWL_SCREENING_IMPLEMENTATION_STAGE_KEY: Final = (
    "firecrawl_screening_implementation"
)
FIRECRAWL_SCREENING_DIRECT_STAGE_KEYS: Final = frozenset(
    {
        "firecrawl_screen_inputs",
        "source_bound_replay",
        "terminal_subset_promotion",
    }
)
SCREENING_SNAPSHOT_UNION_STAGE_KEY: Final = "screening_snapshot_union_inputs"
SOURCE_NEUTRAL_DIRECT_STAGE_KEYS: Final = frozenset(
    {
        "courtlistener_discovery_inputs",
        "courtlistener_rest_screen_inputs",
    }
)
SOURCE_NEUTRAL_NAMED_STAGES: Final = frozenset(
    {
        "exact310-terminal-rest-policy-rebind",
        "rebind-terminal-rest-observations",
    }
)

# Ordered exactly as the audited 18-file compatibility set.  The strict-proof
# validator and recursive union loader are load-bearing admission code, and the
# identity module itself closes the resulting 21-file set.
FIRECRAWL_SCREENING_SOURCE_PATHS: Final = (
    "legalforecast/cli.py",
    "legalforecast/ingestion/budgeted_docket_acquisition.py",
    "legalforecast/ingestion/case_dev_firecrawl.py",
    "legalforecast/ingestion/courtlistener_acquisition.py",
    "legalforecast/ingestion/courtlistener_client.py",
    "legalforecast/ingestion/courtlistener_dates.py",
    "legalforecast/ingestion/courtlistener_web.py",
    "legalforecast/ingestion/cycle_acquisition_store.py",
    "legalforecast/ingestion/docket_sync.py",
    "legalforecast/ingestion/mtd_acquisition_screen.py",
    "legalforecast/ingestion/operative_complaint.py",
    "legalforecast/ingestion/provenance.py",
    "legalforecast/ingestion/recap_api_discovery.py",
    "legalforecast/ingestion/restricted_material.py",
    "legalforecast/ingestion/snapshot_replay.py",
    "legalforecast/ingestion/strict_screen_evidence.py",
    "legalforecast/ingestion/screening_snapshot_union.py",
    "legalforecast/selection/contamination_filters.py",
    "legalforecast/selection/exclusion_ledger.py",
    "legalforecast/selection/motion_linkage.py",
    "legalforecast/ingestion/firecrawl_screening_identity.py",
)

LEGACY_32057DE_SOURCE_MANIFEST_SHA256: Final = (
    "3e1628b1bbeb3d2af682baaa12815a4c631a64a0ca95eadf2d70e9fa9da419c9"
)
LEGACY_32057DE_SOURCE_SHA256: Final[Mapping[str, str]] = {
    "legalforecast/cli.py": (
        "f8084d8e8dea277366131b0ba899e6034ebc3fc000621ddaca798825b855e18c"
    ),
    "legalforecast/ingestion/budgeted_docket_acquisition.py": (
        "a11b91e5b9cef810ab88d6dde16bfe0dc4d77dbce798bf3e354261d34f8c10a9"
    ),
    "legalforecast/ingestion/case_dev_firecrawl.py": (
        "4e3d1bf19c975264c185d1ef6e1c3132a43b72e91d2031b7e98ca93b028180b1"
    ),
    "legalforecast/ingestion/courtlistener_acquisition.py": (
        "261ab270306634cdaf18520ed7bc5e39282ce4dac923c8bb2e307ebda8445394"
    ),
    "legalforecast/ingestion/courtlistener_client.py": (
        "5afbee992368bd790db9eb118a08b895bfe01599f51d8f37885f3d0fcc31640c"
    ),
    "legalforecast/ingestion/courtlistener_dates.py": (
        "c414deb237d62fe6fbdd43863cdd4acf0387a5de54ecb21f0cd7c0ec88417f3d"
    ),
    "legalforecast/ingestion/courtlistener_web.py": (
        "35f4b0a3c88a55cc00de1a61782b8c5a8f1ba64db23c2fe55a1f950ff12c869b"
    ),
    "legalforecast/ingestion/cycle_acquisition_store.py": (
        "94ef6986c054250f75ee93d4f5d99a5192b51fdb03ee4627eea694325b1f0973"
    ),
    "legalforecast/ingestion/docket_sync.py": (
        "0731149bd3d84bf6d87d6e59fbe2631555b4b345b3d0824ad01bb567bc80d33f"
    ),
    "legalforecast/ingestion/mtd_acquisition_screen.py": (
        "72084326faa7f76afc6075556fd8ba6738df83189ce178100cb1a0eb50630e7e"
    ),
    "legalforecast/ingestion/operative_complaint.py": (
        "aff85d1a327d3a7dc44f884d9bd833010ffe3fb32136d48153d4ccb48851a5eb"
    ),
    "legalforecast/ingestion/provenance.py": (
        "fb67f7db133dd3382c12c37010485d321f9b0fab93d7fc9a2f617628d254ae14"
    ),
    "legalforecast/ingestion/recap_api_discovery.py": (
        "ca6ed64c73939778dd1a30e3e018cb72e1866d7ba854c3e061807c9dcd9f8623"
    ),
    "legalforecast/ingestion/restricted_material.py": (
        "f36a0cf5b5db5e3d6d997d46095cccfde89be9a9213db6b26576a116ed16758d"
    ),
    "legalforecast/ingestion/snapshot_replay.py": (
        "b019d01e2a1fef7546d7c12a50dafa60bf6f4c6862493633e60a986a3e410ac1"
    ),
    "legalforecast/selection/contamination_filters.py": (
        "e1437bf64633071c06fa28bee618e8cc17e2a41ca929e9e3a1e8164e4048bde9"
    ),
    "legalforecast/selection/exclusion_ledger.py": (
        "092dc50db5bd27ea924c61472841522a2bce03f9ae81115ed2aceb5d5a6a2915"
    ),
    "legalforecast/selection/motion_linkage.py": (
        "a44d1bb198801cc99d3057d148527e31d6cd5ef6dbdfc0c13271f2cc97f8cfe2"
    ),
}


class FirecrawlScreeningIdentityError(ValueError):
    """Raised when a Firecrawl screening source commitment is not exact."""


def firecrawl_screening_implementation(
    *, source_root: Path | None = None
) -> dict[str, object]:
    """Return the current exact 21-file implementation commitment."""

    root = (
        Path(__file__).resolve().parents[2]
        if source_root is None
        else source_root.resolve()
    )
    source_sha256: dict[str, str] = {}
    for relative_path in FIRECRAWL_SCREENING_SOURCE_PATHS:
        path = root / relative_path
        if path.is_symlink() or not path.is_file():
            raise FirecrawlScreeningIdentityError(
                f"Firecrawl screening source is missing or unsafe: {relative_path}"
            )
        source_sha256[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
        "source_sha256": source_sha256,
        "manifest_sha256": source_manifest_sha256(source_sha256),
    }


def source_manifest_sha256(source_sha256: Mapping[str, str]) -> str:
    """Hash an exact ordered ``path\0sha256\n`` source manifest."""

    if set(source_sha256) == set(FIRECRAWL_SCREENING_SOURCE_PATHS):
        ordered_paths = FIRECRAWL_SCREENING_SOURCE_PATHS
    elif set(source_sha256) == set(LEGACY_32057DE_SOURCE_SHA256):
        ordered_paths = tuple(LEGACY_32057DE_SOURCE_SHA256)
    else:
        ordered_paths = tuple(source_sha256)
    payload = b"".join(
        f"{path}\0{source_sha256[path]}\n".encode() for path in ordered_paths
    )
    return hashlib.sha256(payload).hexdigest()


def validate_firecrawl_screening_implementation(
    commitment: object,
    *,
    require_current: bool,
) -> dict[str, object]:
    """Validate exact shape/digest and optionally current source equality."""

    if not isinstance(commitment, Mapping):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening implementation commitment must be an object"
        )
    typed = cast(Mapping[str, object], commitment)
    if set(typed) != {"schema_version", "source_sha256", "manifest_sha256"}:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening implementation commitment has unexpected fields"
        )
    if typed.get("schema_version") != FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening implementation schema mismatch"
        )
    source_value = typed.get("source_sha256")
    if not isinstance(source_value, Mapping):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source commitment must be an object"
        )
    source_mapping = cast(Mapping[object, object], source_value)
    if set(source_mapping) != set(FIRECRAWL_SCREENING_SOURCE_PATHS):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source key set changed"
        )
    normalized_sources: dict[str, str] = {}
    for path, digest in source_mapping.items():
        if not isinstance(path, str) or not isinstance(digest, str):
            raise FirecrawlScreeningIdentityError(
                "Firecrawl screening source commitment is malformed"
            )
        if _SHA256.fullmatch(digest) is None:
            raise FirecrawlScreeningIdentityError(
                f"Firecrawl screening source SHA-256 is malformed: {path}"
            )
        normalized_sources[path] = digest
    manifest_sha256 = typed.get("manifest_sha256")
    if (
        not isinstance(manifest_sha256, str)
        or _SHA256.fullmatch(manifest_sha256) is None
    ):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source manifest SHA-256 is malformed"
        )
    if source_manifest_sha256(normalized_sources) != manifest_sha256:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening source manifest commitment mismatch"
        )
    normalized: dict[str, object] = {
        "schema_version": FIRECRAWL_SCREENING_IMPLEMENTATION_SCHEMA,
        "source_sha256": {
            path: normalized_sources[path] for path in FIRECRAWL_SCREENING_SOURCE_PATHS
        },
        "manifest_sha256": manifest_sha256,
    }
    if require_current and normalized != firecrawl_screening_implementation():
        raise FirecrawlScreeningIdentityError(
            "Firecrawl screening sources do not match the committed implementation"
        )
    return normalized


def require_snapshot_firecrawl_screening_implementation(
    manifest: Mapping[str, object], *, require_current: bool
) -> dict[str, object]:
    """Extract and validate the required stage commitment from a snapshot."""

    stage_commitments = manifest.get("stage_commitments")
    if not isinstance(stage_commitments, Mapping):
        raise FirecrawlScreeningIdentityError(
            "Firecrawl snapshot lacks stage commitments"
        )
    commitment = cast(Mapping[str, object], stage_commitments).get(
        FIRECRAWL_SCREENING_IMPLEMENTATION_STAGE_KEY
    )
    if commitment is None:
        raise FirecrawlScreeningIdentityError(
            "Firecrawl snapshot lacks firecrawl_screening_implementation"
        )
    return validate_firecrawl_screening_implementation(
        commitment, require_current=require_current
    )


def snapshot_firecrawl_screening_source_count(
    manifest: Mapping[str, object], *, require_current: bool
) -> int:
    """Return authenticated Firecrawl source leaves contributing to a snapshot."""

    stage_commitments = manifest.get("stage_commitments")
    if stage_commitments is None:
        raise FirecrawlScreeningIdentityError(
            "snapshot lacks affirmative stage commitments"
        )
    if not isinstance(stage_commitments, Mapping):
        raise FirecrawlScreeningIdentityError(
            "snapshot stage commitments must be an object"
        )
    if not stage_commitments:
        raise FirecrawlScreeningIdentityError(
            "snapshot lacks affirmative stage commitments"
        )
    return _stage_firecrawl_screening_source_count(
        cast(Mapping[str, object], stage_commitments),
        require_current=require_current,
        label="snapshot",
    )


def _stage_firecrawl_screening_source_count(
    stage_commitments: Mapping[str, object],
    *,
    require_current: bool,
    label: str,
) -> int:
    direct_keys = FIRECRAWL_SCREENING_DIRECT_STAGE_KEYS.intersection(stage_commitments)
    union_present = SCREENING_SNAPSHOT_UNION_STAGE_KEY in stage_commitments
    union_value = stage_commitments.get(SCREENING_SNAPSHOT_UNION_STAGE_KEY)
    implementation = stage_commitments.get(FIRECRAWL_SCREENING_IMPLEMENTATION_STAGE_KEY)
    if union_present:
        if direct_keys:
            raise FirecrawlScreeningIdentityError(
                f"{label} mixes direct Firecrawl and union stage commitments"
            )
        if not isinstance(union_value, Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union commitment must be an object"
            )
        union = cast(Mapping[str, object], union_value)
        if union.get("schema_version") != SCREENING_SNAPSHOT_UNION_INPUTS_SCHEMA:
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union schema is not identity-aware v2"
            )
        source_count = union.get("source_count")
        sources = union.get("sources")
        firecrawl_source_count = union.get("firecrawl_screening_source_count")
        if not isinstance(sources, list):
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union lacks an exact Firecrawl count"
            )
        typed_sources = cast(list[object], sources)
        if (
            not isinstance(source_count, int)
            or isinstance(source_count, bool)
            or source_count < 2
            or len(typed_sources) != source_count
            or not isinstance(firecrawl_source_count, int)
            or isinstance(firecrawl_source_count, bool)
            or firecrawl_source_count < 0
        ):
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union lacks an exact Firecrawl count"
            )
        computed_count = 0
        for index, source_value in enumerate(typed_sources, start=1):
            if not isinstance(source_value, Mapping):
                raise FirecrawlScreeningIdentityError(
                    f"{label} union source {index} must be an object"
                )
            source = cast(Mapping[str, object], source_value)
            nested_stage_commitments = source.get("stage_commitments")
            if not isinstance(nested_stage_commitments, Mapping):
                raise FirecrawlScreeningIdentityError(
                    f"{label} union source {index} lacks stage commitments"
                )
            computed_count += _stage_firecrawl_screening_source_count(
                cast(Mapping[str, object], nested_stage_commitments),
                require_current=require_current,
                label=f"{label} union source {index}",
            )
        if computed_count != firecrawl_source_count:
            raise FirecrawlScreeningIdentityError(
                f"{label} screening snapshot union Firecrawl count mismatch"
            )
        if firecrawl_source_count:
            if implementation is None:
                raise FirecrawlScreeningIdentityError(
                    f"{label} lacks firecrawl_screening_implementation"
                )
            validate_firecrawl_screening_implementation(
                implementation,
                require_current=require_current,
            )
        elif implementation is not None:
            raise FirecrawlScreeningIdentityError(
                f"{label} REST-only union has a Firecrawl implementation commitment"
            )
        return firecrawl_source_count
    if direct_keys:
        if len(direct_keys) != 1:
            raise FirecrawlScreeningIdentityError(
                f"{label} has ambiguous direct Firecrawl stage commitments"
            )
        if implementation is None:
            raise FirecrawlScreeningIdentityError(
                f"{label} lacks firecrawl_screening_implementation"
            )
        validate_firecrawl_screening_implementation(
            implementation,
            require_current=require_current,
        )
        return 1
    if implementation is not None:
        raise FirecrawlScreeningIdentityError(
            f"{label} has an orphan Firecrawl implementation commitment"
        )
    source_neutral_keys = SOURCE_NEUTRAL_DIRECT_STAGE_KEYS.intersection(
        stage_commitments
    )
    for source_neutral_key in source_neutral_keys:
        if not isinstance(stage_commitments[source_neutral_key], Mapping):
            raise FirecrawlScreeningIdentityError(
                f"{label} source-neutral commitment must be an object: "
                f"{source_neutral_key}"
            )
    named_stage = stage_commitments.get("stage")
    recognized_named_stage = (
        isinstance(named_stage, str) and named_stage in SOURCE_NEUTRAL_NAMED_STAGES
    )
    source_neutral_form_count = len(source_neutral_keys) + int(recognized_named_stage)
    if source_neutral_form_count == 0:
        raise FirecrawlScreeningIdentityError(
            f"{label} lacks recognized source-neutral lineage"
        )
    if source_neutral_form_count != 1:
        raise FirecrawlScreeningIdentityError(
            f"{label} has ambiguous source-neutral lineage"
        )
    return 0
