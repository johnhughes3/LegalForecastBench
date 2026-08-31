"""Keep public corpus-membership exposure from expanding.

Cycle 1 accepts the pre-existing numeric candidate-ID inventory as a disclosed
limitation. This whole-tree fence makes the accepted surface explicit and
requires new fixtures to use synthetic identifiers instead.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_INVENTORY_SHA256 = (
    "103ef8fb9b2e40c0db28b2fcd35123406d595c243076ed4c941653bac5e20644"
)
NUMERIC_CANDIDATE_ID = re.compile(rb"candidate[_-]?id[^0-9]{0,8}[0-9]{7,12}")


def _inventory() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    inventory: list[str] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        path = raw_path.decode("utf-8")
        file_path = ROOT / path
        # A staged deletion is still present in ``git ls-files`` until the
        # commit; it must not make this read-only inventory probe crash.
        if not file_path.is_file():
            continue
        payload = file_path.read_bytes()
        if b"\0" in payload:
            continue
        for line_number, line in enumerate(payload.splitlines(), start=1):
            if NUMERIC_CANDIDATE_ID.search(line):
                inventory.append(f"{path}:{line_number}:{line.decode('utf-8')}")
    return sorted(inventory)


def test_public_numeric_candidate_id_inventory_is_frozen() -> None:
    inventory = _inventory()
    payload = ("\n".join(inventory) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    assert digest == ACCEPTED_INVENTORY_SHA256, (
        "public numeric candidate_id inventory changed; use synthetic IDs for "
        "new fixtures, or update the accepted baseline in an explicitly reviewed "
        f"change (found {len(inventory)} lines, digest {digest})"
    )
