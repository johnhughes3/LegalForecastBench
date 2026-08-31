"""Fence the PDF text extractor version Cycle 1's settled evidence replays under."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pypdf

PINNED_PDF_EXTRACTOR_VERSION = "6.14.2"
UNLOCK_CONDITION = (
    "pinned while Cycle 1's settled disclosure evidence must replay; unpin "
    "after Cycle 1 closes or when renderer versioning lands"
)
PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_pdf_text_extractor_stays_pinned_for_cycle_1_replay() -> None:
    """The PDF text extractor is a frozen input of the Cycle 1 evidence chain.

    ``build_marker_page_prompt`` renders its prompt from
    ``extract_disclosure_pdf_pages``, which reads through pypdf. That prompt
    text is hashed into ``prompt_sha256``, which is one of the seven fields
    ``ProviderAttemptJournal._validate_replay`` requires a replay to reproduce
    exactly. So a pypdf release that extracts different text from the same bytes
    retroactively makes every settled disclosure attempt unreplayable -- without
    touching a single document.

    That is not hypothetical. #1022 bumped pypdf 6.14.2 -> 6.16.2 and broke
    ``acquisition issue-manifest-freeze-inputs``: the same command on the same
    inputs passed at 6.14.2 and failed at 6.16.2, with ``prompt_sha256`` the
    only one of the seven identity fields that differed. The documents were
    unchanged -- their sha256 and byte_count commitments both still passed.

    UNLOCK CONDITION: pinned while Cycle 1's settled disclosure evidence must
    replay. Unpin after Cycle 1 closes, or when renderer versioning lands (the
    prompt-layer analogue of ``_SUPERSEDED_USAGE_RULES``), whichever is first.
    """

    assert pypdf.__version__ == PINNED_PDF_EXTRACTOR_VERSION, (
        f"installed pypdf {pypdf.__version__} is not the pinned "
        f"{PINNED_PDF_EXTRACTOR_VERSION}; a different extractor renders "
        f"different prompt bytes and Cycle 1's settled disclosure attempts stop "
        f"replaying. {UNLOCK_CONDITION}."
    )


def test_pyproject_pins_the_extractor_exactly_rather_than_flooring_it() -> None:
    """A floor is what let a routine dependency update invalidate settled evidence.

    ``pypdf>=6.16.2`` is what #1022 left behind, and a floor is precisely the
    shape that lets the next Dependabot run move the extractor again. The
    constraint has to be an exact pin for the fence above to mean anything.
    """

    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert f"pypdf=={PINNED_PDF_EXTRACTOR_VERSION}" in dependencies, (
        f"pyproject.toml must pin pypdf=={PINNED_PDF_EXTRACTOR_VERSION} exactly, "
        f"not a floor: a floor lets a routine dependency update change the "
        f"rendered prompt bytes and invalidate settled evidence. "
        f"{UNLOCK_CONDITION}."
    )
