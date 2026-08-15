"""Installed console-script identity for checkout, wheel, and sdist."""

from __future__ import annotations

import importlib
import importlib.metadata
import tarfile
import tomllib
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.testing.cli_corpus.paths import as_object_dict

ENTRY_POINTS: tuple[tuple[str, str], ...] = (
    ("legalforecast", "legalforecast.cli:main"),
    (
        "legalforecast-acquisition-systemd-run",
        "legalforecast.ingestion.infisical_systemd_launcher:main",
    ),
    (
        "legalforecast-provider-env-run",
        "legalforecast.labeling.provider_environment:main",
    ),
)
_ENTRY_POINT_NAMES = {name for name, _target in ENTRY_POINTS}


def checkout_entry_points() -> dict[str, str]:
    """Resolve the three installed scripts from the current environment."""

    group = importlib.metadata.entry_points(group="console_scripts")
    resolved = {
        entry.name: f"{entry.value}"
        for entry in group
        if entry.name in _ENTRY_POINT_NAMES
    }
    return dict(sorted(resolved.items()))


def resolve_entry_point_callables() -> dict[str, str]:
    """Import each installed script target and confirm the callable exists."""

    resolved: dict[str, str] = {}
    for name, target in ENTRY_POINTS:
        module_name, _, attribute = target.partition(":")
        module = importlib.import_module(module_name)
        callable_obj = getattr(module, attribute)
        if not callable(callable_obj):
            raise TypeError(f"{target} is not callable")
        resolved[name] = f"{callable_obj.__module__}:{callable_obj.__qualname__}"
    return resolved


def parse_entry_points_txt(text: str) -> dict[str, str]:
    """Parse a dist-info ``entry_points.txt`` console_scripts section."""

    resolved: dict[str, str] = {}
    section = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "console_scripts" or "=" not in line:
            continue
        name, _, target = line.partition("=")
        cleaned_name = name.strip()
        if cleaned_name in _ENTRY_POINT_NAMES:
            resolved[cleaned_name] = target.strip()
    return dict(sorted(resolved.items()))


def wheel_entry_points(wheel: Path) -> dict[str, str]:
    """Read console-script targets from a built wheel."""

    with zipfile.ZipFile(wheel) as archive:
        names = [
            member
            for member in archive.namelist()
            if member.endswith(".dist-info/entry_points.txt")
        ]
        if len(names) != 1:
            raise ValueError(f"expected one entry_points.txt in {wheel.name}")
        text = archive.read(names[0]).decode("utf-8")
    return parse_entry_points_txt(text)


def sdist_entry_points(sdist: Path) -> dict[str, str]:
    """Read console-script targets from a built sdist ``pyproject.toml``."""

    with tarfile.open(sdist, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if Path(member.name).name == "pyproject.toml"
        ]
        if not members:
            raise ValueError(f"sdist {sdist.name} has no pyproject.toml")
        extracted = archive.extractfile(members[0])
        if extracted is None:
            raise ValueError(f"sdist {sdist.name} pyproject.toml is unreadable")
        payload = tomllib.loads(extracted.read().decode("utf-8"))
        payload_object = as_object_dict(cast(object, payload))
    project = payload_object.get("project")
    if project is None:
        raise ValueError("sdist pyproject.toml is missing [project]")
    scripts = as_object_dict(project).get("scripts")
    if scripts is None:
        raise ValueError("sdist pyproject.toml is missing [project.scripts]")
    mapping: dict[str, str] = {}
    for name, target in as_object_dict(scripts).items():
        if name in _ENTRY_POINT_NAMES:
            mapping[name] = str(target)
    return dict(sorted(mapping.items()))


def expected_entry_points() -> dict[str, str]:
    """Return the reviewed mapping of script name to ``module:attr``."""

    return {name: target for name, target in ENTRY_POINTS}


def missing_entry_points(observed: Mapping[str, str]) -> tuple[str, ...]:
    """Return reviewed scripts that are absent or retargeted."""

    expected = expected_entry_points()
    missing = [
        name for name, target in expected.items() if observed.get(name) != target
    ]
    return tuple(missing)
