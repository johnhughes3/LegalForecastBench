"""The run-attempt allowance counts case failures, not guard-blocked jobs."""

import json
import runpy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / ".github/scripts/check-jev-failures.py"
MODULE = runpy.run_path(str(SCRIPT))


def job(number, conclusion="failure", step=None, name=None):
    return {
        "id": number,
        "name": name or MODULE["JOB_PREFIX"] + f" (case {number})",
        "steps": [{"name": step or MODULE["EXECUTE_STEP"], "conclusion": conclusion}],
    }


@pytest.mark.parametrize("count,expected", [(0, 0), (1, 0), (2, 0), (3, 1), (4, 1)])
def test_failed_case_allowance(tmp_path, count, expected):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps([{"jobs": [job(i) for i in range(count)]}]))
    assert MODULE["main"](path) == expected


def test_counts_all_pages_and_ignores_other_failures(tmp_path):
    path = tmp_path / "jobs.json"
    path.write_text(
        json.dumps(
            [
                {"jobs": [job(1), job(2, "success"), job(3, "cancelled")]},
                {
                    "jobs": [
                        job(4, step="Check Jev failed-case allowance"),
                        job(5, name="OpenAI cells"),
                        job(6),
                        job(1),
                    ]
                },
            ]
        )
    )
    assert MODULE["main"](path) == 0
    pages = json.loads(path.read_text())
    pages.append({"jobs": [job(7)]})
    path.write_text(json.dumps(pages))
    assert MODULE["main"](path) == 1
