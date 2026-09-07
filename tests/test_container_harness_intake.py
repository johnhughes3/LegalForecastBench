"""Intake trigger model and validation-before-upload for the fenced platform."""

from __future__ import annotations

import json
from pathlib import Path

import legalforecast
import pytest
from legalforecast.multiharness.container_harness.egress_proxy import (
    REASON_HOST_NOT_ALLOWLISTED,
)
from legalforecast.multiharness.container_harness.fence import (
    ParserFenceFields,
    fence_from_parser_fields,
)
from legalforecast.multiharness.container_harness.intake import (
    IntakeError,
    publish_intake_package,
    validate_intake_package,
)
from legalforecast.multiharness.container_harness.publication import (
    write_published_package,
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


def _write_counted_package(destination: Path) -> None:
    write_published_package(
        destination,
        result_record={"run_id": "cycle1-claude-code"},
        egress_evidence={
            "allowed_hosts": ["api.anthropic.com"],
            "refused": [
                {
                    "host": "attacker-choice.not-allowlisted.test",
                    "port": 443,
                    "reason": REASON_HOST_NOT_ALLOWLISTED,
                }
            ],
            "decision_count": 2,
        },
        fence=fence_from_parser_fields(
            ParserFenceFields(
                parse_ok=True,
                reports_fence=True,
                tools_available=("Bash",),
            )
        ),
        allowlist={
            "hosts": ["api.anthropic.com"],
            "subdomain_suffixes": [],
            "ports": [443],
        },
    )


def test_matching_egress_counts_are_accepted_at_intake(tmp_path: Path) -> None:
    package = tmp_path / "published"
    _write_counted_package(package)

    result = json.loads((package / "result.json").read_text(encoding="utf-8"))
    assert result["egress_allowed_host_count"] == 1
    assert result["egress_refused_count"] == 1
    validate_intake_package(package)


def test_writer_counts_the_sanitized_evidence_lists(tmp_path: Path) -> None:
    package = tmp_path / "published"
    write_published_package(
        package,
        result_record={"run_id": "cycle1-claude-code"},
        egress_evidence={
            "allowed_hosts": [
                "first-secret.api.anthropic.com",
                "second-secret.api.anthropic.com",
            ],
            "refused": [],
            "decision_count": 2,
        },
        fence=fence_from_parser_fields(
            ParserFenceFields(parse_ok=True, reports_fence=False)
        ),
        allowlist={
            "hosts": [],
            "subdomain_suffixes": ["anthropic.com"],
            "ports": [443],
        },
    )

    result = json.loads((package / "result.json").read_text(encoding="utf-8"))
    assert result["egress_allowed_hosts"] == ["*.anthropic.com"]
    assert result["egress_allowed_host_count"] == 1
    validate_intake_package(package)


@pytest.mark.parametrize(
    ("field_name", "bad_value", "remove", "match"),
    [
        ("egress_allowed_host_count", None, True, "missing"),
        ("egress_refused_count", None, True, "missing"),
        ("egress_allowed_host_count", True, False, "integer"),
        ("egress_refused_count", False, False, "integer"),
        ("egress_allowed_host_count", 2, False, "does not match"),
        ("egress_refused_count", 0, False, "does not match"),
    ],
)
def test_intake_refuses_missing_bool_or_mismatched_egress_counts(
    tmp_path: Path,
    field_name: str,
    bad_value: object,
    remove: bool,
    match: str,
) -> None:
    package = tmp_path / "published"
    _write_counted_package(package)
    result_path = package / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if remove:
        del result[field_name]
    else:
        result[field_name] = bad_value
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(IntakeError, match=match):
        validate_intake_package(package)
