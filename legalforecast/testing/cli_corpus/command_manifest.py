"""Structured command manifest generated from the live argparse tree."""

# pyright: reportPrivateUsage=false
from __future__ import annotations

import argparse
from collections.abc import Mapping
from typing import cast

from legalforecast.testing.cli_corpus.encode import encode_handler, encode_options
from legalforecast.testing.cli_corpus.paths import (
    MANIFEST_SCHEMA_VERSION,
    as_object_dict,
    as_object_list,
)


def build_command_manifest() -> dict[str, object]:
    """Return the reviewed command tree."""

    from legalforecast.cli import build_parser

    parser = build_parser()
    commands, _index = _walk_commands(parser, (), 1)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "prog": parser.prog,
        "bypasses": [],
        "commands": [
            _root_record(parser),
            *commands,
        ],
    }


def command_paths(manifest: Mapping[str, object]) -> tuple[tuple[str, ...], ...]:
    """Return every documented command path."""

    paths: list[tuple[str, ...]] = []
    for record in _records(manifest, "bypasses") + _records(manifest, "commands"):
        path = record.get("path")
        if path is None:
            continue
        try:
            parts = as_object_list(path)
        except ValueError:
            continue
        paths.append(tuple(str(part) for part in parts))
    return tuple(paths)


def handler_ids(manifest: Mapping[str, object]) -> tuple[str, ...]:
    """Return logical handler IDs in registration order."""

    ids: list[str] = []
    for record in _records(manifest, "bypasses") + _records(manifest, "commands"):
        handler_id = record.get("logical_handler_id")
        if isinstance(handler_id, str) and handler_id:
            ids.append(handler_id)
    return tuple(ids)


def _root_record(parser: argparse.ArgumentParser) -> dict[str, object]:
    return {
        "aliases": [],
        "group_dest": None,
        "handler": None,
        "logical_handler_id": "",
        "options": encode_options(parser),
        "path": [],
        "registration_index": 0,
    }


def _walk_commands(
    parser: argparse.ArgumentParser,
    path: tuple[str, ...],
    index: int,
) -> tuple[list[dict[str, object]], int]:
    records: list[dict[str, object]] = []
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        seen: dict[int, dict[str, object]] = {}
        name_map: dict[str, argparse.ArgumentParser] = {}
        parser_action = cast(argparse.Action, action)
        raw_map = cast(
            dict[object, object], getattr(parser_action, "_name_parser_map", {})
        )
        for raw_name, raw_child in raw_map.items():
            if isinstance(raw_name, str) and isinstance(
                raw_child, argparse.ArgumentParser
            ):
                name_map[raw_name] = raw_child
        for name, child in name_map.items():
            ident = id(child)
            existing = seen.get(ident)
            if existing is None:
                seen[ident] = {"name": name, "aliases": []}
            else:
                aliases = cast(list[str], existing["aliases"])
                aliases.append(name)
        for meta in seen.values():
            name = cast(str, meta["name"])
            child = name_map[name]
            command_path = (*path, name)
            handler = child._defaults.get("handler")
            records.append(
                {
                    "aliases": list(cast(list[str], meta["aliases"])),
                    "group_dest": action.dest,
                    "handler": encode_handler(handler),
                    "logical_handler_id": ".".join(command_path),
                    "options": encode_options(child),
                    "path": list(command_path),
                    "registration_index": index,
                }
            )
            index += 1
            nested, index = _walk_commands(child, command_path, index)
            records.extend(nested)
    return records, index


def _records(
    manifest: Mapping[str, object], field: str
) -> tuple[dict[str, object], ...]:
    raw = manifest.get(field)
    if raw is None:
        return ()
    try:
        items = as_object_list(raw)
    except ValueError:
        return ()
    records: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        records.append(as_object_dict(cast(object, item)))
    return tuple(records)
