#!/usr/bin/env python3
"""Render the LegalForecast-MTD methods preprint from its Markdown source."""

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false

from __future__ import annotations

import argparse
import html
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "docs/preprint/legalforecast-mtd-cycle-1.md"
DEFAULT_OUTPUT = ROOT / "output/pdf/legalforecast-mtd-cycle-1-draft.pdf"

PAGE_WIDTH, PAGE_HEIGHT = LETTER
MARGIN_X = 0.72 * inch
MARGIN_TOP = 0.68 * inch
MARGIN_BOTTOM = 0.64 * inch
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN_X)


class InvariantCanvas(Canvas):
    """Canvas with deterministic metadata and uncompressed text streams."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)


class MethodsPreprintDoc(BaseDocTemplate):
    """Document template with a restrained research-paper page treatment."""

    def __init__(self, output: Path) -> None:
        super().__init__(
            str(output),
            pagesize=LETTER,
            leftMargin=MARGIN_X,
            rightMargin=MARGIN_X,
            topMargin=MARGIN_TOP,
            bottomMargin=MARGIN_BOTTOM,
            title="LegalForecast-MTD Cycle 1",
            author="John J. Hughes III",
            subject="Pre-results methods draft; no Cycle 1 result claimed",
            creator="LegalForecastBench deterministic preprint renderer",
        )
        frame = Frame(
            MARGIN_X,
            MARGIN_BOTTOM,
            CONTENT_WIDTH,
            PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
            id="body",
        )
        self.addPageTemplates(
            [PageTemplate(id="methods", frames=[frame], onPage=_decorate_page)]
        )


def _decorate_page(canvas: Canvas, document: BaseDocTemplate) -> None:
    """Draw the draft label, running header, and page number."""

    canvas.saveState()
    canvas.setTitle("LegalForecast-MTD Cycle 1")
    canvas.setAuthor("John J. Hughes III")
    canvas.setSubject("Pre-results methods draft; no Cycle 1 result claimed")

    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("Helvetica", 7.2)
    header = "LEGALFORECAST-MTD  |  PRE-RESULTS METHODS DRAFT"
    canvas.drawString(MARGIN_X, PAGE_HEIGHT - 0.39 * inch, header)
    page_text = f"{document.page}"
    canvas.drawRightString(PAGE_WIDTH - MARGIN_X, 0.34 * inch, page_text)

    canvas.setFillColor(colors.Color(0.15, 0.23, 0.34, alpha=0.045))
    canvas.setFont("Helvetica-Bold", 44)
    canvas.translate(PAGE_WIDTH / 2, PAGE_HEIGHT / 2)
    canvas.rotate(40)
    watermark = "PRE-RESULTS DRAFT"
    canvas.drawCentredString(
        0, -stringWidth(watermark, "Helvetica-Bold", 44) / 14, watermark
    )
    canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PreprintTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#10243E"),
            spaceAfter=9,
        ),
        "subtitle": ParagraphStyle(
            "PreprintSubtitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.4,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#B45309"),
            borderColor=colors.HexColor("#F59E0B"),
            borderWidth=0.8,
            borderPadding=6,
            backColor=colors.HexColor("#FFFBEB"),
            spaceAfter=11,
        ),
        "author": ParagraphStyle(
            "PreprintAuthor",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#334155"),
            spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "PreprintH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=15.5,
            textColor=colors.HexColor("#10243E"),
            spaceBefore=11,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "PreprintH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.6,
            leading=13,
            textColor=colors.HexColor("#1D4E72"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "PreprintBody",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=9.25,
            leading=12.2,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#172033"),
            spaceAfter=5.5,
        ),
        "small": ParagraphStyle(
            "PreprintSmall",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.4,
            leading=9.2,
            textColor=colors.HexColor("#334155"),
        ),
        "reference": ParagraphStyle(
            "PreprintReference",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=7.1,
            leading=8.5,
            leftIndent=12,
            firstLineIndent=-12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=2,
        ),
        "callout": ParagraphStyle(
            "PreprintCallout",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#78350F"),
            borderColor=colors.HexColor("#F59E0B"),
            borderWidth=0.8,
            borderPadding=7,
            backColor=colors.HexColor("#FFFBEB"),
            spaceBefore=5,
            spaceAfter=8,
        ),
    }


def _inline(markdown: str) -> str:
    """Convert the small inline-Markdown subset used by the manuscript."""

    output: list[str] = []
    cursor = 0
    links = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for match in links.finditer(markdown):
        output.append(html.escape(markdown[cursor : match.start()]))
        label = html.escape(match.group(1))
        target = html.escape(match.group(2), quote=True)
        output.append(f'<link href="{target}" color="#1D4E72"><u>{label}</u></link>')
        cursor = match.end()
    output.append(html.escape(markdown[cursor:]))
    rendered = "".join(output)
    rendered = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", rendered)
    return rendered


def _parse_table(lines: Sequence[str], styles: dict[str, ParagraphStyle]) -> Table:
    rows: list[list[Paragraph]] = []
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if index == 1 and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append([Paragraph(_inline(cell), styles["small"]) for cell in cells])
    column_count = len(rows[0])
    widths = [CONTENT_WIDTH / column_count] * column_count
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0F7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#10243E")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94A3B8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _reference_table(lines: Sequence[str], styles: dict[str, ParagraphStyle]) -> Table:
    """Lay out bibliography entries in two compact, readable columns."""

    entries: list[Paragraph] = []
    paragraph: list[str] = []
    for line in [*lines, ""]:
        if line.strip():
            paragraph.append(line.strip())
            continue
        if paragraph:
            entries.append(Paragraph(_inline(" ".join(paragraph)), styles["reference"]))
            paragraph.clear()
    rows: list[list[Paragraph | str]] = []
    midpoint = (len(entries) + 1) // 2
    left = entries[:midpoint]
    right = entries[midpoint:]
    for index, item in enumerate(left):
        rows.append([item, right[index] if index < len(right) else ""])
    table = Table(
        rows,
        colWidths=[(CONTENT_WIDTH - 12) / 2] * 2,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 10),
                ("RIGHTPADDING", (1, 0), (1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _story(markdown: str) -> list[Flowable]:
    styles = _styles()
    lines = markdown.splitlines()
    story: list[Flowable] = []
    paragraph: list[str] = []
    index = 0
    saw_title = False

    def flush_paragraph() -> None:
        if not paragraph:
            return
        text = " ".join(part.strip() for part in paragraph)
        style = styles["reference"] if re.match(r"^\[R\d+\]:", text) else styles["body"]
        story.append(Paragraph(_inline(text), style))
        paragraph.clear()

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue
        if stripped == "<!-- pagebreak -->":
            flush_paragraph()
            story.append(PageBreak())
            index += 1
            continue
        if stripped.startswith("| "):
            flush_paragraph()
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            story.extend(
                [Spacer(1, 3), _parse_table(table_lines, styles), Spacer(1, 7)]
            )
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            while index < len(lines) and lines[index].strip().startswith("- "):
                item = lines[index].strip()[2:]
                story.append(
                    Paragraph(
                        _inline(item),
                        styles["body"],
                        bulletText="•",
                    )
                )
                index += 1
            continue
        if stripped.startswith("> "):
            flush_paragraph()
            story.append(Paragraph(_inline(stripped[2:]), styles["callout"]))
            index += 1
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            if not saw_title:
                story.append(Spacer(1, 0.2 * inch))
                story.append(Paragraph(_inline(stripped[2:]), styles["title"]))
                saw_title = True
            index += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(_inline(stripped[3:]), styles["h1"]))
            index += 1
            if stripped == "## References":
                story.append(_reference_table(lines[index:], styles))
                index = len(lines)
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            story.append(Paragraph(_inline(stripped[4:]), styles["h2"]))
            index += 1
            continue
        if stripped.startswith("Status: "):
            flush_paragraph()
            story.append(
                Paragraph(
                    _inline(stripped.removeprefix("Status: ")), styles["subtitle"]
                )
            )
            index += 1
            continue
        if stripped.startswith("Author: ") or stripped.startswith("Version: "):
            flush_paragraph()
            author_lines = [stripped]
            index += 1
            while index < len(lines) and lines[index].strip().startswith(
                ("Author: ", "Version: ")
            ):
                author_lines.append(lines[index].strip())
                index += 1
            story.append(
                Paragraph(
                    "<br/>".join(_inline(item) for item in author_lines),
                    styles["author"],
                )
            )
            continue
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    return story


def render(source: Path, output: Path) -> int:
    """Render *source* to *output* and return the resulting page count."""

    markdown = source.read_text(encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = MethodsPreprintDoc(output)
    document.build(_story(markdown), canvasmaker=InvariantCanvas)
    page_count = len(PdfReader(output).pages)
    if not 6 <= page_count <= 10:
        output.unlink(missing_ok=True)
        raise ValueError(f"preprint must render to 6-10 pages; rendered {page_count}")
    return page_count


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Render the LegalForecast-MTD pre-results methods manuscript to a "
            "deterministic 6-10 page PDF."
        )
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Render the manuscript and print the verified page count."""

    args = build_parser().parse_args(argv)
    page_count = render(args.source.resolve(), args.output.resolve())
    print(f"rendered {args.output}: {page_count} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
