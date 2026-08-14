"""Apply a Landlock filesystem scope, then replace this process."""

from __future__ import annotations

import ctypes
import json
import os
import stat
import sys
from typing import cast

_SYS_LANDLOCK_CREATE_RULESET = 444
_SYS_LANDLOCK_ADD_RULE = 445
_SYS_LANDLOCK_RESTRICT_SELF = 446
_LANDLOCK_CREATE_RULESET_VERSION = 1 << 0
_LANDLOCK_RULE_PATH_BENEATH = 1
_PR_SET_NO_NEW_PRIVS = 38
_FS_EXECUTE = 1 << 0
_FS_WRITE_FILE = 1 << 1
_FS_READ_FILE = 1 << 2
_FS_READ_DIR = 1 << 3
_FS_REMOVE_DIR = 1 << 4
_FS_REMOVE_FILE = 1 << 5
_FS_MAKE_CHAR = 1 << 6
_FS_MAKE_DIR = 1 << 7
_FS_MAKE_REG = 1 << 8
_FS_MAKE_SOCK = 1 << 9
_FS_MAKE_FIFO = 1 << 10
_FS_MAKE_BLOCK = 1 << 11
_FS_MAKE_SYM = 1 << 12
_FS_REFER = 1 << 13
_FS_TRUNCATE = 1 << 14
_FS_IOCTL_DEV = 1 << 15
_FS_READ = _FS_EXECUTE | _FS_READ_FILE | _FS_READ_DIR
_FS_ABI1 = (
    _FS_EXECUTE
    | _FS_WRITE_FILE
    | _FS_READ_FILE
    | _FS_READ_DIR
    | _FS_REMOVE_DIR
    | _FS_REMOVE_FILE
    | _FS_MAKE_CHAR
    | _FS_MAKE_DIR
    | _FS_MAKE_REG
    | _FS_MAKE_SOCK
    | _FS_MAKE_FIFO
    | _FS_MAKE_BLOCK
    | _FS_MAKE_SYM
)
_FS_FILE = _FS_EXECUTE | _FS_WRITE_FILE | _FS_READ_FILE | _FS_TRUNCATE | _FS_IOCTL_DEV
_MAX_RULES_BYTES = 65_536


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathBeneath(ctypes.Structure):
    # Packed landlock_path_beneath_attr: __u64 allowed_access + __s32 parent_fd.
    _layout_ = "ms"
    _pack_ = 1
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


def main() -> int:
    """Restrict filesystem access, then exec the contained command."""

    if len(sys.argv) < 5 or sys.argv[1] != "--rules":
        return 125
    try:
        separator = sys.argv.index("--", 3)
    except ValueError:
        return 125
    rules_path = sys.argv[2]
    command = sys.argv[separator + 1 :]
    if not rules_path or not command:
        return 125
    try:
        rules = _load_rules(rules_path)
        try:
            os.unlink(rules_path)
        except OSError:
            return 125
        _restrict(rules)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return 125
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.execvpe(command[0], command, os.environ)
    return 126


def _load_rules(path: str) -> dict[str, list[str]]:
    with open(path, "rb") as handle:
        payload = handle.read(_MAX_RULES_BYTES + 1)
    if len(payload) > _MAX_RULES_BYTES:
        raise ValueError("landlock rules are too large")
    decoded = cast(object, json.loads(payload.decode("utf-8")))
    if not isinstance(decoded, dict):
        raise ValueError("landlock rules must be an object")
    record = cast(dict[object, object], decoded)
    return {
        "read_paths": _string_list(record.get("read_paths")),
        "write_paths": _string_list(record.get("write_paths")),
    }


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("landlock path list is invalid")
    paths: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str) or not item or "\x00" in item:
            raise ValueError("landlock path is invalid")
        paths.append(item)
    return paths


def _handled_fs_bits(abi: int) -> int:
    handled = _FS_ABI1
    if abi >= 2:
        handled |= _FS_REFER
    if abi >= 3:
        handled |= _FS_TRUNCATE
    if abi >= 5:
        handled |= _FS_IOCTL_DEV
    return handled


def _restrict(rules: dict[str, list[str]]) -> None:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = int(
        libc.syscall(
            _SYS_LANDLOCK_CREATE_RULESET,
            None,
            0,
            _LANDLOCK_CREATE_RULESET_VERSION,
        )
    )
    if abi < 1:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset")
    handled = _handled_fs_bits(abi)
    attr = _RulesetAttr(handled)
    ruleset_fd = int(
        libc.syscall(
            _SYS_LANDLOCK_CREATE_RULESET,
            ctypes.byref(attr),
            ctypes.sizeof(attr),
            0,
        )
    )
    if ruleset_fd < 0:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset")
    try:
        for path in rules["read_paths"]:
            _add_path(libc, ruleset_fd, path, _FS_READ & handled)
        for path in rules["write_paths"]:
            _add_path(libc, ruleset_fd, path, handled)
        prctl = libc.prctl
        prctl.argtypes = [
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        prctl.restype = ctypes.c_int
        if int(prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
        if int(libc.syscall(_SYS_LANDLOCK_RESTRICT_SELF, ruleset_fd, 0)) != 0:
            raise OSError(ctypes.get_errno(), "landlock_restrict_self")
    finally:
        os.close(ruleset_fd)


def _add_path(
    libc: ctypes.CDLL,
    ruleset_fd: int,
    path: str,
    access: int,
) -> None:
    flags = os.O_PATH | os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        parent_fd = os.open(path, flags | nofollow)
    except OSError:
        parent_fd = os.open(path, flags)
    try:
        mode = os.fstat(parent_fd).st_mode
        if stat.S_ISREG(mode):
            access &= _FS_FILE
        if not access:
            raise OSError(0, "landlock path has no grantable access")
        rule = _PathBeneath(access, parent_fd)
        result = int(
            libc.syscall(
                _SYS_LANDLOCK_ADD_RULE,
                ruleset_fd,
                _LANDLOCK_RULE_PATH_BENEATH,
                ctypes.byref(rule),
                0,
            )
        )
        if result != 0:
            raise OSError(ctypes.get_errno(), "landlock_add_rule")
    finally:
        os.close(parent_fd)


def path_beneath_struct_size() -> int:
    """Return the packed ``landlock_path_beneath_attr`` byte size."""

    return int(ctypes.sizeof(_PathBeneath))


if __name__ == "__main__":
    raise SystemExit(main())
