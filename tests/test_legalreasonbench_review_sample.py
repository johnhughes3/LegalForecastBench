"""Behavior of the seeded human-review sample of flagged LegalReasonBench criteria."""

from __future__ import annotations

import importlib.util
import random
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load(name: str) -> ModuleType:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sampler = _load("legalreasonbench_review_sample")


def _comparison() -> dict[str, Any]:
    return sampler.load(ROOT / sampler.AUDIT / "comparison.json")


def _rows() -> list[dict[str, Any]]:
    return _comparison()["rows"]


def _complete(verdict: str, **extra: str) -> dict[str, str]:
    review = {
        "Rubric verdict": verdict,
        "AI reasoning": "Correct",
        "Environment": "Correct",
        "Note and source locator": "Reason; Doc p. 1.",
    }
    review.update(extra)
    return {label: review.get(label, "") for label in sampler.FIELDS}


def _sample(n: int = 25) -> list[dict[str, object]]:
    return [
        {
            "task": f"t{i % 3}",
            "criterion": f"c{i}",
            "bucket": "split",
            "reconciliation": None,
        }
        for i in range(n)
    ]


def test_population_is_the_union_of_blind_flags_in_stable_order() -> None:
    rows = _rows()
    pop = sampler.population(rows)
    assert len(pop) == 63
    assert pop == sampler.population(list(reversed(rows)))
    assert [sampler.key(r) for r in pop] == sorted(sampler.key(r) for r in pop)
    assert all(r["bucket"] for r in pop)
    assert (
        Counter(r["bucket"] for r in pop) == _comparison()["blind_agreement"]["buckets"]
    )
    # Reconciliation is metadata: the 27 criteria it did not retain stay eligible.
    assert Counter(r["reconciliation"] for r in pop) == {
        None: 27,
        "arguable": 23,
        "problematic": 13,
    }
    assert sum(1 for r in rows if r["reconciliation"]) == 36


def test_population_deduplicates_pairs_and_rejects_conflicts() -> None:
    rows = _rows()
    flagged = next(r for r in rows if r["bucket"] == "sol_only")
    assert len(sampler.population([*rows, dict(flagged)])) == 63
    conflict = {**flagged, "gpt_6_sol": "arguable", "reconciliation": "problematic"}
    with pytest.raises(ValueError, match="conflicting rows"):
        sampler.population([*rows, conflict])


def test_draw_is_seeded_simple_random_sampling_without_replacement() -> None:
    pop = sampler.population(_rows())
    first = sampler.draw(pop)
    assert sampler.SEED == 20261024
    assert first == sampler.draw(pop)
    assert first == random.Random(20261024).sample(pop, 25)
    assert len({sampler.key(r) for r in first}) == sampler.SAMPLE_SIZE
    assert sampler.draw(pop, seed=1) != first


def test_lower_bound_is_exact_hypergeometric_for_this_population() -> None:
    # Independently computed with scipy.stats.hypergeom for N=63, n=25.
    expected = {0: 0, 1: 1, 5: 7, 10: 17, 13: 24, 20: 42, 25: 58}
    assert {x: sampler.lower_bound(63, 25, x) for x in expected} == expected


def test_blank_placeholders_parse_as_blank_and_never_complete() -> None:
    review = sampler.parse_review(sampler.blank_review())
    assert set(review.values()) == {""}
    lines, complete = sampler.summary(_sample(), [review] * 25, 63)
    assert not complete
    assert "complete 0" in lines[0]
    assert lines[-1].startswith("No estimate: 25 of 25 items are incomplete")


def test_invalid_or_partial_fields_keep_an_item_incomplete() -> None:
    assert sampler.problems(_complete("Maybe")) == [
        "Rubric verdict not one of Defective / Arguable / Not defective / Unresolved"
    ]
    assert sampler.problems(_complete("Defective")) == [
        "Defect basis (Defective only) blank",
        "Defect arises from environment (Defective only) blank",
    ]
    assert sampler.problems(_complete("Arguable", Environment="Defective")) == [
        "Environment explanation blank"
    ]
    assert sampler.problems(_complete("Not defective")) == []
    reviews = [_complete("Arguable")] * 24 + [
        _complete("Arguable", **{"AI reasoning": ""})
    ]
    lines, complete = sampler.summary(_sample(), reviews, 63)
    assert not complete
    assert "  Item 25 incomplete: AI reasoning blank." in lines


def test_multiline_note_is_read_until_the_next_field() -> None:
    block = "\n".join(
        [
            sampler.REVIEW_START,
            "- **Rubric verdict:** Arguable",
            "- **Note and source locator:**",
            "- First reason, Order p. 2.",
            "  continued.",
            "- **Environment:** Correct",
            sampler.REVIEW_END,
        ]
    )
    review = sampler.parse_review(block)
    assert (
        review["Note and source locator"] == "- First reason, Order p. 2.\n  continued."
    )
    assert review["Environment"] == "Correct"
    assert review["AI reasoning"] == ""


