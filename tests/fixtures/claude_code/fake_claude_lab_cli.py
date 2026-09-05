#!/usr/bin/env python3
"""synthetic: true

Hand-authored Claude Code LAB solver wrapper. Writes the expected Harvey LAB
deliverable under the first ``--add-dir`` workspace (contained runs use a
scratch cwd), then execs ``tests/fixtures/local_cli_fake_cli.py`` so the
envelope still comes from the shared fake CLI.
"""

from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1]
FAKE_CLI = FIXTURES / "local_cli_fake_cli.py"
LAB_OUTPUT = "output"
LAB_BASENAME = "issue-identification-memo.docx"
# Shell convention for "found but not executable"; used when exec itself fails.
EXEC_FAILURE_STATUS = 126


def _flag_value(argv: list[str], flag: str) -> str | None:
    try:
        index = argv.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(argv):
        return None
    return argv[index + 1]


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<w:document></w:document>")
    return buffer.getvalue()


def _write_lab_deliverable(argv: list[str]) -> None:
    add_dir = _flag_value(argv, "--add-dir")
    if add_dir is None:
        raise SystemExit("clean-native LAB fixture requires --add-dir")
    base = Path(add_dir)
    if not base.is_absolute():
        raise SystemExit("clean-native LAB --add-dir must be an absolute sandbox path")
    destination_dir = base / LAB_OUTPUT
    destination_dir.mkdir(parents=True, exist_ok=True)
    prompt = _flag_value(argv, "-p") or _flag_value(argv, "--print") or ""
    match = re.search(
        r"Write the expected deliverables (.+?) into the output directory", prompt
    )
    basenames = (
        tuple(name.strip() for name in match.group(1).split(","))
        if match is not None
        else (LAB_BASENAME,)
    )
    for basename in basenames:
        destination = destination_dir / basename
        if destination.exists() or destination.is_symlink():
            raise SystemExit(f"refusing to overwrite {basename}")
        destination.write_bytes(_docx_bytes())


def main(argv: list[str] | None = None) -> int:
    remainder = list(sys.argv[1:] if argv is None else argv)
    _write_lab_deliverable(remainder)
    try:
        os.execv(
            sys.executable,
            [
                sys.executable,
                str(FAKE_CLI),
                "--adapter",
                "claude",
                "--outcome",
                "success",
                *remainder,
            ],
        )
    except OSError as exc:
        print(f"LAB fixture could not exec {FAKE_CLI}: {exc}", file=sys.stderr)
    # ``os.execv`` replaces this process on success, so control reaches here
    # only when exec failed. Return an explicit nonzero status rather than
    # falling off the end with ``None``, which ``raise SystemExit(main())``
    # would report as a successful run.
    return EXEC_FAILURE_STATUS


if __name__ == "__main__":
    raise SystemExit(main())
