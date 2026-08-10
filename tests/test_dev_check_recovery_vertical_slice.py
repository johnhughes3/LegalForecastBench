from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dev_check_recovery_vertical_slice.py"
SHELL_WRAPPER = ROOT / "scripts" / "dev-check-recovery-vertical-slice.sh"


def test_full_check_reports_fixture_only_and_combines_focused_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        diagnostics.write("child diagnostic\n")
        return 0

    monkeypatch.delenv("LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST", raising=False)
    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()
    stderr = io.StringIO()

    assert module.main(["--json"], stdout=stdout, stderr=stderr) == 0

    summary = json.loads(stdout.getvalue())
    assert summary["schema_version"] == (
        "legalforecast.dev_check_recovery_vertical_slice.v1"
    )
    assert summary["mode"] == "full"
    assert summary["verdict"] == "PASS_FIXTURE_ONLY"
    assert summary["real_lineage_evaluated"] is False
    assert set(summary) == {
        "checks",
        "duration_seconds",
        "mode",
        "real_lineage_evaluated",
        "schema_version",
        "verdict",
    }
    assert all(
        set(check)
        == {
            "code",
            "duration_seconds",
            "examples",
            "exit_code",
            "id",
            "message",
            "status",
            "suggestions",
        }
        for check in summary["checks"]
    )
    assert [(check["id"], check["status"]) for check in summary["checks"]] == [
        ("real-lineage-preflight", "NOT_EVALUATED"),
        ("focused-regressions", "PASS"),
        ("public-capsule-preflight", "PASS"),
    ]
    assert len(commands) == 2
    focused = commands[0]
    assert focused[1:4] == ("-m", "pytest", "-q")
    assert "tests/test_cycle_preflight.py" in focused
    assert "tests/test_successor_ledger_rehearsal.py" in focused
    assert "child diagnostic" in stderr.getvalue()


def test_auto_format_uses_human_summary_on_a_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        del command, diagnostics
        return 0

    monkeypatch.delenv("LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST", raising=False)
    monkeypatch.setattr(module, "_execute", succeed)
    stdout = _TtyStringIO()

    assert module.main(["--quick"], stdout=stdout, stderr=io.StringIO()) == 0
    assert "RESULT NOT_EVALUATED real-lineage-preflight" in stdout.getvalue()
    assert "DEV_CHECK_VERDICT PASS_FIXTURE_ONLY" in stdout.getvalue()


def test_quick_check_runs_only_supplied_real_lineage_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        return 0

    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()

    assert (
        module.main(
            ["--quick", "--manifest", str(manifest), "--format", "json"],
            stdout=stdout,
            stderr=io.StringIO(),
        )
        == 0
    )

    summary = json.loads(stdout.getvalue())
    assert summary["mode"] == "quick"
    assert summary["verdict"] == "PASS"
    assert summary["real_lineage_evaluated"] is True
    assert [(check["id"], check["status"]) for check in summary["checks"]] == [
        ("real-lineage-preflight", "PASS")
    ]
    assert len(commands) == 1
    assert commands[0][-4:] == (
        "--manifest",
        str(manifest.resolve()),
        "--format",
        "text",
    )


def test_quick_check_routes_discovered_sidecar_to_the_same_pass_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        del diagnostics
        commands.append(tuple(command))
        return 0

    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": "legalforecast.cycle_preflight_manifest_sidecar.v1",
                "non_authoritative": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_execute", succeed)
    explicit = io.StringIO()
    derived = io.StringIO()

    assert module.main(["--quick", "--manifest", str(sidecar)], stdout=explicit) == 0
    monkeypatch.setenv(module.MANIFEST_ENV, str(sidecar))
    assert module.main(["--quick"], stdout=derived) == 0

    assert json.loads(explicit.getvalue())["verdict"] == "PASS"
    assert json.loads(derived.getvalue())["verdict"] == "PASS"
    assert all("--verify-v2-sidecar" in command for command in commands)


