"""The manifest-staging lane: its IAM grant and the workflow that assumes it.

Kept out of ``tests/test_official_eval_infra.py``, which is already flagged
oversized in the architecture baseline.  The two halves belong together because
neither is safe alone: the grant is create-only, but IAM cannot tell an official
prefix from a supplementary one, so the workflow's pre-write lane fence is what
keeps a sibling freeze out of the prefix that already backs dispatched official
shards.  Manifest-run objects are written create-once and no role can delete
them, so a wrong prefix is unrecoverable.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from tests.official_infra_trust_helpers import (
    job_environment,
    job_grants_id_token_write,
    workflow_jobs,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_ROOT = ROOT / "infra" / "official-eval" / "policies"
STAGING_POLICY = POLICY_ROOT / "manifest-staging-policy.json.tftpl"
STAGING_WORKFLOW = ROOT / ".github" / "workflows" / "stage-manifest-run.yaml"
ENVIRONMENT_MANIFEST = ROOT / "infra" / "official-eval" / "github-environments.json"

PACKET_BUCKET_ARN = "arn:aws:s3:::lfb-packets"
RESULTS_BUCKET_ARN = "arn:aws:s3:::lfb-results"
ARTIFACTS_KMS_KEY_ARN = (
    "arn:aws:kms:us-east-1:123456789012:key/01234567-89ab-cdef-0123-456789abcdef"
)
STAGING_ENVIRONMENT = "legalforecastbench-official-eval-manifest-staging"
STAGING_ROLE_VARIABLE = "LFB_GITHUB_MANIFEST_STAGING_ROLE_ARN"
MANIFEST_RUN_PREFIX = "cycle-1/manifest-runs"

JsonObject = dict[str, object]


def _staging_policy() -> JsonObject:
    rendered = STAGING_POLICY.read_text(encoding="utf-8")
    for name, value in (
        ("artifacts_kms_key_arn", ARTIFACTS_KMS_KEY_ARN),
        ("packet_bucket_arn", PACKET_BUCKET_ARN),
        ("results_bucket_arn", RESULTS_BUCKET_ARN),
    ):
        rendered = rendered.replace(f"${{{name}}}", value)
    assert re.findall(r"\$\{[^}]+\}", rendered) == []
    loaded: object = json.loads(rendered)
    assert isinstance(loaded, dict)
    return cast(JsonObject, loaded)


def _statements() -> list[JsonObject]:
    raw = _staging_policy()["Statement"]
    assert isinstance(raw, list)
    return [cast(JsonObject, statement) for statement in cast(list[object], raw)]


def _workflow_text() -> str:
    return STAGING_WORKFLOW.read_text(encoding="utf-8")


def test_staging_policy_matches_the_staging_call_graph_exactly() -> None:
    """Pin the grant to exactly what the staging code path invokes.

    ``manifest_forecast_stage`` shells out to ``s3api put-object`` with
    ``--if-none-match "*"`` and ``s3api head-object``; the reconstruction step
    adds ``s3api get-object`` by exact key.  Nothing lists and nothing deletes.
    """

    assert _staging_policy() == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DecryptArtifactObjects",
                "Effect": "Allow",
                "Action": "kms:Decrypt",
                "Resource": ARTIFACTS_KMS_KEY_ARN,
            },
            {
                "Sid": "GenerateArtifactDataKeys",
                "Effect": "Allow",
                "Action": "kms:GenerateDataKey",
                "Resource": ARTIFACTS_KMS_KEY_ARN,
            },
            {
                "Sid": "ReadManifestRunArtifacts",
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": f"{RESULTS_BUCKET_ARN}/{MANIFEST_RUN_PREFIX}/*",
            },
            {
                "Sid": "CreateManifestRunArtifacts",
                "Effect": "Allow",
                "Action": "s3:PutObject",
                "Resource": f"{RESULTS_BUCKET_ARN}/{MANIFEST_RUN_PREFIX}/*",
                "Condition": {"Null": {"s3:if-none-match": "false"}},
            },
            {
                "Sid": "ReadModelPackets",
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": f"{PACKET_BUCKET_ARN}/model-packets/*",
            },
            {
                "Sid": "CreateModelPackets",
                "Effect": "Allow",
                "Action": "s3:PutObject",
                "Resource": f"{PACKET_BUCKET_ARN}/model-packets/*",
                "Condition": {"Null": {"s3:if-none-match": "false"}},
            },
        ],
    }


def test_every_staging_write_is_create_only() -> None:
    """A PutObject without the condition would silently overwrite a staged object."""

    puts = [
        statement
        for statement in _statements()
        if statement.get("Action") == "s3:PutObject"
    ]
    assert puts
    for statement in puts:
        assert statement.get("Condition") == {"Null": {"s3:if-none-match": "false"}}


def test_staging_role_cannot_reach_the_other_lanes_namespaces() -> None:
    """The new role must not quietly become a second cell or fan-in role."""

    rendered = json.dumps(_staging_policy())
    for forbidden in (
        "s3:ListBucket",
        "s3:ListBucketVersions",
        "s3:DeleteObject",
        "s3:PutObjectAcl",
        "s3:GetObjectVersion",
        "dynamodb:",
        "bedrock:",
        "/per-case/",
        "/shard-receipts/",
        "/manifests/",
        "/cycle-publication-state/",
        "/reports/",
    ):
        assert forbidden not in rendered, forbidden


def test_environment_manifest_provisions_the_staging_environment() -> None:
    loaded: object = json.loads(ENVIRONMENT_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    rows = cast(JsonObject, loaded)["environments"]
    assert isinstance(rows, list)
    matches = [
        cast(JsonObject, row)
        for row in cast(list[object], rows)
        if cast(JsonObject, row)["name"] == STAGING_ENVIRONMENT
    ]
    assert len(matches) == 1
    row = matches[0]
    assert row["aws_oidc_subject"] == (
        f"repo:johnhughes3/LegalForecastBench:environment:{STAGING_ENVIRONMENT}"
    )
    # Staging touches no provider, so it must carry no provider key.
    assert row["secrets"] == []
    assert row["variables"] == [
        "LFB_AWS_REGION",
        STAGING_ROLE_VARIABLE,
        "LFB_PACKET_BUCKET",
        "LFB_RESULTS_BUCKET",
    ]


def test_workflow_never_runs_with_local_or_long_lived_credentials() -> None:
    """OIDC only: no static keys, no checkout credentials, no ambient session."""

    text = _workflow_text()
    for forbidden in (
        "aws-access-key-id",
        "aws-secret-access-key",
        "AWS_ACCESS_KEY_ID: ${{ secrets",
        "AWS_SECRET_ACCESS_KEY: ${{ secrets",
        "aws configure",
        "aws sso login",
        "--profile",
    ):
        assert forbidden not in text, forbidden
    assert "persist-credentials: false" in text
    assert text.count("persist-credentials: false") == text.count(
        "uses: actions/checkout@"
    )
    # Anything ambient on the runner must be discarded before the assumed role
    # acts, so the only credentials in play are the ones OIDC just minted.
    assert "unset-current-credentials: true" in text
    assert "role-to-assume: ${{ env.LFB_GITHUB_MANIFEST_STAGING_ROLE_ARN }}" in text
    # Every AWS credential is cleared again once staging is done.
    for cleared in (
        "AWS_ACCESS_KEY_ID=",
        "AWS_SECRET_ACCESS_KEY=",
        "AWS_SESSION_TOKEN=",
        "AWS_SECURITY_TOKEN=",
    ):
        assert cleared in text


def test_only_the_staging_job_gets_an_oidc_token_and_it_binds_its_environment() -> None:
    jobs = workflow_jobs(_workflow_text())
    assert set(jobs) == {"validate-request", "stage"}
    # Input validation runs before any token exists, so a malformed or
    # cross-lane request never reaches AWS at all.
    assert not job_grants_id_token_write(jobs["validate-request"])
    assert not re.search(
        r"^    environment:", jobs["validate-request"], flags=re.MULTILINE
    )
    assert job_grants_id_token_write(jobs["stage"])
    assert job_environment(jobs["stage"]) == STAGING_ENVIRONMENT
    assert "permissions:\n  contents: read\n" in _workflow_text()


def test_workflow_refuses_cross_lane_requests_before_assuming_the_role() -> None:
    """Each lane must refuse the other's shape, in the credential-free job."""

    validate = workflow_jobs(_workflow_text())["validate-request"]
    # official: takes no sibling freeze and replaces no artifact.
    assert (
        "The official lane takes no freeze_bundle_path, freeze_bundle_sha256, "
        "or local_artifacts." in validate
    )
    # supplementary: a candidate that hashes to the pinned official bundle IS
    # the official freeze and must not reach the supplementary prefix.
    assert '"${FREEZE_BUNDLE_SHA256}" == "${OFFICIAL_FREEZE_BUNDLE_SHA256}"' in validate
    assert "The supplementary lane requires freeze_bundle_sha256." in validate
    # Only main, and only the exact dispatched commit.
    assert '"${GITHUB_REF}" != "refs/heads/main"' in validate
    assert '"${RELEASE_SHA}" != "${GITHUB_SHA}"' in validate


