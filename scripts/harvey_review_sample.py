"""Draw and tally the human-review sample of AI-flagged Harvey LAB rubric criteria.

The population is every rubric criterion that GPT-6 Sol or Claude Opus 5.5 flagged
(``problematic``/``confirmed`` or ``arguable``) in
``docs/harvey-lab-audit/litigation-dispute-resolution/comparison.json``: the rows that
carry an agreement bucket. A fixed seed selects a simple random sample without
replacement, so anyone can rerun the draw and get the same criteria. The review
protocol and decision rule live in ``human-review/README.md`` beside the output.

Subcommands:

``draw``
    Select the sample and write ``human-review/sample.json`` plus a blank
    ``human-review/worksheet.md``. Criterion text is read from Harvey LAB's
    ``task.json`` at the pinned commit (network access to GitHub required). Refuses
    to overwrite an existing worksheet, which holds the reviewer's verdicts.

``runs``
    Insert or refresh, for every worksheet item, how the published GPT-6 Luna and
    Claude Opus 5.5 runs were graded on that criterion (see ``harvey_model_runs.py``).
    The block sits between ``<!-- runs:start -->`` markers and never touches the
    reviewer's verdict fields.

``tally``
    Check that the worksheet still lists exactly the seeded draw, count the
    reviewer's verdicts, and report the exact one-sided hypergeometric lower bound
    on the number of defective criteria in the flagged population.

Example::

    uv run python scripts/harvey_review_sample.py draw
    uv run python scripts/harvey_review_sample.py runs
    uv run python scripts/harvey_review_sample.py tally"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import urllib.request
from collections import Counter
from fractions import Fraction
from math import comb

from harvey_dual_audit_core import (
    AUDIT_DIR,
    BUCKETS,
    OPUS_JSON,
    OPUS_MD,
    PINNED,
    TASKS_URL,
    Json,
    as_dict,
    as_list,
    crit_key,
    dump,
    load,
)
from harvey_dual_audit_render import sol_report_name
from harvey_model_runs import (
    CONDITIONS,
    JUDGES,
    one_line,
    results_by_criterion,
    scores,
    verdict_word,
)

REVIEW_DIR = AUDIT_DIR / "human-review"

SEED = 20261004

SAMPLE_SIZE = 25

# "Hundreds" is read as at least 200 defective criteria, at one-sided 95% confidence.
TARGET = 200

ALPHA = Fraction(5, 100)

VERDICTS = ("Defective", "Arguable", "Not defective", "Unresolved")

AI_REASONING = ("Correct", "Partly correct", "Wrong")

DOCS_URL = TASKS_URL.replace("/blob/", "/tree/")

RAW_URL = f"https://raw.githubusercontent.com/harveyai/harvey-labs/{PINNED}/tasks/litigation-dispute-resolution"

BUCKET_LABELS = dict(BUCKETS)

RUNS_START = "<!-- runs:start -->"

RUNS_END = "<!-- runs:end -->"


def population(rows: list[Json]) -> list[Json]:
    """Flagged criteria in a stable order, independent of comparison.json row order."""
    flagged = [r for r in rows if r.get("bucket")]
    return sorted(flagged, key=lambda r: (r["task"], crit_key(r["criterion"])))


def draw(pop: list[Json], n: int = SAMPLE_SIZE, seed: int = SEED) -> list[Json]:
    """Seeded simple random sample, returned grouped by task for review convenience."""
    picked = random.Random(seed).sample(pop, n)
    return sorted(picked, key=lambda r: (r["task"], crit_key(r["criterion"])))


def tail(N: int, K: int, n: int, x: int) -> Fraction:
    """P(X >= x) when n of N items are drawn and K of the N are defective."""
    hits = sum(comb(K, k) * comb(N - K, n - k) for k in range(x, min(n, K) + 1))
    return Fraction(hits, comb(N, n))


def lower_bound(N: int, n: int, x: int, alpha: Fraction = ALPHA) -> int:
    """Smallest defect count K in the population not rejected after seeing x of n."""
    return next(K for K in range(N + 1) if tail(N, K, n, x) > alpha)


def threshold(N: int, n: int, target: int = TARGET) -> int:
    """Fewest confirmed defects out of n whose lower bound reaches the target."""
    return next(x for x in range(n + 1) if lower_bound(N, n, x) >= target)


def fetch_criteria(task: str) -> dict[str, Json]:
    with urllib.request.urlopen(f"{RAW_URL}/{task}/task.json", timeout=30) as resp:
        data = json.load(resp)
    return {c["id"]: c for c in data["criteria"]}


def blockquote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def render_item(i: int, row: Json, record: Json, criterion: Json) -> list[str]:
    task, crit = row["task"], row["criterion"]
    line = as_dict(record.get("criterion_lines")).get(crit)
    anchor = f"#L{line}" if line else ""
    opus_blind = row.get("claude_opus_5_5_blind") or "not flagged"
    sol_md = sol_report_name(AUDIT_DIR / "tasks" / task)
    findings = [f"- **GPT-6 Sol:** {f}" for f in as_list(row.get("sol_findings"))] + [
        f"- **Claude Opus 5.5:** {f}" for f in as_list(row.get("opus_findings"))
    ]
    findings += [
        f"- **Claude Opus 5.5 on GPT-6 Sol:** {f}"
        for f in as_list(row.get("opus_on_sol"))
    ]
    return [
        f"## {i}. {record['title']} — {crit}",
        "",
        " · ".join(
            [
                f"[Criterion in pinned rubric]({TASKS_URL}/{task}/task.json{anchor})",
                f"[Source documents]({DOCS_URL}/{task}/documents)",
                f"[Task audit page](../tasks/{task}/README.md)",
            ]
        ),
        "",
        f"**{criterion['title']}**",
        "",
        blockquote(criterion["match_criteria"]),
        "",
        "<details><summary>AI findings (open after forming your own view)</summary>",
        "",
        f"Agreement group: {BUCKET_LABELS[row['bucket']]}. "
        f"GPT-6 Sol: {row.get('gpt_6_sol') or 'not flagged'}; "
        f"Claude Opus 5.5: {row.get('claude_opus_5_5') or 'not flagged'} "
        f"(blind pass: {opus_blind}).",
        "",
        *(findings or ["- No finding text recorded."]),
        "",
        f"Full reports: [GPT-6 Sol](../tasks/{task}/{sol_md}) "
        f"· [Claude Opus 5.5](../tasks/{task}/{OPUS_MD}).",
        "",
        "</details>",
        "",
        f"- **Verdict:** _({' / '.join(VERDICTS)})_",
        f"- **AI reasoning:** _({' / '.join(AI_REASONING)})_",
        "- **Note and source locator:**",
        "",
    ]


def render_worksheet(sample: list[Json], criteria: dict[tuple[str, str], Json]) -> str:
    out = [
        "# Human review worksheet: sampled AI-flagged criteria",
        "",
        f"Seeded draw of {len(sample)} criteria; see the [review protocol](README.md) "
        "before starting. Fill in each item's three fields in place, replacing the "
        "italic placeholder with one listed value. "
        "`uv run python scripts/harvey_review_sample.py tally` counts the verdicts.",
        "",
    ]
    for i, row in enumerate(sample, 1):
        record = load(AUDIT_DIR / "tasks" / row["task"] / OPUS_JSON)
        out += render_item(i, row, record, criteria[(row["task"], row["criterion"])])
    return "\n".join(out).rstrip() + "\n"


def sample_record(pop: list[Json], sample: list[Json]) -> Json:
    return {
        "harvey_commit": PINNED,
        "population": "comparison.json rows with an agreement bucket "
        "(criteria flagged problematic/confirmed or arguable by either model)",
        "population_size": len(pop),
        "seed": SEED,
        "sample_size": len(sample),
        "method": "random.Random(seed).sample over the population sorted by "
        "(task, criterion number)",
        "python": ".".join(map(str, sys.version_info[:3])),
        "target": TARGET,
        "confirmed_needed": threshold(len(pop), len(sample)),
        "sample": [
            {
                k: r.get(k)
                for k in (
                    "task",
                    "criterion",
                    "bucket",
                    "gpt_6_sol",
                    "claude_opus_5_5",
                    "claude_opus_5_5_blind",
                )
            }
            for r in sample
        ],
    }


def cmd_draw() -> None:
    worksheet = REVIEW_DIR / "worksheet.md"
    if worksheet.exists():
        sys.exit(f"{worksheet} exists and may hold verdicts; refusing to overwrite.")
    pop = population(load(AUDIT_DIR / "comparison.json")["rows"])
    sample = draw(pop)
    criteria: dict[tuple[str, str], Json] = {}
    for task in sorted({r["task"] for r in sample}):
        for cid, crit in fetch_criteria(task).items():
            criteria[(task, cid)] = crit
    REVIEW_DIR.mkdir(exist_ok=True)
    dump(REVIEW_DIR / "sample.json", sample_record(pop, sample))
    worksheet.write_text(render_worksheet(sample, criteria), encoding="utf-8")
    print(f"Drew {len(sample)} of {len(pop)} flagged criteria into {REVIEW_DIR}.")


def runs_block(task: str, crit: str) -> list[str]:
    """How each published model run was graded on one sampled criterion."""
    table = [
        "| Run | "
        + " | ".join(label for _, label in JUDGES)
        + " | Other criteria failed ("
        + " / ".join(label for _, label in JUDGES)
        + ") |",
        "|---|" + "---|" * (len(JUDGES) + 1),
    ]
    reasons: list[str] = []
    files: list[str] = []
    for slug, label, *_ in CONDITIONS:
        judged = scores(task, slug)
        if not judged:
            continue
        page = f"../model-runs/{task}/{slug}/README.md"
        files.append(
            f"- {label}: "
            + " · ".join(
                f"[{judge_label} score file](../model-runs/{task}/{slug}/"
                f"scores_{judge}.json)"
                for judge, judge_label in JUDGES
            )
            + f" · [deliverables]({page}#deliverables)"
        )
        cells: list[str] = []
        others: list[str] = []
        for judge, judge_label in JUDGES:
            graded = results_by_criterion(judged[judge])
            result = graded.get(crit)
            cells.append(verdict_word(result))
            others.append(
                str(
                    sum(
                        1
                        for other, r in graded.items()
                        if other != crit and r.get("verdict") != "pass"
                    )
                )
            )
            reasoning = one_line(result.get("reasoning", "")) if result else ""
            reasons.append(
                f"- **{label}, {judge_label}: {verdict_word(result)}.** {reasoning}"
            )
        table.append(
            f"| [{label}]({page}#{crit.lower()}) | "
            + " | ".join(cells)
            + f" | {' / '.join(others)} |"
        )
    if not reasons:
        return [RUNS_START, RUNS_END]
    return [
        RUNS_START,
        "<details><summary>How the model runs were graded (open after forming your "
        "own view)</summary>",
        "",
        "Native LAB grades of the published runs; the judges are AI models and can "
        "misapply a criterion. Under LAB's all-pass scoring a run scores 1 with a "
        "judge only if every criterion passes, so a Fail here with 0 other failures "
        "would by itself have zeroed that judge's score. Each run link opens the "
        "deliverables and every criterion's grades.",
        "",
        *table,
        "",
        "Raw files:",
        "",
        *files,
        "",
        *reasons,
        "",
        "</details>",
        RUNS_END,
    ]


def add_runs(text: str) -> str:
    """Insert or refresh each worksheet item's runs block, leaving verdicts alone."""
    head, *items = re.split(r"(?m)^(?=## \d+\. )", text)
    out = [head]
    for item in items:
        crit = item.splitlines()[0].rsplit("— ", 1)[1].strip()
        found = re.search(r"\]\(\.\./tasks/([^/]+)/README\.md\)", item)
        if not found:
            sys.exit(f"worksheet item for {crit} has no task link")
        block = "\n".join(runs_block(found.group(1), crit))
        if RUNS_START in item:
            item = re.sub(
                re.escape(RUNS_START) + r".*?" + re.escape(RUNS_END),
                lambda _m, block=block: block,
                item,
                flags=re.S,
            )
        else:
            item = item.replace("- **Verdict:**", block + "\n\n- **Verdict:**", 1)
        out.append(item)
    return "".join(out)


