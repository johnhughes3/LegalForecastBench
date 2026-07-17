"""Provider-free sealing of a budget-exhausted ranked Firecrawl docket run."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import parse_qs, urlsplit

from legalforecast.ingestion.budgeted_docket_acquisition import (
    DocketAcquisitionFailure,
    RankedDocketTarget,
    ranked_docket_targets,
    render_complete_docket_html,
)
from legalforecast.ingestion.budgeted_firecrawl import (
    FirecrawlArtifactError,
    FirecrawlPageRecord,
    is_retryable_target_accepted,
    load_successful_firecrawl_pages,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerWebDocketPage,
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    FirecrawlAttempt,
    FirecrawlTarget,
)
from legalforecast.ingestion.firecrawl_docket_pagination import (
    CourtListenerDocketBundle,
    CourtListenerDocketPaginationError,
    canonical_courtlistener_docket_page_url,
    may_stop_at_anchor_boundary,
    paginate_courtlistener_docket,
)

RANKED_FIRECRAWL_SEAL_SCHEMA = "legalforecast.ranked_firecrawl_seal.v1"
RANKED_FIRECRAWL_COMBINED_CREDIT_CEILING = 50_000
RANKED_FIRECRAWL_PARTITION_SCHEMA = (
    "legalforecast.ranked_firecrawl_recovery_partition.v1"
)
_DOCKET_PATH = re.compile(r"^/docket/(?P<docket_id>[1-9][0-9]*)/[^/]+/$")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class RankedFirecrawlRecoveryError(ValueError):
    """Raised when an interrupted run cannot be sealed without inference."""


@dataclass(frozen=True, slots=True)
class UnresolvedRankedDocket:
    """One docket that must be reacquired in a separately authorized store."""

    candidate_id: str
    docket_id: str
    rank: int
    reason: str
    required_page_number: int
    target_status: str | None
    last_failure_code: str | None

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": RANKED_FIRECRAWL_PARTITION_SCHEMA,
            "partition": "unresolved",
            **asdict(self),
        }


@dataclass(frozen=True, slots=True)
class SealedRankedFirecrawlRun:
    """Exact terminal/unresolved projection of one immutable attempt ledger."""

    run_id: str
    source_cycle_hash: str
    source_batch_id: str
    source_run_config_sha256: str
    source_credit_cap: int
    source_candidate_count: int
    bundles: tuple[CourtListenerDocketBundle, ...]
    failures: tuple[DocketAcquisitionFailure, ...]
    unresolved: tuple[UnresolvedRankedDocket, ...]
    target_commitment_sha256: str
    attempt_commitment_sha256: str
    credit_summary: Mapping[str, object]
    source_ledger_as_of: str
    retrieved_at_by_docket: Mapping[str, str]
    rank_by_docket: Mapping[str, int]
    provider_activity_requested: bool = False
    provider_activity_executed: bool = False
    paid_activity_requested: bool = False
    paid_activity_executed: bool = False

    @property
    def terminal_docket_ids(self) -> tuple[str, ...]:
        terminal = {bundle.docket_id for bundle in self.bundles} | {
            failure.docket_id for failure in self.failures
        }
        return tuple(
            docket_id
            for docket_id in self._ranked_docket_ids()
            if docket_id in terminal
        )

    @property
    def unresolved_docket_ids(self) -> tuple[str, ...]:
        return tuple(item.docket_id for item in self.unresolved)

    def _ranked_docket_ids(self) -> tuple[str, ...]:
        return tuple(
            docket_id
            for docket_id, _rank in sorted(
                self.rank_by_docket.items(), key=lambda item: item[1]
            )
        )


@dataclass(frozen=True, slots=True)
class SealedRankedFirecrawlArtifacts:
    """Deterministic screening-compatible outputs and recovery manifests."""

    successes: tuple[Mapping[str, object], ...]
    exclusions: tuple[Mapping[str, object], ...]
    terminal_manifest: tuple[Mapping[str, object], ...]
    unresolved_manifest: tuple[Mapping[str, object], ...]
    raw_html_by_docket: Mapping[str, bytes]


@dataclass(frozen=True, slots=True)
class VerifiedRecoveryPartition:
    """Externally pinned terminal or unresolved partition authority."""

    docket_ids: tuple[str, ...]
    authority: Mapping[str, object]


def build_sealed_ranked_firecrawl_artifacts(
    *,
    sealed: SealedRankedFirecrawlRun,
    records: Sequence[Mapping[str, Any]],
    raw_html_dir: Path,
    lineage_flags: Mapping[str, object] | None = None,
) -> SealedRankedFirecrawlArtifacts:
    """Build deterministic normal outputs without writing any source state."""

    ranked = ranked_docket_targets(records, limit=len(records))
    frozen_lineage = dict(lineage_flags or {})
    record_by_docket = {
        target.docket_id: record for target, record in zip(ranked, records, strict=True)
    }
    bundle_by_docket = {bundle.docket_id: bundle for bundle in sealed.bundles}
    failure_by_docket = {failure.docket_id: failure for failure in sealed.failures}
    unresolved_by_docket = {item.docket_id: item for item in sealed.unresolved}
    successes: list[Mapping[str, object]] = []
    exclusions: list[Mapping[str, object]] = []
    terminal_manifest: list[Mapping[str, object]] = []
    unresolved_manifest: list[Mapping[str, object]] = []
    raw_html_by_docket: dict[str, bytes] = {}
    for target in ranked:
        source_record = record_by_docket[target.docket_id]
        ranked_sha256 = _canonical_sha256(source_record)
        bundle = bundle_by_docket.get(target.docket_id)
        if bundle is not None:
            raw_bytes = render_complete_docket_html(bundle).encode()
            raw_path = (raw_html_dir / f"{target.docket_id}.html").resolve()
            metadata = source_record.get("screening_metadata")
            if not isinstance(metadata, Mapping):
                raise RankedFirecrawlRecoveryError(
                    f"ranked record lacks screening metadata: {target.docket_id}"
                )
            case_metadata = dict(cast(Mapping[str, object], metadata))
            case_metadata["case_id"] = target.candidate_id
            success: Mapping[str, object] = {
                "case_id": target.candidate_id,
                "candidate_id": target.candidate_id,
                "source_url": bundle.base_url,
                "docket_id": target.docket_id,
                "raw_html_path": str(raw_path),
                "case_metadata": case_metadata,
                "raw_html_sha256": "sha256:" + hashlib.sha256(raw_bytes).hexdigest(),
                "raw_html_bytes": len(raw_bytes),
                "retrieved_at": sealed.retrieved_at_by_docket[target.docket_id],
                "pagination_complete_for_anchor_window": True,
                "page_count": len(bundle.pages),
                **frozen_lineage,
            }
            successes.append(success)
            raw_html_by_docket[target.docket_id] = raw_bytes
            terminal_manifest.append(
                {
                    "schema_version": RANKED_FIRECRAWL_PARTITION_SCHEMA,
                    "partition": "terminal",
                    "terminal_outcome": "success",
                    "candidate_id": target.candidate_id,
                    "docket_id": target.docket_id,
                    "rank": target.rank,
                    "ranked_record_sha256": ranked_sha256,
                    "outcome_record_sha256": _canonical_sha256(success),
                    "raw_html_sha256": hashlib.sha256(raw_bytes).hexdigest(),
                }
            )
            continue
        failure = failure_by_docket.get(target.docket_id)
        if failure is not None:
            exclusion = {**failure.as_record(), **frozen_lineage}
            exclusions.append(exclusion)
            terminal_manifest.append(
                {
                    "schema_version": RANKED_FIRECRAWL_PARTITION_SCHEMA,
                    "partition": "terminal",
                    "terminal_outcome": "exclusion",
                    "candidate_id": target.candidate_id,
                    "docket_id": target.docket_id,
                    "rank": target.rank,
                    "ranked_record_sha256": ranked_sha256,
                    "outcome_record_sha256": _canonical_sha256(exclusion),
                    "raw_html_sha256": None,
                }
            )
            continue
        item = unresolved_by_docket.get(target.docket_id)
        if item is None:
            raise RankedFirecrawlRecoveryError(
                f"sealed partition omitted docket {target.docket_id}"
            )
        unresolved_manifest.append(
            {
                **item.as_record(),
                "ranked_record_sha256": ranked_sha256,
                **frozen_lineage,
            }
        )
    return SealedRankedFirecrawlArtifacts(
        successes=tuple(successes),
        exclusions=tuple(exclusions),
        terminal_manifest=tuple(terminal_manifest),
        unresolved_manifest=tuple(unresolved_manifest),
        raw_html_by_docket=raw_html_by_docket,
    )


def canonical_recovery_commitment(value: object) -> str:
    """Return the canonical lowercase SHA-256 used by recovery run cards."""

    return _canonical_sha256(value)


def validate_fresh_recovery_credit_authority(
    *,
    source_credit_cap: int,
    total_prior_authorized_credits: int,
    fresh_recovery_credit_cap: int,
    reserved_credits_per_attempt: int,
) -> None:
    """Fail closed unless all Firecrawl authority stays strictly below 50,000."""

    valid = (
        source_credit_cap > 0
        and total_prior_authorized_credits >= source_credit_cap
        and total_prior_authorized_credits < RANKED_FIRECRAWL_COMBINED_CREDIT_CEILING
        and 0 <= fresh_recovery_credit_cap <= 45_000
        and reserved_credits_per_attempt > 0
        and fresh_recovery_credit_cap % reserved_credits_per_attempt == 0
        and total_prior_authorized_credits + fresh_recovery_credit_cap
        < RANKED_FIRECRAWL_COMBINED_CREDIT_CEILING
    )
    if not valid:
        raise RankedFirecrawlRecoveryError(
            "fresh recovery cap violates the strict combined 50,000-credit "
            "ceiling, prior-authority floor, or request reservation granularity"
        )


def verify_recovery_partition(
    *,
    store: CycleAcquisitionStore,
    records: Sequence[Mapping[str, Any]],
    ranked_path: Path,
    seal_run_card_path: Path,
    expected_seal_run_card_sha256: str,
    partition_manifest_path: Path,
    expected_partition_manifest_sha256: str,
    partition: Literal["terminal", "unresolved"],
) -> VerifiedRecoveryPartition:
    """Recompute and authenticate one exact terminal/unresolved partition."""

    seal_bytes = read_pinned_regular_file(
        seal_run_card_path,
        expected_sha256=expected_seal_run_card_sha256,
        label="recovery seal run card",
    )
    manifest_bytes = read_pinned_regular_file(
        partition_manifest_path,
        expected_sha256=expected_partition_manifest_sha256,
        label=f"{partition} recovery manifest",
    )
    try:
        loaded_card = json.loads(seal_bytes)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RankedFirecrawlRecoveryError(
            "recovery seal run card is not valid UTF-8 JSON"
        ) from error
    if not isinstance(loaded_card, Mapping):
        raise RankedFirecrawlRecoveryError("recovery seal run card must be an object")
    card = cast(Mapping[str, object], loaded_card)
    if (
        card.get("schema_version") != RANKED_FIRECRAWL_SEAL_SCHEMA
        or card.get("stage") != "seal-ranked-firecrawl-run"
        or card.get("status") != "completed"
        or card.get("execute") is not True
        or card.get("dry_run") is not False
        or card.get("provider_activity_requested") is not False
        or card.get("provider_activity_executed") is not False
        or card.get("paid_activity_requested") is not False
        or card.get("paid_activity_executed") is not False
    ):
        raise RankedFirecrawlRecoveryError(
            "recovery seal run card is not a completed zero-provider execution"
        )
    if card.get("source_cycle_store") != str(store.path.resolve()):
        raise RankedFirecrawlRecoveryError(
            "recovery seal run card names a different source store"
        )
    ranked_sha256 = hashlib.sha256(ranked_path.read_bytes()).hexdigest()
    if (
        card.get("ranked_path") != str(ranked_path.resolve())
        or card.get("ranked_sha256") != ranked_sha256
        or card.get("source_candidate_count") != len(records)
    ):
        raise RankedFirecrawlRecoveryError(
            "recovery seal ranking authority differs from supplied records"
        )
    anchor_raw = card.get("decision_filed_on_or_after")
    if not isinstance(anchor_raw, str):
        raise RankedFirecrawlRecoveryError("recovery seal lacks a decision anchor")
    try:
        anchor = date.fromisoformat(anchor_raw)
    except ValueError as error:
        raise RankedFirecrawlRecoveryError(
            "recovery seal has an invalid decision anchor"
        ) from error
    source_run_id = card.get("source_run_id")
    cycle_hash = card.get("source_cycle_hash")
    config_sha256 = card.get("source_run_config_sha256")
    credit_cap = card.get("source_credit_cap")
    max_pages = card.get("max_pages_per_docket")
    if (
        not isinstance(source_run_id, str)
        or not isinstance(cycle_hash, str)
        or not isinstance(config_sha256, str)
        or type(credit_cap) is not int
        or type(max_pages) is not int
    ):
        raise RankedFirecrawlRecoveryError(
            "recovery seal lacks valid source ledger authority"
        )
    sealed = seal_ranked_firecrawl_run(
        store=store,
        run_id=source_run_id,
        records=records,
        expected_cycle_hash=cycle_hash,
        expected_run_config_sha256=config_sha256,
        expected_credit_cap=credit_cap,
        max_pages_per_docket=max_pages,
        decision_anchor=anchor,
    )
    if (
        card.get("target_commitment_sha256") != sealed.target_commitment_sha256
        or card.get("attempt_commitment_sha256") != sealed.attempt_commitment_sha256
    ):
        raise RankedFirecrawlRecoveryError(
            "recovery seal no longer matches the immutable source ledger"
        )
    total_prior_authorized_credits = card.get(
        "total_prior_authorized_firecrawl_credits"
    )
    fresh_cap = card.get("authorized_fresh_recovery_credit_cap")
    reserved_per_attempt = sealed.credit_summary.get("reserved_credits_per_attempt")
    if (
        type(total_prior_authorized_credits) is not int
        or type(fresh_cap) is not int
        or type(reserved_per_attempt) is not int
        or card.get("combined_firecrawl_credit_ceiling")
        != RANKED_FIRECRAWL_COMBINED_CREDIT_CEILING
    ):
        raise RankedFirecrawlRecoveryError(
            "recovery seal lacks valid combined Firecrawl credit authority"
        )
    validate_fresh_recovery_credit_authority(
        source_credit_cap=sealed.source_credit_cap,
        total_prior_authorized_credits=total_prior_authorized_credits,
        fresh_recovery_credit_cap=fresh_cap,
        reserved_credits_per_attempt=reserved_per_attempt,
    )
    raw_dir_value = card.get("raw_html_dir")
    if not isinstance(raw_dir_value, str):
        raise RankedFirecrawlRecoveryError("recovery seal lacks raw HTML authority")
    artifacts = build_sealed_ranked_firecrawl_artifacts(
        sealed=sealed,
        records=records,
        raw_html_dir=Path(raw_dir_value),
        lineage_flags=_lineage_flags_from_card(card),
    )
    expected_manifest = (
        artifacts.unresolved_manifest
        if partition == "unresolved"
        else artifacts.terminal_manifest
    )
    expected_manifest_bytes = _jsonl_bytes(expected_manifest)
    if manifest_bytes != expected_manifest_bytes:
        raise RankedFirecrawlRecoveryError(
            f"{partition} recovery manifest differs from source-ledger projection"
        )
    outputs = card.get("outputs")
    if not isinstance(outputs, Mapping):
        raise RankedFirecrawlRecoveryError("recovery seal lacks output commitments")
    output_name = f"{partition}_manifest"
    partition_output = cast(Mapping[str, object], outputs).get(output_name)
    if not isinstance(partition_output, Mapping):
        raise RankedFirecrawlRecoveryError(
            f"recovery seal lacks {partition} output commitment"
        )
    partition_commitment = cast(Mapping[str, object], partition_output)
    if (
        partition_commitment.get("path") != str(partition_manifest_path.resolve())
        or partition_commitment.get("sha256") != expected_partition_manifest_sha256
        or partition_commitment.get("record_count") != len(expected_manifest)
        or card.get("unresolved_count") != len(artifacts.unresolved_manifest)
        or card.get("terminal_count") != len(artifacts.terminal_manifest)
    ):
        raise RankedFirecrawlRecoveryError(
            f"recovery seal {partition} output commitment is inconsistent"
        )
    docket_ids = tuple(cast(str, record["docket_id"]) for record in expected_manifest)
    if not docket_ids or len(docket_ids) != len(set(docket_ids)):
        raise RankedFirecrawlRecoveryError(
            f"{partition} recovery manifest is empty or repeats a docket"
        )
    authority: dict[str, object] = {
        "schema_version": RANKED_FIRECRAWL_PARTITION_SCHEMA,
        "partition": partition,
        "seal_run_card_path": str(seal_run_card_path.resolve()),
        "seal_run_card_sha256": expected_seal_run_card_sha256,
        "manifest_path": str(partition_manifest_path.resolve()),
        "manifest_sha256": expected_partition_manifest_sha256,
        "source_cycle_hash": sealed.source_cycle_hash,
        "source_run_id": sealed.run_id,
        "source_run_config_sha256": sealed.source_run_config_sha256,
        "source_credit_cap": sealed.source_credit_cap,
        "total_prior_authorized_firecrawl_credits": (total_prior_authorized_credits),
        "authorized_fresh_recovery_credit_cap": card.get(
            "authorized_fresh_recovery_credit_cap"
        ),
        "combined_firecrawl_credit_ceiling": card.get(
            "combined_firecrawl_credit_ceiling"
        ),
        "target_commitment_sha256": sealed.target_commitment_sha256,
        "attempt_commitment_sha256": sealed.attempt_commitment_sha256,
        "partition_candidate_set_sha256": canonical_recovery_commitment(
            [record["candidate_id"] for record in expected_manifest]
        ),
        "selected_docket_ids": list(docket_ids),
        "terminal_dockets_reauthorized": 0,
        "firecrawl_reacquisition_allowed": (
            partition == "unresolved" and fresh_cap > 0
        ),
    }
    return VerifiedRecoveryPartition(
        docket_ids=docket_ids,
        authority=authority,
    )


def seal_ranked_firecrawl_run(
    *,
    store: CycleAcquisitionStore,
    run_id: str,
    records: Sequence[Mapping[str, Any]],
    expected_cycle_hash: str,
    expected_run_config_sha256: str,
    expected_credit_cap: int,
    max_pages_per_docket: int,
    decision_anchor: date,
) -> SealedRankedFirecrawlRun:
    """Reconstruct terminal dockets and the exact unresolved complement."""

    if not store.read_only:
        raise RankedFirecrawlRecoveryError(
            "source cycle store must be opened in exclusive read-only mode"
        )
    if _SHA256.fullmatch(expected_cycle_hash) is None:
        raise RankedFirecrawlRecoveryError("expected cycle hash is invalid")
    if _SHA256.fullmatch(expected_run_config_sha256) is None:
        raise RankedFirecrawlRecoveryError("expected run config SHA-256 is invalid")
    if max_pages_per_docket <= 0:
        raise RankedFirecrawlRecoveryError("max_pages_per_docket must be positive")
    if store.cycle_hash != expected_cycle_hash:
        raise RankedFirecrawlRecoveryError("source cycle hash does not match authority")

    try:
        summary = dict(store.firecrawl_run_summary(run_id))
        config = dict(store.firecrawl_run_config(run_id))
        stored_targets = store.firecrawl_targets(run_id)
        attempts = store.firecrawl_attempts(run_id)
    except KeyError as error:
        raise RankedFirecrawlRecoveryError(
            f"source Firecrawl run is missing: {run_id}"
        ) from error
    if summary.get("config_digest") != expected_run_config_sha256:
        raise RankedFirecrawlRecoveryError(
            "source run config digest does not match authority"
        )
    if summary.get("credit_cap") != expected_credit_cap:
        raise RankedFirecrawlRecoveryError("source credit cap does not match authority")
    reserved_per_attempt = summary.get("reserved_credits_per_attempt")
    remaining_authorization = summary.get("remaining_authorization")
    if (
        type(reserved_per_attempt) is not int
        or type(remaining_authorization) is not int
        or remaining_authorization >= reserved_per_attempt
    ):
        raise RankedFirecrawlRecoveryError(
            "source Firecrawl budget is not exhausted; refusing fresh authority"
        )
    if any(attempt.status == "authorized" for attempt in attempts):
        raise RankedFirecrawlRecoveryError(
            "source run has an outstanding authorized attempt"
        )
    if (
        config.get("purpose") != "ranked-complete-docket-acquisition"
        or config.get("decision_anchor") != decision_anchor.isoformat()
        or config.get("max_pages_per_docket") != max_pages_per_docket
        or config.get("firecrawl_max_credits_per_scrape") != reserved_per_attempt
    ):
        raise RankedFirecrawlRecoveryError(
            "source run config differs from ranked docket recovery authority"
        )
    raw_artifact_root = _verified_raw_artifact_root(config)

    ranked = ranked_docket_targets(records, limit=len(records))
    if len(ranked) != len(records) or not ranked:
        raise RankedFirecrawlRecoveryError(
            "ranked source selection is empty or truncated"
        )
    source_batch_id = cast(str, summary["batch_id"])
    if store.candidate_ids(source_batch_id) != tuple(
        sorted(target.candidate_id for target in ranked)
    ):
        raise RankedFirecrawlRecoveryError(
            "source run batch does not exactly match ranked candidates"
        )

    targets_by_docket = _verify_targets(
        stored_targets,
        ranked=ranked,
        max_pages_per_docket=max_pages_per_docket,
    )
    attempts_by_target = _verify_attempts(
        attempts,
        stored_targets=stored_targets,
        run_config=config,
    )
    _verify_success_artifact_paths(
        attempts,
        raw_artifact_root=raw_artifact_root,
    )
    try:
        successful_pages = load_successful_firecrawl_pages(store=store, run_id=run_id)
    except (FirecrawlArtifactError, OSError, UnicodeError) as error:
        raise RankedFirecrawlRecoveryError(str(error)) from error
    page_by_target = {page.target_id: page for page in successful_pages}

    bundles: list[CourtListenerDocketBundle] = []
    failures: list[DocketAcquisitionFailure] = []
    unresolved: list[UnresolvedRankedDocket] = []
    retrieved_at: dict[str, str] = {}
    for target in ranked:
        outcome = _partition_docket(
            target=target,
            stored_pages=targets_by_docket.get(target.docket_id, {}),
            attempts_by_target=attempts_by_target,
            page_by_target=page_by_target,
            max_pages_per_docket=max_pages_per_docket,
            decision_anchor=decision_anchor,
        )
        if isinstance(outcome, CourtListenerDocketBundle):
            bundles.append(outcome)
            completion_times = [
                attempts_by_target[stored.target_id][-1].completed_at
                for page_number, stored in targets_by_docket[target.docket_id].items()
                if page_number <= len(outcome.pages)
            ]
            if any(value is None for value in completion_times):
                raise RankedFirecrawlRecoveryError(
                    f"successful docket lacks completion time: {target.docket_id}"
                )
            retrieved_at[target.docket_id] = max(cast(list[str], completion_times))
        elif isinstance(outcome, DocketAcquisitionFailure):
            failures.append(outcome)
        else:
            unresolved.append(outcome)

    terminal_ids = {bundle.docket_id for bundle in bundles} | {
        failure.docket_id for failure in failures
    }
    unresolved_ids = {item.docket_id for item in unresolved}
    ranked_ids = {target.docket_id for target in ranked}
    if terminal_ids & unresolved_ids or terminal_ids | unresolved_ids != ranked_ids:
        raise RankedFirecrawlRecoveryError(
            "sealed terminal and unresolved partitions do not exactly reconcile"
        )
    rank_by_docket = {target.docket_id: target.rank for target in ranked}
    completed_times = [
        attempt.completed_at for attempt in attempts if attempt.completed_at is not None
    ]
    if not completed_times:
        raise RankedFirecrawlRecoveryError(
            "budget-exhausted source run has no completed attempts"
        )
    return SealedRankedFirecrawlRun(
        run_id=run_id,
        source_cycle_hash=store.cycle_hash,
        source_batch_id=source_batch_id,
        source_run_config_sha256=expected_run_config_sha256,
        source_credit_cap=expected_credit_cap,
        source_candidate_count=len(ranked),
        bundles=tuple(bundles),
        failures=tuple(failures),
        unresolved=tuple(unresolved),
        target_commitment_sha256=_canonical_sha256(
            [_target_record(item) for item in stored_targets]
        ),
        attempt_commitment_sha256=_canonical_sha256(
            [_attempt_record(item) for item in attempts]
        ),
        credit_summary=summary,
        source_ledger_as_of=max(completed_times),
        retrieved_at_by_docket=retrieved_at,
        rank_by_docket=rank_by_docket,
    )


def _verify_targets(
    stored_targets: Sequence[FirecrawlTarget],
    *,
    ranked: Sequence[RankedDocketTarget],
    max_pages_per_docket: int,
) -> dict[str, dict[int, FirecrawlTarget]]:
    ranked_by_docket = {target.docket_id: target for target in ranked}
    by_docket: dict[str, dict[int, FirecrawlTarget]] = defaultdict(dict)
    selected_count = len(ranked)
    for stored in stored_targets:
        parsed = urlsplit(stored.source_url)
        path_match = _DOCKET_PATH.fullmatch(parsed.path)
        query = parse_qs(parsed.query, strict_parsing=True)
        if (
            stored.target_kind != "docket"
            or parsed.scheme != "https"
            or parsed.netloc != "www.courtlistener.com"
            or path_match is None
            or set(query) != {"order_by", "page"}
            or query.get("order_by") != ["desc"]
            or len(query.get("page", ())) != 1
            or not query["page"][0].isdigit()
        ):
            raise RankedFirecrawlRecoveryError("source run has a noncanonical target")
        docket_id = path_match.group("docket_id")
        page_number = int(query["page"][0])
        target = ranked_by_docket.get(docket_id)
        if target is None or not 1 <= page_number <= max_pages_per_docket:
            raise RankedFirecrawlRecoveryError("source run has an unauthorized target")
        expected_url = canonical_courtlistener_docket_page_url(
            target.docket_url, page_number=page_number
        )
        expected_id = _docket_page_target_id(docket_id, page_number)
        expected_ordinal = (page_number - 1) * selected_count + target.rank
        if (
            stored.source_url != expected_url
            or stored.target_id != expected_id
            or stored.ordinal != expected_ordinal
            or page_number in by_docket[docket_id]
        ):
            raise RankedFirecrawlRecoveryError(
                f"source target identity/ordinal mismatch: {stored.target_id}"
            )
        by_docket[docket_id][page_number] = stored
    for docket_id, pages in by_docket.items():
        if sorted(pages) != list(range(1, max(pages) + 1)):
            raise RankedFirecrawlRecoveryError(
                f"source targets are noncontiguous for docket {docket_id}"
            )
    return dict(by_docket)


def _verify_attempts(
    attempts: Sequence[FirecrawlAttempt],
    *,
    stored_targets: Sequence[FirecrawlTarget],
    run_config: Mapping[str, object],
) -> dict[str, tuple[FirecrawlAttempt, ...]]:
    allowed_target_statuses = {
        "pending",
        "in_progress",
        "succeeded",
        "retry_exhausted",
        "terminal_error",
    }
    allowed_attempt_statuses = {
        "succeeded",
        "provider_error",
        "target_error",
        "transport_error",
        "interrupted",
    }
    reserved_per_attempt = run_config.get("firecrawl_max_credits_per_scrape")
    if type(reserved_per_attempt) is not int or reserved_per_attempt <= 0:
        raise RankedFirecrawlRecoveryError(
            "source run lacks frozen per-attempt credit authority"
        )
    target_by_id = {target.target_id: target for target in stored_targets}
    grouped: dict[str, list[FirecrawlAttempt]] = defaultdict(list)
    for attempt in attempts:
        target = target_by_id.get(attempt.target_id)
        if (
            target is None
            or attempt.request_url != target.source_url
            or attempt.status not in allowed_attempt_statuses
            or attempt.completed_at is None
        ):
            raise RankedFirecrawlRecoveryError(
                "source attempt ledger has an unknown or outstanding request"
            )
        if attempt.reserved_credits != reserved_per_attempt:
            raise RankedFirecrawlRecoveryError(
                "source attempt reservation differs from frozen authority"
            )
        reported_credits = attempt.reported_credits
        if reported_credits is not None and not (
            type(reported_credits) is int
            and 0 <= reported_credits <= reserved_per_attempt
        ):
            raise RankedFirecrawlRecoveryError(
                "source attempt reported credits are invalid"
            )
        # Failed requests may legitimately lack provider-reported usage; their
        # full frozen reservation still counts against exhaustion. A committed
        # artifact must carry exact provider usage data.
        if attempt.status == "succeeded" and reported_credits is None:
            raise RankedFirecrawlRecoveryError(
                "source attempt reported credits are invalid"
            )
        grouped[attempt.target_id].append(attempt)
    max_attempts = run_config.get("max_attempts_per_page")
    if type(max_attempts) is not int or max_attempts <= 0:
        raise RankedFirecrawlRecoveryError("source run lacks max-attempt authority")
    for target in stored_targets:
        if target.status not in allowed_target_statuses:
            raise RankedFirecrawlRecoveryError(
                f"source target has unknown status: {target.target_id}"
            )
        target_attempts = grouped.get(target.target_id, [])
        if len(target_attempts) > max_attempts:
            raise RankedFirecrawlRecoveryError(
                "source target exceeds frozen max-attempt authority"
            )
        if [item.attempt_number for item in target_attempts] != list(
            range(1, len(target_attempts) + 1)
        ):
            raise RankedFirecrawlRecoveryError(
                "source attempt numbers are not contiguous"
            )
        if any(
            item.page_number != _target_page_number(target.source_url)
            for item in target_attempts
        ):
            raise RankedFirecrawlRecoveryError("source attempt page number mismatch")
        successes = [item for item in target_attempts if item.status == "succeeded"]
        if len(successes) > 1 or (successes and target_attempts[-1] != successes[0]):
            raise RankedFirecrawlRecoveryError(
                "source target has impossible success lineage"
            )
        if target.status == "succeeded" and len(successes) != 1:
            raise RankedFirecrawlRecoveryError(
                "successful target lacks one artifact attempt"
            )
        if target.status != "succeeded" and successes:
            raise RankedFirecrawlRecoveryError(
                "nonsuccess target carries a success attempt"
            )
        if target.status == "pending" and target_attempts:
            raise RankedFirecrawlRecoveryError("pending target already has attempts")
        if target.status == "retry_exhausted" and len(target_attempts) != max_attempts:
            raise RankedFirecrawlRecoveryError(
                "retry-exhausted target lacks all attempts"
            )
    return {key: tuple(value) for key, value in grouped.items()}


def _verified_raw_artifact_root(run_config: Mapping[str, object]) -> Path:
    value = run_config.get("raw_artifact_root")
    if not isinstance(value, str):
        raise RankedFirecrawlRecoveryError("source run lacks a valid raw artifact root")
    configured = Path(value)
    try:
        resolved = configured.resolve(strict=True)
    except OSError as error:
        raise RankedFirecrawlRecoveryError(
            "source raw artifact root cannot be resolved"
        ) from error
    if not configured.is_absolute() or configured != resolved or not resolved.is_dir():
        raise RankedFirecrawlRecoveryError(
            "source raw artifact root must be a canonical existing directory"
        )
    return resolved


def _verify_success_artifact_paths(
    attempts: Sequence[FirecrawlAttempt],
    *,
    raw_artifact_root: Path,
) -> None:
    for attempt in attempts:
        if attempt.status != "succeeded":
            continue
        path = attempt.artifact_path
        if path is None or not path.is_absolute():
            raise RankedFirecrawlRecoveryError(
                f"successful attempt has invalid artifact path: {attempt.attempt_id}"
            )
        try:
            resolved = path.resolve(strict=True)
            metadata = path.lstat()
        except OSError as error:
            raise RankedFirecrawlRecoveryError(
                f"successful artifact cannot be resolved: {attempt.attempt_id}"
            ) from error
        if (
            path != resolved
            or resolved == raw_artifact_root
            or not resolved.is_relative_to(raw_artifact_root)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise RankedFirecrawlRecoveryError(
                "successful artifact is not a canonical singly linked file under "
                f"the frozen raw artifact root: {attempt.attempt_id}"
            )


def _partition_docket(
    *,
    target: RankedDocketTarget,
    stored_pages: Mapping[int, FirecrawlTarget],
    attempts_by_target: Mapping[str, tuple[FirecrawlAttempt, ...]],
    page_by_target: Mapping[str, FirecrawlPageRecord],
    max_pages_per_docket: int,
    decision_anchor: date,
) -> CourtListenerDocketBundle | DocketAcquisitionFailure | UnresolvedRankedDocket:
    cached: dict[str, str] = {}
    observed: list[CourtListenerWebDocketPage] = []
    for page_number in range(1, max_pages_per_docket + 1):
        stored = stored_pages.get(page_number)
        if stored is None:
            _reject_later_pages(stored_pages, page_number, target.docket_id)
            return _unresolved(target, page_number, None, (), "missing_page_target")
        target_attempts = attempts_by_target.get(stored.target_id, ())
        if stored.status == "succeeded":
            page = page_by_target.get(stored.target_id)
            if page is None:
                raise RankedFirecrawlRecoveryError(
                    f"successful target lacks verified page: {stored.target_id}"
                )
            cached[stored.source_url] = page.raw_html
            try:
                parsed = parse_courtlistener_docket_html(
                    page.raw_html,
                    source_url=stored.source_url,
                    docket_id=target.docket_id,
                )
            except CourtListenerWebParseError as error:
                _reject_later_pages(stored_pages, page_number + 1, target.docket_id)
                return _failure(
                    target,
                    reason="docket_reconstruction_failed",
                    stage="complete_docket_reconstruction",
                    detail=f"invalid_docket_page_artifact:{error}",
                )
            observed.append(parsed)
            complete = not parsed.has_next_page or may_stop_at_anchor_boundary(
                observed, anchor=decision_anchor
            )
            if complete:
                _reject_later_pages(stored_pages, page_number + 1, target.docket_id)
                try:
                    bundle = paginate_courtlistener_docket(
                        target.docket_url,
                        fetch=lambda url: cached[url],
                        max_pages=max_pages_per_docket,
                        decision_anchor=decision_anchor,
                    )
                except (
                    KeyError,
                    CourtListenerDocketPaginationError,
                    CourtListenerWebParseError,
                ) as error:
                    return _failure(
                        target,
                        reason="docket_reconstruction_failed",
                        stage="complete_docket_reconstruction",
                        detail=str(error),
                    )
                if not bundle.complete_for_anchor_window:
                    return _failure(
                        target,
                        reason="docket_reconstruction_failed",
                        stage="complete_docket_reconstruction",
                        detail="incomplete_anchor_window",
                    )
                return bundle
            if page_number == max_pages_per_docket:
                return _failure(
                    target,
                    reason="fetch_failed",
                    stage="docket_page_acquisition",
                    detail="pagination_page_limit_reached",
                )
            continue

        _reject_later_pages(stored_pages, page_number + 1, target.docket_id)
        if _candidate_local_terminal(stored, target_attempts):
            return _failure(
                target,
                reason="fetch_failed",
                stage="docket_page_acquisition",
                detail=f"page_{page_number}_not_acquired:{stored.status}",
            )
        reason = (
            "retryable_page_incomplete"
            if target_attempts
            and all(item.status == "target_error" for item in target_attempts)
            else "provider_or_interrupted_page_incomplete"
        )
        return _unresolved(
            target,
            page_number,
            stored.status,
            target_attempts,
            reason,
        )
    raise RankedFirecrawlRecoveryError(
        f"unreachable partition state: {target.docket_id}"
    )


def _candidate_local_terminal(
    target: FirecrawlTarget,
    attempts: Sequence[FirecrawlAttempt],
) -> bool:
    if target.status == "terminal_error":
        return bool(attempts and _complete_terminal_target_error(attempts[-1]))
    if target.status == "retry_exhausted":
        return bool(
            attempts
            and all(_complete_retryable_target_error(item) for item in attempts)
        )
    return False


def _complete_terminal_target_error(attempt: FirecrawlAttempt) -> bool:
    """Admit only fully evidenced candidate-local HTTP failures as exclusions."""

    return (
        attempt.status == "target_error"
        and attempt.failure_transient is False
        and attempt.provider_http_status == 200
        and attempt.target_http_status in {404, 410}
        and isinstance(attempt.reported_credits, int)
        and 0 <= attempt.reported_credits <= attempt.reserved_credits
        and attempt.proxy_used in {"basic", "stealth"}
        and isinstance(attempt.failure_code, str)
        and bool(attempt.failure_code)
        and isinstance(attempt.failure_message, str)
        and bool(attempt.failure_message.strip())
        and isinstance(attempt.failure_response_sha256, str)
        and _SHA256.fullmatch(attempt.failure_response_sha256) is not None
        and attempt.artifact_path is None
        and attempt.artifact_sha256 is None
        and attempt.artifact_byte_count is None
        and not is_retryable_target_accepted(attempt)
    )


def _complete_retryable_target_error(attempt: FirecrawlAttempt) -> bool:
    """Require complete HTTP evidence before retry exhaustion is terminal."""

    return (
        is_retryable_target_accepted(attempt)
        and isinstance(attempt.reported_credits, int)
        and 0 <= attempt.reported_credits <= attempt.reserved_credits
        and isinstance(attempt.failure_message, str)
        and bool(attempt.failure_message.strip())
    )


def _unresolved(
    target: RankedDocketTarget,
    page_number: int,
    status: str | None,
    attempts: Sequence[FirecrawlAttempt],
    reason: str,
) -> UnresolvedRankedDocket:
    return UnresolvedRankedDocket(
        candidate_id=target.candidate_id,
        docket_id=target.docket_id,
        rank=target.rank,
        reason=reason,
        required_page_number=page_number,
        target_status=status,
        last_failure_code=attempts[-1].failure_code if attempts else None,
    )


def _failure(
    target: RankedDocketTarget,
    *,
    reason: str,
    stage: str,
    detail: str,
) -> DocketAcquisitionFailure:
    return DocketAcquisitionFailure(
        candidate_id=target.candidate_id,
        docket_id=target.docket_id,
        reason=reason,
        failure_stage=stage,
        failure_reason=detail,
    )


def _reject_later_pages(
    pages: Mapping[int, FirecrawlTarget],
    first_disallowed: int,
    docket_id: str,
) -> None:
    if any(page_number >= first_disallowed for page_number in pages):
        raise RankedFirecrawlRecoveryError(
            "source run has pages after terminal/incomplete page for docket "
            f"{docket_id}"
        )


def _target_page_number(source_url: str) -> int:
    query = parse_qs(urlsplit(source_url).query, strict_parsing=True)
    return int(query["page"][0])


def _docket_page_target_id(docket_id: str, page_number: int) -> str:
    return (
        "docket-"
        + hashlib.sha256(f"{docket_id}:{page_number}".encode()).hexdigest()[:24]
    )


def _target_record(target: FirecrawlTarget) -> dict[str, object]:
    return asdict(target)


def _attempt_record(attempt: FirecrawlAttempt) -> dict[str, object]:
    record = asdict(attempt)
    if attempt.artifact_path is not None:
        record["artifact_path"] = str(attempt.artifact_path)
    return record


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _jsonl_bytes(records: Sequence[Mapping[str, object]]) -> bytes:
    return "".join(
        f"{json.dumps(dict(record), sort_keys=True, allow_nan=False)}\n"
        for record in records
    ).encode()


def read_pinned_regular_file(
    path: Path,
    *,
    expected_sha256: str,
    label: str,
) -> bytes:
    if _SHA256.fullmatch(expected_sha256) is None:
        raise RankedFirecrawlRecoveryError(f"{label} SHA-256 is invalid")
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise RankedFirecrawlRecoveryError(
            f"{label} must be a singly linked regular file"
        )
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise RankedFirecrawlRecoveryError(f"{label} SHA-256 does not match")
    return payload


def _lineage_flags_from_card(card: Mapping[str, object]) -> dict[str, object]:
    if card.get("provisional_frontier") is not True:
        return {}
    fields = (
        "provisional_frontier",
        "final_cohort_eligible",
        "full_source_terminal",
        "source_candidate_count",
        "source_candidate_set_sha256",
        "source_projection_sha256",
        "progress_config_sha256",
        "progress_sha256",
        "success_count",
        "terminal_exclusion_count",
        "pending_count",
        "success_candidate_set_sha256",
        "terminal_excluded_candidate_set_sha256",
        "pending_candidate_set_sha256",
    )
    if any(field not in card for field in fields):
        raise RankedFirecrawlRecoveryError(
            "recovery seal has incomplete provisional lineage"
        )
    return {field: card[field] for field in fields}
