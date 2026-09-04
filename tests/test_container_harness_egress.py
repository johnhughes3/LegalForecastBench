"""Real-socket proof that the harness egress proxy allows and refuses correctly.

Nothing here is mocked: an origin server binds an ephemeral port, the proxy
binds another, and the assertions are made on bytes that crossed a socket.  The
refusal assertions additionally prove the *absence* of a dial by counting
accepts on a second origin server the allowlist does not name -- a proxy that
resolved and connected first and refused afterwards would fail that count.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from legalforecast.multiharness.container_harness.egress_proxy import (
    REASON_HOST_NOT_ALLOWLISTED,
    REASON_MALFORMED_REQUEST,
    REASON_METHOD_NOT_CONNECT,
    REASON_PORT_NOT_ALLOWLISTED,
    AllowlistConnectProxy,
    EgressAllowlist,
    EgressPolicyError,
    normalize_host,
)

_ORIGIN_REPLY = b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nORIGIN"

# Reviewed hostile CONNECT hosts: exact-suffix lookalikes, IP literals, IPv6,
# localhost, link-local metadata, percent-encoding, embedded @ and /, and
# empty/dot-odd names.  All must be refused against a provider allowlist before
# any dial.  Kept at 25 so a silent shrink of the table is a failed test.
HOSTILE_CONNECT_HOSTS: tuple[str, ...] = (
    "api.anthropic.com.evil.tld",
    "api.anthropicx.com",
    "notanthropic.com",
    "anthropic.com",
    "127.0.0.1",
    "0.0.0.0",
    "8.8.8.8",
    "169.254.169.254",
    "10.0.0.1",
    "192.168.0.1",
    "localhost",
    "[::1]",
    "[::ffff:127.0.0.1]",
    "api-anthropic.com",
    "api.anthropic.com%2eevil.tld",
    "user@api.anthropic.com",
    "api.anthropic.com/evil",
    "api..anthropic.com",
    ".anthropic.com",
    "courtlistener.com",
    "metadata.google.internal",
    "example.com",
    "api.anthropic.com.local",
    "256.1.1.1",
    "www.anthropic.com.attacker.test",
)

# Request lines that must never become a tunnel.  Each is a complete head so
# the proxy can refuse without waiting for a second packet.
MALFORMED_CONNECT_REQUESTS: tuple[bytes, ...] = (
    b"GET http://api.anthropic.com/ HTTP/1.1\r\n\r\n",
    b"POST / HTTP/1.1\r\n\r\n",
    b"HEAD api.anthropic.com:443 HTTP/1.1\r\n\r\n",
    b"CONNECT api.anthropic.com HTTP/1.1\r\n\r\n",
    b"CONNECT api.anthropic.com:443\r\n\r\n",
    b"CONNECT api.anthropic.com:99999 HTTP/1.1\r\n\r\n",
    b"CONNECT api.anthropic.com:0 HTTP/1.1\r\n\r\n",
    b"CONNECT  HTTP/1.1\r\n\r\n",
    b"\x80CONNECT api.anthropic.com:443 HTTP/1.1\r\n\r\n",
    b"CONNECT api.anthropic.com:443 HTTP/1.1 extra\r\n\r\n",
    b"OPTIONS * HTTP/1.1\r\n\r\n",
)


class _CountingOrigin:
    """A minimal TCP origin that records how many connections it accepted."""

    def __init__(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(8)
        self._socket.settimeout(0.2)
        self.port = int(self._socket.getsockname()[1])
        self.accepted = 0
        self.reply = _ORIGIN_REPLY
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                connection, _ = self._socket.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with self._lock:
                self.accepted += 1
            try:
                connection.recv(4096)
                connection.sendall(self.reply)
            except OSError:
                pass
            finally:
                connection.close()

    def close(self) -> None:
        self._stop.set()
        self._socket.close()
        self._thread.join(timeout=5.0)


@pytest.fixture
def origin() -> Iterator[_CountingOrigin]:
    server = _CountingOrigin()
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def unlisted_origin() -> Iterator[_CountingOrigin]:
    server = _CountingOrigin()
    try:
        yield server
    finally:
        server.close()


def _proxy_exchange(proxy_port: int, request: bytes, follow_up: bytes = b"") -> bytes:
    """Send raw bytes to the proxy and return everything it sent back."""

    with socket.create_connection(("127.0.0.1", proxy_port), timeout=10) as client:
        client.sendall(request)
        received = bytearray()
        if follow_up:
            header = bytearray()
            while b"\r\n\r\n" not in header:
                chunk = client.recv(4096)
                if not chunk:
                    return bytes(header)
                header.extend(chunk)
            received.extend(header)
            client.sendall(follow_up)
        client.settimeout(10)
        while True:
            try:
                chunk = client.recv(4096)
            except (TimeoutError, OSError):
                break
            if not chunk:
                break
            received.extend(chunk)
        return bytes(received)


def test_exact_rule_refuses_a_suffix_lookalike() -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["api.anthropic.com"])

    assert allowlist.permits("api.anthropic.com", 443) is None
    assert allowlist.permits("api.anthropic.com.evil.tld", 443) == (
        REASON_HOST_NOT_ALLOWLISTED
    )
    assert allowlist.permits("xapi.anthropic.com", 443) == REASON_HOST_NOT_ALLOWLISTED
    assert allowlist.permits("API.ANTHROPIC.COM.", 443) is None


def test_subdomain_rule_admits_only_strictly_below() -> None:
    allowlist = EgressAllowlist.from_rules(subdomains=["*.anthropic.com"])

    assert allowlist.permits("api.anthropic.com", 443) is None
    assert allowlist.permits("console.anthropic.com", 443) is None
    assert allowlist.permits("anthropic.com", 443) == REASON_HOST_NOT_ALLOWLISTED
    assert allowlist.permits("notanthropic.com", 443) == REASON_HOST_NOT_ALLOWLISTED
    assert allowlist.permits("api.anthropic.com.evil.tld", 443) == (
        REASON_HOST_NOT_ALLOWLISTED
    )


def test_port_outside_the_declared_set_is_refused() -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["api.anthropic.com"])

    assert allowlist.permits("api.anthropic.com", 443) is None
    assert allowlist.permits("api.anthropic.com", 8080) == REASON_PORT_NOT_ALLOWLISTED


def test_empty_allowlist_is_refused_at_construction() -> None:
    with pytest.raises(EgressPolicyError, match="at least one host or subdomain"):
        EgressAllowlist.from_rules()


def test_rules_must_be_ascii_dns_labels() -> None:
    with pytest.raises(EgressPolicyError, match="ASCII"):
        normalize_host("exämple.com")
    with pytest.raises(EgressPolicyError, match="dotted DNS labels"):
        normalize_host("api.anthropic.com:443")
    with pytest.raises(EgressPolicyError, match="dotted DNS labels"):
        normalize_host("-leading-dash.com")


def test_proxy_binds_a_real_ephemeral_port() -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["localhost"])
    with AllowlistConnectProxy(allowlist) as proxy:
        assert proxy.port > 0
        assert proxy.bind_host == "127.0.0.1"
        with socket.create_connection(("127.0.0.1", proxy.port), timeout=5) as probe:
            assert probe.getpeername()[1] == proxy.port


def test_proxy_tunnels_an_allowlisted_host_end_to_end(origin: _CountingOrigin) -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["localhost"], ports=[origin.port])
    with AllowlistConnectProxy(allowlist) as proxy:
        received = _proxy_exchange(
            proxy.port,
            f"CONNECT localhost:{origin.port} HTTP/1.1\r\n\r\n".encode("ascii"),
            follow_up=b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n",
        )

        assert received.startswith(b"HTTP/1.1 200 Connection Established\r\n")
        assert b"ORIGIN" in received
        assert origin.accepted == 1
        assert proxy.evidence.allowed_hosts() == ("localhost",)
        assert proxy.evidence.refused() == ()


def test_proxy_refuses_an_unlisted_host_without_dialing(
    origin: _CountingOrigin,
    unlisted_origin: _CountingOrigin,
) -> None:
    allowlist = EgressAllowlist.from_rules(
        hosts=["localhost"], ports=[origin.port, unlisted_origin.port]
    )
    with AllowlistConnectProxy(allowlist) as proxy:
        received = _proxy_exchange(
            proxy.port,
            f"CONNECT 127.0.0.1:{unlisted_origin.port} HTTP/1.1\r\n\r\n".encode(
                "ascii"
            ),
        )

        assert received.startswith(b"HTTP/1.1 403 Forbidden\r\n")
        assert REASON_HOST_NOT_ALLOWLISTED.encode("ascii") in received
        assert unlisted_origin.accepted == 0
        assert proxy.evidence.allowed_hosts() == ()
        refused = proxy.evidence.refused()
        assert len(refused) == 1
        assert refused[0].host == "127.0.0.1"
        assert refused[0].port == unlisted_origin.port
        assert refused[0].reason == REASON_HOST_NOT_ALLOWLISTED


def test_proxy_relays_a_payload_far_larger_than_one_buffer(
    origin: _CountingOrigin,
) -> None:
    """A staged case record is many buffers wide; prove the pump, not one recv."""

    payload = bytes(range(256)) * 4096
    origin.reply = payload
    allowlist = EgressAllowlist.from_rules(hosts=["localhost"], ports=[origin.port])
    with AllowlistConnectProxy(allowlist) as proxy:
        received = _proxy_exchange(
            proxy.port,
            f"CONNECT localhost:{origin.port} HTTP/1.1\r\n\r\n".encode("ascii"),
            follow_up=b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n",
        )

        body = received.split(b"\r\n\r\n", 1)[1]
        assert body == payload
        assert proxy.evidence.allowed_hosts() == ("localhost",)


def test_proxy_refuses_an_allowlisted_host_on_an_unlisted_port_without_dialing(
    origin: _CountingOrigin,
    unlisted_origin: _CountingOrigin,
) -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["localhost"], ports=[origin.port])
    with AllowlistConnectProxy(allowlist) as proxy:
        received = _proxy_exchange(
            proxy.port,
            f"CONNECT localhost:{unlisted_origin.port} HTTP/1.1\r\n\r\n".encode(
                "ascii"
            ),
        )

        assert received.startswith(b"HTTP/1.1 403 Forbidden\r\n")
        assert REASON_PORT_NOT_ALLOWLISTED.encode("ascii") in received
        assert unlisted_origin.accepted == 0
        assert [decision.reason for decision in proxy.evidence.refused()] == [
            REASON_PORT_NOT_ALLOWLISTED
        ]


def test_proxy_refuses_a_cleartext_get_and_records_it() -> None:
    allowlist = EgressAllowlist.from_rules(hosts=["localhost"])
    with AllowlistConnectProxy(allowlist) as proxy:
        received = _proxy_exchange(
            proxy.port,
            b"GET http://example.com/ HTTP/1.1\r\nHost: example.com\r\n\r\n",
        )

        assert received.startswith(b"HTTP/1.1 403 Forbidden\r\n")
        refused = proxy.evidence.refused()
        assert [decision.reason for decision in refused] == [REASON_METHOD_NOT_CONNECT]


def test_proxy_writes_evidence_for_every_decision(
    origin: _CountingOrigin,
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "egress-evidence.json"
    allowlist = EgressAllowlist.from_rules(hosts=["localhost"], ports=[origin.port])
    with AllowlistConnectProxy(allowlist, evidence_path=evidence_path) as proxy:
        _proxy_exchange(
            proxy.port,
            f"CONNECT localhost:{origin.port} HTTP/1.1\r\n\r\n".encode("ascii"),
            follow_up=b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n",
        )
        _proxy_exchange(
            proxy.port,
            f"CONNECT courtlistener.com:{origin.port} HTTP/1.1\r\n\r\n".encode("ascii"),
        )

    record = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert record["allowed_hosts"] == ["localhost"]
    assert record["refused"] == [
        {
            "host": "courtlistener.com",
            "port": origin.port,
            "reason": REASON_HOST_NOT_ALLOWLISTED,
        }
    ]
    assert record["decision_count"] == 2


def test_allowlist_record_is_deterministic() -> None:
    allowlist = EgressAllowlist.from_rules(
        hosts=["api.x.ai", "auth.x.ai"], subdomains=["anthropic.com"], ports=[443]
    )

    assert allowlist.to_record() == {
        "hosts": ["api.x.ai", "auth.x.ai"],
        "subdomain_suffixes": ["anthropic.com"],
        "ports": [443],
    }


def test_hostile_connect_host_table_stays_complete() -> None:
    assert len(HOSTILE_CONNECT_HOSTS) == 25
    assert len(set(HOSTILE_CONNECT_HOSTS)) == 25
    assert len(MALFORMED_CONNECT_REQUESTS) == 11


@pytest.mark.parametrize("host", HOSTILE_CONNECT_HOSTS)
def test_hostile_connect_hosts_are_refused_before_any_dial(host: str) -> None:
    allowlist = EgressAllowlist.from_rules(
        hosts=["api.anthropic.com"], subdomains=["anthropic.com"], ports=[443]
    )

    assert allowlist.permits(host, 443) == REASON_HOST_NOT_ALLOWLISTED


@pytest.mark.parametrize("request_bytes", MALFORMED_CONNECT_REQUESTS)
def test_malformed_request_lines_are_refused_on_the_wire(
    request_bytes: bytes,
    unlisted_origin: _CountingOrigin,
) -> None:
    allowlist = EgressAllowlist.from_rules(
        hosts=["api.anthropic.com"], ports=[unlisted_origin.port, 443]
    )
    with AllowlistConnectProxy(allowlist, dial_timeout=0.5) as proxy:
        received = _proxy_exchange(proxy.port, request_bytes)

    assert received.startswith(b"HTTP/1.1 403 Forbidden\r\n")
    assert unlisted_origin.accepted == 0
    assert (
        REASON_METHOD_NOT_CONNECT.encode("ascii") in received
        or REASON_MALFORMED_REQUEST.encode("ascii") in received
        or REASON_HOST_NOT_ALLOWLISTED.encode("ascii") in received
        or REASON_PORT_NOT_ALLOWLISTED.encode("ascii") in received
    )
