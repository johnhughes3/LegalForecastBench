"""Draw, render, and tally a human-review sample of flagged LegalReasonBench criteria.

The population is every litigation rubric criterion that either saved blind report
(GPT-6 Sol or Claude Opus 5.5) labeled ``problematic`` or ``arguable`` in
``docs/legalreasonbench-audit/litigation/comparison.json``, one entry per
assignment-criterion pair. The later reconciliation travels as metadata and does not
affect eligibility. A fixed seed selects a simple random sample without replacement.
The protocol and analysis live in ``human-review/README.md`` beside the output.

Subcommands:

``draw``
    Select the sample and write ``human-review/sample.json`` plus a blank
    ``human-review/worksheet.md``. Checks the dataset's current Hugging Face revision
    against the pinned one (recording, never adopting, a difference) and reads the
    pinned ``rubric.json`` files to confirm the saved criterion text and find line
    anchors, so network access is required. Refuses to overwrite either file.

``render``
    Regenerate the worksheet's supporting material from the saved audit files,
    copying every reviewer field between the ``<!-- review -->`` markers unchanged.

``tally``
    Check that sample.json and the worksheet still match the seeded draw, count the
    completed reviews, and, once every item is complete, report the estimated number
    of defective criteria among the flagged ones with the exact one-sided 95%
    hypergeometric lower bound. Exits nonzero while any item is incomplete.

Example::

    uv run python scripts/legalreasonbench_review_sample.py draw
    uv run python scripts/legalreasonbench_review_sample.py render
    uv run python scripts/legalreasonbench_review_sample.py tally"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import re
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import quote

from harvey_dual_audit_core import BUCKETS, Json, as_list, dump, load
from harvey_review_sample import blockquote, lower_bound
from legalreasonbench_extract import AUDIT, DATASET, REVISION, upstream_url
from legalreasonbench_report import REPORTS

REVIEW_DIR = AUDIT / "human-review"

SEED = 20261024

SAMPLE_SIZE = 25

BLIND = ("gpt_6_sol", "claude_opus_5_5")

FLAGS = ("problematic", "arguable")

ORDERING = "sorted by (assignment ID, criterion ID) with Python string comparison"

METHOD = "random.Random(seed).sample(population, sample_size)"

VERDICTS = ("Defective", "Arguable", "Not defective", "Unresolved")

AI_REASONING = ("Correct", "Partly correct", "Wrong")

BASIS = ("Unambiguous objective error", "Professional judgment")

ORIGIN = ("Yes", "No")

ENVIRONMENT = ("Defective", "Correct")

FIELDS = {
    "Rubric verdict": VERDICTS,
    "AI reasoning": AI_REASONING,
    "Defect basis (Defective only)": BASIS,
    "Defect arises from environment (Defective only)": ORIGIN,
    "Environment": ENVIRONMENT,
    "Environment explanation": (),
    "Note and source locator": (),
}

REVIEW_START = "<!-- review:start -->"

REVIEW_END = "<!-- review:end -->"

BUCKET_LABELS = dict(BUCKETS)

MODEL_LABELS = {"gpt_6_sol": "GPT-6 Sol", "claude_opus_5_5": "Claude Opus 5.5"}

FIELD_LINE = re.compile(r"^- \*\*(.+?):\*\*\s?(.*)$")

Key = tuple[str, str]


def key(row: Json) -> Key:
    """The sampling unit: (assignment ID, upstream criterion ID)."""
    return (row["task"], row["criterion"])


def population(rows: list[Json]) -> list[Json]:
    """Criteria flagged by either blind report, deduplicated and in a stable order."""
    unique: dict[Key, Json] = {}
    for row in rows:
        if any(row.get(model) in FLAGS for model in BLIND):
            if unique.setdefault(key(row), row) != row:
                raise ValueError(f"conflicting rows for {key(row)} in comparison.json")
    return [unique[k] for k in sorted(unique)]


def draw(pop: list[Json], n: int = SAMPLE_SIZE, seed: int = SEED) -> list[Json]:
    """Seeded simple random sample without replacement, in draw order."""
    return random.Random(seed).sample(pop, n)


def comparison_rows() -> list[Json]:
    """Criterion rows of the saved blind comparison, pinned to the audited revision."""
    comparison = load(AUDIT / "comparison.json")
    if comparison["revision"] != REVISION:
        sys.exit("comparison.json is not pinned to the audited dataset revision.")
    return comparison["rows"]


def frozen_sample() -> tuple[Json, list[Json]]:
    """sample.json after checking it against the seeded draw from comparison.json."""
    record = load(REVIEW_DIR / "sample.json")
    fixed = (record["seed"], record["sample_size"], record["dataset_revision"])
    if fixed != (SEED, SAMPLE_SIZE, REVISION):
        sys.exit("sample.json seed, size, or revision differs from the protocol.")
    pop = population(comparison_rows())
    if [list(key(r)) for r in pop] != record["population_ids"]:
        sys.exit("comparison.json no longer yields the frozen population.")
    drawn = draw(pop, record["sample_size"], record["seed"])
    if [list(key(r)) for r in drawn] != record["selected_in_draw_order"]:
        sys.exit("sample.json no longer matches the seeded draw.")
    if sorted(key(r) for r in drawn) != [key(r) for r in record["sample"]]:
        sys.exit("sample.json display list does not match its draw.")
    return record, sorted(drawn, key=key)


def current_revision() -> str:
    """The dataset's current Hugging Face commit, for comparison with the pin."""
    url = f"https://huggingface.co/api/datasets/{DATASET}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)["sha"]


