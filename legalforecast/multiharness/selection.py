"""Deterministic task selection for multi-harness partial runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from legalforecast.multiharness.spec import CanonicalTask, TaskIndex


@dataclass(frozen=True, slots=True)
class ComparisonGroup:
    """Community-comparison grouping key for a selected task family."""

    family: str
    scoring_mode: str
    selection_sha256: str

    def to_record(self) -> dict[str, str]:
        return {
            "family": self.family,
            "scoring_mode": self.scoring_mode,
            "selection_sha256": self.selection_sha256,
        }


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Selected tasks plus their stable partial-run hash."""

    tasks: tuple[CanonicalTask, ...]
    selection_sha256: str
    selection_label: str

    @property
    def comparison_groups(self) -> tuple[ComparisonGroup, ...]:
        groups = {
            (task.family, task.scoring_mode, self.selection_sha256)
            for task in self.tasks
        }
        return tuple(
            ComparisonGroup(
                family=family,
                scoring_mode=scoring_mode,
                selection_sha256=selection_sha256,
            )
            for family, scoring_mode, selection_sha256 in sorted(groups)
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "selection_sha256": self.selection_sha256,
            "selection_label": self.selection_label,
            "task_ids": [task.task_id for task in self.tasks],
            "comparison_groups": [
                group.to_record() for group in self.comparison_groups
            ],
        }


@dataclass(frozen=True, slots=True)
class TaskSelection:
    """Filter and sample canonical tasks for a partial or full run."""

    families: tuple[str, ...] = ()
    task_ids: tuple[str, ...] = ()
    case_ids: tuple[str, ...] = ()
    candidate_ids: tuple[str, ...] = ()
    ablations: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    practice_areas: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    limit: int | None = None
    seed: str | None = None
    allow_empty: bool = False
    label: str | None = None

    def __post_init__(self) -> None:
        _require_positive_limit(self.limit)
        for value in (
            self.families
            + self.task_ids
            + self.case_ids
            + self.candidate_ids
            + self.ablations
            + self.modules
            + self.practice_areas
            + self.tags
        ):
            if not value.strip():
                raise ValueError("selector values must be non-empty strings")
        if self.seed is not None and not self.seed.strip():
            raise ValueError("seed must be non-empty when provided")
        if self.label is not None and not self.label.strip():
            raise ValueError("label must be non-empty when provided")

    @classmethod
    def full(cls, *, label: str = "full") -> TaskSelection:
        return cls(label=label)

    def normalized(self) -> TaskSelection:
        """Return a selection with duplicate selector values removed."""

        return TaskSelection(
            families=_dedupe(self.families),
            task_ids=_dedupe(self.task_ids),
            case_ids=_dedupe(self.case_ids),
            candidate_ids=_dedupe(self.candidate_ids),
            ablations=_dedupe(self.ablations),
            modules=_dedupe(self.modules),
            practice_areas=_dedupe(self.practice_areas),
            tags=_dedupe(self.tags),
            limit=self.limit,
            seed=self.seed,
            allow_empty=self.allow_empty,
            label=self.label,
        )

    def select(self, task_index: TaskIndex) -> SelectionResult:
        selection = self.normalized()
        selected = tuple(task for task in task_index.tasks if selection._matches(task))
        selected = _stable_sample(selected, seed=selection.seed, limit=selection.limit)
        if not selected and not selection.allow_empty:
            raise ValueError("task selection matched no tasks")
        selection_sha256 = _selection_sha256(selected)
        return SelectionResult(
            tasks=selected,
            selection_sha256=selection_sha256,
            selection_label=selection.label or _default_label(selection),
        )

    def to_record(self) -> dict[str, Any]:
        selection = self.normalized()
        return {
            "families": list(selection.families),
            "task_ids": list(selection.task_ids),
            "case_ids": list(selection.case_ids),
            "candidate_ids": list(selection.candidate_ids),
            "ablations": list(selection.ablations),
            "modules": list(selection.modules),
            "practice_areas": list(selection.practice_areas),
            "tags": list(selection.tags),
            "limit": selection.limit,
            "seed": selection.seed,
            "allow_empty": selection.allow_empty,
            "label": selection.label,
        }

    def _matches(self, task: CanonicalTask) -> bool:
        metadata = task.metadata
        return (
            _matches_optional(task.family, self.families)
            and _matches_optional(task.task_id, self.task_ids)
            and _matches_optional(_metadata_str(metadata, "case_id"), self.case_ids)
            and _matches_optional(
                _metadata_str(metadata, "candidate_id"),
                self.candidate_ids,
            )
            and _matches_optional(_metadata_str(metadata, "ablation"), self.ablations)
            and _matches_optional(_metadata_str(metadata, "module"), self.modules)
            and _matches_optional(
                _metadata_str(metadata, "practice_area"),
                self.practice_areas,
            )
            and _matches_tags(metadata, self.tags)
        )


def _matches_optional(value: str | None, allowed: tuple[str, ...]) -> bool:
    if not allowed:
        return True
    return value in allowed


def _matches_tags(metadata: Mapping[str, Any], required_tags: tuple[str, ...]) -> bool:
    if not required_tags:
        return True
    raw_tags = metadata.get("tags", ())
    if not isinstance(raw_tags, Iterable) or isinstance(raw_tags, str | bytes):
        return False
    raw_tag_values = cast(Iterable[object], raw_tags)
    tags = {value for value in raw_tag_values if isinstance(value, str)}
    return set(required_tags).issubset(tags)


def _metadata_str(metadata: Mapping[str, Any], field_name: str) -> str | None:
    value = metadata.get(field_name)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _stable_sample(
    tasks: tuple[CanonicalTask, ...],
    *,
    seed: str | None,
    limit: int | None,
) -> tuple[CanonicalTask, ...]:
    ordered = tasks
    if seed is not None:
        ordered = tuple(sorted(tasks, key=lambda task: _seeded_sort_key(seed, task)))
    if limit is None:
        return ordered
    return ordered[:limit]


def _seeded_sort_key(seed: str, task: CanonicalTask) -> str:
    payload = {
        "seed": seed,
        "task": task.to_record(),
    }
    return _record_sha256(payload)


def _selection_sha256(tasks: tuple[CanonicalTask, ...]) -> str:
    return _record_sha256([task.to_record() for task in tasks])


def _record_sha256(record: Any) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _default_label(selection: TaskSelection) -> str:
    record = selection.to_record()
    active = [
        field_name
        for field_name, value in record.items()
        if field_name not in {"allow_empty", "label"} and value not in (None, [], ())
    ]
    if not active:
        return "full"
    return "+".join(active)


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _require_positive_limit(limit: int | None) -> None:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive when provided")
