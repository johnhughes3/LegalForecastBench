# Reproduce the paper figures

Run from the repository root:

```bash
uv run --no-project --python 3.14 python docs/papers/legalforecastbench/figures/make_figures.py
uv run --no-project --python 3.14 python docs/papers/legalforecastbench/figures/make_figures.py --check --manuscript docs/papers/legalforecastbench/LegalForecastBench-paper.tex
```

The generator uses Python's standard library and [the empirical inputs](../data/empirical.json). Mean summary probabilities are recomputed from the public JSONL exports named in that file; missing exports are errors. Input paths are relative to the repository, with the public source revision recorded in the empirical provenance. The code does not fetch court documents or call models.

| Generated file | Content |
| --- | --- |
| `figure1_brier_ranked.csv` | The twenty ranked manuscript configurations, ordered by micro-Brier, with equal-case Brier and descriptive context. |
| `figure2_high_confidence_diagnostic.csv` | Confidence and empirical accuracy on each model's own high-confidence subset. These are not matched subsets or a full reliability diagram. |
| `figure3_summary_experiment.csv` | Summary conditions (three on shared Luna summaries, one on separate Grok summaries), the full-document Luna reference, and the constant 0.5 forecast. The full-document row differs in both information access and interaction. |
| `figure4_cost_frontier.csv` | Standard-rate cohort cost and micro-Brier for each priced configuration, flagging the observed Pareto frontier (no other configuration is both no costlier and no worse). |
| `figures-inline.tex` | Four generated TikZ bodies matching the manuscript's results figures, in manuscript order. |

The manuscript embeds the TikZ bodies so it remains usable in a standalone editor. After an intentional data or plotting change, regenerate these files and copy the four result-figure bodies into the manuscript; `--check --manuscript ...` verifies consistency without modifying it. Figure captions and the conceptual pipeline diagram remain authored in the manuscript. Connecting segments show sensitivity to weighting or differences between confidence and accuracy, not uncertainty intervals.

The manuscript panel is deliberately fixed to the twenty ranked configurations. GPT-4.1 is an unranked reference in the broader paired comparison and is not plotted with the ranked panel. Adding a model to the live website does not add it to this paper's comparison.
