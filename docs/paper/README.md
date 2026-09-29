# LegalForecastBench working paper

[Manuscript source](LegalForecastBench-paper.tex) · [Reference metadata](references.json) · [Numerical inputs](data/empirical.json)

This directory is the canonical home of the working manuscript, **LegalForecastBench: Forecasting Judicial Decisions as a Test of Legal Reasoning Ability**. The paper reports the original twelve-configuration comparison on 91 cases and 387 claim–defendant units, a separate summary experiment, and the proposed outcome-feedback research direction. Later models on the live leaderboard are outside this fixed comparison. Draft annotations remain visible; a successful build is not a claim that the paper has completed scientific or editorial review.

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

The image reference is fixed by digest in [texlive-image.txt](texlive-image.txt), using the [TeX Live container maintained by Xu Cheng](https://github.com/xu-cheng/latex-docker). It targets `linux/amd64`; other architectures need Docker emulation. The container reads the checkout and writes only the build directory, with network access disabled during compilation. PDF metadata dates use the checked-out commit time. Locally edited sources produce working-tree previews, not a published paper version.

## Reproduction scope

The empirical inputs are aggregate results and references to result files already in this public repository. The paper keeps the original cohort, conditions, cost qualifications, and missing unit-level coverage explicit. This package does not rerun model inference, relabel cases, or require court-document downloads or provider credentials. Public arithmetic reproduction and access to the underlying litigation records are different capabilities; see [Reproduce or audit a result](../reproduce-or-audit.md).

Regenerate the three result figures and their CSV data using Python's standard library:

```bash
uv run --no-project --python 3.14 python docs/paper/figures/make_figures.py
uv run --no-project --python 3.14 python docs/paper/figures/make_figures.py --check --manuscript docs/paper/LegalForecastBench-paper.tex
```

The generator writes `figures/figures-inline.tex` and three CSVs. Copy the regenerated result-figure bodies into the manuscript when changing the numerical inputs, preserving the standalone editor format. The check compares those bodies with the manuscript and fails on drift. The conceptual pipeline diagram is authored separately. CI runs this check before compiling. See the [figure reproduction notes](figures/README.md) for the fixed panel and input limits.

The research archive, downloaded third-party papers, source credibility notes, and private editorial material are maintained separately. Cite the original authorities linked from the bibliography, rather than redistributed copies of their papers.

## CI previews and published versions

The [Paper workflow](../../.github/workflows/paper.yaml) compiles changes to this directory and uploads a PDF preview named for the tested revision, retained for 30 days. Download it from the corresponding Actions run. A preview is not automatically registered as a version on the public paper page.

To prepare a publication build, first resolve the visible draft annotations and run:

```bash
bash docs/paper/build.sh --container --release
```

Publish the reviewed PDF from the selected source revision under a new immutable name such as `site/public/papers/legalforecastbench-v0.1.pdf`. Record that source revision or tag in the publication PR, append the version/date/results-release entry in [paper.ts](../../site/src/data/paper.ts), and synchronize the site's title and abstract with the published paper. Existing published PDFs remain unchanged when the working manuscript advances. Corrections receive a new version and change note. The site's normal static build serves these versioned files; an Actions preview artifact alone does not publish them.
