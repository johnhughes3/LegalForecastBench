"""Allowlist HTTP CONNECT proxy for containerized agentic-CLI harness runs.

Standard library only, and no imports from the rest of ``legalforecast``: the
same file is unit-tested in-process on the host and bind-mounted alone into the
egress sidecar container, where ``python3 egress_proxy.py --allow-host ...``
runs it.  That dual use is why it carries a ``main`` and no package siblings.

Only ``CONNECT host:port`` is accepted; any other request line -- an absolute-URI
``GET`` on the plain-HTTP proxy port included -- is refused with 403 and
recorded, so a cleartext attempt is seen rather than escaping unseen.  The
allowlist decision is made on the request string before any DNS lookup or dial,
so a refused host is never resolved and never contacted.  After an allowlisted
CONNECT, the proxy peeks at the HTTP Host header and the TLS ClientHello SNI
and refuses a tunnel whose advertised name does not match the CONNECT target
(domain fronting).  TLS is not terminated: only the cleartext ClientHello is
parsed, peeked bytes are forwarded untouched on a match, and the offered SNI
or Host is never recorded -- only the authorized CONNECT name and the reason.
The refusal list is both the evidence that a run stayed inside its fence and
the discovery loop for a missing token-refresh endpoint: an OAuth session that
refreshes mid-run surfaces as a refusal naming the exact host to add to the
manifest allowlist.

Two limits, stated plainly.  Proxy environment variables steer only cooperating
clients, so the runtime that owns this proxy also puts the harness container on
a per-run Docker ``--internal`` network with no external route.  And nothing
here can constrain a *provider-side* web tool: a server-executed web search runs
on the provider's infrastructure, downstream of this fence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import selectors
import signal
import socket
import socketserver
import sys
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any, Final, cast

DEFAULT_ALLOWED_PORTS: Final[frozenset[int]] = frozenset({443})
MAX_REQUEST_HEADER_BYTES: Final[int] = 16 * 1024
RELAY_BUFFER_BYTES: Final[int] = 64 * 1024

REASON_HOST_NOT_ALLOWLISTED: Final[str] = "host_not_allowlisted"
REASON_PORT_NOT_ALLOWLISTED: Final[str] = "port_not_allowlisted"
REASON_METHOD_NOT_CONNECT: Final[str] = "method_not_connect"
REASON_MALFORMED_REQUEST: Final[str] = "malformed_request"
REASON_UPSTREAM_UNREACHABLE: Final[str] = "upstream_unreachable"
REASON_HOST_HEADER_MISMATCH: Final[str] = "host_header_mismatch"
REASON_SNI_MISMATCH: Final[str] = "sni_mismatch"
REASON_SNI_MISSING: Final[str] = "sni_missing"
MAX_TLS_RECORD_BYTES: Final[int] = 16 * 1024 + 256
_HTTP_METHODS: Final[tuple[bytes, ...]] = (
    b"GET ",
    b"POST ",
    b"HEAD ",
    b"PUT ",
    b"PATCH ",
    b"DELETE ",
    b"OPTIONS ",
)

_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_CONNECT_TARGET = re.compile(
    r"(?P<host>\[[0-9A-Fa-f:.]+\]|[^\s:]+):(?P<port>[0-9]{1,5})\Z"
)


class EgressPolicyError(ValueError):
    """Raised when an allowlist rule or CONNECT target is not usable."""


class _RefusedRequest(Exception):
    """Internal carrier for the closed refusal reason of a bad request line."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def normalize_host(value: str) -> str:
    """Return a lowercase, dot-stripped DNS name, or fail with the reason why.

    Normalization is deliberately strict rather than forgiving: a rule that
    cannot be reduced to plain ASCII DNS labels would be matched against
    attacker-influenced text later, and a silently accepted odd rule is exactly
    how a suffix match turns into a substring match.
    """

    candidate = value.strip().rstrip(".").lower()
    if not candidate:
        raise EgressPolicyError("egress host must not be empty")
    if not candidate.isascii():
        raise EgressPolicyError(
            f"egress host must be ASCII (punycode an IDN first): {value!r}"
        )
    labels = candidate.split(".")
    if any(_LABEL.fullmatch(label) is None for label in labels):
        raise EgressPolicyError(f"egress host must be dotted DNS labels: {value!r}")
    return candidate


