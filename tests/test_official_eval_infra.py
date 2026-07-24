from __future__ import annotations

import ast
import copy
import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "official-eval"
POLICY_ROOT = INFRA_ROOT / "policies"
RUN_BENCHMARK_WORKFLOW = ROOT / ".github" / "workflows" / "run-benchmark.yaml"
FAN_IN_WORKFLOW = ROOT / ".github" / "workflows" / "fan-in-publish.yaml"

OIDC_PROVIDER_ARN = (
    "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
)
PACKET_BUCKET_ARN = "arn:aws:s3:::lfb-packets"
RESULTS_BUCKET_ARN = "arn:aws:s3:::lfb-results"
REPOSITORY = "johnhughes3/LegalForecastBench"
REF = "refs/heads/main"
CELL_ENVIRONMENT = "legalforecastbench-official-eval"
FAN_IN_ENVIRONMENT = "legalforecastbench-official-eval-fan-in"
SUBJECT_PREFIX = f"repo:{REPOSITORY}"

JsonObject = dict[str, object]
PolicyMutation = Callable[[JsonObject], None]


def _render_template(path: Path, **values: str) -> JsonObject:
    rendered = path.read_text(encoding="utf-8")
    for name, value in values.items():
        rendered = rendered.replace(f"${{{name}}}", value)
    unresolved = re.findall(r"\$\{[^}]+\}", rendered)
    assert unresolved == []
    loaded: object = json.loads(rendered)
    assert isinstance(loaded, dict)
    return cast(JsonObject, loaded)


def _trust_policy(environment: str) -> JsonObject:
    return _render_template(
        POLICY_ROOT / "github-oidc-trust.json.tftpl",
        github_oidc_provider_arn=OIDC_PROVIDER_ARN,
        github_repository=REPOSITORY,
        github_ref=REF,
        github_subject=f"{SUBJECT_PREFIX}:environment:{environment}",
    )


def _cell_policy() -> JsonObject:
    return _render_template(
        POLICY_ROOT / "cell-storage-policy.json.tftpl",
        packet_bucket_arn=PACKET_BUCKET_ARN,
        results_bucket_arn=RESULTS_BUCKET_ARN,
    )


def _fan_in_policy() -> JsonObject:
    return _render_template(
        POLICY_ROOT / "fan-in-storage-policy.json.tftpl",
        results_bucket_arn=RESULTS_BUCKET_ARN,
    )


def _bedrock_policy() -> JsonObject:
    direct_arn = (
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-direct-example-v1"
    )
    profile_arn = (
        "arn:aws:bedrock:us-east-1:123456789012:"
        "inference-profile/us.anthropic.claude-profile-example-v1"
    )
    destination_arns = [
        (
            "arn:aws:bedrock:us-east-1::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
        (
            "arn:aws:bedrock:us-west-2::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
    ]
    return _render_template(
        POLICY_ROOT / "cell-bedrock-policy.json.tftpl",
        bedrock_invoke_model_statements_json=json.dumps(
            [
                {
                    "Sid": "InvokeReviewedDirectFoundationModels",
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Resource": [direct_arn],
                },
                {
                    "Sid": "GrantGeographicInferenceProfileExampleAccess",
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Resource": [profile_arn],
                },
                {
                    "Sid": "GrantGeographicInferenceProfileExampleModelAccess",
                    "Effect": "Allow",
                    "Action": "bedrock:InvokeModel",
                    "Resource": destination_arns,
                    "Condition": {
                        "StringEquals": {
                            "bedrock:InferenceProfileArn": profile_arn,
                        }
                    },
                },
            ]
        ),
    )


def _statements_by_sid(policy: Mapping[str, object]) -> dict[str, JsonObject]:
    raw_statements = policy.get("Statement")
    assert isinstance(raw_statements, list)
    by_sid: dict[str, JsonObject] = {}
    for raw_statement in cast(list[object], raw_statements):
        assert isinstance(raw_statement, dict)
        statement = cast(JsonObject, raw_statement)
        sid = statement.get("Sid")
        assert isinstance(sid, str)
        assert sid not in by_sid
        by_sid[sid] = statement
    return by_sid


def _assert_exact_trust(policy: Mapping[str, object], *, environment: str) -> None:
    assert set(policy) == {"Version", "Statement"}
    assert policy["Version"] == "2012-10-17"
    statements = policy["Statement"]
    assert isinstance(statements, list)
    assert statements == [
        {
            "Sid": "GitHubActionsOidc",
            "Effect": "Allow",
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Principal": {"Federated": OIDC_PROVIDER_ARN},
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": (
                        f"{SUBJECT_PREFIX}:environment:{environment}"
                    ),
                    "token.actions.githubusercontent.com:repository": REPOSITORY,
                    "token.actions.githubusercontent.com:ref": REF,
                }
            },
        }
    ]


