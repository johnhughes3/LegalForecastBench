from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "official-labeling"

ALLOWED_ACTIONS = {
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:TransactWriteItems",
    "dynamodb:UpdateItem",
}


def test_labeling_role_is_oidc_bound_to_exact_protected_environments() -> None:
    iam = (INFRA_ROOT / "iam.tf").read_text(encoding="utf-8")
    variables = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")

    assert 'data "aws_iam_policy_document" "labeling_trust"' in iam
    assert 'resource "aws_iam_role" "labeling"' in iam
    assert 'resource "aws_iam_role_policy" "labeling"' in iam
    assert "sts:AssumeRoleWithWebIdentity" in iam
    assert "token.actions.githubusercontent.com:aud" in iam
    assert "token.actions.githubusercontent.com:sub" in iam
    assert "sts.amazonaws.com" in iam
    assert 'default     = "repo:johnhughes3/LegalForecastBench"' in variables
    assert (
        'var.github_subject_prefix == "repo:johnhughes3/LegalForecastBench"'
        in variables
    )
    assert "max_session_duration = 7200" in iam

    for environment in (
        "legalforecastbench-official-labeling-authority-smoke",
        "legalforecastbench-official-labeling-anthropic-unitize",
        "legalforecastbench-official-labeling-google-review",
        "legalforecastbench-official-labeling-openai-label",
        "legalforecastbench-official-labeling-google-label",
    ):
        assert environment in variables


def test_labeling_role_has_only_exact_table_data_plane_actions() -> None:
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )
    dynamodb_actions = set(re.findall(r'"(dynamodb:[A-Za-z]+)"', terraform))

    assert dynamodb_actions == ALLOWED_ACTIONS
    for forbidden in (
        "dynamodb:*",
        "dynamodb:BatchWriteItem",
        "dynamodb:CreateTable",
        "dynamodb:DeleteItem",
        "dynamodb:DeleteTable",
        "dynamodb:ListTables",
        "dynamodb:Scan",
        "dynamodb:TagResource",
        "s3:",
    ):
        assert forbidden not in terraform
    assert terraform.count("resources = [var.provider_authority_table_arn]") == 1
    assert 'resources = ["*"]' not in terraform
    assert 'resources = ["${' not in terraform


def test_table_identity_is_exact_and_frozen_before_role_creation() -> None:
    iam = (INFRA_ROOT / "iam.tf").read_text(encoding="utf-8")
    variables = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    outputs = (INFRA_ROOT / "outputs.tf").read_text(encoding="utf-8")

    assert "sha256(" in iam
    assert "var.provider_authority_table_arn" in iam
    assert "var.provider_authority_resource_identity_sha256" in iam
    assert "precondition" in iam
    assert 'variable "provider_authority_table_arn"' in variables
    assert 'variable "provider_authority_resource_identity_sha256"' in variables
    assert 'output "provider_authority_resource_identity_sha256"' in outputs


def test_module_does_not_create_or_administer_the_shared_table() -> None:
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )

    assert 'resource "aws_dynamodb_table"' not in terraform
    assert "prevent_destroy" not in terraform


def test_module_has_no_second_policy_or_broadened_trust_path() -> None:
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )

    assert terraform.count('resource "aws_iam_role"') == 1
    assert terraform.count('resource "aws_iam_role_policy"') == 1
    assert 'resource "aws_iam_policy"' not in terraform
    assert 'resource "aws_iam_role_policy_attachment"' not in terraform
    assert "managed_policy_arns" not in terraform
    assert terraform.count("sts:AssumeRoleWithWebIdentity") == 1