@dataclass(frozen=True, slots=True)
class EgressAllowlist:
    """The exact set of hosts and ports a harness container may reach."""

    hosts: frozenset[str]
    subdomain_suffixes: frozenset[str]
    ports: frozenset[int]

    @classmethod
    def from_rules(
        cls,
        hosts: Iterable[str] = (),
        subdomains: Iterable[str] = (),
        ports: Iterable[int] = DEFAULT_ALLOWED_PORTS,
    ) -> EgressAllowlist:
        """Build an allowlist from exact hosts, subdomain parents, and ports.

        ``hosts`` admit that name and nothing else.  ``subdomains`` admit only
        strictly-below names: an ``anthropic.com`` subdomain rule admits
        ``api.anthropic.com`` but neither ``anthropic.com`` itself nor
        ``notanthropic.com``.  Wildcards are opt-in precisely because a careless
        suffix rule is how ``api.example.com.evil.tld`` gets in.
        """

        exact = frozenset(normalize_host(rule) for rule in hosts)
        parents = frozenset(
            normalize_host(rule.removeprefix("*.")) for rule in subdomains
        )
        allowed_ports = frozenset(ports)
        if not exact and not parents:
            raise EgressPolicyError(
                "egress allowlist must declare at least one host or subdomain rule; "
                "an empty allowlist would refuse the provider API itself"
            )
        if not allowed_ports:
            raise EgressPolicyError("egress allowlist must declare at least one port")
        for port in sorted(allowed_ports):
            if not 1 <= port <= 65535:
                raise EgressPolicyError(f"egress port out of range: {port}")
        return cls(hosts=exact, subdomain_suffixes=parents, ports=allowed_ports)

    def permits(self, host: str, port: int) -> str | None:
        """Return a refusal reason, or ``None`` when the target is admitted."""

        try:
            candidate = normalize_host(host)
        except EgressPolicyError:
            return REASON_HOST_NOT_ALLOWLISTED
        matched = candidate in self.hosts or any(
            candidate.endswith(f".{parent}") for parent in self.subdomain_suffixes
        )
        if not matched:
            return REASON_HOST_NOT_ALLOWLISTED
        if port not in self.ports:
            return REASON_PORT_NOT_ALLOWLISTED
        return None

    def to_record(self) -> dict[str, Any]:
        """Return the declared rules, for the run record."""

        return {
            "hosts": sorted(self.hosts),
            "subdomain_suffixes": sorted(self.subdomain_suffixes),
            "ports": sorted(self.ports),
        }


@dataclass(frozen=True, slots=True)
class EgressDecision:
    """One allow-or-refuse decision, with no payload and no headers."""

    host: str
    port: int
    reason: str | None

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-ready decision record."""
        return {"host": self.host, "port": self.port, "reason": self.reason}


class EgressEvidence:
    """Thread-safe accumulator for what a run reached and what it was refused."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._decisions: list[EgressDecision] = []

    def record(self, host: str, port: int, reason: str | None) -> None:
        """Record one decision."""

        with self._lock:
            self._decisions.append(EgressDecision(host=host, port=port, reason=reason))

    def decisions(self) -> tuple[EgressDecision, ...]:
        """Return every decision in arrival order."""

        with self._lock:
            return tuple(self._decisions)

    def allowed_hosts(self) -> tuple[str, ...]:
        """Return the distinct hosts this run was allowed to reach."""

        return tuple(sorted({d.host for d in self.decisions() if d.reason is None}))

    def refused(self) -> tuple[EgressDecision, ...]:
        """Return the distinct refusals, sorted for a stable run record."""

        seen: dict[tuple[str, int, str], EgressDecision] = {}
        for decision in self.decisions():
            if decision.reason is None:
                continue
            seen.setdefault((decision.host, decision.port, decision.reason), decision)
        return tuple(seen[key] for key in sorted(seen))

    def to_record(self) -> dict[str, Any]:
        """Return the host-path-free evidence record for one run."""

        return {
            "allowed_hosts": list(self.allowed_hosts()),
            "refused": [decision.to_record() for decision in self.refused()],
            "decision_count": len(self.decisions()),
        }


class _ProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        allowlist: EgressAllowlist,
        evidence: EgressEvidence,
        dial_timeout: float,
        idle_timeout: float,
        evidence_path: Path | None,
    ) -> None:
        self.allowlist = allowlist
        self.evidence = evidence
        self.dial_timeout = dial_timeout
        self.idle_timeout = idle_timeout
        self.evidence_path = evidence_path
        # Handlers run on their own threads, and every one of them rewrites the
        # evidence file; without this the concurrent temp-file writes interleave.
        self.evidence_write_lock = threading.Lock()
        super().__init__(address, _ConnectHandler)

    def note(self, host: str, port: int, reason: str | None) -> None:
        """Record a decision and refresh the on-disk evidence file, if any."""

        self.evidence.record(host, port, reason)
        if self.evidence_path is not None:
            with self.evidence_write_lock:
                write_evidence(self.evidence_path, self.evidence)


