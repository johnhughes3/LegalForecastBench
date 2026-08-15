from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.testing.cli_corpus.differential import (
    CASES,
    compare_result,
    load_differential_fixture,
    run_case,
    validate_case_argv,
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
        validate_case_argv(("freeze", "--bundle", "x"))
    with pytest.raises(ValueError, match="help bypass"):
        validate_case_argv(("publish", "aggregate", "--output-dir", "x"))
    validate_case_argv(("freeze", "--help"))
    validate_case_argv(("publish", "aggregate", "--help"))
    for case in CASES:
        validate_case_argv(case.argv_template)
