"""Ratcheting fence for commitment helpers and inline schema literals."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tokenize
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, cast

ALLOW_MARKER: Final[str] = "contract-ratchet: allow"
BASELINE_PATH: Final[Path] = Path("legalforecast/contracts/ratchet_baseline.json")
SCHEMA_LITERAL: Final[re.Pattern[str]] = re.compile(
    r"legalforecast(?:\.[a-z0-9][a-z0-9_-]*)+\.v[1-9][0-9]*"
)
PRIVATE_HELPER_NAMES: Final[frozenset[str]] = frozenset(
    {
        "canonical_json_bytes",
        "_canonical_json_bytes",
        "canonical_json_value_bytes",
        "_canonical_json_value_bytes",
        "_bytes_sha256",
        "_canonical_json_sha256",
        "_canonical_sha256",
        "canonical_sha256",
        "canonical_records_sha256",
        "hash_payload",
    }
)
SCANNED_ROOTS: Final[tuple[str, ...]] = ("legalforecast", "scripts")
EXCLUDED_FILES: Final[frozenset[str]] = frozenset(
    {
        "legalforecast/contracts/schemas.py",
        "legalforecast/contracts/ratchet.py",
    }
)
EXCLUDED_DIR_PARTS: Final[frozenset[str]] = frozenset({"__pycache__", "tmp"})
SUSPICIOUS_ENCODER_NAMES: Final[frozenset[str]] = frozenset(
    {
        "canonical_json_bytes",
        "_canonical_json_bytes",
        "canonical_json_value_bytes",
        "_canonical_json_value_bytes",
        "manifest_canonical_json",
    }
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One ratchet violation candidate."""

    rule: str
    path: str
    subject: str
    line: int
    detail: str
    guidance: str


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    """A reviewed exception for one historical finding."""

    rule: str
    path: str
    subject: str
    reason: str


class _Scope:
    def __init__(self) -> None:
        self.suspicious_bytes_names: set[str] = set()


