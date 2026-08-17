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

The values are read by locating the document structure an approver reads, not
by scanning the file. ``_current_specification_fields`` masks fenced code
blocks, requires exactly one ``## Current specification artifact`` heading,
takes the single rendered table in that section, and requires exactly one
``Structural specification`` row and exactly one ``SHA-256`` row inside that
one table. Scoping is the point: a whole-document regex would happily read a
row out of a fenced Markdown example, a historical table, or a neighbouring
table and report success while the live current-specification table was
missing, duplicated, or malformed -- a gate that inspects something other than
the declaration under review is worse than no gate, because it reports on it.
Cell formats stay strict alongside the scoping (backticked lowercase 64-hex
digest, backticked artifact path), so a scoped-but-garbled row fails loudly
rather than flowing into the comparison.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_DIR = ROOT / "docs" / "community-acceptance"
FREEZE_NAME = "tier0-paired-smoke-structural-freeze.md"
FREEZE_PATH = ACCEPTANCE_DIR / FREEZE_NAME
CHECKSUM_PATH = ACCEPTANCE_DIR / "tier0-paired-smoke-structural-freeze.sha256"
PACK_PATH = ACCEPTANCE_DIR / "tier0-readiness-pack.md"
FREEZE_RELATIVE = f"docs/community-acceptance/{FREEZE_NAME}"

SPECIFICATION_HEADING = "Current specification artifact"
SPECIFICATION_ROW = "Structural specification"
DIGEST_ROW = "SHA-256"

CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})\s+(\S+)$")
_FENCE = re.compile(r"^(`{3,}|~{3,})")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*$")
_DELIMITER_CELL = re.compile(r"^:?-+:?$")
_BACKTICKED = re.compile(r"^`([^`]+)`$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PackTableError(AssertionError):
    """The pack's current-specification table is missing or malformed.

    Subclasses ``AssertionError`` so an unexpected one still reads as an
    ordinary gate failure, while the scoping regressions below can name the
    exact condition they mean to provoke.
    """


def _mask_fenced_blocks(text: str) -> list[str]:
    """Return the document's lines with fenced code blocks blanked out.

    Fenced content is prose *about* Markdown, not Markdown the reader renders,
    so a fenced example table must never feed the gate. Blanking rather than
    deleting keeps a fenced block from silently joining the table rows on
    either side of it.
    """

    masked: list[str] = []
    fence: tuple[str, int] | None = None
    for raw in text.splitlines():
        stripped = raw.strip()
        marker = _FENCE.match(stripped)
        if fence is None:
            if marker is not None:
                run = marker.group(1)
                fence = (run[0], len(run))
                masked.append("")
                continue
            masked.append(raw)
            continue
        if marker is not None and stripped == marker.group(1):
            run = marker.group(1)
            if run[0] == fence[0] and len(run) >= fence[1]:
                fence = None
        masked.append("")
    if fence is not None:
        raise PackTableError(
            f"{PACK_PATH.relative_to(ROOT)} has an unterminated code fence; "
            "the current-specification table cannot be located safely"
        )
    return masked


def _section_lines(lines: list[str], heading: str) -> list[str]:
    """Return the body of the single ``## <heading>`` section in ``lines``."""

    starts: list[int] = []
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match is not None and match.group(2) == heading:
            starts.append(index)
    if len(starts) != 1:
        raise PackTableError(
            f"expected exactly one '{heading}' heading in "
            f"{PACK_PATH.relative_to(ROOT)}, found {len(starts)}"
        )
    start = starts[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = _HEADING.match(lines[index])
        if match is not None and len(match.group(1)) <= 2:
            end = index
            break
    return lines[start + 1 : end]


def _sole_table(section: list[str], heading: str) -> list[str]:
    """Return the one rendered Markdown table in a section body.

    Requiring a single table is stricter than requiring both rows to share a
    table, and it is the stricter rule that actually holds the gate honest: if
    someone adds a second table to this section, the reviewer-visible
    declaration has become ambiguous and a human should say which one binds.
    """

    tables: list[list[str]] = []
    block: list[str] = []
    for line in [*section, ""]:
        if line.lstrip().startswith("|"):
            block.append(line)
            continue
        if block:
            tables.append(block)
            block = []
    if len(tables) != 1:
        raise PackTableError(
            f"expected exactly one table under '{heading}' in "
            f"{PACK_PATH.relative_to(ROOT)}, found {len(tables)}"
        )
    table = tables[0]
    if len(table) < 3 or not _is_delimiter_row(table[1]):
        raise PackTableError(
            f"the block under '{heading}' in {PACK_PATH.relative_to(ROOT)} is "
            "not a rendered table with a header, a delimiter row, and at "
            f"least one body row: {table}"
        )
    return table


def _split_row(line: str) -> list[str]:
    """Split one pipe-delimited Markdown row into stripped cells."""

    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise PackTableError(f"malformed table row: {line!r}")
    return [cell.strip() for cell in stripped[1:-1].split("|")]


def _is_delimiter_row(line: str) -> bool:
    """Report whether ``line`` is a Markdown header/body delimiter row."""

    try:
        cells = _split_row(line)
    except PackTableError:
        return False
    return bool(cells) and all(_DELIMITER_CELL.match(cell) for cell in cells)


def _table_fields(table: list[str], heading: str) -> dict[str, str]:
    """Return the ``Field``/``Value`` mapping of a two-column table."""

    header = _split_row(table[0])
    if len(header) != 2:
        raise PackTableError(
            f"the table under '{heading}' in {PACK_PATH.relative_to(ROOT)} "
            f"must have two columns, found {len(header)}: {header}"
        )
    fields: dict[str, str] = {}
    for line in table[2:]:
        cells = _split_row(line)
        if len(cells) != 2:
            raise PackTableError(
                f"row {line!r} under '{heading}' in "
                f"{PACK_PATH.relative_to(ROOT)} must have two cells, "
                f"found {len(cells)}"
            )
        label, value = cells
        if label in fields:
            raise PackTableError(
                f"the table under '{heading}' in {PACK_PATH.relative_to(ROOT)} "
                f"declares {label!r} more than once"
            )
        fields[label] = value
    return fields


def _current_specification_fields(text: str) -> dict[str, str]:
    """Return the rows of the pack's Current specification artifact table."""

    lines = _mask_fenced_blocks(text)
    section = _section_lines(lines, SPECIFICATION_HEADING)
    table = _sole_table(section, SPECIFICATION_HEADING)
    fields = _table_fields(table, SPECIFICATION_HEADING)
    missing = [row for row in (SPECIFICATION_ROW, DIGEST_ROW) if row not in fields]
    if missing:
        raise PackTableError(
            f"the table under '{SPECIFICATION_HEADING}' in "
            f"{PACK_PATH.relative_to(ROOT)} is missing required row(s) "
            f"{missing}; found {sorted(fields)}"
        )
    return fields


def _backticked(value: str, label: str) -> str:
    """Return the contents of a required backtick-quoted cell."""

    match = _BACKTICKED.match(value)
    if match is None:
        raise PackTableError(
            f"the {label!r} value in {PACK_PATH.relative_to(ROOT)} must be "
            f"wrapped in backticks, found {value!r}"
        )
    return match.group(1)


def _declared_digest(text: str) -> str:
    """Return the SHA-256 declared by the pack's scoped table."""

    value = _backticked(_current_specification_fields(text)[DIGEST_ROW], DIGEST_ROW)
    if _SHA256.match(value) is None:
        raise PackTableError(
            f"the {DIGEST_ROW!r} value in {PACK_PATH.relative_to(ROOT)} must "
            f"be a lowercase 64-character hex digest, found {value!r}"
        )
    return value


def _declared_specification(text: str) -> str:
    """Return the artifact path declared by the pack's scoped table."""

    return _backticked(
        _current_specification_fields(text)[SPECIFICATION_ROW], SPECIFICATION_ROW
    )


def _pack_text() -> str:
    """Return the checked-in readiness pack."""

    return PACK_PATH.read_text(encoding="utf-8")


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
    assert _declared_digest(_pack_text()) == recorded_digest, (
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

    assert _declared_specification(_pack_text()) == FREEZE_RELATIVE
    assert FREEZE_PATH.is_file()


# ---------------------------------------------------------------------------
# Scoping regressions.
#
# Every decoy below is a document shape that a whole-document regex accepts and
# a section-scoped parser must reject: the decoy carries a well-formed row
# while the live table under "Current specification artifact" is deficient. The
# final case is the mirror image -- decoys present, live table intact -- which
# must still pass, because scoping has to ignore decoys rather than trip on
# them.
# ---------------------------------------------------------------------------

SYNTHETIC_DIGEST = "a" * 64
COMPLETE_TABLE = (
    "| Field | Value |\n"
    "| --- | --- |\n"
    f"| {SPECIFICATION_ROW} | `{FREEZE_RELATIVE}` |\n"
    f"| {DIGEST_ROW} | `{SYNTHETIC_DIGEST}` |\n"
)
DIGESTLESS_TABLE = (
    "| Field | Value |\n"
    "| --- | --- |\n"
    f"| {SPECIFICATION_ROW} | `{FREEZE_RELATIVE}` |\n"
    "| Status | Structural pre-spend freeze only |\n"
)


def _pack(section_body: str, *, trailing: str = "") -> str:
    """Assemble a synthetic readiness pack around one section body."""

    return (
        "# Tier-0 readiness pack\n\n"
        "Preamble prose.\n\n"
        f"## {SPECIFICATION_HEADING}\n\n"
        f"{section_body}\n"
        f"{trailing}"
        "## Cost state\n\nUnrelated prose.\n"
    )


def test_scoped_parser_reads_the_current_specification_table() -> None:
    """The happy path returns the rows of the one scoped table."""

    fields = _current_specification_fields(_pack(COMPLETE_TABLE))
    assert fields[SPECIFICATION_ROW] == f"`{FREEZE_RELATIVE}`"
    assert fields[DIGEST_ROW] == f"`{SYNTHETIC_DIGEST}`"


def test_fenced_example_cannot_satisfy_a_deficient_current_table() -> None:
    """A fenced Markdown sample must not stand in for the rendered table."""

    fenced = f"\nExample of the row to add:\n\n```markdown\n{COMPLETE_TABLE}```\n\n"
    document = _pack(DIGESTLESS_TABLE, trailing=fenced)
    with pytest.raises(PackTableError, match=r"missing required row"):
        _current_specification_fields(document)


def test_historical_table_cannot_satisfy_a_deficient_current_table() -> None:
    """A superseded table in another section must not satisfy the gate."""

    document = (
        f"{_pack(DIGESTLESS_TABLE)}\n"
        "## Historical specification artifacts\n\n"
        f"{COMPLETE_TABLE}"
    )
    with pytest.raises(PackTableError, match=r"missing required row"):
        _current_specification_fields(document)


def test_separate_tables_in_the_section_cannot_be_combined() -> None:
    """Two tables in the section are ambiguous, not two halves of one table."""

    split_tables = (
        "| Field | Value |\n"
        "| --- | --- |\n"
        f"| {SPECIFICATION_ROW} | `{FREEZE_RELATIVE}` |\n"
        "\n"
        "| Field | Value |\n"
        "| --- | --- |\n"
        f"| {DIGEST_ROW} | `{SYNTHETIC_DIGEST}` |\n"
    )
    with pytest.raises(PackTableError, match=r"exactly one table"):
        _current_specification_fields(_pack(split_tables))


def test_duplicate_required_row_fails() -> None:
    """Two digests in one table are a contradiction, not a match."""

    duplicated = COMPLETE_TABLE + f"| {DIGEST_ROW} | `{'b' * 64}` |\n"
    with pytest.raises(PackTableError, match=r"more than once"):
        _current_specification_fields(_pack(duplicated))


def test_missing_current_specification_heading_fails() -> None:
    """A renamed or deleted section must fail rather than fall through."""

    document = (
        "# Tier-0 readiness pack\n\n"
        "## Superseded specification artifact\n\n"
        f"{COMPLETE_TABLE}"
    )
    with pytest.raises(PackTableError, match=r"exactly one .* heading"):
        _current_specification_fields(document)


def test_duplicate_current_specification_heading_fails() -> None:
    """Two candidate sections must fail rather than silently pick one."""

    document = (
        f"{_pack(COMPLETE_TABLE)}\n## {SPECIFICATION_HEADING}\n\n{COMPLETE_TABLE}"
    )
    with pytest.raises(PackTableError, match=r"exactly one .* heading"):
        _current_specification_fields(document)


def test_pipe_lines_without_a_delimiter_row_are_not_a_table() -> None:
    """Unrendered pipe lines must not be mistaken for the declaration."""

    unrendered = (
        f"| {SPECIFICATION_ROW} | `{FREEZE_RELATIVE}` |\n"
        f"| {DIGEST_ROW} | `{SYNTHETIC_DIGEST}` |\n"
    )
    with pytest.raises(PackTableError, match=r"not a rendered table"):
        _current_specification_fields(_pack(unrendered))


def test_malformed_digest_cell_fails_even_when_scoped() -> None:
    """Scoping does not relax the required cell format."""

    loose = COMPLETE_TABLE.replace(f"`{SYNTHETIC_DIGEST}`", SYNTHETIC_DIGEST.upper())
    with pytest.raises(PackTableError, match=r"wrapped in backticks"):
        _declared_digest(_pack(loose))

    uppercased = COMPLETE_TABLE.replace(SYNTHETIC_DIGEST, SYNTHETIC_DIGEST.upper())
    with pytest.raises(PackTableError, match=r"lowercase 64-character hex"):
        _declared_digest(_pack(uppercased))


def test_decoy_tables_do_not_disturb_a_valid_current_table() -> None:
    """Scoping ignores decoys; it must not trip over them either."""

    document = (
        _pack(
            COMPLETE_TABLE,
            trailing=f"\nExample:\n\n```markdown\n{DIGESTLESS_TABLE}```\n\n",
        )
        + "\n## Historical specification artifacts\n\n"
        + DIGESTLESS_TABLE
    )
    assert _declared_digest(document) == SYNTHETIC_DIGEST
    assert _declared_specification(document) == FREEZE_RELATIVE
