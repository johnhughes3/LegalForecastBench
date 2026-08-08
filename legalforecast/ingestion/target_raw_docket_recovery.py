"""Bounded Firecrawl recovery of raw docket HTML missing from an exact target.

This is deliberately narrower than the public-document gap bridge: it never
plans a document download or a purchase.  It creates a fresh, same-cycle
Firecrawl batch whose only output is screening-compatible, pagination-proven
raw docket HTML for selected target cases absent from a pinned source manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from legalforecast.contracts import (
    TARGET_RAW_DOCKET_RECOVERY_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1,
    TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1,
)
from legalforecast.ingestion.budgeted_docket_acquisition import (
    acquire_ranked_dockets,
    render_complete_docket_html,
)
from legalforecast.ingestion.budgeted_firecrawl import BudgetedFirecrawlScheduler
from legalforecast.ingestion.cycle_acquisition_store import (
    SnapshotVerificationError,
    verify_snapshot,
)
from legalforecast.ingestion.firecrawl_screening_identity import (
    snapshot_firecrawl_screening_source_count,
)

TARGET_RAW_DOCKET_RECOVERY_PLAN_SCHEMA = str(TARGET_RAW_DOCKET_RECOVERY_PLAN_V1)
TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA = str(TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1)
TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA = str(TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1)
TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_SCHEMA = str(
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DOCKET_ID = re.compile(r"[1-9][0-9]*\Z")
_CANDIDATE_PREFIX = "courtlistener-docket-"


class TargetRawDocketRecoveryError(ValueError):
    """Raised when exact-target raw recovery cannot be authenticated."""


@dataclass(frozen=True, slots=True)
class TargetRawDocketRecoveryPlan:
    selection_path: str
    selection_sha256: str
    source_snapshot_path: str
    source_snapshot_manifest_sha256: str
    source_snapshot_screened_cases_sha256: str
    cycle_hash: str
    source_batch_id: str
    source_batch_digest: str
    source_snapshot_run_card_path: str
    source_snapshot_run_card_sha256: str
    source_raw_manifest_path: str
    source_raw_manifest_sha256: str
    cycle_store_path: str
    batch_id: str
    run_id: str
    credit_cap: int
    workers: int
    max_pages_per_docket: int
    max_attempts_per_page: int
    provider_breaker_threshold: int
    proxy: str
    force_browser: bool
    targets: tuple[Mapping[str, object], ...]

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": TARGET_RAW_DOCKET_RECOVERY_PLAN_SCHEMA,
            **asdict(self),
            "target_count": len(self.targets),
        }


def _read_jsonl(path: Path, label: str) -> list[Mapping[str, Any]]:
    _require_regular(path, label)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines if line]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(f"{label} is not JSONL") from exc
    if not rows or any(not isinstance(row, Mapping) for row in rows):
        raise TargetRawDocketRecoveryError(f"{label} is empty or malformed")
    return rows


def _read_jsonl_allow_empty(path: Path, label: str) -> list[Mapping[str, Any]]:
    _require_regular(path, label)
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(f"{label} is not JSONL") from exc
    if any(not isinstance(row, Mapping) for row in rows):
        raise TargetRawDocketRecoveryError(f"{label} is malformed")
    return cast(list[Mapping[str, Any]], rows)


def _require_regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise TargetRawDocketRecoveryError(
            f"{label} is not a singly linked regular file"
        )


def _pinned_sha(path: Path, expected: str, label: str) -> str:
    if _SHA256.fullmatch(expected) is None:
        raise TargetRawDocketRecoveryError(f"{label} SHA-256 is invalid")
    _require_regular(path, label)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise TargetRawDocketRecoveryError(f"{label} SHA-256 mismatch")
    return actual


def _require_no_symlink_components(path: Path, label: str) -> None:
    normalized = Path(os.path.abspath(path))
    for candidate in (normalized, *normalized.parents):
        if candidate.is_symlink():
            raise TargetRawDocketRecoveryError(f"{label} contains a symlink")


def verify_target_raw_docket_recovery_receipt(
    *,
    receipt_path: Path,
    expected_receipt_sha256: str,
    expected_plan_sha256: str,
    successes_path: Path,
    exclusions_path: Path,
    summary_path: Path,
    raw_html_dir: Path,
) -> Mapping[str, Any]:
    """Authenticate the exact recovery-to-screen handoff."""

    _pinned_sha(receipt_path, expected_receipt_sha256, "recovery receipt")
    for path, label in (
        (successes_path, "recovery successes"),
        (exclusions_path, "recovery exclusions"),
        (summary_path, "recovery summary"),
    ):
        _require_regular(path, label)
    _require_no_symlink_components(raw_html_dir, "recovery raw HTML directory")
    try:
        receipt_value = json.loads(
            receipt_path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
        summary_value = json.loads(
            summary_path.read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise TargetRawDocketRecoveryError(
            "recovery receipt or summary is not canonical JSON"
        ) from exc
    if not isinstance(receipt_value, Mapping) or not isinstance(summary_value, Mapping):
        raise TargetRawDocketRecoveryError("recovery receipt or summary is malformed")
    receipt = cast(Mapping[str, Any], receipt_value)
    summary = cast(Mapping[str, Any], summary_value)
    if (
        receipt.get("schema_version") != TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA
        or receipt.get("dry_run") is not False
        or receipt.get("plan_sha256") != expected_plan_sha256
    ):
        raise TargetRawDocketRecoveryError(
            "recovery receipt does not bind the executed plan"
        )
    expected_paths = {
        "successes_path": successes_path,
        "exclusions_path": exclusions_path,
        "summary_path": summary_path,
        "raw_html_dir": raw_html_dir,
    }
    if any(
        receipt.get(field) != str(path.resolve())
        for field, path in expected_paths.items()
    ):
        raise TargetRawDocketRecoveryError("recovery receipt output path mismatch")
    for field, path in (
        ("successes_sha256", successes_path),
        ("exclusions_sha256", exclusions_path),
        ("summary_sha256", summary_path),
    ):
        if receipt.get(field) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise TargetRawDocketRecoveryError(
                f"recovery receipt {field} commitment mismatch"
            )
    successes = _read_jsonl_allow_empty(successes_path, "recovery successes")
    exclusions = _read_jsonl_allow_empty(exclusions_path, "recovery exclusions")
    expected_provenance = {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_SCHEMA,
        "plan_sha256": expected_plan_sha256,
        "batch_id": receipt.get("batch_id"),
        "run_id": receipt.get("run_id"),
    }
    if any(
        record.get("target_raw_docket_recovery") != expected_provenance
        for record in (*successes, *exclusions)
    ):
        raise TargetRawDocketRecoveryError(
            "recovery terminal record provenance mismatch"
        )
    receipt_artifacts = receipt.get("raw_artifacts")
    summary_artifacts = summary.get("raw_artifacts")
    if (
        not isinstance(receipt_artifacts, list)
        or receipt_artifacts != summary_artifacts
    ):
        raise TargetRawDocketRecoveryError(
            "recovery receipt raw-artifact commitment mismatch"
        )
    projected: list[Mapping[str, object]] = []
    seen_candidates: set[str] = set()
    for record in successes:
        candidate_id = record.get("candidate_id")
        docket_id = record.get("docket_id")
        sha256 = record.get("raw_html_sha256")
        byte_count = record.get("raw_html_bytes")
        retrieved_at = record.get("retrieved_at")
        raw_path_value = record.get("raw_html_path")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(docket_id, str)
            or candidate_id != _CANDIDATE_PREFIX + docket_id
            or candidate_id in seen_candidates
            or not isinstance(sha256, str)
            or _SHA256.fullmatch(sha256.removeprefix("sha256:")) is None
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
            or not isinstance(retrieved_at, str)
            or not retrieved_at
            or not isinstance(raw_path_value, str)
        ):
            raise TargetRawDocketRecoveryError(
                "recovery success has malformed raw-artifact commitment"
            )
        seen_candidates.add(candidate_id)
        raw_path = raw_html_dir / f"{docket_id}.html"
        if Path(raw_path_value).resolve() != raw_path.resolve():
            raise TargetRawDocketRecoveryError("recovery success raw path mismatch")
        _require_regular(raw_path, f"recovery raw HTML {candidate_id}")
        raw = raw_path.read_bytes()
        if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != (
            sha256.removeprefix("sha256:")
        ):
            raise TargetRawDocketRecoveryError(
                f"recovery raw HTML commitment mismatch: {candidate_id}"
            )
        projected.append(
            {
                "candidate_id": candidate_id,
                "sha256": sha256,
                "byte_count": byte_count,
                "retrieved_at": retrieved_at,
            }
        )
    if receipt_artifacts != projected:
        raise TargetRawDocketRecoveryError(
            "recovery receipt does not match success raw artifacts"
        )
    return receipt


def build_target_raw_docket_recovery_plan(
    *,
    selection_path: Path,
    expected_selection_sha256: str,
    source_snapshot_path: Path,
    expected_source_snapshot_manifest_sha256: str,
    expected_cycle_hash: str,
    source_snapshot_run_card_path: Path,
    expected_source_snapshot_run_card_sha256: str,
    source_raw_manifest_path: Path,
    expected_source_raw_manifest_sha256: str,
    cycle_store_path: Path,
    batch_id: str,
    run_id: str,
    credit_cap: int,
    workers: int,
    max_pages_per_docket: int,
    max_attempts_per_page: int,
    provider_breaker_threshold: int,
    proxy: str,
    force_browser: bool,
) -> TargetRawDocketRecoveryPlan:
    """Derive exactly selected-minus-raw targets from three pinned inputs."""

    selection_sha = _pinned_sha(selection_path, expected_selection_sha256, "selection")
    card_sha = _pinned_sha(
        source_snapshot_run_card_path,
        expected_source_snapshot_run_card_sha256,
        "source snapshot run card",
    )
    try:
        manifest = verify_snapshot(
            source_snapshot_path,
            expected_cycle_hash=expected_cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
        snapshot_firecrawl_screening_source_count(manifest, require_current=True)
    except (SnapshotVerificationError, ValueError) as exc:
        raise TargetRawDocketRecoveryError(
            f"source snapshot is not current complete and saturated: {exc}"
        ) from exc
    source_batch_id = manifest.get("batch_id")
    source_batch_digest = manifest.get("batch_digest")
    if (
        not isinstance(source_batch_id, str)
        or not source_batch_id
        or not isinstance(source_batch_digest, str)
        or _SHA256.fullmatch(source_batch_digest) is None
    ):
        raise TargetRawDocketRecoveryError(
            "source snapshot has invalid batch authority"
        )
    snapshot_manifest_path = source_snapshot_path / "manifest.json"
    snapshot_manifest_sha = _pinned_sha(
        snapshot_manifest_path,
        expected_source_snapshot_manifest_sha256,
        "source snapshot manifest",
    )
    screened_path = source_snapshot_path / "screened-cases.jsonl"
    screened_sha = _pinned_sha(
        screened_path,
        hashlib.sha256(screened_path.read_bytes()).hexdigest(),
        "source snapshot screened-cases",
    )
    screened_by_candidate: dict[str, Mapping[str, Any]] = {}
    for screened in _read_jsonl(screened_path, "source snapshot screened-cases"):
        candidate = screened.get("candidate_id")
        if isinstance(candidate, str):
            if candidate in screened_by_candidate:
                raise TargetRawDocketRecoveryError(
                    f"source snapshot repeats screened candidate: {candidate}"
                )
            screened_by_candidate[candidate] = screened
    canonical_raw_manifest = source_snapshot_path / "raw-artifacts.jsonl"
    if source_raw_manifest_path.resolve() != canonical_raw_manifest.resolve():
        raise TargetRawDocketRecoveryError(
            "source raw manifest is not the authenticated snapshot raw-artifacts.jsonl"
        )
    raw_sha = _pinned_sha(
        canonical_raw_manifest,
        expected_source_raw_manifest_sha256,
        "source raw manifest",
    )
    try:
        card = json.loads(source_snapshot_run_card_path.read_bytes())
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError(
            "source snapshot run card is not JSON"
        ) from exc
    if not isinstance(card, dict):
        raise TargetRawDocketRecoveryError("source snapshot run card is not completed")
    typed_card = cast(dict[str, object], card)
    if typed_card.get("status") != "completed":
        raise TargetRawDocketRecoveryError("source snapshot run card is not completed")
    card_snapshot = typed_card.get("snapshot_path")
    if (
        not isinstance(card_snapshot, str)
        or Path(card_snapshot).resolve() != source_snapshot_path.resolve()
    ):
        raise TargetRawDocketRecoveryError(
            "source snapshot run card does not bind source snapshot"
        )
    if not batch_id.strip() or not run_id.strip() or batch_id == run_id:
        raise TargetRawDocketRecoveryError(
            "batch and run identities must be nonempty and distinct"
        )
    if (
        not 1 <= credit_cap <= 500
        or not 1 <= workers <= 10
        or not 1 <= max_pages_per_docket <= 100
    ):
        raise TargetRawDocketRecoveryError(
            "credit cap, workers, or page limit is out of bounds"
        )
    if (
        max_attempts_per_page <= 0
        or provider_breaker_threshold <= 0
        or proxy not in {"basic", "auto", "enhanced"}
    ):
        raise TargetRawDocketRecoveryError("scheduler configuration is invalid")

    selected: dict[str, Mapping[str, Any]] = {}
    for row in _read_jsonl(selection_path, "selection"):
        if row.get("selected") is not True:
            continue
        docket_id = row.get("candidate_id")
        source_url = row.get("source_url")
        if not isinstance(docket_id, str) or _DOCKET_ID.fullmatch(docket_id) is None:
            raise TargetRawDocketRecoveryError(
                "selected target has invalid candidate ID"
            )
        if not isinstance(source_url, str) or not source_url.startswith(
            "https://www.courtlistener.com/docket/"
        ):
            raise TargetRawDocketRecoveryError(
                f"selected target has invalid CourtListener URL: {docket_id}"
            )
        candidate_id = _CANDIDATE_PREFIX + docket_id
        parsed = urlsplit(source_url)
        components = [part for part in parsed.path.split("/") if part]
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.courtlistener.com"
            or len(components) < 2
            or components[0] != "docket"
            or components[1] != docket_id
        ):
            raise TargetRawDocketRecoveryError(
                f"selected URL docket does not match candidate ID: {docket_id}"
            )
        snapshot_source = screened_by_candidate.get(candidate_id)
        if snapshot_source is None:
            snapshot_source = screened_by_candidate.get(docket_id)
        snapshot_candidate_value = (
            snapshot_source.get("candidate")
            if isinstance(snapshot_source, Mapping)
            else None
        )
        snapshot_candidate = (
            cast(Mapping[str, Any], snapshot_candidate_value)
            if isinstance(snapshot_candidate_value, Mapping)
            else None
        )
        snapshot_url = (
            snapshot_candidate.get("url") if snapshot_candidate is not None else None
        )
        if snapshot_url != source_url:
            raise TargetRawDocketRecoveryError(
                f"selected URL is not authenticated by source snapshot: {docket_id}"
            )
        if candidate_id in selected:
            raise TargetRawDocketRecoveryError(
                f"selected target repeats: {candidate_id}"
            )
        selected[candidate_id] = row
    if not selected:
        raise TargetRawDocketRecoveryError("selection contains no selected targets")

    present: set[str] = set()
    for row in _read_jsonl(source_raw_manifest_path, "source raw manifest"):
        candidate_id = row.get("candidate_id")
        sha = row.get("sha256")
        byte_count = row.get("byte_count")
        if (
            not isinstance(candidate_id, str)
            or not isinstance(sha, str)
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise TargetRawDocketRecoveryError("source raw manifest has malformed row")
        if _SHA256.fullmatch(sha.removeprefix("sha256:")) is None:
            raise TargetRawDocketRecoveryError(
                "source raw manifest has invalid content digest"
            )
        # Saturated union snapshots intentionally retain multiple authenticated
        # observations of the same docket.  Presence is candidate-level here;
        # verify_snapshot owns the integrity and conflict checks for each row.
        present.add(candidate_id)

    targets: list[Mapping[str, object]] = []
    for rank, candidate_id in enumerate(sorted(set(selected) - present)):
        source = selected[candidate_id]
        docket_id = candidate_id.removeprefix(_CANDIDATE_PREFIX)
        targets.append(
            {
                "candidate_id": candidate_id,
                "identity": {
                    "courtlistener_docket_id": docket_id,
                    "courtlistener_url": source["source_url"],
                },
                "ranking_key": [rank, candidate_id],
                "screening_metadata": dict(source),
            }
        )
    if not targets:
        raise TargetRawDocketRecoveryError("no selected raw docket gaps remain")
    return TargetRawDocketRecoveryPlan(
        selection_path=str(selection_path.resolve()),
        selection_sha256=selection_sha,
        source_snapshot_path=str(source_snapshot_path.resolve()),
        source_snapshot_manifest_sha256=snapshot_manifest_sha,
        source_snapshot_screened_cases_sha256=screened_sha,
        cycle_hash=expected_cycle_hash,
        source_batch_id=source_batch_id,
        source_batch_digest=source_batch_digest,
        source_snapshot_run_card_path=str(source_snapshot_run_card_path.resolve()),
        source_snapshot_run_card_sha256=card_sha,
        source_raw_manifest_path=str(source_raw_manifest_path.resolve()),
        source_raw_manifest_sha256=raw_sha,
        cycle_store_path=str(cycle_store_path.resolve()),
        batch_id=batch_id,
        run_id=run_id,
        credit_cap=credit_cap,
        workers=workers,
        max_pages_per_docket=max_pages_per_docket,
        max_attempts_per_page=max_attempts_per_page,
        provider_breaker_threshold=provider_breaker_threshold,
        proxy=proxy,
        force_browser=force_browser,
        targets=tuple(targets),
    )


def write_target_raw_docket_recovery_plan(
    path: Path, plan: TargetRawDocketRecoveryPlan
) -> str:
    payload = (
        json.dumps(
            plan.as_record(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )
    if path.exists():
        _require_regular(path, "plan output")
        if path.read_bytes() != payload:
            raise TargetRawDocketRecoveryError(
                "plan output already exists with different bytes"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def target_raw_docket_recovery_receipt_bytes(
    receipt: Mapping[str, object],
) -> bytes:
    """Serialize one deterministic terminal receipt."""
    if receipt.get("schema_version") != TARGET_RAW_DOCKET_RECOVERY_RECEIPT_SCHEMA:
        raise TargetRawDocketRecoveryError("recovery receipt schema is invalid")
    return (
        json.dumps(
            dict(receipt),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        + b"\n"
    )


def write_target_raw_docket_recovery_receipt(
    path: Path, receipt: Mapping[str, object]
) -> str:
    """Publish or exact-byte resume one deterministic terminal receipt."""

    payload = target_raw_docket_recovery_receipt_bytes(receipt)
    if path.exists():
        _require_regular(path, "recovery receipt output")
        if path.read_bytes() != payload:
            raise TargetRawDocketRecoveryError(
                "recovery receipt already exists with different bytes"
            )
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def load_target_raw_docket_recovery_plan(
    path: Path, expected_sha256: str
) -> TargetRawDocketRecoveryPlan:
    _pinned_sha(path, expected_sha256, "plan")
    try:
        record = json.loads(path.read_bytes())
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise TargetRawDocketRecoveryError("plan is not JSON") from exc
    if not isinstance(record, dict):
        raise TargetRawDocketRecoveryError("plan schema is invalid")
    typed_record = cast(dict[str, object], record)
    if typed_record.get("schema_version") != TARGET_RAW_DOCKET_RECOVERY_PLAN_SCHEMA:
        raise TargetRawDocketRecoveryError("plan schema is invalid")
    fields = {field for field in TargetRawDocketRecoveryPlan.__dataclass_fields__}
    targets_value = typed_record.get("targets")
    targets = (
        cast(list[object], targets_value) if isinstance(targets_value, list) else None
    )
    if (
        set(typed_record) != {"schema_version", "target_count", *fields}
        or targets is None
        or typed_record.get("target_count") != len(targets)
    ):
        raise TargetRawDocketRecoveryError("plan fields are invalid")
    try:
        values = {field: cast(Any, typed_record[field]) for field in fields}
        values["targets"] = tuple(cast(Mapping[str, object], item) for item in targets)
        return TargetRawDocketRecoveryPlan(**values)
    except TypeError as exc:
        raise TargetRawDocketRecoveryError("plan fields are malformed") from exc


def execute_target_raw_docket_recovery(
    *,
    plan: TargetRawDocketRecoveryPlan,
    scheduler: BudgetedFirecrawlScheduler,
    raw_html_dir: Path,
) -> tuple[
    list[Mapping[str, object]], list[Mapping[str, object]], Mapping[str, object]
]:
    """Run complete pagination and return screen-firecrawl-compatible records."""

    # Recheck every external pin immediately before provider activity.
    _pinned_sha(Path(plan.selection_path), plan.selection_sha256, "selection")
    try:
        snapshot_manifest = verify_snapshot(
            Path(plan.source_snapshot_path),
            expected_cycle_hash=plan.cycle_hash,
            require_complete=True,
            require_saturated=True,
        )
        snapshot_firecrawl_screening_source_count(
            snapshot_manifest, require_current=True
        )
    except (SnapshotVerificationError, ValueError) as exc:
        raise TargetRawDocketRecoveryError(
            f"source snapshot is not current complete and saturated: {exc}"
        ) from exc
    _pinned_sha(
        Path(plan.source_snapshot_path) / "manifest.json",
        plan.source_snapshot_manifest_sha256,
        "source snapshot manifest",
    )
    _pinned_sha(
        Path(plan.source_snapshot_path) / "screened-cases.jsonl",
        plan.source_snapshot_screened_cases_sha256,
        "source snapshot screened-cases",
    )
    _pinned_sha(
        Path(plan.source_snapshot_run_card_path),
        plan.source_snapshot_run_card_sha256,
        "source snapshot run card",
    )
    _pinned_sha(
        Path(plan.source_raw_manifest_path),
        plan.source_raw_manifest_sha256,
        "source raw manifest",
    )
    result = acquire_ranked_dockets(
        records=plan.targets,
        scheduler=scheduler,
        limit=len(plan.targets),
        max_pages_per_docket=plan.max_pages_per_docket,
        decision_anchor=None,
    )
    successes: list[Mapping[str, object]] = []
    completed_at_by_url = {
        attempt.request_url: attempt.completed_at
        for attempt in scheduler.store.firecrawl_attempts(scheduler.run_id)
        if attempt.status == "succeeded" and attempt.completed_at is not None
    }
    for bundle in result.bundles:
        raw = render_complete_docket_html(bundle).encode()
        path = raw_html_dir / f"{bundle.docket_id}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise TargetRawDocketRecoveryError(
                f"raw output already exists with different bytes: {bundle.docket_id}"
            )
        if not path.exists():
            path.write_bytes(raw)
        retrieval_times = [
            completed_at_by_url.get(page.source_url) for page in bundle.pages
        ]
        if not retrieval_times or any(value is None for value in retrieval_times):
            raise TargetRawDocketRecoveryError(
                f"durable retrieval time is missing: {bundle.docket_id}"
            )
        retrieved_at = max(cast(list[str], retrieval_times))
        target = next(
            item
            for item in plan.targets
            if item["candidate_id"] == _CANDIDATE_PREFIX + bundle.docket_id
        )
        screening_metadata = dict(
            cast(Mapping[str, object], target["screening_metadata"])
        )
        screening_metadata["case_id"] = target["candidate_id"]
        successes.append(
            {
                "case_id": target["candidate_id"],
                "candidate_id": target["candidate_id"],
                "source_url": bundle.base_url,
                "docket_id": bundle.docket_id,
                "raw_html_path": str(path.resolve()),
                "case_metadata": screening_metadata,
                "raw_html_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "raw_html_bytes": len(raw),
                "retrieved_at": retrieved_at,
                "pagination_complete_for_anchor_window": True,
                "page_count": len(bundle.pages),
            }
        )
    exclusions: list[Mapping[str, object]] = [
        dict(failure.as_record()) for failure in result.failures
    ]
    summary: Mapping[str, object] = {
        "schema_version": TARGET_RAW_DOCKET_RECOVERY_SUMMARY_SCHEMA,
        **dict(result.credit_summary),
        "target_count": len(plan.targets),
        "success_count": len(successes),
        "exclusion_count": len(exclusions),
        "pagination_complete_before_screening": True,
        "source_snapshot_manifest_sha256": plan.source_snapshot_manifest_sha256,
        "source_batch_id": plan.source_batch_id,
        "source_batch_digest": plan.source_batch_digest,
    }
    return successes, exclusions, summary