def test_full_require_real_lineage_fails_before_expensive_checks_when_manifest_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        return 0

    monkeypatch.delenv("LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST", raising=False)
    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()

    assert (
        module.main(
            ["--require-real-lineage", "--format", "text"],
            stdout=stdout,
            stderr=io.StringIO(),
        )
        == 1
    )

    rendered = stdout.getvalue()
    assert "RESULT FAIL real-lineage-preflight" in rendered
    assert "code=REAL_LINEAGE_MANIFEST_REQUIRED" in rendered
    assert "pass --manifest PATH" in rendered
    assert "SUGGESTION Supply the current authenticated lineage manifest." in rendered
    assert "DEV_CHECK_VERDICT FAIL" in rendered
    assert commands == []


def test_public_capsule_cannot_satisfy_required_real_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        return 0

    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()

    assert (
        module.main(
            [
                "--quick",
                "--manifest",
                str(module.PUBLIC_MANIFEST),
                "--require-real-lineage",
                "--json",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )
        == 1
    )

    summary = json.loads(stdout.getvalue())
    assert summary["real_lineage_evaluated"] is False
    assert summary["verdict"] == "FAIL"
    assert [(check["id"], check["status"]) for check in summary["checks"]] == [
        ("real-lineage-preflight", "FAIL"),
    ]
    assert summary["checks"][0]["code"] == ("REAL_LINEAGE_MANIFEST_IS_PUBLIC_FIXTURE")
    assert "equivalent copy" in summary["checks"][0]["message"]
    assert commands == []


def test_copied_public_capsule_cannot_satisfy_required_real_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    copied_capsule = tmp_path / "copied-capsule"
    shutil.copytree(module.PUBLIC_MANIFEST.parent, copied_capsule)
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        return 0

    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()

    assert (
        module.main(
            [
                "--quick",
                "--manifest",
                str(copied_capsule / "manifest.json"),
                "--require-real-lineage",
                "--json",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )
        == 1
    )

    summary = json.loads(stdout.getvalue())
    assert summary["real_lineage_evaluated"] is False
    assert summary["checks"][0]["code"] == ("REAL_LINEAGE_MANIFEST_IS_PUBLIC_FIXTURE")
    assert commands == []


def test_reordered_public_capsule_cannot_satisfy_required_real_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    copied_capsule = tmp_path / "reordered-capsule"
    shutil.copytree(module.PUBLIC_MANIFEST.parent, copied_capsule)
    manifest = copied_capsule / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["nodes"][0], payload["nodes"][1] = payload["nodes"][1], payload["nodes"][0]
    manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        return 0

    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()

    assert (
        module.main(
            [
                "--quick",
                "--manifest",
                str(manifest),
                "--require-real-lineage",
                "--json",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )
        == 1
    )

    summary = json.loads(stdout.getvalue())
    assert summary["real_lineage_evaluated"] is False
    assert summary["checks"][0]["code"] == ("REAL_LINEAGE_MANIFEST_IS_PUBLIC_FIXTURE")
    assert commands == []


def test_public_capsule_with_ignored_sha_field_remains_fixture_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    copied_capsule = tmp_path / "augmented-capsule"
    shutil.copytree(module.PUBLIC_MANIFEST.parent, copied_capsule)
    manifest = copied_capsule / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["nodes"][0]["validator"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        return 0

    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()

    assert (
        module.main(
            [
                "--quick",
                "--manifest",
                str(manifest),
                "--require-real-lineage",
                "--json",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )
        == 1
    )

    summary = json.loads(stdout.getvalue())
    assert summary["real_lineage_evaluated"] is False
    assert summary["checks"][0]["code"] == ("REAL_LINEAGE_MANIFEST_IS_PUBLIC_FIXTURE")
    assert commands == []


def test_public_capsule_with_uppercase_digest_hex_remains_fixture_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    copied_capsule = tmp_path / "uppercase-capsule"
    shutil.copytree(module.PUBLIC_MANIFEST.parent, copied_capsule)
    manifest = copied_capsule / "manifest.json"

    def uppercase_digest(value: str) -> str:
        prefix = "sha256:" if value.startswith("sha256:") else ""
        return prefix + value.removeprefix(prefix).upper()

    payload = json.loads(
        manifest.read_text(encoding="utf-8"),
        object_hook=lambda record: {
            key: uppercase_digest(value)
            if key == "sha256" and isinstance(value, str)
            else value
            for key, value in record.items()
        },
    )
    manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    commands: list[tuple[str, ...]] = []

    def succeed(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        commands.append(tuple(command))
        return 0

    monkeypatch.setattr(module, "_execute", succeed)
    stdout = io.StringIO()

    assert (
        module.main(
            [
                "--quick",
                "--manifest",
                str(manifest),
                "--require-real-lineage",
                "--json",
            ],
            stdout=stdout,
            stderr=io.StringIO(),
        )
        == 1
    )

    summary = json.loads(stdout.getvalue())
    assert summary["real_lineage_evaluated"] is False
    assert summary["checks"][0]["code"] == ("REAL_LINEAGE_MANIFEST_IS_PUBLIC_FIXTURE")
    assert commands == []


def test_full_check_collects_all_results_after_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    calls = 0

    def fail_first(command: Sequence[str], *, diagnostics: io.TextIOBase) -> int:
        del command, diagnostics
        nonlocal calls
        calls += 1
        return 7 if calls == 1 else 0

    monkeypatch.delenv("LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST", raising=False)
    monkeypatch.setattr(module, "_execute", fail_first)
    stdout = io.StringIO()

    assert module.main(["--format", "json"], stdout=stdout, stderr=io.StringIO()) == 1

    summary = json.loads(stdout.getvalue())
    assert summary["verdict"] == "FAIL"
    assert [(check["id"], check["status"]) for check in summary["checks"]] == [
        ("real-lineage-preflight", "NOT_EVALUATED"),
        ("focused-regressions", "FAIL"),
        ("public-capsule-preflight", "PASS"),
    ]
    failed = summary["checks"][1]
    assert failed["code"] == "CHECK_COMMAND_FAILED"
    assert failed["message"] == "command exited with status 7"
    assert failed["suggestions"]
    assert failed["examples"]
    assert calls == 2


def test_shell_wrapper_help_is_concise_and_executes_no_checks() -> None:
    completed = subprocess.run(
        [str(SHELL_WRAPPER), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert completed.stdout.startswith(
        "usage: scripts/dev-check-recovery-vertical-slice.sh"
    )
    assert "--quick" in completed.stdout
    assert "--require-real-lineage" in completed.stdout
    assert "Examples:" in completed.stdout
    assert "CHECK " not in completed.stderr


def test_shell_wrapper_rejects_unknown_pytest_arguments_before_checks() -> None:
    completed = subprocess.run(
        [str(SHELL_WRAPPER), "--extra-test=--collect-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 2
    assert "unrecognized arguments" in completed.stderr
    assert "scripts/dev-check-recovery-vertical-slice.sh" in completed.stderr
    assert "CHECK " not in completed.stderr


def test_shell_wrapper_quick_success_keeps_json_summary_on_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LEGALFORECAST_CYCLE_PREFLIGHT_MANIFEST", raising=False)
    completed = subprocess.run(
        [str(SHELL_WRAPPER), "--quick", "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0
    assert completed.stdout.count("\n") == 1
    summary = json.loads(completed.stdout)
    assert summary["verdict"] == "PASS_FIXTURE_ONLY"
    assert summary["real_lineage_evaluated"] is False
    assert [check["id"] for check in summary["checks"]] == [
        "real-lineage-preflight",
        "public-capsule-preflight",
    ]
    assert "CHECK public-capsule-preflight" in completed.stderr


def test_shell_wrapper_preserves_caller_relative_manifest_paths(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")

    completed = subprocess.run(
        [str(SHELL_WRAPPER), "--quick", "--manifest", manifest.name, "--json"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 1
    summary = json.loads(completed.stdout)
    assert summary["checks"][0]["status"] == "FAIL"
    assert str(manifest) in summary["checks"][0]["examples"][0]


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "dev_check_recovery_vertical_slice", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not load developer-check script")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


class _TtyStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True
