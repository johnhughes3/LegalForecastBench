"""Redact denied hostnames before anything leaves the operator's machine.

The sidecar still records the CONNECT target in-process so a missing
allowlist entry can be diagnosed.  That raw name is an exfil channel the
moment it is copied into a results package, a proxy-log artifact, or the
community tree: an evaluated agent encodes a secret as a subdomain of a
host it knows will be refused, never egresses, and reads the secret back
from the public record.

Published refused hosts are replaced with the constant ``denied/redacted``.
It cannot carry an attacker-selected bit or support dictionary recovery. Extra
labels on an allowlisted parent are published as ``*.<parent>``, not the
requested name.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.multiharness.container_harness.egress_proxy import (
    EgressAllowlist,
    EgressPolicyError,
    normalize_host,
)
from legalforecast.multiharness.container_harness.evidence import (
    AccountedEgress,
    EgressEvidenceError,
    parse_egress_evidence,
)
from legalforecast.multiharness.container_harness.fence import (
    FenceObservation,
    require_honest_fence_record,
)

DENIED_HOST_PLACEHOLDER: Final[str] = "denied/redacted"
RESULT_FILE_NAME: Final[str] = "result.json"
PROXY_LOGS_FILE_NAME: Final[str] = "proxy-logs.json"
FENCE_FILE_NAME: Final[str] = "fence.json"
_REFUSED_KEYS: Final[frozenset[str]] = frozenset({"refused", "egress_refused"})
_JSON_SUFFIXES: Final[frozenset[str]] = frozenset({".json", ".jsonl"})
_ATTACKER_LABEL_MIN_LEN: Final[int] = 8


class PublicationError(ValueError):
    """Raised when a published package would leak a denied hostname."""


def denied_host_token(host: str) -> str:
    """Return one constant placeholder carrying no attacker-controlled bits."""

    del host
    return DENIED_HOST_PLACEHOLDER


def publish_allowed_host(host: str, allowlist: Mapping[str, Any]) -> str:
    """Return an allowlisted name, or the parent suffix, never extra labels."""

    if host == DENIED_HOST_PLACEHOLDER:
        return host
    try:
        candidate = normalize_host(host)
    except EgressPolicyError:
        return DENIED_HOST_PLACEHOLDER
    exact = _normalized_allowlist_names(allowlist, "hosts")
    if candidate in exact:
        return candidate
    parents = sorted(
        (_normalized_allowlist_names(allowlist, "subdomain_suffixes")),
        key=len,
        reverse=True,
    )
    for parent in parents:
        if candidate.endswith(f".{parent}"):
            return f"*.{parent}"
    return DENIED_HOST_PLACEHOLDER


def publish_refused_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return one refusal with the CONNECT target replaced by a capped token."""

    host = record.get("host")
    recorded = host if isinstance(host, str) else ""
    return {
        "host": denied_host_token(recorded),
        "host_redacted": True,
        "port": record.get("port"),
        "reason": record.get("reason"),
    }


def publish_egress_evidence(
    accounted: AccountedEgress, allowlist: Mapping[str, Any]
) -> dict[str, Any]:
    """Return the sidecar evidence record with attacker-chosen names removed."""

    published_allowed = tuple(
        publish_allowed_host(host, allowlist) for host in accounted.allowed_hosts
    )
    if DENIED_HOST_PLACEHOLDER in published_allowed:
        raise PublicationError(
            "sidecar recorded an allowed host outside the declared allowlist"
        )
    allowed = tuple(dict.fromkeys(published_allowed))
    return {
        "allowed_hosts": list(allowed),
        "refused": [publish_refused_record(record) for record in accounted.refused],
        "decision_count": accounted.decision_count,
    }


def write_published_package(
    destination: Path,
    *,
    result_record: Mapping[str, Any],
    egress_evidence: Mapping[str, Any],
    fence: FenceObservation,
    allowlist: Mapping[str, Any] | None = None,
) -> tuple[Path, ...]:
    """Write result, proxy-log, and fence files with no raw denied hostnames."""

    if destination.exists():
        raise PublicationError(f"destination already exists: {destination}")
    try:
        accounted = parse_egress_evidence(egress_evidence)
    except EgressEvidenceError as exc:
        raise PublicationError(str(exc)) from exc
    resolved_allowlist = _mapping(
        allowlist if allowlist is not None else result_record.get("egress_allowlist")
    )
    canonical_allowlist = _parse_allowlist(resolved_allowlist).to_record()
    proxy_logs = publish_egress_evidence(accounted, canonical_allowlist)
    published_allowed_hosts = list(proxy_logs["allowed_hosts"])
    published_refused = list(proxy_logs["refused"])
    published_result = dict(result_record)
    published_result["egress_allowed_hosts"] = published_allowed_hosts
    published_result["egress_refused"] = published_refused
    published_result["egress_allowed_host_count"] = len(published_allowed_hosts)
    published_result["egress_refused_count"] = len(published_refused)
    published_result["egress_allowlist"] = canonical_allowlist
    fence_record = fence.to_record()
    require_honest_fence_record(fence_record)
    destination.mkdir(mode=0o700, parents=True)
    written = (
        _write_json(destination / RESULT_FILE_NAME, published_result),
        _write_json(destination / PROXY_LOGS_FILE_NAME, proxy_logs),
        _write_json(destination / FENCE_FILE_NAME, fence_record),
    )
    require_tree_omits(
        destination, _needles_from_accounted(accounted, canonical_allowlist)
    )
    validate_published_package(destination)
    return written


