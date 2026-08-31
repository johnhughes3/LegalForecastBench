from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.testing.cli_corpus.differential import (
    CASES,
    DifferentialCase,
    compare_result,
    load_differential_fixture,
    run_case,
    validate_case_argv,
)
from legalforecast.testing.cli_corpus.invoke import (
    CliCapture,
    _normalize_argparse_choose_from,
    invoke_cli,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
def test_differential_case_matches_exact_byte_fixture(case, tmp_path: Path) -> None:
    result = run_case(case, tmp_path)
    expected = load_differential_fixture(ROOT, case.case_id)
    assert result.exit_status == case.expected_exit
    assert result.extra_files == ()
    assert compare_result(result, expected) == ()
    if case.case_id == "unknown-command":
        assert result.output_tree == ()
        assert "definitely-not-a-command" in result.stderr


def test_differential_corpus_refuses_live_provider_and_authority_actions() -> None:
    with pytest.raises(ValueError, match="forbidden tokens"):
        validate_case_argv(("retrieve", "--live"))
    with pytest.raises(ValueError, match="forbidden tokens"):
        validate_case_argv(("acquisition", "purchase"))
    with pytest.raises(ValueError, match="help bypass"):
        validate_case_argv(("publish", "aggregate", "--output-dir", "x"))
    validate_case_argv(("publish", "aggregate", "--help"))
    for case in CASES:
        validate_case_argv(case.argv_template)


def test_resume_keeps_failing_first_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def fake_invoke(argv: object, **kwargs: object) -> CliCapture:
        del argv, kwargs
        calls["n"] += 1
        if calls["n"] == 1:
            return CliCapture(1, "", "first-failed\n")
        return CliCapture(0, "", "second-ok\n")

    monkeypatch.setattr(
        "legalforecast.testing.cli_corpus.differential.invoke_cli",
        fake_invoke,
    )
    case = DifferentialCase(
        "manifest-help",
        ("manifest", "--help"),
        0,
        "empty",
        resume=True,
    )
    result = run_case(case, tmp_path)
    assert calls["n"] == 1
    assert result.exit_status == 1
    assert result.first_exit_status == 1
    assert result.stderr == "first-failed\n"
    assert result.first_stderr == "first-failed\n"


def test_resume_fixtures_record_the_first_invocation() -> None:
    for case_id in ("score-dry-run",):
        payload = load_differential_fixture(ROOT, case_id)
        assert payload["first_exit_status"] == payload["exit_status"] == 0
        assert "first_stdout" in payload
        assert "first_stderr" in payload


def test_invoke_cli_disables_color_and_pins_width(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import shutil

    monkeypatch.setenv("PYTHON_COLORS", "1")
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(
        shutil,
        "get_terminal_size",
        lambda fallback=(80, 24): os.terminal_size((32, 10)),
    )
    captured = invoke_cli(("definitely-not-a-command",))
    assert captured.exit_status == 2
    assert "\x1b[" not in captured.stderr
    assert captured.stderr.startswith("usage: legalforecast")
    assert "definitely-not-a-command" in captured.stderr
    assert "choose from manifest, release" in captured.stderr
    assert "'manifest'" not in captured.stderr


def test_argparse_choose_from_quotes_are_stripped() -> None:
    quoted = (
        "legalforecast: error: argument COMMAND: invalid choice: "
        "'definitely-not-a-command' (choose from 'manifest', 'release')\n"
    )
    assert _normalize_argparse_choose_from(quoted) == (
        "legalforecast: error: argument COMMAND: invalid choice: "
        "'definitely-not-a-command' (choose from manifest, release)\n"
    )