def cmd_runs() -> None:
    worksheet = REVIEW_DIR / "worksheet.md"
    text = worksheet.read_text(encoding="utf-8")
    updated = add_runs(text)
    if [v[1:] for v in parse_worksheet(updated)] != [
        v[1:] for v in parse_worksheet(text)
    ]:
        sys.exit("refusing to write: the runs block changed parsed verdicts")
    worksheet.write_text(updated, encoding="utf-8")
    print(f"Updated model-run grades for {len(parse_worksheet(updated))} items.")


def parse_worksheet(text: str) -> list[tuple[str, str, str, str]]:
    """(task, criterion, verdict, AI reasoning) per item, in worksheet order."""
    items = re.split(r"^## \d+\. ", text, flags=re.M)[1:]
    parsed: list[tuple[str, str, str, str]] = []
    for item in items:
        crit = item.splitlines()[0].rsplit("— ", 1)[1].strip()
        task = re.search(r"\]\(\.\./tasks/([^/]+)/README\.md\)", item)
        verdict = re.search(r"^- \*\*Verdict:\*\* (.*)$", item, re.M)
        reasoning = re.search(r"^- \*\*AI reasoning:\*\* (.*)$", item, re.M)
        parsed.append(
            (
                task.group(1) if task else "",
                crit,
                verdict.group(1).strip() if verdict else "",
                reasoning.group(1).strip() if reasoning else "",
            )
        )
    return parsed


