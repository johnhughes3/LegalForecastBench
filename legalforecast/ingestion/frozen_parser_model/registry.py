"""Authenticated identity of the CourtListener parser model a snapshot used.

A frozen screening snapshot does not store observed bytes alone.  ``role`` on
every selected docket entry, and the whole ``mtd_decision_screen`` assessment,
are *derived* values produced by the parser and screen implementations that ran
at capture time.  Replaying that evidence through a later production model is
therefore not a byte-identity check of the evidence: it compares one model's
output against a different model's output, so any deliberate later broadening of
the classifier reads as evidence corruption.

This module names the model that produced a snapshot, keyed by the snapshot
manifest digest the caller has already authenticated.  It mints no new trust
root.  Every preserved-source digest below is re-used verbatim from the identity
allowlist already on main, so a preserved model is admissible exactly when the
identity layer already accepts the producer that emitted it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from legalforecast.ingestion.firecrawl_screening_identity import (
    COMPATIBLE_911371F_FINAL153_SOURCE_SHA256,
)

CURRENT_PARSER_MODEL: Final = "current"
"""The production model in this checkout, and the default for a new snapshot."""

PARSER_MODEL_911371F: Final = "911371f"
"""The model that produced the 2026-07-24 cycle-1 final153 union snapshot."""


class FrozenParserModelError(ValueError):
    """Raised when a preserved parser model is unpinned or fails its digest."""


@dataclass(frozen=True, slots=True)
class FrozenParserModelIdentity:
    """Exact authenticated identity of one preserved parser model."""

    version: str
    source_sha256: Mapping[str, str]
    accepts_screen_court_id: bool


# The screen API gained ``court_id`` after this model was frozen, so the
# preserved implementation is called with its own historical signature rather
# than being handed an argument it never accepted.
_FROZEN_PARSER_MODELS: Final[Mapping[str, FrozenParserModelIdentity]] = (
    MappingProxyType(
        {
            PARSER_MODEL_911371F: FrozenParserModelIdentity(
                version=PARSER_MODEL_911371F,
                source_sha256=MappingProxyType(
                    {
                        "courtlistener_web": (
                            COMPATIBLE_911371F_FINAL153_SOURCE_SHA256[
                                "legalforecast/ingestion/courtlistener_web.py"
                            ]
                        ),
                        "mtd_acquisition_screen": (
                            COMPATIBLE_911371F_FINAL153_SOURCE_SHA256[
                                "legalforecast/ingestion/mtd_acquisition_screen.py"
                            ]
                        ),
                    }
                ),
                accepts_screen_court_id=False,
            )
        }
    )
)

# Only a snapshot whose manifest digest is named here replays under a preserved
# model.  The mapping is closed and content-addressed: the key is the digest the
# caller already authenticated against its own expected pin, so nothing a
# snapshot carries in its own payload can select its verifier.
SNAPSHOT_PARSER_MODEL: Final[Mapping[str, str]] = MappingProxyType(
    {
        # cycle1-final153-current-policy-union-main-911371f-v1, generated
        # 2026-07-24 at commit 911371fc and bound by the exact-100 predecessor
        # Stage A run cards.
        "487bec5f70289e212554a9af59fc195c9d6244060550d346612cb589405b138c": (
            PARSER_MODEL_911371F
        )
    }
)


def parser_model_version_for_snapshot(snapshot_manifest_sha256: str) -> str:
    """Return the model version that produced one authenticated snapshot.

    An unlisted snapshot replays under the current production model, which is
    the behaviour every snapshot has today.  Selection never relaxes byte
    identity: whichever model is chosen, its output must still reproduce the
    frozen evidence exactly.
    """

    return SNAPSHOT_PARSER_MODEL.get(snapshot_manifest_sha256, CURRENT_PARSER_MODEL)


def frozen_parser_model_identity(version: str) -> FrozenParserModelIdentity:
    """Return one preserved model's authenticated identity, or fail closed."""

    identity = _FROZEN_PARSER_MODELS.get(version)
    if identity is None:
        raise FrozenParserModelError(f"parser model version is not pinned: {version!r}")
    return identity


def frozen_parser_model_versions() -> tuple[str, ...]:
    """Return every pinned preserved model version, in sorted order."""

    return tuple(sorted(_FROZEN_PARSER_MODELS))
