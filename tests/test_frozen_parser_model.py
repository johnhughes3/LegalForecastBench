"""The preserved parser model must be authenticated, closed, and fail closed."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from legalforecast.ingestion import courtlistener_web as current_web
from legalforecast.ingestion.firecrawl_screening_identity import (
    COMPATIBLE_911371F_FINAL153_SOURCE_SHA256,
)
from legalforecast.ingestion.frozen_parser_model import loader as frozen_loader
from legalforecast.ingestion.frozen_parser_model.loader import load_parser_model
from legalforecast.ingestion.frozen_parser_model.registry import (
    CURRENT_PARSER_MODEL,
    PARSER_MODEL_911371F,
    FrozenParserModelError,
    frozen_parser_model_identity,
    frozen_parser_model_versions,
    parser_model_version_for_snapshot,
)

FINAL153_SNAPSHOT_MANIFEST_SHA256 = (
    "487bec5f70289e212554a9af59fc195c9d6244060550d346612cb589405b138c"
)
PRESERVED_MODULES = ("courtlistener_web", "mtd_acquisition_screen")


def preserved_source_path(version: str, module: str) -> Path:
    return (
        Path(frozen_loader.__file__).resolve().parent
        / "sources"
        / version
        / f"{module}.pysource"
    )


def test_preserved_sources_match_the_already_authenticated_identity_pins() -> None:
    """The preserved bytes mint no new trust root.

    Each digest below is the one ``firecrawl_screening_identity`` already
    allowlists for the 911371f producer, so a reformat or any other edit of the
    preserved sources fails here rather than silently replaying a model the
    identity layer never accepted.
    """

    for module in PRESERVED_MODULES:
        payload = preserved_source_path(PARSER_MODEL_911371F, module).read_bytes()
        assert (
            hashlib.sha256(payload).hexdigest()
            == (
                COMPATIBLE_911371F_FINAL153_SOURCE_SHA256[
                    f"legalforecast/ingestion/{module}.py"
                ]
            )
        ), module


def test_frozen_identity_reuses_those_pins() -> None:
    identity = frozen_parser_model_identity(PARSER_MODEL_911371F)
    for module in PRESERVED_MODULES:
        assert (
            identity.source_sha256[module]
            == (
                COMPATIBLE_911371F_FINAL153_SOURCE_SHA256[
                    f"legalforecast/ingestion/{module}.py"
                ]
            )
        )
    assert identity.accepts_screen_court_id is False
    assert frozen_parser_model_versions() == (PARSER_MODEL_911371F,)


def test_snapshot_digest_selects_its_producing_model() -> None:
    assert (
        parser_model_version_for_snapshot(FINAL153_SNAPSHOT_MANIFEST_SHA256)
        == PARSER_MODEL_911371F
    )


def test_an_unlisted_snapshot_keeps_the_current_model() -> None:
    assert parser_model_version_for_snapshot("0" * 64) == CURRENT_PARSER_MODEL


def test_an_unpinned_model_version_fails_closed() -> None:
    with pytest.raises(FrozenParserModelError, match="not pinned"):
        load_parser_model("911371f-but-not-really")


def test_a_tampered_preserved_source_refuses_to_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """One flipped byte must refuse, not load a slightly different model."""

    version = PARSER_MODEL_911371F
    tampered_root = tmp_path / "sources" / version
    tampered_root.mkdir(parents=True)
    for module in PRESERVED_MODULES:
        payload = preserved_source_path(version, module).read_bytes()
        (tampered_root / f"{module}.pysource").write_bytes(
            payload.replace(b"OTHER = ", b"OTHER  = ", 1)
        )
    monkeypatch.setattr(frozen_loader, "_SOURCES_ROOT", tmp_path / "sources")
    monkeypatch.setattr(frozen_loader, "_CACHE", {})

    with pytest.raises(
        FrozenParserModelError, match="differs from its authenticated digest"
    ):
        load_parser_model(version)


def test_a_missing_preserved_source_refuses_to_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(frozen_loader, "_SOURCES_ROOT", tmp_path / "sources")
    monkeypatch.setattr(frozen_loader, "_CACHE", {})

    with pytest.raises(FrozenParserModelError, match="not a regular file"):
        load_parser_model(PARSER_MODEL_911371F)


def test_the_preserved_screen_binds_the_preserved_parser() -> None:
    """The composition must never mix a preserved screen with the live parser.

    ``mtd_acquisition_screen`` imports ``courtlistener_web`` by its package
    path, so a naive load would bind the current implementation and produce a
    model that never generated any evidence.
    """

    model = load_parser_model(PARSER_MODEL_911371F)
    preserved_entry_class = model._screen.__dict__["CourtListenerWebDocketEntry"]

    assert preserved_entry_class is model._web.__dict__["CourtListenerWebDocketEntry"]
    assert preserved_entry_class is not current_web.CourtListenerWebDocketEntry


def test_loading_a_preserved_model_leaves_the_production_modules_alone() -> None:
    import sys

    load_parser_model(PARSER_MODEL_911371F)

    assert sys.modules["legalforecast.ingestion.courtlistener_web"] is current_web


def test_role_values_agree_across_every_pinned_model() -> None:
    """Role *values* are frozen evidence, so they must be model-invariant.

    Downstream role mapping is keyed by value rather than by enum member,
    because ``Enum.__hash__`` hashes the member name while ``StrEnum.__eq__``
    compares the value, and members of two model classes are not interchangeable
    dictionary keys.
    """

    expected = [member.value for member in current_web.CourtListenerEntryRole]
    for version in frozen_parser_model_versions():
        model = load_parser_model(version)
        assert [
            member.value for member in model._web.__dict__["CourtListenerEntryRole"]
        ] == expected, version


def test_the_two_models_really_do_classify_differently() -> None:
    """Guard the premise: without drift, versioned replay would be pointless."""

    text = "RESPONSE in Opposition re 12 MOTION for Summary Judgment"
    fields = {
        "row_id": "row-1",
        "entry_number": "13",
        "filed_at": "01/02/2025",
        "text": text,
        "documents": (),
        "restriction_markers": (),
    }

    preserved = load_parser_model(PARSER_MODEL_911371F).entry(**fields)
    current = load_parser_model(CURRENT_PARSER_MODEL).entry(**fields)

    assert str(preserved.role) == "other"
    assert str(current.role) == "opposition"


def test_the_preserved_screen_is_called_without_court_id() -> None:
    """The screen API gained ``court_id`` after this model was frozen."""

    preserved = load_parser_model(PARSER_MODEL_911371F)
    current = load_parser_model(CURRENT_PARSER_MODEL)

    assert preserved.accepts_screen_court_id is False
    assert current.accepts_screen_court_id is True
