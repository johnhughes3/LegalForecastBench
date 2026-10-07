"""Draw and render the attorney validation sample for the LAB citation check.

The citation check (``docs/harvey-lab-audit/litigation-dispute-resolution/
citation-check/``) reports 436 problem citations that no rubric criterion asks the
model to catch. This script draws the seeded simple random sample an attorney reviews
to estimate how many of those AI findings are real errors, and writes the worksheet.

Subcommands:

``draw``
    Write ``attorney-review/sample.json`` and ``attorney-review/worksheet.md``.
    Refuses to overwrite a worksheet that already has verdicts.

``tally``
    Recompute the draw, check the worksheet still lists it in order, apply the
    stopping rule, and print the exact one-sided 95% lower bound.

Example::

    uv run python scripts/harvey_citation_sample.py draw
    uv run python scripts/harvey_citation_sample.py tally
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHECK_DIR = ROOT / "docs/harvey-lab-audit/litigation-dispute-resolution/citation-check"
REVIEW_DIR = CHECK_DIR / "attorney-review"
HARVEY_COMMIT = "1dd81403b2fbb60596f7aea3fcecafad7bf73143"
TASK_URL = (
    "https://github.com/harveyai/harvey-labs/blob/"
    f"{HARVEY_COMMIT}/tasks/litigation-dispute-resolution"
)
SEED = 20261007
DRAW_SIZE = 20
FIRST_STAGE = 10
VERDICTS = ("Confirmed error", "Not an error", "Minor defect only")
Json = dict[str, Any]


def population() -> list[Json]:
    """The unintentional problem citations, sorted by task and citation number."""
    intent: list[Json] = json.loads(
        (CHECK_DIR / "rubric-intent.json").read_text(encoding="utf-8")
    )
    rows = [r for r in intent if not r["intentional"]]
    return sorted(rows, key=lambda r: (r["task"], r["ref"]))


def draw(pop: list[Json]) -> list[Json]:
    """Seeded simple random sample in draw order, which is also review order."""
    return random.Random(SEED).sample(pop, DRAW_SIZE)


def _citation(task: str, ref: int) -> Json:
    data: Json = json.loads(
        (CHECK_DIR / "results" / f"{task}.json").read_text(encoding="utf-8")
    )
    return next(c for c in data["citations"] if c["ref"] == ref)


def _source(task: str, document: str) -> str:
    if document.startswith("task.json"):
        return f"{TASK_URL}/{task}/task.json"
    name = document.removesuffix(".md").replace("__", "/")
    return f"{TASK_URL}/{task}/documents/{name}"


def _block(text: str) -> str:
    return " ".join(str(text).split())


def _passage(text_dir: Path | None, task: str, document: str, context: str) -> str:
    """About 1,200 characters of the document around the citation, or ''."""
    if text_dir is None:
        return ""
    path = text_dir / task / document
    if not path.exists():
        return ""

    def plain(text: str) -> str:  # drop Markdown emphasis and escapes before matching
        return " ".join(re.sub(r"[*_\\]", "", text).split())

    body = plain(path.read_text(encoding="utf-8"))
    probe = plain(context).strip("()")[:80]
    at = body.find(probe) if probe else -1
    if at < 0:
        return ""
    start, end = max(0, at - 500), min(len(body), at + len(probe) + 700)
    return ("…" if start else "") + body[start:end] + ("…" if end < len(body) else "")


def render(sample: list[Json], text_dir: Path | None = None) -> str:
    """The reviewer's worksheet: one entry per sampled citation, in draw order."""
    out = [
        "# Attorney review of sampled citation-check findings: worksheet",
        "",
        "Review in order, following the [protocol](README.md). Fill in the three "
        "fields under each entry; leave everything else as drawn.",
        "",
    ]
    for n, row in enumerate(sample, 1):
        c = _citation(row["task"], row["ref"])
        first = c["first_check"]
        second = c.get("second_check")
        stage = "first ten" if n <= FIRST_STAGE else "second ten (only if needed)"
        out += [
            f"## {n}. {row['task']} — citation {row['ref']} ({stage})",
            "",
            f"- **Document:** [{c['document'].removesuffix('.md')}]"
            f"({_source(row['task'], c['document'])}), {_block(c['location'])}",
            "- **Authority as written:** "
            + (
                _block(c["citation_as_written"])
                if _block(c["authority"]) in _block(c["citation_as_written"])
                else f"{_block(c['authority'])}, {_block(c['citation_as_written'])}"
            ).strip(", ")
            + (f" (pin {_block(c['pincite'])})" if c["pincite"] else ""),
            f"- **Cited for:** {_block(c['cited_for'])}",
        ]
        if c["quotes"]:
            out.append(
                "- **Quoted as:** " + " / ".join(f"“{_block(q)}”" for q in c["quotes"])
            )
        passage = _passage(text_dir, row["task"], c["document"], c["context"])
        out += [
            f"- **Context:** {_block(c['context'])}",
            f"- **AI finding:** {row['final_status']}",
            f"- **AI explanation:** {_block((second or first)['explanation'])}",
        ]
        if first.get("evidence_excerpt"):
            out.append(
                f"- **What the source says (AI excerpt):** "
                f"“{_block(first['evidence_excerpt'])}”"
            )
        if first.get("correct_citation"):
            out.append(
                f"- **AI's correct citation:** {_block(first['correct_citation'])}"
            )
        urls: list[str] = list((second or first).get("source_urls") or [])
        if urls:
            out.append("- **Sources the AI read:** " + " · ".join(urls))
        if passage:
            out += [
                "",
                "<details><summary>Passage in the document</summary>",
                "",
                f"> {passage}",
                "",
                "</details>",
            ]
        out += [
            "",
            "- **Verdict:** ",
            "- **Error type, if confirmed:** ",
            "- **Note:** ",
            "",
        ]
    return "\n".join(out)


