"""Import native LegalReasonBench Harbor outputs into the public audit.

Each condition is supplied explicitly: ``--runs-root`` contains directories
named ``gpt6luna-xhigh`` and/or ``opus55-low``, or ``--runs-map`` maps those
slugs to Harbor job directories. The importer never infers model identity.
Missing or incomplete panels are retained as partial, non-failure imports.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard, cast

Json = dict[str, Any]


def _is_object(value: object) -> TypeGuard[Json]:
    return isinstance(value, dict)


def _is_list(value: object) -> TypeGuard[list[Any]]:
    return isinstance(value, list)


AUDIT_DIR = Path("docs/legalreasonbench-audit/litigation")
SOURCE_INDEX = AUDIT_DIR / "source-index.json"
SCOPE_INDEX = AUDIT_DIR / "in-scope.json"
RUNS_DIR = AUDIT_DIR / "model-runs"
DATASET = "micro1-inc/LegalReasonBench"
REVISION = "1bfa904c8f255925baf2610c0f86aa7c05d94ed9"
CONDITIONS = (
    ("gpt6luna-xhigh", "GPT-6 Luna (xhigh)", "openai/gpt-6-luna", "xhigh"),
    (
        "opus55-low",
        "Claude Opus 5.5 (low)",
        "anthropic/claude-opus-5-5",
        "low",
    ),
)
JUDGES = (
    ("openai/gpt-5.6-terra", "GPT-5.6 Terra"),
    ("anthropic/claude-sonnet-5", "Claude Sonnet 5"),
    ("gemini/gemini-3.8-flash", "Gemini 3.8 Flash"),
)
NATIVE_POLARITY = {"positive": "required", "negative": "penalty"}


class NativeRunError(ValueError):
    """A native output cannot be interpreted without guessing."""


class IncompletePanel(NativeRunError):
    """A judge panel is missing, errored, or malformed."""


class CriterionMismatch(NativeRunError):
    """Native criterion names, weights, or polarities differ from the audit."""


def _native_polarity(value: Any) -> str:
    polarity = NATIVE_POLARITY.get(value) if isinstance(value, str) else None
    if polarity is None:
        raise CriterionMismatch(f"unknown native polarity {value!r}")
    return polarity


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    points: float
    polarity: str
    description: str


@dataclass(frozen=True)
class Assignment:
    matter_id: str
    number: int
    criteria: tuple[Criterion, ...]

    @property
    def assignment_id(self) -> str:
        return f"{self.matter_id}-assignment-{self.number}"


def _load(path: Path) -> Json:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeRunError(
            f"could not read JSON {path.name} ({type(exc).__name__})"
        ) from exc
    if not _is_object(value):
        raise NativeRunError(f"JSON object expected in {path.name}")
    return value


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise NativeRunError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise NativeRunError(f"{label} is not finite")
    return result


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise NativeRunError(f"{label} is missing or not a string")
    return value


def load_assignments(
    source_index: Path = SOURCE_INDEX, scope_index: Path | None = SCOPE_INDEX
) -> dict[str, Assignment]:
    """Read the pinned source rubric, selecting in-scope rows when available."""
    source = _load(source_index)
    if source.get("dataset") != DATASET or source.get("revision") != REVISION:
        raise NativeRunError("source-index dataset or revision is not pinned")
    included: set[tuple[str, int]] | None = None
    if scope_index is not None and scope_index.exists():
        scope = _load(scope_index)
        included = set()
        for item in scope.get("tasks", []):
            if _is_object(item) and item.get("in_scope") is True:
                included.add(
                    (
                        _string(item.get("matter_id"), "scope matter_id"),
                        int(item["assignment"]),
                    )
                )
    rows = source.get("rows")
    if not _is_list(rows):
        raise NativeRunError("source-index rows must be a list")
    assignments: dict[str, Assignment] = {}
    for row in rows:
        if not _is_object(row):
            raise NativeRunError("source-index row is not an object")
        matter_id = _string(row.get("matter_id"), "matter_id")
        number = row.get("assignment")
        if isinstance(number, bool) or not isinstance(number, int):
            raise NativeRunError(f"{matter_id}: assignment is not an integer")
        if included is not None and (matter_id, number) not in included:
            continue
        rubric = row.get("rubric")
        if not _is_list(rubric) or not rubric:
            raise NativeRunError(f"{matter_id}-{number}: rubric is empty")
        criteria: list[Criterion] = []
        for item in rubric:
            if not _is_object(item):
                raise NativeRunError(f"{matter_id}-{number}: malformed rubric")
            criterion_id = _string(item.get("criterion_id"), "criterion_id")
            points = _number(item.get("points"), f"{criterion_id}.points")
            polarity = _string(item.get("polarity"), f"{criterion_id}.polarity")
            if polarity not in {"required", "penalty"} or (polarity == "penalty") != (
                points < 0
            ):
                raise NativeRunError(f"{criterion_id}: points/polarity mismatch")
            criteria.append(
                Criterion(
                    criterion_id, points, polarity, str(item.get("criterion", ""))
                )
            )
        assignment = Assignment(matter_id, number, tuple(criteria))
        if assignment.assignment_id in assignments:
            raise NativeRunError(f"duplicate assignment {assignment.assignment_id}")
        assignments[assignment.assignment_id] = assignment
    if not assignments:
        raise NativeRunError("source-index selected no assignments")
    return assignments


def _criteria(details: Json) -> list[Json]:
    correctness = details.get("correctness")
    items = correctness.get("criteria") if _is_object(correctness) else None
    if not _is_list(items) or not all(_is_object(item) for item in items):
        raise IncompletePanel("reward-details has no valid correctness.criteria list")
    return cast(list[Json], items)


def _binary(value: Any, label: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float) and math.isfinite(value) and value in {0, 1}:
        return int(value)
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"yes", "true", "1"}:
            return 1
        if value in {"no", "false", "0"}:
            return 0
    raise IncompletePanel(f"{label} is not binary")


def _negate(details: Json, criterion_id: str, item: Json) -> bool | None:
    if isinstance(item.get("negate"), bool):
        return item["negate"]
    correctness = details.get("correctness")
    raw = correctness.get("raw_rewardkit") if _is_object(correctness) else None
    found: list[bool] = []

    def visit(value: Any) -> None:
        if _is_list(value):
            for child in value:
                visit(child)
        elif _is_object(value):
            if value.get("name") == criterion_id and isinstance(
                value.get("negate"), bool
            ):
                found.append(value["negate"])
            for child in value.values():
                visit(child)

    visit(raw)
    if len(set(found)) > 1:
        raise CriterionMismatch(f"{criterion_id}: native negate flags disagree")
    return found[0] if found else None


def validate_panel(
    details: Json, assignment: Assignment, reward: Json | None = None
) -> tuple[Json, ...]:
    """Strictly validate a complete native three-judge panel."""
    items = _criteria(details)
    correctness = details["correctness"]
    score = _number(correctness.get("score"), "details.correctness.score")
    if reward is not None and not math.isclose(
        score, _number(reward.get("correctness"), "reward.correctness")
    ):
        raise CriterionMismatch("reward and reward-details scores differ")
    expected = {criterion.criterion_id: criterion for criterion in assignment.criteria}
    names = [str(item.get("name")) for item in items]
    if len(names) != len(set(names)) or set(names) != set(expected):
        raise CriterionMismatch(
            f"{assignment.assignment_id}: criterion membership mismatch"
        )
    expected_judges = {model for model, _label in JUDGES}
    for item in items:
        criterion_id = str(item["name"])
        criterion = expected[criterion_id]
        polarity = _native_polarity(item.get("polarity"))
        if polarity != criterion.polarity:
            raise CriterionMismatch(f"{criterion_id}: polarity mismatch")
        if _number(item.get("weight"), "weight") != criterion.points:
            raise CriterionMismatch(f"{criterion_id}: weight mismatch")
        if _number(item.get("signed_score"), "signed_score") != criterion.points:
            raise CriterionMismatch(f"{criterion_id}: signed_score mismatch")
        value = _number(item.get("value"), "value")
        contribution = _number(item.get("contribution"), "contribution")
        if value not in {0, 1} or not math.isclose(
            contribution, value * criterion.points
        ):
            raise CriterionMismatch(f"{criterion_id}: contribution mismatch")
        if "raw" not in item:
            raise IncompletePanel(f"{criterion_id}: raw score is missing")
        raw = _binary(item["raw"], f"{criterion_id}.raw")
        negate = _negate(details, criterion_id, item)
        if negate is not None:
            expected_raw = int(1 - value) if negate else int(value)
            if raw != expected_raw:
                raise CriterionMismatch(f"{criterion_id}: raw/value mismatch")
        votes = item.get("votes")
        if not _is_list(votes) or len(votes) != 3:
            raise IncompletePanel(f"{criterion_id}: expected three judge votes")
        seen: set[str] = set()
        vote_values: list[int] = []
        for vote in votes:
            if not _is_object(vote) or not _is_object(vote.get("judge")):
                raise IncompletePanel(f"{criterion_id}: malformed judge vote")
            judge = vote["judge"]
            model = judge.get("model")
            if model not in expected_judges or model in seen:
                raise IncompletePanel(f"{criterion_id}: judge membership mismatch")
            if judge.get("reasoning_effort") != "medium":
                raise IncompletePanel(f"{criterion_id}: judge effort mismatch")
            if vote.get("error") or vote.get("judge_error"):
                raise IncompletePanel(f"{criterion_id}: judge returned an error")
            if vote.get("name") != criterion_id or "raw" not in vote:
                raise CriterionMismatch(f"{criterion_id}: vote fields mismatch")
            if (
                not isinstance(vote.get("reasoning"), str)
                or not vote["reasoning"].strip()
            ):
                raise IncompletePanel(f"{criterion_id}: judge reasoning is missing")
            vote_value = _number(vote.get("value"), "vote.value")
            if vote_value not in {0, 1}:
                raise IncompletePanel(f"{criterion_id}: malformed binary vote")
            vote_raw = _binary(vote["raw"], f"{criterion_id}.vote.raw")
            if negate is not None:
                expected_vote_raw = int(1 - vote_value) if negate else int(vote_value)
                if vote_raw != expected_vote_raw:
                    raise CriterionMismatch(f"{criterion_id}: vote raw/value mismatch")
            vote_values.append(int(vote_value))
            seen.add(str(model))
        if seen != expected_judges:
            raise IncompletePanel(f"{criterion_id}: judge membership mismatch")
        if int(value) != int(sum(vote_values) >= 2):
            raise CriterionMismatch(f"{criterion_id}: majority value mismatch")
    aggregation = correctness.get("aggregation")
    if not _is_object(aggregation):
        raise IncompletePanel("reward-details correctness.aggregation is missing")
    if aggregation.get("method") != "signed_score_ratio_clamped":
        raise CriterionMismatch("unexpected correctness aggregation method")
    earned = sum(_number(item.get("contribution"), "contribution") for item in items)
    positive_total = sum(
        criterion.points for criterion in assignment.criteria if criterion.points > 0
    )
    unclamped = earned / positive_total
    clamped = max(0.0, min(1.0, unclamped))
    if (
        not math.isclose(
            _number(aggregation.get("earned"), "aggregation.earned"), earned
        )
        or not math.isclose(
            _number(aggregation.get("positive_total"), "aggregation.positive_total"),
            positive_total,
        )
        or not math.isclose(
            _number(aggregation.get("unclamped"), "aggregation.unclamped"), unclamped
        )
        or not math.isclose(
            _number(aggregation.get("clamped"), "aggregation.clamped"), clamped
        )
        or not math.isclose(score, clamped)
    ):
        raise CriterionMismatch("aggregation score mismatch")
    return tuple(items)


def _find_trial(root: Path, assignment: Assignment) -> Path | None:
    matches: list[Path] = []
    result_files = list(root.rglob("result.json")) if root.is_dir() else []
    if (root / "result.json").is_file():
        result_files.append(root / "result.json")
    for result_file in sorted(set(result_files)):
        trial = result_file.parent
        try:
            result = _load(trial / "result.json")
        except NativeRunError:
            continue
        task_name = result.get("task_name")
        step = trial / "steps" / f"assignment-{assignment.number}"
        if (
            isinstance(task_name, str)
            and task_name.rsplit("/", 1)[-1] == assignment.matter_id
            and step.is_dir()
        ):
            matches.append(trial)
    if len(matches) > 1:
        raise NativeRunError(
            f"{assignment.assignment_id}: multiple Harbor trials found"
        )
    return matches[0] if matches else None


def _answer_path(step: Path) -> Path | None:
    paths = [step / "verifier" / "answer.md", step / "artifacts" / "answer.md"]
    present = [path for path in paths if path.is_file()]
    if len(present) == 2 and present[0].read_bytes() != present[1].read_bytes():
        raise NativeRunError("conflicting verifier and artifact answer.md files")
    return present[0] if present else None


def _validate_identity(trial: Path, condition: str) -> Json:
    expected = next((item for item in CONDITIONS if item[0] == condition), None)
    if expected is None:
        raise NativeRunError(f"unknown condition {condition}")
    _slug, _label, expected_model, expected_variant = expected
    config = _load(trial / "config.json")
    agent = config.get("agent")
    if not _is_object(agent) or agent.get("model_name") != expected_model:
        raise NativeRunError(
            "Harbor config model identity is unavailable or mismatched"
        )
    kwargs = agent.get("kwargs")
    if not _is_object(kwargs) or kwargs.get("variant") != expected_variant:
        raise NativeRunError("Harbor config model variant is unavailable or mismatched")
    result = _load(trial / "result.json")
    model_info = result.get("agent_info", {}).get("model_info")
    observed = (
        f"{model_info.get('provider')}/{model_info.get('name')}"
        if _is_object(model_info)
        else None
    )
    if observed != expected_model:
        raise NativeRunError(
            "Harbor result model identity is unavailable or mismatched"
        )
    return result


def _agent_exception(result: Json, assignment: Assignment) -> str | None:
    """Expose the exception type without publishing commands or private logs."""
    steps = result.get("step_results", [])
    if not _is_list(steps):
        return None
    for step in steps:
        if (
            not _is_object(step)
            or step.get("step_name") != f"assignment-{assignment.number}"
        ):
            continue
        exception = step.get("exception_info")
        if _is_object(exception):
            name = exception.get("exception_type")
            return str(name) if name else "native agent exception"
    return None


def read_native_run(trial: Path, assignment: Assignment, condition: str) -> Json:
    """Read one native trial; incomplete grading is not a model failure."""
    if condition not in {item[0] for item in CONDITIONS}:
        raise NativeRunError(f"unknown condition {condition}")
    # Identity is an import boundary: never publish another model's answer or
    # grades under the requested condition, even as an incomplete panel.
    result = _validate_identity(trial, condition)
    step = trial / "steps" / f"assignment-{assignment.number}"
    response: Path | None = None
    reward_path = step / "verifier" / "reward.json"
    details_path = step / "verifier" / "reward-details.json"
    reward: Json | None = None
    details: Json | None = None
    status, error = "answer-only", None
    try:
        response = _answer_path(step)
        if reward_path.is_file():
            reward = _load(reward_path)
        if details_path.is_file():
            details = _load(details_path)
        if response is None:
            status, error = "incomplete", "verifier answer.md is missing"
        elif reward is None and details is None:
            status = "answer-only"
        elif reward is None or details is None:
            status, error = (
                "incomplete",
                "reward.json and reward-details.json must both exist",
            )
        else:
            correctness = _number(reward.get("correctness"), "reward.correctness")
            if not 0 <= correctness <= 1:
                raise NativeRunError("reward.correctness is outside [0, 1]")
            validate_panel(details, assignment, reward)
            status = "complete"
    except NativeRunError as exc:
        status, error = "incomplete", str(exc)
    return {
        "assignment": assignment,
        "condition": condition,
        "trial": trial,
        "step": step,
        "response_path": response,
        "reward_path": reward_path if reward_path.is_file() else None,
        "details_path": details_path if details_path.is_file() else None,
        "reward": reward,
        "details": details,
        "status": status,
        "error": error,
        "agent_exception": _agent_exception(result, assignment),
    }


def read_run(assignment_id: str, condition: str, root: Path = RUNS_DIR) -> Json:
    """Read a published run for worksheet consumers."""
    path = root / assignment_id / condition
    result: Json = {
        "path": path,
        "response": None,
        "reward": None,
        "reward_details": None,
        "complete": False,
    }
    response = path / "response.md"
    if response.is_file():
        result["response"] = response.read_bytes()
    for key, filename in (
        ("reward", "reward.json"),
        ("reward_details", "reward-details.json"),
    ):
        file = path / filename
        if file.is_file():
            try:
                result[key] = _load(file)
            except NativeRunError as exc:
                result["error"] = str(exc)
    if _is_object(result["reward"]) and _is_object(result["reward_details"]):
        try:
            assignment = load_assignments().get(assignment_id)
            if assignment is not None:
                validate_panel(result["reward_details"], assignment, result["reward"])
                result["complete"] = True
        except NativeRunError as exc:
            result["error"] = str(exc)
    return result


def _majority(item: Json) -> tuple[bool, int]:
    votes = item.get("votes", [])
    values = [int(bool(vote.get("value"))) for vote in votes if _is_object(vote)]
    return len(values) == 3 and sum(values) >= 2, sum(values)


def _label(criterion: Criterion, item: Json) -> str:
    majority, count = _majority(item)
    if criterion.polarity == "penalty":
        return (
            f"**PENALTY TRIGGERED** ({count}/3)"
            if majority
            else f"penalty clear ({count}/3)"
        )
    return f"met ({count}/3)" if majority else f"not met ({count}/3)"


def _published_item(published: Json, criterion: str) -> Json | None:
    details = published.get("reward_details")
    correctness = details.get("correctness") if _is_object(details) else None
    items: list[Any] = (
        correctness.get("criteria", []) if _is_object(correctness) else []
    )
    return next(
        (item for item in items if _is_object(item) and item.get("name") == criterion),
        None,
    )


def _descriptor(criterion: str, item: Json) -> Criterion:
    return Criterion(
        criterion,
        _number(item.get("signed_score", item.get("weight")), "signed_score"),
        _native_polarity(item.get("polarity")),
        "",
    )


def run_grades(
    task: str, criterion: str, relative_prefix: str, root: Path = RUNS_DIR
) -> str:
    """Return compact linked condition grades for a worksheet row."""
    cells: list[str] = []
    for slug, label, _model, _effort in CONDITIONS:
        published = read_run(task, slug, root)
        if not published["complete"]:
            continue
        item = _published_item(published, criterion)
        if not _is_object(item):
            continue
        try:
            label_text = _label(_descriptor(criterion, item), item)
        except NativeRunError:
            continue
        link = (
            f"{relative_prefix}model-runs/{task}/{slug}/README.md#{criterion.lower()}"
        )
        cells.append(f"{label.split(' (', 1)[0]} [{label_text}]({link})")
    return " · ".join(cells) or "—"


def _inline(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def run_block(
    task: str, criterion: str, relative_prefix: str, root: Path = RUNS_DIR
) -> str:
    """Return the collapsed worksheet block, or empty when no run is published."""
    condition_blocks: list[str] = []
    for slug, label, _model, _effort in CONDITIONS:
        published = read_run(task, slug, root)
        path: Path = published["path"]
        if not path.is_dir() or not any(
            (path / filename).is_file()
            for filename in ("response.md", "reward.json", "reward-details.json")
        ):
            continue
        links = [
            f"[{name}]({relative_prefix}model-runs/{task}/{slug}/{filename})"
            for name, filename in (
                ("run record", "README.md"),
                ("answer", "response.md"),
                ("reward", "reward.json"),
                ("details", "reward-details.json"),
            )
            if (path / filename).is_file()
        ]
        item = _published_item(published, criterion)
        lines = [f"### {label}", ""]
        if not _is_object(item) or not published["complete"]:
            lines.append(
                "Grade panel unavailable or incomplete; this is not a model failure."
            )
        else:
            try:
                descriptor = _descriptor(criterion, item)
                votes = item.get("votes")
                majority = (
                    _label(descriptor, item)
                    if _is_list(votes) and len(votes) == 3
                    else "grade panel incomplete"
                )
                contribution = _number(item.get("contribution"), "contribution")
                lines.append(
                    f"**Status:** {majority}. **Contribution:** `{contribution:g}`."
                )
            except NativeRunError:
                lines.append("Grade panel incomplete; this is not a model failure.")
            votes = item.get("votes")
            if _is_list(votes):
                for vote in votes:
                    if not _is_object(vote):
                        continue
                    judge = vote.get("judge", {})
                    model = judge.get("model") if _is_object(judge) else "unknown judge"
                    detail = (
                        vote.get("reasoning")
                        or vote.get("error")
                        or "reasoning unavailable"
                    )
                    lines.append(
                        f"- `{_inline(model)}`: value `{_inline(vote.get('value'))}` — "
                        f"{_inline(detail)}"
                    )
        if links:
            lines += ["", "Links: " + " · ".join(links) + "."]
        condition_blocks.append("\n".join(lines))
    if not condition_blocks:
        return ""
    return "\n".join(
        [
            "<details>",
            "<summary>Native LegalReasonBench model-run grades</summary>",
            "",
            *condition_blocks,
            "",
            "</details>",
        ]
    )


def _copy(source: Path | None, destination: Path, *, write: bool = True) -> None:
    if source is None:
        if destination.exists():
            raise NativeRunError(
                f"refusing to leave stale generated file {destination}"
            )
        return
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != source.read_bytes():
            raise NativeRunError(f"refusing to overwrite existing file {destination}")
        return
    if not write:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _readme(run: Json) -> str:
    assignment: Assignment = run["assignment"]
    response = run["response_path"]
    reward_path = run["reward_path"]
    details_path = run["details_path"]
    lines = [
        f"# {assignment.assignment_id}: {run['condition']}",
        "",
        f"Dataset: `{DATASET}` at revision `{REVISION}`.",
        "",
        "The response is a byte-preserved native Harbor output; it was not edited "
        "or corrected.",
        "",
        "[Response](response.md)" if response else "Response is unavailable.",
        "",
        "Raw verifier files: "
        + ", ".join(
            [
                "[reward.json](reward.json)"
                if reward_path
                else "reward.json unavailable",
                "[reward-details.json](reward-details.json)"
                if details_path
                else "reward-details.json unavailable",
            ]
        )
        + ".",
        "",
    ]
    if run.get("agent_exception"):
        lines += [
            f"**Native agent diagnostic:** `{run['agent_exception']}`. "
            "The saved response and native grading files are retained unchanged. "
            "A complete grade panel does not imply a clean agent exit.",
            "",
        ]
    if run["status"] != "complete":
        lines += [
            f"**Grade panel:** {run['status']}; no criterion failure is assigned.",
            "",
            run["error"] or "The native panel was not present.",
            "",
            "The answer is retained for partial-import accounting; "
            "the overview does not count this as a complete graded assignment.",
        ]
        return "\n".join(lines)
    details: Json = run["details"]
    items = {item["name"]: item for item in validate_panel(details, assignment)}
    score = details["correctness"]["score"]
    lines += [
        f"**Grade panel:** complete three-judge panel. Native correctness: `{score}`.",
        "",
        "| Criterion | Points | Polarity | Majority | Contribution |",
        "|---|---:|---|---|---:|",
    ]
    for criterion in assignment.criteria:
        item = items[criterion.criterion_id]
        contribution = _number(item["contribution"], "contribution")
        lines.append(
            f"| [{criterion.criterion_id}](#{criterion.criterion_id.lower()}) | "
            f"{criterion.points:g} | {criterion.polarity} | "
            f"{_label(criterion, item)} | "
            f"{contribution:g} |"
        )
    lines += ["", "## Criterion reasoning", ""]
    for criterion in assignment.criteria:
        item = items[criterion.criterion_id]
        lines += [
            f"### {criterion.criterion_id}",
            "",
            "**Audited rubric:** "
            f"{criterion.description or '(description unavailable)'}",
            "",
            f"**Majority:** {_label(criterion, item)}. "
            f"**Contribution:** `{item['contribution']}`.",
            "",
            "| Judge | Value | Raw | Reasoning |",
            "|---|---:|---|---|",
        ]
        for vote in item["votes"]:
            judge = vote["judge"]
            reasoning = str(vote["reasoning"]).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| `{judge['model']}` (medium) | {vote['value']} | {vote['raw']} | "
                f"{reasoning} |"
            )
        lines += [
            "",
            "[Source-index rubric](../../../source-index.json#"
            f"{criterion.criterion_id})",
            "",
        ]
    return "\n".join(lines)


def _sources(root: Path | None, mapping_path: Path | None) -> dict[str, Path]:
    known = {condition[0] for condition in CONDITIONS}
    result: dict[str, Path] = {}
    if root is not None:
        result.update({slug: root / slug for slug in known if (root / slug).is_dir()})
    if mapping_path is not None:
        for slug, path in _load(mapping_path).items():
            if slug not in known or not isinstance(path, str) or not path:
                raise NativeRunError(f"invalid runs-map entry for {slug}")
            result[slug] = Path(path)
    if not result:
        raise NativeRunError("provide --runs-root or --runs-map")
    return result


def import_runs(
    *,
    runs_root: Path | None = None,
    runs_map: Path | None = None,
    source_index: Path = SOURCE_INDEX,
    scope_index: Path | None = SCOPE_INDEX,
    output: Path = RUNS_DIR,
) -> Json:
    """Import available answers and complete native panels into ``output``."""
    assignments = load_assignments(source_index, scope_index)
    sources = _sources(runs_root, runs_map)
    statuses: dict[str, dict[str, str]] = {}
    counts = {"answers": 0, "complete": 0, "partial": 0, "missing": 0}
    plans: list[tuple[Json, Path, str]] = []
    for assignment_id, assignment in assignments.items():
        statuses[assignment_id] = {}
        for slug, _label, _model, _effort in CONDITIONS:
            source = sources.get(slug)
            trial = _find_trial(source, assignment) if source else None
            if trial is None:
                statuses[assignment_id][slug] = (
                    "missing assignment" if source else "missing condition"
                )
                counts["missing"] += 1
                continue
            run = read_native_run(trial, assignment, slug)
            destination = output / assignment_id / slug
            plans.append((run, destination, _readme(run) + "\n"))
            counts["answers"] += int(run["response_path"] is not None)
            counts[(run["status"] == "complete" and "complete") or "partial"] += 1
            statuses[assignment_id][slug] = str(run["status"])
    planned_destinations = {destination for _run, destination, _readme in plans}
    lines = [
        "# LegalReasonBench litigation model runs",
        "",
        f"Pinned source: `{DATASET}` revision `{REVISION}`.",
        "",
        "Only explicitly mapped native Harbor outputs are included. Responses and raw "
        "verifier files are copied unchanged. Missing or incomplete panels are not "
        "model failures.",
        "",
        f"Answers: **{counts['answers']}**; complete panels: **{counts['complete']}**; "
        f"partial/incomplete: **{counts['partial']}**; "
        f"missing: **{counts['missing']}**.",
        "",
        "| Assignment | Criteria | GPT-6 Luna (xhigh) | Claude Opus 5.5 (low) |",
        "|---|---:|---|---|",
    ]
    for assignment_id, assignment in assignments.items():
        cells: list[str] = []
        for slug, _label, _model, _effort in CONDITIONS:
            status = statuses[assignment_id][slug]
            link = output / assignment_id / slug / "README.md"
            cells.append(
                f"[{status}]({assignment_id}/{slug}/README.md)"
                if link.is_file() or link.parent in planned_destinations
                else status
            )
        lines.append(
            f"| {assignment_id} | {len(assignment.criteria)} | "
            + " | ".join(cells)
            + " |"
        )
    overview = "\n".join(lines) + "\n"
    for run, destination, _readme_text in plans:
        _copy(run["response_path"], destination / "response.md", write=False)
        _copy(run["reward_path"], destination / "reward.json", write=False)
        _copy(run["details_path"], destination / "reward-details.json", write=False)
    for run, destination, readme in plans:
        _copy(run["response_path"], destination / "response.md")
        _copy(run["reward_path"], destination / "reward.json")
        _copy(run["details_path"], destination / "reward-details.json")
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "README.md").write_text(readme, encoding="utf-8")
    output.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(overview, encoding="utf-8")
    return {"assignments": len(assignments), **counts}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n", 1)[0])
    subparsers = parser.add_subparsers(dest="command", required=True)
    importer = subparsers.add_parser("import", help="import native Harbor outputs")
    importer.add_argument(
        "--runs-root",
        type=Path,
        help="Harbor jobs grouped under condition-named subdirectories",
    )
    importer.add_argument(
        "--runs-map",
        type=Path,
        help="JSON object mapping condition slugs to native Harbor job directories",
    )
    importer.add_argument(
        "--source-index",
        type=Path,
        default=SOURCE_INDEX,
        help="Pinned audit rubric index",
    )
    importer.add_argument(
        "--scope-index",
        type=Path,
        default=SCOPE_INDEX,
        help="Litigation assignment selection",
    )
    importer.add_argument(
        "--output",
        type=Path,
        default=RUNS_DIR,
        help="Public output directory; conflicting raw files are refused",
    )
    args = parser.parse_args(argv)
    if args.command == "import":
        print(
            json.dumps(
                import_runs(
                    runs_root=args.runs_root,
                    runs_map=args.runs_map,
                    source_index=args.source_index,
                    scope_index=args.scope_index,
                    output=args.output,
                ),
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
