"""Extraction and counting boundaries unique to the LegalReasonBench audit."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

extractor = importlib.import_module("legalreasonbench_extract")
reporter = importlib.import_module("legalreasonbench_report")
renderer = importlib.import_module("legalreasonbench_render")
citations = importlib.import_module("legalreasonbench_citations")


def finding(
    fid: str, status: str, category: str, criteria: list[str]
) -> dict[str, Any]:
    return {
        "id": fid,
        "status": status,
        "category": category,
        "criteria": criteria,
        "title": "Rubric issue",
        "explanation": "Explanation",
        "evidence": [{"source": "instruction.md", "quote": "Source text"}],
        "authorities": [],
    }


def save(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def setup_task(root: Path, task: str = "matter-assignment-1") -> Path:
    save(
        root / "in-scope.json",
        {
            "dataset": extractor.DATASET,
            "revision": extractor.REVISION,
            "tasks": [
                {
                    "task": task,
                    "criteria_total": 2,
                    "in_scope": True,
                    "penalty_count": 1,
                    "scope_reason": "litigation",
                }
            ],
        },
    )
    directory = root / "tasks" / task
    save(
        directory / "input.json",
        {
            "rubric": [
                {"criterion_id": "c1", "criterion": "First", "polarity": "required"},
                {"criterion_id": "c2", "criterion": "Second", "polarity": "penalty"},
            ]
        },
    )
    return directory


def blind(task: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task": task,
        "criteria_total": 2,
        "model": "test-model",
        "reasoning_effort": "high",
        "coverage": "Both criteria read",
        "findings": findings,
    }


def test_blind_buckets_ignore_reconciliation_and_deduplicate(tmp_path: Path) -> None:
    task = setup_task(tmp_path)
    sol = [
        finding("s1", "arguable", "legal_error", ["c1"]),
        finding("s2", "problematic", "legal_error", ["c1"]),
        finding("s3", "problematic", "source_conflict", ["c1"]),
    ]
    opus = [finding("o1", "arguable", "legal_error", ["c1"])]
    save(task / "gpt-6-sol-audit.json", blind(task.name, sol))
    save(task / "claude-opus-5-5-audit.json", blind(task.name, opus))
    save(
        task / "reconciliation.json",
        {
            "model": "reviewer",
            "reasoning_effort": "high",
            "verdicts": [],
            "findings": [finding("r1", "problematic", "legal_error", ["c2"])],
        },
    )
    result, _ = reporter.compare(tmp_path)
    assert result["blind_agreement"]["buckets"]["split"] == 1
    assert result["blind_agreement"]["flagged_criteria"] == 1
    assert result["blind_agreement"]["unflagged_criteria"] == 1
    assert result["rows"][1]["bucket"] is None
    assert result["rows"][1]["reconciliation"] == "problematic"
    counts = result["report_counts"]["gpt_6_sol"]
    assert counts["findings"] == 3
    assert counts["flagged_criteria"] == 1
    assert counts["categories"]["legal_error"]["flagged_criteria"] == 1
    assert counts["categories"]["legal_error"]["problematic"] == 1
    assert counts["categories"]["legal_error"]["arguable"] == 0
    assert counts["categories"]["source_conflict"]["flagged_criteria"] == 1


def test_missing_report_is_unavailable_not_zero_or_one_model_bucket(
    tmp_path: Path,
) -> None:
    task = setup_task(tmp_path)
    save(task / "gpt-6-sol-audit.json", blind(task.name, []))
    result, _ = reporter.compare(tmp_path)
    assert result["report_counts"]["gpt_6_sol"]["flagged_criteria"] == 0
    assert result["report_counts"]["claude_opus_5_5"]["flagged_criteria"] is None
    assert result["blind_agreement"]["flagged_criteria"] is None
    assert result["blind_agreement"]["buckets"]["sol_only"] is None
    assert result["rows"][0]["claude_opus_5_5_findings"] is None
    assert result["rows"][0]["gpt_6_sol_findings"] == []
    save(
        task / "gpt-6-sol-audit.json",
        blind(
            task.name,
            [
                finding("s1", "problematic", "legal_error", ["c1"]),
            ],
        ),
    )
    result, _ = reporter.compare(tmp_path)
    assert result["report_counts"]["gpt_6_sol"]["flagged_criteria"] == 1
    assert result["rows"][0]["bucket"] is None


def test_harvey_comparison_uses_json_categories_and_discloses_limit(
    tmp_path: Path,
) -> None:
    out = tmp_path / "lrb"
    setup_task(out)
    harvey = tmp_path / "harvey"
    save(
        harvey / "comparison.json",
        {
            "rows": [
                {"task": "h", "criterion": "C-001", "bucket": "both_arguable"},
            ]
        },
    )
    save(
        harvey / "gpt-6-sol/index.json",
        {
            "tasks": [
                {"task": "h", "criteria_total": 3},
            ]
        },
    )
    save(
        harvey / "tasks/h/claude-opus-5-5-audit.json",
        {
            "final": {
                "findings": [
                    finding("h1", "arguable", "legal_error", ["C-001"]),
                    finding("h2", "problematic", "legal_error", ["C-001"]),
                ]
            }
        },
    )
    save(harvey / "citation-check/summary.json", {"problems": 2, "checked": 5})
    renderer.render(out, harvey)
    data = json.loads((out / "comparison-to-harvey.json").read_text())
    assert "not directly comparable" in data["comparability_limit"]
    assert data["harvey"]["criteria_total"] == 3
    assert (
        data["harvey"]["final_opus"]["categories"]["legal_error"]["flagged_criteria"]
        == 1
    )
    assert data["legalreasonbench"]["final_reconciliation"]["flagged_criteria"] is None
    markdown = (out / "comparison-to-harvey.md").read_text()
    assert "1 / 3 (33.3%)" in markdown
    assert "| legal_error | 1 / 3 (33.3%) | unavailable |" in markdown
    assert "| Harvey | 2 / 5 (40.0%) |" in markdown
    assert "| LegalReasonBench | unavailable; coverage or checks pending |" in markdown
    assert "different counting units" in markdown
    assert "verified error rate" in markdown and "score corrections" in markdown
    renderer.harvey_comparison(
        out,
        json.loads((out / "comparison.json").read_text()),
        harvey,
        {
            "complete": False,
            "checked": 4,
            "observed_final_problems": 1,
            "observed_problem_rate": 0.25,
        },
    )
    assert (
        "1 / 4 (25.0%) among recorded citations; coverage incomplete"
        in (out / "comparison-to-harvey.md").read_text()
    )


def test_report_rejects_wrong_denominator_and_unknown_criteria(tmp_path: Path) -> None:
    task = setup_task(tmp_path)
    data = blind(task.name, [finding("s1", "arguable", "legal_error", ["missing"])])
    save(task / "gpt-6-sol-audit.json", data)
    with pytest.raises(ValueError, match="Unknown criterion"):
        reporter.compare(tmp_path)
    data["findings"] = []
    data["criteria_total"] = 3
    save(task / "gpt-6-sol-audit.json", data)
    with pytest.raises(ValueError, match="denominator mismatch"):
        reporter.compare(tmp_path)


def test_render_is_reproducible_and_preserves_blind_json(tmp_path: Path) -> None:
    task = setup_task(tmp_path)
    data = blind(task.name, [finding("s1", "arguable", "legal_error", ["c1"])])
    data["coverage"] = "Read source; email writer@example.invalid"
    path = task / "gpt-6-sol-audit.json"
    save(path, data)
    before = path.read_bytes()
    renderer.render(tmp_path, tmp_path / "no-harvey")
    first = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    renderer.render(tmp_path, tmp_path / "no-harvey")
    second = {
        p.relative_to(tmp_path): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    assert first == second
    assert path.read_bytes() == before
    assert "[email redacted]" in path.with_suffix(".md").read_text()
    assert "unavailable" in (tmp_path / "comparison.md").read_text()
    assert "Final reconciliation" in (task / "README.md").read_text()


@pytest.mark.parametrize("use_index", [False, True])
def test_sequential_extraction_carries_prompts_and_attachments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    use_index: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    (upstream / "first.docx").write_bytes(b"data only")
    (upstream / "excluded.pdf").write_bytes(b"not extracted")
    rows: list[dict[str, Any]] = []
    for assignment in (1, 2):
        rows.append(
            {
                "matter_id": "matter",
                "matter_title": "Title",
                "assignment": assignment,
                "assignment_title": "Assignment",
                "prompt": f"Prompt {assignment} writer@example.invalid",
                "rubric_count": 1,
                "penalty_count": 1,
                "rubric": json.dumps(
                    [
                        {
                            "criterion_id": "c1",
                            "criterion": "Criterion",
                            "polarity": "penalty",
                        }
                    ]
                ),
                "attachments": ["first.docx"] if assignment == 1 else [],
                "instruction_path": (
                    f"tasks/matter/assignment-{assignment}/instruction.md"
                ),
                "rubric_path": "tasks/matter/rubric.json",
            }
        )
    excluded = dict(rows[0], matter_id=extractor.EXCLUDED, attachments=["excluded.pdf"])
    all_rows = [*rows, excluded]
    for r in rows:
        instruction = upstream / r["instruction_path"]
        instruction.parent.mkdir(parents=True, exist_ok=True)
        instruction.write_text(
            "Use `/app/attachments/a file.pdf`; writer@example.invalid"
        )
    save(
        tmp_path / "rows.json",
        {
            "dataset": extractor.DATASET,
            "revision": extractor.REVISION,
            "rows": all_rows,
        }
        if use_index
        else all_rows,
    )
    save(
        tmp_path / "api.json",
        {"sha": extractor.REVISION, "cardData": {"license": "cc-by-4.0"}},
    )
    converted: list[str] = []

    def convert(path: Path) -> str:
        converted.append(path.name)
        return "Body writer@example.invalid"

    monkeypatch.setattr(extractor, "attachment_text", convert)
    out = tmp_path / "out"
    extractor.extract(tmp_path / "rows.json", tmp_path / "api.json", upstream, out)
    second = json.loads((out / "tasks/matter-assignment-2/input.json").read_text())
    assert second["prior_prompts"][0]["prompt"] == "Prompt 1 [email redacted]"
    assert len(second["attachments"]) == 1
    assert converted == ["first.docx"]
    attachment = (
        out / "tasks/matter-assignment-2" / second["attachments"][0]["extracted_path"]
    )
    assert "Body [email redacted]" in attachment.read_text()
    assert extractor.REVISION in attachment.read_text()
    source = json.loads((out / "source-index.json").read_text())
    assert len(source["rows"]) == 3
    assert isinstance(source["rows"][0]["rubric"], list)
    native = (out / "tasks/matter-assignment-2/upstream-instruction.md").read_text()
    assert "attachments/a file.pdf" in native
    assert "/app/" not in native and "[email redacted]" in native
    assert "Source: " + extractor.upstream_url(rows[1]["instruction_path"]) in native
    census = out / "in-scope.json"
    census.write_text('{"owner_scope": true}')
    extractor.extract(tmp_path / "rows.json", tmp_path / "api.json", upstream, out)
    assert json.loads(census.read_text()) == {"owner_scope": True}


def test_pdf_retains_blank_page_boundaries(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "blank.pdf"
    writer.write(path)
    text = extractor.pdf_text(path)
    assert "## PDF page 1" in text and "## PDF page 2" in text
    assert text.count("No extractable text") == 2


def test_upstream_paths_are_pinned_and_cannot_escape() -> None:
    assert f"/resolve/{extractor.REVISION}/" in extractor.upstream_url(
        "tasks/a file.pdf", raw=True
    )
    assert "a%20file.pdf" in extractor.upstream_url("tasks/a file.pdf")
    for path in (
        "/tmp/file",
        "../file",
        "tasks/../file",
        "tasks\\file",
        "https://evil.invalid/file",
        "//evil.invalid/file",
        "%2e%2e/file",
        "tasks/%2e%2e/file",
        "tasks/%5cfile",
    ):
        with pytest.raises(ValueError, match="Unsafe upstream path"):
            extractor.upstream_url(path)


def checked_citation(
    ref: str, status: str = "VERIFIED", *, fictional: bool = False
) -> dict[str, Any]:
    return {
        "ref": ref,
        "document": "authority.pdf",
        "location": "PDF page 1",
        "authority_type": "case",
        "authority": "Fixture authority",
        "citation_as_written": "Fixture citation",
        "pincite": "1",
        "cited_for": "Fixture proposition",
        "quotes": ["Fixture quote"],
        "context": "Fixture context",
        "fictional_by_design": fictional,
        "fictional_reason": "Planted exercise" if fictional else "",
        "first_check": {
            "status": status,
            "explanation": "Fixture finding",
            "source_urls": ["https://example.invalid/authority"],
            "excerpt_read": "Fixture source excerpt",
        },
    }


def save_citations(
    root: Path, rows: list[dict[str, Any]], limits: list[str] | None = None
) -> Path:
    path = root / "citation-check/results/matter.json"
    save(
        path,
        {
            "matter": "matter",
            "dataset_revision": extractor.REVISION,
            "model": "fixture-model",
            "reasoning_effort": "high",
            "coverage": {
                "files_read": ["authority.pdf"],
                "census_complete": not bool(limits),
                "limits": limits or [],
                "counting_unit": "unique matter document citations",
            },
            "citations": rows,
        },
    )
    return path


def test_citations_pending_second_check_and_real_dedup_counts(tmp_path: Path) -> None:
    setup_task(tmp_path)
    good = checked_citation("good")
    planted = checked_citation("planted", fictional=True)
    planted.pop("first_check")
    problem = checked_citation("problem", "MISQUOTED")
    source = save_citations(tmp_path, [good, good, planted, problem])
    original = source.read_bytes()
    summary, rows = citations.citation_summary(tmp_path)
    assert summary["citation_instances"] == 3
    assert summary["checked"] == 2
    assert summary["fictional_by_design"] == 1
    assert summary["pending_checks"] == 1
    assert summary["problems"] is None and summary["problem_rate"] is None
    assert summary["by_final_status"]["MISQUOTED"] == 0
    assert summary["complete"] is False
    assert summary["observed_problem_rate"] is None
    pages = citations.citation_pages(summary, rows)
    assert "Second check: pending" in "\n".join(
        pages[Path("citation-check/results/matter.md")]
    )
    assert source.read_bytes() == original
    problem["second_check"] = {
        "revised_status": "VERIFIED",
        "explanation": "Overturned",
        "source_urls": [],
        "excerpt_read": "Read",
        "model": "second",
        "reasoning_effort": "high",
    }
    save_citations(tmp_path, [good, good, planted, problem])
    summary, rows = citations.citation_summary(tmp_path)
    assert summary["complete"] is True
    assert summary["problems"] == 0 and summary["problem_rate"] == 0
    assert summary["by_final_status"]["VERIFIED"] == 2
    problems = "\n".join(
        citations.citation_pages(summary, rows)[Path("citation-check/problems.md")]
    )
    assert "MISQUOTED | VERIFIED | Overturned" in problems
    problem["second_check"]["revised_status"] = "MISQUOTED"
    save_citations(tmp_path, [good, good, planted, problem])
    summary, _ = citations.citation_summary(tmp_path)
    assert summary["problems"] == 1 and summary["problem_rate"] == 0.5


def test_worker_limits_and_missing_matters_prevent_complete_rate(
    tmp_path: Path,
) -> None:
    setup_task(tmp_path)
    save_citations(tmp_path, [checked_citation("a")], ["Tables not inspected"])
    summary, rows = citations.citation_summary(tmp_path)
    assert summary["complete"] is False and summary["problem_rate"] is None
    assert summary["checked"] == 1
    assert summary["observed_problem_rate"] == 0
    assert "coverage incomplete" in "\n".join(
        citations.citation_pages(summary, rows)[Path("citation-check/README.md")]
    )
    assert "Tables not inspected" in "\n".join(
        citations.citation_pages(summary, rows)[Path("citation-check/README.md")]
    )
    (tmp_path / "citation-check/results/matter.json").unlink()
    summary, _ = citations.citation_summary(tmp_path)
    assert summary["checked"] is None and summary["problems"] is None
    assert summary["matters_available"] == 0
    assert summary["observed_problem_rate"] is None
    assert summary["per_matter"][0]["coverage"] is None


def test_completed_census_can_disclose_verification_limits(tmp_path: Path) -> None:
    setup_task(tmp_path)
    path = save_citations(
        tmp_path,
        [checked_citation("a", "UNABLE_TO_VERIFY")],
        ["Historical text unavailable"],
    )
    report = json.loads(path.read_text())
    report["coverage"]["census_complete"] = True
    save(path, report)
    summary, rows = citations.citation_summary(tmp_path)
    assert summary["complete"] is True
    assert summary["problem_rate"] == 0
    assert summary["by_final_status"]["UNABLE_TO_VERIFY"] == 1
    assert "Historical text unavailable" in "\n".join(
        citations.citation_pages(summary, rows)[Path("citation-check/README.md")]
    )
    report["coverage"].pop("census_complete")
    save(path, report)
    summary, _ = citations.citation_summary(tmp_path)
    assert summary["complete"] is False and summary["problem_rate"] is None


def test_citation_status_and_conflicting_duplicate_rejected(tmp_path: Path) -> None:
    setup_task(tmp_path)
    save_citations(tmp_path, [checked_citation("a", "INVENTED_STATUS")])
    with pytest.raises(ValueError, match="Unknown citation status"):
        citations.citation_summary(tmp_path)
    save_citations(
        tmp_path, [checked_citation("a"), checked_citation("a", "MISQUOTED")]
    )
    with pytest.raises(ValueError, match="Conflicting citation ref"):
        citations.citation_summary(tmp_path)
    incomplete = checked_citation("a", "MISQUOTED")
    incomplete["second_check"] = {"revised_status": "VERIFIED"}
    save_citations(tmp_path, [incomplete])
    with pytest.raises(ValueError, match="Incomplete second check"):
        citations.citation_summary(tmp_path)


def test_fictional_authority_problem_is_excluded_from_problem_outputs(
    tmp_path: Path,
) -> None:
    setup_task(tmp_path)
    save_citations(
        tmp_path, [checked_citation("scenario", "MISQUOTED", fictional=True)]
    )
    summary, rows = citations.citation_summary(tmp_path)
    assert summary["first_check_problems"] == 0
    assert summary["pending_checks"] == 0
    intent = citations.rubric_intent(tmp_path, summary, rows)
    assert intent["first_check_problems_without_intent"] == []
    pages = citations.citation_pages(summary, rows)
    assert "scenario" not in "\n".join(pages[Path("citation-check/problems.md")])
    assert "scenario" in "\n".join(pages[Path("citation-check/results/matter.md")])


def test_intent_carries_saved_judgments_and_requires_problem_mapping(
    tmp_path: Path,
) -> None:
    setup_task(tmp_path)
    problem = checked_citation("a", "MISQUOTED")
    problem["second_check"] = {
        "revised_status": "VERIFIED",
        "explanation": "Overturned",
        "source_urls": [],
        "excerpt_read": "Read",
        "model": "second",
        "reasoning_effort": "high",
    }
    save_citations(tmp_path, [problem])
    summary, rows = citations.citation_summary(tmp_path)
    missing = citations.rubric_intent(tmp_path, summary, rows)
    assert missing["complete"] is False
    assert missing["records_available"] is None
    judgment = {
        "ref": "a",
        "targeted_by_instructions": True,
        "targeted_by_criteria": ["c1"],
        "rewards_reliance": [],
        "explanation": "Solver is instructed to detect it",
    }
    save(
        tmp_path / "citation-check/intent/matter.json",
        {"matter": "matter", "records": [judgment]},
    )
    result = citations.rubric_intent(tmp_path, summary, rows)
    assert result["complete"] is True
    assert result["records"][0]["explanation"] == judgment["explanation"]
    assert result["records"][0]["first_check_status"] == "MISQUOTED"
    assert result["records"][0]["final_status"] == "VERIFIED"
    assert result["targeted_by_instructions"] == 1 and result["rewards_reliance"] == 0


def test_render_indexes_every_markdown_and_preserves_parent_prose(
    tmp_path: Path,
) -> None:
    task = setup_task(tmp_path)
    original = (
        "Parent prose stays exact.\n\n<!-- file-index:start -->\nold\n"
        "<!-- file-index:end -->\nTail.\n"
    )
    (tmp_path / "README.md").write_text(original)
    (task / "a file's (record).md").write_text("Source")
    renderer.render(tmp_path, tmp_path / "absent-harvey")
    readme = (tmp_path / "README.md").read_text()
    assert readme.startswith("Parent prose stays exact.\n\n<!-- file-index:start -->")
    assert readme.endswith("<!-- file-index:end -->\nTail.\n")
    assert "a%20file%27s%20%28record%29.md" in readme
    import re

    links = {unquote(link) for link in re.findall(r"\]\(([^)]+)\)", readme)}
    assert links == {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.md")}
    assert (
        "[Native upstream instructions](upstream-instruction.md)"
        in (task / "README.md").read_text()
    )
    assert not list((tmp_path / "citation-check/results").glob("*.json"))
    assert "unavailable" in (tmp_path / "citation-check/README.md").read_text()
    assert (tmp_path / "citation-check/rubric-intent.json").exists()


def test_extraction_downloads_instructions_counts_equal_bytes_and_encodes_links(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    for name in ("a file.docx", "same.docx"):
        (upstream / name).write_bytes(b"equal attachment bytes")
    row: dict[str, Any] = {
        "matter_id": "matter",
        "assignment": 1,
        "assignment_title": "Title",
        "prompt": "Prompt",
        "rubric": [],
        "rubric_count": 0,
        "penalty_count": 0,
        "attachments": ["a file.docx", "same.docx"],
        "instruction_path": "tasks/matter/instruction.md",
        "rubric_path": "rubric.json",
    }
    save(tmp_path / "rows.json", [row])
    save(
        tmp_path / "api.json",
        {"sha": extractor.REVISION, "cardData": {"license": "cc-by-4.0"}},
    )
    from io import BytesIO

    downloaded: list[str] = []

    def download(url: str, timeout: int) -> BytesIO:
        downloaded.append(url)
        assert timeout > 0
        return BytesIO(b"Use /app/attachments/ and /app/response1.md")

    monkeypatch.setattr(extractor.urllib.request, "urlopen", download)

    def convert(path: Path) -> str:
        assert path.suffix == ".docx"
        return "Extracted fixture text"

    monkeypatch.setattr(extractor, "attachment_text", convert)
    out = tmp_path / "out"
    extractor.extract(tmp_path / "rows.json", tmp_path / "api.json", upstream, out)
    assert downloaded == [extractor.upstream_url(row["instruction_path"], raw=True)]
    assert (upstream / row["instruction_path"]).exists()
    counts = json.loads((out / "source-index.json").read_text())["attachment_counts"]
    assert counts["attachment_paths_total"] == 2
    assert counts["distinct_attachment_contents_total"] == 1
    assert counts["distinct_attachment_contents_in_scope"] == 1
    assert (
        "a%20file.docx.md"
        in (out / "tasks/matter-assignment-1/instruction.md").read_text()
    )
    save(
        tmp_path / "rows.json",
        {"dataset": extractor.DATASET, "revision": "wrong", "rows": [row]},
    )
    with pytest.raises(ValueError, match="pinned dataset revision"):
        extractor.extract(tmp_path / "rows.json", tmp_path / "api.json", upstream, out)
    save(tmp_path / "rows.json", [row])
    save(tmp_path / "api.json", {"sha": "wrong"})
    with pytest.raises(ValueError, match="pinned revision"):
        extractor.extract(tmp_path / "rows.json", tmp_path / "api.json", upstream, out)
