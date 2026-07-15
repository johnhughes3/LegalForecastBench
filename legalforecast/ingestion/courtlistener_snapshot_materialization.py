"""Verify provider-free inputs for a direct CourtListener discovery snapshot."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast


class CourtListenerSnapshotMaterializationError(ValueError):
    """Raised when discovery evidence cannot support an immutable snapshot."""


@dataclass(frozen=True, slots=True)
class VerifiedRawArtifact:
    candidate_id: str
    path: Path
    content: bytes
    sha256: str
    byte_count: int
    retrieved_at: str


@dataclass(frozen=True, slots=True)
class VerifiedCourtListenerDiscovery:
    run_card_sha256: str
    cycle_hash: str
    batch_digest: str
    eligibility_anchor: date
    query_terms: tuple[str, ...]
    screened_cases: tuple[Mapping[str, Any], ...]
    exclusions: tuple[Mapping[str, Any], ...]
    search_pages: tuple[Mapping[str, Any], ...]
    raw_artifacts: tuple[VerifiedRawArtifact, ...]
    stage_commitment: Mapping[str, Any]


_SHA256 = re.compile(r"[0-9a-f]{64}")
_OUTPUT_NAMES = (
    "screened_cases",
    "exclusions",
    "raw_html_directory",
    "summary",
    "search_pages",
    "raw_artifacts",
)


def verify_courtlistener_discovery(
    *,
    run_card_path: Path,
    expected_run_card_sha256: str,
    expected_cycle_hash: str,
    expected_batch_digest: str,
    cycle_policy: Mapping[str, object],
    batch_config: Mapping[str, object],
) -> VerifiedCourtListenerDiscovery:
    """Verify one completed, saturated, hash-bound direct discovery run."""

    if _SHA256.fullmatch(expected_run_card_sha256) is None:
        raise CourtListenerSnapshotMaterializationError(
            "expected discovery run-card SHA-256 must be 64 lowercase hex characters"
        )
    run_card_bytes = _read_regular_file(run_card_path, "discovery run card")
    actual_run_card_sha256 = hashlib.sha256(run_card_bytes).hexdigest()
    if actual_run_card_sha256 != expected_run_card_sha256:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card SHA-256 mismatch"
        )
    run_card = _json_object(run_card_bytes, "discovery run card")
    if (
        run_card.get("schema_version") != "legalforecast.acquisition_run_card.v1"
        or run_card.get("stage") != "discover-courtlistener"
        or run_card.get("status") != "completed"
        or run_card.get("dry_run") is not False
        or run_card.get("execute") is not True
        or run_card.get("paid_activity_requested") is not False
        or run_card.get("paid_activity_executed") is not False
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card is not a completed noncharging execution"
        )
    if run_card.get("cycle_hash") != expected_cycle_hash:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card cycle hash mismatch"
        )
    if run_card.get("batch_digest") != expected_batch_digest:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card batch digest mismatch"
        )
    output_paths_value = run_card.get("output_paths")
    if not isinstance(output_paths_value, list):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card lacks the required transcript and artifact outputs"
        )
    output_path_items = cast(list[object], output_paths_value)
    if len(output_path_items) != 6:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card lacks the required transcript and artifact outputs"
        )
    output_paths = tuple(
        _absolute_path(value, f"discovery output {index}")
        for index, value in enumerate(output_path_items, start=1)
    )
    paths = dict(zip(_OUTPUT_NAMES, output_paths, strict=True))
    commitments_value = run_card.get("output_commitments")
    if not isinstance(commitments_value, Mapping):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run card lacks output commitments"
        )
    commitments = cast(Mapping[str, object], commitments_value)
    committed_files = {
        name: paths[name]
        for name in (
            "screened_cases",
            "exclusions",
            "summary",
            "search_pages",
            "raw_artifacts",
        )
    }
    if set(commitments) != set(committed_files):
        raise CourtListenerSnapshotMaterializationError(
            "discovery output commitment set is incomplete"
        )
    for name, path in committed_files.items():
        _verify_file_commitment(path, commitments[name], name)

    screened_cases = tuple(_jsonl(paths["screened_cases"], "screened cases"))
    exclusions = tuple(_jsonl(paths["exclusions"], "discovery exclusions"))
    search_pages = tuple(_jsonl(paths["search_pages"], "search-page transcript"))
    raw_manifest = tuple(_jsonl(paths["raw_artifacts"], "raw-artifact manifest"))
    summary = _json_object(
        _read_regular_file(paths["summary"], "discovery summary"),
        "discovery summary",
    )

    anchor = _validate_frozen_identity(
        run_card=run_card,
        summary=summary,
        cycle_policy=cycle_policy,
        batch_config=batch_config,
    )
    accepted_ids = _accepted_ids(screened_cases, anchor=anchor)
    excluded_ids = _excluded_ids(exclusions)
    if accepted_ids & excluded_ids:
        raise CourtListenerSnapshotMaterializationError(
            "a candidate appears in both screened cases and exclusions"
        )
    outcome_ids = accepted_ids | excluded_ids
    query_terms = _string_list(summary.get("query_terms"), "summary query_terms")
    transcript_ids = _validate_transcript(
        search_pages,
        summary=summary,
        query_terms=query_terms,
    )
    if transcript_ids != outcome_ids:
        raise CourtListenerSnapshotMaterializationError(
            "discovery transcript candidates do not exactly match terminal outcomes"
        )
    _validate_summary_counts(
        run_card=run_card,
        summary=summary,
        accepted_count=len(accepted_ids),
        excluded_count=len(excluded_ids),
        transcript_count=len(transcript_ids),
    )
    artifacts = _verify_raw_artifacts(
        raw_html_directory=paths["raw_html_directory"],
        manifest=raw_manifest,
        retrieved_at=_string(run_card.get("generated_at"), "run-card generated_at"),
        accepted_ids=accepted_ids,
        exclusions=exclusions,
        outcome_ids=outcome_ids,
    )
    stage_commitment = {
        "schema_version": ("legalforecast.courtlistener_discovery_snapshot_inputs.v1"),
        "discovery_run_card_sha256": actual_run_card_sha256,
        "cycle_hash": expected_cycle_hash,
        "batch_digest": expected_batch_digest,
        "eligibility_anchor": anchor.isoformat(),
        "source_saturated": True,
        "accepted_case_count": len(accepted_ids),
        "excluded_case_count": len(excluded_ids),
        "candidate_count": len(outcome_ids),
        "output_commitments": json.loads(_canonical_json(commitments)),
    }
    return VerifiedCourtListenerDiscovery(
        run_card_sha256=actual_run_card_sha256,
        cycle_hash=expected_cycle_hash,
        batch_digest=expected_batch_digest,
        eligibility_anchor=anchor,
        query_terms=query_terms,
        screened_cases=screened_cases,
        exclusions=exclusions,
        search_pages=search_pages,
        raw_artifacts=artifacts,
        stage_commitment=stage_commitment,
    )


def _validate_frozen_identity(
    *,
    run_card: Mapping[str, Any],
    summary: Mapping[str, Any],
    cycle_policy: Mapping[str, object],
    batch_config: Mapping[str, object],
) -> date:
    if (
        summary.get("schema_version")
        != "legalforecast.courtlistener_discovery_summary.v1"
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary schema mismatch"
        )
    if summary.get("dry_run") is not False:
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary is not an executed result"
        )
    anchor_text = _string(summary.get("anchor_date"), "summary anchor_date")
    try:
        anchor = date.fromisoformat(anchor_text)
    except ValueError as error:
        raise CourtListenerSnapshotMaterializationError(
            "summary anchor_date is not an ISO date"
        ) from error
    if cycle_policy.get("eligibility_anchor") != anchor_text:
        raise CourtListenerSnapshotMaterializationError(
            "discovery anchor does not match the frozen cycle policy"
        )
    if run_card.get("anchor_date") != anchor_text:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card anchor does not match its summary"
        )
    expected_batch = {
        "provider": "courtlistener",
        "search_window_start": summary.get("search_window_start"),
        "search_window_end": summary.get("search_window_end"),
        "query_terms": summary.get("query_terms"),
        "target_clean_cases": summary.get("target_clean_cases"),
        "max_candidates": summary.get("max_candidates"),
        "search_page_size": summary.get("search_page_size"),
        "docket_html_source": summary.get("docket_html_source"),
    }
    if dict(batch_config) != expected_batch:
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary does not match the frozen batch configuration"
        )
    per_term = summary.get("per_term")
    query_terms = _string_list(summary.get("query_terms"), "summary query_terms")
    if not isinstance(per_term, Mapping):
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary does not include every frozen query term"
        )
    per_term_records = cast(Mapping[str, object], per_term)
    if set(per_term_records) != set(query_terms):
        raise CourtListenerSnapshotMaterializationError(
            "discovery summary does not include every frozen query term"
        )
    for term in query_terms:
        record_value = per_term_records[term]
        if not isinstance(record_value, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"discovery diagnostic is invalid for query term {term!r}"
            )
        record = cast(Mapping[str, object], record_value)
        if (
            record.get("terminal_status") != "exhausted"
            or record.get("limit_bound") is not False
        ):
            raise CourtListenerSnapshotMaterializationError(
                f"discovery is not saturated: query term {term!r} was not exhausted"
            )
    if (
        summary.get("target_met") is not False
        or summary.get("candidate_limit_reached") is not False
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery is not saturated: a target or candidate limit bound the run"
        )
    return anchor


def _accepted_ids(records: tuple[Mapping[str, Any], ...], *, anchor: date) -> set[str]:
    ids: set[str] = set()
    for row_number, record in enumerate(records, start=1):
        candidate = record.get("candidate")
        if not isinstance(candidate, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"screened case row {row_number} lacks candidate metadata"
            )
        candidate_record = cast(Mapping[str, object], candidate)
        candidate_id = _string(
            candidate_record.get("docket_id"),
            f"screened case row {row_number} docket_id",
        )
        if candidate_id in ids:
            raise CourtListenerSnapshotMaterializationError(
                f"duplicate screened candidate {candidate_id}"
            )
        metadata = candidate_record.get("metadata")
        if not isinstance(metadata, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate identity mismatch for {candidate_id}"
            )
        metadata_record = cast(Mapping[str, object], metadata)
        if metadata_record.get("case_id") != candidate_id:
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate identity mismatch for {candidate_id}"
            )
        if record.get("eligibility_anchor_date") != anchor.isoformat():
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate {candidate_id} has different anchor lineage"
            )
        disposition = _string(
            record.get("first_written_mtd_disposition_date"),
            f"screened candidate {candidate_id} disposition date",
        )
        try:
            disposition_date = date.fromisoformat(disposition)
        except ValueError as error:
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate {candidate_id} disposition date is invalid"
            ) from error
        if disposition_date < anchor:
            raise CourtListenerSnapshotMaterializationError(
                f"screened candidate {candidate_id} predates the eligibility anchor"
            )
        ids.add(candidate_id)
    return ids


def _excluded_ids(records: tuple[Mapping[str, Any], ...]) -> set[str]:
    ids: set[str] = set()
    for row_number, record in enumerate(records, start=1):
        candidate_id = _string(
            record.get("candidate_id"), f"exclusion row {row_number} candidate_id"
        )
        if candidate_id in ids:
            raise CourtListenerSnapshotMaterializationError(
                f"duplicate excluded candidate {candidate_id}"
            )
        if record.get("stage") == "retrieval":
            raise CourtListenerSnapshotMaterializationError(
                "transient CourtListener retrieval outcome is unresolved: "
                f"{candidate_id}"
            )
        ids.add(candidate_id)
    return ids


def _validate_transcript(
    pages: tuple[Mapping[str, Any], ...],
    *,
    summary: Mapping[str, Any],
    query_terms: tuple[str, ...],
) -> set[str]:
    pages_by_term: dict[str, list[Mapping[str, Any]]] = {
        term: [] for term in query_terms
    }
    all_ids: set[str] = set()
    total_hits = 0
    seen_hits: dict[tuple[str, str], str] = {}
    for row_number, page in enumerate(pages, start=1):
        if page.get("schema_version") != (
            "legalforecast.courtlistener_search_page_transcript.v1"
        ):
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript row {row_number} has wrong schema"
            )
        term = _string(page.get("term"), f"search transcript row {row_number} term")
        if term not in pages_by_term:
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript contains unknown query term {term!r}"
            )
        hits = page.get("hits")
        if not isinstance(hits, list):
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript row {row_number} hits must be a list"
            )
        page_provider_ids: set[str] = set()
        for raw_hit in cast(list[object], hits):
            if not isinstance(raw_hit, Mapping):
                raise CourtListenerSnapshotMaterializationError(
                    f"search transcript row {row_number} contains a non-object hit"
                )
            hit = cast(Mapping[str, object], raw_hit)
            provider_hit_id = _string(hit.get("provider_hit_id"), "provider_hit_id")
            candidate_id = _string(hit.get("candidate_id"), "candidate_id")
            payload = hit.get("payload")
            if not isinstance(payload, Mapping):
                raise CourtListenerSnapshotMaterializationError(
                    f"search hit {provider_hit_id} payload is not an object"
                )
            if provider_hit_id in page_provider_ids:
                raise CourtListenerSnapshotMaterializationError(
                    f"duplicate provider hit within transcript page: {provider_hit_id}"
                )
            page_provider_ids.add(provider_hit_id)
            payload_record = cast(Mapping[str, object], payload)
            identity = _canonical_json(
                {"candidate_id": candidate_id, "payload": payload_record}
            )
            prior = seen_hits.get((term, provider_hit_id))
            if prior is not None and prior != identity:
                raise CourtListenerSnapshotMaterializationError(
                    f"provider hit identity changed for {provider_hit_id}"
                )
            seen_hits[(term, provider_hit_id)] = identity
            all_ids.add(candidate_id)
            total_hits += 1
        pages_by_term[term].append(page)

    per_term = cast(Mapping[str, object], summary["per_term"])
    for term in query_terms:
        term_pages = pages_by_term[term]
        if not term_pages:
            raise CourtListenerSnapshotMaterializationError(
                f"search transcript is missing query term {term!r}"
            )
        expected_cursor: str | None = None
        term_ids: set[str] = set()
        for index, page in enumerate(term_pages):
            if page.get("request_cursor") != expected_cursor:
                raise CourtListenerSnapshotMaterializationError(
                    f"search transcript cursor chain is broken for {term!r}"
                )
            terminal = page.get("terminal_status")
            is_last = index == len(term_pages) - 1
            if is_last:
                if terminal != "exhausted" or page.get("next_cursor") is not None:
                    raise CourtListenerSnapshotMaterializationError(
                        f"search transcript is not exhausted for {term!r}"
                    )
            else:
                next_cursor = page.get("next_cursor")
                if (
                    terminal is not None
                    or not isinstance(next_cursor, str)
                    or not next_cursor
                ):
                    raise CourtListenerSnapshotMaterializationError(
                        f"search transcript has an incomplete page for {term!r}"
                    )
                expected_cursor = next_cursor
            for raw_hit in cast(list[object], page["hits"]):
                hit = cast(Mapping[str, object], raw_hit)
                term_ids.add(cast(str, hit["candidate_id"]))
        diagnostic = per_term[term]
        if not isinstance(diagnostic, Mapping):
            raise CourtListenerSnapshotMaterializationError(
                f"summary diagnostic for {term!r} is invalid"
            )
        diagnostic_record = cast(Mapping[str, object], diagnostic)
        if diagnostic_record.get("request_count") != len(
            term_pages
        ) or diagnostic_record.get("candidate_count") != len(term_ids):
            raise CourtListenerSnapshotMaterializationError(
                f"summary diagnostic count mismatch for {term!r}"
            )
    if summary.get("search_hit_count") != total_hits:
        raise CourtListenerSnapshotMaterializationError(
            "summary search-hit count does not match the transcript"
        )
    if summary.get("duplicate_search_hit_count") != total_hits - len(all_ids):
        raise CourtListenerSnapshotMaterializationError(
            "summary duplicate-hit count does not match the transcript"
        )
    return all_ids


def _validate_summary_counts(
    *,
    run_card: Mapping[str, Any],
    summary: Mapping[str, Any],
    accepted_count: int,
    excluded_count: int,
    transcript_count: int,
) -> None:
    processed = accepted_count + excluded_count
    expected = {
        "accepted_case_count": accepted_count,
        "excluded_case_count": excluded_count,
        "processed_candidate_count": processed,
        "unique_candidate_count": transcript_count,
    }
    for name, value in expected.items():
        if summary.get(name) != value:
            raise CourtListenerSnapshotMaterializationError(
                f"discovery summary count mismatch: {name}"
            )
    if run_card.get("record_count") != accepted_count:
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card record count mismatch"
        )
    if (
        run_card.get("accepted_case_count") != accepted_count
        or run_card.get("excluded_case_count") != excluded_count
    ):
        raise CourtListenerSnapshotMaterializationError(
            "discovery run-card outcome counts do not reconcile"
        )


def _verify_raw_artifacts(
    *,
    raw_html_directory: Path,
    manifest: tuple[Mapping[str, Any], ...],
    retrieved_at: str,
    accepted_ids: set[str],
    exclusions: tuple[Mapping[str, Any], ...],
    outcome_ids: set[str],
) -> tuple[VerifiedRawArtifact, ...]:
    if raw_html_directory.is_symlink() or not raw_html_directory.is_dir():
        raise CourtListenerSnapshotMaterializationError(
            "raw CourtListener HTML output is not a regular directory"
        )
    artifacts: list[VerifiedRawArtifact] = []
    manifest_ids: set[str] = set()
    manifest_names: set[str] = set()
    for row_number, record in enumerate(manifest, start=1):
        candidate_id = _string(
            record.get("candidate_id"), f"raw manifest row {row_number} candidate_id"
        )
        if candidate_id not in outcome_ids or candidate_id in manifest_ids:
            raise CourtListenerSnapshotMaterializationError(
                f"raw manifest candidate identity is invalid: {candidate_id}"
            )
        relative = _string(
            record.get("relative_path"), f"raw manifest row {row_number} path"
        )
        if relative != f"{candidate_id}.html" or Path(relative).name != relative:
            raise CourtListenerSnapshotMaterializationError(
                f"raw manifest path is unsafe for {candidate_id}"
            )
        path = raw_html_directory / relative
        content = _read_regular_file(path, f"raw HTML for {candidate_id}")
        digest = hashlib.sha256(content).hexdigest()
        if record.get("sha256") != digest or record.get("byte_count") != len(content):
            raise CourtListenerSnapshotMaterializationError(
                f"raw HTML commitment mismatch for {candidate_id}"
            )
        if not content.strip():
            raise CourtListenerSnapshotMaterializationError(
                f"raw HTML is empty for {candidate_id}"
            )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise CourtListenerSnapshotMaterializationError(
                f"raw HTML is not UTF-8 for {candidate_id}"
            ) from error
        manifest_ids.add(candidate_id)
        manifest_names.add(relative)
        artifacts.append(
            VerifiedRawArtifact(
                candidate_id=candidate_id,
                path=path,
                content=content,
                sha256=digest,
                byte_count=len(content),
                retrieved_at=retrieved_at,
            )
        )
    actual_names: set[str] = set()
    for path in raw_html_directory.iterdir():
        if path.is_symlink() or not path.is_file():
            raise CourtListenerSnapshotMaterializationError(
                f"unexpected non-regular raw HTML artifact: {path}"
            )
        actual_names.add(path.name)
    if actual_names != manifest_names:
        raise CourtListenerSnapshotMaterializationError(
            "raw HTML directory does not exactly match its committed manifest"
        )
    required_ids = set(accepted_ids)
    for exclusion in exclusions:
        notes = exclusion.get("notes")
        if exclusion.get("stage") not in {"discovery", "retrieval"} or (
            isinstance(notes, str)
            and "failed the strict MTD acquisition screen" in notes
        ):
            required_ids.add(cast(str, exclusion["candidate_id"]))
    missing = sorted(required_ids - manifest_ids)
    if missing:
        raise CourtListenerSnapshotMaterializationError(
            "discovery outcomes are missing required raw HTML: " + ", ".join(missing)
        )
    return tuple(artifacts)


def _verify_file_commitment(path: Path, value: object, name: str) -> None:
    if not isinstance(value, Mapping):
        raise CourtListenerSnapshotMaterializationError(
            f"discovery commitment for {name} is invalid"
        )
    payload = _read_regular_file(path, f"discovery output {name}")
    commitment = cast(Mapping[str, object], value)
    if (
        commitment.get("sha256") != hashlib.sha256(payload).hexdigest()
        or commitment.get("byte_count") != len(payload)
        or commitment.get("row_count") != payload.count(b"\n")
    ):
        raise CourtListenerSnapshotMaterializationError(
            f"discovery output commitment mismatch: {name}"
        )


def _read_regular_file(path: Path, label: str) -> bytes:
    if not path.is_absolute():
        path = path.resolve()
    if path.is_symlink() or not path.is_file():
        raise CourtListenerSnapshotMaterializationError(
            f"{label} is not a regular file: {path}"
        )
    return path.read_bytes()


def _jsonl(path: Path, label: str) -> list[Mapping[str, Any]]:
    payload = _read_regular_file(path, label)
    records: list[Mapping[str, Any]] = []
    for row_number, line in enumerate(payload.splitlines(), start=1):
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError as error:
            raise CourtListenerSnapshotMaterializationError(
                f"{label} row {row_number} is invalid JSON"
            ) from error
        if not isinstance(value, dict):
            raise CourtListenerSnapshotMaterializationError(
                f"{label} row {row_number} is not an object"
            )
        records.append(cast(dict[str, Any], value))
    return records


def _json_object(payload: bytes, label: str) -> Mapping[str, Any]:
    try:
        value: object = json.loads(payload)
    except json.JSONDecodeError as error:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} is invalid JSON"
        ) from error
    if not isinstance(value, dict):
        raise CourtListenerSnapshotMaterializationError(f"{label} is not an object")
    return cast(dict[str, Any], value)


def _absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise CourtListenerSnapshotMaterializationError(f"{label} is invalid")
    path = Path(value)
    if not path.is_absolute():
        raise CourtListenerSnapshotMaterializationError(f"{label} must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be an existing canonical absolute path without symlinks"
        ) from error
    if path != resolved:
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must be an existing canonical absolute path without symlinks"
        )
    return path


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CourtListenerSnapshotMaterializationError(f"{label} is required")
    return value.strip()


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CourtListenerSnapshotMaterializationError(f"{label} must be a list")
    result = tuple(_string(item, label) for item in cast(list[object], value))
    if not result or len(set(result)) != len(result):
        raise CourtListenerSnapshotMaterializationError(
            f"{label} must contain unique values"
        )
    return result


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
