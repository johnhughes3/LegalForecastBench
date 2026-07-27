from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/official-s3-access-validation.yaml").read_text(
    encoding="utf-8",
)
RUN_BENCHMARK_WORKFLOW = (ROOT / ".github/workflows/run-benchmark.yaml").read_text(
    encoding="utf-8",
)


def _job_slice(source: str, start_marker: str, end_marker: str | None = None) -> str:
    start_count = source.count(start_marker)
    if start_count != 1:
        raise AssertionError(
            f"expected job marker {start_marker!r} exactly once; found {start_count}"
        )
    remainder = source.split(start_marker, maxsplit=1)[1]
    if end_marker is None:
        return remainder
    end_count = remainder.count(end_marker)
    if end_count != 1:
        raise AssertionError(
            f"expected following job marker {end_marker!r} exactly once; "
            f"found {end_count}"
        )
    return remainder.split(end_marker, maxsplit=1)[0]


CELL_JOB = _job_slice(
    WORKFLOW,
    "  validate-official-s3-access:",
    "  validate-fan-in-access:",
)
FAN_IN_JOB = _job_slice(
    WORKFLOW,
    "  validate-fan-in-access:",
    "  validate-cell-receipt-denial:",
)
CELL_RECEIPT_DENIAL_JOB = _job_slice(
    WORKFLOW,
    "  validate-cell-receipt-denial:",
)


def test_job_slice_rejects_a_missing_or_duplicated_marker() -> None:
    malformed = (
        ("jobs:\n", "  cell:", None, "expected job marker"),
        ("  cell:\n  cell:\n", "  cell:", None, "expected job marker"),
        ("  cell:\n", "  cell:", "  next:", "expected following job marker"),
        (
            "  cell:\n  next:\n  next:\n",
            "  cell:",
            "  next:",
            "expected following job marker",
        ),
    )
    for source, start_marker, end_marker, expected_message in malformed:
        try:
            _job_slice(source, start_marker, end_marker)
        except AssertionError as exc:
            assert expected_message in str(exc)
            assert "exactly once" in str(exc)
        else:
            raise AssertionError("malformed workflow markers must fail closed")


def test_official_s3_workflow_is_manual_and_protected() -> None:
    assert "workflow_dispatch:" in WORKFLOW
    assert "pull_request:" not in WORKFLOW
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "environment: legalforecastbench-official-eval-fan-in" in WORKFLOW
    assert "secure-gate deployment protection" in WORKFLOW
    assert "github.ref == 'refs/heads/main'" in WORKFLOW
    assert "Official LegalForecastBench S3 validation is allowed only from" in WORKFLOW
    assert "release_sha must be reachable from origin/main" in WORKFLOW
    assert (
        '[[ ! "${PACKET_OBJECT_KEY_INPUT}" =~ '
        "^model-packets/[A-Za-z0-9._/-]+$ ]]" in WORKFLOW
    )
    assert (
        '[[ ! "${MANIFEST_OBJECT_KEY_INPUT}" =~ '
        "^manifests/[A-Za-z0-9._/-]+$ ]]" in WORKFLOW
    )
    packet_input = WORKFLOW.split("      packet_object_key:", maxsplit=1)[1].split(
        "      manifest_object_key:", maxsplit=1
    )[0]
    manifest_input = WORKFLOW.split("      manifest_object_key:", maxsplit=1)[1].split(
        "      per_case_object_key:", maxsplit=1
    )[0]
    per_case_input = WORKFLOW.split("      per_case_object_key:", maxsplit=1)[1].split(
        "      per_case_version_id:", maxsplit=1
    )[0]
    per_case_version_input = WORKFLOW.split("      per_case_version_id:", maxsplit=1)[
        1
    ].split("      shard_receipt_object_key:", maxsplit=1)[0]
    shard_receipt_input = WORKFLOW.split("      shard_receipt_object_key:", maxsplit=1)[
        1
    ].split("\n\npermissions:", maxsplit=1)[0]
    assert "required: true" in packet_input
    assert "required: true" in manifest_input
    assert "required: true" in per_case_input
    assert "required: true" in per_case_version_input
    assert "required: true" in shard_receipt_input


