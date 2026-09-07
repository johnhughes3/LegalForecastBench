"""The closed-universe Harvey document workspace tools.

This module contains the tool semantics shared by the production worker image
and its protocol tests.  It intentionally has no access to a release object,
labels, provider credentials, or a host filesystem outside the three roots
passed by the container entrypoint.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from legalforecast.multiharness.tool_protocol import ToolRequest, ToolResponse

HARVEY_TOOL_NAMES = ("bash", "read", "write", "edit", "glob", "grep")
HARVEY_TOOL_POLICY = "harvey_closed_universe_v1"
MAX_TOOL_OUTPUT_BYTES = 512 * 1024
MAX_READ_BYTES = 512 * 1024
MAX_SEARCH_MATCHES = 10_000
BASH_TIMEOUT_SECONDS = 120


class HarveyToolError(ValueError):
    """A request violated the closed Harvey workspace contract."""


class HarveyToolExecutor:
    """Execute exactly the six Harvey tools inside an isolated workspace."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        documents_root: Path | None = None,
        output_root: Path | None = None,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.documents_root = (
            documents_root or self.workspace_root / "documents"
        ).resolve()
        self.output_root = (output_root or self.workspace_root / "output").resolve()
        self.documents_root.mkdir(parents=True, exist_ok=True)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._cwd = self.workspace_root

    def execute(self, request: ToolRequest, workspace: Path) -> ToolResponse:
        """Execute one request, returning typed errors without leaking paths."""

        if workspace.resolve() != self.workspace_root:
            raise HarveyToolError("tool workspace does not match executor root")
        from legalforecast.multiharness.tool_protocol import ToolResponse

        try:
            output = self.handle(request.operation, request.arguments)
            return ToolResponse(
                request_id=request.request_id, status="succeeded", output=output
            )
        except (
            HarveyToolError,
            OSError,
            UnicodeError,
            subprocess.SubprocessError,
        ) as exc:
            return ToolResponse(
                request_id=request.request_id,
                status="failed",
                error_code=_error_code(exc),
                output={},
            )

    def handle(self, operation: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Execute an operation for the standalone image entrypoint."""

        if operation not in HARVEY_TOOL_NAMES:
            raise HarveyToolError("unsupported Harvey tool")
        return getattr(self, f"_{operation}")(arguments)

    def close(self) -> None:
        """Close the persistent bash process."""

        # Bash calls are bounded subprocesses; cwd is carried across calls.
        return None

    def _bash(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        command = _required_string(arguments, "command")
        marker = f"__LFB_HARVEY_{os.urandom(10).hex()}__"
        script = f"{command}\nprintf '\\n{marker}:%s\\n' \"$PWD\""
        try:
            completed = subprocess.run(
                ("bash", "--noprofile", "--norc", "-c", script),
                cwd=self._cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=_safe_shell_environment(),
                timeout=BASH_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise HarveyToolError("bash command timed out") from exc
        output = completed.stdout
        marker_line = next(
            (
                line
                for line in output.splitlines()
                if line.startswith(marker.encode() + b":")
            ),
            None,
        )
        if marker_line is None:
            raise HarveyToolError("bash command did not report its working directory")
        cwd_text = marker_line[len(marker) + 1 :].strip().decode("utf-8")
        self._cwd = self._safe_workspace_directory(cwd_text)
        output = output.replace(marker_line, b"").strip(b"\n")
        if len(output) > MAX_TOOL_OUTPUT_BYTES:
            raise HarveyToolError("bash output exceeds the tool limit")
        return {
            "output": bytes(output).decode("utf-8", errors="replace"),
            "cwd": self._display_path(self._cwd),
        }

    def _read(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        path = self._read_path(_required_string(arguments, "file_path"))
        offset = _optional_nonnegative_int(arguments, "offset", default=0)
        limit = _optional_positive_int(arguments, "limit", default=MAX_READ_BYTES)
        selected_lines: list[str] = []
        output_bytes = 0
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream):
                if line_number < offset:
                    continue
                if line_number >= offset + limit:
                    break
                output_bytes += len(line.encode("utf-8"))
                if output_bytes > MAX_TOOL_OUTPUT_BYTES:
                    raise HarveyToolError("read output exceeds the tool limit")
                selected_lines.append(line)
        selected = "".join(selected_lines)
        return {
            "file_path": self._display_path(path),
            "content": selected,
        }

    def _write(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        relative = _required_string(arguments, "file_path")
        content = _required_string(arguments, "content")
        path = self._output_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "file_path": self._display_path(path),
            "bytes_written": len(content.encode("utf-8")),
        }

    def _edit(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        path = self._output_path(_required_string(arguments, "file_path"))
        old = _required_string(arguments, "old_string")
        new = _required_string(arguments, "new_string")
        replace_all = arguments.get("replace_all", False)
        if type(replace_all) is not bool:
            raise HarveyToolError("replace_all must be boolean")
        if not path.exists():
            raise HarveyToolError("file is unavailable")
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            raise HarveyToolError("old_string was not found")
        if count > 1 and not replace_all:
            raise HarveyToolError("old_string matched more than once")
        path.write_text(
            text.replace(old, new, -1 if replace_all else 1), encoding="utf-8"
        )
        return {
            "file_path": self._display_path(path),
            "replacements": count if replace_all else 1,
        }

    def _glob(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        pattern = _required_string(arguments, "pattern")
        root = self._search_root(arguments.get("path"))
        matches = sorted(
            (
                path
                for path in root.glob(pattern)
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda path: (-path.stat().st_mtime_ns, str(path)),
        )
        return {
            "matches": [
                self._display_path(path) for path in matches[:MAX_SEARCH_MATCHES]
            ]
        }

    def _grep(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        pattern = _required_string(arguments, "pattern")
        root = self._search_root(arguments.get("path"))
        glob = arguments.get("glob", "*")
        if not isinstance(glob, str) or not glob:
            raise HarveyToolError("glob must be a non-empty string")
        output_mode = arguments.get("output_mode", "files_with_matches")
        if output_mode not in {"content", "files_with_matches", "count"}:
            raise HarveyToolError("unsupported grep output_mode")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise HarveyToolError("grep pattern is invalid") from exc
        files = sorted(
            path
            for path in root.rglob(glob)
            if path.is_file() and not path.is_symlink()
        )
        matches: list[dict[str, Any]] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            found = [
                (index + 1, line)
                for index, line in enumerate(lines)
                if compiled.search(line)
            ]
            if not found:
                continue
            display = self._display_path(path)
            if output_mode == "files_with_matches":
                matches.append({"file_path": display})
            elif output_mode == "count":
                matches.append({"file_path": display, "count": len(found)})
            else:
                matches.extend(
                    {"file_path": display, "line_number": n, "line": line}
                    for n, line in found
                )
            if len(matches) >= MAX_SEARCH_MATCHES:
                break
        return {"matches": matches[:MAX_SEARCH_MATCHES]}

    def _read_path(self, value: str) -> Path:
        path = self._resolve_workspace_path(value)
        if not path.is_file() or path.is_symlink():
            raise HarveyToolError("file is unavailable")
        return path

    def _output_path(self, value: str) -> Path:
        candidate = self._resolve_workspace_path(value, relative_root=self.output_root)
        if not _is_relative_to(candidate, self.output_root) or _is_relative_to(
            candidate, self.documents_root
        ):
            raise HarveyToolError("writes are restricted to workspace/output")
        if candidate.exists() and candidate.is_symlink():
            raise HarveyToolError("symlinked output is unavailable")
        return candidate

    def _search_root(self, value: Any) -> Path:
        if value is None:
            return self.documents_root
        if not isinstance(value, str):
            raise HarveyToolError("path must be a string")
        root = self._resolve_workspace_path(value)
        if not root.is_dir() or root.is_symlink():
            raise HarveyToolError("search path is unavailable")
        return root

    def _resolve_workspace_path(
        self, value: str, *, relative_root: Path | None = None
    ) -> Path:
        relative = PurePosixPath(value)
        if relative.is_absolute():
            prefix = PurePosixPath("/workspace")
            try:
                relative = relative.relative_to(prefix)
            except ValueError as exc:
                raise HarveyToolError("absolute path escapes workspace") from exc
            if relative.parts[:1] == ("documents",):
                root = self.documents_root
                relative = PurePosixPath(*relative.parts[1:])
            elif relative.parts[:1] == ("output",):
                root = self.output_root
                relative = PurePosixPath(*relative.parts[1:])
            else:
                root = self.workspace_root
        else:
            root = relative_root or self.workspace_root
            if relative.parts[:1] == ("documents",):
                root = self.documents_root
                relative = PurePosixPath(*relative.parts[1:])
            elif relative.parts[:1] == ("output",):
                root = self.output_root
                relative = PurePosixPath(*relative.parts[1:])
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise HarveyToolError("path is unsafe")
        candidate = (root / Path(*relative.parts)).resolve()
        if not _is_relative_to(candidate, self.workspace_root) and not _is_relative_to(
            candidate, self.output_root
        ):
            raise HarveyToolError("path escapes workspace")
        return candidate

    def _safe_workspace_directory(self, value: str) -> Path:
        path = Path(value).resolve()
        if (
            not (
                _is_relative_to(path, self.workspace_root)
                or _is_relative_to(path, self.output_root)
            )
            or not path.is_dir()
        ):
            raise HarveyToolError("bash changed directory outside workspace")
        return path

    def _display_path(self, path: Path) -> str:
        resolved = path.resolve()
        for actual, virtual in (
            (self.documents_root, "documents"),
            (self.output_root, "output"),
        ):
            if _is_relative_to(resolved, actual):
                suffix = resolved.relative_to(actual).as_posix()
                return (
                    f"/workspace/{virtual}/{suffix}"
                    if suffix != "."
                    else f"/workspace/{virtual}"
                )
        return "/workspace/" + resolved.relative_to(self.workspace_root).as_posix()


def _required_string(arguments: Mapping[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value:
        raise HarveyToolError(f"{name} must be a non-empty string")
    return value


def _optional_nonnegative_int(
    arguments: Mapping[str, Any], name: str, *, default: int
) -> int:
    value = arguments.get(name, default)
    if type(value) is not int or value < 0:
        raise HarveyToolError(f"{name} must be a non-negative integer")
    return value


def _optional_positive_int(
    arguments: Mapping[str, Any], name: str, *, default: int
) -> int:
    value = arguments.get(name, default)
    if type(value) is not int or value <= 0:
        raise HarveyToolError(f"{name} must be a positive integer")
    return value


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_shell_environment() -> dict[str, str]:
    # Deliberately start with a tiny environment: host/provider credentials are
    # never inherited even if the worker is accidentally launched directly.
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "C"}


def _error_code(error: BaseException) -> str:
    if isinstance(error, HarveyToolError):
        return (
            "security_error"
            if "unsafe" in str(error)
            or "escap" in str(error)
            or "restricted" in str(error)
            else "tool_error"
        )
    return "tool_error"


__all__ = [
    "HARVEY_TOOL_NAMES",
    "HARVEY_TOOL_POLICY",
    "HarveyToolError",
    "HarveyToolExecutor",
]