def _assert_exact_cell_policy(policy: Mapping[str, object]) -> None:
    assert set(policy) == {"Version", "Statement"}
    assert policy["Version"] == "2012-10-17"
    statements = _statements_by_sid(policy)
    assert set(statements) == {
        "ReadModelPackets",
        "ListModelPackets",
        "ReadFrozenManifests",
        "ListFrozenManifests",
        "ReadWritePerCaseResults",
        "ReadWritePerCaseRunnerLogs",
        "ListPerCaseResults",
        "ReadMutationMarkers",
        "CreateMutationMarkers",
        "ReadCycleSeal",
        "ProbeExactCycleSeal",
    }
    assert statements["ReadModelPackets"] == {
        "Sid": "ReadModelPackets",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": f"{PACKET_BUCKET_ARN}/model-packets/*",
    }
    assert statements["ListModelPackets"] == {
        "Sid": "ListModelPackets",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": PACKET_BUCKET_ARN,
        "Condition": {"StringLike": {"s3:prefix": "model-packets/*"}},
    }
    assert statements["ReadFrozenManifests"] == {
        "Sid": "ReadFrozenManifests",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": f"{RESULTS_BUCKET_ARN}/manifests/*",
    }
    assert statements["ListFrozenManifests"] == {
        "Sid": "ListFrozenManifests",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {"StringLike": {"s3:prefix": "manifests/*"}},
    }
    assert statements["ReadWritePerCaseResults"] == {
        "Sid": "ReadWritePerCaseResults",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject"],
        "Resource": f"{RESULTS_BUCKET_ARN}/per-case/*/metrics/*",
    }
    assert statements["ReadWritePerCaseRunnerLogs"] == {
        "Sid": "ReadWritePerCaseRunnerLogs",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:PutObject"],
        "Resource": (f"{RESULTS_BUCKET_ARN}/per-case/*/reports/*/*.runner-log.jsonl"),
    }
    assert statements["ListPerCaseResults"] == {
        "Sid": "ListPerCaseResults",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {"StringLike": {"s3:prefix": "per-case/*"}},
    }
    mutation_resources = [
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/intent.json",
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/done.json",
    ]
    assert statements["ReadMutationMarkers"] == {
        "Sid": "ReadMutationMarkers",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": mutation_resources,
    }
    assert statements["CreateMutationMarkers"] == {
        "Sid": "CreateMutationMarkers",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": mutation_resources,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    assert statements["ReadCycleSeal"] == {
        "Sid": "ReadCycleSeal",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": (f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/seal.json"),
    }
    assert statements["ProbeExactCycleSeal"] == {
        "Sid": "ProbeExactCycleSeal",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {
            "StringLike": {
                "s3:prefix": "cycle-publication-state/*/seal.json",
            }
        },
    }