def test_official_s3_workflow_scopes_oidc_to_the_protected_job() -> None:
    assert WORKFLOW.count("id-token: write") == 3
    assert "permissions:\n  contents: read" in WORKFLOW
    assert CELL_JOB.count("id-token: write") == 1
    assert FAN_IN_JOB.count("id-token: write") == 1
    assert CELL_RECEIPT_DENIAL_JOB.count("id-token: write") == 1
    assert "role-to-assume: ${{ env.LFB_GITHUB_PACKET_READ_ROLE_ARN }}" in CELL_JOB
    assert "role-to-assume: ${{ env.LFB_GITHUB_FAN_IN_ROLE_ARN }}" not in CELL_JOB
    assert "role-to-assume: ${{ env.LFB_GITHUB_FAN_IN_ROLE_ARN }}" in FAN_IN_JOB
    assert (
        "role-to-assume: ${{ env.LFB_GITHUB_PACKET_READ_ROLE_ARN }}" not in FAN_IN_JOB
    )
    assert (
        "role-to-assume: ${{ env.LFB_GITHUB_PACKET_READ_ROLE_ARN }}"
        in CELL_RECEIPT_DENIAL_JOB
    )
    assert (
        "role-to-assume: ${{ env.LFB_GITHUB_FAN_IN_ROLE_ARN }}"
        not in CELL_RECEIPT_DENIAL_JOB
    )
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN: ${{ vars." in CELL_JOB
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN: ${{ vars." in FAN_IN_JOB
    configure_aws_pins = re.findall(
        r"uses: aws-actions/configure-aws-credentials@([0-9a-f]{40})(?=\s|$)",
        WORKFLOW,
    )
    assert len(configure_aws_pins) == 3
    assert CELL_JOB.count("uses: aws-actions/configure-aws-credentials@") == 1
    assert FAN_IN_JOB.count("uses: aws-actions/configure-aws-credentials@") == 1
    assert (
        CELL_RECEIPT_DENIAL_JOB.count("uses: aws-actions/configure-aws-credentials@")
        == 1
    )
    assert "AWS_ACCESS_KEY_ID" not in WORKFLOW
    assert "AWS_SECRET_ACCESS_KEY" not in WORKFLOW


def test_official_workflows_share_one_configure_aws_credentials_pin() -> None:
    action_pin_pattern = (
        r"uses: aws-actions/configure-aws-credentials@([0-9a-f]{40})(?=\s|$)"
    )
    pins = re.findall(action_pin_pattern, WORKFLOW)
    pins.extend(re.findall(action_pin_pattern, RUN_BENCHMARK_WORKFLOW))

    assert pins
    assert len(set(pins)) == 1


def test_official_s3_workflow_consumes_only_the_read_contract() -> None:
    assert "LFB_PACKET_BUCKET: ${{ vars.LFB_PACKET_BUCKET }}" in WORKFLOW
    assert "LFB_RESULTS_BUCKET: ${{ vars.LFB_RESULTS_BUCKET }}" in WORKFLOW
    assert "LFB_MODEL_PACKET_PREFIX" in WORKFLOW
    assert "model-packets/" in WORKFLOW
    assert "LFB_RESULTS_MANIFEST_PREFIX" in WORKFLOW
    assert "manifests/" in WORKFLOW
    assert "aws s3api list-objects-v2" in WORKFLOW
    assert "aws s3api head-object" in WORKFLOW
    assert "Validate fan-in read contract" in WORKFLOW
    assert 'allowed_prefixes=("per-case/" "shard-receipts/")' in WORKFLOW
    assert '--key "${PER_CASE_OBJECT_KEY}"' in FAN_IN_JOB
    assert '--version-id "${PER_CASE_VERSION_ID}"' in FAN_IN_JOB
    assert '--key "${SHARD_RECEIPT_OBJECT_KEY}"' in FAN_IN_JOB
    assert "LFB_PROVIDER_AUTHORITY_TABLE: ${{ vars." in CELL_JOB
    assert "aws dynamodb describe-table" in CELL_JOB
    assert "LFB_PROVIDER_AUTHORITY_TABLE" not in FAN_IN_JOB
    assert "aws dynamodb" not in FAN_IN_JOB


def test_fan_in_denials_reuse_objects_proven_by_the_cell_job() -> None:
    assert "      - validate-official-s3-access" in FAN_IN_JOB
    assert (
        "MANIFEST_OBJECT_KEY: "
        "${{ needs.validate-request.outputs.manifest_object_key }}" in FAN_IN_JOB
    )
    assert (
        "PACKET_OBJECT_KEY: "
        "${{ needs.validate-request.outputs.packet_object_key }}" in FAN_IN_JOB
    )
    assert '--key "${MANIFEST_OBJECT_KEY}"' in FAN_IN_JOB
    assert '--key "${PACKET_OBJECT_KEY}"' in FAN_IN_JOB
    assert "manifests/security-negative-control.json" not in WORKFLOW
    assert "model-packets/security-negative-control.json" not in WORKFLOW


def test_two_role_validation_uses_proven_existing_fan_in_objects() -> None:
    assert (
        "per_case_object_key must name an existing object under "
        "per-case/<case>/metrics/." in WORKFLOW
    )
    assert "per_case_version_id must be a nonempty S3 VersionId" in WORKFLOW
    assert (
        "shard_receipt_object_key must name an existing object under "
        "shard-receipts/." in WORKFLOW
    )
    assert (
        "PER_CASE_OBJECT_KEY: "
        "${{ needs.validate-request.outputs.per_case_object_key }}" in FAN_IN_JOB
    )
    assert (
        "PER_CASE_VERSION_ID: "
        "${{ needs.validate-request.outputs.per_case_version_id }}" in FAN_IN_JOB
    )
    assert (
        "SHARD_RECEIPT_OBJECT_KEY: "
        "${{ needs.validate-request.outputs.shard_receipt_object_key }}" in FAN_IN_JOB
    )
    assert "--version-id" in FAN_IN_JOB
    assert "> /tmp/lfb-fan-in-per-case-version-head.json" not in FAN_IN_JOB
    assert ">/tmp/lfb-fan-in-per-case-version-head.json" in FAN_IN_JOB
    assert ">/tmp/lfb-fan-in-shard-receipt-head.json" in FAN_IN_JOB
    assert "      - validate-fan-in-access" in CELL_RECEIPT_DENIAL_JOB
    assert (
        "SHARD_RECEIPT_OBJECT_KEY: "
        "${{ needs.validate-request.outputs.shard_receipt_object_key }}"
        in CELL_RECEIPT_DENIAL_JOB
    )
    assert '--key "${SHARD_RECEIPT_OBJECT_KEY}"' in CELL_RECEIPT_DENIAL_JOB
    assert "already proven under fan-in" in CELL_RECEIPT_DENIAL_JOB


def test_official_s3_workflow_does_not_administer_aws_or_s3_state() -> None:
    forbidden_snippets = (
        "cdk deploy",
        "cloudformation",
        "create-stack",
        "delete-stack",
        "aws s3 cp",
        "iam create-",
        "iam delete-",
        "iam put-",
    )
    lowered = WORKFLOW.lower()
    for snippet in forbidden_snippets:
        assert snippet not in lowered


def test_runtime_roles_exercise_denied_calls_without_session_policy() -> None:
    assert "inline-session-policy" not in WORKFLOW
    assert CELL_JOB.count("expect_access_denied()") == 1
    assert FAN_IN_JOB.count("expect_access_denied()") == 1
    assert WORKFLOW.count('report_key="reports/security-negative-controls/') == 2
    assert "per-case/security-negative-controls/" not in WORKFLOW
    assert "shard-receipts/security-negative-controls/" not in WORKFLOW
    for denied_operation in (
        "s3api put-object",
        "s3api list-objects-v2",
        "s3api delete-object",
        "s3api put-object-acl",
        "s3api list-object-versions",
    ):
        assert denied_operation in CELL_JOB
        assert denied_operation in FAN_IN_JOB


def test_fan_in_validation_has_no_provider_or_packet_read_authority() -> None:
    assert "secrets." not in FAN_IN_JOB
    assert "PROVIDER_API_KEY" not in FAN_IN_JOB
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" not in FAN_IN_JOB
    assert "role-to-assume: ${{ env.LFB_GITHUB_FAN_IN_ROLE_ARN }}" in FAN_IN_JOB
    assert "fan-in-manifest-read" in FAN_IN_JOB
    assert "fan-in-packet-read" in FAN_IN_JOB