def rubric_lines(inputs: Json) -> dict[str, int]:
    """Line of each criterion in the pinned rubric.json, after checking saved text."""
    url = upstream_url(inputs["rubric_path"], raw=True)
    with urllib.request.urlopen(url, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    upstream = {c["name"]: c for c in json.loads(raw)["criteria"]}
    for crit in inputs["rubric"]:
        found = upstream.get(crit["criterion_id"], {})
        if (found.get("description"), found.get("score")) != (
            crit["criterion"],
            crit["points"],
        ):
            sys.exit(f"saved rubric differs from upstream: {crit['criterion_id']}")
    lines: dict[str, int] = {}
    for number, line in enumerate(raw.splitlines(), 1):
        name = re.search(r'"name":\s*"([^"]+)"', line)
        if name:
            lines[name.group(1)] = number
    return lines


def task_inputs(task: str) -> Json:
    return load(AUDIT / "tasks" / task / "input.json")


def one_line(text: str) -> str:
    return " ".join(str(text).split())


def finding_lines(label: str, finding: Json) -> list[str]:
    """One AI finding with its quoted evidence and authorities, as worksheet text."""
    out = [
        f"**{label} {finding['id']} ({finding['status']}, {finding['category']}): "
        f"{one_line(finding['title'])}**",
        "",
        one_line(finding["explanation"]),
        "",
    ]
    evidence = [
        f"- {one_line(e.get('source', ''))}: “{one_line(e.get('quote', ''))}”"
        for e in as_list(finding.get("evidence"))
    ]
    if evidence:
        out += ["Evidence the model quoted (check against the source):", "", *evidence]
        out.append("")
    authorities = [
        f"- {one_line(a.get('citation', ''))}: {one_line(a.get('proposition', ''))}"
        + (f" ([link]({a['url']}))" if a.get("url") else "")
        for a in as_list(finding.get("authorities"))
    ]
    if authorities:
        out += ["Authorities the model cited:", "", *authorities, ""]
    if finding.get("suggested_fix"):
        out += [f"Suggested fix: {one_line(finding['suggested_fix'])}", ""]
    return out


def rulings(reconciliation: Json, blind: list[tuple[str, Json]], cid: str) -> list[str]:
    """Reconciliation rulings on the blind findings that cover this criterion."""
    wanted = {(model, f["id"]) for model, f in blind}
    out: list[str] = []
    for v in as_list(reconciliation.get("verdicts")):
        if (v["model"], v["finding_id"]) not in wanted:
            continue
        name = f"{MODEL_LABELS[v['model']]} {v['finding_id']}"
        part = next(
            (p for p in as_list(v.get("per_criterion")) if p["criterion"] == cid), None
        )
        if part:
            out.append(
                f"- **{name} → {v['verdict']}; for this criterion "
                f"{part['verdict']}:** {one_line(part['reason'])} "
                f"Overall ruling: {one_line(v['reason'])}"
            )
        else:
            out.append(f"- **{name} → {v['verdict']}:** {one_line(v['reason'])}")
    return out or ["- No ruling recorded on a blind finding for this criterion."]


def attachment_lines(task: str, inputs: Json) -> list[str]:
    """Pinned upstream and extracted-text links for every accumulated attachment."""
    task_dir = AUDIT / "tasks" / task
    out: list[str] = []
    for a in as_list(inputs["attachments"]):
        rel = a["extracted_path"]
        name = Path(a["upstream_path"]).name
        parts = [
            f"[{name}]({a['source_url']})",
            f"[extracted text](../tasks/{task}/{quote(rel)})",
        ]
        for suffix, label in (
            (".transcription.md", "AI visual transcription of scanned or image text"),
            (".figures.md", "AI descriptions of embedded figures"),
        ):
            extra = rel.removesuffix(".md") + suffix
            if (task_dir / extra).exists():
                parts.append(f"[{label}](../tasks/{task}/{quote(extra)})")
        out.append(f"- Assignment {a['assignment']}: " + " · ".join(parts))
    return out


def blank_review() -> str:
    """The reviewer block with every field blank or showing its permitted values."""
    lines = [REVIEW_START]
    for label, options in FIELDS.items():
        lines.append(
            f"- **{label}:** _({' / '.join(options)})_"
            if options
            else f"- **{label}:**"
        )
    return "\n".join([*lines, REVIEW_END])


def render_item(i: int, row: Json, inputs: Json, line: int, review: str) -> list[str]:
    """One worksheet entry: criterion, sources, collapsed AI material, review block."""
    task, cid = key(row)
    crit = next(c for c in inputs["rubric"] if c["criterion_id"] == cid)
    reports = {
        name: load(AUDIT / "tasks" / task / filename)
        for name, filename in REPORTS.items()
    }
    blind = [
        (model, f)
        for model in BLIND
        for f in as_list(reports[model]["findings"])
        if cid in f["criteria"]
    ]
    final = [
        f
        for f in as_list(reports["reconciliation"]["findings"])
        if cid in f["criteria"]
    ]
    kind = "Penalty" if crit["polarity"] == "penalty" else "Reward"
    prior = [
        f"[assignment {p['assignment']}]({p['source_url']})"
        for p in as_list(inputs["prior_prompts"])
    ]
    return [
        f"## {i}. {inputs['matter_title']}, assignment {inputs['assignment']}"
        + (f": {inputs['assignment_title']}" if inputs["assignment_title"] else "")
        + f" — {cid}",
        "",
        " · ".join(
            [
                f"[Criterion in pinned rubric]({inputs['rubric_url']}#L{line})",
                f"[Pinned task instructions]({inputs['instruction_url']})",
                f"[Prompt with earlier prompts and attachment list]"
                f"(../tasks/{task}/instruction.md)",
                f"[Task audit page](../tasks/{task}/README.md)",
                f"[Matter citation check](../citation-check/results/"
                f"{inputs['matter_id']}.md)",
            ]
        ),
        "",
        f"**{kind} criterion, {crit['points']:+g} points** "
        f"(the assignment's reward criteria total {inputs['positive_points']:g}) · "
        f"IRAC section: {crit.get('irac_section') or 'not given'} · "
        f"Research universe: {inputs['research_universe']}",
        "",
        blockquote(crit["criterion"]),
        "",
        f"Upstream `source` field: {one_line(crit.get('source') or 'not given')}",
        "",
        "Earlier same-matter prompts: "
        + (", ".join(prior) if prior else "none (first assignment in the matter)")
        + ".",
        "",
        "<details><summary>Upstream justification field and source documents</summary>",
        "",
        f"Justification: {one_line(crit.get('justification') or 'not given')}",
        "",
        "Attachments available at this assignment, including earlier assignments' "
        "(pinned upstream file, then the audit's extracted text):",
        "",
        *attachment_lines(task, inputs),
        "",
        "</details>",
        "",
        "<details><summary>Blind AI findings</summary>",
        "",
        f"Agreement bucket: {BUCKET_LABELS[row['bucket']]}. "
        f"GPT-6 Sol (blind): {row['gpt_6_sol'] or 'not flagged'}; "
        f"Claude Opus 5.5 (blind): {row['claude_opus_5_5'] or 'not flagged'}.",
        "",
        *(
            text
            for model, finding in blind
            for text in finding_lines(MODEL_LABELS[model], finding)
        ),
        f"Full reports: [GPT-6 Sol](../tasks/{task}/gpt-6-sol-audit.md) · "
        f"[Claude Opus 5.5](../tasks/{task}/claude-opus-5-5-audit.md).",
        "",
        "</details>",
        "",
        "<details><summary>Later reconciliation (saw both blind reports)</summary>",
        "",
        f"Final reconciliation status: {row['reconciliation'] or 'not retained'}.",
        "",
        "Rulings on the blind findings above:",
        "",
        *rulings(reports["reconciliation"], blind, cid),
        "",
        *(text for f in final for text in finding_lines("Reconciliation", f)),
        f"[Full reconciliation](../tasks/{task}/reconciliation.md).",
        "",
        "</details>",
        "",
        review,
        "",
    ]


HEADER = (
    "\n\n".join(
        [
            "# Human review worksheet: sampled AI-flagged LegalReasonBench criteria",
            "A simple random sample of {n} of the {N} litigation criteria that either "
            "blind AI report flagged (seed `{seed}`). Read the [review protocol]"
            "(README.md) first. Replace each italic placeholder with one listed value, "
            "write the explanation and note in place, then run `uv run python "
            "scripts/legalreasonbench_review_sample.py tally`. Keep the `review` "
            "markers: "
            "`render` refreshes everything else in this file and copies the fields "
            "between them unchanged.",
            "Items are grouped by assignment for reading; the order has no effect on "
            "which criteria were drawn. The AI findings and the later reconciliation "
            "are "
            "collapsed to keep entries readable. That is a convenience, not reviewer "
            "blinding: open them whenever useful, and test their arguments against the "
            "pinned upstream files and the governing authority. Quotations in the AI "
            "reports are leads, not sources.",
            "Source limits: the extracted text is a convenience copy of the pinned "
            "upstream files. PDF extraction used no OCR, DOCX locators are not "
            "original "
            "pagination, and the AI visual transcriptions and figure descriptions "
            "linked "
            "below supplement scanned or image-only documents without guaranteeing "
            "complete capture (see the [audit README](../README.md)). No solver "
            "responses or benchmark grades exist for these assignments: the audit "
            "submitted no responses to the benchmark's judges.",
        ]
    )
    + "\n"
)


def render_worksheet(
    record: Json, sample: list[Json], reviews: dict[Key, str] | None = None
) -> str:
    """The full worksheet, reusing saved reviewer blocks where given."""
    out = [
        HEADER.format(
            n=record["sample_size"], N=record["population_size"], seed=record["seed"]
        )
    ]
    lines = {key(s): s["rubric_line"] for s in record["sample"]}
    for i, row in enumerate(sample, 1):
        review = (reviews or {}).get(key(row), blank_review())
        out += render_item(i, row, task_inputs(row["task"]), lines[key(row)], review)
    return "\n".join(out).rstrip() + "\n"


def split_items(text: str) -> list[tuple[Key, str]]:
    """(task, criterion) and the reviewer block of each worksheet item, in order."""
    out: list[tuple[Key, str]] = []
    for item in re.split(r"(?m)^(?=## \d+\. )", text)[1:]:
        crit = item.splitlines()[0].rsplit(" — ", 1)[-1].strip()
        task = re.search(r"\]\(\.\./tasks/([^/]+)/README\.md\)", item)
        block = re.search(
            re.escape(REVIEW_START) + r".*?" + re.escape(REVIEW_END), item, re.S
        )
        if not task or not block:
            sys.exit(f"worksheet item {crit} lacks its task link or review markers")
        out.append(((task.group(1), crit), block.group(0)))
    return out


def parse_review(block: str) -> dict[str, str]:
    """Reviewer fields with placeholders treated as blank; notes may span lines."""
    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in block.splitlines()[1:-1]:
        match = FIELD_LINE.match(line)
        label = match.group(1) if match else ""
        if match and label in FIELDS:
            current = label
            fields[label] = [match.group(2)]
        elif current:
            fields[current].append(line)
    out: dict[str, str] = {}
    for label in FIELDS:
        value = "\n".join(fields.get(label, [])).strip()
        out[label] = "" if re.fullmatch(r"_\(.*\)_", value) else value
    return out


def problems(review: dict[str, str]) -> list[str]:
    """Missing or invalid fields that keep a review from counting as complete."""
    out: list[str] = []
    required = ["Rubric verdict", "AI reasoning", "Environment"]
    if review["Rubric verdict"] == "Defective":
        required += [
            "Defect basis (Defective only)",
            "Defect arises from environment (Defective only)",
        ]
    for label in required:
        if not review[label]:
            out.append(f"{label} blank")
        elif review[label] not in FIELDS[label]:
            out.append(f"{label} not one of {' / '.join(FIELDS[label])}")
    if review["Environment"] == "Defective" and not review["Environment explanation"]:
        out.append("Environment explanation blank")
    if not review["Note and source locator"]:
        out.append("Note and source locator blank")
    return out


def summary(
    sample: list[Json], reviews: list[dict[str, str]], population_size: int
) -> tuple[list[str], bool]:
    """Report lines and whether every item is complete enough to estimate."""
    incomplete = {i: p for i, r in enumerate(reviews, 1) if (p := problems(r))}
    done = [
        (row, r)
        for i, (row, r) in enumerate(zip(sample, reviews, strict=True), 1)
        if i not in incomplete
    ]
    n, N = len(sample), population_size
    lines = [f"Population {N} flagged criteria; sample {n}; complete {len(done)}."]
    for i, found in incomplete.items():
        lines.append(f"  Item {i} incomplete: {'; '.join(found)}.")
    scope = "" if not incomplete else " (completed items only)"
    verdicts = Counter(r["Rubric verdict"] for _, r in done)
    lines.append(
        f"Rubric verdicts{scope}: " + ", ".join(f"{v} {verdicts[v]}" for v in VERDICTS)
    )
    reasoning = Counter(r["AI reasoning"] for _, r in done)
    lines.append(
        f"AI reasoning{scope}: "
        + ", ".join(f"{v} {reasoning[v]}" for v in AI_REASONING)
    )
    env = Counter(r["Environment"] for _, r in done)
    bad = {row["task"] for row, r in done if r["Environment"] == "Defective"}
    lines.append(
        f"Task environment{scope}: "
        + ", ".join(f"{v} {env[v]}" for v in ENVIRONMENT)
        + f"; assignments with a Defective environment {len(bad)} of "
        f"{len({row['task'] for row in sample})} sampled"
    )
    lines.append("  Rubric verdict x environment: " + " | ".join(ENVIRONMENT))
    for v in VERDICTS:
        cells = [
            sum(1 for _, r in done if (r["Rubric verdict"], r["Environment"]) == (v, e))
            for e in ENVIRONMENT
        ]
        lines.append(f"    {v}: " + " | ".join(map(str, cells)))
    defective = [r for _, r in done if r["Rubric verdict"] == "Defective"]
    basis = Counter(r["Defect basis (Defective only)"] for r in defective)
    origin = Counter(
        r["Defect arises from environment (Defective only)"] for r in defective
    )
    lines.append(
        f"Defective by basis{scope}: "
        + ", ".join(f"{b} {basis[b]}" for b in BASIS)
        + f"; arising from the environment {origin['Yes']}"
    )
    for label, field, groups in (
        ("agreement bucket", "bucket", [(b, BUCKET_LABELS[b]) for b, _ in BUCKETS]),
        (
            "later reconciliation",
            "reconciliation",
            [
                ("problematic", "problematic"),
                ("arguable", "arguable"),
                (None, "not retained"),
            ],
        ),
    ):
        lines.append(f"By {label} (descriptive){scope}:")
        for value, name in groups:
            members = [r for row, r in done if row[field] == value]
            total = sum(1 for row in sample if row[field] == value)
            if total:
                got = Counter(r["Rubric verdict"] for r in members)
                lines.append(
                    f"  {name}: {total} sampled, {len(members)} complete; "
                    + ", ".join(f"{v} {got[v]}" for v in VERDICTS)
                )
    if incomplete:
        lines.append(
            f"No estimate: {len(incomplete)} of {n} items are incomplete, and blank "
            "or invalid fields never count as completed reviews."
        )
        return lines, False
    x = verdicts["Defective"]
    lines.append(
        f"Defective {x} of {n} ({x / n:.0%}); estimated {round(x * N / n)} of the {N} "
        f"flagged criteria; exact one-sided 95% hypergeometric lower bound "
        f"{lower_bound(N, n, x)} of {N}."
    )
    k = basis["Unambiguous objective error"]
    lines.append(
        f"Secondary: unambiguous objective errors {k} of {n}; one-sided 95% lower "
        f"bound {lower_bound(N, n, k)} of {N}."
    )
    return lines, True


def git_commit(path: Path) -> str:
    """The commit that last changed ``path``, recorded as the audit source."""
    return subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def cmd_draw() -> None:
    """Draw once and write sample.json and a blank worksheet; never overwrite."""
    for name in ("sample.json", "worksheet.md"):
        if (REVIEW_DIR / name).exists():
            sys.exit(f"{REVIEW_DIR / name} exists; refusing to overwrite the draw.")
    observed = current_revision()
    if observed != REVISION:
        print(f"Hugging Face now reports {observed}; keeping pinned {REVISION}.")
    pop = population(comparison_rows())
    picked = draw(pop)
    sample = sorted(picked, key=key)
    lines: dict[str, dict[str, int]] = {}
    for task in sorted({r["task"] for r in sample}):
        lines[task] = rubric_lines(task_inputs(task))
    record: Json = {
        "dataset": DATASET,
        "dataset_revision": REVISION,
        "dataset_revision_check": {
            "date": datetime.date.today().isoformat(),
            "huggingface_current_sha": observed,
            "matches_pinned_revision": observed == REVISION,
        },
        "audit_source_commit": git_commit(AUDIT / "comparison.json"),
        "population": "comparison.json criteria labeled problematic or arguable by "
        "either blind report (gpt_6_sol, claude_opus_5_5), one per "
        "assignment-criterion pair; reconciliation does not affect eligibility",
        "ordering": ORDERING,
        "population_size": len(pop),
        "population_ids": [list(key(r)) for r in pop],
        "seed": SEED,
        "sample_size": len(picked),
        "method": METHOD,
        "python": ".".join(map(str, sys.version_info[:3])),
        "selected_in_draw_order": [list(key(r)) for r in picked],
        "sample": [
            {
                "task": r["task"],
                "criterion": r["criterion"],
                "bucket": r["bucket"],
                "gpt_6_sol": r["gpt_6_sol"],
                "claude_opus_5_5": r["claude_opus_5_5"],
                "reconciliation": r["reconciliation"],
                "polarity": r["polarity"],
                "rubric_line": lines[r["task"]][r["criterion"]],
            }
            for r in sample
        ],
    }
    REVIEW_DIR.mkdir(exist_ok=True)
    dump(REVIEW_DIR / "sample.json", record)
    (REVIEW_DIR / "worksheet.md").write_text(
        render_worksheet(record, sample), encoding="utf-8"
    )
    print(f"Drew {len(picked)} of {len(pop)} flagged criteria into {REVIEW_DIR}.")


def checked_reviews(sample: list[Json]) -> list[str]:
    """Reviewer blocks of the worksheet, after checking it lists the frozen sample."""
    text = (REVIEW_DIR / "worksheet.md").read_text(encoding="utf-8")
    items = split_items(text)
    if [k for k, _ in items] != [key(r) for r in sample]:
        sys.exit("worksheet.md items do not match sample.json.")
    return [block for _, block in items]


def cmd_render() -> None:
    """Refresh supporting material while copying reviewer fields unchanged."""
    record, sample = frozen_sample()
    blocks = checked_reviews(sample)
    updated = render_worksheet(
        record, sample, {key(r): b for r, b in zip(sample, blocks, strict=True)}
    )
    if [b for _, b in split_items(updated)] != blocks:
        sys.exit("refusing to write: rendering changed a reviewer field")
    (REVIEW_DIR / "worksheet.md").write_text(updated, encoding="utf-8")
    print(f"Refreshed {len(sample)} items; reviewer fields unchanged.")


def cmd_tally() -> None:
    """Print the tally; exit 1 while any sampled item is incomplete."""
    record, sample = frozen_sample()
    blocks = checked_reviews(sample)
    lines, complete = summary(
        sample, [parse_review(b) for b in blocks], record["population_size"]
    )
    print("\n".join(lines))
    if not complete:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("command", choices=["draw", "render", "tally"])
    args = parser.parse_args()
    {"draw": cmd_draw, "render": cmd_render, "tally": cmd_tally}[args.command]()


if __name__ == "__main__":
    main()
