---
name: artifact-archive
description: Preserve surviving GitHub Actions artifact ZIPs in protected durable storage and verify archive coverage.
---

The workflow runs automatically (`workflow_run`) after every Run Benchmark, Recover Benchmark, Protected Labels Fan In, Score Terminal Release, and Prepare Jev Summaries run, scoped to that run's artifacts. Use `gh workflow run archive-github-artifacts.yaml --ref main` for a full inventory, or add `-f source_run_id=<run-id>` to re-archive one run. The job uses `legalforecastbench-official-eval-fan-in` and its existing S3 role. Preserve the protected-environment approval boundary; no local S3 writes, IAM widening, or provider calls are needed.

The workflow inventories every currently available artifact in this repository, including checkpoints from failed runs. Original ZIPs go to `s3://${LFB_RESULTS_BUCKET}/reports/github-artifacts/multi-ablation/<owner>/<repository>/artifacts/<artifact-id>.zip`. It never extracts artifact contents. A deterministic pointer at `by-run/<source-run-id>/<artifact-name>/<artifact-id>.json` names each ZIP and its GitHub SHA-256 digest; fan-in lists that prefix to restore an expired forecast package. An S3 denial prints the AWS error in the job log and fails the run. Names and source workflow identities remain in the snapshot and result indexes under `runs/`. This is preservation, not canonical benchmark publication.

The implementation entrypoint is `uv run python -m legalforecast.artifact_archive --help`. Normal operation is the protected workflow. Existing matching S3 objects are reused through the shared create-once helper; conflicting content fails. Per-artifact failures do not discard successful copies, but the run must report incomplete coverage and fail if any selected artifact could not be copied.

Inspect the final index and job conclusion before claiming completion. Report selected, archived, failed, and already-expired counts; a new artifact created after the snapshot is outside that invocation. Rerun through the same workflow to cover newer artifacts or remaining copies. Retain failed-copy evidence and never treat an expiring GitHub index alone as proof that the ZIPs reached S3.

Artifact downloads run before assuming the S3 role. The downloader checks GitHub API quota in bounded batches and waits for its reset when necessary; the upload phase then obtains fresh one-hour AWS credentials. Large inventories can therefore take one or more quota windows. Download failures remain failures even if successfully downloaded ZIPs are preserved.
