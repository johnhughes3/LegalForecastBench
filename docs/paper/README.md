# LegalForecastBench working paper

[Manuscript source](LegalForecastBench-paper.tex) · [Reference metadata](references.json) · [Numerical inputs](data/empirical.json)

This directory is the canonical home of the working manuscript, **LegalForecastBench: Forecasting Judicial Decisions as a Test of Legal Reasoning Ability**. The paper reports the seventeen-configuration ranked comparison on 91 cases and 387 claim–defendant units, a separate summary experiment, and the proposed outcome-feedback research direction. That comparison matches the ranked leaderboard. The four summary conditions are reported separately and are not in the main table. GPT-4.1 is a reference and is not ranked. Draft annotations remain visible; a successful build is not a claim that the paper has completed scientific or editorial review.

## Edit and build

Edit `LegalForecastBench-paper.tex`. Its bibliography and vector figures are embedded, so it also compiles directly in a standalone LaTeX editor without additional project files. The bibliography in the `.tex` is authoritative; `references.json` supplies convenient structured metadata and links to original sources.

From the repository root, with TeX Live and `latexmk` installed:

```bash
bash docs/paper/build.sh
```

The output is `docs/paper/build/LegalForecastBench-paper.pdf`. Build products are ignored by Git. The script treats unresolved references and citations as errors and disables shell escape.

To use the same pinned TeX Live image as CI, with Docker available:

```bash
bash docs/paper/build.sh --container
```

