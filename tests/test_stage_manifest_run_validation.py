"""Execute the staging workflow's request gate, rather than reading it.

``tests/test_stage_manifest_run_lane.py`` pins the workflow's shape.  This file
runs the gate's actual shell against a throwaway checkout, because "refuses a
cross-lane request" is a behavioural claim and a string-presence assertion is
not evidence for it.  The script is extracted from the production workflow on
every run, never transcribed, so drift reddens these tests instead of leaving a
copy quietly passing.

The gate is the last check that happens before any AWS credential exists: it
runs in a ``contents: read`` job with no ``id-token: write``, so a request it
refuses never reaches a role at all.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGING_WORKFLOW = ROOT / ".github" / "workflows" / "stage-manifest-run.yaml"
MANIFEST_RUN_PREFIX = "cycle-1/manifest-runs"
MANIFEST_DIGEST = "a" * 64
OFFICIAL_FREEZE_DIGEST = "b" * 64


def _validation_script() -> str:
    """Extract the production validation script, dedented to column zero."""

    text = STAGING_WORKFLOW.read_text(encoding="utf-8")
    start = text.index("      - name: Validate lane, pins, and checked-out inputs")
    body = text[start:].split("        run: |\n", 1)[1]
    body = body.split("\n  stage:", 1)[0]
    lines = [
        line[10:] if line.startswith(" " * 10) else line
        for line in body.rstrip().splitlines()
    ]
    assert lines[0].startswith("set -euo pipefail"), lines[0]
    return "\n".join(lines) + "\n"


def _run_validation(
    tmp_path: Path,
    tracked: Mapping[str, bytes],
    *,
    untracked: Mapping[str, bytes] | None = None,
    **inputs: str,
) -> subprocess.CompletedProcess[str]:
    """Run the real script in a throwaway git repo standing in for the checkout."""

    repo = tmp_path / "repo"
    repo.mkdir()

    def _write(name: str, payload: bytes) -> None:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    for name, payload in tracked.items():
        _write(name, payload)
    for command in (
        ["git", "init", "--quiet", "--initial-branch", "main"],
        ["git", "config", "user.email", "test@example.invalid"],
        ["git", "config", "user.name", "test"],
        ["git", "add", "--all"],
        ["git", "commit", "--quiet", "-m", "fixture"],
    ):
        subprocess.run(command, cwd=repo, check=True, capture_output=True)
    # Written after the commit on purpose: present on disk, absent from the
    # release, which is the shape of the operator's gitignored artifacts/ tree.
    for name, payload in (untracked or {}).items():
        _write(name, payload)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": head,
        "GITHUB_OUTPUT": str(tmp_path / "github-output"),
        "DRY_RUN": "true",
        "FREEZE_BUNDLE_PATH": "",
        "FREEZE_BUNDLE_SHA256": "",
        "LANE": "supplementary",
        "LOCAL_ARTIFACTS": "",
        "MANIFEST_DIGEST": MANIFEST_DIGEST,
        "OFFICIAL_FREEZE_BUNDLE_SHA256": OFFICIAL_FREEZE_DIGEST,
        "RELEASE_SHA": head,
        **inputs,
    }
    script = tmp_path / "validate.sh"
    script.write_text(_validation_script(), encoding="utf-8")
    return subprocess.run(
        ["bash", str(script)],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def tracked_supplementary() -> tuple[dict[str, bytes], str]:
    freeze = b'{"cycle_id": "cycle-1"}'
    tracked = {
        "committed/sibling.freeze.json": freeze,
        "model_registries/supplementary.json": b'{"registry": "supplementary"}',
    }
    return tracked, hashlib.sha256(freeze).hexdigest()


def test_a_well_formed_supplementary_request_is_accepted(
    tmp_path: Path, tracked_supplementary: tuple[dict[str, bytes], str]
) -> None:
    tracked, digest = tracked_supplementary
    result = _run_validation(
        tmp_path,
        tracked,
        LANE="supplementary",
        FREEZE_BUNDLE_PATH="committed/sibling.freeze.json",
        FREEZE_BUNDLE_SHA256=digest,
        LOCAL_ARTIFACTS="model_registry=model_registries/supplementary.json",
    )
    assert result.returncode == 0, result.stderr
    written = (tmp_path / "github-output").read_text(encoding="utf-8")
    assert (
        f"expected_prefix={MANIFEST_RUN_PREFIX}/supplementary/"
        f"{MANIFEST_DIGEST}/{digest}" in written
    )


def test_a_well_formed_official_request_is_accepted(tmp_path: Path) -> None:
    result = _run_validation(tmp_path, {"README.md": b"fixture\n"}, LANE="official")
    assert result.returncode == 0, result.stderr
    written = (tmp_path / "github-output").read_text(encoding="utf-8")
    assert f"expected_prefix={MANIFEST_RUN_PREFIX}/{MANIFEST_DIGEST}" in written
    # The official prefix must never acquire the supplementary segment.
    assert "supplementary" not in written


@pytest.mark.parametrize(
    ("label", "overrides", "expected"),
    [
        (
            "official lane carrying a sibling freeze",
            {"LANE": "official", "FREEZE_BUNDLE_PATH": "committed/x.json"},
            "takes no freeze_bundle_path",
        ),
        (
            "official lane replacing an artifact",
            {"LANE": "official", "LOCAL_ARTIFACTS": "model_registry=x.json"},
            "takes no freeze_bundle_path",
        ),
        (
            "official lane carrying a sibling digest",
            {"LANE": "official", "FREEZE_BUNDLE_SHA256": "c" * 64},
            "takes no freeze_bundle_path",
        ),
        (
            "supplementary lane with no freeze digest",
            {"LANE": "supplementary"},
            "requires freeze_bundle_sha256",
        ),
        (
            "supplementary lane pinning the official bundle itself",
            {
                "LANE": "supplementary",
                "FREEZE_BUNDLE_SHA256": OFFICIAL_FREEZE_DIGEST,
                "FREEZE_BUNDLE_PATH": "committed/sibling.freeze.json",
            },
            "belongs in the official lane",
        ),
        (
            "an unreviewed lane",
            {"LANE": "experimental"},
            "outside the reviewed allowlist",
        ),
        (
            "a manifest digest that is not a digest",
            {"LANE": "official", "MANIFEST_DIGEST": "not-a-digest"},
            "MANIFEST_DIGEST must be a lowercase SHA-256",
        ),
        (
            "an uppercase digest",
            {"LANE": "official", "OFFICIAL_FREEZE_BUNDLE_SHA256": "B" * 64},
            "OFFICIAL_FREEZE_BUNDLE_SHA256 must be a lowercase SHA-256",
        ),
        (
            "a dispatch that is not the exact main commit",
            {"LANE": "official", "RELEASE_SHA": "0" * 40},
            "release_sha must equal the exact main commit",
        ),
        (
            "a dispatch from a branch other than main",
            {"LANE": "official", "GITHUB_REF": "refs/heads/feature"},
            "allowed only from refs/heads/main",
        ),
        (
            "a dry_run value that is neither true nor false",
            {"LANE": "official", "DRY_RUN": "maybe"},
            "dry_run must be true or false",
        ),
    ],
)
def test_malformed_and_cross_lane_requests_are_refused(
    tmp_path: Path,
    tracked_supplementary: tuple[dict[str, bytes], str],
    label: str,
    overrides: Mapping[str, str],
    expected: str,
) -> None:
    tracked, _ = tracked_supplementary
    result = _run_validation(tmp_path, tracked, **overrides)
    assert result.returncode != 0, f"{label} was accepted"
    assert expected in result.stderr, f"{label}: {result.stderr}"


@pytest.mark.parametrize(
    ("label", "path"),
    [
        ("an absolute path", "/etc/hostname"),
        ("a traversal", "../../etc/hostname"),
        ("a path that does not exist", "committed/absent.json"),
        ("a command substitution", "committed/$(id).json"),
    ],
)
def test_paths_outside_the_tracked_checkout_are_refused(
    tmp_path: Path,
    tracked_supplementary: tuple[dict[str, bytes], str],
    label: str,
    path: str,
) -> None:
    tracked, digest = tracked_supplementary
    result = _run_validation(
        tmp_path,
        tracked,
        LANE="supplementary",
        FREEZE_BUNDLE_PATH=path,
        FREEZE_BUNDLE_SHA256=digest,
        LOCAL_ARTIFACTS="model_registry=model_registries/supplementary.json",
    )
    assert result.returncode != 0, label


def test_an_untracked_working_tree_file_is_refused(
    tmp_path: Path, tracked_supplementary: tuple[dict[str, bytes], str]
) -> None:
    """The gitignored ``artifacts/`` tree is exactly what must not be read here.

    A file present on disk but absent from the commit did not go through review,
    so it must not become a staging input even though it would open cleanly.
    """

    tracked, _ = tracked_supplementary
    payload = b'{"cycle_id": "cycle-1", "source": "operator working tree"}'
    result = _run_validation(
        tmp_path,
        tracked,
        untracked={"artifacts/local-only.freeze.json": payload},
        LANE="supplementary",
        FREEZE_BUNDLE_PATH="artifacts/local-only.freeze.json",
        # The pin agrees with the bytes, so only trackedness can refuse this.
        FREEZE_BUNDLE_SHA256=hashlib.sha256(payload).hexdigest(),
        LOCAL_ARTIFACTS="model_registry=model_registries/supplementary.json",
    )
    assert result.returncode != 0
    assert "is not tracked at the release commit" in result.stderr


def test_a_supplementary_request_replacing_nothing_is_refused(
    tmp_path: Path, tracked_supplementary: tuple[dict[str, bytes], str]
) -> None:
    """A sibling freeze replaces at least its own registry, by construction.

    An empty replacement set means the candidate is claiming to be a sibling
    while sharing every artifact with the official freeze, which is either the
    official freeze itself or a mistake.
    """

    tracked, digest = tracked_supplementary
    result = _run_validation(
        tmp_path,
        tracked,
        LANE="supplementary",
        FREEZE_BUNDLE_PATH="committed/sibling.freeze.json",
        FREEZE_BUNDLE_SHA256=digest,
        LOCAL_ARTIFACTS="",
    )
    assert result.returncode != 0
    assert "requires local_artifacts" in result.stderr


def test_local_artifact_entries_must_name_a_tracked_path(
    tmp_path: Path, tracked_supplementary: tuple[dict[str, bytes], str]
) -> None:
    tracked, digest = tracked_supplementary
    result = _run_validation(
        tmp_path,
        tracked,
        LANE="supplementary",
        FREEZE_BUNDLE_PATH="committed/sibling.freeze.json",
        FREEZE_BUNDLE_SHA256=digest,
        LOCAL_ARTIFACTS="model_registry=model_registries/absent.json",
    )
    assert result.returncode != 0
    assert "local_artifacts entry model_registry" in result.stderr


def test_local_artifact_entries_must_be_name_equals_path(
    tmp_path: Path, tracked_supplementary: tuple[dict[str, bytes], str]
) -> None:
    tracked, digest = tracked_supplementary
    result = _run_validation(
        tmp_path,
        tracked,
        LANE="supplementary",
        FREEZE_BUNDLE_PATH="committed/sibling.freeze.json",
        FREEZE_BUNDLE_SHA256=digest,
        LOCAL_ARTIFACTS="model_registries/supplementary.json",
    )
    assert result.returncode != 0
    assert "must be <artifact_name>=<path>" in result.stderr


def test_a_freeze_whose_bytes_disagree_with_its_pin_is_refused(
    tmp_path: Path, tracked_supplementary: tuple[dict[str, bytes], str]
) -> None:
    """The pin is what makes the supplementary prefix computable up front."""

    tracked, _ = tracked_supplementary
    result = _run_validation(
        tmp_path,
        tracked,
        LANE="supplementary",
        FREEZE_BUNDLE_PATH="committed/sibling.freeze.json",
        FREEZE_BUNDLE_SHA256="c" * 64,
        LOCAL_ARTIFACTS="model_registry=model_registries/supplementary.json",
    )
    assert result.returncode != 0
    assert "hashes to" in result.stderr


def test_validation_script_passes_shellcheck(tmp_path: Path) -> None:
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck is not installed")
    script = tmp_path / "validate.sh"
    script.write_text("#!/usr/bin/env bash\n" + _validation_script(), encoding="utf-8")
    result = subprocess.run(
        ["shellcheck", "--severity=warning", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