def test_expected_prefixes_are_the_two_documented_lane_shapes() -> None:
    validate = workflow_jobs(_workflow_text())["validate-request"]
    assert f'expected_prefix="{MANIFEST_RUN_PREFIX}/${{MANIFEST_DIGEST}}"' in validate
    assert (
        f'expected_prefix="{MANIFEST_RUN_PREFIX}/supplementary/'
        '${MANIFEST_DIGEST}/${FREEZE_BUNDLE_SHA256}"' in validate
    )


def test_lane_fence_runs_on_the_dry_run_plan_before_any_write() -> None:
    """The fence is only worth anything before the first create-once upload."""

    jobs = workflow_jobs(_workflow_text())
    stage = jobs["stage"]
    plan_index = stage.index("Prove the upload plan stays inside its own lane")
    write_index = stage.index("Stage the manifest run")
    assert plan_index < write_index
    fence = stage[plan_index:write_index]
    assert "--dry-run" in fence
    assert 'startswith($prefix + "/")' in fence
    assert 'startswith("model-packets/")' in fence
    assert "refusing to write" in fence
    assert 'contains("/supplementary/")' in fence


def test_workflow_emits_the_staged_freeze_raw_digest_scope_issuance_needs() -> None:
    """Staging rewrites artifact paths, so this digest is an output, not an input.

    Execution-scope issuance binds the STAGED bundle's raw SHA-256, which cannot
    be computed before staging runs.  Three digests exist for one freeze in this
    lane -- the pre-staging raw digest that keys the supplementary prefix, the
    freeze protocol's canonical ``hash_bundle_sha256``, and this one -- and
    substituting either of the others silently breaks scope verification.
    """

    text = _workflow_text()
    stage = workflow_jobs(text)["stage"]
    assert "staged_freeze_sha256: ${{ steps.stage.outputs.staged_freeze_sha256 }}" in (
        text
    )
    assert "staged_freeze_uri: ${{ steps.stage.outputs.staged_freeze_uri }}" in text
    assert 'echo "staged_freeze_sha256=${staged_freeze_sha256}"' in stage
    # Read from the stage record's own object entry for <prefix>/freeze.json,
    # which carries the raw digest of the bytes that were uploaded.
    assert '--arg key "${prefix}/freeze.json"' in stage
    assert "GITHUB_STEP_SUMMARY" in stage
    # And proven against the object that actually landed.
    assert "Verify the staged freeze reads back byte-identical" in stage
    assert "sha256sum --check --strict" in stage


