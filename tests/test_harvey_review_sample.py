"""Behavior of the seeded human-review sample of AI-flagged Harvey LAB criteria."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

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


sampler = _load("harvey_review_sample")


def _rows() -> list[dict[str, object]]:
    return sampler.load(ROOT / sampler.AUDIT_DIR / "comparison.json")["rows"]


def test_lower_bound_matches_published_decision_rule() -> None:
    # Values in human-review/README.md; scipy's hypergeometric agrees.
    assert sampler.lower_bound(835, 25, 10) == 199
    assert sampler.lower_bound(835, 25, 11) == 228
    assert sampler.lower_bound(835, 25, 0) == 0
    assert sampler.threshold(835, 25) == 11


def test_population_is_final_flags_in_stable_order() -> None:
    rows = _rows()
    pop = sampler.population(list(reversed(rows)))
    assert len(pop) == 835
    assert all(r["bucket"] for r in pop)
    assert pop == sampler.population(rows)


def test_draw_is_seeded_and_without_replacement() -> None:
    pop = sampler.population(_rows())
    first = sampler.draw(pop)
    assert first == sampler.draw(pop)
    keys = {(r["task"], r["criterion"]) for r in first}
    assert len(keys) == sampler.SAMPLE_SIZE
    assert sampler.draw(pop, seed=1) != first


def test_committed_sample_matches_seeded_draw() -> None:
    record = sampler.load(ROOT / sampler.REVIEW_DIR / "sample.json")
    drawn = sampler.draw(
        sampler.population(_rows()), record["sample_size"], record["seed"]
    )
    assert [(r["task"], r["criterion"]) for r in record["sample"]] == [
        (r["task"], r["criterion"]) for r in drawn
    ]
    assert record["confirmed_needed"] == 11


def test_worksheet_item_round_trips_through_parser() -> None:
    row = {
        "task": "draft-complaint",
        "criterion": "C-004",
        "bucket": "split",
        "gpt_6_sol": "arguable",
        "claude_opus_5_5": "problematic",
        "sol_findings": ["Sol reason"],
        "opus_findings": ["Opus reason"],
    }
    record = {"title": "Draft Complaint", "criterion_lines": {"C-004": 41}}
    criterion = {
        "title": "Names the court",
        "match_criteria": "PASS if...\n\nFAIL if...",
    }
    text = "\n".join(sampler.render_item(1, row, record, criterion))
    text = text.replace(
        "- **Verdict:** _(Defective / Arguable / Not defective / Unresolved)_",
        "- **Verdict:** Defective",
    )
    assert sampler.parse_worksheet(text) == [
        (
            "draft-complaint",
            "C-004",
            "Defective",
            "_(Correct / Partly correct / Wrong)_",
        )
    ]


runs = _load("harvey_model_runs")


def test_published_runs_cover_every_task_and_criterion() -> None:
    tasks = sorted(p.name for p in (ROOT / sampler.AUDIT_DIR / "tasks").iterdir())
    for task in tasks:
        total = sampler.load(
            ROOT / sampler.AUDIT_DIR / "tasks" / task / "claude-opus-5-5-audit.json"
        )["criteria_total"]
        for slug, *_ in runs.CONDITIONS:
            folder = ROOT / runs.run_dir(task, slug)
            assert (folder / "README.md").exists()
            assert any((folder / "output").iterdir())
            for judge, _label in runs.JUDGES:
                score = sampler.load(folder / f"scores_{judge}.json")
                assert len(runs.results_by_criterion(score)) == total


def test_run_grades_match_the_archived_judgments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sonnet passed Luna on C-003 by quoting the facts section; GPT-5.5 failed it.
    monkeypatch.chdir(ROOT)
    task = "draft-defective-industrial-equipment-product-liability"
    assert runs.run_grades(task, "C-003", "../../").startswith("Luna [P/F](")
    assert "Opus [F/F](" in runs.run_grades(task, "C-003", "../../")


def test_runs_block_is_idempotent_and_keeps_verdicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(ROOT)
    text = (sampler.REVIEW_DIR / "worksheet.md").read_text(encoding="utf-8")
    once = sampler.add_runs(text.replace("- **Verdict:** _(", "- **Verdict:** X_(", 1))
    assert sampler.add_runs(once) == once
    parsed = sampler.parse_worksheet(once)
    assert len(parsed) == sampler.SAMPLE_SIZE
    assert parsed[0][2].startswith("X_(")
    assert once.count(sampler.RUNS_START) == sampler.SAMPLE_SIZE


def test_import_rejects_grades_for_the_wrong_criteria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(ROOT)
    task = "draft-complaint"
    for slug, *_ in runs.CONDITIONS:
        src = tmp_path / task / slug / "run"
        (src / "output").mkdir(parents=True)
        for judge, _label in runs.JUDGES:
            published = ROOT / runs.run_dir(task, slug) / f"scores_{judge}.json"
            (src / published.name).write_text(published.read_text(encoding="utf-8"))
    assert set(runs.source_runs(tmp_path, [task])) == {
        (task, slug) for slug, *_ in runs.CONDITIONS
    }
    first = tmp_path / task / runs.CONDITIONS[0][0] / "run"
    score = first / f"scores_{runs.JUDGES[0][0]}.json"
    score.write_text(score.read_text(encoding="utf-8").replace('"C-001"', '"C-999"'))
    with pytest.raises(SystemExit, match="grades other criteria"):
        runs.source_runs(tmp_path, [task])