class _ConnectHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = cast("_ProxyServer", self.server)
        client = cast(socket.socket, self.request)
        client.settimeout(server.idle_timeout)
        try:
            head = _read_request_head(client)
            host, port = _parse_connect_target(head)
            connect_host_header = _ascii_headers(head).get("host")
        except _RefusedRequest as exc:
            server.note("", 0, exc.reason)
            _respond(client, 403, "Forbidden", exc.reason)
            return
        except OSError:
            server.note("", 0, REASON_MALFORMED_REQUEST)
            return
        reason = server.allowlist.permits(host, port)
        if reason is not None:
            server.note(host, port, reason)
            _respond(client, 403, "Forbidden", reason)
            return
        if connect_host_header is not None and not _names_match(
            connect_host_header, host
        ):
            server.note(host, port, REASON_HOST_HEADER_MISMATCH)
            _respond(client, 403, "Forbidden", REASON_HOST_HEADER_MISMATCH)
            return
        try:
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            peeked, bind_reason = _peek_tunneled_name(client, host)
        except _RefusedRequest as exc:
            server.note(host, port, exc.reason)
            return
        except OSError:
            server.note(host, port, REASON_MALFORMED_REQUEST)
            return
        if bind_reason is not None:
            server.note(host, port, bind_reason)
            return
        try:
            upstream = socket.create_connection(
                (host, port), timeout=server.dial_timeout
            )
        except OSError:
            server.note(host, port, REASON_UPSTREAM_UNREACHABLE)
            return
        try:
            if peeked:
                try:
                    upstream.sendall(peeked)
                except OSError:
                    return
            server.note(host, port, None)
            _relay(client, upstream, server.idle_timeout)
        finally:
            upstream.close()


def _read_request_head(client: socket.socket) -> bytes:
    """Read raw bytes up to the end of the request head, bounded."""

    buffer = bytearray()
    while b"\r\n\r\n" not in buffer:
        if len(buffer) > MAX_REQUEST_HEADER_BYTES:
            raise _RefusedRequest(REASON_MALFORMED_REQUEST)
        chunk = client.recv(4096)
        if not chunk:
            raise _RefusedRequest(REASON_MALFORMED_REQUEST)
        buffer.extend(chunk)
    return bytes(buffer)


def _parse_connect_target(head: bytes) -> tuple[str, int]:
    """Return the CONNECT host and port, refusing every other request form."""

    request_line = head.split(b"\r\n", 1)[0]
    try:
        decoded = request_line.decode("ascii")
    except UnicodeDecodeError as exc:
        raise _RefusedRequest(REASON_MALFORMED_REQUEST) from exc
    parts = decoded.split(" ")
    if len(parts) != 3:
        raise _RefusedRequest(REASON_MALFORMED_REQUEST)
    if parts[0].upper() != "CONNECT":
        raise _RefusedRequest(REASON_METHOD_NOT_CONNECT)
    match = _CONNECT_TARGET.fullmatch(parts[1])
    if match is None:
        raise _RefusedRequest(REASON_MALFORMED_REQUEST)
    port = int(match.group("port"))
    if not 1 <= port <= 65535:
        raise _RefusedRequest(REASON_MALFORMED_REQUEST)
    return match.group("host"), port


def _ascii_headers(head: bytes) -> dict[str, str]:
    """Return lower-cased header names from a request head."""

    headers: dict[str, str] = {}
    for line in head.split(b"\r\n")[1:]:
        if line == b"":
            break
        if b":" not in line:
            raise _RefusedRequest(REASON_MALFORMED_REQUEST)
        name, value = line.split(b":", 1)
        try:
            key = name.decode("ascii").strip().lower()
            parsed = value.decode("ascii").strip()
        except UnicodeDecodeError as exc:
            raise _RefusedRequest(REASON_MALFORMED_REQUEST) from exc
        if key in headers and headers[key] != parsed:
            reason = (
                REASON_HOST_HEADER_MISMATCH
                if key == "host"
                else REASON_MALFORMED_REQUEST
            )
            raise _RefusedRequest(reason)
        headers[key] = parsed
    return headers


def _names_match(left: str, right: str) -> bool:
    """Return True when two hostnames name the same target, ignoring case/port."""

    return _canonical_name(left) == _canonical_name(right) and bool(
        _canonical_name(left)
    )


