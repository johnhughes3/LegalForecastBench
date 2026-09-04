"""Semantic public-boundary fences for the supported LegalForecastBench runtime.

Each fence is proved by a permitted near-neighbor and a planted forbidden
example so the gate protects behavior rather than topology or names.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from legalforecast.testing.architecture_rules.public_boundary import (
    OPERATOR_COMMANDS,
    RETIRED_OFFICIAL_WORKFLOWS,
    approval_prose_lookups,
    bd_execution_argvs,
    forbidden_imports_in,
    is_forbidden_import,
    private_runtime_help_violations,
    retired_dispatch_inputs,
    scan_public_boundary,
)
from legalforecast.testing.cli_corpus.invoke import invoke_cli

ROOT = Path(__file__).resolve().parents[1]

_PERMITTED_IMPORTS = (
    "from legalforecast.cli_commands.manifest import run_validate\n",
    "from legalforecast.contracts.schemas import FORECAST_RELEASE_V1\n",
    "from legalforecast.evals.scorers import score_cases\n",
    "from legalforecast.immutable_io import read_single_link_file\n",
    "from legalforecast.ingestion.canonical_json import canonical_json_bytes\n",
    "from legalforecast.publication.withdrawal import WithdrawalLedgerEntry\n",
    "from legalforecast.release import load_run_manifest\n",
    (
        "from legalforecast.reporting.leaderboard import "
        "build_benchmark_leaderboard_report\n"
    ),
)
_FORBIDDEN_IMPORTS = (
    "from legalforecast.acquisition import pacer\n",
    "from legalforecast.labeling import llm_pipeline\n",
    "import courtlistener\n",
    "import pacer\n",
    "import recap\n",
    "import beads\n",
)
_PERMITTED_GIT = """\
import subprocess

subprocess.run(["git", "ls-files", "--", "*.py"])
"""
_FORBIDDEN_BD = """\
import subprocess

subprocess.run(["bd", "show", "legalforecastbench-xvg1"])
"""
_FORBIDDEN_BD_COMMENTS = """\
import subprocess

subprocess.run(["bd", "comments", "legalforecastbench-xvg1", "--json"])
"""
_PERMITTED_APPROVAL_REFERENCE = """\
def bind_run(*, approval_reference: str | None) -> dict[str, str]:
    return {"approval_reference": approval_reference or ""}
"""
_FORBIDDEN_OWNER_PROSE = """\
from pathlib import Path

def load_approval_prose(path: Path) -> str:
    return Path("owner-prose.md").read_text(encoding="utf-8")
"""
_PERMITTED_FORECAST_WORKFLOW = """\
on:
  workflow_dispatch:
    inputs:
      manifest_uri:
        required: true
      forecast_release_uri:
        required: true
jobs:
  prepare-inputs:
    runs-on: ubuntu-latest
"""
_PERMITTED_FAN_IN_WORKFLOW = """\
on:
  workflow_dispatch:
    inputs:
      manifest_uri:
        required: true
      labels_release_uri:
        required: true
jobs:
  fan-in-results:
    runs-on: ubuntu-latest
"""
_FORBIDDEN_FORECAST_WORKFLOW = """\
on:
  workflow_dispatch:
    inputs:
      manifest_uri:
        required: true
      labels_uri:
        required: true
      run_input_manifest_uri:
        required: true
jobs:
  prepare-inputs:
    runs-on: ubuntu-latest
