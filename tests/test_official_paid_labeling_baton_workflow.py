from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "official-paid-labeling-baton.yaml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_baton_workflow_is_provider_free_and_ciphertext_only() -> None:
    text = _text()

    assert "environment: legalforecastbench-official-labeling-baton" in text
    assert "id-token: write" not in text
    assert "PROVIDER_API_KEY" not in text
    assert "OPENAI_API_KEY" not in text
    assert "ANTHROPIC_API_KEY" not in text
    assert "GEMINI_API_KEY" not in text
    assert "aws " not in text
    assert "run-benchmark" not in text
    assert "legalforecast freeze" not in text
    assert "gh workflow run" not in text
    assert "fan-in-publish" not in text
    assert "BATON_AGE_IDENTITY" in text
    upload = text.split("- name: Upload ciphertext-only paid-labeling baton", 1)[1]
    assert "official-paid-labeling-baton.age" in upload
    assert "baton-receipt.json" in upload
    assert "JOB_ROOT" not in upload
    assert "private/job" not in upload


def test_baton_workflow_requires_exact_main_release_and_closed_pairs() -> None:
    text = _text()

    assert '[[ "${GITHUB_REF}" != "refs/heads/main" ]]' in text
    assert '[[ "${RELEASE_SHA}" != "${GITHUB_SHA}" ]]' in text
    assert '[[ "$(git rev-parse HEAD)" != "${GITHUB_SHA}" ]]' in text
    for pair in (
        "llm-unitize:anthropic",
        "llm-review-stage-a:google",
        "llm-label-provider-shard:openai",
        "llm-label-provider-shard:google",
    ):
        assert pair in text
    assert "git merge-base --is-ancestor" not in text
    assert "git fetch" not in text


def test_baton_workflow_authenticates_draft_asset_and_predecessor() -> None:
    text = _text()

    assert ".draft == true" in text
    assert "/releases/assets/${SOURCE_ASSET_ID}" in text
    assert ".digest == $digest" in text
    assert "sha256sum --check --strict" in text
    assert '".github/workflows/official-paid-labeling.yaml"' in text
    assert '.event == "workflow_dispatch"' in text
    assert '.head_branch == "main"' in text
    assert ".head_sha == $release_sha" in text
    assert ".run_attempt == $attempt" in text
    assert '.conclusion == "success"' in text
    assert "predecessor-package-manifest-sha256" in text
    assert "assemble-paid-labeling-baton" in text
    assert ".target_commitish == $release_sha" in text
    assert (
        "official-paid-labeling-source-${RELEASE_SHA}-${STAGE}-${PROVIDER}-${SEQUENCE_ORDINAL}.age"
        in text
    )
    assert "-${predecessor_run_id}-${predecessor_run_attempt}" in text
    assert "predecessor_name" in text


def test_baton_workflow_clears_plaintext_before_upload() -> None:
    text = _text()

    assert "id: clear_sensitive" in text
    assert "shred --force --iterations=1 --zero --remove" in text
    assert '"${BATON_ROOT}/private" "${JOB_ROOT}"' in text
    assert 'test ! -e "${sensitive_root}"' in text
    assert text.index("Clear plaintext and decryption identity") < text.index(
        "Upload ciphertext-only paid-labeling baton"
    )
    assert "steps.clear_sensitive.outcome == 'success'" in text
    assert "steps.assemble.outcome == 'success'" in text


def test_baton_and_provider_workflows_use_the_same_canonical_job_root() -> None:
    text = _text()
    provider = (
        ROOT / ".github" / "workflows" / "official-paid-labeling.yaml"
    ).read_text(encoding="utf-8")

    canonical = "JOB_ROOT: ${{ github.workspace }}/.official-paid-labeling-job"
    assert canonical in text
    assert canonical in provider
    assert '--job-root "${JOB_ROOT}"' in text
    assert "private/job" not in text


def test_baton_workflow_pins_actions_and_age_archive() -> None:
    text = _text()
    uses = re.findall(r"^\s*uses:\s*(\S+)\s*(?:#.*)?$", text, re.MULTILINE)

    assert uses
    for action in uses:
        _, reference = action.rsplit("@", 1)
        assert len(reference) == 40
        assert all(character in "0123456789abcdef" for character in reference)
    assert "age-v1.3.1-linux-amd64.tar.gz" in text
    assert "bdc69c09cbdd6cf8b1f333d372a1f58247b3a33146406333e30c0f26e8f51377" in text
