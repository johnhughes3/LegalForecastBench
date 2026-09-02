"""Accept one containerized harness-lane run from a community contributor.

A community member can run this lane on their own machine with their own
subscription, but has nowhere to put the evidence: the interesting part of a
harness-vs-API measurement is the transcript, and a transcript is too big and too
sensitive to paste into an issue.  So the contributor packages a run here, opens
a pull request carrying the package, and a maintainer-triggered workflow
validates every declared digest against the actual bytes before pushing them to
the Hugging Face dataset repository this project already hosts for community
artifacts.  Contributors never receive a credential to anything of ours.

**A package built here is not an official LegalForecastBench result** and says
so in its own record: ``official`` is ``false`` and the required
``not_official_legalforecastbench_result`` attestation is carried verbatim.

Why the redaction is light
--------------------------
:mod:`~legalforecast.multiharness.harness_lane.results_package` keeps its
archive private because a *general* run directory carries the operator's
environment.  A **containerized** row is different, and the difference was
verified against
:func:`~legalforecast.multiharness.container_harness.plan.build_harness_run_argv`:
the harness container gets exactly two bind mounts -- the task workspace and a
freshly staged 0700 HOME holding only the credential files the manifest declared
-- its environment is constructed rather than inherited, and it sits on an
internal network whose only door is the allowlist proxy.  There is no operator
home directory, no personal config, and no unrelated host data inside the
container for a transcript to leak.

So what needs scrubbing is small and specific: absolute host paths written on the
*host* side (``row-results.jsonl`` records a ``workspace``), which become
readable placeholders such as ``/[host-run-dir]/rows/row-0``; and credential
values, because the staged login is copied in and a CLI that echoes its own token
puts it in a transcript.  Everything else -- prompts, reasoning, tool calls, tool
outputs, answers -- is kept verbatim, because a transcript scrubbed into
unreadability proves nothing.  The publication guardrails are the fail-closed
backstop: anything that still reads as a secret refuses the package rather than
being quietly rewritten.

One tree is dropped rather than redacted: ``container-workspace``, which is what
this lane staged *into* the container -- projected Harvey LAB documents and the
tool-use sentinel token -- not what the harness produced.  See
:func:`_copy_redacted_tree`.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast._json_io import read_json_object
from legalforecast.multiharness.community import (
    ATTEST_NOT_OFFICIAL,
    HF_UPLOAD_PLAN_SCHEMA_VERSION,
)
from legalforecast.multiharness.harness_lane.community_upload import (
    COMMUNITY_HARNESS_ARTIFACT_MIRROR,
    MAX_ARTIFACT_BYTES,
    UPLOAD_PLAN_NAME,
    CommunityIntakeError,
    declared_artifact,
    enforce_caps,
    plan_artifacts,
)
from legalforecast.multiharness.harness_lane.results_package import (
    SUMMARY_OBJECT_NAME,
    harness_lane_public_summary,
)
from legalforecast.multiharness.harness_lane.sentinel import (
    CONTAINER_WORKSPACE_DIRECTORY,
)
from legalforecast.multiharness.local_cli_redaction import REDACTED, redact_bytes
from legalforecast.protocol.freeze import sha256_file
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)

#: Hyphenated like its sibling ``legalforecast-harness-lane-results-v1`` and for
#: the same reason: this is a lane record, not a corpus contract.
COMMUNITY_HARNESS_SUBMISSION_SCHEMA_VERSION: Final = (
    "legalforecast-community-harness-submission-v1"
)
SUBMISSION_RECORD_NAME: Final = "community-harness-submission.json"
FULL_RESULTS_DIRECTORY: Final = "full-results"
RESULT_CLASS: Final = "community_harness_lane"
NOT_OFFICIAL_NOTICE: Final = (
    "Community harness-lane submission. Contributor-run and contributor-funded. "
    "Not an official LegalForecastBench result."
)

# Host-root shapes rewritten to a placeholder that keeps the rest of the path
# readable, longest-context first so /run/user/<uid> is not clipped.  The
# lookbehind excludes word characters only, not "/": a Docker socket really is
# written "unix:///run/user/<uid>/docker.sock", and excluding "/" would leave it.
_HOST_ROOT_RULES: Final[tuple[tuple[re.Pattern[bytes], bytes], ...]] = (
    (re.compile(rb"(?<![\w])/run/user/\d+"), b"/[host-runtime]"),
    (
        re.compile(rb"(?<![\w])/var/folders/[^/\s\"']+/[^/\s\"']+"),
        b"/[host-tmp]",
    ),
    (re.compile(rb"(?<![\w])/home/[^/\s\"']+"), b"/[host-home]"),
    (re.compile(rb"(?<![\w])/Users/[^/\s\"']+"), b"/[host-home]"),
)

# Provider credential shapes.  The prefix survives so a reader can still tell
# *which* credential appeared -- the interesting fact -- without the secret
# itself.  publication_guardrails refuses whatever these miss.
_TOKEN_RULES: Final[tuple[tuple[re.Pattern[bytes], bytes], ...]] = (
    (re.compile(rb"sk-ant-[A-Za-z0-9_-]{8,}"), b"sk-ant-" + REDACTED.encode("ascii")),
    (re.compile(rb"sk-[A-Za-z0-9]{20,}"), b"sk-" + REDACTED.encode("ascii")),
    (re.compile(rb"xai-[A-Za-z0-9]{16,}"), b"xai-" + REDACTED.encode("ascii")),
    (re.compile(rb"ya29\.[A-Za-z0-9_-]{16,}"), b"ya29." + REDACTED.encode("ascii")),
    (re.compile(rb"gh[posur]_[A-Za-z0-9]{16,}"), b"gh_" + REDACTED.encode("ascii")),
    (
        re.compile(rb"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
        REDACTED.encode("ascii") + b"-jwt",
    ),
)


@dataclass(frozen=True, slots=True)
class CommunityHarnessSubmission:
    """What one packaged contributor run looks like on disk."""

    submission_dir: Path
    submission_id: str
    artifact_count: int
    total_bytes: int
    redacted_file_count: int
    excluded_workspace_file_count: int
    upload_plan_sha256: str


def redact_run_bytes(
    payload: bytes,
    *,
    host_roots: Sequence[Path] = (),
    secret_values: Sequence[str] = (),
) -> bytes:
    """Rewrite host paths and credential shapes, keeping everything else.

    Exact declared values go first, then the exact run-directory roots (the
    most specific rewrite available), then the generic host-root and
    provider-token shapes.
    """

    redacted = redact_bytes(payload, secret_values)
    for root in sorted(host_roots, key=lambda item: len(str(item)), reverse=True):
        encoded = str(root).encode("utf-8")
        if encoded and encoded != b"/":
            redacted = redacted.replace(encoded, b"/[host-run-dir]")
    for pattern, replacement in (*_HOST_ROOT_RULES, *_TOKEN_RULES):
        redacted = pattern.sub(replacement, redacted)
    return redacted


def build_community_harness_submission(
    *,
    run_dir: Path,
    output_dir: Path,
    submission_id: str,
    submitter_name: str,
    run_operator_name: str,
    adapter_author_name: str,
    submitter_github: str | None = None,
    secret_values: Sequence[str] = (),
) -> CommunityHarnessSubmission:
    """Write a reviewable, light-redacted package for one harness-lane run."""

    if not submission_id or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", submission_id):
        raise CommunityIntakeError(
            "submission_id must be 3-64 lowercase alphanumeric or hyphen characters: "
            f"{submission_id!r}"
        )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CommunityIntakeError(
            f"refusing to write into a non-empty {output_dir}; remove it and re-run"
        )
    summary = harness_lane_public_summary(run_dir)
    full_results = output_dir / FULL_RESULTS_DIRECTORY
    full_results.mkdir(parents=True, exist_ok=True)
    redacted_count, excluded_count = _copy_redacted_tree(
        run_dir,
        full_results,
        host_roots=(run_dir.resolve(),),
        secret_values=secret_values,
    )
    summary_path = output_dir / SUMMARY_OBJECT_NAME
    summary_path.write_bytes(_canonical_bytes(summary))

    artifacts = plan_artifacts(
        output_dir, exclude=(SUBMISSION_RECORD_NAME, UPLOAD_PLAN_NAME)
    )
    plan_path = output_dir / UPLOAD_PLAN_NAME
    plan_path.write_bytes(
        _canonical_bytes(
            {
                "schema_version": HF_UPLOAD_PLAN_SCHEMA_VERSION,
                "mirror_repository": COMMUNITY_HARNESS_ARTIFACT_MIRROR,
                "revision_policy": "immutable-commit",
                "artifacts": artifacts,
            }
        )
    )
    plan_sha256 = sha256_file(plan_path)
    total_bytes = sum(int(artifact["size_bytes"]) for artifact in artifacts)
    record: dict[str, Any] = {
        "schema_version": COMMUNITY_HARNESS_SUBMISSION_SCHEMA_VERSION,
        "submission_id": submission_id,
        "result_class": RESULT_CLASS,
        "official": False,
        "not_official_notice": NOT_OFFICIAL_NOTICE,
        "attestations": [ATTEST_NOT_OFFICIAL],
        "credits": _credits(
            submitter_name=submitter_name,
            submitter_github=submitter_github,
            run_operator_name=run_operator_name,
            adapter_author_name=adapter_author_name,
        ),
        "run_id": summary["run_id"],
        "harness_lane_summary_sha256": sha256_file(summary_path),
        "upload_plan_sha256": plan_sha256,
        "artifact_count": len(artifacts),
        "total_bytes": total_bytes,
        "redacted_file_count": redacted_count,
        "excluded_workspace_file_count": excluded_count,
    }
    (output_dir / SUBMISSION_RECORD_NAME).write_bytes(_canonical_bytes(record))
    enforce_publication_guardrails(
        PublicationGuardrailConfig(public_paths=(output_dir,))
    )
    return CommunityHarnessSubmission(
        submission_dir=output_dir,
        submission_id=submission_id,
        artifact_count=len(artifacts),
        total_bytes=total_bytes,
        redacted_file_count=redacted_count,
        excluded_workspace_file_count=excluded_count,
        upload_plan_sha256=plan_sha256,
    )


def validate_community_harness_submission(
    submission_dir: Path,
) -> tuple[dict[str, Any], ...]:
    """Refuse a contributor package that the workflow must not upload.

    Runs in this order, because each step is only meaningful once the previous
    one held: caps, then declared-versus-actual digests, then the secret scan
    over the bytes that would travel.
    """

    record = _read_object(submission_dir / SUBMISSION_RECORD_NAME)
    if record.get("schema_version") != COMMUNITY_HARNESS_SUBMISSION_SCHEMA_VERSION:
        raise CommunityIntakeError(
            f"{SUBMISSION_RECORD_NAME} is not a "
            f"{COMMUNITY_HARNESS_SUBMISSION_SCHEMA_VERSION} record"
        )
    if (
        record.get("official") is not False
        or record.get("result_class") != RESULT_CLASS
    ):
        raise CommunityIntakeError(
            "a community harness-lane submission must declare official=false and "
            f"result_class={RESULT_CLASS!r}"
        )
    attestations = record.get("attestations")
    if not isinstance(attestations, list) or ATTEST_NOT_OFFICIAL not in attestations:
        raise CommunityIntakeError(f"submission must attest {ATTEST_NOT_OFFICIAL!r}")

    plan_path = submission_dir / UPLOAD_PLAN_NAME
    plan_bytes = plan_path.read_bytes() if plan_path.is_file() else b""
    if not plan_bytes:
        raise CommunityIntakeError(f"submission is missing {UPLOAD_PLAN_NAME}")
    if hashlib.sha256(plan_bytes).hexdigest() != record.get("upload_plan_sha256"):
        raise CommunityIntakeError(
            f"{UPLOAD_PLAN_NAME} does not match upload_plan_sha256 in "
            f"{SUBMISSION_RECORD_NAME}"
        )
    plan = _read_object(plan_path)
    if plan.get("schema_version") != HF_UPLOAD_PLAN_SCHEMA_VERSION:
        raise CommunityIntakeError(f"{UPLOAD_PLAN_NAME} has an unexpected schema")
    if plan.get("mirror_repository") != COMMUNITY_HARNESS_ARTIFACT_MIRROR:
        raise CommunityIntakeError(
            f"{UPLOAD_PLAN_NAME} must target {COMMUNITY_HARNESS_ARTIFACT_MIRROR}"
        )
    artifacts = plan.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CommunityIntakeError(f"{UPLOAD_PLAN_NAME} declares no artifacts")
    declared = [declared_artifact(item) for item in cast(list[object], artifacts)]
    enforce_caps(declared)

    for artifact in declared:
        path = _resolve_declared_path(submission_dir, str(artifact["path"]))
        actual = path.read_bytes()
        if len(actual) != int(artifact["size_bytes"]):
            raise CommunityIntakeError(
                f"{artifact['path']} is {len(actual)} bytes; the plan declares "
                f"{artifact['size_bytes']}"
            )
        digest = f"sha256:{hashlib.sha256(actual).hexdigest()}"
        if digest != artifact["sha256"]:
            raise CommunityIntakeError(
                f"{artifact['path']} digest {digest} does not match the declared "
                f"{artifact['sha256']}"
            )
    _refuse_undeclared_bytes(submission_dir, declared)
    enforce_publication_guardrails(
        PublicationGuardrailConfig(public_paths=(submission_dir,))
    )
    return tuple(declared)


def _copy_redacted_tree(
    run_dir: Path,
    destination: Path,
    *,
    host_roots: Sequence[Path],
    secret_values: Sequence[str],
) -> tuple[int, int]:
    """Copy the run's evidence, leaving the mounted workspace behind.

    Returns ``(redacted_file_count, excluded_workspace_file_count)``.

    ``container-workspace`` is what this lane *staged into* the container, not
    what the harness produced: on a Harvey LAB row it holds the projected
    corpus documents themselves, and on every row it holds the sentinel token
    file.  Publishing the first would republish case documents through a
    community mirror, and the ``.txt`` publication guardrail refuses the second,
    so a real run could not be packaged at all.  Excluding the tree fixes both,
    and costs nothing on the LFB path: the answer travels in
    ``private-logs/release-forecast-output.json`` and the transcript in
    ``container-logs/`` and ``private-logs/``, all of which are kept.
    """

    if not run_dir.is_dir():
        raise CommunityIntakeError(f"run directory is not a directory: {run_dir}")
    redacted_files = 0
    excluded = 0
    copied = 0
    for path in sorted(run_dir.rglob("*")):
        if path.is_symlink():
            raise CommunityIntakeError(f"run directory contains a symlink: {path}")
        if not path.is_file():
            continue
        if CONTAINER_WORKSPACE_DIRECTORY in path.relative_to(run_dir).parts:
            excluded += 1
            continue
        payload = path.read_bytes()
        if len(payload) > MAX_ARTIFACT_BYTES:
            raise CommunityIntakeError(
                f"{path.relative_to(run_dir)} is {len(payload)} bytes; the community "
                f"intake cap is {MAX_ARTIFACT_BYTES}"
            )
        rewritten = redact_run_bytes(
            payload, host_roots=host_roots, secret_values=secret_values
        )
        if rewritten != payload:
            redacted_files += 1
        target = destination / path.relative_to(run_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rewritten)
        copied += 1
    if copied == 0:
        raise CommunityIntakeError(f"run directory holds no files: {run_dir}")
    return redacted_files, excluded


def _resolve_declared_path(submission_dir: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or any(
        part in {"..", ""} or part.startswith(".") for part in candidate.parts
    ):
        raise CommunityIntakeError(
            f"declared path is not a safe relative path: {relative}"
        )
    path = submission_dir / candidate
    if path.is_symlink() or not path.is_file():
        raise CommunityIntakeError(f"declared artifact is missing: {relative}")
    return path


def _refuse_undeclared_bytes(
    submission_dir: Path, declared: Sequence[Mapping[str, Any]]
) -> None:
    allowed = {str(artifact["path"]) for artifact in declared}
    allowed.update({SUBMISSION_RECORD_NAME, UPLOAD_PLAN_NAME})
    present: set[str] = set()
    for path in submission_dir.rglob("*"):
        if path.is_symlink():
            # Refused rather than skipped: the uploader follows symlinks, so a
            # link is a way to put bytes nobody hashed into the dataset.
            raise CommunityIntakeError(
                f"submission contains a symlink: "
                f"{path.relative_to(submission_dir).as_posix()}"
            )
        if path.is_file():
            present.add(path.relative_to(submission_dir).as_posix())
    undeclared = sorted(present - allowed)
    if undeclared:
        raise CommunityIntakeError(
            "the submission carries bytes the upload plan does not declare: "
            + ", ".join(undeclared)
        )


def _credits(
    *,
    submitter_name: str,
    submitter_github: str | None,
    run_operator_name: str,
    adapter_author_name: str,
) -> dict[str, Any]:
    for label, value in (
        ("submitter_name", submitter_name),
        ("run_operator_name", run_operator_name),
        ("adapter_author_name", adapter_author_name),
    ):
        if not value.strip():
            raise CommunityIntakeError(f"{label} must not be empty")
    submitter: dict[str, Any] = {"name": submitter_name}
    if submitter_github:
        submitter["github"] = submitter_github
    return {
        "submitter": submitter,
        "run_operator": {"name": run_operator_name},
        "adapter_author": {"name": adapter_author_name},
        "benchmark_infrastructure": {"name": "LegalForecastBench"},
    }


def _canonical_bytes(record: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(dict(record), indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


def _read_object(path: Path) -> dict[str, Any]:
    return read_json_object(
        path,
        error_factory=CommunityIntakeError,
        missing_message=lambda item: f"submission is missing {item.name}",
        non_object_message=lambda item: f"{item.name} is not a JSON object",
    )