def _assert_exact_fan_in_policy(policy: Mapping[str, object]) -> None:
    assert set(policy) == {"Version", "Statement"}
    assert policy["Version"] == "2012-10-17"
    statements = _statements_by_sid(policy)
    assert set(statements) == {
        "ReadExactPerCaseVersions",
        "ReadShardReceipts",
        "CreateShardReceipts",
        "ReadCycleClosure",
        "CreateCycleClosure",
        "ReadCanonicalPublication",
        "CreateCanonicalPublication",
        "ListFanInNamespaces",
    }
    assert statements["ReadExactPerCaseVersions"] == {
        "Sid": "ReadExactPerCaseVersions",
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:GetObjectVersion"],
        "Resource": f"{RESULTS_BUCKET_ARN}/per-case/*/metrics/*",
    }
    receipt_resource = f"{RESULTS_BUCKET_ARN}/shard-receipts/*/*/*/*.json"
    assert statements["ReadShardReceipts"] == {
        "Sid": "ReadShardReceipts",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": receipt_resource,
    }
    assert statements["CreateShardReceipts"] == {
        "Sid": "CreateShardReceipts",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": receipt_resource,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    closure_resources = [
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/intent.json",
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/runs/*/*/done.json",
        f"{RESULTS_BUCKET_ARN}/cycle-publication-state/*/seal.json",
    ]
    assert statements["ReadCycleClosure"] == {
        "Sid": "ReadCycleClosure",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": closure_resources,
    }
    assert statements["CreateCycleClosure"] == {
        "Sid": "CreateCycleClosure",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": closure_resources,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    report_resource = f"{RESULTS_BUCKET_ARN}/reports/*/multi-ablation/*"
    assert statements["ReadCanonicalPublication"] == {
        "Sid": "ReadCanonicalPublication",
        "Effect": "Allow",
        "Action": "s3:GetObject",
        "Resource": report_resource,
    }
    assert statements["CreateCanonicalPublication"] == {
        "Sid": "CreateCanonicalPublication",
        "Effect": "Allow",
        "Action": "s3:PutObject",
        "Resource": report_resource,
        "Condition": {"Null": {"s3:if-none-match": "false"}},
    }
    assert statements["ListFanInNamespaces"] == {
        "Sid": "ListFanInNamespaces",
        "Effect": "Allow",
        "Action": "s3:ListBucket",
        "Resource": RESULTS_BUCKET_ARN,
        "Condition": {
            "StringLike": {
                "s3:prefix": [
                    "cycle-publication-state/*/runs/*",
                    "cycle-publication-state/*/seal.json",
                    "per-case/*",
                    "reports/*/multi-ablation/*",
                    "shard-receipts/*",
                ]
            }
        },
    }


def test_exact_two_role_topology_and_policy_attachments() -> None:
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )
    roles = set(re.findall(r'resource "aws_iam_role" "([^"]+)"', terraform))
    inline_policies = set(
        re.findall(r'resource "aws_iam_role_policy" "([^"]+)"', terraform)
    )

    assert roles == {"cell", "fan_in"}
    assert inline_policies == {"cell_storage", "cell_bedrock", "fan_in_storage"}
    assert set(
        re.findall(
            r'resource "aws_iam_role_policies_exclusive" "([^"]+)"',
            terraform,
        )
    ) == {"cell", "fan_in"}
    assert set(
        re.findall(
            r'resource "aws_iam_role_policy_attachments_exclusive" "([^"]+)"',
            terraform,
        )
    ) == {"cell", "fan_in"}
    assert 'resource "aws_iam_policy"' not in terraform
    assert 'resource "aws_iam_role_policy_attachment"' not in terraform
    assert "aws_dynamodb" not in terraform
    assert "assume_role_policy   = local.cell_trust_policy_json" in terraform
    assert "assume_role_policy   = local.fan_in_trust_policy_json" in terraform
    assert "role   = aws_iam_role.cell.id" in terraform
    assert "policy = local.cell_storage_policy_json" in terraform
    assert "role   = aws_iam_role.fan_in.id" in terraform
    assert "policy = local.fan_in_storage_policy_json" in terraform
    assert "policy_arns = []" in terraform
    assert "aws_iam_role_policy.cell_bedrock[0].name" in terraform
    assert "var.enable_bedrock_runtime" in terraform
    assert {path.name for path in POLICY_ROOT.glob("*.json.tftpl")} == {
        "cell-bedrock-policy.json.tftpl",
        "cell-storage-policy.json.tftpl",
        "fan-in-storage-policy.json.tftpl",
        "github-oidc-trust.json.tftpl",
        "tls-only-bucket-policy.json.tftpl",
    }
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" in (INFRA_ROOT / "outputs.tf").read_text(
        encoding="utf-8"
    )
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in (INFRA_ROOT / "outputs.tf").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "environment",
    [CELL_ENVIRONMENT, FAN_IN_ENVIRONMENT],
)
def test_oidc_trust_is_exact_for_repository_ref_and_environment(
    environment: str,
) -> None:
    _assert_exact_trust(_trust_policy(environment), environment=environment)


