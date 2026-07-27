# Frozen-batch Firecrawl observation run v1

Schema identifier: `legalforecast.frozen_batch_firecrawl_observation_run.v1`

This run replaces only the CourtListener REST docket-reconstruction transport for an already frozen direct-search priority tranche. It does not create a new cohort, rerank candidates, change the eligibility window, relax screening, purchase documents, or authorize evaluation.

The durable Firecrawl run configuration binds:

- the source cycle hash, batch ID, and batch digest;
- the frozen ranking-policy and deferred-frontier commitments;
- the exact selected candidate set and its frozen traversal order;
- the eligibility anchor and decision-window upper bound;
- the raw artifact root, pagination ceiling, retry ceiling, circuit threshold, concurrency ceiling, proxy mode, browser mode, and worst-case credits per request; and
- the scheduler's target-HTTP pressure policy version.

Candidate IDs supplied on the command line act only as a set selector. The adapter always restores their order from the frozen priority records. With no explicit IDs, a new run freezes the candidates that do not have a current terminal observation. A resumed run restores its original selected scope from the durable configuration, skips candidates that have since become terminal, and retains each candidate's batch-global ordinal for page scheduling.

Every requested page is authorized in the cycle-wide Firecrawl ledger before the provider call. Successful raw HTML is committed durably by the existing scheduler. Pagination uses strict newest-first CourtListener URLs and exposes a docket to screening only after full exhaustion or a conservative pre-anchor boundary proof.

The reconstructed rows terminate in the same provider-independent canonical screen used by REST observation. That screen applies:

- the frozen first-written-disposition anchor and decision-window upper bound;
- unbounded first-disposition detection;
- the strict MTD/Rule 12(c)/Rule 7012 screen;
- deterministic motion-to-disposition linkage;
- operative-complaint requirements for bankruptcy adversary proceedings; and
- outcome-leakage screening over model-visible predecision materials.

Canonical terminal outcomes use the existing cycle reason taxonomy. Missing pages, page-cap exhaustion, malformed or ambiguous HTML, unparseable disposition dates, and other incomplete proof are append-only transient observations. They do not become a candidate's current observation and therefore remain retryable.

The command has no PACER, RECAP Fetch, fee acknowledgment, purchase, model evaluation, freeze, or dispatch path.
