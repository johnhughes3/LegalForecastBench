#!/usr/bin/env python3
"""Synthetic Harvey LAB solver for offline discovery tests.

Writes one DOCX under --output-dir and exits 0. No network, no credentials.
synthetic: true
"""

from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "<w:document></w:document>")
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harvey_lab_fake_solver")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--basename", required=True)
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / args.basename
    if destination.exists() or destination.is_symlink():
        raise SystemExit(f"refusing to overwrite {destination}")
    destination.write_bytes(_docx_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