def test_cell_policy_matches_current_call_graph_exactly() -> None:
    _assert_exact_cell_policy(_cell_policy())


def test_fan_in_policy_matches_current_call_graph_exactly() -> None:
    _assert_exact_fan_in_policy(_fan_in_policy())


def test_optional_bedrock_policy_separates_direct_and_profile_grants() -> None:
    direct_arn = (
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-direct-example-v1"
    )
    profile_arn = (
        "arn:aws:bedrock:us-east-1:123456789012:"
        "inference-profile/us.anthropic.claude-profile-example-v1"
    )
    destination_arns = [
        (
            "arn:aws:bedrock:us-east-1::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
        (
            "arn:aws:bedrock:us-west-2::foundation-model/"
            "anthropic.claude-profile-example-v1"
        ),
    ]
    assert _bedrock_policy() == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "InvokeReviewedDirectFoundationModels",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": [direct_arn],
            },
            {
                "Sid": "GrantGeographicInferenceProfileExampleAccess",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": [profile_arn],
            },
            {
                "Sid": "GrantGeographicInferenceProfileExampleModelAccess",
                "Effect": "Allow",
                "Action": "bedrock:InvokeModel",
                "Resource": destination_arns,
                "Condition": {
                    "StringEquals": {
                        "bedrock:InferenceProfileArn": profile_arn,
                    }
                },
            },
        ],
    }
    statements = _statements_by_sid(_bedrock_policy())
    direct = statements["InvokeReviewedDirectFoundationModels"]
    profile = statements["GrantGeographicInferenceProfileExampleAccess"]
    profile_models = statements["GrantGeographicInferenceProfileExampleModelAccess"]
    assert "Condition" not in direct
    assert direct["Resource"] == [direct_arn]
    assert "Condition" not in profile
    assert profile["Resource"] == [profile_arn]
    assert profile_models["Resource"] == destination_arns
    assert profile_models["Condition"] == {
        "StringEquals": {"bedrock:InferenceProfileArn": profile_arn}
    }
    assert not set(cast(list[str], direct["Resource"])) & set(destination_arns)
    assert profile_arn not in cast(list[str], profile_models["Resource"])