def test_uploaded_artifact_carries_only_hash_bearing_metadata() -> None:
    """Run artifacts on a public repository are publicly downloadable.

    The rebuilt tree holds model packets and frozen corpus artifacts, so it is
    deleted before the upload step can run and never appears in its path list.
    """

    stage = workflow_jobs(_workflow_text())["stage"]
    upload_index = stage.index("- name: Upload stage record")
    upload = stage[upload_index:]
    assert "path: ${{ env.OUTPUT_ROOT }}/stage-record.json" in upload
    assert "WORK_ROOT" not in upload
    assert "artifact-root" not in upload
    assert "model-packets" not in upload
    clear_index = stage.index("Clear reconstructed corpus bytes and AWS credentials")
    assert clear_index < upload_index
    assert 'rm -rf "${WORK_ROOT}"' in stage
    assert "steps.clear_sensitive.outcome == 'success'" in upload


def test_workflow_pins_every_action_to_a_commit_sha() -> None:
    uses: list[str] = re.findall(r"^\s*uses: (\S+)", _workflow_text(), re.MULTILINE)
    assert uses
    for reference in uses:
        _, _, version = reference.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", version), reference


def test_concurrency_never_cancels_a_run_that_may_have_written(
    tmp_path: Path,
) -> None:
    """Create-once uploads are not interruptible: a cancelled run leaves a
    half-populated prefix that no role can clean up."""

    del tmp_path
    text = _workflow_text()
    assert "cancel-in-progress: false" in text
    assert "cancel-in-progress: true" not in text
    assert (
        "group: stage-manifest-run-${{ inputs.manifest_digest }}-${{ inputs.lane }}"
        in text
    )


def _dispatch_inputs(text: str) -> Mapping[str, str]:
    block = text.split("  workflow_dispatch:\n    inputs:\n", 1)[1]
    block = block.split("\npermissions:", 1)[0]
    return {
        name: ""
        for name in re.findall(r"^      ([a-z0-9_]+):\s*$", block, re.MULTILINE)
    }


def test_dispatch_surface_is_the_reviewed_input_set() -> None:
    assert set(_dispatch_inputs(_workflow_text())) == {
        "release_sha",
        "lane",
        "manifest_digest",
        "official_freeze_bundle_sha256",
        "freeze_bundle_path",
        "freeze_bundle_sha256",
        "local_artifacts",
        "dry_run",
    }
