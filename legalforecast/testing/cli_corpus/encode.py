"""JSON-safe encoding of argparse actions and callables."""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
from typing import cast

_ACTION_NAMES: dict[type[argparse.Action], str] = {
    argparse._StoreAction: "store",
    argparse._StoreConstAction: "store_const",
    argparse._StoreTrueAction: "store_true",
    argparse._StoreFalseAction: "store_false",
    argparse._AppendAction: "append",
    argparse._AppendConstAction: "append_const",
    argparse._CountAction: "count",
    argparse._HelpAction: "help",
    argparse._VersionAction: "version",
    argparse._SubParsersAction: "subparsers",
}


def encode_options(parser: argparse.ArgumentParser) -> list[dict[str, object]]:
    """Return registration-ordered options and positionals, excluding subparsers."""

    encoded: list[dict[str, object]] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            continue
        encoded.append(encode_action(action))
    return encoded


def encode_action(action: argparse.Action) -> dict[str, object]:
    """Encode one argparse action as a stable corpus record."""

    return {
        "action": _action_name(action),
        "choices": _encode_choices(action.choices),
        "default": encode_default(action.default),
        "dest": action.dest,
        "metavar": _encode_metavar(action.metavar),
        "nargs": _encode_nargs(action.nargs),
        "option_strings": list(action.option_strings),
        "required": bool(action.required),
        "type": encode_type(action.type),
    }


def encode_handler(handler: object) -> dict[str, str] | None:
    """Return inventory metadata for a command handler, if one is bound."""

    if handler is None or not callable(handler):
        return None
    module = getattr(handler, "__module__", None)
    name = getattr(handler, "__name__", None)
    qualname = getattr(handler, "__qualname__", None)
    if (
        not isinstance(module, str)
        or not isinstance(name, str)
        or not isinstance(qualname, str)
    ):
        return {"repr": repr(handler)}
    return {"module": module, "name": name, "qualname": qualname}


def encode_default(value: object) -> object:
    """Return a JSON-safe default, preserving suppress and Path values."""

    if value is argparse.SUPPRESS:
        return {"kind": "suppress"}
    if isinstance(value, Path):
        return {"kind": "path", "value": value.as_posix()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [encode_default(item) for item in cast(list[object], value)]
    if isinstance(value, tuple):
        return [encode_default(item) for item in cast(tuple[object, ...], value)]
    if callable(value) and not isinstance(value, type):
        encoded = encode_handler(value)
        return {"kind": "callable", **(encoded or {"repr": repr(value)})}
    return {"kind": "repr", "value": repr(value)}


def encode_type(value: object) -> str | None:
    """Return a stable type name for an argparse ``type=`` callable."""

    if value is None:
        return None
    if value is Path:
        return "pathlib.Path"
    if isinstance(value, type):
        module = value.__module__
        qualname = value.__qualname__
        if module in {"builtins", "typing"}:
            return qualname
        return f"{module}.{qualname}"
    encoded = encode_handler(value)
    if encoded is not None and "module" in encoded:
        return f"{encoded['module']}.{encoded['qualname']}"
    return repr(value)


def _action_name(action: argparse.Action) -> str:
    named = _ACTION_NAMES.get(type(action))
    if named is not None:
        return named
    return type(action).__name__


def _encode_nargs(nargs: object) -> object:
    if nargs is None or isinstance(nargs, (int, str)):
        return nargs
    return repr(nargs)


def _encode_metavar(metavar: object) -> object:
    if metavar is None or isinstance(metavar, str):
        return metavar
    if isinstance(metavar, tuple):
        return [str(item) for item in cast(tuple[object, ...], metavar)]
    return repr(metavar)


def _encode_choices(choices: object) -> list[object] | None:
    if choices is None:
        return None
    if isinstance(choices, (str, bytes)) or not isinstance(choices, Iterable):
        return [repr(choices)]
    encoded: list[object] = []
    for item in cast(Iterable[object], choices):
        if isinstance(item, (str, int, float, bool)) or item is None:
            encoded.append(item)
        else:
            encoded.append(str(item))
    return encoded
