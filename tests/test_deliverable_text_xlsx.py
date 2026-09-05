from __future__ import annotations

import io

import pytest
from legalforecast.multiharness.deliverable_text import (
    DeliverableTextError,
    deliverable_visible_text,
    xlsx_visible_text,
)
from openpyxl import Workbook


def _workbook_bytes(*, empty: bool = False) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Compliance\nTracker"
    if not empty:
        sheet.append(("Requirement", "Amount", "Complete"))
        sheet.append(("File\treport", 1250, False))
        sheet["D2"] = "=B2*2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_xlsx_visible_text_preserves_sheet_cells_and_formulas() -> None:
    assert xlsx_visible_text(_workbook_bytes()) == (
        "=== Sheet: Compliance\\nTracker ===\n"
        "A1=Requirement\tB1=Amount\tC1=Complete\n"
        "A2=File\\treport\tB2=1250\tC2=FALSE\tD2==B2*2"
    )


def test_xlsx_visible_text_refuses_empty_workbook() -> None:
    with pytest.raises(DeliverableTextError, match="no extractable cell values"):
        xlsx_visible_text(_workbook_bytes(empty=True))


def test_xlsx_visible_text_refuses_oversized_sheet_dimensions() -> None:
    with pytest.raises(DeliverableTextError, match="too many cell slots"):
        xlsx_visible_text(_workbook_bytes(), max_cell_slots=3)


def test_xlsx_dispatch_refuses_docx_bytes_renamed_as_xlsx() -> None:
    with pytest.raises(DeliverableTextError, match="SpreadsheetML"):
        deliverable_visible_text(
            b"PK\x03\x04not-a-spreadsheet", basename="misnamed.xlsx"
        )


def test_deliverable_dispatch_refuses_unknown_suffix() -> None:
    with pytest.raises(DeliverableTextError, match="unsupported suffix"):
        deliverable_visible_text(b"payload", basename="tracker.xls")
