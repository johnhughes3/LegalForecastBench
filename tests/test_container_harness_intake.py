"""Intake trigger model and validation-before-upload for the fenced platform."""

from __future__ import annotations

from pathlib import Path

import legalforecast
import pytest
from legalforecast.multiharness.container_harness.intake import (
    IntakeError,
    publish_intake_package,
    validate_intake_package,
)

ROOT = Path(legalforecast.__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/harness-lane-intake.yaml"
WORKFLOW_ROOT = ROOT / ".github" / "workflows"


def test_intake_workflow_is_dispatch_only_with_empty_top_level_permissions() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    trigger, _, rest = workflow.partition("\njobs:")
    assert "\non:\n  workflow_dispatch:\n" in trigger
    assert "pull_request:" not in trigger
    assert "pull_request_target:" not in workflow
    assert "push:" not in trigger
    assert "schedule:" not in trigger
    assert "\npermissions: {}\n" in workflow
    assert "legalforecast.multiharness.container_harness.intake" in rest


def test_intake_validation_runs_before_any_upload() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    validate_at = workflow.index("container_harness.intake \\\n            validate")
    publish_at = workflow.index("container_harness.intake \\\n            publish")
    upload_at = workflow.index("actions/upload-artifact@")
    assert validate_at < publish_at < upload_at


def test_no_workflow_uses_pull_request_target() -> None:
    offenders = [
        path.name
        for path in sorted(WORKFLOW_ROOT.glob("*.y*ml"))
        if "pull_request_target:" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_validate_refuses_a_secret_bearing_package(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "notes.json").write_text(
        '{"ANTHROPIC_API_KEY": "sk-ant-not-for-publication"}\n',
        encoding="utf-8",
    )

    with pytest.raises(IntakeError, match="publication guardrail"):
        validate_intake_package(package)


def test_publish_does_not_write_destination_when_validation_fails(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "notes.json").write_text(
        '{"ANTHROPIC_API_KEY": "sk-ant-not-for-publication"}\n',
        encoding="utf-8",
    )
    destination = tmp_path / "destination"

    with pytest.raises(IntakeError, match="publication guardrail"):
        publish_intake_package(package, destination)

    assert not destination.exists()


def test_publish_copies_only_after_validation(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "summary.json").write_text('{"ok": true}\n', encoding="utf-8")
    destination = tmp_path / "destination"

    publish_intake_package(package, destination)

    assert (destination / "summary.json").read_text(
        encoding="utf-8"
    ) == '{"ok": true}\n'


def test_publish_refuses_to_overwrite_an_existing_destination(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "summary.json").write_text('{"ok": true}\n', encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "already.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(IntakeError, match="already exists"):
        publish_intake_package(package, destination)

    assert (destination / "already.json").read_text(encoding="utf-8") == "{}\n"
    assert not (destination / "summary.json").exists()


def test_validate_refuses_an_oversized_artifact(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    huge = package / "blob.json"
    huge.write_bytes(b"{" + (b"x" * (8 * 1024 * 1024)) + b"}")

    with pytest.raises(IntakeError, match="intake cap"):
        validate_intake_package(package)


def test_validate_refuses_a_symlink_file_inside_the_package(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "summary.json").write_text('{"ok": true}\n', encoding="utf-8")
    host_file = tmp_path / "host-secret.json"
    host_file.write_text(
        '{"ANTHROPIC_API_KEY": "sk-ant-host-file"}\n', encoding="utf-8"
    )
    (package / "leak.json").symlink_to(host_file)

    with pytest.raises(IntakeError, match="symlink"):
        validate_intake_package(package)


def test_validate_refuses_a_directory_symlink_inside_the_package(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "summary.json").write_text('{"ok": true}\n', encoding="utf-8")
    host_dir = tmp_path / "host-dir"
    host_dir.mkdir()
    (host_dir / "secret.json").write_text("{}\n", encoding="utf-8")
    (package / "nested").symlink_to(host_dir)

    with pytest.raises(IntakeError, match="symlink"):
        validate_intake_package(package)


def test_validate_refuses_a_symlinked_package_root(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "summary.json").write_text('{"ok": true}\n', encoding="utf-8")
    package = tmp_path / "package"
    package.symlink_to(real)

    with pytest.raises(IntakeError, match="symlink"):
        validate_intake_package(package)


def test_publish_does_not_copy_through_a_symlink(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "summary.json").write_text('{"ok": true}\n', encoding="utf-8")
    host_file = tmp_path / "host-secret.json"
    host_file.write_text("host-bytes-must-not-be-copied\n", encoding="utf-8")
    (package / "leak.json").symlink_to(host_file)
    destination = tmp_path / "destination"

    with pytest.raises(IntakeError, match="symlink"):
        publish_intake_package(package, destination)

    assert not destination.exists()


def test_validate_scans_text_up_to_the_intake_cap(tmp_path: Path) -> None:
    """A secret in a 3 MiB JSON is under the 8 MiB cap and must still be refused.

    The guardrail default of 2_000_000 bytes would skip this file; intake must
    scan every text artifact the cap permits.
    """

    package = tmp_path / "package"
    package.mkdir()
    padding = "x" * (3 * 1024 * 1024)
    (package / "notes.json").write_text(
        f'{{"ANTHROPIC_API_KEY": "sk-ant-not-for-publication", "pad": "{padding}"}}\n',
        encoding="utf-8",
    )

    with pytest.raises(IntakeError, match="publication guardrail"):
        validate_intake_package(package)