def require_tree_omits(root: Path, needles: Sequence[str]) -> None:
    """Refuse a published tree that still contains a denied hostname or label."""

    for path in _regular_files(root):
        payload = path.read_bytes()
        for needle in needles:
            encoded = needle.encode("utf-8")
            if encoded and encoded in payload:
                raise PublicationError(
                    f"published {path.name} contains a denied hostname"
                )


def require_published_refused_hosts_redacted(root: Path) -> None:
    """Refuse JSON whose refused-host fields are still raw DNS names."""

    for path in _regular_files(root):
        if path.suffix.lower() not in _JSON_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise PublicationError(f"{path.name} is not UTF-8 JSON") from exc
        if path.suffix.lower() == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    payload: object = json.loads(line)
                except ValueError as exc:
                    raise PublicationError(
                        f"{path.name}:{line_number} is not JSON"
                    ) from exc
                _require_refused_hosts_redacted(payload, path.name)
            continue
        try:
            decoded: object = json.loads(text)
        except ValueError as exc:
            raise PublicationError(f"{path.name} is not JSON") from exc
        _require_refused_hosts_redacted(decoded, path.name)


def validate_published_package(root: Path) -> None:
    """Validate a complete container-harness package before public intake."""

    require_published_refused_hosts_redacted(root)
    result_path = root / RESULT_FILE_NAME
    proxy_path = root / PROXY_LOGS_FILE_NAME
    fence_path = root / FENCE_FILE_NAME
    result = _optional_json_object(result_path)
    is_container_package = (
        proxy_path.exists()
        or fence_path.exists()
        or (
            result is not None
            and any(
                key in result
                for key in (
                    "egress_allowlist",
                    "egress_allowed_hosts",
                    "egress_refused",
                )
            )
        )
    )
    if not is_container_package:
        return
    missing = [
        path.name
        for path in (result_path, proxy_path, fence_path)
        if not path.is_file()
    ]
    if missing:
        raise PublicationError(
            "container-harness package is missing: " + ", ".join(missing)
        )
    result = _json_object(result_path)
    proxy = _json_object(proxy_path)
    fence = _json_object(fence_path)
    try:
        accounted = parse_egress_evidence(proxy)
        allowlist = _parse_allowlist(result.get("egress_allowlist"))
    except (EgressEvidenceError, EgressPolicyError) as exc:
        raise PublicationError(str(exc)) from exc
    _require_published_allowed_hosts(accounted.allowed_hosts, allowlist)
    for record in accounted.refused:
        if (
            record.get("host") != DENIED_HOST_PLACEHOLDER
            or record.get("host_redacted") is not True
        ):
            raise PublicationError("proxy-logs.json has an unredacted refused host")
    if result.get("egress_allowed_hosts") != list(accounted.allowed_hosts):
        raise PublicationError("result.json allowed hosts do not match proxy-logs.json")
    if result.get("egress_refused") != [dict(item) for item in accounted.refused]:
        raise PublicationError("result.json refusals do not match proxy-logs.json")
    _require_evidence_count(
        result,
        "egress_allowed_host_count",
        len(accounted.allowed_hosts),
    )
    _require_evidence_count(
        result,
        "egress_refused_count",
        len(accounted.refused),
    )
    try:
        require_honest_fence_record(fence)
    except ValueError as exc:
        raise PublicationError(str(exc)) from exc


def _require_refused_hosts_redacted(payload: object, origin: str) -> None:
    _walk_refused(payload, origin, under_refused=False)


