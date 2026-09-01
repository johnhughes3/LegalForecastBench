"""Community intake for the containerized harness lane.

The lane's value to an outsider is the transcript: a bare-API number can be
reproduced from a model card, but "did the harness beat the API" is only
believable if you can read what the harness actually did.  A contributor cannot
mail us that, so this module's tests hold the intake honest in both directions --
the substance has to survive readable, and the credentials and host paths have to
be gone before any byte is offered for upload to storage we host.

Nothing here is an official LegalForecastBench result, and the package says so
in its own record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.multiharness.harness_lane.community_intake import (
    CommunityHarnessSubmission,
    CommunityIntakeError,
    build_community_harness_submission,
    validate_community_harness_submission,
)
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailError,
)
from tests.test_multiharness_harness_lane_run import (
    _HOST_HOME,  # pyright: ignore[reportPrivateUsage]
    _HOST_SESSION,  # pyright: ignore[reportPrivateUsage]
    _PLANTED_MARKERS,  # pyright: ignore[reportPrivateUsage]
    _fixture_run_directory,  # pyright: ignore[reportPrivateUsage]
)

_SUBSTANTIVE_TRANSCRIPT = (
    "PROMPT: Forecast whether the motion to dismiss is granted in full.\n"
    "THINKING: The complaint pleads scienter through the confidential-witness\n"
    "  accounts in paragraphs 61-74, which the opposition never rebuts.\n"
    'TOOL Read(/workspace/task/complaint.txt) -> "Plaintiffs allege that ..."\n'
    "TOOL Bash(grep -c 'Rule 12(b)(6)' /workspace/task/opposition.txt) -> 4\n"
    "ANSWER: probability_fully_dismissed 0.35; the scienter theory survives.\n"
)


def _community_run_directory(root: Path) -> Path:
    """The shared fixture plus a transcript with something worth reading."""

    run_dir = _fixture_run_directory(root)
    (run_dir / "rows" / "row-0" / "container-logs" / "harness.log").write_text(
        f"HOME={_HOST_HOME}/lfb\nsession={_HOST_SESSION}\n" + _SUBSTANTIVE_TRANSCRIPT,
        encoding="utf-8",
    )
    return run_dir


def _package_community_submission(root: Path) -> CommunityHarnessSubmission:
    return build_community_harness_submission(
        run_dir=_community_run_directory(root),
        output_dir=root / "submission",
        submission_id="community-harness-fixture",
        submitter_name="Example Contributor",
        submitter_github="example-contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        # The automatic layer catches host roots and provider-token shapes; a
        # contributor declares anything else exactly, the way this session id is.
        secret_values=(_HOST_SESSION,),
    )


def test_the_packaged_submission_keeps_the_substance_a_reader_needs(
    tmp_path: Path,
) -> None:
    submission = _package_community_submission(tmp_path)

    transcript = (
        submission.submission_dir
        / "full-results"
        / "rows"
        / "row-0"
        / "container-logs"
        / "harness.log"
    ).read_text(encoding="utf-8")
    # Light touch means light: the prompt, the reasoning, both tool calls with
    # their arguments and their outputs, and the answer all survive verbatim.
    for line in _SUBSTANTIVE_TRANSCRIPT.splitlines():
        assert line in transcript, line
    # A container path is not host data -- the workspace is the one thing the
    # container can see -- so it stays readable rather than being blanked.
    assert "/workspace/task/complaint.txt" in transcript
    record = json.loads(
        (submission.submission_dir / "community-harness-submission.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["official"] is False
    assert record["result_class"] == "community_harness_lane"
    assert "not_official_legalforecastbench_result" in record["attestations"]
    assert record["run_id"] == "harness-lane-fixture"


def test_the_packaged_submission_carries_no_credential_or_host_path(
    tmp_path: Path,
) -> None:
    submission = _package_community_submission(tmp_path)

    for path in sorted(submission.submission_dir.rglob("*")):
        if not path.is_file():
            continue
        payload = path.read_bytes()
        for marker in _PLANTED_MARKERS:
            assert marker.encode("utf-8") not in payload, f"{marker} in {path.name}"
    transcript = (
        submission.submission_dir
        / "full-results"
        / "rows"
        / "row-0"
        / "container-logs"
        / "stdout.log"
    ).read_text(encoding="utf-8")
    # The rewrite says which credential appeared and where the path pointed,
    # which is the reviewable fact, without the secret or the operator's name.
    assert "token=sk-ant-[redacted]" in transcript
    assert "HOME=/[host-home]" in transcript
    assert "unix:///[host-runtime]/docker.sock" in transcript
    rows = (submission.submission_dir / "full-results" / "row-results.jsonl").read_text(
        encoding="utf-8"
    )
    assert "/[host-home]/lfb/run/rows/row-0" in rows

    # Everything the plan declares is what is actually there.
    assert validate_community_harness_submission(submission.submission_dir)


def test_a_declared_digest_that_no_longer_matches_the_bytes_is_refused(
    tmp_path: Path,
) -> None:
    submission = _package_community_submission(tmp_path)
    transcript = (
        submission.submission_dir
        / "full-results"
        / "rows"
        / "row-0"
        / "container-logs"
        / "harness.log"
    )
    # One flipped byte, same length, so only the digest can catch it.
    transcript.write_bytes(transcript.read_bytes().replace(b"0.35", b"0.95"))

    with pytest.raises(CommunityIntakeError, match="does not match the declared"):
        validate_community_harness_submission(submission.submission_dir)


def test_an_undeclared_file_smuggled_beside_the_plan_is_refused(
    tmp_path: Path,
) -> None:
    submission = _package_community_submission(tmp_path)
    (submission.submission_dir / "full-results" / "extra.log").write_text(
        "bytes nobody declared\n", encoding="utf-8"
    )

    with pytest.raises(CommunityIntakeError, match="does not declare"):
        validate_community_harness_submission(submission.submission_dir)


def test_a_residual_secret_the_scrubber_missed_refuses_the_package(
    tmp_path: Path,
) -> None:
    run_dir = _community_run_directory(tmp_path)
    # A shape no rewrite rule claims to know: the guardrails are the backstop,
    # and a backstop that quietly rewrote this would be worse than one that stops.
    (run_dir / "rows" / "row-0" / "container-logs" / "leak.log").write_text(
        "AWS_ACCESS_KEY_ID=AKIAEXAMPLEEXAMPLE12\n", encoding="utf-8"
    )

    with pytest.raises(PublicationGuardrailError):
        build_community_harness_submission(
            run_dir=run_dir,
            output_dir=tmp_path / "submission",
            submission_id="community-harness-fixture",
            submitter_name="Example Contributor",
            run_operator_name="Example Contributor",
            adapter_author_name="Example Contributor",
        )


def test_the_community_intake_workflow_stays_maintainer_triggered() -> None:
    workflow = Path(".github/workflows/community-harness-intake.yaml").read_text(
        encoding="utf-8"
    )

    # workflow_dispatch only. A stranger's pull request must never be able to
    # start a job that pushes bytes into a repository we host.
    assert workflow.startswith("name: Community Harness Lane Intake\n")
    assert "\non:\n  workflow_dispatch:\n" in workflow
    assert "pull_request:" not in workflow
    assert "pull_request_target:" not in workflow
    assert "\npermissions: {}\n" in workflow
    assert "environment: legalforecastbench-community-artifacts" in workflow
    assert "      contents: read\n      id-token: write\n" in workflow
    # Validation runs before anything is offered for upload, and the ordering is
    # the point: caps and digests first, secret scan last, upload after both.
    validate_at = workflow.index("community_intake_cli \\\n            validate")
    upload_at = workflow.index("api.upload_folder(")
    assert validate_at < upload_at
    # No durable credential: the HF token is exchanged from the OIDC identity,
    # exactly as docs/hugging-face-publication.md describes for the official lane.
    assert "HF_OIDC_RESOURCE: datasets/${{ vars.LFB_HF_COMMUNITY_DATASET_REPO }}" in (
        workflow
    )
    assert "HF_TOKEN:" not in workflow
    assert "secrets." not in workflow
    assert "not an official LegalForecastBench result" in workflow
