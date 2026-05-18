from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_result_tier_policy_defines_release_boundaries() -> None:
    policy = (ROOT / "docs" / "result_tiers.md").read_text(encoding="utf-8")

    for required_text in (
        "`official`",
        "`verified-community`",
        "`community-unverified`",
        "results/",
        "alpha/",
        "v0.1/",
        "superseded_by",
        "non-canonical-superseded",
        "No Hosted Community Runner",
        "bring-your-own-key runner",
    ):
        assert required_text in policy


def test_public_entrypoints_link_result_tier_policy() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    run_card_template = (ROOT / "docs" / "run_card_template.md").read_text(
        encoding="utf-8"
    )
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")

    assert "docs/result_tiers.md" in readme
    assert "docs/result_tiers.md" in run_card_template
    assert "result_tiers.md" in docs_index
