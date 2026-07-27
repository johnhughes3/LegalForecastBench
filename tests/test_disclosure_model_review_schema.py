from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_disclosure_review_schema_closes_attempt_and_version_contracts() -> None:
    schema = (ROOT / "docs" / "schemas" / "disclosure-model-review-v1.md").read_text(
        encoding="utf-8"
    )

    for expected in (
        "exactly one raw provider response per authenticated batch-attempt identity",
        "verifier-owned attempt identity",
        "distinct next attempt identity",
        "distinct private raw-response artifact",
        "must never overwrite or replace the first attempt's raw artifact",
        "combine responses across attempts",
        "make either attempt appear to have more than one response",
        "authenticated transport served-version metadata is authoritative",
        "must exactly equal that authenticated served version",
        "rejects the entire batch before any private or public projection",
        "must derive any served-version value from the authenticated "
        "transport evidence",
        "must never trust or copy the model-generated `model_version` field",
        "pure core cannot authenticate or compare transport metadata",
        "does not authorize provider calls, retries, spending, evaluation, "
        "freeze, or dispatch",
    ):
        assert expected in schema
