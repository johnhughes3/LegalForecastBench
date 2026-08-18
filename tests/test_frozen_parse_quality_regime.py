"""The predecessor gate regime may only ever narrow *which gate*, never *which bytes*.

``parse_quality`` was added by PR #764, five days after the exact-100
predecessor cohort was parsed, and the predecessor ``llm-unitize`` run card
commits that parse manifest by digest — so the committed inputs cannot be
redirected at a corrected parse stage.  Replaying that evidence under the
assessment regime that produced it is therefore the only route that does not
either suppress a real finding or rewrite a paid run card.

These tests pin the two properties that make the selection safe: a tampered
byte still refuses under the preserved regime, and evidence outside the closed
pin cannot select that regime.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.frozen_parse_quality_regime import (
    FROZEN_PREDECESSOR_PARSE_QUALITY_REGIME,
    PARSE_QUALITY_REGIME_CURRENT,
    PARSE_QUALITY_REGIME_PRE_764,
    ParseQualityRegimeError,
    frozen_predecessor_parse_quality_regime,
    parse_quality_regime_names,
    replay_parse_quality_regime,
    resolve_parse_quality_regime,
)
from legalforecast.ingestion.stage_a_lineage_verification import (
    verify_stage_a_parse_records,
)

# The 2026-08-07 exact-100 predecessor parse manifest, the single pinned digest.
_PINNED_MANIFEST_SHA256 = (
    "53c9e7245b56b0f21e5cac715a6010156ba4d3f4d322911d54beb27279de8357"
)
# Stages 31/32, the ancestor the materialization projection replays while
# authenticating 47.
_PINNED_ANCESTOR_MANIFEST_SHA256 = (
    "f0059a6c19afec540331337a4f8e5ba89a7802f886180943b318bde7bf35bcc6"
)
_BOILERPLATE_ONLY = (
    "Case 2:25-cv-02154-DCF Document 3 Filed 11/20/25 Page 1 of 21 PageID #: 154\n"
    "Case 2:25-cv-02154-DCF Document 3 Filed 11/20/25 Page 2 of 21 PageID #: 155\n"
)


def test_the_pinned_map_holds_exactly_the_one_audited_manifest() -> None:
    """A closed mapping is the whole security argument; keep it visible."""

    assert dict(FROZEN_PREDECESSOR_PARSE_QUALITY_REGIME) == {
        _PINNED_MANIFEST_SHA256: PARSE_QUALITY_REGIME_PRE_764,
        _PINNED_ANCESTOR_MANIFEST_SHA256: PARSE_QUALITY_REGIME_PRE_764,
    }
    assert parse_quality_regime_names() == (
        PARSE_QUALITY_REGIME_CURRENT,
        PARSE_QUALITY_REGIME_PRE_764,
    )


def test_an_unlisted_manifest_selects_the_current_gate() -> None:
    """Default strict: only an audited digest may replay under a past regime."""

    assert (
        frozen_predecessor_parse_quality_regime("f" * 64)
        == PARSE_QUALITY_REGIME_CURRENT
    )
    assert (
        frozen_predecessor_parse_quality_regime(_PINNED_MANIFEST_SHA256)
        == PARSE_QUALITY_REGIME_PRE_764
    )
    assert (
        frozen_predecessor_parse_quality_regime(f"sha256:{_PINNED_MANIFEST_SHA256}")
        == PARSE_QUALITY_REGIME_PRE_764
    )


@pytest.mark.parametrize(
    ("digest", "flagged", "expected"),
    [
        pytest.param(
            _PINNED_MANIFEST_SHA256,
            True,
            PARSE_QUALITY_REGIME_PRE_764,
            id="pinned-and-frozen-caller",
        ),
        pytest.param(
            _PINNED_MANIFEST_SHA256,
            False,
            PARSE_QUALITY_REGIME_CURRENT,
            id="pinned-but-ordinary-caller",
        ),
        pytest.param(
            "f" * 64, True, PARSE_QUALITY_REGIME_CURRENT, id="frozen-caller-unpinned"
        ),
        pytest.param("f" * 64, False, PARSE_QUALITY_REGIME_CURRENT, id="neither"),
    ],
)
def test_both_conditions_are_required(
    digest: str, flagged: bool, expected: str
) -> None:
    """The whole truth table, because neither condition alone may suffice.

    The third row matters most in practice: the flag reaches shared code that
    also replays ancestors while authenticating the *successor* half, so an
    unpinned manifest has to stay strict even on a flagged path.
    """

    assert (
        replay_parse_quality_regime(
            parser_manifest_sha256=digest, frozen_predecessor_replay=flagged
        )
        == expected
    )


def test_an_unpinned_regime_name_fails_closed() -> None:
    """An unknown regime is a defect, not a licence to skip the gate."""

    with pytest.raises(ParseQualityRegimeError, match="regime is not pinned"):
        resolve_parse_quality_regime("lenient")
    assert resolve_parse_quality_regime(
        PARSE_QUALITY_REGIME_CURRENT
    ).enforces_parse_quality
    assert not resolve_parse_quality_regime(
        PARSE_QUALITY_REGIME_PRE_764
    ).enforces_parse_quality


class _ParseLineageReached(Exception):
    """Sentinel carrying the flag the parse-lineage verifier was handed."""

    def __init__(self, frozen_predecessor_replay: bool) -> None:
        super().__init__(str(frozen_predecessor_replay))
        self.frozen_predecessor_replay = frozen_predecessor_replay


def test_only_the_frozen_predecessor_branch_asserts_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the wiring, because the flag is caller-asserted rather than checked.

    Reading the call graph is exactly how a future live caller would inherit
    this branch unnoticed, so assert both directions: building the lineage in
    place asserts the frozen-predecessor context, and the shared entry point
    defaults to not asserting it.
    """

    import legalforecast.ingestion.stage_a_lineage_verification as slv

    # Read the real default before patching: it is what keeps the successor
    # half, and every ordinary caller, on the current gate.
    assert (
        inspect.signature(slv.verify_stage_a_parse_lineage_uncached)
        .parameters["frozen_predecessor_replay"]
        .default
        is False
    )

    def _capture(
        _inputs: object,
        *,
        markdown_root: Path,
        frozen_predecessor_replay: bool = False,
    ) -> None:
        del markdown_root
        raise _ParseLineageReached(frozen_predecessor_replay)

    monkeypatch.setattr(slv, "verify_stage_a_parse_lineage_uncached", _capture)

    with pytest.raises(_ParseLineageReached) as caught:
        slv.verify_stage_a_unitization_lineage_uncached(
            cast(Any, object()), markdown_root=Path("/nonexistent")
        )
    assert caught.value.frozen_predecessor_replay is True


