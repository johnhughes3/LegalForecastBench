from __future__ import annotations

from pathlib import Path

REQUIRED_EDGE_CLASSES = (
    "Rule 12(b)(1)",
    "Rule 12(b)(2)",
    "Rule 12(b)(6)",
    "Rule 12(c)",
    "Arbitration or stay orders",
    "Venue",
    "Transfer",
    "Forum non conveniens",
    "Personal jurisdiction",
    "Anti-SLAPP",
    "Report and recommendation adoption",
    "Mixed MTD/MSJ orders",
    "Voluntary withdrawal",
    "Mootness",
    "Dismissal without prejudice",
    "Partial theory dismissal",
    "Generic granted-in-part orders",
    "Successive amended complaints",
    "Multiple motions resolved in one order",
)


def test_outcome_rules_appendix_covers_required_edge_classes() -> None:
    appendix = Path("docs/outcome_rules_appendix.md").read_text(encoding="utf-8")

    assert (
        "| Edge-case class | Rule | Rationale | Route | Example / pilot status |"
        in (appendix)
    )
    assert "## Amendment Track" in appendix
    assert "## Pilot Follow-Up Requirements" in appendix
    assert "zero live clean packets" in appendix
    assert "Unobserved in v1 live pilot" in appendix
    assert "Search-only candidate IDs must stay out of this appendix." in appendix
    assert "Placeholder:" not in appendix
    assert "replace with first" not in appendix

    missing = [
        edge_class for edge_class in REQUIRED_EDGE_CLASSES if edge_class not in appendix
    ]

    assert missing == []
