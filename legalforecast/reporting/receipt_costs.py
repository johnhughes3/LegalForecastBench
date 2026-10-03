"""Cost-only receipt reporting without inferred latency or tool observations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any

from legalforecast import cli_support as _cli_support
from legalforecast.publication.site_export import build_site_export


def append_receipt_costs(
    scores: Mapping[str, Any],
    accounting: Sequence[Mapping[str, Any]],
    json_path: Path,
    markdown_path: Path,
    html_path: Path,
) -> None:
    """Render sanitized receipt costs without inventing operational observations."""
    export = build_site_export(scores, accounting=accounting)
    rows = [
        {"model_id": row.model_id, **row.costs.model_dump(mode="json")}
        for row in export.results
    ]
    payload = _cli_support.read_json_object(json_path)
    payload["cost_accounting"] = rows
    _cli_support.write_json(json_path, payload)
    caveat = (
        "Successful case workload only. Provider-reported charges and usage estimates "
        "are identified separately; these are not invoice totals. Failed attempts, "
        "retries, unresolved charges and summary preparation are excluded. Missing "
        "latency and tool-call observations remain unknown in the leaderboard. "
        "Standard repricing retains missing usage/cache evidence and coverage."
    )
    headers = (
        "Model",
        "Workload USD",
        "Basis",
        "Cases covered",
        "Standard-rate USD",
        "Standard cases covered",
    )
    rendered: list[tuple[str, ...]] = []
    for row in rows:
        amount = row["total_cost"]
        standard = row["standard_rate_total_cost"]
        rendered.append(
            (
                str(row["model_id"]),
                "unavailable" if amount is None else f"{amount:.6f}",
                str(row["basis"]),
                str(row["covered_case_count"]),
                "unavailable" if standard is None else f"{standard:.6f}",
                (
                    f"{row['standard_rate_covered_case_count']} "
                    f"({row['standard_rate_status']})"
                ),
            )
        )
    markdown = "\n\n## Receipt cost accounting\n\n" + caveat + "\n\n"
    markdown += "| " + " | ".join(headers) + " |\n"
    markdown += "| " + " | ".join("---" for _ in headers) + " |\n"
    markdown += "".join(
        "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |\n"
        for row in rendered
    )
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8") + markdown, encoding="utf-8"
    )
    section = (
        "<section><h2>Receipt cost accounting</h2><p>"
        + escape(caveat)
        + "</p><table><thead><tr>"
    )
    section += (
        "".join("<th>" + escape(header) + "</th>" for header in headers)
        + "</tr></thead><tbody>"
    )
    section += "".join(
        "<tr>" + "".join("<td>" + escape(cell) + "</td>" for cell in row) + "</tr>"
        for row in rendered
    )
    section += "</tbody></table></section>"
    html = html_path.read_text(encoding="utf-8")
    html_path.write_text(
        html.replace("</body>", section + "</body>")
        if "</body>" in html
        else html + section,
        encoding="utf-8",
    )