"""


def _write_probe(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "legalforecast" / "probe.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_production_runtime_stays_inside_the_public_boundary() -> None:
    assert scan_public_boundary(ROOT) == ()


@pytest.mark.parametrize("source", _PERMITTED_IMPORTS)
def test_permitted_near_neighbor_imports_are_allowed(
    tmp_path: Path, source: str
) -> None:
    assert forbidden_imports_in(_write_probe(tmp_path, source)) == ()


@pytest.mark.parametrize("source", _FORBIDDEN_IMPORTS)
def test_seeded_private_runtime_imports_are_rejected(
    tmp_path: Path, source: str
) -> None:
    found = forbidden_imports_in(_write_probe(tmp_path, source))
    assert found
    assert all(is_forbidden_import(module) for module in found)


def test_schema_identifier_strings_are_not_treated_as_imports(tmp_path: Path) -> None:
    source = 'SCHEMA = "legalforecast.acquisition_run_card.v1"\n'
    assert forbidden_imports_in(_write_probe(tmp_path, source)) == ()


def test_dynamic_courtlistener_import_is_rejected(tmp_path: Path) -> None:
    source = "import importlib\n\nimportlib.import_module('courtlistener')\n"
    assert "courtlistener" in forbidden_imports_in(_write_probe(tmp_path, source))


def test_git_subprocess_near_neighbor_is_allowed(tmp_path: Path) -> None:
    assert bd_execution_argvs(_write_probe(tmp_path, _PERMITTED_GIT)) == ()


def test_seeded_bd_execution_is_rejected(tmp_path: Path) -> None:
    found = bd_execution_argvs(_write_probe(tmp_path, _FORBIDDEN_BD))
    assert found == (("bd", "show", "legalforecastbench-xvg1"),)


def test_approval_reference_string_is_not_prose_lookup(tmp_path: Path) -> None:
    assert (
        approval_prose_lookups(_write_probe(tmp_path, _PERMITTED_APPROVAL_REFERENCE))
        == ()
    )


def test_seeded_owner_prose_lookup_is_rejected(tmp_path: Path) -> None:
    found = approval_prose_lookups(_write_probe(tmp_path, _FORBIDDEN_OWNER_PROSE))
    assert "load_approval_prose" in found
    assert "owner-prose.md" in found


def test_seeded_bd_comment_lookup_is_rejected(tmp_path: Path) -> None:
    found = approval_prose_lookups(_write_probe(tmp_path, _FORBIDDEN_BD_COMMENTS))
    assert "bd comments" in found


def test_forecast_workflow_allows_locked_manifest_inputs() -> None:
    assert retired_dispatch_inputs(_PERMITTED_FORECAST_WORKFLOW, role="forecast") == ()


def test_fan_in_workflow_may_accept_labels_release_uri() -> None:
    assert retired_dispatch_inputs(_PERMITTED_FAN_IN_WORKFLOW, role="fan-in") == ()
    assert retired_dispatch_inputs(_PERMITTED_FAN_IN_WORKFLOW, role="forecast") == (
        "labels_release_uri",
    )


def test_seeded_retired_forecast_inputs_are_rejected() -> None:
    assert retired_dispatch_inputs(_FORBIDDEN_FORECAST_WORKFLOW, role="forecast") == (
        "labels_uri",
        "run_input_manifest_uri",
    )


def test_retired_official_workflows_are_absent() -> None:
    workflow_root = ROOT / ".github" / "workflows"
    present = [
        name
        for name in sorted(RETIRED_OFFICIAL_WORKFLOWS)
        if (workflow_root / name).is_file()
    ]
    assert present == []


def test_seeded_retired_workflow_file_is_detected(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "official-paid-labeling.yaml").write_text(
        "name: retired\n", encoding="utf-8"
    )
    (workflows / "run-benchmark.yaml").write_text(
        _PERMITTED_FORECAST_WORKFLOW, encoding="utf-8"
    )
    found = scan_public_boundary(tmp_path)
    assert any("official-paid-labeling.yaml" in item for item in found)
    assert not any("run-benchmark.yaml accepts retired input" in item for item in found)


def test_operator_help_covers_manifest_run_score_and_report() -> None:
    captured = invoke_cli(("--help",))
    assert captured.exit_status == 0
    for command in OPERATOR_COMMANDS:
        assert command in captured.stdout
    assert private_runtime_help_violations(captured.stdout) == ()


@pytest.mark.parametrize(
    ("argv", "needle"),
    (
        (("manifest", "validate"), "Canonical locked benchmark-run manifest JSON"),
        (("run",), "issue-fixture"),
        (("score",), "labels-release.json"),
        (("report",), "--run-manifest MANIFEST"),
    ),
)
def test_operator_command_help_stays_concise(
    argv: tuple[str, ...], needle: str
) -> None:
    captured = invoke_cli((*argv, "--help"))
    assert captured.exit_status == 0
    assert needle in captured.stdout
    assert private_runtime_help_violations(captured.stdout) == ()


def test_seeded_private_runtime_help_is_rejected() -> None:
    help_text = (
        "usage: legalforecast acquisition run-cycle\n"
        "Fetch PACER dockets through CourtListener and execute bd comments.\n"
    )
    found = private_runtime_help_violations(help_text)
    assert "acquisition" in {token.lower() for token in found}
    assert "pacer" in {token.lower() for token in found}
    assert "courtlistener" in {token.lower() for token in found}
    assert "bd" in {token.lower() for token in found}
