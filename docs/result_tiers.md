# Result Tiers and Public Alpha Publication

This policy governs v0.1 alpha result artifacts, future v1.0 official
leaderboards, and community-submitted results. It separates provenance tiers so
public feedback can be accepted without blurring what is canonical.

## Result Tiers

LegalForecast-MTD reports must use these tiers:

- `official`: a maintainer or trusted operator ran the benchmark from frozen
  protocol artifacts, validated run cards, retained accounting records, and
  reviewed labels. Only this tier is canonical for project-published
  leaderboard claims.
- `verified-community`: a community run that maintainers independently
  reproduced or audited against the submitted artifacts. This tier can be
  discussed as corroborating evidence, but it is not mixed into the official
  leaderboard unless maintainers rerun it as an `official` result.
- `community-unverified`: a self-reported community run. It may be listed for
  transparency or debugging, but it is non-canonical and must not be merged
  into official tables, rank deltas, model claims, or release headlines.

Every public table or report must state its tier. If a page shows multiple
tiers, official rows must be structurally separated from
community-unverified rows. The canonical leaderboard is always the official
tier unless maintainers explicitly publish a replacement official run.

## Publication Layout

Public alpha artifacts should be laid out under a results root that mirrors the
run tier and release channel:

```text
results/
  alpha/
    v0.1/
      README.md
      runs/
        <run_id>/
          artifact-index.json
          artifact-manifest.json
          report/
            leaderboard.json
            leaderboard.csv
            leaderboard.md
            leaderboard.html
          run-cards/
            <provider>_<model>_<run_label>.json
          manifests/
            cycle-manifest.jsonl
            cycle-freeze.json
          errata/
            <erratum_id>.md
      community-unverified/
        <submission_id>/
          README.md
          run-card.json
          submitted-results.json
          artifact-index.json
  official/
    v1.0/
      <cycle_id>/
        README.md
        runs/
        reports/
        errata/
```

The tracked repository does not need to contain every generated result artifact.
Generated outputs may live in release assets, object storage, or a separate
publication repository, but each published bundle must preserve this shape or
include a manifest that maps its paths to the same roles.

## Required Artifacts

An official or verified-community bundle must include frozen artifacts that
support independent reproduction:

- a validated run card for each model/run condition;
- leaderboard outputs in machine-readable and human-readable forms;
- the artifact index and artifact manifest from the run;
- frozen manifest, protocol, unit, label, prompt, scorer, harness, model
  registry, and baseline hashes where applicable;
- accounting records or a non-sensitive accounting summary;
- the data card, redistribution policy, and reconstruction instructions for
  the cycle;
- any errata or supersession records.

Community-unverified submissions should include the same materials where
possible, but missing materials are allowed only if the submission bundle is
clearly marked non-canonical. Submissions must not include API keys, provider
account identifiers, sealed or restricted filings, or source-document text that
the project has not approved for redistribution.

## Retention and Supersession

Published alpha artifacts are retained for auditability. Do not silently delete
or rewrite a public alpha run after publication. If a run is wrong, publish an
erratum or replacement record with these fields:

```json
{
  "supersedes": "alpha-v0.1/run-001",
  "superseded_by": "alpha-v0.1/run-001-r2",
  "reason": "Corrected model-registry hash in run cards.",
  "published_at": "2026-05-17T00:00:00Z"
}
```

Superseded alpha runs remain discoverable but must be labeled
`non-canonical-superseded`. v1.0 canonical results are separate from alpha
artifacts and must not inherit alpha leaderboard claims by default. Private
scratch runs under `tmp/` or an unshared local workspace may be deleted at any
time unless they have been cited in a public report.

## Community Submission Process

Community submissions, if accepted, should arrive as a single directory or
archive containing:

- `README.md` with submitter contact, run date, environment summary, and result
  tier requested;
- one validated `run-card.json` per model/run condition;
- `submitted-results.json` or `leaderboard.json` with the reported scores;
- `artifact-index.json` listing hashes for every artifact used to generate the
  result;
- a short statement that the submitter had lawful access to any source
  materials used and did not include sealed, restricted, or unapproved
  redistributed filings.

Maintainer review follows this path:

1. Validate submitted run cards and artifact hashes.
2. Confirm the submission uses the published protocol and allowed packet
   materials for the named cycle.
3. Recompute scores from submitted outputs when labels and packets are
   available.
4. Reproduce the run locally or with a maintainer-controlled account before
   promoting it to `verified-community`.
5. Rerun under maintainer control before including it in an `official`
   leaderboard.

Until those steps complete, the submission remains `community-unverified`.

## No Hosted Community Runner

The v0.1 alpha does not provide a hosted community bring-your-own-key runner.
Community users run the benchmark locally and keep model-provider tokens in
their own environment. The project does not take custody of community API keys,
pay provider bills for community runs, or expose a shared service that can call
models on behalf of unknown users.

This boundary is intentional. A hosted runner would create token-custody,
billing, abuse, rate-limit, logging, and data-visibility risks that are outside
the v0.1 release scope. Official runs remain maintainer-controlled; community
runs remain local unless a later release explicitly adds a separately reviewed
hosted service.
