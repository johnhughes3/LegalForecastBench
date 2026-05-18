from __future__ import annotations

import tomllib
from pathlib import Path

import legalforecast

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_alpha_release_convention() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["version"] == legalforecast.__version__
    assert legalforecast.__version__ == "0.1.0a1"


def test_public_docs_record_alpha_version_and_tag() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "0.1.0a1" in readme
    assert "v0.1.0-alpha.1" in readme
