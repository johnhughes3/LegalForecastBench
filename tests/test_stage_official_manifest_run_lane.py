"""The official first-stage lane: its workflow shape and its executable fence.

Manifest-run objects are created once and no role holds a delete grant, so an
object written under the wrong prefix is unrecoverable and a lane confusion is
not a bug you fix later. The fence that prevents one is a shell script shared by
both lanes, so it is exercised here as bytes actually run through bash rather
than as a transcription of what it is believed to do.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from official_infra_trust_helpers import (
    job_environment,
    job_grants_id_token_write,
    workflow_jobs,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "stage-official-manifest-run.yaml"
SUPPLEMENTARY_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "stage-manifest-run.yaml"
FENCE_SCRIPT = ROOT / ".github" / "scripts" / "assert-manifest-run-lane.sh"
STAGING_ENVIRONMENT = "legalforecastbench-official-eval-manifest-staging"
STAGING_ROLE_VARIABLE = "LFB_GITHUB_MANIFEST_STAGING_ROLE_ARN"
# A synthetic 64-hex corpus digest. Deliberately not a real manifest digest:
# the shape is what the fence asserts, and a live digest in a public test
# would publish a private-tree identifier for no test value.
DIGEST = "0123456789abcdef" * 4
OFFICIAL_PREFIX = f"cycle-1/manifest-runs/{DIGEST}"
RESULTS_BUCKET = "results-bucket"
PACKET_BUCKET = "packet-bucket"


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _record(*keys: tuple[str, str], prefix: str = OFFICIAL_PREFIX) -> dict[str, object]:
    return {
        "prefix": prefix,
        "objects": [{"bucket": bucket, "key": key} for bucket, key in keys],
    }


def _official_record(prefix: str = OFFICIAL_PREFIX) -> dict[str, object]:
    return _record(
        (RESULTS_BUCKET, f"{prefix}/freeze.json"),
        (RESULTS_BUCKET, f"{prefix}/artifacts/manifest.json"),
        (RESULTS_BUCKET, f"{prefix}/run-inputs.json"),
        (RESULTS_BUCKET, f"{prefix}/model-packets/cycle-1/case-1/full_packet.json"),
        (PACKET_BUCKET, "model-packets/cycle-1/case-1/full_packet.json"),
        prefix=prefix,
    )


def _run_fence(
    tmp_path: Path, record: dict[str, object], *, prefix: str, lane: str | None
) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    args = [
        "bash",
        str(FENCE_SCRIPT),
        str(path),
        prefix,
        RESULTS_BUCKET,
        PACKET_BUCKET,
    ]
    if lane is not None:
        args.append(lane)
    return subprocess.run(args, capture_output=True, text=True, check=False)


# --- the fence, run as bytes ------------------------------------------------


def test_official_lane_accepts_the_official_first_stage_plan(tmp_path: Path) -> None:
    result = _run_fence(
        tmp_path, _official_record(), prefix=OFFICIAL_PREFIX, lane="official"
    )
    assert result.returncode == 0, result.stderr


def test_official_lane_refuses_a_supplementary_key(tmp_path: Path) -> None:
    """The refusal that keeps a sibling freeze out of the shared official prefix.

    Official shards have already been dispatched against the bare manifest-digest
    prefix, so a supplementary object landing inside it would be indistinguishable
    from official corpus bytes and could never be removed.
    """

    record = _official_record()
    objects = record["objects"]
    assert isinstance(objects, list)
    objects.append(
        {
            "bucket": RESULTS_BUCKET,
            "key": f"cycle-1/manifest-runs/supplementary/{DIGEST}/{DIGEST}/freeze.json",
        }
    )

    result = _run_fence(tmp_path, record, prefix=OFFICIAL_PREFIX, lane="official")

    assert result.returncode != 0
    assert "refusing" in result.stderr


def test_official_lane_refuses_a_doubled_artifacts_segment(tmp_path: Path) -> None:
    """The legalforecastbench-bh6j signature, refused at the fence too.

    The first-stage precondition already refuses the restage that produces these
    keys. This is the cheap second look, and it is worth having because the
    objects it would let through are undeletable.
    """

    record = _official_record()
    objects = record["objects"]
    assert isinstance(objects, list)
    objects.append(
        {
            "bucket": RESULTS_BUCKET,
            "key": f"{OFFICIAL_PREFIX}/artifacts/artifacts/manifest.json",
        }
    )

    result = _run_fence(tmp_path, record, prefix=OFFICIAL_PREFIX, lane="official")

    assert result.returncode != 0
    assert "doubles the artifacts/ segment" in result.stderr


def test_official_lane_refuses_a_prefix_that_is_not_a_corpus_digest(
    tmp_path: Path,
) -> None:
    prefix = "cycle-1/manifest-runs/not-a-digest"
    result = _run_fence(
        tmp_path, _official_record(prefix), prefix=prefix, lane="official"
    )

    assert result.returncode != 0
    assert "refusing" in result.stderr


def test_official_lane_refuses_an_object_outside_its_own_prefix(
    tmp_path: Path,
) -> None:
    record = _official_record()
    objects = record["objects"]
    assert isinstance(objects, list)
    objects.append(
        {
            "bucket": RESULTS_BUCKET,
            "key": f"cycle-1/manifest-runs/{'b' * 64}/freeze.json",
        }
    )

    result = _run_fence(tmp_path, record, prefix=OFFICIAL_PREFIX, lane="official")

    assert result.returncode != 0
    assert "outside" in result.stderr


def test_supplementary_lane_still_refuses_an_official_record(tmp_path: Path) -> None:
    """The separation is symmetric, and the supplementary lane is unchanged.

    Adding an official mode must not make the supplementary fence accept official
    keys: the two lanes stay mutually exclusive, which is the whole point of the
    literal ``supplementary`` segment that no digest can equal.
    """

    result = _run_fence(
        tmp_path, _official_record(), prefix=OFFICIAL_PREFIX, lane="supplementary"
    )

    assert result.returncode != 0
    assert "supplementary segment" in result.stderr


def test_supplementary_lane_accepts_a_supplementary_record(tmp_path: Path) -> None:
    prefix = f"cycle-1/manifest-runs/supplementary/{DIGEST}/{DIGEST}"
    result = _run_fence(
        tmp_path,
        _record(
            (RESULTS_BUCKET, f"{prefix}/freeze.json"),
            (PACKET_BUCKET, "model-packets/cycle-1/case-1/full_packet.json"),
            prefix=prefix,
        ),
        prefix=prefix,
        lane="supplementary",
    )
    assert result.returncode == 0, result.stderr


def test_fence_refuses_a_missing_or_unknown_lane(tmp_path: Path) -> None:
    """Required, never defaulted.

    A caller that forgets which lane it is in must fail rather than quietly
    inherit the other lane's fence, because the two lanes share a bucket and the
    wrong answer is unrecoverable.
    """

    missing = _run_fence(
        tmp_path, _official_record(), prefix=OFFICIAL_PREFIX, lane=None
    )
    assert missing.returncode != 0
    assert "lane is required" in missing.stderr

    unknown = _run_fence(
        tmp_path, _official_record(), prefix=OFFICIAL_PREFIX, lane="whatever"
    )
    assert unknown.returncode != 0
    assert "must be supplementary or official" in unknown.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck absent")
def test_fence_script_passes_shellcheck() -> None:
    result = subprocess.run(
        ["shellcheck", str(FENCE_SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout


# --- the workflow -----------------------------------------------------------


def test_only_the_staging_job_gets_an_oidc_token_and_it_binds_its_environment() -> None:
    jobs = workflow_jobs(_workflow_text())

    assert set(jobs) == {"validate-request", "stage"}
    validate = jobs["validate-request"]
    assert "id-token" not in validate
    assert "environment:" not in validate
    stage = jobs["stage"]
    assert job_environment(stage) == STAGING_ENVIRONMENT
    assert job_grants_id_token_write(stage)
    assert f"role-to-assume: ${{{{ env.{STAGING_ROLE_VARIABLE} }}}}" in stage


def test_workflow_pins_every_action_to_a_commit_sha() -> None:
    versions = re.findall(r"uses: [^@\s]+@([^\s]+)", _workflow_text())
    assert versions
    for version in versions:
        assert re.fullmatch(r"[0-9a-f]{40}", version), version


def test_workflow_never_runs_with_local_or_long_lived_credentials() -> None:
    text = _workflow_text()
    for forbidden in (
        "aws configure",
        "AWS_ACCESS_KEY_ID: ${{ secrets",
        "AWS_SECRET_ACCESS_KEY: ${{ secrets",
        "--profile",
        "aws_access_key_id",
        "pull_request",
        "schedule:",
    ):
        assert forbidden not in text, forbidden
    assert "unset-current-credentials: true" in text
    assert text.count("persist-credentials: false") == text.count(
        "uses: actions/checkout@"
    )


def test_concurrency_never_cancels_a_run_that_may_have_written() -> None:
    """Keyed on the corpus digest alone, because that alone keys the prefix.

    Two concurrent first stagings of different bundles over one corpus would both
    pass the precondition and then interleave create-once puts into a prefix
    nothing can clean up.
    """

    text = _workflow_text()
    assert "group: stage-official-manifest-run-${{ inputs.manifest_digest }}\n" in text
    assert "cancel-in-progress: false" in text
    assert "cancel-in-progress: true" not in text


def test_dispatch_surface_is_the_reviewed_input_set() -> None:
    text = _workflow_text()
    block = text.split("  workflow_dispatch:\n    inputs:\n", 1)[1].split(
        "\npermissions:", 1
    )[0]
    names = re.findall(r"(?m)^      ([A-Za-z_][A-Za-z0-9_-]*):\s*$", block)

    assert names == [
        "release_sha",
        "manifest_digest",
        "source_descriptor_json",
        "freeze_bundle_sha256",
        "run_inputs_sha256",
        "run_record_sha256",
        "dry_run",
    ]


def test_the_expected_prefix_is_the_bare_official_manifest_digest() -> None:
    """No supplementary segment and no freeze component.

    The official prefix is the corpus manifest digest alone, unchanged, because
    official shards have already been dispatched against it.
    """

    text = _workflow_text()
    assert 'expected_prefix="cycle-1/manifest-runs/${MANIFEST_DIGEST}"' in text
    # The literal segment that keys the other lane appears nowhere in a key, a
    # prefix, or a command; the header comment naming the sibling workflow is
    # not part of any path this workflow builds.
    assert "manifest-runs/supplementary" not in text
    assert "--supplementary" not in text


def test_both_staging_invocations_carry_the_first_stage_precondition() -> None:
    """The plan and the write are separate invocations of the same command.

    Only the second describes real writes, so the flag has to be on both: on the
    plan so a doomed request is refused while refusal is still free, and on the
    write because that is the invocation the precondition actually gates.
    """

    text = _workflow_text()
    invocation = "uv run legalforecast acquisition stage-manifest-forecast"
    blocks = text.split(invocation)
    assert len(blocks) == 3, "expected exactly the plan and the write invocations"
    for block in blocks[1:]:
        command = block.split("\n\n", 1)[0]
        assert "--first-stage-only" in command
        assert "--supplementary" not in command
    assert "--supplementary" not in text


def test_lane_fence_runs_before_any_write_and_again_on_what_was_written() -> None:
    stage = workflow_jobs(_workflow_text())["stage"]

    assert stage.count(FENCE_SCRIPT.name) == 2
    assert stage.count('"${LFB_PACKET_BUCKET}" official') == 2
    plan_index = stage.index("Prove the upload plan stays inside its own prefix")
    write_index = stage.index("- name: Stage the official manifest run")
    assert plan_index < write_index
    assert plan_index < stage.index("--dry-run") < write_index


def test_the_corpus_arrives_as_a_pinned_never_published_draft_asset() -> None:
    """Every hop of the transport is pinned, and none of it is trusted.

    A published release would put the ciphertext of the un-run corpus on a public
    download URL permanently, so ``draft == true`` is a precondition rather than a
    convention; the asset's id, name, size, and digest pin which bytes arrive; and
    the packaged freeze bundle and run-inputs digests are what make those bytes
    self-authenticating once they do.
    """

    text = _workflow_text()
    assert ".draft == true and .target_commitish == $release_sha" in text
    assert "--first-stage-only" in text
    assert "sha256sum --check --strict" in text
    assert "open-manifest-run-source-package" in text
    for pinned in (
        '--freeze-bundle-sha256 "${FREEZE_BUNDLE_SHA256}"',
        '--run-inputs-sha256 "${RUN_INPUTS_SHA256}"',
        '--run-record-sha256 "${RUN_RECORD_SHA256}"',
    ):
        assert pinned in text, pinned


def test_decrypted_corpus_and_identity_never_reach_a_public_artifact() -> None:
    """Run artifacts on a public repository are publicly downloadable.

    The decrypted archive, the rebuilt corpus tree, and the age identity all live
    under WORK_ROOT, and the upload is gated on the step that destroys it having
    succeeded.
    """

    text = _workflow_text()
    stage = workflow_jobs(text)["stage"]
    assert 'find "${WORK_ROOT}" -type f -exec shred' in stage
    assert 'test ! -e "${WORK_ROOT}"' in stage
    assert "steps.clear_sensitive.outcome == 'success'" in stage
    upload = stage.split("- name: Upload stage record", 1)[1]
    assert "${{ env.WORK_ROOT }}" not in upload
    assert "include-hidden-files: false" in upload
    assert "if-no-files-found: error" in upload


def test_the_supplementary_lane_keeps_its_own_fence_argument() -> None:
    """Byte-compatible for supplementary: same prefix, same checks, same record.

    The only change to the existing lane is that it now names itself when it
    calls the shared fence.
    """

    text = SUPPLEMENTARY_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert text.count('"${LFB_PACKET_BUCKET}" supplementary') == 2
    assert '"${LFB_PACKET_BUCKET}" official' not in text
    assert "--supplementary" in text
    assert "--first-stage-only" not in text
