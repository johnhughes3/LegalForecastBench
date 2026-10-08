# Working papers

This directory holds two working papers by the same author. Each lives in its own subdirectory with one `*-paper.tex` manuscript, its `references.json`, and any analysis scripts; the build, PDF, and Pangram tooling here is shared.

| Paper | Source | Committed PDF |
| --- | --- | --- |
| **Law as a Verifiable Domain: Using Real-World Judicial Outcomes to Evaluate AI Legal Reasoning** | [legalforecastbench/LegalForecastBench-paper.tex](legalforecastbench/LegalForecastBench-paper.tex) · [references](legalforecastbench/references.json) · [numerical inputs](legalforecastbench/data/empirical.json) | `site/public/paper/legalforecastbench-working.pdf` (served by the website) |
| **Auditing Harvey's Legal Agent Benchmark: Rubric and Citation Errors in Litigation Tasks** | [lab-audit/LAB-audit-paper.tex](lab-audit/LAB-audit-paper.tex) · [references](lab-audit/references.json) | `docs/papers/lab-audit/LAB-audit-paper.pdf` (not yet on the website) |

The LegalForecastBench paper reports the seventeen-configuration ranked comparison on 91 cases and 387 claim–defendant units, a separate summary experiment, and the proposed outcome-feedback research direction. That comparison matches the ranked leaderboard. The four summary conditions are reported separately and are not in the main table. GPT-4.1 is a reference and is not ranked. Draft annotations remain visible; a successful build is not a claim that the paper has completed scientific or editorial review.

The LAB audit paper reports the AI-assisted audit of Harvey LAB's litigation rubrics, the human review of a random sample of the flagged criteria (with its per-criterion appendix), the citation check of the task environments, and a motion-to-dismiss case study. The two papers cite each other.

## Edit and build

Edit the paper's `*-paper.tex`. Its bibliography and vector figures are embedded, so it also compiles directly in a standalone LaTeX editor without additional project files. The bibliography in the `.tex` is authoritative; `references.json` supplies convenient structured metadata and links to original sources.

From the repository root, with TeX Live and `latexmk` installed:

```bash
bash docs/papers/build.sh                     # LegalForecastBench paper
bash docs/papers/build.sh --paper lab-audit   # LAB audit paper
```

The output is `docs/papers/NAME/build/*-paper.pdf`, for example `docs/papers/legalforecastbench/build/LegalForecastBench-paper.pdf`. Build products are ignored by Git. The script treats unresolved references and citations as errors and disables shell escape.

To use the same pinned TeX Live image as CI, with Docker available:

```bash
bash docs/papers/build.sh --container
bash docs/papers/build.sh --paper lab-audit --container
```

