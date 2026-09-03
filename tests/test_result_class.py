"""Official versus post-anchor supplementary classification.

The property under test is the one integrity guarantee the supplementary lane
must never be able to defeat: a model released after a cycle's corpus decision
window closed can never be published as an official result, whatever a caller,
run card, or sidecar claims about it.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from legalforecast.evals.model_registry import (
    ModelRegistry,
    ModelRegistryEntry,
    ToolPolicy,
    TrainingCutoffStatus,
)
from legalforecast.reporting.contamination_tiers import frozen_result_digest
from legalforecast.reporting.result_class import (
    SUPPLEMENTARY_CAVEAT,
    SUPPLEMENTARY_MARKER,
    ResultClass,
    ResultClassError,
    build_result_class_sidecar,
    classify_registry_entry,
    classify_result_class,
    corpus_anchor_from_decision_dates,
    load_result_class_sidecar,
    require_official_result_classes,
    result_class_marker,
    supplementary_caveat_if_needed,
    supplementary_model_ids,
    write_result_class_sidecar,
)

CORPUS_ANCHOR = date(2026, 6, 26)


def _entry(
    model_id: str,
    *,
    release_timestamp: datetime | None = datetime(2026, 5, 28, tzinfo=UTC),
    provider: str = "fixture",
) -> ModelRegistryEntry:
    return ModelRegistryEntry(
        provider=provider,
        model_id=model_id,
        display_name=model_id,
        model_version_or_snapshot=model_id,
        provider_training_cutoff_status=TrainingCutoffStatus.UNKNOWN,
        max_output_tokens=128_000,
        network_disabled=True,
        search_disabled=True,
        tool_policy=ToolPolicy.CONTROLLED_DOCKET_TOOL_ONLY,
        context_limit=1_000_000,
        pricing_source="fixture",
        input_token_price=1.0,
        output_token_price=2.0,
        release_timestamp=release_timestamp,
        release_timestamp_source=(
            "fixture release note" if release_timestamp is not None else None
        ),
    )


def test_model_released_after_the_corpus_anchor_is_supplementary() -> None:
    assert (
        classify_result_class(
            release_timestamp=datetime(2026, 8, 13, tzinfo=UTC),
            corpus_anchor=CORPUS_ANCHOR,
        )
        is ResultClass.SUPPLEMENTARY_POST_ANCHOR
    )


def test_model_released_on_the_corpus_anchor_stays_official() -> None:
    assert (
        classify_result_class(
            release_timestamp=datetime(2026, 6, 26, tzinfo=UTC),
            corpus_anchor=CORPUS_ANCHOR,
        )
        is ResultClass.OFFICIAL
    )


def test_missing_release_timestamp_fails_closed_to_supplementary() -> None:
    """A model that cannot prove it predates the anchor does not inherit official."""

    assert (
        classify_result_class(release_timestamp=None, corpus_anchor=CORPUS_ANCHOR)
        is ResultClass.SUPPLEMENTARY_POST_ANCHOR
    )


def test_naive_release_timestamp_is_refused() -> None:
    with pytest.raises(ResultClassError, match="timezone-aware"):
        classify_result_class(
            release_timestamp=datetime(2026, 8, 13),
            corpus_anchor=CORPUS_ANCHOR,
        )


def test_post_anchor_model_can_never_be_classed_official() -> None:
    """The fail-closed property: no override path produces an official class."""

    post_anchor = _entry(
        "gemini-3.7-flash",
        release_timestamp=datetime(2026, 8, 13, tzinfo=UTC),
        provider="google",
    )
    assert (
        classify_registry_entry(post_anchor, corpus_anchor=CORPUS_ANCHOR)
        is ResultClass.SUPPLEMENTARY_POST_ANCHOR
    )
    assert supplementary_model_ids([post_anchor], corpus_anchor=CORPUS_ANCHOR) == (
        "google:gemini-3.7-flash",
    )
    with pytest.raises(ResultClassError, match="released after the corpus anchor"):
        require_official_result_classes([post_anchor], corpus_anchor=CORPUS_ANCHOR)


def test_official_entries_pass_the_official_gate() -> None:
    require_official_result_classes(
        [_entry("model-a"), _entry("model-b")],
        corpus_anchor=CORPUS_ANCHOR,
    )


def test_corpus_anchor_is_the_earliest_decision_the_cycle_scores() -> None:
    """Deriving from the corpus, not the models, keeps the check non-vacuous."""

    anchor = corpus_anchor_from_decision_dates(
        [date(2026, 8, 1), date(2026, 6, 26), date(2026, 7, 14)]
    )
    assert anchor == CORPUS_ANCHOR


def test_corpus_anchor_requires_at_least_one_decision_date() -> None:
    with pytest.raises(ResultClassError, match="at least one decision date"):
        corpus_anchor_from_decision_dates([])


def test_supplementary_marker_is_distinct_from_the_contamination_asterisk() -> None:
    """Opus 4.8 already carries '*' for an undisclosed cutoff while staying official."""

    from legalforecast.reporting.contamination_tiers import PRELIMINARY_MARKER

    assert SUPPLEMENTARY_MARKER != PRELIMINARY_MARKER
    assert result_class_marker(ResultClass.SUPPLEMENTARY_POST_ANCHOR) == (
        SUPPLEMENTARY_MARKER
    )
    assert result_class_marker(ResultClass.OFFICIAL) == ""


def test_caveat_appears_only_when_a_supplementary_row_is_present() -> None:
    assert supplementary_caveat_if_needed([ResultClass.OFFICIAL]) is None
    assert (
        supplementary_caveat_if_needed(
            [ResultClass.OFFICIAL, ResultClass.SUPPLEMENTARY_POST_ANCHOR]
        )
        == SUPPLEMENTARY_CAVEAT
    )


def test_sidecar_round_trips_and_binds_to_the_frozen_leaderboard_bytes(
    tmp_path: Path,
) -> None:
    leaderboard_bytes = b'{"rows": []}'
    digest = frozen_result_digest(leaderboard_bytes)
    registry = ModelRegistry(
        (
            _entry("model-a"),
            _entry(
                "gemini-3.7-flash",
                release_timestamp=datetime(2026, 8, 13, tzinfo=UTC),
                provider="google",
            ),
        )
    )
    sidecar = build_result_class_sidecar(
        [
            ("model-a", "fixture:model-a"),
            ("gemini-3.7-flash", "google:gemini-3.7-flash"),
        ],
        result_digest=digest,
        registry=registry,
        corpus_anchor=CORPUS_ANCHOR,
    )
    assert sidecar.result_class_by_model_id() == {
        "model-a": ResultClass.OFFICIAL,
        "gemini-3.7-flash": ResultClass.SUPPLEMENTARY_POST_ANCHOR,
    }
    assert sidecar.authoritative is False

    path = tmp_path / "result-class-sidecar.json"
    write_result_class_sidecar(path, sidecar)
    loaded = load_result_class_sidecar(path, expected_digest=digest)
    assert loaded.result_class_by_model_id() == sidecar.result_class_by_model_id()


def test_sidecar_refuses_a_mismatched_result_digest(tmp_path: Path) -> None:
    digest = frozen_result_digest(b"original")
    path = tmp_path / "result-class-sidecar.json"
    write_result_class_sidecar(
        path,
        build_result_class_sidecar(
            [("model-a", "fixture:model-a")],
            result_digest=digest,
            registry=ModelRegistry((_entry("model-a"),)),
            corpus_anchor=CORPUS_ANCHOR,
        ),
    )
    with pytest.raises(ValueError, match="result_digest does not match"):
        load_result_class_sidecar(
            path, expected_digest=frozen_result_digest(b"tampered")
        )


def test_sidecar_refuses_an_authoritative_claim(tmp_path: Path) -> None:
    """The overlay is presentation; it must never assert authority over rows."""

    path = tmp_path / "result-class-sidecar.json"
    path.write_text(
        json.dumps(
            {
                "authoritative": True,
                "corpus_anchor": CORPUS_ANCHOR.isoformat(),
                "kind": "result_class_sidecar",
                "result_digest": frozen_result_digest(b"x"),
                "rows": [{"model_id": "model-a", "result_class": "official"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="authoritative must be false"):
        load_result_class_sidecar(path, expected_digest=frozen_result_digest(b"x"))
