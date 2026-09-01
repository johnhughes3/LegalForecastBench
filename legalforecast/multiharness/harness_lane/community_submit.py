"""One command that turns a finished harness-lane run into a submittable package.

Before this, a contributor could package a run and could validate a package,
but had to know two module entry points, the registry layout, the caps, and
which workflow a maintainer dispatches -- and would discover a mistake in any
of them from a red workflow run days later.  ``multiharness harness submit``
does the whole thing on the contributor's machine: package with the light-touch
redaction, write the upload plan, and then run the *same* validation the
publishing job runs before it uploads anything.

THE LOCAL CHECK DOES NOT REPLACE THE SERVER-SIDE ONE.  It is deliberately the
same code, called earlier, so that a contributor learns about a digest mismatch
or a residual secret from their own terminal.  ``community-harness-intake.yaml``
still re-validates from scratch at the dispatched commit, because bytes that
travelled through a pull request are not the bytes that were checked, and
because a contributor's local run is not evidence about a stranger's package.

**Nothing built here is an official LegalForecastBench result.**  The package
says so in its own record, the workflow refuses one that does not, and the
destination is a different Hugging Face repository from the official dataset.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast._json_io import read_json_object
from legalforecast.multiharness.harness_lane.community_intake import (
    SUBMISSION_RECORD_NAME,
    build_community_harness_submission,
    validate_community_harness_submission,
)
from legalforecast.multiharness.harness_lane.community_upload import (
    COMMUNITY_HARNESS_DATASET_REPO,
    UPLOAD_PLAN_NAME,
    CommunityIntakeError,
    assert_upload_plan_targets,
)

#: Where a submission has to live in this repository for the intake workflow to
#: accept it: the workflow refuses a ``submission_dir`` outside this root.
COMMUNITY_SUBMISSION_ROOT: Final = "community/submissions"
#: Immutable prefix inside the dataset repository.
RELEASE_PATH_ROOT: Final = "harness-lane"
INTAKE_WORKFLOW: Final = ".github/workflows/community-harness-intake.yaml"

_YEAR: Final = re.compile(r"[0-9]{4}")


@dataclass(frozen=True, slots=True)
class CommunitySubmitResult:
    """One packaged, locally validated submission and where it has to go next."""

    submission_dir: Path
    submission_id: str
    artifact_count: int
    total_bytes: int
    redacted_file_count: int
    excluded_workspace_file_count: int
    normalized_text_file_count: int
    tracked_submission_dir: str | None
    release_path: str | None

    def next_steps(self) -> tuple[str, ...]:
        """Return the exact remaining steps, in order, for this package."""

        lines: list[str] = []
        if self.tracked_submission_dir is None:
            target = f"{COMMUNITY_SUBMISSION_ROOT}/<year>/{self.submission_id}"
            lines.append(
                f"1. Move the package to {target} in a clone of this repository. "
                "The intake workflow refuses a submission outside that root."
            )
            lines.append("2. Commit only that directory, then open a pull request.")
            lines.append(
                "3. Ask a maintainer to dispatch "
                f"{INTAKE_WORKFLOW} at the merge commit with submission_dir="
                f"{target} and release_path={RELEASE_PATH_ROOT}/<year>/"
                f"{self.submission_id}."
            )
        else:
            lines.append(
                f"1. git add {self.tracked_submission_dir} && commit only that "
                "directory, then open a pull request."
            )
            lines.append(
                "2. Ask a maintainer to dispatch "
                f"{INTAKE_WORKFLOW} at the merge commit with submission_dir="
                f"{self.tracked_submission_dir} and release_path="
                f"{self.release_path}."
            )
        lines.append(
            f"The maintainer's job re-validates every declared digest and publishes "
            f"to {COMMUNITY_HARNESS_DATASET_REPO}. It is not the official dataset: "
            "a community harness-lane submission is not an official "
            "LegalForecastBench result."
        )
        return tuple(lines)


def submit_community_harness_run(
    *,
    run_dir: Path,
    output_dir: Path,
    submission_id: str,
    submitter_name: str,
    run_operator_name: str,
    adapter_author_name: str,
    submitter_github: str | None = None,
    secret_values: Sequence[str] = (),
) -> CommunitySubmitResult:
    """Package one run, then refuse it locally for anything the workflow would."""

    submission = build_community_harness_submission(
        run_dir=run_dir,
        output_dir=output_dir,
        submission_id=submission_id,
        submitter_name=submitter_name,
        submitter_github=submitter_github,
        run_operator_name=run_operator_name,
        adapter_author_name=adapter_author_name,
        secret_values=secret_values,
    )
    check_community_harness_submission(submission.submission_dir)
    tracked, release_path = _registry_location(submission.submission_dir, submission_id)
    return CommunitySubmitResult(
        submission_dir=submission.submission_dir,
        submission_id=submission.submission_id,
        artifact_count=submission.artifact_count,
        total_bytes=submission.total_bytes,
        redacted_file_count=submission.redacted_file_count,
        excluded_workspace_file_count=submission.excluded_workspace_file_count,
        normalized_text_file_count=submission.normalized_text_file_count,
        tracked_submission_dir=tracked,
        release_path=release_path,
    )


def check_community_harness_submission(submission_dir: Path) -> tuple[Any, ...]:
    """Run every refusal the publishing job runs, against a package on disk.

    Caps, declared-versus-actual digests, undeclared bytes, symlinks and the
    publication secret scan come from ``validate_community_harness_submission``;
    the destination agreement is checked here because the publishing job checks
    it too, and a contributor should not be the one to discover it is wrong.
    """

    declared = validate_community_harness_submission(submission_dir)
    plan = read_json_object(
        submission_dir / UPLOAD_PLAN_NAME,
        error_factory=CommunityIntakeError,
        missing_message=lambda item: f"submission is missing {item.name}",
        non_object_message=lambda item: f"{item.name} is not a JSON object",
    )
    assert_upload_plan_targets(
        str(plan.get("mirror_repository", "")), COMMUNITY_HARNESS_DATASET_REPO
    )
    return declared


def _registry_location(
    submission_dir: Path, submission_id: str
) -> tuple[str | None, str | None]:
    """Return the tracked path and release prefix, when the layout already fits."""

    resolved = submission_dir.resolve()
    year = resolved.parent.name
    if (
        resolved.name != submission_id
        or _YEAR.fullmatch(year) is None
        or resolved.parent.parent.name != "submissions"
        or resolved.parent.parent.parent.name != "community"
    ):
        return None, None
    return (
        f"{COMMUNITY_SUBMISSION_ROOT}/{year}/{submission_id}",
        f"{RELEASE_PATH_ROOT}/{year}/{submission_id}",
    )


def add_community_submission_parsers(harness_commands: Any) -> None:
    """Register ``submit`` and ``check-submission`` under ``harness``."""

    submit = harness_commands.add_parser(
        "submit",
        help="Package a finished harness-lane run for community submission.",
        description=(
            "Package one containerized harness-lane run, write its upload plan, "
            "and run every check the publishing workflow runs -- before you open "
            "a pull request. A community submission is contributor-run and is "
            "NOT an official LegalForecastBench result."
        ),
    )
    submit.add_argument(
        "--run-dir", type=Path, required=True, help="Completed run output directory."
    )
    submit.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help=(
            "Empty destination for the package. Use "
            f"{COMMUNITY_SUBMISSION_ROOT}/<year>/<submission-id> in a clone of "
            "this repository to get the exact dispatch inputs printed."
        ),
    )
    submit.add_argument(
        "--submission-id",
        required=True,
        help="3-64 lowercase alphanumeric or hyphen characters.",
    )
    submit.add_argument("--submitter-name", required=True)
    submit.add_argument("--submitter-github")
    submit.add_argument("--run-operator-name", required=True)
    submit.add_argument("--adapter-author-name", required=True)
    submit.add_argument(
        "--secret-value",
        action="append",
        default=[],
        metavar="VALUE",
        help=(
            "An exact value that must never survive into the package. Repeatable. "
            "Provider-token shapes and host paths are rewritten without this."
        ),
    )
    submit.set_defaults(handler=cmd_harness_submit)

    check = harness_commands.add_parser(
        "check-submission",
        help="Re-run every intake refusal against a package already on disk.",
        description=(
            "Run the publishing job's checks -- caps, declared digests, "
            "undeclared bytes, symlinks, the publication secret scan, and the "
            "upload plan's destination -- against a submission directory."
        ),
    )
    check.add_argument("--submission-dir", type=Path, required=True)
    check.set_defaults(handler=cmd_harness_check_submission)


def cmd_harness_submit(args: argparse.Namespace) -> int:
    """Package one run for community submission and print what to do next."""

    result = submit_community_harness_run(
        run_dir=cast(Path, args.run_dir),
        output_dir=cast(Path, args.output_dir),
        submission_id=cast(str, args.submission_id),
        submitter_name=cast(str, args.submitter_name),
        submitter_github=cast("str | None", args.submitter_github),
        run_operator_name=cast(str, args.run_operator_name),
        adapter_author_name=cast(str, args.adapter_author_name),
        secret_values=tuple(cast(list[str], args.secret_value)),
    )
    print(
        f"packaged and validated {result.artifact_count} artifact(s), "
        f"{result.total_bytes} bytes, "
        f"{result.redacted_file_count} file(s) redacted, "
        f"{result.excluded_workspace_file_count} staged workspace file(s) left "
        f"out, {result.normalized_text_file_count} plain-text file(s) carried as "
        f"'.json' so the raw-document guardrail still holds, "
        f"into {result.submission_dir}"
    )
    print("")
    for line in result.next_steps():
        print(line)
    return 0


def cmd_harness_check_submission(args: argparse.Namespace) -> int:
    """Re-run the intake refusals against an existing submission directory."""

    submission_dir = cast(Path, args.submission_dir)
    declared = check_community_harness_submission(submission_dir)
    print(
        f"{submission_dir}/{SUBMISSION_RECORD_NAME}: {len(declared)} declared "
        f"artifact(s) match the bytes on disk and target "
        f"{COMMUNITY_HARNESS_DATASET_REPO}"
    )
    return 0