def environment_defects(text: str) -> list[int]:
    """Worksheet items flagged as environment defects, tallied apart from verdicts."""
    items = re.split(r"(?m)^(?=## \d+\. )", text)[1:]
    return [
        int(m.group(1))
        for item in items
        if re.search(r"(?m)^- \*\*Environment defect:\*\* Yes", item)
        and (m := re.match(r"## (\d+)\.", item))
    ]


def cmd_tally() -> None:
    record = load(REVIEW_DIR / "sample.json")
    pop = population(load(AUDIT_DIR / "comparison.json")["rows"])
    sample = draw(pop, record["sample_size"], record["seed"])
    if [(r["task"], r["criterion"]) for r in sample] != [
        (r["task"], r["criterion"]) for r in record["sample"]
    ]:
        sys.exit("sample.json no longer matches the seeded draw from comparison.json.")
    text = (REVIEW_DIR / "worksheet.md").read_text(encoding="utf-8")
    items = parse_worksheet(text)
    if [(t, c) for t, c, _, _ in items] != [
        (r["task"], r["criterion"]) for r in sample
    ]:
        sys.exit("worksheet.md items do not match sample.json.")
    verdicts = Counter(v for _, _, v, _ in items if v in VERDICTS)
    pending = len(items) - sum(verdicts.values())
    print(f"Population {len(pop)}; sample {len(items)}; pending {pending}.")
    for v in VERDICTS:
        print(f"  {v}: {verdicts[v]}")
    by_bucket: dict[str, Counter[str]] = {}
    for row, (_, _, v, _) in zip(sample, items, strict=True):
        by_bucket.setdefault(row["bucket"], Counter())[v] += 1
    for key, label in BUCKETS:
        if key in by_bucket:
            got = by_bucket[key]
            print(f"  {label}: {got['Defective']} defective of {sum(got.values())}")
    env = environment_defects(text)
    print(f"  Environment defects (tallied separately): {len(env)} {env}")
    reasoning = Counter(r for _, _, _, r in items if r in AI_REASONING)
    print("  AI reasoning: " + ", ".join(f"{k} {reasoning[k]}" for k in AI_REASONING))
    if pending:
        print("Bound not reported until every item has a verdict.")
        return
    x, n, N = verdicts["Defective"], len(items), len(pop)
    bound = lower_bound(N, n, x)
    print(
        f"Defective {x}/{n}: point estimate {round(x * N / n)}; one-sided 95% "
        f"lower bound {bound} of {N} flagged criteria "
        f"({'meets' if bound >= TARGET else 'does not meet'} the {TARGET} target)."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("command", choices=["draw", "runs", "tally"])
    args = parser.parse_args()
    {"draw": cmd_draw, "runs": cmd_runs, "tally": cmd_tally}[args.command]()


if __name__ == "__main__":
    main()
