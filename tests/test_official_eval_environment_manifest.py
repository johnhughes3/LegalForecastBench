from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra" / "official-eval" / "github-environments.json"
INFRA_WORKFLOW = (
    ROOT / ".github" / "workflows" / "official-provider-authority-infra.yaml"
)
RUNTIME_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "official-s3-access-validation.yaml",
    ROOT / ".github" / "workflows" / "run-benchmark.yaml",
    ROOT / ".github" / "actions" / "official-provider-cell" / "action.yml",
    ROOT / ".github" / "workflows" / "fan-in-publish.yaml",
    ROOT / ".github" / "workflows" / "stage-manifest-run.yaml",
    ROOT / ".github" / "workflows" / "stage-official-manifest-run.yaml",
)

INFRA_ENVIRONMENT = "legalforecastbench-official-provider-authority-infra"
CELL_ENVIRONMENT = "legalforecastbench-official-eval"
PREPARE_INPUTS_ENVIRONMENT = "legalforecastbench-official-eval-prepare-inputs"
FAN_IN_ENVIRONMENT = "legalforecastbench-official-eval-fan-in"
STAGING_ENVIRONMENT = "legalforecastbench-official-eval-manifest-staging"

INFRA_VARIABLES = {
    "LFB_AWS_REGION",
    "LFB_ARTIFACTS_KMS_KEY_ARN",
    "LFB_GITHUB_OIDC_PROVIDER_ARN",
    "LFB_INFRA_OPERATOR_ROLE_ARN",
    "LFB_INFRA_PLAN_AGE_RECIPIENT",
    "LFB_PACKET_BUCKET",
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256",
    "LFB_PROVIDER_AUTHORITY_TABLE_ARN",
    "LFB_RESULTS_BUCKET",
    "LFB_TERRAFORM_STATE_BUCKET",
    "LFB_TERRAFORM_STATE_KEY_PREFIX",
    "LFB_TERRAFORM_STATE_KMS_KEY_ID",
}
CELL_VARIABLES = {
    "LFB_ANTHROPIC_BEDROCK_MODEL_ID",
    "LFB_ANTHROPIC_RUNTIME",
    "LFB_AWS_REGION",
    "LFB_GITHUB_PACKET_READ_ROLE_ARN",
    "LFB_MODEL_PACKET_PREFIX",
    "LFB_PACKET_BUCKET",
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256",
    "LFB_PROVIDER_AUTHORITY_TABLE",
    "LFB_RESULTS_BUCKET",
    "LFB_RESULTS_MANIFEST_PREFIX",
}
# The canonical benchmark dispatcher now invokes the public runner directly,
# while the retained S3 validation workflow remains the producer of the
# packet-read cell variables. The composite provider-cell action also retains
# the two model/runtime variables for community callers, but action metadata
# is not a workflow job and therefore cannot be discovered by the environment
# inventory sweep below.
CELL_RUNTIME_VARIABLES = {
    "LFB_AWS_REGION",
    "LFB_GITHUB_PACKET_READ_ROLE_ARN",
    "LFB_MODEL_PACKET_PREFIX",
    "LFB_PACKET_BUCKET",
    "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256",
    "LFB_PROVIDER_AUTHORITY_TABLE",
    "LFB_RESULTS_BUCKET",
    "LFB_RESULTS_MANIFEST_PREFIX",
}
PREPARE_INPUTS_VARIABLES = {
    "LFB_AWS_REGION",
    "LFB_GITHUB_PREPARE_INPUTS_ROLE_ARN",
    "LFB_RESULTS_BUCKET",
}
FAN_IN_VARIABLES = {
    "LFB_AWS_REGION",
    "LFB_GITHUB_FAN_IN_ROLE_ARN",
    "LFB_PACKET_BUCKET",
    "LFB_RESULTS_BUCKET",
}
# Staging touches no provider and no DynamoDB table, so its environment carries
# only the two bucket names, the region, and its own role ARN.
STAGING_VARIABLES = {
    "LFB_AWS_REGION",
    "LFB_GITHUB_MANIFEST_STAGING_ROLE_ARN",
    "LFB_PACKET_BUCKET",
    "LFB_RESULTS_BUCKET",
}
# Staging reaches no provider, and this is not a provider key. It is the age
# decryption identity for the closed corpus package a FIRST official staging has
# to carry in: that package holds the un-run evaluation inputs and the final
# labels, so it travels as ciphertext on a never-published draft release and the
# runner is the only place it is opened. Nothing else in this environment is a
# secret, and nothing here reaches a model provider.
STAGING_SECRETS = {"LFB_STAGE_SOURCE_AGE_IDENTITY"}
CELL_SECRETS = {
    "AI_GATEWAY_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
}
LOCKED_WORKFLOW_CELL_SECRETS = {
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
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


def _workflow_names(text: str, context: str) -> set[str]:
    if context == "secrets":
        # Reusable provider cells select one secret conditionally, so the
        # reference is not immediately after the expression opener.
        return set(re.findall(rf"\b{context}\.([A-Za-z0-9_]+)", text))
    return set(re.findall(rf"\$\{{\{{\s*{context}\.([A-Za-z0-9_]+)", text))


def _workflow_names_by_environment(text: str, context: str) -> dict[str, set[str]]:
    job_starts = list(re.finditer(r"(?m)^  [A-Za-z0-9_-]+:\n", text))
    names_by_environment: dict[str, set[str]] = {}

    for index, job_start in enumerate(job_starts):
        job_end = job_starts[index + 1].start() if index + 1 < len(job_starts) else None
        job_text = text[job_start.start() : job_end]
        environment_match = re.search(
            r"(?m)^    environment: ([A-Za-z0-9_-]+)$", job_text
        )
        if environment_match is None:
            continue
        environment = environment_match.group(1)
        names_by_environment.setdefault(environment, set()).update(
            _workflow_names(job_text, context)
        )

    return names_by_environment


def test_manifest_is_closed_to_the_five_official_eval_environments() -> None:
    manifest = _manifest()
    environments = _environments()

    assert set(manifest) == {
        "schema_version",
        "repository",
        "common_protection",
        "environments",
    }
    assert manifest["schema_version"] == (
        "legalforecast.official_eval_github_environments.v1"
    )
    assert manifest["repository"] == "johnhughes3/LegalForecastBench"
    assert set(environments) == {
        INFRA_ENVIRONMENT,
        CELL_ENVIRONMENT,
        PREPARE_INPUTS_ENVIRONMENT,
        FAN_IN_ENVIRONMENT,
        STAGING_ENVIRONMENT,
    }
    assert len(environments) == 5
    assert all(
        set(row) == {"name", "authority", "aws_oidc_subject", "secrets", "variables"}
        for row in environments.values()
    )


def test_every_environment_is_human_reviewed_and_main_only() -> None:
    protection = cast(dict[str, object], _manifest()["common_protection"])
    branch_policy = cast(dict[str, object], protection["deployment_branch_policy"])

    assert set(protection) == {
        "required_reviewers",
        "prevent_self_review",
        "deployment_branch_policy",
        "custom_branch_policies",
    }
    assert protection["required_reviewers"] == [
        {"type": "User", "login": "johnjhughes"}
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
    infra = environments[INFRA_ENVIRONMENT]
    cell = environments[CELL_ENVIRONMENT]
    prepare_inputs = environments[PREPARE_INPUTS_ENVIRONMENT]
    fan_in = environments[FAN_IN_ENVIRONMENT]

    assert infra["authority"] == "infrastructure_operator"
    assert infra["secrets"] == ["LFB_INFRA_PLAN_AGE_IDENTITY"]
    assert set(cast(list[str], infra["variables"])) == INFRA_VARIABLES

    assert cell["authority"] == "evaluation_cell"
    assert set(cast(list[str], cell["secrets"])) == CELL_SECRETS
    assert set(cast(list[str], cell["variables"])) == CELL_VARIABLES

    assert prepare_inputs["authority"] == "prepare_inputs"
    assert prepare_inputs["secrets"] == []
    assert set(cast(list[str], prepare_inputs["variables"])) == PREPARE_INPUTS_VARIABLES

    assert fan_in["authority"] == "fan_in"
    assert fan_in["secrets"] == []
    assert set(cast(list[str], fan_in["variables"])) == FAN_IN_VARIABLES

    staging = environments[STAGING_ENVIRONMENT]
    assert staging["authority"] == "manifest_staging"
    assert set(cast(list[str], staging["secrets"])) == STAGING_SECRETS
    assert set(cast(list[str], staging["variables"])) == STAGING_VARIABLES


def test_oidc_subjects_and_role_variables_do_not_cross_environments() -> None:
    environments = _environments()
    role_placements = {
        INFRA_ENVIRONMENT: "LFB_INFRA_OPERATOR_ROLE_ARN",
        CELL_ENVIRONMENT: "LFB_GITHUB_PACKET_READ_ROLE_ARN",
        PREPARE_INPUTS_ENVIRONMENT: "LFB_GITHUB_PREPARE_INPUTS_ROLE_ARN",
        FAN_IN_ENVIRONMENT: "LFB_GITHUB_FAN_IN_ROLE_ARN",
        STAGING_ENVIRONMENT: "LFB_GITHUB_MANIFEST_STAGING_ROLE_ARN",
    }

    for environment, expected_role in role_placements.items():
        row = environments[environment]
        assert row["aws_oidc_subject"] == (
            "repo:johnhughes3/LegalForecastBench:environment:" + environment
        )
        variables = set(cast(list[str], row["variables"]))
        assert variables & set(role_placements.values()) == {expected_role}


def test_manifest_inventories_match_the_workflow_configuration_names() -> None:
    infra_text = INFRA_WORKFLOW.read_text(encoding="utf-8")
    runtime_texts = [
        workflow.read_text(encoding="utf-8") for workflow in RUNTIME_WORKFLOWS
    ]
    runtime_variables: dict[str, set[str]] = {
        CELL_ENVIRONMENT: set(),
        PREPARE_INPUTS_ENVIRONMENT: set(),
        FAN_IN_ENVIRONMENT: set(),
        STAGING_ENVIRONMENT: set(),
    }
    runtime_secrets: dict[str, set[str]] = {
        CELL_ENVIRONMENT: set(),
        PREPARE_INPUTS_ENVIRONMENT: set(),
        FAN_IN_ENVIRONMENT: set(),
        STAGING_ENVIRONMENT: set(),
    }
    for runtime_text in runtime_texts:
        for environment, names in _workflow_names_by_environment(
            runtime_text, "vars"
        ).items():
            runtime_variables[environment].update(names)
        for environment, names in _workflow_names_by_environment(
            runtime_text, "secrets"
        ).items():
            runtime_secrets[environment].update(names)

    assert _workflow_names(infra_text, "vars") == INFRA_VARIABLES
    assert _workflow_names(infra_text, "secrets") == {"LFB_INFRA_PLAN_AGE_IDENTITY"}
    # Protected-environment jobs stay on GitHub-hosted ubuntu-latest and do not
    # read vars.CI_RUNNER, so the environment-scoped inventory matches the
    # manifest. Repo/org CI_RUNNER may appear on jobs without environment:.
    assert runtime_variables[CELL_ENVIRONMENT] == CELL_RUNTIME_VARIABLES
    assert runtime_variables[CELL_ENVIRONMENT] <= CELL_VARIABLES
    assert runtime_variables[FAN_IN_ENVIRONMENT] == FAN_IN_VARIABLES
    assert runtime_variables[STAGING_ENVIRONMENT] == STAGING_VARIABLES
    # The sibling run-benchmark lane wires this environment when it lands. Keep
    # the manifest contract test useful on either side of that integration.
    assert runtime_variables[PREPARE_INPUTS_ENVIRONMENT] in (
        set(),
        PREPARE_INPUTS_VARIABLES,
    )
    assert runtime_secrets == {
        CELL_ENVIRONMENT: LOCKED_WORKFLOW_CELL_SECRETS,
        PREPARE_INPUTS_ENVIRONMENT: set(),
        FAN_IN_ENVIRONMENT: set(),
        # Staging reaches no provider, so the one secret its environment holds is
        # the corpus package's age decryption identity and nothing else.
        STAGING_ENVIRONMENT: STAGING_SECRETS,
    }

    for environment in (
        INFRA_ENVIRONMENT,
        CELL_ENVIRONMENT,
        FAN_IN_ENVIRONMENT,
        STAGING_ENVIRONMENT,
    ):
        assert environment in infra_text + "\n".join(runtime_texts)
    # The sibling run-benchmark lane will reference this environment when its
    # preparation job switches to the dedicated role.
    assert PREPARE_INPUTS_ENVIRONMENT in MANIFEST.read_text(encoding="utf-8")


def test_public_manifest_contains_names_not_configuration_values() -> None:
    text = MANIFEST.read_text(encoding="utf-8")

    assert "arn:aws" not in text
    assert "AKIA" not in text
    assert "age1" not in text
    assert "PRIVATE KEY" not in text