def _parse_records(
    tmp_path: Path, *, markdown: str
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Author one authenticated-shaped parse row over ``markdown``."""

    markdown_root = tmp_path / "markdown"
    (markdown_root / "cand-1").mkdir(parents=True)
    payload = markdown.encode("utf-8")
    (markdown_root / "cand-1" / "complaint.md").write_bytes(payload)
    document_root = tmp_path / "documents"
    document_root.mkdir()
    (document_root / "complaint.pdf").write_bytes(b"%PDF fixture")
    download = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "document_role": "complaint",
        "local_path": "complaint.pdf",
        "sha256": "a" * 64,
        "byte_count": 12,
    }
    request = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "input_path": str((document_root / "complaint.pdf").resolve()),
        "markdown_output_path": "markdown/cand-1/complaint.md",
        "expected_sha256": "a" * 64,
        "expected_byte_count": 12,
    }
    parser = {
        "candidate_id": "cand-1",
        "source_document_id": "complaint",
        "status": "succeeded",
        "quality_flags": [],
        # Parser records name Markdown relative to the Markdown root; requests
        # name it relative to the parser output root.
        "markdown_path": "cand-1/complaint.md",
        "parser_config": {"engine": "mistral"},
        "extracted_text": {
            "extraction_method": "mistral_parser_markdown",
            "text_sha256": hashlib.sha256(payload).hexdigest(),
        },
        "source_sha256": "a" * 64,
        "source_byte_count": 12,
    }
    return (
        {
            "download_records": (download,),
            "request_records": (request,),
            "parser_records": (parser,),
            "document_root": tmp_path / "documents",
            "parser_output_root": tmp_path,
            "markdown_root": markdown_root,
            "markdown_bytes": {"cand-1/complaint.md": payload},
        },
        {"cand-1/complaint.md": payload},
    )


def _verify(kwargs: dict[str, Any], **overrides: Any) -> None:
    verify_stage_a_parse_records(**{**kwargs, **overrides})


def test_the_preserved_regime_still_refuses_a_tampered_byte(tmp_path: Path) -> None:
    """Direction one: byte identity is never relaxed by the regime selection.

    The record commits ``text_sha256`` over the Markdown it produced.  Flipping
    one byte of the captured Markdown must refuse under the preserved regime
    exactly as it does under the current one — the regime decides only whether a
    gate written later is applied retroactively.
    """

    from legalforecast.cli import CommandError

    kwargs, payloads = _parse_records(tmp_path, markdown=_BOILERPLATE_ONLY)
    # Boilerplate-only Markdown is precisely what the current gate rejects, so
    # this row proves the preserved regime is doing something...
    _verify(kwargs, parse_quality_regime=PARSE_QUALITY_REGIME_PRE_764)
    with pytest.raises(CommandError, match="parser Markdown failed parse-quality gate"):
        _verify(kwargs, parse_quality_regime=PARSE_QUALITY_REGIME_CURRENT)

    # ...and this proves it is doing only that.
    tampered = dict(payloads)
    tampered["cand-1/complaint.md"] = payloads["cand-1/complaint.md"] + b"x"
    (tmp_path / "markdown" / "cand-1" / "complaint.md").write_bytes(
        tampered["cand-1/complaint.md"]
    )
    with pytest.raises(CommandError, match="parser Markdown hash differs"):
        _verify(
            kwargs,
            markdown_bytes=tampered,
            parse_quality_regime=PARSE_QUALITY_REGIME_PRE_764,
        )


def test_an_unpinned_regime_refuses_the_whole_replay(tmp_path: Path) -> None:
    """A regime name nobody pinned must never read as 'no gate'."""

    kwargs, _payloads = _parse_records(tmp_path, markdown=_BOILERPLATE_ONLY)

    with pytest.raises(ParseQualityRegimeError, match="regime is not pinned"):
        _verify(kwargs, parse_quality_regime="pre-764")
