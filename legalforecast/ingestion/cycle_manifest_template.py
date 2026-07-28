"""Render canonical acquisition-cycle configs from path-parameterized templates."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

from legalforecast.ingestion.cycle_orchestrator import (
    CONFIG_SCHEMA_VERSION,
    AcquisitionCycleConfig,
    CycleOrchestratorError,
    validate_cycle_config_bytes,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    canonical_json_bytes,
    read_unique_regular_file,
)

TEMPLATE_SCHEMA_VERSION = "legalforecast.acquisition_cycle_template.v1"
_TEMPLATE_FIELDS = frozenset(
    {"schema_version", "completion_mode", "variables", "config"}
)
_VARIABLE_NAME = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_PLACEHOLDER = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


class CycleManifestTemplateError(ValueError):
    """Raised when a cycle template or rendered config is unsafe."""


CycleArgumentValidator = Callable[[AcquisitionCycleConfig], None]


def render_cycle_config(
    *,
    template_path: Path,
    output_path: Path,
    variable_assignments: Sequence[str],
    argument_validator: CycleArgumentValidator | None = None,
) -> dict[str, object]:
    """Render, validate, and exclusively publish one canonical cycle config."""

    template = _read_template(template_path)
    completion_mode = template.get("completion_mode")
    if completion_mode not in {"corpus", "partial"}:
        raise CycleManifestTemplateError(
            "template completion_mode must be corpus or partial"
        )
    declared = _declared_variables(template)
    supplied = _parse_assignments(variable_assignments)
    if frozenset(supplied) != declared:
        missing = sorted(declared - frozenset(supplied))
        unexpected = sorted(frozenset(supplied) - declared)
        details: list[str] = []
        if missing:
            details.append(f"missing variables: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected variables: {', '.join(unexpected)}")
        raise CycleManifestTemplateError("; ".join(details))

    rendered = _substitute(template["config"], supplied)
    if not isinstance(rendered, Mapping):
        raise CycleManifestTemplateError("template config must be a JSON object")
    rendered_record = cast(Mapping[str, object], rendered)
    if rendered_record.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise CycleManifestTemplateError(
            "rendered config must use the acquisition-cycle v1 schema"
        )
    payload = canonical_json_bytes(rendered_record)
    config = _validate_and_publish(
        output_path,
        payload,
        argument_validator=argument_validator,
        require_finalization=completion_mode == "corpus",
    )
    return {
        "schema_version": "legalforecast.acquisition_cycle_render_receipt.v1",
        "template_path": str(template_path.absolute()),
        "template_sha256": hashlib.sha256(canonical_json_bytes(template)).hexdigest(),
        "output_path": str(output_path.absolute()),
        "output_sha256": config.config_sha256,
        "cycle_id": config.cycle_id,
        "eligibility_anchor": config.eligibility_anchor.isoformat(),
        "target_case_count": config.target_case_count,
        "stage_count": len(config.stages),
        "completion_mode": completion_mode,
        "corpus_finalization_planned": config.stages[-1].command == "finalize-corpus",
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }


def _read_template(path: Path) -> Mapping[str, object]:
    try:
        payload = read_unique_regular_file(path)
    except (OSError, ReviewBundleError) as exc:
        raise CycleManifestTemplateError(str(exc)) from exc
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CycleManifestTemplateError(
            "cycle template must be valid UTF-8 JSON"
        ) from exc
    if not isinstance(raw, Mapping):
        raise CycleManifestTemplateError("cycle template must be a JSON object")
    template = cast(Mapping[str, object], raw)
    if canonical_json_bytes(template) != payload:
        raise CycleManifestTemplateError("cycle template must use canonical JSON bytes")
    if frozenset(template) != _TEMPLATE_FIELDS:
        raise CycleManifestTemplateError(
            "cycle template fields differ from the v1 schema"
        )
    if template.get("schema_version") != TEMPLATE_SCHEMA_VERSION:
        raise CycleManifestTemplateError("cycle template schema_version is unsupported")
    return template


def _declared_variables(template: Mapping[str, object]) -> frozenset[str]:
    raw = template.get("variables")
    if not isinstance(raw, list):
        raise CycleManifestTemplateError("template variables must be a JSON list")
    variables: list[str] = []
    for value in cast(list[object], raw):
        if not isinstance(value, str) or not _VARIABLE_NAME.fullmatch(value):
            raise CycleManifestTemplateError(
                "template variable names must use uppercase safe-name characters"
            )
        variables.append(value)
    if len(variables) != len(set(variables)):
        raise CycleManifestTemplateError("template variable names must be unique")
    used = frozenset(_collect_placeholders(template.get("config")))
    declared = frozenset(variables)
    if used != declared:
        missing = sorted(declared - used)
        undeclared = sorted(used - declared)
        details: list[str] = []
        if missing:
            details.append(f"unused variables: {', '.join(missing)}")
        if undeclared:
            details.append(f"undeclared placeholders: {', '.join(undeclared)}")
        raise CycleManifestTemplateError("; ".join(details))
    return declared


def _collect_placeholders(value: object) -> list[str]:
    if isinstance(value, str):
        return _PLACEHOLDER.findall(value)
    if isinstance(value, list):
        return [
            name
            for item in cast(list[object], value)
            for name in _collect_placeholders(item)
        ]
    if isinstance(value, Mapping):
        return [
            name
            for item in cast(Mapping[str, object], value).values()
            for name in _collect_placeholders(item)
        ]
    return []


def _parse_assignments(values: Sequence[str]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for value in values:
        name, separator, raw_path = value.partition("=")
        if (
            not separator
            or not _VARIABLE_NAME.fullmatch(name)
            or not raw_path
            or name in assignments
        ):
            raise CycleManifestTemplateError(
                "each --variable must be a unique NAME=/absolute/path assignment"
            )
        path = Path(raw_path)
        if not path.is_absolute():
            raise CycleManifestTemplateError(
                f"template variable {name} must be an absolute path"
            )
        assignments[name] = str(path)
    return assignments


def _substitute(value: object, assignments: Mapping[str, str]) -> object:
    if isinstance(value, str):
        rendered = _PLACEHOLDER.sub(lambda match: assignments[match.group(1)], value)
        if "${" in rendered:
            raise CycleManifestTemplateError(
                "template contains a malformed or unresolved placeholder"
            )
        return rendered
    if isinstance(value, list):
        return [_substitute(item, assignments) for item in cast(list[object], value)]
    if isinstance(value, Mapping):
        return {
            key: _substitute(item, assignments)
            for key, item in cast(Mapping[str, object], value).items()
        }
    return value


def _validate_and_publish(
    output: Path,
    payload: bytes,
    *,
    argument_validator: CycleArgumentValidator | None,
    require_finalization: bool,
) -> AcquisitionCycleConfig:
    output = output.absolute()
    try:
        parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise CycleManifestTemplateError(
            f"output directory must already exist: {output.parent}"
        ) from exc
    if parent != output.parent:
        raise CycleManifestTemplateError(
            f"output directory must not contain symlinks: {output.parent}"
        )

    try:
        config = validate_cycle_config_bytes(payload, config_path=output)
    except CycleOrchestratorError as exc:
        raise CycleManifestTemplateError(str(exc)) from exc
    if argument_validator is not None:
        argument_validator(config)
    if require_finalization and config.stages[-1].command != "finalize-corpus":
        raise CycleManifestTemplateError(
            "corpus template must end with finalize-corpus"
        )

    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise CycleManifestTemplateError(
            "cycle config publication requires O_NOFOLLOW and O_DIRECTORY"
        )
    try:
        preopen_metadata = os.stat(parent, follow_symlinks=False)
    except OSError as exc:
        raise CycleManifestTemplateError(str(exc)) from exc
    if not stat.S_ISDIR(preopen_metadata.st_mode):
        raise CycleManifestTemplateError(
            f"output directory is not a directory: {parent}"
        )
    expected_parent_identity = (
        preopen_metadata.st_dev,
        preopen_metadata.st_ino,
    )
    staging_name = _staging_name(output.name, payload)
    parent_descriptor = -1
    staging_descriptor = -1
    staging_created = False
    try:
        parent_descriptor = os.open(
            parent,
            os.O_RDONLY | os.O_CLOEXEC | nofollow | directory,
        )
        _require_directory_identity(
            parent_descriptor,
            parent,
            expected_identity=expected_parent_identity,
        )
        staging_descriptor, staging_created = _open_locked_staging(
            parent_descriptor,
            staging_name,
            nofollow=nofollow,
        )
        _require_directory_identity(
            parent_descriptor,
            parent,
            expected_identity=expected_parent_identity,
        )
        _require_owned_staging_file(staging_descriptor, staging_name)

        existing = _read_published_output(
            parent_descriptor,
            output.name,
            nofollow=nofollow,
        )
        if existing is not None:
            output_metadata, output_payload = existing
            staging_metadata = os.fstat(staging_descriptor)
            if output_payload != payload:
                raise CycleManifestTemplateError(f"output already exists: {output}")
            if output_metadata.st_nlink == 1:
                _unlink_staging(
                    parent_descriptor,
                    staging_name,
                    staging_descriptor,
                )
            elif output_metadata.st_nlink == 2 and (
                output_metadata.st_dev,
                output_metadata.st_ino,
            ) == (staging_metadata.st_dev, staging_metadata.st_ino):
                _unlink_staging(
                    parent_descriptor,
                    staging_name,
                    staging_descriptor,
                )
            else:
                raise CycleManifestTemplateError(
                    "published cycle config is not a unique regular file"
                )
            os.fsync(parent_descriptor)
            _require_directory_identity(
                parent_descriptor,
                parent,
                expected_identity=expected_parent_identity,
            )
            _require_exact_published_output(
                parent_descriptor,
                output.name,
                payload,
                nofollow=nofollow,
            )
            return config

        if os.fstat(staging_descriptor).st_nlink != 1:
            raise CycleManifestTemplateError(
                "staged cycle config has unexpected hard links"
            )
        _write_staging_payload(staging_descriptor, payload)
        _require_directory_identity(
            parent_descriptor,
            parent,
            expected_identity=expected_parent_identity,
        )
        try:
            os.link(
                staging_name,
                output.name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            existing = _read_published_output(
                parent_descriptor,
                output.name,
                nofollow=nofollow,
            )
            if existing is None or existing[1] != payload:
                raise CycleManifestTemplateError(
                    f"output already exists: {output}"
                ) from exc
        _require_linked_output(
            parent_descriptor,
            output.name,
            staging_descriptor,
            payload,
            nofollow=nofollow,
        )
        _unlink_staging(parent_descriptor, staging_name, staging_descriptor)
        os.fsync(parent_descriptor)
        _require_directory_identity(
            parent_descriptor,
            parent,
            expected_identity=expected_parent_identity,
        )
        _require_exact_published_output(
            parent_descriptor,
            output.name,
            payload,
            nofollow=nofollow,
        )
    except (CycleManifestTemplateError, OSError) as exc:
        if staging_descriptor >= 0 and parent_descriptor >= 0:
            try:
                staging_metadata = os.fstat(staging_descriptor)
                if staging_created or staging_metadata.st_nlink == 1:
                    _unlink_staging(
                        parent_descriptor,
                        staging_name,
                        staging_descriptor,
                    )
            except (CycleManifestTemplateError, OSError):
                pass
        raise CycleManifestTemplateError(str(exc)) from exc
    finally:
        if staging_descriptor >= 0:
            os.close(staging_descriptor)
        if parent_descriptor >= 0:
            os.close(parent_descriptor)
    return config


def _staging_name(output_name: str, payload: bytes) -> str:
    identity = hashlib.sha256(output_name.encode("utf-8") + b"\0" + payload).hexdigest()
    return f".lfb-cycle-{identity}.partial"


def _require_directory_identity(
    descriptor: int,
    path: Path,
    *,
    expected_identity: tuple[int, int],
) -> None:
    descriptor_stat = os.fstat(descriptor)
    path_stat = os.stat(path, follow_symlinks=False)
    if (
        not stat.S_ISDIR(descriptor_stat.st_mode)
        or not stat.S_ISDIR(path_stat.st_mode)
        or (descriptor_stat.st_dev, descriptor_stat.st_ino) != expected_identity
        or (path_stat.st_dev, path_stat.st_ino) != expected_identity
        or (descriptor_stat.st_dev, descriptor_stat.st_ino)
        != (path_stat.st_dev, path_stat.st_ino)
    ):
        raise CycleManifestTemplateError(
            f"output directory identity changed during publication: {path}"
        )


def _require_owned_staging_file(descriptor: int, staging_name: str) -> None:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink not in {1, 2}
    ):
        raise CycleManifestTemplateError(
            f"unsafe staged cycle config residue: {staging_name}"
        )


def _open_locked_staging(
    parent_descriptor: int,
    staging_name: str,
    *,
    nofollow: int,
) -> tuple[int, bool]:
    while True:
        created = False
        try:
            descriptor = os.open(
                staging_name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | nofollow,
                0o600,
                dir_fd=parent_descriptor,
            )
            created = True
            os.fchmod(descriptor, 0o600)
        except FileExistsError:
            descriptor = os.open(
                staging_name,
                os.O_RDWR | os.O_CLOEXEC | nofollow,
                dir_fd=parent_descriptor,
            )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        try:
            path_metadata = os.stat(
                staging_name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            os.close(descriptor)
            continue
        descriptor_metadata = os.fstat(descriptor)
        if (path_metadata.st_dev, path_metadata.st_ino) != (
            descriptor_metadata.st_dev,
            descriptor_metadata.st_ino,
        ):
            os.close(descriptor)
            continue
        return descriptor, created


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 1024 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def _write_staging_payload(descriptor: int, payload: bytes) -> None:
    os.ftruncate(descriptor, 0)
    os.lseek(descriptor, 0, os.SEEK_SET)
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written == 0:
            raise OSError("zero-byte write while staging cycle config")
        view = view[written:]
    os.fsync(descriptor)
    if _read_descriptor(descriptor) != payload:
        raise CycleManifestTemplateError("staged cycle config bytes differ after write")


def _read_published_output(
    parent_descriptor: int,
    output_name: str,
    *,
    nofollow: int,
) -> tuple[os.stat_result, bytes] | None:
    try:
        descriptor = os.open(
            output_name,
            os.O_RDONLY | os.O_CLOEXEC | nofollow,
            dir_fd=parent_descriptor,
        )
    except FileNotFoundError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise CycleManifestTemplateError(
                "published cycle config is not a regular file"
            )
        return metadata, _read_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _require_linked_output(
    parent_descriptor: int,
    output_name: str,
    staging_descriptor: int,
    payload: bytes,
    *,
    nofollow: int,
) -> None:
    existing = _read_published_output(
        parent_descriptor,
        output_name,
        nofollow=nofollow,
    )
    if existing is None:
        raise CycleManifestTemplateError("published cycle config disappeared")
    output_metadata, output_payload = existing
    staging_metadata = os.fstat(staging_descriptor)
    if (
        output_payload != payload
        or output_metadata.st_nlink != 2
        or staging_metadata.st_nlink != 2
        or (output_metadata.st_dev, output_metadata.st_ino)
        != (staging_metadata.st_dev, staging_metadata.st_ino)
    ):
        raise CycleManifestTemplateError(
            "published cycle config does not match its staged file"
        )


def _unlink_staging(
    parent_descriptor: int,
    staging_name: str,
    staging_descriptor: int,
) -> None:
    path_metadata = os.stat(
        staging_name,
        dir_fd=parent_descriptor,
        follow_symlinks=False,
    )
    descriptor_metadata = os.fstat(staging_descriptor)
    if (path_metadata.st_dev, path_metadata.st_ino) != (
        descriptor_metadata.st_dev,
        descriptor_metadata.st_ino,
    ):
        raise CycleManifestTemplateError(
            "staged cycle config identity changed before cleanup"
        )
    os.unlink(staging_name, dir_fd=parent_descriptor)


def _require_exact_published_output(
    parent_descriptor: int,
    output_name: str,
    payload: bytes,
    *,
    nofollow: int,
) -> None:
    existing = _read_published_output(
        parent_descriptor,
        output_name,
        nofollow=nofollow,
    )
    if existing is None or existing[0].st_nlink != 1 or existing[1] != payload:
        raise CycleManifestTemplateError(
            "published cycle config is not the expected unique regular file"
        )
