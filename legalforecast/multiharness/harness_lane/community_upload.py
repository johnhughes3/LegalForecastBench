"""Where a community harness-lane submission goes, and what may travel there.

Three callers have to agree on this, or a contributor learns about a problem
from a failed workflow run instead of from their own machine: the packager that
writes ``hf-upload-plan.json``, the local check a contributor runs before
opening a pull request, and the Actions job that publishes.  The caps, the
artifact-plan shape, and the destination therefore live here once, and all
three read the same numbers.

WHERE IT GOES, AND WHY NOT THERE
--------------------------------
A community submission is contributor-run and contributor-funded, it never
enters the official aggregate, and it is not comparable to an official row.  So
it is published to its own Hugging Face dataset repository and never to the
official one: a reader who finds one of these files can tell from the
repository alone that it is not an official LegalForecastBench result, without
having to open the record and read ``official: false``.

:func:`resolve_community_dataset_repo` is that binding, and it is fail-closed
in three directions -- an unset variable, a variable naming some other
repository, and a variable that has been pointed at the official dataset.  The
equality check is the weaker of the two on purpose and the comment on it says
why; the check against the expected repository is the one that actually holds.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from legalforecast._json_io import read_json_object

#: The dataset repository this lane publishes to, decided by the owner.  Kept
#: in code so the error a contributor or a workflow sees can name the exact
#: value the variable should hold rather than only the variable.
COMMUNITY_HARNESS_DATASET_REPO: Final = "johnhughes3/legal-quants-community-submissions"
COMMUNITY_HARNESS_ARTIFACT_MIRROR: Final = (
    f"https://huggingface.co/datasets/{COMMUNITY_HARNESS_DATASET_REPO}"
)
#: Set on the ``legalforecastbench-community-artifacts`` GitHub environment.
COMMUNITY_DATASET_REPO_VARIABLE: Final = "LFB_HF_COMMUNITY_DATASET_REPO"
#: The official lane's variable, read here only to refuse a collision.
OFFICIAL_DATASET_REPO_VARIABLE: Final = "LFB_HF_OFFICIAL_DATASET_REPO"

UPLOAD_PLAN_NAME: Final = "hf-upload-plan.json"

# These bytes ride inside a pull request so CI can scan the actual files rather
# than a description of them, which is what makes the digest check and the
# secret scan mean anything.  The caps are therefore review-sized, not
# bucket-sized.
MAX_ARTIFACT_BYTES: Final = 8 * 1024 * 1024
MAX_TOTAL_BYTES: Final = 64 * 1024 * 1024
MAX_ARTIFACT_COUNT: Final = 2_000

_SHA256: Final = re.compile(r"[0-9a-f]{64}")

_MEDIA_TYPES: Final[Mapping[str, str]] = {
    ".json": "application/json",
    ".jsonl": "application/jsonl",
    ".log": "text/plain",
    ".md": "text/markdown",
    ".txt": "text/plain",
}


class CommunityIntakeError(ValueError):
    """Raised when a community harness-lane package cannot be built or trusted.

    One error type for the whole intake path, so a contributor sees the same
    class of refusal locally that the workflow would raise server-side.
    """


def resolve_community_dataset_repo(env: Mapping[str, str]) -> str:
    """Return the community dataset repository, or refuse the configuration.

    Called from the publishing workflow before anything is uploaded.  It never
    falls back to a default: an unconfigured environment must stop the job, not
    quietly publish somewhere.
    """

    configured = env.get(COMMUNITY_DATASET_REPO_VARIABLE, "").strip()
    if not configured:
        raise CommunityIntakeError(
            f"{COMMUNITY_DATASET_REPO_VARIABLE} is not set on this environment. "
            f"Set it to {COMMUNITY_HARNESS_DATASET_REPO!r} -- namespace/repository, "
            "with no URL and no 'datasets/' prefix."
        )
    # Environment-scoped elsewhere: the official variable lives on the official
    # fan-in environment, so it is usually absent in this job and this check
    # only catches a repository-scoped collision.  It is cheap, and the failure
    # it guards against -- a community package landing in the official dataset
    # -- is one that cannot be undone by editing a variable afterwards.
    official = env.get(OFFICIAL_DATASET_REPO_VARIABLE, "").strip()
    if official and official == configured:
        raise CommunityIntakeError(
            f"{COMMUNITY_DATASET_REPO_VARIABLE} and {OFFICIAL_DATASET_REPO_VARIABLE} "
            f"both name {configured!r}. A community submission must never be "
            "published where official benchmark results live."
        )
    if configured != COMMUNITY_HARNESS_DATASET_REPO:
        raise CommunityIntakeError(
            f"{COMMUNITY_DATASET_REPO_VARIABLE} names {configured!r}, but this lane "
            f"publishes only to {COMMUNITY_HARNESS_DATASET_REPO!r}."
        )
    return configured


def assert_upload_plan_targets(mirror: str, repository: str) -> None:
    """Refuse an upload plan whose declared mirror is not the destination.

    The reviewed bytes name where they expect to go; the dispatch names where
    they are being sent.  This is where those two have to agree, and it is run
    both locally and in the publishing job.
    """

    expected = f"https://huggingface.co/datasets/{repository}"
    if mirror.rstrip("/") != expected:
        raise CommunityIntakeError(
            f"{UPLOAD_PLAN_NAME} names the mirror {mirror!r}, but the destination "
            f"is {repository!r} ({expected})."
        )


def plan_artifacts(
    submission_dir: Path, *, exclude: Sequence[str]
) -> list[dict[str, Any]]:
    """Return the per-file upload plan: relative path, sha256, size, media type."""

    excluded = set(exclude)
    artifacts: list[dict[str, Any]] = []
    for path in sorted(submission_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(submission_dir).as_posix()
        if relative in excluded:
            continue
        payload = path.read_bytes()
        artifacts.append(
            {
                "artifact_id": relative,
                "path": relative,
                "sha256": f"sha256:{hashlib.sha256(payload).hexdigest()}",
                "media_type": _MEDIA_TYPES.get(
                    path.suffix.lower(), "application/octet-stream"
                ),
                "size_bytes": len(payload),
            }
        )
    return artifacts


def declared_artifact(item: object) -> dict[str, Any]:
    """Return one plan entry, refusing anything a digest check could not use."""

    if not isinstance(item, Mapping):
        raise CommunityIntakeError(f"{UPLOAD_PLAN_NAME} holds a non-object artifact")
    record = cast(Mapping[str, Any], item)
    path = record.get("path")
    digest = record.get("sha256")
    size = record.get("size_bytes")
    if not isinstance(path, str) or not path:
        raise CommunityIntakeError("declared artifact has no path")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise CommunityIntakeError(f"{path} has no sha256: digest")
    if _SHA256.fullmatch(digest.removeprefix("sha256:")) is None:
        raise CommunityIntakeError(f"{path} digest is not a lowercase SHA-256")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise CommunityIntakeError(f"{path} has no size_bytes")
    return {"path": path, "sha256": digest, "size_bytes": size}


def enforce_caps(artifacts: Sequence[Mapping[str, Any]]) -> None:
    """Refuse a submission too large or too numerous to review inside a PR."""

    if len(artifacts) > MAX_ARTIFACT_COUNT:
        raise CommunityIntakeError(
            f"{len(artifacts)} artifacts exceeds the intake cap of {MAX_ARTIFACT_COUNT}"
        )
    total = 0
    for artifact in artifacts:
        size = int(artifact["size_bytes"])
        if size > MAX_ARTIFACT_BYTES:
            raise CommunityIntakeError(
                f"{artifact['path']} declares {size} bytes; the intake cap is "
                f"{MAX_ARTIFACT_BYTES}"
            )
        total += size
    if total > MAX_TOTAL_BYTES:
        raise CommunityIntakeError(
            f"the submission declares {total} bytes; the intake cap is "
            f"{MAX_TOTAL_BYTES}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve and print the community dataset repository for a publish job."""

    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.multiharness.harness_lane.community_upload",
        description=(
            "Resolve the community harness-lane dataset repository from the "
            "environment and refuse a submission that names a different mirror. "
            "Community submissions are not official LegalForecastBench results."
        ),
    )
    parser.add_argument(
        "--submission-dir",
        type=Path,
        help="Submission package whose upload plan must name the destination.",
    )
    args = parser.parse_args(argv)
    # A stack trace in a workflow log buries the one sentence that says how to
    # fix the configuration, so the refusal is printed rather than raised.
    try:
        repository = resolve_community_dataset_repo(os.environ)
        submission_dir = cast(Path | None, args.submission_dir)
        if submission_dir is not None:
            plan = read_json_object(
                submission_dir / UPLOAD_PLAN_NAME,
                error_factory=CommunityIntakeError,
                missing_message=lambda item: f"submission is missing {item.name}",
                non_object_message=lambda item: f"{item.name} is not a JSON object",
            )
            assert_upload_plan_targets(
                str(plan.get("mirror_repository", "")), repository
            )
    except CommunityIntakeError as exc:
        print(f"refusing publication: {exc}", file=sys.stderr)
        return 1
    print(repository)
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
