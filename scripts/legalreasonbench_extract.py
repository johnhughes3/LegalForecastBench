"""Prepare pinned LegalReasonBench records and sequential document inputs.

Downloads are data only; no upstream code is imported or executed. Run the CLI
with ``uv run --with pypdf --with fonttools python -I`` and the audit CLI
from outside the download directory. DOCX conversion requires pandoc.
"""

from __future__ import annotations

import importlib
import json
import re
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Any, cast
from urllib.parse import quote, unquote, urlsplit

REVISION = "1bfa904c8f255925baf2610c0f86aa7c05d94ed9"
DATASET = "micro1-inc/LegalReasonBench"
BASE = f"https://huggingface.co/datasets/{DATASET}"
EXCLUDED = "lrb-interim-cmo-appointment-governance"
AUDIT = Path("docs/legalreasonbench-audit/litigation")
EMAIL = re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}")
REDACTION_NOTE = (
    "Email addresses are replaced with [email redacted] in quoted upstream text. "
    "No OCR was performed; PDF pages with no extracted text are explicitly marked. "
    "DOCX conversion shows tracked changes; original pagination is not retained."
)


def upstream_url(path: str, *, raw: bool = False) -> str:
    """Return a revision-pinned file URL, rejecting paths outside the dataset."""
    decoded = unquote(path)
    parsed = PurePosixPath(decoded)
    if (
        not path
        or urlsplit(decoded).scheme
        or parsed.is_absolute()
        or ".." in parsed.parts
        or "\\" in decoded
        or "\x00" in decoded
        or any(ord(c) < 32 for c in decoded)
    ):
        raise ValueError(f"Unsafe upstream path: {path}")
    return f"{BASE}/{'resolve' if raw else 'blob'}/{REVISION}/{quote(path, safe='/')}"


def redact(value: Any) -> Any:
    """Redact source email addresses without dropping row fields."""
    if isinstance(value, str):
        return EMAIL.sub("[email redacted]", value)
    if isinstance(value, list):
        return [redact(v) for v in cast(list[object], value)]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in cast(dict[str, object], value).items()}
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def task_id(row: dict[str, Any]) -> str:
    result = f"{row['matter_id']}-assignment-{row['assignment']}"
    if "/" in result or "\\" in result or ".." in result:
        raise ValueError("Unsafe task identifier")
    return result


def pdf_text(path: Path) -> str:
    """Extract every PDF page, retaining even blank or scanned page positions."""
    reader = importlib.import_module("pypdf").PdfReader(path)
    pages: list[str] = []
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if not text.strip():
            text = (
                "[No extractable text on this page; it may be blank or scanned. "
                "No OCR performed.]"
            )
        pages.append(f"## PDF page {number}\n\n{text.strip()}\n")
    return "\n".join(pages)


