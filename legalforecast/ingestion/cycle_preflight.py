"""Manifest-driven, provider-free verification of an existing recovery slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseSnapshot,
    canonical_purchase_state_sha256,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.replacement_recovery_source import (
    SOURCE_RUN_CARD_SCHEMA,
    build_recovery_source_descriptor,
    derive_clearance_source_coordinates,
    derive_recovery_source_coordinates,
    derive_resolved_source_coordinates,
)
from legalforecast.ingestion.resolved_post_recovery import (
    reconstruct_pre_resolution_purchase_snapshot,
)

# contract-ratchet: allow local read-only preflight envelope
MANIFEST_SCHEMA = "legalforecast.cycle_preflight_manifest.v1"
# contract-ratchet: allow local read-only preflight envelope
REPORT_SCHEMA = "legalforecast.cycle_preflight_report.v1"
_SHA256 = "sha256:"
_REQUIRED_NODES: Mapping[str, tuple[str, frozenset[str]]] = {
    "recovery": ("recovery_card", frozenset()),
    "purchase-baseline": ("purchase_transition", frozenset()),
    "clearance": ("clearance_card", frozenset({"recovery"})),
    "resolution": (
        "resolution_card",
        frozenset({"clearance", "purchase-baseline"}),
    ),
    "replacement-recovery-source": ("replacement_source", frozenset({"resolution"})),
}
_PATH_COMMITMENT_METADATA = frozenset({"record_count"})
_SCALAR_COMMITMENTS = frozenset({"purchase_state_sha256"})
_SHARED_ARTIFACTS = (
    ("recovery", "clearance", ("recovery-card-json", "selection-jsonl")),
    (
        "recovery",
        "resolution",
        ("recovery-card-json", "selection-jsonl", "purchase-ledger-json"),
    ),
    (
        "purchase-baseline",
        "resolution",
        ("purchase-after-json", "resolved-jsonl"),
    ),
    ("clearance", "resolution", ("clearance-card-json", "clearance-jsonl")),
    (
        "resolution",
        "replacement-recovery-source",
        (
            "recovery-card-json",
            "clearance-card-json",
            "resolved-jsonl",
            "purchase-after-json",
        ),
    ),
)


class CyclePreflightError(ValueError):
    """Raised when a preflight manifest is ambiguous or malformed."""


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    """One stable, content-redacted preflight finding."""

    code: str
    status: str
    node_id: str
    artifact: str
    message: str
    blocked_by: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "code": self.code,
            "status": self.status,
            "node_id": self.node_id,
            "artifact": self.artifact,
            "message": self.message,
        }
        if self.blocked_by:
            record["blocked_by"] = list(self.blocked_by)
        return record


@dataclass(frozen=True, slots=True)
class PreflightNodeResult:
    """Deterministic verdict for one manifest node."""

    node_id: str
    status: str
    issues: tuple[PreflightIssue, ...] = ()
    blocked_by: tuple[str, ...] = ()

    def to_record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "id": self.node_id,
            "status": self.status,
            "issues": [issue.to_record() for issue in self.issues],
        }
        if self.blocked_by:
            record["blocked_by"] = list(self.blocked_by)
        return record


@dataclass(frozen=True, slots=True)
class CyclePreflightResult:
    """Stable collect-all report for one recovery vertical slice."""

    nodes: tuple[PreflightNodeResult, ...]

    @property
    def ok(self) -> bool:
        return all(node.status == "PASSED" for node in self.nodes)

    @property
    def issues(self) -> tuple[PreflightIssue, ...]:
        return tuple(issue for node in self.nodes for issue in node.issues)

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": REPORT_SCHEMA,
            "ok": self.ok,
            "node_count": len(self.nodes),
            "issue_count": len(self.issues),
            "nodes": [node.to_record() for node in self.nodes],
        }


@dataclass(frozen=True, slots=True)
class _Artifact:
    name: str
    path: Path
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class _Node:
    node_id: str
    depends_on: tuple[str, ...]
    artifacts: tuple[_Artifact, ...]
    validator_kind: str
    validator: Mapping[str, object]


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in cast(Mapping[object, object], value)
    ):
        raise CyclePreflightError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CyclePreflightError(f"{label} must be a list")
    return cast(Sequence[object], value)


def _text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CyclePreflightError(f"{label} must be a non-empty string")
    return value


def _prefixed_sha256(value: object, *, label: str) -> str:
    digest = _text(value, label=label)
    suffix = digest.removeprefix(_SHA256)
    if (
        not digest.startswith(_SHA256)
        or len(suffix) != 64
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise CyclePreflightError(f"{label} is not a SHA-256 commitment")
    return digest


def _bare_sha256(value: object, *, label: str) -> str:
    digest = _text(value, label=label)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise CyclePreflightError(f"{label} is not a bare SHA-256 digest")
    return digest


def _path(root: Path, value: object, *, label: str) -> Path:
    raw = _text(value, label=label)
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise CyclePreflightError(f"{label} must be a contained relative path")
    candidate = root / relative
    resolved_root = root.resolve()
    if not candidate.resolve(strict=False).is_relative_to(resolved_root):
        raise CyclePreflightError(f"{label} escapes the preflight capsule")
    return candidate


def _card_path(root: Path, value: object, *, label: str) -> Path:
    """Rebase capsule-relative card data without granting file-read authority."""

    raw = _text(value, label=label)
    path = Path(raw)
    return path if path.is_absolute() else root / path


def _read_stable(path: Path, *, label: str) -> bytes:
    """Read one singly linked regular file without following its leaf link."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise CyclePreflightError(f"{label} requires no-follow support")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | nofollow)
    except OSError as exc:
        raise CyclePreflightError(f"{label} is unavailable or unsafe") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise CyclePreflightError(f"{label} is not a singly linked regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read()
        after = os.fstat(descriptor)
        lexical = os.stat(path, follow_symlinks=False)
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if identity != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or (after.st_dev, after.st_ino) != (lexical.st_dev, lexical.st_ino):
            raise CyclePreflightError(f"{label} changed while reading")
        return payload
    except OSError as exc:
        raise CyclePreflightError(f"{label} is unavailable or changed") from exc
    finally:
        os.close(descriptor)


def _json_object(payload: bytes, *, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CyclePreflightError(f"{label} is not JSON") from exc
    return _mapping(value, label=label)


def _jsonl(payload: bytes, *, label: str) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    try:
        for line in payload.splitlines():
            if line:
                rows.append(
                    cast(Mapping[str, Any], _mapping(json.loads(line), label=label))
                )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CyclePreflightError(f"{label} is not JSONL") from exc
    return tuple(rows)


def _load_manifest(path: Path) -> tuple[Path, tuple[_Node, ...]]:
    root = path.resolve().parent
    manifest = _json_object(
        _read_stable(path, label="cycle preflight manifest"),
        label="cycle preflight manifest",
    )
    if (
        set(manifest) != {"schema_version", "nodes"}
        or manifest.get("schema_version") != MANIFEST_SCHEMA
    ):
        raise CyclePreflightError("cycle preflight manifest schema is invalid")
    raw_nodes = _sequence(manifest.get("nodes"), label="manifest nodes")
    nodes: list[_Node] = []
    seen: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        record = _mapping(raw_node, label=f"manifest node {index}")
        if set(record) != {"id", "depends_on", "artifacts", "validator"}:
            raise CyclePreflightError(f"manifest node {index} fields differ")
        node_id = _text(record.get("id"), label=f"manifest node {index} id")
        if node_id in seen:
            raise CyclePreflightError(f"manifest repeats node id: {node_id}")
        dependencies = tuple(
            _text(value, label=f"manifest node {node_id} dependency")
            for value in _sequence(
                record.get("depends_on"), label=f"manifest node {node_id} dependencies"
            )
        )
        if len(set(dependencies)) != len(dependencies) or node_id in dependencies:
            raise CyclePreflightError(
                f"manifest node dependencies are ambiguous: {node_id}"
            )
        raw_artifacts = _sequence(
            record.get("artifacts"), label=f"manifest node {node_id} artifacts"
        )
        artifacts: list[_Artifact] = []
        artifact_names: set[str] = set()
        for raw_artifact in raw_artifacts:
            artifact = _mapping(raw_artifact, label=f"manifest node {node_id} artifact")
            if set(artifact) != {"name", "path", "sha256"}:
                raise CyclePreflightError(
                    f"manifest node artifact fields differ: {node_id}"
                )
            name = _text(
                artifact.get("name"), label=f"manifest node {node_id} artifact name"
            )
            digest = _text(
                artifact.get("sha256"), label=f"manifest node {node_id} artifact digest"
            )
            if (
                name in artifact_names
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise CyclePreflightError(
                    f"manifest node artifact is ambiguous: {node_id}/{name}"
                )
            artifact_names.add(name)
            artifacts.append(
                _Artifact(
                    name=name,
                    path=_path(
                        root,
                        artifact.get("path"),
                        label=f"manifest node {node_id} artifact path",
                    ),
                    expected_sha256=digest,
                )
            )
        validator = _mapping(
            record.get("validator"), label=f"manifest node {node_id} validator"
        )
        kind = _text(
            validator.get("kind"), label=f"manifest node {node_id} validator kind"
        )
        nodes.append(
            _Node(
                node_id=node_id,
                depends_on=dependencies,
                artifacts=tuple(artifacts),
                validator_kind=kind,
                validator=validator,
            )
        )
        seen.add(node_id)
    for node in nodes:
        missing = set(node.depends_on) - seen
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise CyclePreflightError(
                f"manifest node {node.node_id} has unknown dependencies: {missing_text}"
            )
    if set(seen) != set(_REQUIRED_NODES):
        raise CyclePreflightError("cycle preflight manifest stage set differs")
    for node in nodes:
        expected_kind, expected_dependencies = _REQUIRED_NODES[node.node_id]
        if node.validator_kind != expected_kind or set(node.depends_on) != set(
            expected_dependencies
        ):
            raise CyclePreflightError(
                f"cycle preflight manifest stage contract differs: {node.node_id}"
            )
    nodes_by_id = {node.node_id: node for node in nodes}
    for predecessor_id, descendant_id, shared_names in _SHARED_ARTIFACTS:
        predecessor = {
            artifact.name: artifact
            for artifact in nodes_by_id[predecessor_id].artifacts
        }
        descendant = {
            artifact.name: artifact for artifact in nodes_by_id[descendant_id].artifacts
        }
        for name in shared_names:
            earlier = predecessor.get(name)
            later = descendant.get(name)
            if (
                earlier is None
                or later is None
                or earlier.path.absolute() != later.path.absolute()
                or earlier.expected_sha256 != later.expected_sha256
            ):
                raise CyclePreflightError(
                    f"cycle preflight dependency artifact differs: {name}"
                )
    completed: set[str] = set()
    remaining = list(nodes)
    ordered: list[_Node] = []
    while remaining:
        ready = [node for node in remaining if set(node.depends_on) <= completed]
        if not ready:
            raise CyclePreflightError(
                "cycle preflight manifest dependency graph has a cycle"
            )
        for node in ready:
            completed.add(node.node_id)
            remaining.remove(node)
            ordered.append(node)
    return root, tuple(ordered)


def _artifact_payloads(node: _Node) -> tuple[dict[str, bytes], list[PreflightIssue]]:
    payloads: dict[str, bytes] = {}
    issues: list[PreflightIssue] = []
    for artifact in node.artifacts:
        try:
            payload = _read_stable(
                artifact.path,
                label=f"preflight artifact {node.node_id}/{artifact.name}",
            )
        except CyclePreflightError as exc:
            issues.append(
                PreflightIssue(
                    code="ARTIFACT_UNAVAILABLE",
                    status="FAILED",
                    node_id=node.node_id,
                    artifact=artifact.name,
                    message=str(exc),
                )
            )
            continue
        payloads[artifact.name] = payload
        if hashlib.sha256(payload).hexdigest() != artifact.expected_sha256:
            issues.append(
                PreflightIssue(
                    code="ARTIFACT_SHA256_MISMATCH",
                    status="FAILED",
                    node_id=node.node_id,
                    artifact=artifact.name,
                    message="artifact bytes do not match the manifest commitment",
                )
            )
    return payloads, issues


def _artifact_name(config: Mapping[str, object], field: str) -> str:
    return _text(config.get(field), label=f"validator {field}")


def _payload(
    payloads: Mapping[str, bytes], config: Mapping[str, object], field: str
) -> bytes:
    name = _artifact_name(config, field)
    payload = payloads.get(name)
    if payload is None:
        raise CyclePreflightError(
            f"validator {field} names an undeclared artifact: {name}"
        )
    return payload


def _tree_commitment_paths(
    card: Mapping[str, object],
    *,
    config: Mapping[str, object],
    root: Path,
    payloads: Mapping[str, bytes],
    node: _Node,
) -> tuple[frozenset[str], frozenset[Path]]:
    """Replay explicitly declared frozen producer directory-tree schemas."""

    raw_contracts = config.get("tree_commitments", {})
    contracts = _mapping(raw_contracts, label="validator tree_commitments")
    handled: set[str] = set()
    committed_roots: set[Path] = set()
    artifacts = {artifact.name: artifact for artifact in node.artifacts}
    for contract_name, raw_contract in contracts.items():
        parts = contract_name.split("/")
        if len(parts) != 2 or parts[0] not in {
            "source_commitments",
            "output_commitments",
        }:
            raise CyclePreflightError("validator tree commitment name is invalid")
        field, name = parts
        contract = _mapping(
            raw_contract, label=f"validator tree commitment {contract_name}"
        )
        if set(contract) != {"root", "files"}:
            raise CyclePreflightError(
                f"validator tree commitment {contract_name} fields differ"
            )
        tree_root = _path(
            root,
            contract.get("root"),
            label=f"validator tree commitment {contract_name} root",
        )
        files = _mapping(
            contract.get("files"),
            label=f"validator tree commitment {contract_name} files",
        )
        current_files: set[str] = set()
        try:
            if tree_root.is_symlink() or not tree_root.is_dir():
                raise CyclePreflightError(
                    f"validator tree commitment {contract_name} root is unsafe"
                )
            for path in tree_root.rglob("*"):
                if path.is_symlink():
                    raise CyclePreflightError(
                        f"validator tree commitment {contract_name} tree is unsafe"
                    )
                metadata = path.stat(follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    continue
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise CyclePreflightError(
                        f"validator tree commitment {contract_name} tree is unsafe"
                    )
                current_files.add(path.relative_to(tree_root).as_posix())
        except OSError as exc:
            raise CyclePreflightError(
                f"validator tree commitment {contract_name} tree is unavailable"
            ) from exc
        if current_files != set(files):
            raise CyclePreflightError(
                f"validator tree commitment {contract_name} file set differs"
            )
        observed: dict[str, str] = {}
        for relative, raw_artifact_name in files.items():
            relative_path = Path(relative)
            if (
                not relative
                or relative_path.is_absolute()
                or ".." in relative_path.parts
                or relative_path.as_posix() != relative
            ):
                raise CyclePreflightError(
                    f"validator tree commitment {contract_name} file is invalid"
                )
            artifact_name = _text(
                raw_artifact_name,
                label=f"validator tree commitment {contract_name} artifact",
            )
            artifact = artifacts.get(artifact_name)
            payload = payloads.get(artifact_name)
            expected_path = tree_root / relative_path
            if (
                artifact is None
                or payload is None
                or artifact.path.absolute() != expected_path.absolute()
            ):
                raise CyclePreflightError(
                    f"validator tree commitment {contract_name} is not authenticated"
                )
            observed[relative] = _SHA256 + hashlib.sha256(payload).hexdigest()

        commitments = _mapping(card.get(field), label=f"card {field}")
        raw_commitment = commitments.get(name)
        commitment = _mapping(raw_commitment, label=f"card {field}/{name}")
        if contract_name == "output_commitments/document_tree":
            if commitment != observed:
                raise CyclePreflightError(f"card {field}/{name} commitment differs")
        elif contract_name == "source_commitments/document_root":
            if set(commitment) != {"path", "tree_sha256", "document_count"}:
                raise CyclePreflightError(f"card {field}/{name} fields differ")
            declared_root = _card_path(
                root, commitment.get("path"), label=f"card {field}/{name} path"
            )
            canonical_tree = json.dumps(
                observed,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            expected_tree = _SHA256 + hashlib.sha256(canonical_tree).hexdigest()
            document_count = commitment.get("document_count")
            if (
                declared_root.absolute() != tree_root.absolute()
                or type(document_count) is not int
                or document_count != len(observed)
                or _prefixed_sha256(
                    commitment.get("tree_sha256"),
                    label=f"card {field}/{name} tree sha256",
                )
                != expected_tree
            ):
                raise CyclePreflightError(f"card {field}/{name} commitment differs")
        else:
            raise CyclePreflightError("validator tree commitment schema is unsupported")
        handled.add(contract_name)
        committed_roots.add(tree_root.resolve())
    return frozenset(handled), frozenset(committed_roots)


def _verify_card_commitments(
    card: Mapping[str, object],
    *,
    config: Mapping[str, object],
    root: Path,
    payloads: Mapping[str, bytes],
    node: _Node,
) -> frozenset[Path]:
    """Bind producer-card path commitments to manifest-authenticated bytes."""

    by_path = {
        artifact.path.resolve(): payloads[artifact.name]
        for artifact in node.artifacts
        if artifact.name in payloads
    }
    handled_trees, committed_tree_roots = _tree_commitment_paths(
        card,
        config=config,
        root=root,
        payloads=payloads,
        node=node,
    )
    committed_paths: set[Path] = set(committed_tree_roots)
    for field in ("source_commitments", "output_commitments"):
        raw_commitments = card.get(field)
        if raw_commitments is None:
            continue
        commitments = _mapping(raw_commitments, label=f"card {field}")
        for name, raw_commitment in commitments.items():
            if f"{field}/{name}" in handled_trees:
                continue
            if not isinstance(raw_commitment, Mapping):
                if name in _SCALAR_COMMITMENTS:
                    _prefixed_sha256(raw_commitment, label=f"card {field}/{name}")
                    continue
                raise CyclePreflightError(f"card {field}/{name} is malformed")
            commitment = _mapping(
                cast(object, raw_commitment), label=f"card {field}/{name}"
            )
            fields = set(commitment)
            if (
                not {"path", "sha256"} <= fields
                or not (fields - {"path", "sha256"}) <= _PATH_COMMITMENT_METADATA
            ):
                raise CyclePreflightError(f"card {field}/{name} fields differ")
            record_count = commitment.get("record_count")
            if record_count is not None and (
                type(record_count) is not int or record_count < 0
            ):
                raise CyclePreflightError(
                    f"card {field}/{name} record count is invalid"
                )
            path = _card_path(
                root, commitment.get("path"), label=f"card {field}/{name} path"
            )
            expected = _prefixed_sha256(
                commitment.get("sha256"), label=f"card {field}/{name} sha256"
            )
            payload = by_path.get(path.resolve())
            if payload is None:
                raise CyclePreflightError(
                    f"card {field}/{name} is not authenticated by this node"
                )
            observed = _SHA256 + hashlib.sha256(payload).hexdigest()
            if observed != expected:
                raise CyclePreflightError(f"card {field}/{name} commitment differs")
            if (
                record_count is not None
                and len(_jsonl(payload, label=f"card {field}/{name}")) != record_count
            ):
                raise CyclePreflightError(f"card {field}/{name} record count differs")
            committed_paths.add(path.resolve())

    extra_commitments = config.get("input_commitments", {})
    for name, raw_commitment in _mapping(
        extra_commitments, label="validator input_commitments"
    ).items():
        commitment = _mapping(raw_commitment, label=f"validator input/{name}")
        if set(commitment) != {"path", "sha256"}:
            raise CyclePreflightError(f"validator input/{name} fields differ")
        path = _path(root, commitment.get("path"), label=f"validator input/{name}")
        expected = _prefixed_sha256(
            commitment.get("sha256"), label=f"validator input/{name} sha256"
        )
        payload = by_path.get(path.resolve())
        if payload is None or _SHA256 + hashlib.sha256(payload).hexdigest() != expected:
            raise CyclePreflightError(f"validator input/{name} commitment differs")
        committed_paths.add(path.resolve())

    for field in ("input_paths", "output_paths"):
        raw_paths = card.get(field)
        if raw_paths is None:
            continue
        declared = {
            _card_path(root, raw_path, label=f"card {field}").resolve()
            for raw_path in _sequence(raw_paths, label=f"card {field}")
        }
        if not declared <= committed_paths:
            raise CyclePreflightError(f"card {field} contains uncommitted paths")
    return frozenset(committed_paths)


def _rebased_card(value: object, *, root: Path) -> object:
    if isinstance(value, list):
        return [_rebased_card(item, root=root) for item in cast(list[object], value)]
    if not isinstance(value, Mapping):
        return value
    record = _mapping(cast(object, value), label="semantic card")
    rebased: dict[str, object] = {}
    path_fields = {
        "path",
        "selection",
        "recovery_root",
        "purchased_clearance",
        "purchased_clearance_run_card",
        "resolved_post_recovery_documents",
        "replacement_purchase_authority",
        "replacement_controlled_private_root",
        "replacement_budget_plan",
    }
    path_lists = {"input_paths", "output_paths"}
    for key, raw in record.items():
        if key in path_fields and isinstance(raw, str):
            rebased[key] = str(_card_path(root, raw, label=key).absolute())
        elif key in path_lists and isinstance(raw, list):
            rebased[key] = [
                str(_card_path(root, item, label=key).absolute())
                if isinstance(item, str)
                else item
                for item in cast(list[object], raw)
            ]
        elif key == "terminal_disposition_sources" and isinstance(raw, Mapping):
            path_mapping = _mapping(cast(object, raw), label=key)
            rebased[key] = {
                name: str(_card_path(root, item, label=name).absolute())
                for name, item in path_mapping.items()
            }
        else:
            rebased[key] = _rebased_card(raw, root=root)
    return rebased


def _semantic_recovery(
    root: Path,
    config: Mapping[str, object],
    payloads: Mapping[str, bytes],
    node: _Node,
) -> None:
    card = _json_object(_payload(payloads, config, "card"), label="recovery run card")
    _verify_card_commitments(
        card, config=config, root=root, payloads=payloads, node=node
    )
    coordinates = derive_recovery_source_coordinates(
        cast(Mapping[str, object], _rebased_card(card, root=root))
    )
    if coordinates.kind != _text(config.get("expected_kind"), label="expected_kind"):
        raise CyclePreflightError("recovery source kind differs")


def _semantic_clearance(
    root: Path,
    config: Mapping[str, object],
    payloads: Mapping[str, bytes],
    node: _Node,
) -> None:
    card = _json_object(_payload(payloads, config, "card"), label="clearance run card")
    _verify_card_commitments(
        card, config=config, root=root, payloads=payloads, node=node
    )
    coordinates = derive_clearance_source_coordinates(
        cast(Mapping[str, object], _rebased_card(card, root=root))
    )
    expected = _path(
        root, config.get("expected_clearance"), label="expected clearance path"
    )
    if coordinates.clearance_path.resolve() != expected.resolve():
        raise CyclePreflightError("clearance output path differs")


def _snapshot(payload: bytes, *, label: str) -> CaseDevPurchaseSnapshot:
    record = _json_object(payload, label=label)
    if set(record) != {"operations", "committed_amount_usd", "purchase_state_sha256"}:
        raise CyclePreflightError(f"{label} fields differ")
    operations = tuple(
        cast(Mapping[str, Any], _mapping(row, label=f"{label} operation"))
        for row in _sequence(record.get("operations"), label=f"{label} operations")
    )
    return CaseDevPurchaseSnapshot(
        operations=operations,
        committed_amount_usd=_text(
            record.get("committed_amount_usd"), label=f"{label} committed amount"
        ),
        purchase_state_sha256=_bare_sha256(
            record.get("purchase_state_sha256"), label=f"{label} state"
        ),
    )


def _semantic_purchase_transition(
    _root: Path,
    config: Mapping[str, object],
    payloads: Mapping[str, bytes],
    _node: _Node,
) -> None:
    policy = verify_case_dev_purchase_policy(
        _json_object(_payload(payloads, config, "policy"), label="purchase policy")
    )
    before = _snapshot(_payload(payloads, config, "before"), label="purchase baseline")
    after = _snapshot(
        _payload(payloads, config, "after"), label="purchase current state"
    )
    for label, snapshot in (("baseline", before), ("current", after)):
        observed = canonical_purchase_state_sha256(
            policy,
            committed_amount_usd=snapshot.committed_amount_usd,
            operations=snapshot.operations,
        )
        if observed != snapshot.purchase_state_sha256:
            raise CyclePreflightError(f"purchase {label} state commitment differs")
    resolved = _jsonl(
        _payload(payloads, config, "resolved"), label="resolved documents"
    )
    reconstructed = reconstruct_pre_resolution_purchase_snapshot(
        current_snapshot=after,
        resolved_records=resolved,
        policy=policy,
        expected_purchase_state_before_sha256=before.purchase_state_sha256,
    )
    if reconstructed != before:
        raise CyclePreflightError("resolved transition does not reproduce baseline")


def _semantic_resolution(
    root: Path,
    config: Mapping[str, object],
    payloads: Mapping[str, bytes],
    node: _Node,
) -> None:
    card = _json_object(_payload(payloads, config, "card"), label="resolution run card")
    _verify_card_commitments(
        card, config=config, root=root, payloads=payloads, node=node
    )
    after = _snapshot(
        _payload(payloads, config, "after"), label="purchase current state"
    )
    inputs = tuple(
        _path(root, item, label="resolution input")
        for item in _sequence(config.get("expected_inputs"), label="resolution inputs")
    )
    terminal_path = _path(root, config.get("terminal_path"), label="terminal path")
    terminal_name = _artifact_name(config, "terminal")
    terminal_artifact = next(
        (artifact for artifact in node.artifacts if artifact.name == terminal_name),
        None,
    )
    if (
        terminal_artifact is None
        or terminal_artifact.path.resolve() != terminal_path.resolve()
    ):
        raise CyclePreflightError("terminal partition artifact path differs")
    terminal_payload = _payload(payloads, config, "terminal")
    terminal_sha256 = _SHA256 + hashlib.sha256(terminal_payload).hexdigest()
    terminal_count = len(_jsonl(terminal_payload, label="terminal partition"))
    raw_dispositions = config.get("terminal_disposition_paths")
    if terminal_count:
        raise CyclePreflightError(
            "nonempty terminal partition requires authoritative disposition replay"
        )
    else:
        if raw_dispositions is not None:
            raise CyclePreflightError(
                "empty terminal partition cannot declare disposition paths"
            )
        dispositions = None
    coordinates = derive_resolved_source_coordinates(
        cast(Mapping[str, object], _rebased_card(card, root=root)),
        expected_input_paths=inputs,
        expected_ledger_path=_path(root, config.get("ledger"), label="ledger"),
        expected_purchase_state_sha256=_SHA256 + after.purchase_state_sha256,
        expected_terminal_unavailable_path=terminal_path,
        expected_terminal_unavailable_sha256=terminal_sha256,
        expected_terminal_unavailable_count=terminal_count,
        expected_terminal_disposition_paths=dispositions,
    )
    expected_resolved = _path(
        root, config.get("expected_resolved"), label="expected resolved path"
    )
    if coordinates.resolved_path.resolve() != expected_resolved.resolve():
        raise CyclePreflightError("resolution output path differs")


def _semantic_replacement_source(
    root: Path,
    config: Mapping[str, object],
    payloads: Mapping[str, bytes],
    _node: _Node,
) -> None:
    recovery_card = _json_object(
        _payload(payloads, config, "recovery_card"), label="recovery run card"
    )
    coordinates = derive_recovery_source_coordinates(
        cast(Mapping[str, object], _rebased_card(recovery_card, root=root))
    )
    ordinal = config.get("ordinal")
    if type(ordinal) is not int:
        raise CyclePreflightError("replacement source ordinal must be an integer")
    expected = build_recovery_source_descriptor(
        coordinates=coordinates,
        ordinal=ordinal,
        recovery_root=_path(root, config.get("recovery_root"), label="recovery root"),
        purchased_clearance_path=_path(
            root, config.get("clearance"), label="clearance"
        ),
        purchased_clearance_run_card_path=_path(
            root, config.get("clearance_card"), label="clearance card"
        ),
        resolved_post_recovery_documents_path=_path(
            root, config.get("resolved"), label="resolved documents"
        ),
        replacement_controlled_private_root=_path(
            root, config.get("controlled_private_root"), label="controlled private root"
        ),
    )
    observed = _json_object(
        _payload(payloads, config, "descriptor"), label="recovery source descriptor"
    )
    if _rebased_card(observed, root=root) != expected:
        raise CyclePreflightError("replacement recovery source descriptor differs")
    producer = _json_object(
        _payload(payloads, config, "producer_card"),
        label="replacement source producer card",
    )
    allowed_fields = {
        "schema_version",
        "stage",
        "status",
        "dry_run",
        "execute",
        "kind",
        "ordinal",
        "record_count",
        "input_paths",
        "output_paths",
        "source_commitments",
        "output_commitments",
        "purchase_state_sha256",
        "paid_activity_requested",
        "paid_activity_executed",
        "provider_activity_requested",
        "provider_activity_executed",
    }
    schema = producer.get("schema_version")
    if (
        set(producer) != allowed_fields
        or schema != SOURCE_RUN_CARD_SCHEMA
        or producer.get("stage") != "build-replacement-recovery-source"
        or producer.get("status") != "completed"
        or producer.get("dry_run") is not False
        or producer.get("execute") is not True
        or producer.get("kind") != coordinates.kind
        or producer.get("ordinal") != ordinal
        or producer.get("record_count") != 1
        or producer.get("paid_activity_requested") is not False
        or producer.get("paid_activity_executed") is not False
        or producer.get("provider_activity_requested") is not False
        or producer.get("provider_activity_executed") is not False
    ):
        raise CyclePreflightError("replacement source producer card is not closed")
    after = _snapshot(
        _payload(payloads, config, "after"), label="purchase current state"
    )
    if producer.get("purchase_state_sha256") != after.purchase_state_sha256:
        raise CyclePreflightError("replacement producer purchase state differs")
    artifacts_by_path = {
        artifact.path.resolve(): payloads[artifact.name]
        for artifact in _node.artifacts
        if artifact.name in payloads
    }
    input_paths = tuple(
        _card_path(root, raw_path, label="producer input").resolve()
        for raw_path in _sequence(producer.get("input_paths"), label="producer inputs")
    )
    source_commitments = _mapping(
        producer.get("source_commitments"), label="producer source commitments"
    )
    committed_inputs = {
        _card_path(root, raw_path, label="producer commitment").resolve(): digest
        for raw_path, digest in source_commitments.items()
    }
    if (
        len(set(input_paths)) != len(input_paths)
        or len(committed_inputs) != len(source_commitments)
        or set(input_paths) != set(committed_inputs)
    ):
        raise CyclePreflightError("replacement producer input commitments differ")
    for path, digest in committed_inputs.items():
        payload = artifacts_by_path.get(path)
        if payload is None or _SHA256 + hashlib.sha256(
            payload
        ).hexdigest() != _prefixed_sha256(digest, label="producer source digest"):
            raise CyclePreflightError("replacement producer source bytes differ")
    required_inputs = {
        _path(root, raw_path, label="required producer input").resolve()
        for raw_path in _sequence(
            config.get("expected_producer_inputs"), label="required producer inputs"
        )
    }
    if required_inputs != set(input_paths):
        raise CyclePreflightError("replacement producer evidence set differs")
    output_paths = tuple(
        _card_path(root, raw_path, label="producer output").resolve()
        for raw_path in _sequence(
            producer.get("output_paths"), label="producer outputs"
        )
    )
    output_commitments = _mapping(
        producer.get("output_commitments"), label="producer output commitments"
    )
    normalized_outputs = {
        _card_path(root, raw_path, label="producer output commitment").resolve(): digest
        for raw_path, digest in output_commitments.items()
    }
    if len(output_paths) != 1 or set(normalized_outputs) != {output_paths[0]}:
        raise CyclePreflightError("replacement producer output commitments differ")
    descriptor_name = _artifact_name(config, "descriptor")
    descriptor_payload = _payload(payloads, config, "descriptor")
    descriptor_artifact = next(
        (artifact for artifact in _node.artifacts if artifact.name == descriptor_name),
        None,
    )
    configured_descriptor_path = _path(
        root, config.get("descriptor_path"), label="descriptor path"
    )
    if (
        descriptor_artifact is None
        or descriptor_artifact.path.absolute() != configured_descriptor_path.absolute()
        or output_paths[0].absolute() != descriptor_artifact.path.absolute()
    ):
        raise CyclePreflightError("replacement producer descriptor coordinate differs")
    if (
        _prefixed_sha256(
            normalized_outputs[output_paths[0]], label="producer output digest"
        )
        != _SHA256 + hashlib.sha256(descriptor_payload).hexdigest()
    ):
        raise CyclePreflightError("replacement producer descriptor bytes differ")


_VALIDATORS: Mapping[
    str, Callable[[Path, Mapping[str, object], Mapping[str, bytes], _Node], None]
] = {
    "recovery_card": _semantic_recovery,
    "clearance_card": _semantic_clearance,
    "purchase_transition": _semantic_purchase_transition,
    "resolution_card": _semantic_resolution,
    "replacement_source": _semantic_replacement_source,
}


def verify_cycle_manifest(path: Path) -> CyclePreflightResult:
    """Verify every independently evaluable manifest node without side effects."""

    root, nodes = _load_manifest(path)
    results: list[PreflightNodeResult] = []
    statuses: dict[str, str] = {}
    for node in nodes:
        blocked_by = tuple(
            dependency
            for dependency in node.depends_on
            if statuses[dependency] != "PASSED"
        )
        if blocked_by:
            issue = PreflightIssue(
                code="DEPENDENCY_NOT_VERIFIED",
                status="NOT_EVALUATED",
                node_id=node.node_id,
                artifact="node",
                message="node prerequisites did not authenticate",
                blocked_by=blocked_by,
            )
            result = PreflightNodeResult(
                node_id=node.node_id,
                status="NOT_EVALUATED",
                issues=(issue,),
                blocked_by=blocked_by,
            )
        else:
            payloads, issues = _artifact_payloads(node)
            if not issues:
                validator = _VALIDATORS.get(node.validator_kind)
                if validator is None:
                    issues.append(
                        PreflightIssue(
                            code="UNSUPPORTED_VALIDATOR",
                            status="FAILED",
                            node_id=node.node_id,
                            artifact="node",
                            message=(
                                "unsupported cycle preflight validator: "
                                f"{node.validator_kind}"
                            ),
                        )
                    )
                else:
                    try:
                        validator(root, node.validator, payloads, node)
                    except CyclePreflightError as exc:
                        message = str(exc)
                    except (KeyError, TypeError, ValueError) as exc:
                        message = (
                            "semantic replay rejected authenticated inputs "
                            f"({type(exc).__name__})"
                        )
                    else:
                        message = None
                    if message is not None:
                        issues.append(
                            PreflightIssue(
                                code="SEMANTIC_REPLAY_FAILED",
                                status="FAILED",
                                node_id=node.node_id,
                                artifact="node",
                                message=message,
                            )
                        )
            result = PreflightNodeResult(
                node_id=node.node_id,
                status="FAILED" if issues else "PASSED",
                issues=tuple(issues),
            )
        results.append(result)
        statuses[node.node_id] = result.status
    return CyclePreflightResult(nodes=tuple(results))


def _render_text(result: CyclePreflightResult) -> str:
    lines: list[str] = []
    for node in result.nodes:
        verb = {"PASSED": "PASS", "FAILED": "FAIL", "NOT_EVALUATED": "NOT_EVALUATED"}[
            node.status
        ]
        blocked = f" blocked_by={','.join(node.blocked_by)}" if node.blocked_by else ""
        lines.append(f"{verb} {node.node_id}{blocked}")
        for issue in node.issues:
            if issue.status == "FAILED":
                lines.append(f"  {issue.code} {issue.artifact}: {issue.message}")
    verdict = "PASS" if result.ok else "FAIL"
    lines.append(
        f"VERDICT {verdict} nodes={len(result.nodes)} issues={len(result.issues)}"
    )
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the read-only cycle preflight and print one stable verdict."""

    parser = argparse.ArgumentParser(
        prog="python -m legalforecast.ingestion.cycle_preflight",
        description="Verify an existing recovery vertical slice without side effects.",
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)
    try:
        result = verify_cycle_manifest(cast(Path, args.manifest))
    except CyclePreflightError as exc:
        issue = PreflightIssue(
            code="MANIFEST_INVALID",
            status="FAILED",
            node_id="manifest",
            artifact="manifest",
            message=str(exc),
        )
        result = CyclePreflightResult(
            nodes=(
                PreflightNodeResult(
                    node_id="manifest", status="FAILED", issues=(issue,)
                ),
            )
        )
    if args.format == "json":
        print(json.dumps(result.to_record(), sort_keys=True, separators=(",", ":")))
    else:
        sys.stdout.write(_render_text(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
