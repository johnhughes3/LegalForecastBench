from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra" / "official-labeling" / "github-environments.json"
PAID_WORKFLOW = ROOT / ".github" / "workflows" / "official-paid-labeling.yaml"
BATON_WORKFLOW = ROOT / ".github" / "workflows" / "official-paid-labeling-baton.yaml"
SMOKE_WORKFLOW = (
    ROOT / ".github" / "workflows" / "official-paid-labeling-authority-smoke.yaml"
)

BATON_ENVIRONMENT = "legalforecastbench-official-labeling-baton"
SMOKE_ENVIRONMENT = "legalforecastbench-official-labeling-authority-smoke"
PROVIDER_ENVIRONMENTS = {
    "legalforecastbench-official-labeling-anthropic-unitize": "anthropic",
    "legalforecastbench-official-labeling-google-review": "google",
    "legalforecastbench-official-labeling-openai-label": "openai",
    "legalforecastbench-official-labeling-google-label": "google",
}
AWS_VARIABLES = {
    "LFB_AWS_REGION",
    "LFB_GITHUB_LABELING_ROLE_ARN",
    "LFB_PROVIDER_AUTHORITY_TABLE",
}


def _manifest() -> dict[str, object]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _environments() -> dict[str, dict[str, object]]:
    rows = _manifest()["environments"]
    assert isinstance(rows, list)
    typed_rows = cast(list[dict[str, object]], rows)
    return {cast(str, row["name"]): row for row in typed_rows}


def test_manifest_is_closed_to_the_exact_six_paid_labeling_environments() -> None:
    manifest = _manifest()
    environments = _environments()

    assert manifest["schema_version"] == (
        "legalforecast.paid_labeling_github_environments.v1"
    )
    assert manifest["repository"] == "johnhughes3/LegalForecastBench"
    assert set(environments) == {
        BATON_ENVIRONMENT,
        SMOKE_ENVIRONMENT,
        *PROVIDER_ENVIRONMENTS,
    }
    assert len(environments) == 6


def test_every_environment_is_human_reviewed_and_main_only() -> None:
    protection = cast(dict[str, object], _manifest()["common_protection"])
    branch_policy = cast(dict[str, object], protection["deployment_branch_policy"])

    assert protection["required_reviewers"] == [
        {"type": "User", "login": "johnhughes3"}
    ]
    assert protection["prevent_self_review"] is False
    assert branch_policy == {
        "protected_branches": False,
        "custom_branch_policies": True,
    }
    assert protection["custom_branch_policies"] == ["main"]
    assert all("protection" not in row for row in _environments().values())


def test_manifest_has_exact_secret_and_variable_inventories() -> None:
    environments = _environments()
    baton = environments[BATON_ENVIRONMENT]
    smoke = environments[SMOKE_ENVIRONMENT]

    assert baton["aws_oidc_subject"] is None
    assert baton["provider"] is None
    assert baton["secrets"] == ["BATON_AGE_IDENTITY"]
    assert baton["variables"] == ["LFB_BATON_AGE_RECIPIENT"]

    assert smoke["provider"] is None
    assert smoke["secrets"] == []
    assert set(cast(list[str], smoke["variables"])) == AWS_VARIABLES | {
        "LFB_OUTSIDE_AUTHORITY_TABLE",
        "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256",
    }

    for environment, provider in PROVIDER_ENVIRONMENTS.items():
        row = environments[environment]
        assert row["provider"] == provider
        assert row["secrets"] == ["BATON_AGE_IDENTITY", "PROVIDER_API_KEY"]
        assert set(cast(list[str], row["variables"])) == AWS_VARIABLES | {
            "LFB_BATON_AGE_RECIPIENT",
            "LFB_PROVIDER_ACCOUNT_ALIAS",
        }
        assert row["aws_oidc_subject"] == (
            "repo:johnhughes3/LegalForecastBench:environment:" + environment
        )


def test_manifest_matches_the_three_runtime_workflows() -> None:
    environments = _environments()
    paid_text = PAID_WORKFLOW.read_text(encoding="utf-8")
    baton_text = BATON_WORKFLOW.read_text(encoding="utf-8")
    smoke_text = SMOKE_WORKFLOW.read_text(encoding="utf-8")

    for environment in PROVIDER_ENVIRONMENTS:
        assert environment in paid_text
    assert BATON_ENVIRONMENT in baton_text
    assert SMOKE_ENVIRONMENT in smoke_text

    manifest_secrets = {
        secret
        for row in environments.values()
        for secret in cast(list[str], row["secrets"])
    }
    workflow_secrets = set(
        re.findall(
            r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)\s*\}\}",
            paid_text + baton_text + smoke_text,
        )
    )
    assert workflow_secrets == manifest_secrets

    manifest_variables = {
        variable
        for row in environments.values()
        for variable in cast(list[str], row["variables"])
    }
    workflow_variables = set(
        re.findall(
            r"\$\{\{\s*vars\.([A-Za-z0-9_]+)",
            paid_text + baton_text + smoke_text,
        )
    )
    assert workflow_variables == manifest_variables