def test_optional_bedrock_contract_is_default_off_cell_only_and_rejects_global() -> (
    None
):
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )
    locals_source = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    variables_source = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    assert 'variable "enable_bedrock_runtime"' in terraform
    assert "default     = false" in terraform
    assert 'variable "bedrock_direct_foundation_model_arns"' in terraform
    assert 'variable "bedrock_geographic_inference_profiles"' in terraform
    assert "length(var.bedrock_direct_foundation_model_arns) > 0" in terraform
    assert "length(var.bedrock_geographic_inference_profiles) > 0" in terraform
    assert (
        "Resource = sort(tolist(var.bedrock_direct_foundation_model_arns))"
        in locals_source
    )
    assert (
        "Resource = [var.bedrock_geographic_inference_profiles"
        "[profile_key].inference_profile_arn]" in locals_source
    )
    assert (
        "var.bedrock_geographic_inference_profiles"
        "[profile_key].destination_foundation_model_arns" in locals_source
    )
    assert '"bedrock:InferenceProfileArn"' in locals_source
    assert (
        '"bedrock:InferenceProfileArn" = '
        "var.bedrock_geographic_inference_profiles"
        "[profile_key].inference_profile_arn" in locals_source
    )
    assert ":inference-profile/global." in variables_source
    assert "Global Bedrock inference profiles are unsupported" in variables_source
    assert "distinct three-part policy contract" in variables_source
    assert "(us|eu|apac)" in variables_source
    assert "length(profile.destination_foundation_model_arns) > 0" in variables_source
    assert (
        "Each geographic Bedrock inference-profile ARN must appear" in variables_source
    )
    assert "application-inference-profile" not in terraform
    assert "bedrock:InvokeModel" not in json.dumps(_fan_in_policy())


def _add_statement(policy: JsonObject) -> None:
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statements = cast(list[object], raw_statements)
    statements.append(
        {
            "Sid": "Broadening",
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": "*",
        }
    )


def _add_action(policy: JsonObject) -> None:
    statement = _statements_by_sid(policy)["ReadWritePerCaseResults"]
    raw_actions = statement["Action"]
    assert isinstance(raw_actions, list)
    actions = cast(list[object], raw_actions)
    actions.append("s3:DeleteObject")


def _add_resource(policy: JsonObject) -> None:
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statement: JsonObject | None = None
    for item in cast(list[object], raw_statements):
        if isinstance(item, dict):
            candidate = cast(JsonObject, item)
            if candidate.get("Sid") == "ReadWritePerCaseResults":
                statement = candidate
                break
    assert statement is not None
    statement["Resource"] = [
        statement["Resource"],
        f"{RESULTS_BUCKET_ARN}/reports/*",
    ]


@pytest.mark.parametrize(
    "mutation",
    [_add_statement, _add_action, _add_resource],
)
def test_cell_contract_guard_rejects_policy_broadening(
    mutation: PolicyMutation,
) -> None:
    policy = copy.deepcopy(_cell_policy())
    mutation(policy)
    with pytest.raises(AssertionError):
        _assert_exact_cell_policy(policy)


def test_trust_contract_guard_rejects_extra_principal_or_claim_drift() -> None:
    policy = copy.deepcopy(_trust_policy(CELL_ENVIRONMENT))
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statements = cast(list[object], raw_statements)
    statement = statements[0]
    assert isinstance(statement, dict)
    statement = cast(JsonObject, statement)
    statement["Principal"] = {
        "Federated": [OIDC_PROVIDER_ARN, "arn:aws:iam::123456789012:root"]
    }
    with pytest.raises(AssertionError):
        _assert_exact_trust(policy, environment=CELL_ENVIRONMENT)

    policy = copy.deepcopy(_trust_policy(CELL_ENVIRONMENT))
    raw_statements = policy["Statement"]
    assert isinstance(raw_statements, list)
    statements = cast(list[object], raw_statements)
    statement = statements[0]
    assert isinstance(statement, dict)
    statement = cast(JsonObject, statement)
    condition = statement["Condition"]
    assert isinstance(condition, dict)
    condition = cast(JsonObject, condition)
    string_equals = condition["StringEquals"]
    assert isinstance(string_equals, dict)
    string_equals = cast(JsonObject, string_equals)
    string_equals["token.actions.githubusercontent.com:ref"] = "refs/heads/*"
    with pytest.raises(AssertionError):
        _assert_exact_trust(policy, environment=CELL_ENVIRONMENT)


