"""Preregistration metadata validation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.evals.model_registry import ModelRegistry
from legalforecast.protocol.manifest import hash_payload

REQUIRED_PROTOCOL_FIELDS = (
    "cycle_id",
    "claim_level",
    "public_registration.provider",
    "public_registration.url",
    "public_registration.timestamp",
    "freeze_timestamp",
    "anchors.model_release",
    "anchors.decision_window_start",
    "anchors.decision_window_end",
    "anchors.candidate_source_provider",
    "metrics.primary",
    "inference.method",
    "inference.bootstrap_replicates",
    "model_registry.path",
    "model_registry.sha256",
    "frozen_artifacts.manifest_sha256",
    "frozen_artifacts.units_sha256",
    "frozen_artifacts.labels_sha256",
    "frozen_artifacts.prompt_sha256",
    "frozen_artifacts.scorer_sha256",
    "frozen_artifacts.harness_sha256",
)
FROZEN_HASH_FIELDS = (
    "manifest_sha256",
    "units_sha256",
    "labels_sha256",
    "prompt_sha256",
    "scorer_sha256",
    "harness_sha256",
)
REQUIRED_TEMPLATE_TERMS = (
    "Cycle ID",
    "Public registration provider",
    "Candidate manifest",
    "Prediction units",
    "Outcome labels",
    "Model registry SHA-256",
    "Case-mix diagnostics",
)


@dataclass(frozen=True, slots=True)
class PreregistrationValidationIssue:
    path: str
    message: str

    def to_record(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


@dataclass(frozen=True, slots=True)
class PreregistrationValidationResult:
    issues: tuple[PreregistrationValidationIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues

    def to_record(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [issue.to_record() for issue in self.issues],
        }

    def raise_for_errors(self) -> None:
        if self.passed:
            return
        messages = "; ".join(f"{issue.path}: {issue.message}" for issue in self.issues)
        raise ValueError(messages)


def load_preregistration(path: str | Path) -> Mapping[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() == ".json":
        loaded: object = json.loads(text)
    else:
        loaded = parse_simple_yaml(text)
    if not isinstance(loaded, Mapping):
        raise ValueError("preregistration document must be a mapping")
    return cast(Mapping[str, Any], loaded)


def validate_preregistration_record(
    record: Mapping[str, Any],
    *,
    model_registry: ModelRegistry | None = None,
    expected_hashes: Mapping[str, str] | None = None,
    template_text: str | None = None,
) -> PreregistrationValidationResult:
    issues: list[PreregistrationValidationIssue] = []
    for field_path in REQUIRED_PROTOCOL_FIELDS:
        value = _get_path(record, field_path)
        if _is_missing(value):
            issues.append(_issue(field_path, "required field is missing or empty"))

    _validate_public_registration(record, issues)
    _validate_frozen_hashes(record, expected_hashes, issues)
    _validate_model_registry(record, model_registry, issues)
    if template_text is not None:
        _validate_template_terms(template_text, issues)

    return PreregistrationValidationResult(tuple(issues))


def validate_preregistration_file(
    path: str | Path,
    *,
    model_registry: ModelRegistry | None = None,
    expected_hashes: Mapping[str, str] | None = None,
    template_path: str | Path | None = None,
) -> PreregistrationValidationResult:
    template_text = (
        Path(template_path).read_text(encoding="utf-8")
        if template_path is not None
        else None
    )
    return validate_preregistration_record(
        load_preregistration(path),
        model_registry=model_registry,
        expected_hashes=expected_hashes,
        template_text=template_text,
    )


def parse_simple_yaml(text: str) -> Mapping[str, Any]:
    lines: tuple[tuple[int, str], ...] = tuple(_yaml_lines(text))
    parsed, index = _parse_yaml_block(lines, 0, 0)
    if index != len(lines):
        raise ValueError("could not parse preregistration YAML")
    if not isinstance(parsed, Mapping):
        raise ValueError("preregistration YAML root must be a mapping")
    return cast(Mapping[str, Any], parsed)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legalforecast validate-preregistration",
        description="Validate a LegalForecast-MTD preregistration file.",
    )
    parser.add_argument("protocol_path")
    parser.add_argument("--template", default="docs/preregistration_template.md")
    return parser


def cli_validate_preregistration(argv: Sequence[str]) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    result = validate_preregistration_file(
        args.protocol_path,
        template_path=args.template,
    )
    if result.passed:
        print(json.dumps(result.to_record(), sort_keys=True))
        return 0
    print(json.dumps(result.to_record(), sort_keys=True))
    return 1


def _validate_public_registration(
    record: Mapping[str, Any],
    issues: list[PreregistrationValidationIssue],
) -> None:
    provider = _get_path(record, "public_registration.provider")
    url = _get_path(record, "public_registration.url")
    if not isinstance(provider, str) or not isinstance(url, str):
        return
    normalized_provider = provider.strip().lower()
    normalized_url = url.strip().lower()
    if normalized_provider == "osf" and "osf.io" not in normalized_url:
        issues.append(
            _issue("public_registration.url", "OSF URL must reference osf.io")
        )
    if normalized_provider == "aspredicted" and not normalized_url:
        issues.append(
            _issue(
                "public_registration.url",
                "AsPredicted registration URL or ID is required",
            )
        )
    if normalized_provider not in {"osf", "aspredicted"}:
        issues.append(
            _issue(
                "public_registration.provider",
                "provider must be osf or aspredicted",
            )
        )


def _validate_frozen_hashes(
    record: Mapping[str, Any],
    expected_hashes: Mapping[str, str] | None,
    issues: list[PreregistrationValidationIssue],
) -> None:
    frozen_artifacts = _get_path(record, "frozen_artifacts")
    if not isinstance(frozen_artifacts, Mapping):
        return
    artifact_hashes = cast(Mapping[str, Any], frozen_artifacts)
    for field_name in FROZEN_HASH_FIELDS:
        path = f"frozen_artifacts.{field_name}"
        value = artifact_hashes.get(field_name)
        if not isinstance(value, str) or not _is_sha256(value):
            issues.append(_issue(path, "must be a lowercase SHA-256 hash"))
            continue
        if expected_hashes is not None and expected_hashes.get(field_name) != value:
            issues.append(_issue(path, "hash does not match frozen artifact"))


def _validate_model_registry(
    record: Mapping[str, Any],
    model_registry: ModelRegistry | None,
    issues: list[PreregistrationValidationIssue],
) -> None:
    registry_section = _get_path(record, "model_registry")
    if not isinstance(registry_section, Mapping):
        return
    registry = cast(Mapping[str, Any], registry_section)
    registry_hash = registry.get("sha256")
    if not isinstance(registry_hash, str) or not _is_sha256(registry_hash):
        issues.append(
            _issue("model_registry.sha256", "must be a lowercase SHA-256 hash")
        )
    models_raw: object = registry.get("models")
    if model_registry is None or models_raw is None:
        return
    if not isinstance(models_raw, list):
        issues.append(_issue("model_registry.models", "must be a list"))
        return
    models = cast(list[object], models_raw)
    for index, model_key in enumerate(models):
        if not isinstance(model_key, str) or ":" not in model_key:
            issues.append(
                _issue(f"model_registry.models[{index}]", "must be provider:model_id")
            )
            continue
        provider, model_id = model_key.split(":", 1)
        try:
            model_registry.get(provider, model_id)
        except KeyError:
            issues.append(
                _issue(
                    f"model_registry.models[{index}]",
                    f"model registry entry not found: {model_key}",
                )
            )


def _validate_template_terms(
    template_text: str,
    issues: list[PreregistrationValidationIssue],
) -> None:
    for term in REQUIRED_TEMPLATE_TERMS:
        if term not in template_text:
            issues.append(_issue("docs/preregistration_template.md", f"missing {term}"))


def _get_path(record: Mapping[str, Any], field_path: str) -> object:
    current: object = record
    for part in field_path.split("."):
        if not isinstance(current, Mapping):
            return None
        mapping = cast(Mapping[str, object], current)
        if part not in mapping:
            return None
        current = mapping[part]
    return current


def _is_missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _issue(path: str, message: str) -> PreregistrationValidationIssue:
    return PreregistrationValidationIssue(path=path, message=message)


def _is_sha256(value: str) -> bool:
    return is_lowercase_sha256(value)


def _yaml_lines(text: str) -> Iterable[tuple[int, str]]:
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        yield indent, line.strip()


def _parse_yaml_block(
    lines: tuple[tuple[int, str], ...],
    index: int,
    indent: int,
) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    is_list = lines[index][1].startswith("- ")
    if is_list:
        values: list[Any] = []
        while index < len(lines):
            line_indent, text = lines[index]
            if line_indent < indent:
                break
            if line_indent != indent or not text.startswith("- "):
                break
            values.append(_parse_scalar(text[2:].strip()))
            index += 1
        return values, index

    mapping: dict[str, Any] = {}
    while index < len(lines):
        line_indent, text = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent:
            raise ValueError(f"unexpected YAML indentation at: {text}")
        if ":" not in text:
            raise ValueError(f"expected YAML mapping entry: {text}")
        key, raw_value = text.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key:
            raise ValueError("YAML keys must be non-empty")
        if value:
            mapping[key] = _parse_scalar(value)
            index += 1
            continue
        child, index = _parse_yaml_block(lines, index + 1, indent + 2)
        mapping[key] = child
    return mapping, index


def _parse_scalar(value: str) -> Any:
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value == "[]":
        return []
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def artifact_hash_for_record(record: Mapping[str, Any]) -> str:
    """Expose the manifest canonical-hash helper for preregistration tests."""

    return hash_payload(dict(record))