def _require_evidence_count(
    result: Mapping[str, Any], field_name: str, expected: int
) -> None:
    if field_name not in result:
        raise PublicationError(f"result.json is missing {field_name}")
    value = result[field_name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise PublicationError(f"result.json {field_name} must be an integer")
    if value != expected:
        raise PublicationError(
            f"result.json {field_name} does not match proxy-logs.json"
        )


def _walk_refused(value: object, origin: str, *, under_refused: bool) -> None:
    if isinstance(value, Mapping):
        for key, child in cast(Mapping[str, object], value).items():
            key_name = str(key)
            nested = under_refused or key_name in _REFUSED_KEYS
            if under_refused and key_name == "host":
                if not isinstance(child, str) or child != DENIED_HOST_PLACEHOLDER:
                    raise PublicationError(f"{origin} has an unredacted refused host")
            _walk_refused(child, origin, under_refused=nested)
        return
    if isinstance(value, list):
        for child in cast(list[object], value):
            _walk_refused(child, origin, under_refused=under_refused)


def _needles_from_accounted(
    accounted: AccountedEgress, allowlist: Mapping[str, Any]
) -> tuple[str, ...]:
    allowlist_labels = _allowlist_labels(allowlist)
    needles: list[str] = []
    for record in accounted.refused:
        host = record.get("host")
        if isinstance(host, str) and host and host != DENIED_HOST_PLACEHOLDER:
            needles.append(host)
            needles.extend(_attacker_labels(host, allowlist_labels))
    for host in accounted.allowed_hosts:
        if publish_allowed_host(host, allowlist) != host:
            needles.append(host)
            needles.extend(_attacker_labels(host, allowlist_labels))
    return tuple(dict.fromkeys(needle for needle in needles if needle))


def _allowlist_labels(allowlist: Mapping[str, Any]) -> set[str]:
    labels: set[str] = set()
    for field_name in ("hosts", "subdomain_suffixes"):
        for value in allowlist.get(field_name, ()):
            if isinstance(value, str):
                labels.update(part for part in value.lower().split(".") if part)
    return labels


def _attacker_labels(host: str, allowlist_labels: set[str]) -> tuple[str, ...]:
    return tuple(
        label
        for label in host.lower().split(".")
        if len(label) >= _ATTACKER_LABEL_MIN_LEN and label not in allowlist_labels
    )


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    return {}


def _normalized_allowlist_names(
    allowlist: Mapping[str, Any], field_name: str
) -> set[str]:
    names: set[str] = set()
    for value in allowlist.get(field_name, ()):
        if not isinstance(value, str):
            continue
        try:
            names.add(normalize_host(value.removeprefix("*.")))
        except EgressPolicyError:
            continue
    return names


def _parse_allowlist(value: object) -> EgressAllowlist:
    if not isinstance(value, Mapping):
        raise PublicationError("result.json egress_allowlist must be an object")
    record = cast(Mapping[str, object], value)
    expected = {"hosts", "subdomain_suffixes", "ports"}
    if set(record) != expected:
        raise PublicationError("result.json egress_allowlist has the wrong schema")
    hosts = _string_list(record["hosts"], "egress_allowlist.hosts")
    subdomains = _string_list(
        record["subdomain_suffixes"], "egress_allowlist.subdomain_suffixes"
    )
    ports_raw = record["ports"]
    if not isinstance(ports_raw, list):
        raise PublicationError("egress_allowlist.ports must be a list of integers")
    ports = cast(list[object], ports_raw)
    if any(isinstance(port, bool) or not isinstance(port, int) for port in ports):
        raise PublicationError("egress_allowlist.ports must be a list of integers")
    allowlist = EgressAllowlist.from_rules(
        hosts=hosts,
        subdomains=subdomains,
        ports=cast(list[int], ports),
    )
    if dict(record) != allowlist.to_record():
        raise PublicationError("result.json egress_allowlist is not canonical")
    return allowlist


def _require_published_allowed_hosts(
    hosts: Sequence[str], allowlist: EgressAllowlist
) -> None:
    for host in hosts:
        if host == DENIED_HOST_PLACEHOLDER:
            continue
        if host.startswith("*."):
            parent = host.removeprefix("*.")
            if parent in allowlist.subdomain_suffixes and host == f"*.{parent}":
                continue
        else:
            try:
                normalized = normalize_host(host)
            except EgressPolicyError:
                normalized = ""
            if host == normalized and normalized in allowlist.hosts:
                continue
        raise PublicationError("proxy-logs.json has an unredacted allowed host")


def _string_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise PublicationError(f"{field_name} must be a list of strings")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise PublicationError(f"{field_name} must be a list of strings")
    return cast(list[str], items)


def _optional_json_object(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    return _json_object(path)


def _json_object(path: Path) -> Mapping[str, Any]:
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise PublicationError(f"{path.name} is not UTF-8 JSON") from exc
    except ValueError as exc:
        raise PublicationError(f"{path.name} is not JSON") from exc
    if not isinstance(decoded, Mapping):
        raise PublicationError(f"{path.name} must be a JSON object")
    return cast(Mapping[str, Any], decoded)


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _regular_files(root: Path) -> tuple[Path, ...]:
    return tuple(path for path in sorted(root.rglob("*")) if path.is_file())