def attachment_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return pdf_text(path)
    if path.suffix.lower() == ".docx":
        return subprocess.run(
            [
                "pandoc",
                "--sandbox",
                "--track-changes=all",
                "-t",
                "gfm",
                "--wrap=none",
                str(path.resolve()),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    raise ValueError(f"Unsupported attachment: {path.name}")


def extract(
    rows_path: Path, api_path: Path, upstream: Path, out: Path
) -> dict[str, Any]:
    """Download all attachments; extract only the selected sequential assignments."""
    upstream = upstream.resolve()
    if Path.cwd().is_relative_to(upstream):
        raise ValueError("Run extraction from outside the untrusted upstream directory")
    saved = json.loads(rows_path.read_text())
    if isinstance(saved, dict):
        index = cast(dict[str, Any], saved)
        if index.get("revision") != REVISION or index.get("dataset") != DATASET:
            raise ValueError("Source index does not match the pinned dataset revision")
        saved = index["rows"]
    rows = cast(list[dict[str, Any]], saved)
    api = json.loads(api_path.read_text())
    if api["sha"] != REVISION:
        raise ValueError("API metadata does not match the pinned revision")
    for row in rows:
        task_id(row)
        for path in [*row["attachments"], row["instruction_path"], row["rubric_path"]]:
            upstream_url(path)
        if isinstance(row["rubric"], str):
            row["rubric"] = json.loads(row["rubric"])
        if len(row["rubric"]) != row["rubric_count"]:
            raise ValueError(f"Rubric count mismatch: {task_id(row)}")
    attachments = sorted({p for row in rows for p in row["attachments"]})
    instructions = sorted({r["instruction_path"] for r in rows})
    upstream.mkdir(parents=True, exist_ok=True)

    def download(path: str) -> None:
        url = upstream_url(path, raw=True)
        target = upstream / path
        if not target.resolve().is_relative_to(upstream):
            raise ValueError(f"Unsafe upstream path: {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with urllib.request.urlopen(url, timeout=120) as response:
                payload = response.read()
            target.write_bytes(payload)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(download, [*attachments, *instructions]))

    in_scope = [r for r in rows if r["matter_id"] != EXCLUDED]
    scope_path = out / "in-scope.json"
    if scope_path.exists():
        scope = json.loads(scope_path.read_text())
        if "tasks" in scope:
            selected = {t["task"] for t in scope["tasks"] if t["in_scope"]}
            in_scope = [r for r in rows if task_id(r) in selected]
    scope_attachments = sorted({p for r in in_scope for p in r["attachments"]})
    # This small public sample needs direct byte equality, not content digests.
    contents = {p: (upstream / p).read_bytes() for p in attachments}
    source: dict[str, Any] = {
        "dataset": DATASET,
        "revision": REVISION,
        "license": api["cardData"]["license"],
        "dataset_card_url": upstream_url("README.md"),
        "parquet_url": upstream_url("data/assignments/test-00000-of-00001.parquet"),
        "redactions": REDACTION_NOTE,
        "rows": redact(rows),
        "attachment_counts": {
            "attachment_paths_total": len(attachments),
            "in_scope_attachment_paths": len(scope_attachments),
            "distinct_attachment_contents_total": len(set(contents.values())),
            "distinct_attachment_contents_in_scope": len(
                {contents[p] for p in scope_attachments}
            ),
            "method": "Direct equality of downloaded bytes",
        },
    }
    census = {
        "dataset": DATASET,
        "revision": REVISION,
        "classification_status": "provisional; owner finalizes scope",
        "assignments_total": len(rows),
        "criteria_total": sum(r["rubric_count"] for r in rows),
        "in_scope_assignments": len(in_scope),
        "in_scope_criteria": sum(r["rubric_count"] for r in in_scope),
        "attachment_paths_total": len(attachments),
        "in_scope_attachment_paths": len(
            {p for r in in_scope for p in r["attachments"]}
        ),
        **source["attachment_counts"],
        "tasks": [
            {
                "task": task_id(r),
                "matter_id": r["matter_id"],
                "assignment": r["assignment"],
                "title": r["assignment_title"],
                "criteria_total": r["rubric_count"],
                "penalty_count": r["penalty_count"],
                "in_scope": r["matter_id"] != EXCLUDED,
                "scope_reason": "Litigation assignment"
                if r["matter_id"] != EXCLUDED
                else "Interim CMO appointment governance; excluded by owner scope",
            }
            for r in rows
        ],
    }
    # Scope is parent-owned once prepared: rerunning extraction preserves its decisions.
    if not (out / "in-scope.json").exists():
        write_json(out / "in-scope.json", census)
    extracted: dict[str, str] = {}
    pdf_pages: dict[str, int] = {}
    for current in in_scope:
        prior = sorted(
            (
                r
                for r in rows
                if r["matter_id"] == current["matter_id"]
                and r["assignment"] <= current["assignment"]
            ),
            key=lambda r: r["assignment"],
        )
        task_dir = out / "tasks" / task_id(current)
        task_dir.mkdir(parents=True, exist_ok=True)
        native = (upstream / current["instruction_path"]).read_text()
        native = redact(native.replace("/app/", ""))
        (task_dir / "upstream-instruction.md").write_text(
            f"Source: {upstream_url(current['instruction_path'])}\n\n"
            "Source sandbox paths made relative; source email addresses redacted.\n\n"
            + native
        )
        inputs = dict(current)
        inputs.update(
            {
                "task": task_id(current),
                "revision": REVISION,
                "instruction_url": upstream_url(current["instruction_path"]),
                "rubric_url": upstream_url(current["rubric_path"]),
                "redactions": REDACTION_NOTE,
            }
        )
        inputs["prior_prompts"] = [
            {
                "assignment": r["assignment"],
                "prompt": r["prompt"],
                "source_url": upstream_url(r["instruction_path"]),
            }
            for r in prior[:-1]
        ]
        accumulated: list[dict[str, Any]] = []
        for r in prior:
            for path in r["attachments"]:
                if path not in extracted:
                    raw = attachment_text(upstream / path)
                    if Path(path).suffix.lower() == ".pdf":
                        pdf_pages[path] = len(
                            re.findall(r"^## PDF page \d+$", raw, re.M)
                        )
                    count = len(EMAIL.findall(raw))
                    extracted[path] = (
                        f"# {Path(path).name}\n\nSource: {upstream_url(path)}\n\n"
                        f"Email addresses redacted: {count}.\n\n{redact(raw)}\n"
                    )
                local = (
                    Path("attachments")
                    / f"assignment-{r['assignment']}"
                    / (Path(path).name + ".md")
                )
                destination = task_dir / local
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(extracted[path])
                accumulated.append(
                    {
                        "assignment": r["assignment"],
                        "upstream_path": path,
                        "source_url": upstream_url(path),
                        "extracted_path": local.as_posix(),
                    }
                )
        inputs["attachments"] = accumulated
        write_json(task_dir / "input.json", redact(inputs))
        instruction = [
            f"# {current['assignment_title']}",
            "",
            f"Source: {upstream_url(current['instruction_path'])}",
            "",
            REDACTION_NOTE,
            "",
            "Prior model answers are unavailable; no answers have been synthesized. "
            "Prior prompts and accumulated source attachments follow.",
            "",
        ]
        for r in prior:
            label = "Current" if r is current else "Prior"
            instruction += [
                f"## {label} assignment {r['assignment']}",
                "",
                f"Source: {upstream_url(r['instruction_path'])}",
                "",
                redact(r["prompt"]),
                "",
            ]
        instruction += ["## Accumulated attachments", ""]
        instruction += [
            f"- [{a['upstream_path']}]({quote(a['extracted_path'], safe='/')}) "
            f"(assignment {a['assignment']})"
            for a in accumulated
        ]
        (task_dir / "instruction.md").write_text("\n".join(instruction) + "\n")
    source["extraction"] = {
        "pdf_page_counts_by_path": pdf_pages,
        "pdf_pages_distinct_contents": sum(
            next(pdf_pages[p] for p in pdf_pages if contents[p] == payload)
            for payload in {contents[p] for p in pdf_pages}
        ),
        "note": "PDF text extraction page count; no OCR or visual completeness check",
    }
    write_json(out / "source-index.json", source)
    return {
        "assignments": len(in_scope),
        "criteria": census["in_scope_criteria"],
        "downloaded_attachment_paths": len(attachments),
        "extracted_attachment_paths": len(extracted),
    }
