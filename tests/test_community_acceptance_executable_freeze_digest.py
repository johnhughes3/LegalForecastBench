"""Bind the readiness pack's executable-freeze digest to the packet bytes."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_DIR = ROOT / "docs" / "community-acceptance"
PACK_PATH = ACCEPTANCE_DIR / "tier0-readiness-pack.md"
FREEZE_PATH = ACCEPTANCE_DIR / "tier0-paired-smoke-executable-freeze.md"
COMPANION_PATH = ACCEPTANCE_DIR / "tier0-paired-smoke-executable-freeze.sha256"

HEADING = "Executable freeze artifact"
CHECKSUM_LINE = re.compile(
    r"^([0-9a-f]{64})\s+tier0-paired-smoke-executable-freeze\.md$"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _pack_digest() -> str:
    text = PACK_PATH.read_text(encoding="utf-8")
    in_section = False
    digest: str | None = None
    for raw in text.splitlines():
        if raw.startswith("## "):
            in_section = raw[3:].strip() == HEADING
            continue
        if not in_section or not raw.startswith("|"):
            continue
        cells = [cell.strip() for cell in raw.strip("|").split("|")]
        if len(cells) != 2:
            continue
        if cells[0] == "SHA-256":
            value = cells[1]
            assert value.startswith("`") and value.endswith("`"), value
            digest = value[1:-1]
    assert digest is not None, "readiness pack is missing the executable-freeze digest"
    assert SHA256.fullmatch(digest), digest
    return digest


def test_executable_freeze_digest_matches_pack_and_companion() -> None:
    payload = FREEZE_PATH.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    companion = COMPANION_PATH.read_text(encoding="utf-8").strip()
    match = CHECKSUM_LINE.fullmatch(companion)
    assert match is not None, companion
    recorded = match.group(1)
    assert actual == recorded == _pack_digest()