def write_draw(text_dir: Path | None) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    worksheet = REVIEW_DIR / "worksheet.md"
    if worksheet.exists() and re.search(
        r"(?m)^- \*\*Verdict:\*\* \S", worksheet.read_text(encoding="utf-8")
    ):
        raise SystemExit("worksheet already has verdicts; refusing to overwrite it")
    pop = population()
    sample = draw(pop)
    record = {
        "population": "unintentional problem citations in rubric-intent.json",
        "population_size": len(pop),
        "seed": SEED,
        "method": "random.Random(seed).sample over the population sorted by "
        "(task, ref); review order is draw order",
        "draw_size": DRAW_SIZE,
        "first_stage": FIRST_STAGE,
        "sample": [{k: r[k] for k in ("task", "ref", "final_status")} for r in sample],
    }
    (REVIEW_DIR / "sample.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    worksheet.write_text(render(sample, text_dir) + "\n", encoding="utf-8")
    print(f"drew {DRAW_SIZE} of {len(pop)} with seed {SEED}; wrote {REVIEW_DIR}")


def lower_bound(population_size: int, n: int, confirmed: int) -> int:
    """Smallest count of real errors in the population consistent at one-sided 95%."""

    def tail(errors: int) -> float:  # P(X >= confirmed) under the hypergeometric
        total = math.comb(population_size, n)
        return (
            sum(
                math.comb(errors, k) * math.comb(population_size - errors, n - k)
                for k in range(confirmed, min(n, errors) + 1)
            )
            / total
        )

    return next(e for e in range(population_size + 1) if tail(e) >= 0.05)


def tally() -> None:
    record: Json = json.loads((REVIEW_DIR / "sample.json").read_text(encoding="utf-8"))
    pop = population()
    expected = [(r["task"], r["ref"]) for r in draw(pop)]
    if [(r["task"], r["ref"]) for r in record["sample"]] != expected:
        raise SystemExit("sample.json does not match the seeded draw")
    text = (REVIEW_DIR / "worksheet.md").read_text(encoding="utf-8")
    heads = re.findall(r"(?m)^## (\d+)\. (\S+) — citation (\d+)", text)
    if [(t, int(r)) for _, t, r in heads] != expected:
        raise SystemExit("worksheet entries do not match the seeded draw")
    verdicts = [v.strip() for v in re.findall(r"(?m)^- \*\*Verdict:\*\*(.*)$", text)]
    done = [v for v in verdicts if v]
    if any(v not in VERDICTS for v in done):
        raise SystemExit(f"verdicts must be one of {VERDICTS}")
    first = done[:FIRST_STAGE]
    if len(first) < FIRST_STAGE:
        print(f"{len(done)} of {FIRST_STAGE} first-stage entries reviewed")
        return
    stop = all(v == VERDICTS[0] for v in first)
    reviewed = first if stop else done
    if not stop and len(done) < DRAW_SIZE:
        print(f"first ten not all confirmed; {len(done)} of {DRAW_SIZE} reviewed")
        return
    confirmed = sum(v == VERDICTS[0] for v in reviewed)
    bound = lower_bound(len(pop), len(reviewed), confirmed)
    print(
        f"{confirmed} of {len(reviewed)} confirmed"
        f"{' (stopped after the first ten)' if stop else ''}; at least {bound} of "
        f"{len(pop)} ({100 * bound / len(pop):.1f}%) are real errors at one-sided 95%"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("draw", help="write the sample and the reviewer worksheet")
    one.add_argument(
        "--text",
        type=Path,
        help="task text from harvey_citation_check.py extract, to quote each "
        "citation's surrounding passage in the worksheet",
    )
    sub.add_parser("tally", help="check the worksheet and report the bound")
    args = parser.parse_args()
    if args.command == "draw":
        write_draw(args.text)
    else:
        tally()


if __name__ == "__main__":
    main()
