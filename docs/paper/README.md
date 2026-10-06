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

The appendix on the human review of AI-flagged Harvey LAB criteria is generated from the review worksheet (`docs/harvey-lab-audit/litigation-dispute-resolution/human-review/worksheet.md`). The script writes the counts as LaTeX macros in the preamble and the per-criterion entries in the appendix, between `% BEGIN GENERATED LAB REVIEW` markers; the surrounding prose is hand-written. CI fails if the blocks drift from the worksheet.

```bash
uv run --frozen python docs/paper/analysis/lab_review.py --write-manuscript --manuscript docs/paper/LegalForecastBench-paper.tex
uv run --frozen python docs/paper/analysis/lab_review.py --check --manuscript docs/paper/LegalForecastBench-paper.tex
```

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