def _canonical_name(value: str) -> str:
    candidate = value.strip().rstrip(".").lower()
    if candidate.startswith("["):
        end = candidate.find("]")
        return candidate[1:end] if end != -1 else candidate
    if candidate.count(":") == 1:
        host, port = candidate.rsplit(":", 1)
        if port.isdigit():
            return host
    return candidate


def _recv_exact(client: socket.socket, size: int) -> bytes:
    buffer = bytearray()
    while len(buffer) < size:
        chunk = client.recv(size - len(buffer))
        if not chunk:
            raise _RefusedRequest(REASON_MALFORMED_REQUEST)
        buffer.extend(chunk)
    return bytes(buffer)


def _peek_tunneled_name(
    client: socket.socket, authorized_host: str
) -> tuple[bytes, str | None]:
    """Peek TLS SNI or HTTP Host; return (buffered bytes, refusal or None)."""

    first = client.recv(1)
    if not first:
        return b"", REASON_SNI_MISSING
    if first == b"\x16":
        header_rest = _recv_exact(client, 4)
        record_len = int.from_bytes(header_rest[2:4], "big")
        if record_len < 4 or record_len > MAX_TLS_RECORD_BYTES:
            return first + header_rest, REASON_MALFORMED_REQUEST
        body = _recv_exact(client, record_len)
        record = first + header_rest + body
        sni = _tls_client_hello_sni(record)
        if sni is None:
            return record, REASON_SNI_MISSING
        if not _names_match(sni, authorized_host):
            return record, REASON_SNI_MISMATCH
        return record, None
    buffer = bytearray(first)
    while b"\r\n\r\n" not in buffer:
        if len(buffer) > MAX_REQUEST_HEADER_BYTES:
            return bytes(buffer), REASON_MALFORMED_REQUEST
        chunk = client.recv(4096)
        if not chunk:
            break
        buffer.extend(chunk)
    data = bytes(buffer)
    if not data.startswith(_HTTP_METHODS):
        return data, REASON_MALFORMED_REQUEST
    try:
        headers = _ascii_headers(data)
    except _RefusedRequest as exc:
        return data, exc.reason
    offered = headers.get("host")
    if offered is None or not _names_match(offered, authorized_host):
        return data, REASON_HOST_HEADER_MISMATCH
    return data, None


def _tls_client_hello_sni(record: bytes) -> str | None:
    """Return the SNI hostname from a TLS handshake record, or None."""

    if len(record) < 5 or record[0] != 0x16:
        return None
    rec_len = int.from_bytes(record[3:5], "big")
    handshake = record[5 : 5 + rec_len]
    if len(handshake) != rec_len or rec_len < 4 or handshake[0] != 0x01:
        return None
    hs_len = int.from_bytes(handshake[1:4], "big")
    body = handshake[4 : 4 + hs_len]
    if len(body) != hs_len or len(body) < 35:
        return None
    offset = 34
    sid_len = body[offset]
    offset += 1 + sid_len
    if offset + 2 > len(body):
        return None
    cipher_len = int.from_bytes(body[offset : offset + 2], "big")
    offset += 2 + cipher_len
    if offset + 1 > len(body):
        return None
    compression_len = body[offset]
    offset += 1 + compression_len
    if offset == len(body):
        return None
    if offset + 2 > len(body):
        return None
    ext_len = int.from_bytes(body[offset : offset + 2], "big")
    offset += 2
    end = offset + ext_len
    if end > len(body):
        return None
    sni: str | None = None
    while offset + 4 <= end:
        ext_type = int.from_bytes(body[offset : offset + 2], "big")
        ext_len_one = int.from_bytes(body[offset + 2 : offset + 4], "big")
        offset += 4
        if offset + ext_len_one > end:
            return None
        data = body[offset : offset + ext_len_one]
        offset += ext_len_one
        if ext_type != 0:
            continue
        parsed = _parse_sni_extension(data)
        if parsed is None:
            return None
        sni = parsed
    return sni


def _parse_sni_extension(data: bytes) -> str | None:
    if len(data) < 2:
        return None
    list_len = int.from_bytes(data[:2], "big")
    if list_len != len(data) - 2:
        return None
    offset = 2
    names: list[str] = []
    while offset < len(data):
        if offset + 3 > len(data):
            return None
        name_type = data[offset]
        name_len = int.from_bytes(data[offset + 1 : offset + 3], "big")
        offset += 3
        if offset + name_len > len(data):
            return None
        raw = data[offset : offset + name_len]
        offset += name_len
        if name_type != 0:
            continue
        try:
            names.append(raw.decode("ascii"))
        except UnicodeDecodeError:
            return None
    if len(names) != 1:
        return None
    return names[0]