The image reference is fixed by digest in [texlive-image.txt](texlive-image.txt), using the smaller `texlive-small` distribution from the [TeX Live containers maintained by Xu Cheng](https://github.com/xu-cheng/latex-docker). It targets `linux/amd64`; other architectures need Docker emulation. The container reads the checkout and writes only the build directory, with network access disabled during compilation. PDF metadata dates use the month, day, and year in the manuscript's `\date` line, so a later commit does not change the file. Locally edited sources produce working-tree previews, not a published paper version.

## Reproduction scope

The empirical inputs are aggregate results and references to result files already in this public repository. The paper keeps the cohort, conditions, and cost qualifications explicit. This package does not rerun model inference, relabel cases, or require court-document downloads or provider credentials. Public arithmetic reproduction and access to the underlying litigation records are different capabilities; see [Reproduce or audit a result](../reproduce-or-audit.md).

Regenerate the three result figures and their CSV data using Python's standard library:

```bash
uv run --no-project --python 3.14 python docs/papers/legalforecastbench/figures/make_figures.py
uv run --no-project --python 3.14 python docs/papers/legalforecastbench/figures/make_figures.py --check --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
```

The generator writes `figures/figures-inline.tex` and three CSVs. Copy the regenerated result-figure bodies into the manuscript when changing the numerical inputs, preserving the standalone editor format. The check compares those bodies with the manuscript and fails on drift. The conceptual pipeline diagram is authored separately. CI runs this check before compiling. See the [figure reproduction notes](legalforecastbench/figures/README.md) for the manuscript panel and input limits.

### Harvey LAB human-review counts

The counts from the human review of AI-flagged Harvey LAB criteria are generated from the review worksheet (`docs/harvey-lab-audit/litigation-dispute-resolution/human-review/worksheet.md`) by [`lab-audit/analysis/lab_review.py`](lab-audit/analysis/lab_review.py). It writes them as LaTeX macros in a preamble block between `% BEGIN GENERATED LAB REVIEW NUMBERS` markers, and writes the verdict table in the LAB audit paper's appendix between `% BEGIN GENERATED LAB REVIEW TABLE` markers. Each manuscript carries whichever blocks it uses: the LAB audit paper has both, and the LegalForecastBench paper has only the numbers, because its introduction cites two of them. CI fails if a block in either paper drifts from the worksheet.

The 25 per-criterion entries are edited by hand in the LAB audit paper, which is their source of truth. Each entry quotes Harvey's criterion in a `labquote` block, gives the author's assessment and LAB's own grades in a table, and then the author's analysis. Changing a verdict means changing it in the entry and in the worksheet; the check fails when the two disagree, because the generated counts would then contradict the entries.

```bash
uv run --frozen python docs/papers/lab-audit/analysis/lab_review.py --write-manuscript --manuscript docs/papers/lab-audit/LAB-audit-paper.tex
uv run --frozen python docs/papers/lab-audit/analysis/lab_review.py --write-manuscript --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
uv run --frozen python docs/papers/lab-audit/analysis/lab_review.py --check --manuscript docs/papers/lab-audit/LAB-audit-paper.tex
uv run --frozen python docs/papers/lab-audit/analysis/lab_review.py --check --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
```

### Pangram check of the author-written prose

`pangram_check.py` renders a manuscript to the plain text a reader sees and sends it to [Pangram](https://www.pangram.com/), an AI-text detector, as one document. It reports Pangram's result for the whole document and how many of its windows were flagged in each section. It is not part of the local build. Every scoring run spends Pangram credits (about 2,300 words for the LegalForecastBench paper and 8,200 for the LAB audit paper, roughly $1 and $4 at the published rate of $0.05 per 100 words); CI runs it on pull requests as described below, and the script prints its own estimate before sending anything and refuses to send if the estimate exceeds `--max-usd` (default $10).

Text the author did not write is left out, and each omission appears in the document as `[...]`. Left out are passages between `% BEGIN AI-PREPARED` and `% END AI-PREPARED` comment lines in the manuscript, which mark what the paper's AI-use statement discloses as prepared with AI; the criteria and task titles quoted from Harvey LAB in the appendix; tables, figures, display equations, and the bibliography; and the generated blocks. LaTeX commands and source comments are never sent. To leave out another passage, wrap it in the two comment lines; they do not change the compiled paper.

To see exactly what would be sent, without a key and without spending credits, write the document to `docs/papers/NAME/build/pangram/paper.txt` (ignored by Git). It can also be pasted into Pangram's web app. This step needs `pandoc`.

```bash
uv run --frozen python docs/papers/pangram_check.py --extract-only --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
uv run --frozen python docs/papers/pangram_check.py --extract-only --manuscript docs/papers/lab-audit/LAB-audit-paper.tex
```

To score it, put a Pangram API key in the `PANGRAM_API_KEY` environment variable and add Pangram's Python SDK for the one run. The script saves Pangram's raw response next to the document; `--verbose` prints an excerpt of every window Pangram did not label human-written, with its section.

```bash
uv run --frozen --with "pangram-sdk>=1.0" python docs/papers/pangram_check.py --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
```

In CI, the Paper workflow's *Pangram check* job runs this for each paper on every pull request from this repository and fails unless Pangram classifies all of the scored text as human-written: any passage it labels AI-generated or AI-assisted fails the check (override with the `PANGRAM_MAX_AI_FRACTION` repository variable). It needs the `PANGRAM_API_KEY` repository secret. It skips scoring a paper when the pull request leaves its scored text identical to the base branch's (for example a dependency bump or a PDF rebuild), and it caches each result by the exact text sent, so later commits and reruns in the same pull request reuse it rather than paying again; the report appears in the job summary, and the scored text and Pangram's response are uploaded as an artifact. Forks and Dependabot pull requests are not scored.

#### The website's own prose

`scripts/pangram_site.py` runs the same check over the built website, other than the paper. It reads `site/dist` (run `pnpm --dir site build` first), keeps the visible text of each page's main content, and leaves out the `/paper/` page; the Harvey LAB deliverable, task, and review pages, which hold AI model output, Harvey's task material, and AI audit findings; navigation, headers, footers, tables, code, and hidden elements; fragments under five words, such as statistic tiles; and any paragraph already scored on an earlier page, ignoring numbers, so template text on the model pages counts once. The rest, about 13,000 words, goes to Pangram as one document for roughly $6.50; the script refuses to send above `--max-usd` (default $15) and reports, for each page, how many of the windows covering it Pangram flagged. It is not run in CI.

```bash
pnpm --dir site build
uv run --frozen python scripts/pangram_site.py --extract-only
uv run --frozen --with pangram-sdk==1.0.0 python scripts/pangram_site.py --verbose
```

`--exclude-section` leaves out a whole section by its key in the printed table or part of its title, for example `--exclude-section A --exclude-section B`. Pangram's limits and prices are taken from its [API reference](https://docs.pangram.com/api-reference/introduction.md) and [input-size note](https://www.pangram.com/knowledge-hub/minimum-and-maximum-input-sizes).

### Within-case clustering

The [clustering analysis](legalforecastbench/analysis/README.md) reads the public unit-level exports listed in the significance input manifest. It regenerates outcome, prediction-error, and Brier-loss ICCs, bootstrap intervals, a label-permutation test, and the manuscript paragraph:

```bash
uv run --frozen python docs/papers/legalforecastbench/analysis/clustering.py --write-manuscript --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
uv run --frozen python docs/papers/legalforecastbench/analysis/clustering.py --check --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
```

The write command updates only the marked clustering paragraph, leaving the rest of the manuscript editable in a standalone LaTeX editor. CI reruns the analysis and rejects stale numerical outputs or manuscript text when inputs change. See the analysis notes for custom cohorts, weighting, and assumptions.

The research archive, downloaded third-party papers, source credibility notes, and private editorial material are maintained separately. Cite the original authorities linked from the bibliography, rather than redistributed copies of their papers.

## Committed PDFs, CI previews, and the public paper page

The [Paper workflow](../../.github/workflows/paper.yaml) compiles both papers with the pinned TeX Live image and uploads a 30-day preview artifact for each. It fails when a compiled PDF differs from the committed PDF in the table above. Commit the rebuilt PDF in the same pull request as the manuscript change; a local container build is byte-identical to CI's.

`bash docs/papers/check-pdfs.sh` runs the same build-and-compare locally and prints the `cp` command for any stale PDF. It is also a pre-push hook in the repository's [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml), run by `pre-commit` or `prek` (`prek run --hook-stage pre-push --all-files` to try it); on a push it builds only the papers whose files changed. Without Docker it warns and passes, and CI still enforces the check. `publish-working-copy.sh` copies a fresh LegalForecastBench build onto the website path. main cannot accept an automatic follow-up commit, because every commit there must already have passed the Python tests. The site serves the committed file at `/paper/legalforecastbench-working.pdf`. The paper page reads its title and abstract from `LegalForecastBench-paper.tex` while the site builds, so those update with the manuscript and do not have a second copy in [paper.ts](../../site/src/data/paper.ts).

The website serves only the LegalForecastBench paper. That working file is replaced when the manuscript changes. An immutable version is a separate, deliberate publication. Resolve the visible draft annotations and run:

```bash
bash docs/papers/build.sh --container --release
```

Add the reviewed PDF under a new name such as `site/public/paper/legalforecastbench-v0.1.pdf`, record the source revision in the publication PR, and append the version, date, and results release in `paper.ts`. Leave older version files unchanged. A correction is a new version with a change note. The preview artifact alone is not a published version.
