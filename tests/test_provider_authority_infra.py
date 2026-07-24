from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "provider-authority"
RUNBOOK = ROOT / "docs" / "official-run-runbook.md"


def _terraform() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )


class _HclToken(NamedTuple):
    kind: str
    value: str


class _HclBlock(NamedTuple):
    kind: str
    labels: tuple[str, ...]
    body: tuple[_HclToken, ...]


def _hcl_quoted_string(source: str, start: int) -> tuple[str, int]:
    assert source[start] == '"'
    cursor = start + 1
    value: list[str] = []
    template_depth = 0
    while cursor < len(source):
        if source[cursor] == "\\":
            assert cursor + 1 < len(source)
            if template_depth == 0:
                value.append(source[cursor + 1])
            cursor += 2
            continue
        if template_depth == 0:
            if source[cursor] == '"':
                return "".join(value), cursor + 1
            if source.startswith(("$${", "%%{"), cursor):
                value.extend(source[cursor : cursor + 3])
                cursor += 3
                continue
            if source.startswith(("${", "%{"), cursor):
                template_depth = 1
                cursor += 2
                continue
            value.append(source[cursor])
            cursor += 1
            continue
        if source[cursor] == '"':
            _, cursor = _hcl_quoted_string(source, cursor)
            continue
        if source[cursor] == "#" or source.startswith("//", cursor):
            newline = source.find("\n", cursor)
            cursor = len(source) if newline == -1 else newline + 1
            continue
        if source.startswith("/*", cursor):
            end = source.find("*/", cursor + 2)
            assert end != -1
            cursor = end + 2
            continue
        if source[cursor] == "{":
            template_depth += 1
        elif source[cursor] == "}":
            template_depth -= 1
        cursor += 1
    raise AssertionError("unterminated HCL quoted string")


def _hcl_tokens(source: str) -> tuple[_HclToken, ...]:
    tokens: list[_HclToken] = []
    cursor = 0
    while cursor < len(source):
        if source[cursor] in "\r\n":
            if source[cursor] == "\r" and source.startswith("\r\n", cursor):
                cursor += 1
            tokens.append(_HclToken("newline", "\n"))
            cursor += 1
            continue
        if source[cursor].isspace():
            cursor += 1
            continue
        if source[cursor] == "#" or source.startswith("//", cursor):
            newline = source.find("\n", cursor)
            if newline == -1:
                cursor = len(source)
            else:
                tokens.append(_HclToken("newline", "\n"))
                cursor = newline + 1
            continue
        if source.startswith("/*", cursor):
            end = source.find("*/", cursor + 2)
            assert end != -1
            cursor = end + 2
            continue
        if source.startswith("<<", cursor):
            header = re.match(
                r"<<-?([A-Za-z_][A-Za-z0-9_]*)[^\n]*\n",
                source[cursor:],
            )
            if header is not None:
                delimiter = re.escape(header.group(1))
                body_start = cursor + header.end()
                terminator = re.search(
                    rf"(?m)^[ \t]*{delimiter}[ \t]*(?:\r?\n|$)",
                    source[body_start:],
                )
                assert terminator is not None
                tokens.append(_HclToken("newline", "\n"))
                cursor = body_start + terminator.end()
                continue
        if source[cursor] == '"':
            value, cursor = _hcl_quoted_string(source, cursor)
            tokens.append(_HclToken("string", value))
            continue
        identifier = re.match(r"[A-Za-z_][A-Za-z0-9_-]*", source[cursor:])
        if identifier is not None:
            tokens.append(_HclToken("identifier", identifier.group(0)))
            cursor += identifier.end()
            continue
        punctuation = {
            "{": "left_brace",
            "}": "right_brace",
            "=": "equals",
        }
        kind = punctuation.get(source[cursor])
        if kind is not None:
            tokens.append(_HclToken(kind, source[cursor]))
        else:
            tokens.append(_HclToken("symbol", source[cursor]))
        cursor += 1
    return tuple(tokens)


def _direct_blocks(tokens: tuple[_HclToken, ...]) -> tuple[_HclBlock, ...]:
    blocks: list[_HclBlock] = []
    cursor = 0
    while cursor < len(tokens):
        if tokens[cursor].kind != "identifier":
            cursor += 1
            continue
        kind = tokens[cursor].value
        header_end = cursor + 1
        labels: list[str] = []
        while header_end < len(tokens) and tokens[header_end].kind == "string":
            labels.append(tokens[header_end].value)
            header_end += 1
        if header_end >= len(tokens) or tokens[header_end].kind != "left_brace":
            cursor += 1
            continue
        depth = 1
        body_end = header_end + 1
        while body_end < len(tokens) and depth:
            if tokens[body_end].kind == "left_brace":
                depth += 1
            elif tokens[body_end].kind == "right_brace":
                depth -= 1
            body_end += 1
        assert depth == 0
        blocks.append(
            _HclBlock(
                kind=kind,
                labels=tuple(labels),
                body=tokens[header_end + 1 : body_end - 1],
            )
        )
        cursor = body_end
    return tuple(blocks)


def _required_block(
    blocks: tuple[_HclBlock, ...],
    kind: str,
    labels: tuple[str, ...] = (),
) -> _HclBlock:
    matches = [
        block for block in blocks if block.kind == kind and block.labels == labels
    ]
    assert len(matches) == 1
    return matches[0]


