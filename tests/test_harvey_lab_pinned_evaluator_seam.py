from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pytest
from legalforecast.multiharness.deliverable_text import (
    DeliverableTextError,
    deliverable_visible_text,
    xlsx_visible_text,
)
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "harvey_lab"
    / "pinned-evaluator-seam-73feb91.json"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _xlsx_bytes(*, empty: bool = False) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Compliance\nTracker"
    if not empty:
        sheet.append(("Requirement", "Amount", "Complete"))
        sheet.append(("File\treport", 1250, False))
        sheet["D2"] = "=B2*2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _rewrite_xlsx_part(payload: bytes, name: str, body: bytes) -> bytes:
    target = io.BytesIO()
    found = False
    with (
        zipfile.ZipFile(io.BytesIO(payload)) as source,
        zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as destination,
    ):
        for info in source.infolist():
            content = source.read(info)
            if info.filename == name:
                content = body
                found = True
            destination.writestr(info, content)
        if not found:
            destination.writestr(name, body)
    return target.getvalue()


def test_xlsx_visible_text_preserves_sheet_cells_and_formulas() -> None:
    assert xlsx_visible_text(_xlsx_bytes()) == (
        "=== Sheet: Compliance\\nTracker ===\n"
        "A1=Requirement\tB1=Amount\tC1=Complete\n"
        "A2=File\\treport\tB2=1250\tC2=FALSE\tD2==B2*2"
    )


def test_xlsx_visible_text_refuses_empty_workbook() -> None:
    with pytest.raises(DeliverableTextError, match="no extractable cell values"):
        xlsx_visible_text(_xlsx_bytes(empty=True))


def test_xlsx_visible_text_refuses_oversized_sheet_dimensions() -> None:
    with pytest.raises(DeliverableTextError, match="too many cell slots"):
        xlsx_visible_text(_xlsx_bytes(), max_cell_slots=3)


def test_xlsx_preflight_refuses_too_many_package_members() -> None:
    with pytest.raises(DeliverableTextError, match="too many package members"):
        xlsx_visible_text(_xlsx_bytes(), max_package_members=1)


def test_xlsx_preflight_refuses_compressed_oversized_package_part() -> None:
    payload = _rewrite_xlsx_part(_xlsx_bytes(), "xl/sharedStrings.xml", b"x" * 10_000)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        planted = archive.getinfo("xl/sharedStrings.xml")
        assert planted.compress_size < planted.file_size
    with pytest.raises(DeliverableTextError, match="package part is too large"):
        xlsx_visible_text(payload, max_package_part_bytes=1_000)


def test_xlsx_preflight_refuses_underreported_worksheet_dimension() -> None:
    payload = _xlsx_bytes()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        worksheet = archive.read("xl/worksheets/sheet1.xml")
    planted = re.sub(
        rb'<dimension ref="[^"]+"\s*/>', b'<dimension ref="A1:A1"/>', worksheet
    )
    assert planted != worksheet
    payload = _rewrite_xlsx_part(payload, "xl/worksheets/sheet1.xml", planted)

    with pytest.raises(DeliverableTextError, match="under-reports populated cells"):
        xlsx_visible_text(payload)


def test_xlsx_visible_text_renders_array_and_data_table_formulas() -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet["A1"] = ArrayFormula("A1:A1", "=SUM(B1:B2)")
    sheet["A2"] = DataTableFormula("A2:B3", ca=True, dt2D=True, r1="C1", r2="C2")
    buffer = io.BytesIO()
    workbook.save(buffer)

    rendered = xlsx_visible_text(buffer.getvalue())
    assert "A1=ARRAY_FORMULA(ref=A1:A1,text==SUM(B1:B2))" in rendered
    assert "A2=DATA_TABLE_FORMULA(ref=A2:B3" in rendered


def test_xlsx_dispatch_refuses_docx_bytes_renamed_as_xlsx() -> None:
    with pytest.raises(DeliverableTextError, match="SpreadsheetML"):
        deliverable_visible_text(
            b"PK\x03\x04not-a-spreadsheet", basename="misnamed.xlsx"
        )


