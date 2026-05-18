# Cycle Data Card Requirements

This data card describes each published LegalForecast-MTD cycle. It is a scope
and reconstruction artifact, not a claim that the benchmark sample represents
all federal motions to dismiss.

## Intended Dataset

LegalForecast-MTD contains federal district-court motion-to-dismiss candidates
selected from public docket materials. The benchmark unit is a challenged claim
against a challenged defendant or defendant group. Models receive pre-decision
materials and predict whether each frozen unit will be fully dismissed in the
first written disposition resolving the target motion.

The dataset is designed for relative model comparison on the included
public-record task. It should not be used to estimate population outcome rates
for all federal MTDs.

## Source Systems

The acquisition runbook owns live-source commands and fallback policy; this data
card records what a specific cycle actually used. Each candidate must be
classified as `case.dev-only`, `case.dev-plus-fallback`, or `excluded`. Each
cycle data card must list:

- source systems and API versions if known;
- discovery queries and date windows;
- retrieval timestamps;
- source case IDs, docket IDs, document IDs, source URLs or reconstruction
  references;
- source class, fallback source, and fallback reason where supplemental
  retrieval was used;
- SHA-256 hashes for docket exports, source documents, extracted text,
  prediction units, labels, packets, prompts, scorers, and manifests.

Until `docs/acquisition.md` says the live route is unblocked, the data card
should state that case.dev seeded discovery and that official evaluation remains
blocked unless retrieval/export support or an approved public-record fallback
path produced clean packets.

## Inclusion Rules

An included clean case or motion must have:

- a federal district-court MTD or Rule 12(c) motion treated as an MTD-equivalent
  target;
- an identifiable written disposition resolving the target motion;
- enough pre-decision complaint, motion, briefing, docket, and metadata material
  to construct prediction units;
- frozen Stage A units before outcome labeling;
- outcome labels locked to the first written disposition;
- no known outcome leakage in the model packet or controlled docket tools.

## Exclusion Rules

Excluded candidates must appear in the exclusion ledger with exactly one primary
exclusion reason. Common exclusions include:

- no identifiable target MTD;
- unclean motion-to-order linkage;
- missing complaint, motion, briefing, disposition, or docket materials;
- final decision text, leaked minute order, oral ruling transcript, already
  dispositive R&R, or public reporting of the target disposition before
  evaluation;
- sealed or restricted material needed for scoring;
- insufficient text quality or failed extraction;
- duplicate related-case or MDL-family inflation that would distort the cycle;
- unresolved unitization or outcome-label ambiguity after review.

## Case-Mix Diagnostics

Each cycle must publish case-mix diagnostics for the included and excluded
candidate stream. Required fields include:

- district and circuit;
- NOS code and NOS macro-category where available;
- represented-party status and government-party status where available;
- public-company indicator where available;
- press-publicity sensitivity flag and tags for non-leaking public attention
  signals;
- judge and magistrate-judge availability;
- MDL flag, related-case-family ID, and MDL-family ID;
- number of claims, defendants, units, and units per motion;
- document completeness bucket;
- source-class distribution for `case.dev-only`, `case.dev-plus-fallback`, and
  `excluded` candidates;
- fallback usage and fallback reason;
- exclusion reason distribution;
- dominance triggers for district, NOS macro-category, related-case family, and
  MDL family.

If any dominance trigger fires, the report must include the pre-specified
capping, exclusion, or downweighting sensitivity result. These diagnostics
describe the benchmark's scope; they do not make the sample representative.
Press-publicity tags do not exclude a candidate unless public materials reveal
the target disposition before evaluation. Official reports should publish the
tag distribution and, when tagged cases are present in sufficient quantity,
compare headline scores with tagged cases excluded or separately sliced.
Search-hit metadata alone must not be presented as retained-packet case mix.
If retrieval fails before packet construction, report source-class and
exclusion-reason counts for attempted retrievals and defer district, NOS, judge,
unit-count, and dominance diagnostics until packets exist.

## Sensitive Materials

The benchmark excludes sealed materials and should not use restricted filings
that cannot be lawfully accessed or redistributed under the cycle's policy. If a
clean prediction would require sealed or restricted material, the candidate
should be excluded or represented only through non-sensitive metadata and a
clear exclusion note.

Cases involving minors, victims, immigration-sensitive facts, health records,
sexual-assault allegations, or similarly sensitive personal facts require extra
review before inclusion. The default publication artifact for those cases should
be hashes and reconstruction handles, not extracted text.

## Judge, Party, and Counsel Fields

Judge identity is included because this is an outcome-prediction benchmark and
judge-specific priors are legitimate predictive signal. The benchmark must not
pretend that judge identity is irrelevant. Instead, reports must quantify
reliance on that signal through judge-only and no-judge ablations, including:

- share of units using judge-specific priors;
- fallback hierarchy when judge history is sparse;
- judge-only baseline Brier;
- no-judge baseline or model ablation result;
- whether model rankings materially change when judge identity is removed.

Party and counsel metadata may also be predictive. Reports should disclose
which party/counsel fields were included, whether law-firm or public-company
indicators were used, and whether any party/counsel-only or no-party/counsel
ablation was run. These fields must not be used to profile individual lawyers
or parties outside benchmark analysis.

## Redistribution

Default publication should favor:

- manifests;
- source IDs and reconstruction handles;
- document and extracted-text hashes;
- prediction units and outcome labels;
- prompt, scorer, harness, and model-registry hashes;
- code needed to reconstruct packets where access is permitted.

Full extracted text should be published only when the document is clearly
public, appropriate for redistribution, and consistent with source-system terms
and the cycle's sensitive-material policy. Otherwise, publish reconstruction
instructions and hashes so users with lawful access can verify the artifacts.

## Corrections and Takedowns

Each cycle report should provide a contact path for incorrect labels,
unitization errors, leakage, sealed or restricted material, sensitive-party
concerns, and hash or reconstruction mismatches. The operational takedown,
errata, tombstone, and future-run exclusion procedure lives in
`docs/withdrawal_workflow.md`; the data card should record the public-safe
correction status and replacement manifest or erratum hash for the affected
cycle.