@pytest.mark.parametrize(
    ("policy_factory", "sid"),
    [
        (_cell_policy, "CreateMutationMarkers"),
        (_fan_in_policy, "CreateShardReceipts"),
        (_fan_in_policy, "CreateCycleClosure"),
        (_fan_in_policy, "CreateCanonicalPublication"),
    ],
)
def test_immutable_write_contract_rejects_missing_or_wrong_precondition(
    policy_factory: Callable[[], JsonObject],
    sid: str,
) -> None:
    for replacement in (
        None,
        {"Null": {"s3:if-none-match": "true"}},
        {"Null": {"s3:wrong-header": "false"}},
    ):
        policy = copy.deepcopy(policy_factory())
        statement = _statements_by_sid(policy)[sid]
        if replacement is None:
            statement.pop("Condition")
        else:
            statement["Condition"] = replacement
        with pytest.raises(AssertionError):
            if policy_factory is _cell_policy:
                _assert_exact_cell_policy(policy)
            else:
                _assert_exact_fan_in_policy(policy)


def _function_source(
    path: Path,
    function_name: str,
    *,
    owner: str | None = None,
) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    scope: list[ast.stmt] = tree.body
    if owner is not None:
        owners = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == owner
        ]
        assert len(owners) == 1
        scope = owners[0].body
    matches = [
        node
        for node in scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    assert len(matches) == 1
    segment = ast.get_source_segment(source, matches[0])
    assert segment is not None
    return segment


def test_cross_file_workflow_and_python_call_graph_matches_policy_contract() -> None:
    run_workflow = RUN_BENCHMARK_WORKFLOW.read_text(encoding="utf-8")
    fan_in_workflow = FAN_IN_WORKFLOW.read_text(encoding="utf-8")
    per_case_source = ROOT / "legalforecast" / "evals" / "per_case_runner.py"
    bedrock_source = ROOT / "legalforecast" / "evals" / "live_model_solver.py"
    closure_source = ROOT / "legalforecast" / "publication" / "cycle_closure.py"
    receipt_source = ROOT / "legalforecast" / "publication" / "shard_receipt.py"
    publish_source = ROOT / "legalforecast" / "publication" / "shard_fan_in_publish.py"

    assert "environment: legalforecastbench-official-eval" in run_workflow
    assert "LFB_GITHUB_PACKET_READ_ROLE_ARN" in run_workflow
    assert "environment: legalforecastbench-official-eval-fan-in" in run_workflow
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in run_workflow
    assert '--packet-store-root "s3://${LFB_PACKET_BUCKET}"' in run_workflow
    assert (
        '--results-store-root "s3://${LFB_RESULTS_BUCKET}/per-case/${CYCLE_ID}"'
        in run_workflow
    )
    for runtime in ("bedrock", "aws-bedrock", "aws_bedrock"):
        assert runtime in run_workflow
    assert "LFB_ANTHROPIC_BEDROCK_MODEL_ID" in run_workflow

    assert "environment: legalforecastbench-official-eval-fan-in" in fan_in_workflow
    assert "LFB_GITHUB_FAN_IN_ROLE_ARN" in fan_in_workflow
    assert (
        '"s3://${LFB_RESULTS_BUCKET}/reports/${CYCLE_ID}/multi-ablation/"'
        in fan_in_workflow
    )

    output_keys_source = _function_source(per_case_source, "_output_keys")
    assert 'f"metrics/{cycle_slug}/{run_id}.runs.jsonl"' in output_keys_source
    assert 'f"metrics/{cycle_slug}/{run_id}.recovery.json"' in output_keys_source
    run_source = _function_source(per_case_source, "run_per_case_evaluation")
    assert 'f"reports/{_cycle_slug(packet_object)}/{run_id}.runner-log.jsonl"' in (
        run_source
    )
    assert "aws s3 sync \\" in run_workflow
    assert '"s3://${LFB_RESULTS_BUCKET}/per-case/${CYCLE_ID}/" \\' in run_workflow
    ordinary_put_source = _function_source(per_case_source, "_upload_path")
    assert '"put-object"' in ordinary_put_source
    assert '"--if-none-match"' not in ordinary_put_source

    bedrock_call_source = _function_source(
        bedrock_source,
        "_invoke_bedrock_runtime_json",
    )
    assert '"bedrock-runtime"' in bedrock_call_source
    assert '"invoke-model"' in bedrock_call_source

    for path, function_name, owner in (
        (closure_source, "create", "_S3ObjectStore"),
        (receipt_source, "write_receipt_once", None),
        (publish_source, "_put_s3_file_once", None),
    ):
        immutable_put_source = _function_source(path, function_name, owner=owner)
        assert '"put-object"' in immutable_put_source
        assert '"--if-none-match"' in immutable_put_source
        assert '"*"' in immutable_put_source

    assert 'return f"{_STATE_NAMESPACE}/{cycle}/seal.json"' in _function_source(
        closure_source,
        "seal_key",
    )
    assert 'return f"shard-receipts/{cycle_id}/' in _function_source(
        receipt_source,
        "receipt_key",
    )
    assert 'f"reports/{cycle_id}/multi-ablation"' in _function_source(
        publish_source,
        "_require_canonical_publish_root",
    )


def test_storage_is_private_owned_encrypted_versioned_and_tls_only() -> None:
    storage = (INFRA_ROOT / "storage.tf").read_text(encoding="utf-8")
    tls_policy = _render_template(
        POLICY_ROOT / "tls-only-bucket-policy.json.tftpl",
        bucket_arn=RESULTS_BUCKET_ARN,
    )

    assert storage.count('resource "aws_s3_bucket"') == 2
    assert storage.count('resource "aws_s3_bucket_public_access_block"') == 2
    assert storage.count('resource "aws_s3_bucket_ownership_controls"') == 2
    assert (
        storage.count('resource "aws_s3_bucket_server_side_encryption_configuration"')
        == 2
    )
    assert storage.count('resource "aws_s3_bucket_versioning"') == 2
    assert storage.count('resource "aws_s3_bucket_policy"') == 2
    assert storage.count("BucketOwnerEnforced") == 2
    assert storage.count('sse_algorithm = "AES256"') == 2
    assert storage.count('status = "Enabled"') >= 2
    assert tls_policy == {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "DenyInsecureTransport",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [RESULTS_BUCKET_ARN, f"{RESULTS_BUCKET_ARN}/*"],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            }
        ],
    }