def test_deliverable_dispatch_refuses_unknown_suffix() -> None:
    with pytest.raises(DeliverableTextError, match="unsupported suffix"):
        deliverable_visible_text(b"payload", basename="tracker.xls")


EXTERNAL_EVALUATION_PROBE = r"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import evaluation.run_eval as run_eval

task = "employment-labor/identify-issues-in-counterparty-motion-brief"
source = Path("tasks") / task / "documents" / "briggs-declaration.docx"
expected = "issue-identification-memo.docx"


class StubJudge:
    model = "no-credential-stub"

    def __init__(self) -> None:
        self.calls = 0

    def evaluate_from_file(self, *, prompt_name, variables):
        assert prompt_name == "rubric_criterion"
        assert variables["agent_output"]
        self.calls += 1
        return {"verdict": "pass", "reasoning": "seam probe"}


with tempfile.TemporaryDirectory(prefix="harvey-lab-external-eval-") as raw:
    results_dir = Path(raw) / "results"
    run_id = "external-sealed-deliverable"
    output_dir = results_dir / run_id / "output"
    output_dir.mkdir(parents=True)
    target = output_dir / expected
    shutil.copy2(source, target)
    run_eval.RESULTS_DIR = results_dir
    judge = StubJudge()
    scores = run_eval.evaluate_run(run_id, task, judge, parallel=1)
    print(json.dumps({
        "ambient_env_files": sorted(path.name for path in Path.cwd().glob(".env*")),
        "config_present": (results_dir / run_id / "config.json").exists(),
        "criteria_evaluated": judge.calls,
        "entrypoint": "evaluation.run_eval.evaluate_run",
        "judge": "deterministic local stub",
        "metrics_present": (results_dir / run_id / "metrics.json").exists(),
        "provider_environment_names": sorted(
            name for name in os.environ
            if name.endswith("_API_KEY") or "TOKEN" in name
        ),
        "score": scores["score"],
        "scores_written": (results_dir / run_id / "scores.json").exists(),
        "source_hash_equal_to_overlay_hash": (
            hashlib.sha256(source.read_bytes()).hexdigest()
            == hashlib.sha256(target.read_bytes()).hexdigest()
        ),
        "transcript_present": (results_dir / run_id / "transcript.jsonl").exists(),
    }, sort_keys=True))
