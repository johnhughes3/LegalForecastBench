# Prior Art and Positioning

LegalForecast-MTD should not be positioned as the first system to predict litigation outcomes or motions to dismiss. The stronger and more defensible claim is narrower: an open, contamination-controlled benchmark for probabilistic, claim-defendant-level MTD forecasting from the pre-decision record, with empirical metadata and judge-history baselines scored next to frontier models.

## Commercial MTD Prediction

[Pre/Dicta](https://www.pre-dicta.com/) publicly markets motion-level federal litigation prediction and claims 85% accuracy on motion prediction, including motions to dismiss. Third-party coverage describes the product as predicting MTD outcomes from docket number and party/judge/case metadata rather than the legal briefs themselves, which is direct market evidence that metadata priors can be strong on this task.

That makes `judge_history`, `court_nos_motion_base_rate`, and `metadata_only` not secondary diagnostics but central adversarial baselines. A model that beats raw micro-Brier but fails to beat the informed baseline has not shown that reading the record added value. Once a historical baseline corpus is frozen, public leaderboards should headline skill over the informed baseline, using raw micro-Brier as the base proper scoring metric and the baseline-relative score as the practitioner-facing interpretation. Cycle 1 predates that corpus: it publishes relative model comparisons only, states that scope explicitly, and makes no skill-over-baseline claim.

## Legal Judgment Prediction Literature

Legal judgment prediction is a mature research area. Close analogues include [Katz, Bommarito, and Blackman on SCOTUS prediction](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0174698), [Aletras et al. on ECtHR decisions](https://discovery.ucl.ac.uk/id/eprint/1522370/), [Chalkidis et al. on neural ECtHR judgment prediction](https://aclanthology.org/P19-1424/), [CAIL2018](https://arxiv.org/abs/1810.05851), [Swiss-Judgment-Prediction](https://aclanthology.org/2021.nllp-1.3/), and [CLC-UKET](https://aclanthology.org/2024.nllp-1.7/).

The key distinction is not that those projects are unimportant; it is that many legal judgment prediction setups predict outcomes from court-authored fact sections, judgment texts, or post-hoc summaries. Medvedeva, Wieling, and Vols emphasize the difference between outcome identification, outcome-based judgment classification, and prediction in a realistic professional setting in ["Rethinking the field of automatic prediction of court decisions"](https://d-nb.info/1257127764/34). LegalForecast-MTD is intended to stay on the realistic side of that line: the model sees the pre-decision litigation record, not the judge's later explanation of the decision.

CLC-UKET is the closest recent legal benchmark analogue because it constructs a UK Employment Tribunal case outcome prediction task and includes human predictions as a performance reference. LegalForecast-MTD should cite it, and should treat an expert-lawyer comparison group as a natural follow-on once the official data path is stable.

## ForecastBench

[ForecastBench](https://openreview.net/forum?id=lfPkGWXLLf) is the closest benchmark-design analogue outside law: dynamic question sets, post-cutoff evaluation, Brier scoring, and human comparison groups. LegalForecast-MTD borrows the contamination-resistant forecasting pattern but applies it to a court-record task with objective public resolutions and a fixed legal unit of prediction.

The contamination guarantee should be stated retrospectively. The anchor is the first documented external deployment of the evaluated artifact, including a restricted preview. It deliberately uses a later, independently observable event than the provider-stated knowledge cutoff and applies no extra calendar-day buffer. A temporary suspension, re-release, or later general availability does not move it. The deployment anchor means a model whose served weights were frozen at that point could not have trained on later rulings, but it does not prove that a provider never updated a mutable alias afterward. That is why official runs must pin registry metadata, record provider-served model versions, and publish residual-risk language.

## Harvey LAB

Harvey LAB is a different benchmark family: long-horizon legal work-product tasks, tools, documents, and expert-written criteria. Harvey describes LAB as evaluating agents on real legal work, and Vals AI reports both all-pass final scores and per-criterion pass rates.

The clean critique is not that all-pass aggregation is inherently wrong. All-pass can be a conservative way to reflect legal deliverable risk, where one missed material issue can matter. The relevant limitation for LegalForecast-MTD positioning is that issue-spotting rubrics can be recall-heavy unless they also penalize spurious issues. A model that lists many extra risks may improve recall without being well calibrated. LegalForecast-MTD is complementary because Brier scoring penalizes both false confidence and missed probability mass against objective ground truth.

## Positioning Language

Use:

- "LegalForecast-MTD measures whether frontier models add predictive value beyond metadata and judge-history baselines when given the actual pre-decision record."
- "The benchmark is an open, contamination-controlled, probabilistic MTD forecasting benchmark at the claim-defendant level."
- "The primary interpretation is Brier skill over the informed baseline; raw micro-Brier remains the underlying proper scoring metric."
- "The release-date anchor is a retrospective contamination control, not a prospective promise about provider aliases."

Avoid:

- "No one else predicts motions to dismiss."
- "This is the first legal outcome prediction benchmark."
- "High accuracy proves legal reasoning."
- "A model is contamination-free without pinned release metadata and provider-served version capture."

## Release Checklist

Before a public cycle, the release package should include a prior-art paragraph citing the commercial MTD prediction market and the legal judgment prediction literature, and a limitations paragraph explaining that prediction from the pre-decision record is a hypothesized proxy for legal reasoning, not a direct measure of correctness. Once the historical baseline corpus exists, the package should also include baseline rows for `global_base_rate`, `court_nos_motion_base_rate`, `metadata_only`, and `judge_history`, plus a leaderboard column for skill over the selected informed baseline; until then, each cycle must state explicitly that it publishes relative model comparisons only.