def test_lifecycle_preserves_audit_versions_and_only_expires_negative_controls() -> (
    None
):
    storage = (INFRA_ROOT / "storage.tf").read_text(encoding="utf-8")

    assert "per-case/" not in storage
    assert "noncurrent_result_retention_days" not in storage
    assert 'prefix = "reports/security-negative-controls/"' in storage
    assert "var.negative_control_retention_days" in storage
    assert storage.count("abort_incomplete_multipart_upload") == 2


def test_docs_record_unapplied_import_remote_state_and_live_acceptance_boundaries() -> (
    None
):
    readme = (INFRA_ROOT / "README.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "official-run-runbook.md").read_text(encoding="utf-8")
    combined = f"{readme}\n{runbook}"

    for required in (
        CELL_ENVIRONMENT,
        FAN_IN_ENVIRONMENT,
        "LFB_GITHUB_PACKET_READ_ROLE_ARN",
        "LFB_GITHUB_FAN_IN_ROLE_ARN",
        "terraform import",
        "aws_iam_role_policies_exclusive",
        "aws_iam_role_policy_attachments_exclusive",
        "remote state",
        "reports/security-negative-controls/",
        "VersionId",
        "PII",
        "plan",
        "apply",
        "post-provision",
        "main",
        "LFB_ANTHROPIC_RUNTIME",
        "bedrock_direct_foundation_model_arns",
        "bedrock_geographic_inference_profiles",
        "bedrock:InferenceProfileArn",
        "global inference profiles",
    ):
        assert required in combined

    assert "fan-in environment does not yet exist" in combined
    assert "code validation is not live acceptance" in combined
    assert "has never run" in combined
    assert "five environments" not in combined
