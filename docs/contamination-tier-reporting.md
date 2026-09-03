# Contamination-tier reporting

This is the mechanical publication rule for two result tracks on a frozen
cohort. It is a reporting overlay. It does not change acquisition eligibility,
packet leakage filters, freeze codecs, or authenticated aggregate bytes.

Related code already in the tree:

- Model cutoff and eligibility metadata: `legalforecast.evals.model_registry`
  (`TrainingCutoffStatus`, `ModelRunMetadata`).
- Registry cutoff fields: `model_registries/*.json` via
  `ModelRegistryEntry.provider_training_cutoff` /
  `provider_training_cutoff_status`.
- Cohort contamination boundary: the existing `eligibility_anchor` (the
  earliest admitted decision date). Cycle 1 uses `2026-06-30`.

## Why two tracks

A contamination-resistant score requires the evaluated model's recorded
training cutoff to predate every scored decision in the cohort. Building a
fresh cohort for every model release is the expensive way to keep that claim.

Instead:

1. Freeze a cohort a few times per year.
2. Score a newly released model against that frozen cohort on release day.
3. If the model's cutoff still predates the cohort boundary, the score is
   contamination-resistant on that cohort.
4. If it does not, publish the score as **preliminary (non-contamination-resistant)**
   with a visible marker and a standard caveat.
5. When a later resistant cohort covers the same model, publish the paired
   score delta (**drift**) as its own metric.

Both tracks are official, viable benchmark results. Contamination-resistant is the gold standard, and building a fresh cohort for a newly released model is how the benchmark earns it; a preliminary score is reportable and first class alongside it rather than withheld until that cohort exists. The tier records which claim a score supports, never whether the score may be published.

Drift is the reason the two tracks are worth keeping distinct. Holding steady validates both the preliminary number and the contamination method. A large drop — resistant micro-Brier worse than the preliminary number — is a finding about that provider, and a near-zero drift is an equally publishable finding about how much contamination actually moves the score. Either way the delta is a headline result of this benchmark, not an artifact of when a cohort happened to be frozen.

## Vocabulary (do not collapse these)

| Term | Meaning | Not the same as |
| --- | --- | --- |
| `contamination_resistant` | Known training cutoff strictly predates the cohort `eligibility_anchor`. | Official vs community evidence. |
| `preliminary` | The contamination-resistant claim is not available for this (model, cohort) pair. | Publication-governance "Preliminary" (community evidence tier). |
| Rank tier | Bonferroni grouping on the leaderboard. | Contamination tier. |
| Estimand Tier-0 | Matched-harness observed difference (`dm0g.4.1.13`). | Contamination tier. |
| Result class (pre-anchor / post-anchor) | Whether the model's *first external deployment* predates the corpus anchor, the earliest decision date the cycle scores. | Contamination tier, which compares the model's *training cutoff* against the cohort `eligibility_anchor`. Both arms are official; see [publication-governance.md](publication-governance.md). |

Machine field: `contamination_tier`. Human marker for `preliminary`: a
trailing asterisk on the model label, plus this exact sentence wherever that
score is shown:

> Preliminary (non-contamination-resistant) result: the evaluated model's recorded training cutoff does not predate this cohort's contamination boundary, so the model theoretically could have seen these cases in training.

## Mechanical rule

Computed per `(model, cohort)` from existing fields only.

Let `C` be the cohort `eligibility_anchor` (date). Let `K` be
`provider_training_cutoff` when status is `known`.

- **contamination-resistant** iff status is `known` and `K < C`.
- **preliminary** otherwise, including:
  - `K >= C` (cutoff overlaps or postdates the decision window),
  - status `unknown` or `not_disclosed` (the resistant claim cannot be proven).

Date granularity matches eligibility: decision metadata is a calendar date,
so equality fails closed to preliminary. A model released after dataset freeze
is still contamination-resistant on that cohort if its recorded cutoff
predates `C`. Release-after-freeze is why we bother scoring the old cohort; it
is not a separate predicate.

This reporting rule keys off the recorded training cutoff. The separate release-date rule — which keys off first external deployment — decides the result class, and cohort acquisition, which decides which cases enter a cohort at all, lives in the companion private corpus repository. None of the three withholds a score; each decides which claim we print next to one.

## Sidecar (non-authoritative)

Official `legalforecast-official-aggregate-v1` envelopes (`scores.json`,
`report/leaderboard.json`, run cards, artifact index) stay byte-frozen.
Community `legalforecast.multiharness.community_report.v1` JSON stays
byte-frozen.

The tier flag lives in a sidecar document with `kind` equal to
`contamination_tier_sidecar` and `authoritative` equal to `false`. It must
not declare a `legalforecast.*.vN` `schema_version`. It is keyed by
`result_digest` (`sha256:` plus the SHA-256 of the frozen result bytes it
annotates — official `report/leaderboard.json` or the community comparison
JSON). A digest mismatch fails closed.

## Drift

Drift is defined only when the same `model_id` has both tiers, on two
different cohort identities:

`resistant_minus_preliminary_micro_brier = resistant_micro_brier - preliminary_micro_brier`

A single-tier pair is refused. Two scores of the same tier are refused. The
same `cohort_id` on both sides is refused.

## Rendering surfaces

Human-readable surfaces that know a row is preliminary must go through
`reported_model_label` and must emit `PRELIMINARY_CAVEAT`:

- Cycle 1 official site (`legalforecast.publication.official_report_site`)
- Leaderboard markdown/HTML when annotations are supplied
  (`legalforecast.reporting.leaderboard`)
- Community comparison markdown/HTML
  (`legalforecast.multiharness.reporting`)
- `legalforecast report` markdown/HTML when registry + boundary + cohort id
  are passed together

Unauthenticated overlay only: the official aggregate's own `leaderboard.md` and `leaderboard.html` remain the frozen dump and are not rewritten.
