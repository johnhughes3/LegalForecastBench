"""Bind the Tier-0 readiness pack's declared digest to the frozen bytes.

``docs/community-acceptance/tier0-readiness-pack.md`` names one structural
specification and embeds its SHA-256 in the "Current specification artifact"
table. That digest is the only thing telling the designated approver *which*
bytes the pack is describing, and it is maintained by hand. Regenerating the
freeze document therefore has three separate places to update -- the freeze
file, its ``.sha256`` companion, and the pack's table -- and updating only two
of them leaves a document that contradicts itself while every existing check
still passes. That is exactly how the pack desynced in #769: the freeze bytes
changed, the companion was regenerated, ``sha256sum -c`` reported OK, and the
pack went on advertising the superseded digest. Only a human reviewer caught
it.

These tests close the loop mechanically by asserting a single chain:

    pack table digest == ``.sha256`` recorded digest == sha256(freeze bytes)

Each link is checked because each can break on its own. Comparing only the two
recorded strings would pass while both pointed at bytes that no longer exist;
comparing only the companion against the file would pass while the pack -- the
document an approver actually reads -- named something else entirely.

The pack's digest is extracted by matching the table row structurally and
requiring exactly one match, never by scanning the file for any 64-character
hex run. The pack legitimately quotes other SHA-256 values in prose (the
documented Claude Code binary identity, for one), so a loose scan would either
compare the wrong digest or pass vacuously, and a future second table row would
be silently ignored instead of surfacing as a failure.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_DIR = ROOT / "docs" / "community-acceptance"
FREEZE_NAME = "tier0-paired-smoke-structural-freeze.md"
FREEZE_PATH = ACCEPTANCE_DIR / FREEZE_NAME
CHECKSUM_PATH = ACCEPTANCE_DIR / "tier0-paired-smoke-structural-freeze.sha256"
PACK_PATH = ACCEPTANCE_DIR / "tier0-readiness-pack.md"
FREEZE_RELATIVE = f"docs/community-acceptance/{FREEZE_NAME}"

PACK_DIGEST_ROW = re.compile(
    r"^\|\s*SHA-256\s*\|\s*`([0-9a-f]{64})`\s*\|\s*$",
    re.MULTILINE,
)
PACK_SPECIFICATION_ROW = re.compile(
    r"^\|\s*Structural specification\s*\|\s*`([^`]+)`\s*\|\s*$",
    re.MULTILINE,
)
CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})\s+(\S+)$")


def _sole_match(pattern: re.Pattern[str], text: str, label: str) -> str:
    """Return the single capture of ``pattern``, failing on any other count."""

    matches = pattern.findall(text)
    assert len(matches) == 1, (
        f"expected exactly one {label} row in {PACK_PATH.relative_to(ROOT)}, "
        f"found {len(matches)}: {matches}"
    )
    return matches[0]


def _pack_declared_digest() -> str:
    """Return the SHA-256 embedded in the pack's specification table."""

    return _sole_match(
        PACK_DIGEST_ROW, PACK_PATH.read_text(encoding="utf-8"), "SHA-256"
    )


def _recorded_checksum() -> tuple[str, str]:
    """Return the digest and target filename recorded in the companion file."""

    lines = [
        line
        for line in CHECKSUM_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1, (
        f"{CHECKSUM_PATH.relative_to(ROOT)} must record exactly one artifact, "
        f"found {len(lines)} lines"
    )
    match = CHECKSUM_LINE.match(lines[0])
    assert match is not None, (
        f"{CHECKSUM_PATH.relative_to(ROOT)} is not a sha256sum line: {lines[0]!r}"
    )
    return match.group(1), match.group(2)


def test_readiness_pack_digest_matches_the_recorded_checksum() -> None:
    """The pack's table and the ``.sha256`` companion must agree."""

    recorded_digest, _ = _recorded_checksum()
    assert _pack_declared_digest() == recorded_digest, (
        "the Tier-0 readiness pack's embedded SHA-256 no longer matches "
        f"{CHECKSUM_PATH.relative_to(ROOT)}; regenerate the pack table from the "
        "companion checksum instead of editing either in isolation"
    )


def test_recorded_checksum_matches_the_frozen_bytes() -> None:
    """The companion checksum must describe the freeze document on disk."""

    recorded_digest, recorded_name = _recorded_checksum()
    assert recorded_name == FREEZE_NAME, (
        f"{CHECKSUM_PATH.relative_to(ROOT)} must name {FREEZE_NAME}, "
        f"found {recorded_name!r}"
    )
    actual = hashlib.sha256(FREEZE_PATH.read_bytes()).hexdigest()
    assert actual == recorded_digest, (
        f"{FREEZE_RELATIVE} hashes to {actual} but "
        f"{CHECKSUM_PATH.relative_to(ROOT)} records {recorded_digest}"
    )


def test_readiness_pack_names_the_hashed_specification() -> None:
    """The digest must be attributed to the freeze document, not another file."""

    declared = _sole_match(
        PACK_SPECIFICATION_ROW,
        PACK_PATH.read_text(encoding="utf-8"),
        "Structural specification",
    )
    assert declared == FREEZE_RELATIVE
    assert FREEZE_PATH.is_file()