def _has_true_assignment(block: _HclBlock, name: str) -> bool:
    depth = 0
    for index, token in enumerate(block.body):
        if token.kind == "left_brace":
            depth += 1
            continue
        if token.kind == "right_brace":
            depth -= 1
            assert depth >= 0
            continue
        if (
            depth == 0
            and token == _HclToken("identifier", name)
            and block.body[index + 1 : index + 3]
            == (
                _HclToken("equals", "="),
                _HclToken("identifier", "true"),
            )
            and (
                index + 3 == len(block.body) or block.body[index + 3].kind == "newline"
            )
        ):
            return True
    assert depth == 0
    return False


def test_hcl_security_checks_ignore_non_live_decoys() -> None:
    source = """
    # resource "aws_dynamodb_table" "provider_authority" {}
    // resource "aws_iam_role" "also_not_live" {}
    /*
    point_in_time_recovery { enabled = true }
    output "protected" { sensitive = true }
    */
    # point_in_time_recovery { enabled = true }
    description = "server_side_encryption { enabled = true }"
    label = "resource \\"aws_kms_key\\" \\"not_live\\" {}"
    note = <<EOT
    output "protected" { sensitive = true }
    EOT
    locals {
      opener = "${format("%s{", "foo")}"
    }
    resource "aws_s3_bucket" "unexpected" {}
    point_in_time_recovery { enabled = true ? false : true }
    server_side_encryption {
      nested_decoy { enabled = true }
      enabled = false
    }
    output "protected" {
      sensitive = true /*
        multiline comment inside the expression
      */ ? false : true
    }
    """
    blocks = _direct_blocks(_hcl_tokens(source))
    resources = {block.labels for block in blocks if block.kind == "resource"}

    assert resources == {("aws_s3_bucket", "unexpected")}
    assert not _has_true_assignment(
        _required_block(blocks, "point_in_time_recovery"),
        "enabled",
    )
    assert not _has_true_assignment(
        _required_block(blocks, "server_side_encryption"),
        "enabled",
    )
    assert not _has_true_assignment(
        _required_block(blocks, "output", ("protected",)),
        "sensitive",
    )


def test_module_creates_only_the_shared_provider_authority_table() -> None:
    blocks = _direct_blocks(_hcl_tokens(_terraform()))
    resources = {block.labels for block in blocks if block.kind == "resource"}
    assert resources == {("aws_dynamodb_table", "provider_authority")}


def test_table_has_exact_runtime_key_schema() -> None:
    terraform = _terraform()

    assert re.search(r'\bhash_key\s*=\s*"authority_key"', terraform)
    assert re.search(r'\brange_key\s*=\s*"record_key"', terraform)
    assert terraform.count('name = "authority_key"') == 1
    assert terraform.count('name = "record_key"') == 1
    assert terraform.count('type = "S"') == 2
    assert "global_secondary_index" not in terraform
    assert "local_secondary_index" not in terraform


def test_table_is_fail_closed_against_loss_or_unbounded_capacity() -> None:
    terraform = _terraform()
    blocks = _direct_blocks(_hcl_tokens(terraform))
    table = _required_block(
        blocks,
        "resource",
        ("aws_dynamodb_table", "provider_authority"),
    )
    table_blocks = _direct_blocks(table.body)
    recovery = _required_block(table_blocks, "point_in_time_recovery")
    encryption = _required_block(table_blocks, "server_side_encryption")

    assert 'billing_mode = "PAY_PER_REQUEST"' in terraform
    assert "deletion_protection_enabled = true" in terraform
    assert _has_true_assignment(recovery, "enabled")
    assert _has_true_assignment(encryption, "enabled")
    assert 'attribute_name = "expires_at"' in terraform
    assert "prevent_destroy = true" in terraform
    assert "read_capacity" not in terraform
    assert "write_capacity" not in terraform


def test_table_name_and_public_identity_are_stable() -> None:
    variables = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    outputs = (INFRA_ROOT / "outputs.tf").read_text(encoding="utf-8")
    output_blocks = _direct_blocks(_hcl_tokens(outputs))

    assert 'variable "table_name"' in variables
    assert (
        'default     = "legalforecastbench-official-eval-provider-authority"'
        in variables
    )
    assert (
        'var.table_name == "legalforecastbench-official-eval-provider-authority"'
        in variables
    )
    table_name = _required_block(
        output_blocks,
        "output",
        ("provider_authority_table_name",),
    )
    table_arn = _required_block(
        output_blocks,
        "output",
        ("provider_authority_table_arn",),
    )
    assert _has_true_assignment(table_name, "sensitive")
    assert _has_true_assignment(table_arn, "sensitive")
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
    gitignore = (INFRA_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "table-only" in readme
    assert "terraform import" in readme
    assert "Terraform plan" in readme
    assert "Provider-free operator procedure" not in readme
    assert "protected operator" in readme
    assert "AWS provider" in readme
    assert "LFB_PROTECTED_STATE_DIR" in readme
    assert "LFB_PROVIDER_AUTHORITY_VAR_FILE" in readme
    assert '-state="$state_dir/terraform.tfstate"' in readme
    assert '-var-file="$var_file"' in readme
    assert "terraform -chdir=infra/provider-authority apply" in readme
    assert (
        'apply \\\n  -input=false \\\n  -state="$state_dir/terraform.tfstate"' in readme
    )
    assert "before John" not in readme
    assert "LegalForecastBench-5qd6.98.1" in readme
    assert "*.tfvars" in gitignore
    assert "*.tfvars.json" in gitignore
    assert "does not create IAM roles" in readme
    assert "does not create S3" in readme
    assert "`infra/provider-authority`" in runbook
    assert "Stage A/B" in runbook
    assert "separately authorized Terraform apply" in runbook
