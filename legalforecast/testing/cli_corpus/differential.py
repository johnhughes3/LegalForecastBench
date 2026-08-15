"""Provider-free CLI differential cases with exact bytes and output trees."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from legalforecast.testing.cli_corpus.invoke import invoke_cli
from legalforecast.testing.cli_corpus.paths import (
    DIFFERENTIAL_DIR,
    DIFFERENTIAL_SCHEMA_VERSION,
    as_object_dict,
    dump_json,
    load_json,
)

_FORBIDDEN_TOKENS = frozenset(
    {
        "--live",
        "dispatch",
        "finalize-corpus",
        "purchase",
    }
)
_SKIP_EXACT_SUFFIXES = frozenset({".sqlite", ".db", ".sqlite3"})
WorkspaceSetup = Callable[[Path], None]


@dataclass(frozen=True, slots=True)
class DifferentialCase:
    """One provider-free CLI characterization case."""

    case_id: str
    argv_template: tuple[str, ...]
    expected_exit: int
    setup: str
    resume: bool = False


CASES: tuple[DifferentialCase, ...] = (
    DifferentialCase("root-help", ("--help",), 0, "empty"),
    DifferentialCase("version", ("--version",), 0, "empty"),
    DifferentialCase(
        "unknown-command",
        ("definitely-not-a-command",),
        2,
        "empty",
    ),
    DifferentialCase("freeze-help", ("freeze", "--help"), 0, "empty"),
    DifferentialCase(
        "publish-aggregate-help",
        ("publish", "aggregate", "--help"),
        0,
        "empty",
    ),
    DifferentialCase(
        "discover-dry-run",
        (
            "discover",
            "--input",
            "{workspace}/input.jsonl",
            "--output",
            "{workspace}/output.jsonl",
            "--dry-run",
        ),
        0,
        "empty-jsonl",
        resume=True,
    ),
    DifferentialCase(
        "score-dry-run",
        (
            "score",
            "--runs",
            "{workspace}/runs.jsonl",
            "--labels",
            "{workspace}/labels.jsonl",
            "--output",
            "{workspace}/scores.json",
            "--dry-run",
        ),
        0,
        "score-inputs",
        resume=True,
    ),
)


@dataclass(frozen=True, slots=True)
class DifferentialResult:
    """Normalized observation for one case, suitable for exact-byte compare."""

    case_id: str
    exit_status: int
    stdout: str
    stderr: str
    output_tree: tuple[str, ...]
    artifacts: dict[str, str]
    extra_files: tuple[str, ...]


def validate_case_argv(argv: Sequence[str]) -> None:
    """Refuse corpus cases that could purchase, freeze, dispatch, or go live."""

    tokens = set(argv)
    forbidden = sorted(tokens & _FORBIDDEN_TOKENS)
    if forbidden:
        raise ValueError(f"differential case uses forbidden tokens: {forbidden}")
    if "freeze" in tokens and "--help" not in tokens:
        raise ValueError("freeze is only allowed as a help bypass in this corpus")
    if argv[:2] == ("publish", "aggregate") and "--help" not in tokens:
        raise ValueError("publish aggregate is only allowed as a help bypass")


def run_case(case: DifferentialCase, workspace: Path) -> DifferentialResult:
    """Execute one case against ``workspace`` and normalize durable outputs."""

    validate_case_argv(case.argv_template)
    _setup(case.setup, workspace)
    argv = _render_argv(case.argv_template, workspace)
    before = _relative_files(workspace)
    captured = invoke_cli(argv)
    after_first = _relative_files(workspace)
    extra: set[str] = set()
    if case.resume:
        captured = invoke_cli(argv)
        extra = _relative_files(workspace) - after_first
    created = tuple(sorted(after_first - before))
    expected_created = tuple(path for path in created if not _is_skipped_artifact(path))
    return DifferentialResult(
        case_id=case.case_id,
        exit_status=captured.exit_status,
        stdout=_normalize_text(captured.stdout, workspace),
        stderr=_normalize_text(captured.stderr, workspace),
        output_tree=expected_created,
        artifacts=_artifact_payload(workspace, expected_created),
        extra_files=tuple(sorted(extra)),
    )


def result_payload(result: DifferentialResult) -> dict[str, object]:
    """JSON object stored as the reviewed fixture for one case."""

    return {
        "artifacts": result.artifacts,
        "case_id": result.case_id,
        "exit_status": result.exit_status,
        "extra_files": list(result.extra_files),
        "output_tree": list(result.output_tree),
        "stderr": result.stderr,
        "stdout": result.stdout,
    }


def write_differential_fixtures(root: Path, workspace: Path) -> None:
    """Run the corpus and write exact-byte fixtures."""

    directory = root / DIFFERENTIAL_DIR
    directory.mkdir(parents=True, exist_ok=True)
    index = {
        "schema_version": DIFFERENTIAL_SCHEMA_VERSION,
        "cases": [case.case_id for case in CASES],
    }
    dump_json(directory / "cases.json", index)
    for case in CASES:
        case_dir = workspace / case.case_id
        case_dir.mkdir()
        result = run_case(case, case_dir)
        if result.exit_status != case.expected_exit:
            raise RuntimeError(
                f"{case.case_id} exited {result.exit_status}, "
                f"expected {case.expected_exit}"
            )
        dump_json(directory / f"{case.case_id}.json", result_payload(result))


def load_differential_fixture(root: Path, case_id: str) -> dict[str, object]:
    """Load one reviewed differential fixture."""

    payload = load_json(root / DIFFERENTIAL_DIR / f"{case_id}.json")
    return as_object_dict(payload)


def compare_result(
    observed: DifferentialResult, expected: Mapping[str, object]
) -> tuple[str, ...]:
    """Return violations between a live result and its reviewed fixture."""

    violations: list[str] = []
    payload = result_payload(observed)
    for field in (
        "exit_status",
        "stdout",
        "stderr",
        "output_tree",
        "artifacts",
        "extra_files",
    ):
        if payload[field] != expected.get(field):
            violations.append(f"{observed.case_id}.{field} mismatch")
    return tuple(violations)


def _setup(kind: str, workspace: Path) -> None:
    if kind == "empty":
        return
    if kind == "empty-jsonl":
        (workspace / "input.jsonl").write_text("", encoding="utf-8")
        return
    if kind == "score-inputs":
        (workspace / "runs.jsonl").write_text("", encoding="utf-8")
        (workspace / "labels.jsonl").write_text("", encoding="utf-8")
        return
    raise ValueError(f"unknown differential setup {kind}")


def _render_argv(template: Sequence[str], workspace: Path) -> list[str]:
    rendered = [part.replace("{workspace}", str(workspace)) for part in template]
    return rendered


def _relative_files(workspace: Path) -> set[str]:
    files: set[str] = set()
    for path in workspace.rglob("*"):
        if path.is_file():
            files.add(path.relative_to(workspace).as_posix())
    return files


def _is_skipped_artifact(relative: str) -> bool:
    return Path(relative).suffix in _SKIP_EXACT_SUFFIXES


def _artifact_payload(workspace: Path, relative_paths: Sequence[str]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for relative in relative_paths:
        path = workspace / relative
        text = _normalize_text(path.read_text(encoding="utf-8"), workspace)
        artifacts[relative] = text
        artifacts[f"{relative}.sha256"] = hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
    return artifacts


def _normalize_text(text: str, workspace: Path) -> str:
    return text.replace(str(workspace), "{workspace}")
