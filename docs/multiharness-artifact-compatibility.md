# Multi-harness artifact compatibility baseline

This compatibility baseline freezes the community artifact behavior inherited from the closed `054` platform before score and evaluation semantics are added.

The executable fixtures live in `tests/fixtures/multiharness-artifact-characterization/manifest.json`. That manifest is the inventory of production readers and writers covered by the baseline; adding another compatibility reader requires adding it to the inventory and proving its behavior in `tests/test_multiharness_artifact_characterization.py`.

## Versioned migration readers

| Artifact | Accepted schema | Production reader | Rewrite expectation |
| --- | --- | --- | --- |
| Canonical task | `legalforecast.multiharness.task.v1` | `CanonicalTask.from_record` | `to_record()` reproduces the fixture exactly. |
| Public run summary | `legalforecast.multiharness.community_run_summary.v1` | `CommunityRunSummary.from_record` | `to_record()` reproduces the fixture exactly. |
| Submission shard | `legalforecast.multiharness.community_shard.v1` | `CommunitySubmissionShard.from_record` | `to_record()` reproduces the fixture exactly. |
| Current submission package | `legalforecast.multiharness.community_submission_manifest.v1` | `CommunitySubmissionManifest.from_record` and `validate_submission_file` | Nested run summaries and shards retain their own version checks, rewrite exactly, and pass file-and-hash validation. |
| Legacy submission envelope | `legalforecast.multiharness.community_submission.v1` | `CommunitySubmission.from_record` | The reader remains available for migration and rewrites the legacy shape exactly. |
| Legacy aggregate envelope | `legalforecast.multiharness.community_aggregate.v1` | `CommunityAggregate.from_record` | The reader remains available for migration and rewrites the legacy shape exactly. |

Every versioned reader accepts only its exact schema version. Missing or unknown versions fail closed with `MultiHarnessValidationError`; they are never guessed, coerced, or promoted to a newer schema.

## Generated aggregate and publication artifacts

`CommunityComparisonRow` is the current aggregate-row writer contract. The JSON, CSV, Markdown, and HTML renderers are write-only publication surfaces rather than migration readers, so their exact golden output is frozen without implying that arbitrary report files may be ingested as submissions.

`registry/site-summary.json` is an input to the community static-site renderer and must declare `legalforecast.multiharness.community_aggregate_bundle.v1`. The renderer rejects an unknown bundle version before using any rows.

## Migration policy

A future schema change must add a new version and explicit reader instead of changing a V1 reader in place. The change must retain these fixtures, add new-version fixtures, document the conversion direction, and prove both legacy read/rewrite equivalence and unknown-version refusal. Removal of a legacy reader requires a separately reviewed deprecation decision and cannot be inferred from a new writer becoming available.

The full source-checkout release smoke remains the final compatibility gate because it exercises packaging, CLI smokes, fixture E2E flows, multiharness no-network smokes, and installed wheel and source-distribution behavior together.