The image reference is fixed by digest in [texlive-image.txt](texlive-image.txt), using the [TeX Live container maintained by Xu Cheng](https://github.com/xu-cheng/latex-docker). It targets `linux/amd64`; other architectures need Docker emulation. The container reads the checkout and writes only the build directory, with network access disabled during compilation. PDF metadata dates use the month, day, and year in the manuscript's `\date` line, so a later commit does not change the file. Locally edited sources produce working-tree previews, not a published paper version.

## Reproduction scope

The empirical inputs are aggregate results and references to result files already in this public repository. The paper keeps the cohort, conditions, and cost qualifications explicit. This package does not rerun model inference, relabel cases, or require court-document downloads or provider credentials. Public arithmetic reproduction and access to the underlying litigation records are different capabilities; see [Reproduce or audit a result](../reproduce-or-audit.md).

Regenerate the three result figures and their CSV data using Python's standard library:

```bash
uv run --no-project --python 3.14 python docs/paper/figures/make_figures.py
uv run --no-project --python 3.14 python docs/paper/figures/make_figures.py --check --manuscript docs/paper/LegalForecastBench-paper.tex
```

The generator writes `figures/figures-inline.tex` and three CSVs. Copy the regenerated result-figure bodies into the manuscript when changing the numerical inputs, preserving the standalone editor format. The check compares those bodies with the manuscript and fails on drift. The conceptual pipeline diagram is authored separately. CI runs this check before compiling. See the [figure reproduction notes](figures/README.md) for the manuscript panel and input limits.

### Harvey LAB human-review appendix

The counts in the appendix on the human review of AI-flagged Harvey LAB criteria are generated from the review worksheet (`docs/harvey-lab-audit/litigation-dispute-resolution/human-review/worksheet.md`). The script writes them as LaTeX macros in the preamble and writes the verdict table in the appendix, between `% BEGIN GENERATED LAB REVIEW` markers. CI fails if either block drifts from the worksheet.

The 25 per-criterion entries are edited by hand in the manuscript, which is their source of truth. Each entry quotes Harvey's criterion in a `labquote` block, gives the author's assessment and LAB's own grades in a table, and then the author's analysis. Changing a verdict means changing it in the entry and in the worksheet; the check fails when the two disagree, because the generated counts would then contradict the entries.

```bash
uv run --frozen python docs/paper/analysis/lab_review.py --write-manuscript --manuscript docs/paper/LegalForecastBench-paper.tex
uv run --frozen python docs/paper/analysis/lab_review.py --check --manuscript docs/paper/LegalForecastBench-paper.tex
```

### Pangram check of the author-written prose

`analysis/pangram_check.py` renders the manuscript to the plain text a reader sees and sends it to [Pangram](https://www.pangram.com/), an AI-text detector, as one document. It reports Pangram's result for the whole document and how many of its windows were flagged in each section. It is opt-in and is not part of the build or CI: every run spends Pangram credits (about 10,000 words, roughly $5 at the published rate of $0.05 per 100 words), and the script prints its own estimate before sending anything.

Text the author did not write is left out, and each omission appears in the document as `[...]`. Left out are passages between `% BEGIN AI-PREPARED` and `% END AI-PREPARED` comment lines in the manuscript, which mark what the paper's AI-use statement discloses as prepared with AI; the criteria and task titles quoted from Harvey LAB in the appendix; tables, figures, display equations, and the bibliography; and the generated blocks. LaTeX commands and source comments are never sent. To leave out another passage, wrap it in the two comment lines; they do not change the compiled paper.

To see exactly what would be sent, without a key and without spending credits, write the document to `docs/paper/build/pangram/paper.txt` (ignored by Git). It can also be pasted into Pangram's web app. This step needs `pandoc`.

```bash
uv run --frozen python docs/paper/analysis/pangram_check.py --extract-only --manuscript docs/paper/LegalForecastBench-paper.tex
```

To score it, put a Pangram API key in the `PANGRAM_API_KEY` environment variable and add Pangram's Python SDK for the one run. The script saves Pangram's raw response next to the document; `--verbose` prints an excerpt of every window Pangram did not label human-written, with its section.

```bash
uv run --frozen --with "pangram-sdk>=1.0" python docs/paper/analysis/pangram_check.py --manuscript docs/paper/LegalForecastBench-paper.tex
```

`--exclude-section` leaves out a whole section by its key in the printed table or part of its title, for example `--exclude-section A --exclude-section B`. Pangram's limits and prices are taken from its [API reference](https://docs.pangram.com/api-reference/introduction.md) and [input-size note](https://www.pangram.com/knowledge-hub/minimum-and-maximum-input-sizes).

### Within-case clustering

The [clustering analysis](analysis/README.md) reads the public unit-level exports listed in the significance input manifest. It regenerates outcome, prediction-error, and Brier-loss ICCs, bootstrap intervals, a label-permutation test, and the manuscript paragraph:

```bash
uv run --frozen python docs/paper/analysis/clustering.py --write-manuscript --manuscript docs/paper/LegalForecastBench-paper.tex
uv run --frozen python docs/paper/analysis/clustering.py --check --manuscript docs/paper/LegalForecastBench-paper.tex
```

The write command updates only the marked clustering paragraph, leaving the rest of the manuscript editable in a standalone LaTeX editor. CI reruns the analysis and rejects stale numerical outputs or manuscript text when inputs change. See the analysis notes for custom cohorts, weighting, and assumptions.

The research archive, downloaded third-party papers, source credibility notes, and private editorial material are maintained separately. Cite the original authorities linked from the bibliography, rather than redistributed copies of their papers.

## CI previews and the public paper page

The [Paper workflow](../../.github/workflows/paper.yaml) compiles changes to this directory with the pinned TeX Live image and uploads a 30-day preview artifact. It fails when that PDF differs from `site/public/papers/legalforecastbench-working.pdf`. Commit the artifact in the same pull request. main cannot accept an automatic follow-up commit, because every commit there must already have passed the Python tests. The site serves the committed file at `/papers/legalforecastbench-working.pdf`. The paper page reads its title and abstract from `LegalForecastBench-paper.tex` while the site builds, so those update with the manuscript and do not have a second copy in [paper.ts](../../site/src/data/paper.ts).

That working file is replaced when the manuscript changes. An immutable version is a separate, deliberate publication. Resolve the visible draft annotations and run:

```bash
bash docs/paper/build.sh --container --release
```

Add the reviewed PDF under a new name such as `site/public/papers/legalforecastbench-v0.1.pdf`, record the source revision in the publication PR, and append the version, date, and results release in `paper.ts`. Leave older version files unchanged. A correction is a new version with a change note. The preview artifact alone is not a published version.
