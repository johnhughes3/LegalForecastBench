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
from legalforecast.multiharness.harness_lane.community_submit import (
    check_community_harness_submission,
    submit_community_harness_run,
)
from legalforecast.multiharness.harness_lane.community_upload import (
    COMMUNITY_HARNESS_DATASET_REPO,
    assert_upload_plan_targets,
    resolve_community_dataset_repo,
)
from legalforecast.multiharness.harness_lane.sentinel import (
    CONTAINER_WORKSPACE_DIRECTORY,
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


def test_a_work_tree_host_path_is_redacted_the_way_home_already_was(
    tmp_path: Path,
) -> None:
    """The Linux builders live under /work/, not /home/.

    A file containing this repo's real path used to package as
    ``0 file(s) redacted`` because ``_HOST_ROOT_RULES`` only knew /home and
    /Users.  Do not replace this with a tree-wide absolute-path refusal: that
    would also refuse ``/workspace/foo``.
    """

    run_dir = _community_run_directory(tmp_path)
    host_path = "/work/Development/legal/LegalForecastBench"
    log = run_dir / "rows" / "row-0" / "container-logs" / "harness.log"
    log.write_bytes(log.read_bytes() + f"cwd={host_path}\n".encode())

    submission = build_community_harness_submission(
        run_dir=run_dir,
        output_dir=tmp_path / "work-submission",
        submission_id="community-harness-worktree",
        submitter_name="Example Contributor",
        submitter_github="example-contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        secret_values=(_HOST_SESSION,),
    )

    packaged = (
        submission.submission_dir
        / "full-results"
        / "rows"
        / "row-0"
        / "container-logs"
        / "harness.log"
    ).read_text(encoding="utf-8")
    assert host_path not in packaged
    assert "cwd=/[host-work]" in packaged
    assert submission.redacted_file_count >= 1
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
    # and a backstop that quietly rewrote this would be worse than one that
    # stops.  It shares its line with a value the scrubber *did* rewrite,
    # because the scan drops only the redacted span -- never the rest of a line.
    (run_dir / "rows" / "row-0" / "container-logs" / "leak.stdout").write_text(
        f"session={_HOST_SESSION} AWS_ACCESS_KEY_ID=AKIAEXAMPLEEXAMPLE12\n",
        encoding="utf-8",
    )

    with pytest.raises(PublicationGuardrailError):
        build_community_harness_submission(
            run_dir=run_dir,
            output_dir=tmp_path / "submission",
            submission_id="community-harness-fixture",
            submitter_name="Example Contributor",
            run_operator_name="Example Contributor",
            adapter_author_name="Example Contributor",
            secret_values=(_HOST_SESSION,),
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


def _run_directory_with_a_staged_workspace(root: Path) -> Path:
    """A run directory shaped the way a real containerized run leaves one.

    ``container-workspace`` is what the lane staged *into* the container: the
    sentinel token every row writes, and on a Harvey LAB row the projected
    corpus documents.  Both were guaranteed to be there and neither had a path
    out -- ``workspace-token.txt`` alone refuses the package, because the
    publication guardrails refuse a ``.txt`` in a public artifact.
    """

    run_dir = _community_run_directory(root)
    workspace = run_dir / "rows" / "row-0" / CONTAINER_WORKSPACE_DIRECTORY
    (workspace / "harness-sentinel").mkdir(parents=True)
    (workspace / "harness-sentinel" / "workspace-token.txt").write_text(
        "0123456789abcdef0123456789abcdef\n", encoding="utf-8"
    )
    (workspace / "complaint.md").write_text(
        "Projected LAB document text that must not be republished.\n",
        encoding="utf-8",
    )
    return run_dir


def test_the_staged_container_workspace_never_reaches_the_package(
    tmp_path: Path,
) -> None:
    result = submit_community_harness_run(
        run_dir=_run_directory_with_a_staged_workspace(tmp_path),
        output_dir=tmp_path / "submission",
        submission_id="community-harness-fixture",
        submitter_name="Example Contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        secret_values=(_HOST_SESSION,),
    )

    # Two staged files left behind, counted rather than silently dropped.
    assert result.excluded_workspace_file_count == 2
    packaged = {
        path.relative_to(result.submission_dir).as_posix()
        for path in result.submission_dir.rglob("*")
        if path.is_file()
    }
    assert not [name for name in packaged if CONTAINER_WORKSPACE_DIRECTORY in name]
    assert not [name for name in packaged if name.endswith(".txt")]
    # The evidence the lane exists to publish is still all there.
    assert "full-results/rows/row-0/container-logs/harness.log" in packaged
    assert "full-results/rows/row-0/private-logs/harness-lane-transcript.json" in (
        packaged
    )
    plan = json.loads(
        (result.submission_dir / "hf-upload-plan.json").read_text(encoding="utf-8")
    )
    declared = {str(item["path"]) for item in plan["artifacts"]}
    assert not [name for name in declared if CONTAINER_WORKSPACE_DIRECTORY in name]


def test_submit_prints_the_exact_dispatch_inputs_from_the_registry_layout(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "community" / "submissions" / "2026" / "harness-abc"
    result = submit_community_harness_run(
        run_dir=_community_run_directory(tmp_path),
        output_dir=output_dir,
        submission_id="harness-abc",
        submitter_name="Example Contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        secret_values=(_HOST_SESSION,),
    )

    assert result.tracked_submission_dir == "community/submissions/2026/harness-abc"
    assert result.release_path == "harness-lane/2026/harness-abc"
    steps = "\n".join(result.next_steps())
    assert "community/submissions/2026/harness-abc" in steps
    assert "harness-lane/2026/harness-abc" in steps
    assert ".github/workflows/community-harness-intake.yaml" in steps
    assert "not an official LegalForecastBench result" in steps


def test_a_package_outside_the_registry_is_told_where_it_has_to_go(
    tmp_path: Path,
) -> None:
    result = submit_community_harness_run(
        run_dir=_community_run_directory(tmp_path),
        output_dir=tmp_path / "scratch",
        submission_id="harness-abc",
        submitter_name="Example Contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        secret_values=(_HOST_SESSION,),
    )

    assert result.tracked_submission_dir is None
    assert "community/submissions/<year>/harness-abc" in "\n".join(result.next_steps())


def test_the_local_check_refuses_a_tampered_digest_and_accepts_a_clean_package(
    tmp_path: Path,
) -> None:
    result = submit_community_harness_run(
        run_dir=_community_run_directory(tmp_path),
        output_dir=tmp_path / "submission",
        submission_id="community-harness-fixture",
        submitter_name="Example Contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        secret_values=(_HOST_SESSION,),
    )
    # submit_community_harness_run already ran it once; a clean package passes.
    assert check_community_harness_submission(result.submission_dir)

    transcript = (
        result.submission_dir
        / "full-results"
        / "rows"
        / "row-0"
        / "container-logs"
        / "harness.log"
    )
    transcript.write_bytes(transcript.read_bytes().replace(b"0.35", b"0.95"))

    with pytest.raises(CommunityIntakeError, match="does not match the declared"):
        check_community_harness_submission(result.submission_dir)


def test_the_upload_plan_names_the_community_dataset_and_not_the_official_one(
    tmp_path: Path,
) -> None:
    result = submit_community_harness_run(
        run_dir=_community_run_directory(tmp_path),
        output_dir=tmp_path / "submission",
        submission_id="community-harness-fixture",
        submitter_name="Example Contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        secret_values=(_HOST_SESSION,),
    )

    plan = json.loads(
        (result.submission_dir / "hf-upload-plan.json").read_text(encoding="utf-8")
    )
    assert plan["mirror_repository"] == (
        "https://huggingface.co/datasets/johnhughes3/legal-quants-community-submissions"
    )
    assert COMMUNITY_HARNESS_DATASET_REPO == (
        "johnhughes3/legal-quants-community-submissions"
    )
    # A plan naming somewhere else is refused before anything is uploaded.
    with pytest.raises(CommunityIntakeError, match="names the mirror"):
        assert_upload_plan_targets(
            "https://huggingface.co/datasets/johnhughes3/legalforecastbench",
            COMMUNITY_HARNESS_DATASET_REPO,
        )


def test_the_destination_variable_fails_closed_in_every_direction() -> None:
    assert (
        resolve_community_dataset_repo(
            {"LFB_HF_COMMUNITY_DATASET_REPO": COMMUNITY_HARNESS_DATASET_REPO}
        )
        == COMMUNITY_HARNESS_DATASET_REPO
    )

    with pytest.raises(CommunityIntakeError) as unset:
        resolve_community_dataset_repo({})
    # The message has to carry both the variable and the value it should hold:
    # whoever reads it is configuring an environment, not reading this module.
    assert "LFB_HF_COMMUNITY_DATASET_REPO" in str(unset.value)
    assert COMMUNITY_HARNESS_DATASET_REPO in str(unset.value)

    with pytest.raises(CommunityIntakeError, match="publishes only to"):
        resolve_community_dataset_repo(
            {"LFB_HF_COMMUNITY_DATASET_REPO": "johnhughes3/some-other-dataset"}
        )

    with pytest.raises(CommunityIntakeError, match="official benchmark results"):
        resolve_community_dataset_repo(
            {
                "LFB_HF_COMMUNITY_DATASET_REPO": "johnhughes3/legalforecastbench",
                "LFB_HF_OFFICIAL_DATASET_REPO": "johnhughes3/legalforecastbench",
            }
        )


def test_the_intake_workflow_binds_the_destination_before_it_uploads() -> None:
    workflow = Path(".github/workflows/community-harness-intake.yaml").read_text(
        encoding="utf-8"
    )

    bind_at = workflow.index("community_upload \\")
    upload_at = workflow.index("api.upload_folder(")
    assert bind_at < upload_at
    # Both variables reach the step, because refusing a collision needs both.
    assert (
        "LFB_HF_COMMUNITY_DATASET_REPO: ${{ vars.LFB_HF_COMMUNITY_DATASET_REPO }}"
    ) in workflow
    assert (
        "LFB_HF_OFFICIAL_DATASET_REPO: ${{ vars.LFB_HF_OFFICIAL_DATASET_REPO }}"
    ) in workflow
    assert "johnhughes3/legal-quants-community-submissions" in workflow


_PLAIN_TEXT_ANSWER = "Motion likely granted: the complaint pleads no scienter.\n"


def test_plain_text_and_an_already_scrubbed_credential_no_longer_block_a_run(
    tmp_path: Path,
) -> None:
    """The two shapes a legitimate run produced that nothing could package.

    A ``.txt`` outside ``container-workspace`` -- codex-cli writes one, a failed
    row writes one -- and a transcript the scrubber had already rewritten, which
    the scan then refused for the rewrite it had just made.
    """

    run_dir = _community_run_directory(tmp_path)
    logs = run_dir / "rows" / "row-0" / "container-logs"
    (logs / "answer.txt").write_text(_PLAIN_TEXT_ANSWER, encoding="utf-8")
    (logs / "env.log").write_text(
        "ANTHROPIC_API_KEY=sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFF\n", encoding="utf-8"
    )

    result = submit_community_harness_run(
        run_dir=run_dir,
        output_dir=tmp_path / "submission",
        submission_id="community-harness-fixture",
        submitter_name="Example Contributor",
        run_operator_name="Example Contributor",
        adapter_author_name="Example Contributor",
        secret_values=(_HOST_SESSION,),
    )
    full = result.submission_dir / "full-results" / "rows" / "row-0" / "container-logs"

    # The text is kept and told where it came from; only the suffix changed, so
    # the rule that stops case text being republished is untouched.
    assert result.normalized_text_file_count == 1
    carried = json.loads((full / "answer.txt.json").read_text(encoding="utf-8"))
    assert carried["source_path"] == "rows/row-0/container-logs/answer.txt"
    assert carried["text"] == _PLAIN_TEXT_ANSWER
    assert not [path for path in result.submission_dir.rglob("*.txt") if path.is_file()]
    # End to end, this is the placeholder pin: the exact bytes the scrubber
    # writes are the exact bytes the scan now lets through.
    assert (full / "env.log").read_text(encoding="utf-8") == (
        "ANTHROPIC_API_KEY=sk-ant-[redacted]\n"
    )


def test_a_plain_text_run_file_that_is_not_utf8_is_refused_by_name(
    tmp_path: Path,
) -> None:
    run_dir = _community_run_directory(tmp_path)
    (run_dir / "rows" / "row-0" / "container-logs" / "blob.txt").write_bytes(
        b"\xff\xfe"
    )

    with pytest.raises(CommunityIntakeError, match="is not UTF-8 text"):
        build_community_harness_submission(
            run_dir=run_dir,
            output_dir=tmp_path / "submission",
            submission_id="community-harness-fixture",
            submitter_name="Example Contributor",
            run_operator_name="Example Contributor",
            adapter_author_name="Example Contributor",
        )