def test_estimate_counts_only_defective_with_others_in_denominator() -> None:
    objective = {
        "Defect basis (Defective only)": "Unambiguous objective error",
        "Defect arises from environment (Defective only)": "Yes",
    }
    judgment = {
        "Defect basis (Defective only)": "Professional judgment",
        "Defect arises from environment (Defective only)": "No",
    }
    reviews = (
        [_complete("Defective", **objective)] * 4
        + [_complete("Defective", **judgment)] * 6
        + [_complete("Arguable")] * 5
        + [_complete("Not defective")] * 5
        + [_complete("Unresolved")] * 5
    )
    lines, complete = sampler.summary(_sample(), reviews, 63)
    assert complete
    assert (
        "Rubric verdicts: Defective 10, Arguable 5, Not defective 5, Unresolved 5"
        in lines
    )
    assert any("arising from the environment 4" in line for line in lines)
    assert lines[-2] == (
        "Defective 10 of 25 (40%); estimated 25 of the 63 flagged criteria; exact "
        "one-sided 95% hypergeometric lower bound 17 of 63."
    )
    assert lines[-1].startswith("Secondary: unambiguous objective errors 4 of 25")


def test_every_flagged_criterion_renders_with_blank_review_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    pop = sampler.population(_rows())
    record = {
        "sample_size": len(pop),
        "population_size": len(pop),
        "seed": sampler.SEED,
        "sample": [{**r, "rubric_line": 7} for r in pop],
    }
    text = sampler.render_worksheet(record, pop)
    items = sampler.split_items(text)
    assert [k for k, _ in items] == [sampler.key(r) for r in pop]
    assert {b for _, b in items} == {sampler.blank_review()}
    for row in pop:
        assert sampler.blockquote(row["criterion_text"]) in text
    assert text.count("<details><summary>Blind AI findings</summary>") == len(pop)
    assert text.count("<details><summary>Later reconciliation") == len(pop)
    assert "for this criterion" in text  # a mixed reconciliation ruling
    assert text.count(sampler.REAL_CASE_LABEL) == len(pop)


def test_every_flagged_matter_has_a_real_world_basis_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    matters = {
        sampler.task_inputs(r["task"])["matter_id"] for r in sampler.population(_rows())
    }
    cases = sampler.load(sampler.REAL_CASES)
    assert set(cases) == matters
    assert all(isinstance(v, str) and v.strip() for v in cases.values())


def test_render_copies_reviewer_fields_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    row = sampler.population(_rows())[0]
    record = {
        "sample_size": 1,
        "population_size": 63,
        "seed": sampler.SEED,
        "sample": [{**row, "rubric_line": 7}],
    }
    filled = sampler.blank_review().replace(
        "- **Note and source locator:**",
        "- **Note and source locator:** Human note.\n- Second line.",
    )
    once = sampler.render_worksheet(record, [row], {sampler.key(row): filled})
    assert sampler.split_items(once) == [(sampler.key(row), filled)]
    reviews = {k: b for k, b in sampler.split_items(once)}
    assert sampler.render_worksheet(record, [row], reviews) == once


@pytest.mark.parametrize("existing", ["sample.json", "worksheet.md"])
def test_draw_refuses_to_overwrite_a_prior_draw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: str
) -> None:
    monkeypatch.setattr(sampler, "REVIEW_DIR", tmp_path)

    def offline() -> str:
        raise AssertionError("draw must refuse before any network access")

    monkeypatch.setattr(sampler, "current_revision", offline)
    (tmp_path / existing).write_text("reviewer verdicts", encoding="utf-8")
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        sampler.cmd_draw()
    assert (tmp_path / existing).read_text(encoding="utf-8") == "reviewer verdicts"


def test_committed_sample_is_the_protocol_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    record, sample = sampler.frozen_sample()
    pop = sampler.population(_rows())
    assert record["population_size"] == 63
    assert record["ordering"] == sampler.ORDERING
    assert record["method"] == sampler.METHOD
    assert record["dataset_revision_check"]["matches_pinned_revision"]
    assert [sampler.key(r) for r in sample] == sorted(
        sampler.key(r) for r in random.Random(20261024).sample(pop, 25)
    )


def test_committed_worksheet_is_current_and_not_tallied_while_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(ROOT)
    record, sample = sampler.frozen_sample()
    blocks = sampler.checked_reviews(sample)
    reviews = {sampler.key(r): b for r, b in zip(sample, blocks, strict=True)}
    text = (sampler.REVIEW_DIR / "worksheet.md").read_text(encoding="utf-8")
    assert sampler.render_worksheet(record, sample, reviews) == text
    incomplete = [b for b in blocks if sampler.problems(sampler.parse_review(b))]
    if not incomplete:
        pytest.skip("every item is complete; the tally test no longer applies")
    with pytest.raises(SystemExit) as exit_info:
        sampler.cmd_tally()
    assert exit_info.value.code == 1
    out = capsys.readouterr().out
    assert f"No estimate: {len(incomplete)} of 25 items are incomplete" in out
