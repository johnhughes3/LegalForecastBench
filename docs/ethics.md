# Ethics and Legal-Risk Note

LegalForecast-MTD evaluates model performance on a defined public-record legal
forecasting task. It is not legal advice, not a litigation-strategy tool, and
not a claim about the overall federal docket.

## Intended Use

Appropriate uses include:

- comparing models on the included benchmark sample;
- testing calibration, robustness, refusal, invalid-output, cost, and latency;
- studying whether public pre-decision litigation materials support calibrated
  outcome forecasts;
- auditing how benchmark results change under pre-registered sensitivity
  analyses.

Inappropriate uses include:

- advising a real client about a pending motion without lawyer review;
- ranking judges, lawyers, parties, or law firms for operational decisions;
- claiming population-level federal MTD accuracy from a limited public-record
  sample;
- using benchmark packets as a substitute for docket access, legal research, or
  professional judgment.

## Public Records and Privacy

Federal court filings are public in many circumstances, but public does not mean
risk-free. Redistribution can still create privacy, contractual, reputational,
and practical concerns. The benchmark therefore prefers hashes, source IDs,
metadata, labels, and reconstruction scripts over bulk redistribution of
extracted text.

Sealed and restricted filings are excluded. Sensitive public filings require
heightened review before inclusion, especially matters involving minors,
victims, immigration-sensitive facts, medical information, sexual-assault
allegations, or similarly sensitive personal material.

## Outcome Leakage

Outcome leakage is an ethics and validity problem. A benchmark packet must not
show the model the answer through final orders, leaked minute entries, oral
ruling transcripts, already-dispositive R&Rs, public reporting of the target
disposition, or related-case orders resolving materially identical units. When
leakage is discovered, the candidate should be excluded or the affected artifact
should be corrected and re-frozen.

## Judge Identity

Judge identity is included because the benchmark measures outcome prediction.
In litigation forecasting, judge-specific procedural and doctrinal tendencies
can be legitimate public signal. The ethical response is transparency and
ablation, not pretending the signal does not exist.

Every public report should include judge-only and no-judge ablations when the
cycle has enough data to make them meaningful. Reports should state how much of
the result depends on judge-specific priors and whether model rankings change
when judge identity is removed.

The benchmark should not be used to rate, shame, target, or market to judges.
Judge information is included only to measure and explain model performance on
the benchmark task.

## Party and Counsel Metadata

Party and counsel metadata can be relevant public forecasting signal, but it can
also invite misuse. Reports should disclose which fields were included and
should use aggregate diagnostics rather than individual lawyer or party
scorecards. Counsel and party fields should not be used outside benchmark
analysis to make client, staffing, marketing, or reputational decisions.

## Human Review

The benchmark relies on lawyer review for ambiguous unitization, difficult
outcome labels, LLM-label disagreement, low-confidence labels, and sensitive
publication decisions. Human review is part of the validity design; it does not
convert the benchmark into legal advice.

For label reliability studies, reviewers should receive clear instructions,
time tracking, confidence capture, and blind review conditions where applicable.
Decision excerpts may be shown to Stage B label reviewers, but decision text
must not be shown to Stage A unitizers except through the blinded repair
protocol specified for frozen-unit repair.

## Non-Representativeness

The benchmark does not claim to represent every federal MTD, every district, or
every case type. Public docket availability, case.dev/RECAP coverage, decision
windows, clean-packet yield, and exclusion rules all shape the sample. Reports
must state these limitations plainly and avoid population claims unless the
claim is explicitly limited to the benchmark sample and supported by the
registered analysis.

## Corrections, Redactions, and Takedowns

The project should maintain a correction path for label errors, unitization
errors, leakage, sensitive-party concerns, sealed-material mistakes, and
reconstruction mismatches. Corrections should be auditable: preserve prior hash
references where possible, publish an erratum or replacement manifest hash, and
explain the non-sensitive reason for the change.

If a document should not remain in public artifacts, remove or redact the
material and leave a non-sensitive placeholder explaining the correction. The
benchmark should never preserve sensitive text merely to keep an old hash
stable.
