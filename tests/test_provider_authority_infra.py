from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "provider-authority"
RUNBOOK = ROOT / "docs" / "official-run-runbook.md"


def _terraform() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )


def test_module_creates_only_the_shared_provider_authority_table() -> None:
    terraform = _terraform()

    assert terraform.count('resource "aws_dynamodb_table"') == 1
    assert 'resource "aws_dynamodb_table" "provider_authority"' in terraform
    for forbidden_resource in (
        'resource "aws_iam_',
        'resource "aws_s3_',
        'resource "aws_kms_',
        'resource "aws_secretsmanager_',
    ):
        assert forbidden_resource not in terraform


def test_table_has_exact_runtime_key_schema() -> None:
    terraform = _terraform()

    assert 'hash_key     = "authority_key"' in terraform
    assert 'range_key    = "record_key"' in terraform
    assert terraform.count('name = "authority_key"') == 1
    assert terraform.count('name = "record_key"') == 1
    assert terraform.count('type = "S"') == 2
    assert "global_secondary_index" not in terraform
    assert "local_secondary_index" not in terraform


def test_table_is_fail_closed_against_loss_or_unbounded_capacity() -> None:
    terraform = _terraform()

    assert 'billing_mode = "PAY_PER_REQUEST"' in terraform
    assert "deletion_protection_enabled = true" in terraform
    assert "point_in_time_recovery" in terraform
    assert "server_side_encryption" in terraform
    assert 'attribute_name = "expires_at"' in terraform
    assert "enabled        = true" in terraform
    assert "prevent_destroy = true" in terraform
    assert "read_capacity" not in terraform
    assert "write_capacity" not in terraform


def test_table_name_and_public_identity_are_stable() -> None:
    variables = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    outputs = (INFRA_ROOT / "outputs.tf").read_text(encoding="utf-8")

    assert 'variable "table_name"' in variables
    assert (
        'default     = "legalforecastbench-official-eval-provider-authority"'
        in variables
    )
    assert (
        'var.table_name == "legalforecastbench-official-eval-provider-authority"'
        in variables
    )
    assert 'output "provider_authority_table_name"' in outputs
    assert "sensitive   = true" in outputs
    assert 'output "provider_authority_table_arn"' in outputs
    assert 'output "provider_authority_resource_identity_sha256"' in outputs
    assert "sha256(aws_dynamodb_table.provider_authority.arn)" in outputs


def test_module_has_pinned_tooling_and_no_remote_backend() -> None:
    versions = (INFRA_ROOT / "versions.tf").read_text(encoding="utf-8")
    terraform = _terraform()

    assert 'required_version = ">= 1.8.0"' in versions
    assert 'source  = "hashicorp/aws"' in versions
    assert 'version = "~> 6.0"' in versions
    assert 'provider "aws"' in versions
    assert "backend " not in terraform


def test_docs_keep_table_provisioning_separate_from_eval_infrastructure() -> None:
    readme = (INFRA_ROOT / "README.md").read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "table-only" in readme
    assert "terraform import" in readme
    assert "Terraform plan" in readme
    assert "does not create IAM roles" in readme
    assert "does not create S3" in readme
    assert "`infra/provider-authority`" in runbook
    assert "Stage A/B" in runbook
    assert "separately authorized Terraform apply" in runbook
