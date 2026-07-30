"""Wait for host attestation and environment delivery, then replace this process."""

from __future__ import annotations

import json
import os
import socket
import sys
from typing import cast

_MAX_CONTROL_MESSAGE_BYTES = 1_048_576


def main() -> int:
    """Run the private containment gate used by ``CommandAdapter``."""

    if len(sys.argv) < 7 or sys.argv[1] != "--socket" or sys.argv[3] != "--token":
        return 125
    try:
        separator = sys.argv.index("--", 5)
    except ValueError:
        return 125
    socket_address = sys.argv[2]
    if socket_address.startswith("@"):
        socket_address = "\0" + socket_address[1:]
    expected_token = sys.argv[4]
    command = sys.argv[separator + 1 :]
    if not expected_token or not command:
        return 125

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as control:
            control.connect(socket_address)
            handshake = json.dumps(
                {"token": expected_token, "pid": os.getpid()},
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
            control.sendall(handshake + b"\n")
            response = _read_control_line(control)
    except (OSError, UnicodeError, ValueError):
        return 125
    environment_raw = response.get("environment")
    if not isinstance(environment_raw, dict):
        return 125
    environment: dict[str, str] = {}
    for key, value in cast(dict[object, object], environment_raw).items():
        if (
            not isinstance(key, str)
            or not key
            or "=" in key
            or "\x00" in key
            or not isinstance(value, str)
            or "\x00" in value
        ):
            return 125
        environment[key] = value
    os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
    os.environ.pop("XDG_RUNTIME_DIR", None)
    os.environ.update(environment)
    os.execvpe(command[0], command, os.environ)
    return 126


def _read_control_line(control: socket.socket) -> dict[str, object]:
    payload = bytearray()
    while b"\n" not in payload:
        chunk = control.recv(65_536)
        if not chunk:
            raise ValueError("containment controller closed before release")
        payload.extend(chunk)
        if len(payload) > _MAX_CONTROL_MESSAGE_BYTES:
            raise ValueError("containment control message is too large")
    line, remainder = bytes(payload).split(b"\n", 1)
    if remainder:
        raise ValueError("containment controller sent trailing data")
    decoded = cast(object, json.loads(line))
    if not isinstance(decoded, dict):
        raise ValueError("containment control message must be an object")
    return cast(dict[str, object], decoded)


if __name__ == "__main__":
    raise SystemExit(main())