def _respond(client: socket.socket, status: int, phrase: str, reason: str) -> None:
    body = f"{reason}\n".encode("ascii")
    head = (
        f"HTTP/1.1 {status} {phrase}\r\n"
        "Content-Type: text/plain; charset=us-ascii\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    try:
        client.sendall(head + body)
    except OSError:
        return


def _relay(client: socket.socket, upstream: socket.socket, idle_timeout: float) -> None:
    """Pump opaque bytes both ways until either side closes or goes idle."""

    client.settimeout(None)
    upstream.settimeout(None)
    selector = selectors.DefaultSelector()
    selector.register(client, selectors.EVENT_READ, upstream)
    selector.register(upstream, selectors.EVENT_READ, client)
    try:
        while True:
            events = selector.select(timeout=idle_timeout)
            if not events:
                return
            for key, _ in events:
                source = key.fileobj
                target = cast(socket.socket, key.data)
                if not isinstance(source, socket.socket):
                    return
                try:
                    chunk = source.recv(RELAY_BUFFER_BYTES)
                except OSError:
                    return
                if not chunk:
                    return
                try:
                    target.sendall(chunk)
                except OSError:
                    return
    finally:
        selector.close()


class AllowlistConnectProxy:
    """A running CONNECT proxy bound to an ephemeral port by default."""

    def __init__(
        self,
        allowlist: EgressAllowlist,
        *,
        bind_host: str = "127.0.0.1",
        bind_port: int = 0,
        dial_timeout: float = 10.0,
        idle_timeout: float = 300.0,
        evidence_path: Path | None = None,
    ) -> None:
        self.evidence = EgressEvidence()
        self._server = _ProxyServer(
            (bind_host, bind_port),
            allowlist,
            self.evidence,
            dial_timeout,
            idle_timeout,
            evidence_path,
        )
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        """Return the real bound port, which is never a fixed well-known one."""
        return int(self._server.server_address[1])

    @property
    def bind_host(self) -> str:
        """Return the bound address."""
        return str(self._server.server_address[0])

    def start(self) -> AllowlistConnectProxy:
        """Start serving on a background daemon thread."""

        if self._thread is not None:
            raise RuntimeError("proxy is already started")
        thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        return self

    def stop(self) -> None:
        """Stop serving and release the listening socket."""

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None

    def __enter__(self) -> AllowlistConnectProxy:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.stop()


def write_evidence(path: Path, evidence: EgressEvidence) -> None:
    """Atomically write the evidence record beside its final path."""

    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(evidence.to_record(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the parser for the standalone sidecar entry point."""

    parser = argparse.ArgumentParser(
        prog="egress-proxy",
        description="Allowlist CONNECT proxy for one containerized harness run.",
    )
    parser.add_argument("--allow-host", action="append", default=[], metavar="HOST")
    parser.add_argument("--allow-subdomains", action="append", default=[])
    parser.add_argument("--allow-port", action="append", type=int, default=[])
    parser.add_argument("--bind", default="0.0.0.0", metavar="ADDRESS")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--evidence-file", type=Path, default=None)
    parser.add_argument("--idle-timeout", type=float, default=300.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the proxy in the foreground until SIGTERM or SIGINT.

    The sidecar binds ``0.0.0.0`` by default because both Docker networks it
    sits on are created per run and hold nothing but this container and the
    harness, so there is no wider surface to bind away from.  Host-side callers
    pass ``--bind 127.0.0.1``.
    """

    args = build_argument_parser().parse_args(argv)
    ports: Iterable[int] = args.allow_port or DEFAULT_ALLOWED_PORTS
    allowlist = EgressAllowlist.from_rules(
        hosts=args.allow_host, subdomains=args.allow_subdomains, ports=ports
    )
    proxy = AllowlistConnectProxy(
        allowlist,
        bind_host=args.bind,
        bind_port=args.port,
        idle_timeout=args.idle_timeout,
        evidence_path=args.evidence_file,
    )
    stopping = threading.Event()

    def _handle(_signum: int, _frame: FrameType | None) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    proxy.start()
    if args.evidence_file is not None:
        write_evidence(args.evidence_file, proxy.evidence)
    print(proxy.port, flush=True)
    try:
        stopping.wait()
    finally:
        proxy.stop()
        if args.evidence_file is not None:
            write_evidence(args.evidence_file, proxy.evidence)
    return 0


if __name__ == "__main__":
    sys.exit(main())