"""


def test_pinned_harvey_lab_evaluator_seam_records_required_boundaries() -> None:
    fixture = _load_fixture()

    assert fixture["schema_version"] == (
        "legalforecast.harvey_lab_evaluator_characterization.v1"
    )
    upstream = fixture["upstream"]
    assert upstream["commit"] == "73feb91d63d53b1a44151d99329779c4defcdb72"
    assert upstream["tree"] == "944913ee8cdeaef4930a106e5e16d74aa93a29d7"
    assert upstream["tags_at_commit"] == []
    assert upstream["license"]["spdx"] == "MIT"
    assert SHA256_RE.fullmatch(upstream["license"]["sha256"])

    task = fixture["task"]
    assert task["id"] == (
        "employment-labor/identify-issues-in-counterparty-motion-brief"
    )
    assert task["expected_deliverable"] == "issue-identification-memo.docx"
    assert task["criterion_count"] == 23
    assert len(task["solver_visible"]["documents"]) == 8
    assert set(task["solver_visible"]) == {
        "documents",
        "expected_deliverable",
        "instructions",
    }
    assert "criteria" not in json.dumps(task["solver_visible"], sort_keys=True)
    assert "criteria" in task["evaluator_private"]["task_json_fields"]
    assert task["evaluator_private"]["whole_task_json_solver_visible"] is False

    commands = fixture["observed_commands"]
    assert commands["run"]["argv_prefix"] == [
        "uv",
        "run",
        "python",
        "-m",
        "harness.run",
    ]
    assert commands["evaluate"]["argv_prefix"] == [
        "uv",
        "run",
        "python",
        "-m",
        "evaluation.run_eval",
    ]
    for unsupported_flag in ("--lab-root", "--output-dir"):
        assert unsupported_flag not in commands["run"]["observed_flags"]
        assert unsupported_flag not in commands["evaluate"]["observed_flags"]
    assert set(commands["run"]["native_files"]) == {
        "config.json",
        "metrics.json",
        "output/",
        "transcript.jsonl",
        "workspace/",
    }
    assert "exit 2" in commands["run"]["exit_behavior"]
    assert (
        "completed 0.0 task score still exits 0"
        in commands["evaluate"]["exit_behavior"]
    )

    scoring = fixture["evaluation"]["scoring"]
    assert scoring["criterion_verdicts"] == ["pass", "fail"]
    assert scoring["criterion_weights"] is None
    assert scoring["task_score"] == "1.0 iff all criteria pass; otherwise 0.0"
    assert scoring["rounding"] is None
    assert scoring["missing_deliverable"] == (
        "sent to the judge as a file-not-found marker; not an automatic failure"
    )
    judge = fixture["evaluation"]["judge"]
    assert "_load_env" in judge["ambient_env_behavior"]
    assert judge["clean_git_checkout_proves_no_ambient_env"] is False
    assert (
        "reject checkout-root .env and .env* entries"
        in judge["overlay_environment_decision"]
    )
    assert "evaluation.run_eval.evaluate_run" in judge["overlay_environment_decision"]

    overlay = fixture["external_deliverable_evaluation"]
    assert overlay["feasible"] is True
    assert overlay["decision"] == "narrow_native_run_directory_overlay"
    assert overlay["rerun_solver"] is False
    assert overlay["native_output_path"] == (
        "results/<run-id>/output/issue-identification-memo.docx"
    )
    assert overlay["no_credential_probe"] == {
        "ambient_env_files": [],
        "config_present": False,
        "criteria_evaluated": 23,
        "entrypoint": "evaluation.run_eval.evaluate_run",
        "judge": "deterministic local stub",
        "metrics_present": False,
        "provider_environment_names": [],
        "score": 1.0,
        "scores_written": True,
        "source_hash_equal_to_overlay_hash": True,
        "transcript_present": False,
    }

    for file_record in upstream["observed_files"]:
        assert SHA256_RE.fullmatch(file_record["sha256"])
    for document in task["solver_visible"]["documents"]:
        assert SHA256_RE.fullmatch(document["sha256"])
        assert document["size_bytes"] > 0


def test_pinned_harvey_lab_fixture_matches_requested_checkout() -> None:
    raw_root = os.environ.get("HARVEY_LAB_ROOT")
    if raw_root is None:
        pytest.skip("set HARVEY_LAB_ROOT to verify the pinned upstream checkout")

    root = Path(raw_root)
    _assert_pinned_checkout(root)


def _assert_pinned_checkout(root: Path) -> None:
    fixture = _load_fixture()
    assert sorted(path.name for path in root.glob(".env*")) == []
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert commit == fixture["upstream"]["commit"]
    assert tree == fixture["upstream"]["tree"]
    for record in fixture["upstream"]["observed_files"]:
        assert _sha256(root / record["path"]) == record["sha256"]
    assert _sha256(root / "LICENSE") == fixture["upstream"]["license"]["sha256"]
    for record in fixture["task"]["solver_visible"]["documents"]:
        assert _sha256(root / record["path"]) == record["sha256"]


def test_pinned_harvey_lab_external_deliverable_probe(tmp_path: Path) -> None:
    raw_root = os.environ.get("HARVEY_LAB_ROOT")
    if raw_root is None:
        pytest.skip("set HARVEY_LAB_ROOT to replay the pinned evaluator seam")

    root = Path(raw_root)
    _assert_pinned_checkout(root)
    home = tmp_path / "home"
    cache = tmp_path / "cache"
    config = tmp_path / "config"
    for path in (home, cache, config):
        path.mkdir()
    environment = {
        "HOME": str(home),
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ["PATH"],
        "UV_CACHE_DIR": str(cache / "uv"),
        "UV_LINK_MODE": "copy",
        "XDG_CACHE_HOME": str(cache),
        "XDG_CONFIG_HOME": str(config),
    }

    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(root),
            "python",
            "-c",
            EXTERNAL_EVALUATION_PROBE,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=360,
    )
    observed = json.loads(result.stdout)

    assert (
        observed
        == _load_fixture()["external_deliverable_evaluation"]["no_credential_probe"]
    )


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