class _Scanner(ast.NodeVisitor):
    def __init__(self, path: Path, relative_path: str, source: str) -> None:
        self.path = path
        self.relative_path = relative_path
        self.source = source
        self.allowed_lines = _allowed_lines(path)
        self.findings_by_key: dict[tuple[str, str, str], Finding] = {}
        self.parents: dict[ast.AST, ast.AST] = {}
        self.scopes: list[_Scope] = [_Scope()]
        self.hashlib_aliases: set[str] = {"hashlib"}
        self.sha256_aliases: set[str] = set()

    def visit(self, node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            self.parents[child] = node
        super().visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "hashlib":
                self.hashlib_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "hashlib":
            for alias in node.names:
                if alias.name == "sha256":
                    self.sha256_aliases.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._maybe_add_private_helper(node)
        self.scopes.append(_Scope())
        self.generic_visit(node)
        self.scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._maybe_add_private_helper(node)
        self.scopes.append(_Scope())
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        if _expr_is_suspicious_bytes(node.value):
            for target in node.targets:
                for name in _assigned_names(target):
                    self.scopes[-1].suspicious_bytes_names.add(name)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and _expr_is_suspicious_bytes(node.value):
            for name in _assigned_names(node.target):
                self.scopes[-1].suspicious_bytes_names.add(name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_suspicious_sha256(node):
            snippet = _source_segment(self.source, node)
            self._record(
                rule="direct_commitment_hash",
                subject=snippet or "hashlib.sha256(...)",
                line=node.lineno,
                detail=(
                    "direct sha256 over commitment-like bytes; use a named "
                    "profile from legalforecast.contracts instead"
                ),
                guidance=(
                    "Import ARTIFACT_RAW_SHA256_V1, ARTIFACT_PREFIXED_SHA256_V1, "
                    "MANIFEST_RAW_SHA256_V1, or RUN_CARD_RAW_SHA256_V1 from "
                    "legalforecast.contracts. For a truly non-persisted one-off, add "
                    f"a nearby '# {ALLOW_MARKER} <reason>' comment."
                ),
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if (
            isinstance(node.value, str)
            and SCHEMA_LITERAL.fullmatch(node.value)
            and not self._is_docstring(node)
        ):
            self._record(
                rule="inline_schema_literal",
                subject=node.value,
                line=node.lineno,
                detail="inline legalforecast schema identifier outside the registry",
                guidance=(
                    "Add the schema identifier to legalforecast/contracts/schemas.py "
                    "and import the named constant instead of inlining the literal. "
                    f"For a narrow non-registry exception, add '# {ALLOW_MARKER} "
                    "<reason>' beside the literal."
                ),
            )
        self.generic_visit(node)

    def findings(self) -> tuple[Finding, ...]:
        return tuple(
            sorted(
                self.findings_by_key.values(),
                key=lambda finding: (
                    finding.path,
                    finding.rule,
                    finding.subject,
                    finding.line,
                ),
            )
        )

    def _maybe_add_private_helper(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        if node.name not in PRIVATE_HELPER_NAMES and not (
            "sha256" in node.name and _function_uses_canonical_contracts(node)
        ):
            return
        self._record(
            rule="private_commitment_helper",
            subject=node.name,
            line=node.lineno,
            detail="private commitment or canonicalization helper",
            guidance=(
                "Import named codecs and commitment profiles from "
                "legalforecast.contracts instead of defining a new private helper. "
                f"For a narrow non-persisted exception, add '# {ALLOW_MARKER} "
                "<reason>' above the helper."
            ),
        )

    def _record(
        self, *, rule: str, subject: str, line: int, detail: str, guidance: str
    ) -> None:
        # `allowed_lines` already contains both the marker's own line (trailing
        # comment) and the line below it (comment above the offending code).
        # Also accepting `line - 1` here would stretch one marker across three
        # lines and silently excuse code the reviewer never looked at.
        if line in self.allowed_lines:
            return
        key = (rule, self.relative_path, subject)
        self.findings_by_key.setdefault(
            key,
            Finding(
                rule=rule,
                path=self.relative_path,
                subject=subject,
                line=line,
                detail=detail,
                guidance=guidance,
            ),
        )

    def _is_docstring(self, node: ast.Constant) -> bool:
        parent = self.parents.get(node)
        if not isinstance(parent, ast.Expr):
            return False
        grandparent = self.parents.get(parent)
        if isinstance(grandparent, ast.Module):
            return grandparent.body[:1] == [parent]
        if isinstance(
            grandparent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            return grandparent.body[:1] == [parent]
        return False

    def _is_suspicious_sha256(self, node: ast.Call) -> bool:
        if not _is_sha256_constructor(node, self.hashlib_aliases, self.sha256_aliases):
            return False
        if not node.args:
            return False
        return _arg_is_commitment_like(node.args[0], self.scopes)


def scan_repository(root: Path) -> tuple[Finding, ...]:
    """Return all ratchet findings beneath the tracked roots."""

    findings: list[Finding] = []
    for relative_path in _iter_python_paths(root):
        source_path = root / relative_path
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        scanner = _Scanner(source_path, relative_path, source)
        scanner.visit(tree)
        findings.extend(scanner.findings())
    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                finding.path,
                finding.rule,
                finding.subject,
                finding.line,
            ),
        )
    )


def load_baseline(path: Path) -> tuple[BaselineEntry, ...]:
    """Load and validate a reviewed baseline file."""

    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, list):
        raise ValueError("ratchet baseline must be a JSON list")
    payload = cast(list[object], raw_payload)
    entries: list[BaselineEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw_row in enumerate(payload):
        if not isinstance(raw_row, dict):
            raise ValueError(f"ratchet baseline entry {index} must be an object")
        row = cast(dict[str, object], raw_row)
        rule = _required_baseline_str(row, index, "rule")
        path_value = _required_baseline_str(row, index, "path")
        subject = _required_baseline_str(row, index, "subject")
        reason = _required_baseline_str(row, index, "reason")
        if not reason.strip():
            raise ValueError(f"ratchet baseline entry {index} must include a reason")
        key = (rule, path_value, subject)
        if key in seen:
            raise ValueError(
                "ratchet baseline contains a duplicate entry for "
                f"{path_value}: {subject}"
            )
        seen.add(key)
        entries.append(
            BaselineEntry(
                rule=rule,
                path=path_value,
                subject=subject,
                reason=reason.strip(),
            )
        )
    return tuple(entries)


def find_new_violations(
    findings: Sequence[Finding], baseline: Sequence[BaselineEntry]
) -> tuple[Finding, ...]:
    """Return findings not covered by the reviewed baseline."""

    allowed = {(entry.rule, entry.path, entry.subject) for entry in baseline}
    return tuple(
        finding
        for finding in findings
        if (finding.rule, finding.path, finding.subject) not in allowed
    )


def build_baseline(findings: Sequence[Finding]) -> tuple[BaselineEntry, ...]:
    """Turn a raw scan into a reviewed-looking baseline skeleton."""

    return tuple(
        BaselineEntry(
            rule=finding.rule,
            path=finding.path,
            subject=finding.subject,
            reason=_default_reason(finding.rule),
        )
        for finding in findings
    )


def write_baseline(path: Path, findings: Sequence[Finding]) -> None:
    """Write a normalized baseline file."""

    payload = [asdict(entry) for entry in build_baseline(findings)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when new private commitment helpers, direct commitment-byte hashes, "
            "or inline legalforecast schema literals appear outside the reviewed "
            "baseline."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help="Path to the reviewed ratchet baseline JSON file.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline from the current findings instead of checking it.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    baseline_path = args.baseline
    if not baseline_path.is_absolute():
        baseline_path = root / baseline_path
    findings = scan_repository(root)
    if args.write_baseline:
        write_baseline(baseline_path, findings)
        print(f"wrote ratchet baseline with {len(findings)} entries to {baseline_path}")
        return 0

    baseline = load_baseline(baseline_path)
    violations = find_new_violations(findings, baseline)
    if not violations:
        print(
            f"contract ratchet passed: {len(findings)} historical findings reviewed in "
            f"{baseline_path.relative_to(root)}"
        )
        return 0

    print("contract ratchet found new violations:\n", file=sys.stderr)
    for finding in violations:
        print(
            f"- {finding.path}:{finding.line}: {finding.rule}: {finding.subject}\n"
            f"  {finding.detail}\n"
            f"  {finding.guidance}",
            file=sys.stderr,
        )
    print(
        "\nIf a finding is truly intentional, either migrate it to the shared "
        "contracts surface or add a reviewed baseline entry with a one-line reason.",
        file=sys.stderr,
    )
    return 1


def _iter_python_paths(root: Path) -> Iterable[str]:
    for base in SCANNED_ROOTS:
        base_path = root / base
        if not base_path.exists():
            continue
        for path in sorted(base_path.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if relative in EXCLUDED_FILES:
                continue
            if any(part in EXCLUDED_DIR_PARTS for part in Path(relative).parts):
                continue
            yield relative


def _allowed_lines(path: Path) -> set[int]:
    allowed: set[int] = set()
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type == tokenize.COMMENT and ALLOW_MARKER in token.string:
                allowed.add(token.start[0])
                allowed.add(token.start[0] + 1)
    return allowed


def _assigned_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in node.elts:
            names.extend(_assigned_names(element))
        return tuple(names)
    return ()


def _function_uses_canonical_contracts(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if _called_name(child.func) in SUSPICIOUS_ENCODER_NAMES:
                return True
            if _called_name(child.func) == "dumps":
                owner = _attribute_owner(child.func)
                if owner in {None, "json"}:
                    return True
        if _is_sha256_constructor(child, {"hashlib"}, set()):
            return True
    return False


def _arg_is_commitment_like(argument: ast.expr, scopes: Sequence[_Scope]) -> bool:
    if _expr_is_suspicious_bytes(argument):
        return True
    if isinstance(argument, ast.Name):
        return any(
            argument.id in scope.suspicious_bytes_names for scope in reversed(scopes)
        )
    if isinstance(argument, ast.Call):
        return _called_name(argument.func) in {"bytes", "b64decode"}
    return False


def _expr_is_suspicious_bytes(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        called = _called_name(node.func)
        if called in SUSPICIOUS_ENCODER_NAMES:
            return True
        if called == "encode" and isinstance(node.func, ast.Attribute):
            return _called_name(node.func.value) == "manifest_canonical_json"
    return False


def _is_sha256_constructor(
    node: ast.AST, hashlib_aliases: set[str], sha256_aliases: set[str]
) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Attribute):
        return (
            node.func.attr == "sha256"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in hashlib_aliases
        )
    return isinstance(node.func, ast.Name) and node.func.id in sha256_aliases


def _called_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _attribute_owner(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id
    return None


def _source_segment(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node)
    if segment is None:
        return ""
    return " ".join(segment.split())


def _default_reason(rule: str) -> str:
    if rule == "private_commitment_helper":
        return "legacy private commitment helper pending shared-contract migration"
    if rule == "direct_commitment_hash":
        return "legacy direct commitment hash pending named-profile migration"
    if rule == "inline_schema_literal":
        return "legacy schema literal pending registry import"
    return "legacy reviewed exception"


def _required_baseline_str(
    row: Mapping[str, object], index: int, field_name: str
) -> str:
    value = row.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"ratchet baseline entry {index} has invalid {field_name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
