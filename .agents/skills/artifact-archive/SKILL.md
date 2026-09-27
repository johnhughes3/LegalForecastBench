---
name: artifact-archive
description: Preserve surviving GitHub Actions artifact ZIPs in protected durable storage and verify archive coverage.
---

Use `gh workflow run archive-github-artifacts.yaml --ref main` when the owner requests durable preservation of existing artifacts. The job uses `legalforecastbench-official-eval-fan-in` and its existing S3 role. Preserve the protected-environment approval boundary; no local S3 writes, IAM widening, or provider calls are needed.

The workflow inventories every currently available artifact in this repository, including checkpoints from failed runs. Original ZIPs go to `s3://${LFB_RESULTS_BUCKET}/reports/github-artifacts/multi-ablation/<owner>/<repository>/artifacts/<artifact-id>.zip`. It never extracts artifact contents. Names and source workflow identities remain in the snapshot and result indexes under `runs/`. This is preservation, not canonical benchmark publication.

The implementation entrypoint is `uv run python -m legalforecast.artifact_archive --help`. Normal operation is the protected workflow. Existing matching S3 objects are reused through the shared create-once helper; conflicting content fails. Per-artifact failures do not discard successful copies, but the run must report incomplete coverage and fail if any selected artifact could not be copied.

Inspect the final index and job conclusion before claiming completion. Report selected, archived, failed, and already-expired counts; a new artifact created after the snapshot is outside that invocation. Rerun through the same workflow to cover newer artifacts or remaining copies. Retain failed-copy evidence and never treat an expiring GitHub index alone as proof that the ZIPs reached S3.
