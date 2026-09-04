"""The two-subject manifest-staging trust that carries the corpus handoff.

Manifest staging is the only official-eval role whose trust admits a second
GitHub OIDC subject: the private corpus repository issues the outcome-blinded
release and hands it to the official results bucket under this same role ARN.
Because the assumed principal is unchanged, widening this trust is the whole
AWS-side change -- the results/packet bucket policies and the artifacts KMS key
policy name principals by role ARN and never see a repository claim.

These fences live apart from ``test_official_eval_infra.py`` so the four-role
topology file stays inside its reviewed size.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest
from tests.official_infra_trust_helpers import render_policy_template

ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = ROOT / "infra" / "official-eval"
POLICY_ROOT = INFRA_ROOT / "policies"
TRUST_TEMPLATE = POLICY_ROOT / "manifest-staging-trust.json.tftpl"

OIDC_PROVIDER_ARN = (
    "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
)
REPOSITORY = "johnhughes3/LegalForecastBench"
REF = "refs/heads/main"
MANIFEST_STAGING_ENVIRONMENT = "legalforecastbench-official-eval-manifest-staging"
SUBJECT = f"repo:{REPOSITORY}:environment:{MANIFEST_STAGING_ENVIRONMENT}"

# The corpus repository's numeric identifiers are Terraform inputs with no
# defaults, so these are deliberately placeholders: a fence that passed only
# against the production IDs would be testing the tfvars file, not the module.
CORPUS_REPOSITORY = "johnhughes3/LegalForecastCorpus"
CORPUS_REPOSITORY_ID = "1010101010"
CORPUS_REPOSITORY_OWNER_ID = "2020202020"
CORPUS_ENVIRONMENT = "corpus-release-staging"
CORPUS_SUBJECT = (
    "repo:johnhughes3@2020202020/LegalForecastCorpus@1010101010"
    f":environment:{CORPUS_ENVIRONMENT}"
)

JsonObject = dict[str, object]


def _trust_policy() -> JsonObject:
    return render_policy_template(
        TRUST_TEMPLATE,
        github_oidc_provider_arn=OIDC_PROVIDER_ARN,
        github_repository=REPOSITORY,
        github_ref=REF,
        github_subject=SUBJECT,
        corpus_github_repository=CORPUS_REPOSITORY,
        corpus_github_repository_id=CORPUS_REPOSITORY_ID,
        corpus_github_repository_owner_id=CORPUS_REPOSITORY_OWNER_ID,
        corpus_github_environment=CORPUS_ENVIRONMENT,
        corpus_github_subject=CORPUS_SUBJECT,
    )


def _assert_exact_trust(policy: Mapping[str, object]) -> None:
    assert set(policy) == {"Version", "Statement"}
    assert policy["Version"] == "2012-10-17"
    assert policy["Statement"] == [
        {
            "Sid": "GitHubActionsOidc",
            "Effect": "Allow",
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Principal": {"Federated": OIDC_PROVIDER_ARN},
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": SUBJECT,
                    "token.actions.githubusercontent.com:repository": REPOSITORY,
                    "token.actions.githubusercontent.com:ref": REF,
                }
            },
        },
        {
            "Sid": "GitHubActionsOidcCorpusReleaseStaging",
            "Effect": "Allow",
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Principal": {"Federated": OIDC_PROVIDER_ARN},
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": CORPUS_SUBJECT,
                    "token.actions.githubusercontent.com:repository": CORPUS_REPOSITORY,
                    "token.actions.githubusercontent.com:repository_id": (
                        CORPUS_REPOSITORY_ID
                    ),
                    "token.actions.githubusercontent.com:repository_owner_id": (
                        CORPUS_REPOSITORY_OWNER_ID
                    ),
                    "token.actions.githubusercontent.com:environment": (
                        CORPUS_ENVIRONMENT
                    ),
                    "token.actions.githubusercontent.com:ref": REF,
                }
            },
        },
    ]


def _corpus_claims(policy: JsonObject) -> JsonObject:
    statement = cast(JsonObject, cast(list[object], policy["Statement"])[1])
    condition = cast(JsonObject, statement["Condition"])
    return cast(JsonObject, condition["StringEquals"])


def test_trust_admits_exactly_two_exactly_pinned_subjects() -> None:
    """The public staging environment and the corpus release-staging environment."""

    _assert_exact_trust(_trust_policy())


def test_neither_statement_is_a_list_or_a_pattern() -> None:
    """Two exact statements, never one loosened statement.

    A single statement carrying list-valued or ``StringLike`` claims would admit
    the cartesian product of the two repositories' claim sets: a token bearing
    one repository's subject and the other's repository name would satisfy it.
    Each statement therefore stays wholly single-valued.
    """

    statements = _trust_policy()["Statement"]
    assert isinstance(statements, list)
    assert len(statements) == 2
    for raw_statement in cast(list[object], statements):
        statement = cast(JsonObject, raw_statement)
        assert statement["Effect"] == "Allow"
        assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
        assert statement["Principal"] == {"Federated": OIDC_PROVIDER_ARN}
        condition = cast(JsonObject, statement["Condition"])
        assert set(condition) == {"StringEquals"}
        claims = cast(JsonObject, condition["StringEquals"])
        assert claims
        for name, value in claims.items():
            assert name.startswith("token.actions.githubusercontent.com:")
            assert isinstance(value, str)
            assert value
            assert "*" not in value
            assert "?" not in value


def test_trust_guard_rejects_widened_or_dropped_claims() -> None:
    """Prove the guard discriminates rather than validating a copy of itself.

    Each mutation is a real way a later edit could loosen this trust, and each
    must redden the guard.
    """

    merged = copy.deepcopy(_trust_policy())
    merged_statements = cast(list[object], merged["Statement"])
    public_statement = cast(JsonObject, merged_statements[0])
    public_claims = cast(
        JsonObject, cast(JsonObject, public_statement["Condition"])["StringEquals"]
    )
    public_claims["token.actions.githubusercontent.com:sub"] = [SUBJECT, CORPUS_SUBJECT]
    merged["Statement"] = [public_statement]
    with pytest.raises(AssertionError):
        _assert_exact_trust(merged)

    patterned = copy.deepcopy(_trust_policy())
    corpus_statement = cast(JsonObject, cast(list[object], patterned["Statement"])[1])
    corpus_statement["Condition"] = {
        "StringLike": {"token.actions.githubusercontent.com:sub": "repo:*"}
    }
    with pytest.raises(AssertionError):
        _assert_exact_trust(patterned)

    unpinned = copy.deepcopy(_trust_policy())
    del _corpus_claims(unpinned)["token.actions.githubusercontent.com:repository_id"]
    with pytest.raises(AssertionError):
        _assert_exact_trust(unpinned)

    unbranched = copy.deepcopy(_trust_policy())
    _corpus_claims(unbranched)["token.actions.githubusercontent.com:ref"] = (
        "refs/heads/*"
    )
    with pytest.raises(AssertionError):
        _assert_exact_trust(unbranched)

    dropped = copy.deepcopy(_trust_policy())
    dropped["Statement"] = [cast(list[object], dropped["Statement"])[0]]
    with pytest.raises(AssertionError):
        _assert_exact_trust(dropped)


def test_only_manifest_staging_renders_from_the_two_subject_template() -> None:
    """Admitting a second repository must not touch the other three trusts."""

    locals_text = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    two_subject = re.findall(
        r'templatefile\(\s*"\$\{path\.module\}/policies/manifest-staging-trust'
        r'\.json\.tftpl"',
        locals_text,
    )
    assert len(two_subject) == 1
    single_subject = re.findall(
        r'templatefile\(\s*"\$\{path\.module\}/policies/github-oidc-trust\.json\.tftpl"',
        locals_text,
    )
    assert len(single_subject) == 3
    terraform = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(INFRA_ROOT.glob("*.tf"))
    )
    assert (
        "assume_role_policy   = local.manifest_staging_trust_policy_json" in terraform
    )


def test_corpus_subject_is_derived_in_the_immutable_claim_form() -> None:
    """The corpus repository opts into GitHub's immutable subject claim.

    Its ``sub`` names numeric owner and repository IDs rather than the mutable
    owner/repository pair this repository uses. Deriving the subject in Terraform
    instead of accepting it as free-form input keeps a reverted customization
    fail-closed: the default subject stops matching and the assume is refused.
    """

    locals_text = (INFRA_ROOT / "locals.tf").read_text(encoding="utf-8")
    assert (
        'corpus_github_repository_parts = split("/", var.corpus_github_repository)'
        in locals_text
    )
    assert (
        '"repo:${local.corpus_github_repository_parts[0]}'
        '@${var.corpus_github_repository_owner_id}"'
    ) in locals_text
    assert (
        '"/${local.corpus_github_repository_parts[1]}'
        '@${var.corpus_github_repository_id}"'
    ) in locals_text
    assert '":environment:${var.corpus_github_environment}"' in locals_text


def test_corpus_numeric_identifiers_are_inputs_rather_than_committed_constants() -> (
    None
):
    """This repository is public.

    Another repository's numeric identifiers are supplied at apply time from the
    protected variable file rather than committed here.
    """

    variables = (INFRA_ROOT / "variables.tf").read_text(encoding="utf-8")
    for name in ("corpus_github_repository_id", "corpus_github_repository_owner_id"):
        block = re.search(
            rf'variable "{name}" \{{(.*?)\n\}}\n', variables, flags=re.DOTALL
        )
        assert block is not None, name
        body = block.group(1)
        assert "default" not in body, name
        assert "type        = string" in body, name
        assert "validation" in body, name
    assert not re.search(
        r'corpus_github_repository_(owner_)?id\s*=\s*"[0-9]',
        variables,
    )
    tfvars = (INFRA_ROOT / "terraform.tfvars.example").read_text(encoding="utf-8")
    assert 'corpus_github_repository_id       = "replace-with-' in tfvars
    assert 'corpus_github_repository_owner_id = "replace-with-' in tfvars
