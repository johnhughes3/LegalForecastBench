from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_result_tier_policy_defines_publication_and_submission_contracts() -> None:
    policy = _read("docs/result_tiers.md")
    readme = _read("README.md")
    methodology = _read("docs/methodology.md")
    run_card_template = _read("docs/run_card_template.md")

    required_policy_terms = (
        "official",
        "verified-community",
        "community-unverified",
        "canonical leaderboard",
        "validated run card",
        "frozen artifacts",
        "independent reproduction",
        "self-reported",
        "submission bundle",
    )

    missing = [term for term in required_policy_terms if term not in policy]

    assert missing == []
    assert "docs/result_tiers.md" in readme
    assert "Result tiers" in methodology
    assert "Only official results are canonical" in run_card_template


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")
