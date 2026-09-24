from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import legalforecast.jev.prepare as prepare
import pytest
from legalforecast.contracts import (
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_RAW_SHA256_V1,
    PUBLIC_RUN_IDENTITY_V1,
)
from legalforecast.evals.model_registry import (
    ModelRegistryEntry,
    model_registry_entry_sha256,
)
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.jev.packets import (
    JEV_REQUEST_BYTE_BUDGET,
    CaseDocument,
    case_documents,
)
from legalforecast.jev.summaries import DocumentSummary, SummaryCache
from legalforecast.jev.summary_recovery import (
    SummaryRecoveryError,
    _response,  # pyright: ignore[reportPrivateUsage]
    recover_saved_overrun,
)
from legalforecast.release import ForecastExecution, load_forecast_execution
from legalforecast.runner import issue_runner_fixture
from tests.test_jev_grok_prepare import _entry  # pyright: ignore[reportPrivateUsage]


def _seed(
    tmp_path: Path,
) -> tuple[ForecastExecution, ModelRegistryEntry, Path, Path, int, str]:
    fixture = tmp_path / "fixture"
    issue_runner_fixture(fixture)
    execution = load_forecast_execution(
        fixture / "release/forecast-release.json", artifact_root=fixture / "release"
    )
    entry = _entry()
    cache_path = tmp_path / "summaries.json"
    ledger_path = tmp_path / "ledger.sqlite3"
    cache = SummaryCache(cache_path, execution.release.release_digest)
    identity = str(
        ARTIFACT_RAW_SHA256_V1.commit(
            {
                "release": execution.release.release_digest,
                "model": model_registry_entry_sha256(entry),
                "prompt": prepare.SUMMARY_PROMPT_VERSION,
                "request_byte_budget": JEV_REQUEST_BYTE_BUDGET,
            },
            domain=PUBLIC_RUN_IDENTITY_V1,
        ).digest
    )
    documents: list[tuple[str, CaseDocument]] = []
    for case in execution.release.cases:
        units = tuple(
            unit
            for unit in execution.release.prediction_units
            if unit.case_id == case.case_id
        )
        documents.extend(
            (case.case_id, document) for document in case_documents(execution, units)
        )
    target_index = len(documents) - 1
    with SqliteProviderSpendAuthority(
        ledger_path,
        authority_identity_sha256=identity,
        cycle_id=execution.release.release_id,
        provider=entry.provider,
        account="jev-summaries",
        cap_microusd=20_000_000,
        policy=FrozenAttemptPolicy(
            reservation_ledger_sha256=identity,
            max_billable_attempts=1,
            failure_threshold=1,
            failure_window_seconds=86_400,
        ),
    ) as authority:
        for index, (case_id, document) in enumerate(documents):
            target = index == target_index
            summary = DocumentSummary(
                document_id=document.document_id,
                source_sha256=document.source_sha256,
                text=f"saved summary {index}",
                model=entry.model_id,
                prompt_version=prepare.SUMMARY_PROMPT_VERSION,
                input_tokens=6_939 if target else 10,
                output_tokens=15_167 if target else 10,
                estimated_cost_usd=0.10488 if target else 0.00008,
            )
            cache.put(case_id, summary)
            key = ProviderSpendKey(
                execution.release.release_id,
                entry.provider,
                "jev-summaries",
                "document_summary",
                entry.registry_key,
                ARTIFACT_CANONICAL_JSON_V1.encode(
                    {"case_id": case_id, "document_id": document.document_id}
                ).decode(),
                "none",
                1,
            )
            lease = authority.authorize_attempt(
                key, reservation_microusd=99_388 if target else 100_000
            )
            if not target:
                authority.record_response(
                    lease,
                    input_tokens=summary.input_tokens,
                    output_tokens=summary.output_tokens,
                    actual_microusd=80,
                    response_sha256=_response(summary),
                )
    # Model the historic ledger state directly: current settlement correctly
    # accepts this within-cap response, but saved poisoned ledgers still need
    # the old recovery path.
    with sqlite3.connect(ledger_path) as connection:
        connection.execute(
            "UPDATE provider_spend_metadata SET authority_poisoned=1, "
            "poison_reason='observed provider cost exceeds frozen reservation'"
        )
    return execution, entry, cache_path, ledger_path, len(documents), identity


def test_saved_overrun_recovery_is_idempotent_and_prepare_reuses_every_cache_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    execution, entry, cache, ledger, count, _identity = _seed(tmp_path)
    recovered = recover_saved_overrun(
        execution,
        entry=entry,
        cache_path=cache,
        ledger_path=ledger,
        ceiling_microusd=20_000_000,
    )
    assert recovered.actual_microusd == 104_880
    assert recovered.prior_settled_microusd == 1_280
    assert recovered.settled_microusd == 106_160
    assert recovered.already_recovered is False

    with sqlite3.connect(ledger) as connection:
        before = connection.execute(
            "SELECT COUNT(*) FROM provider_attempts"
        ).fetchone()[0]
        poison_reason = connection.execute(
            "SELECT poison_reason FROM provider_spend_metadata"
        ).fetchone()[0]
        reservation = connection.execute(
            "SELECT reservation_microusd FROM provider_attempts "
            "WHERE output_tokens = 15167"
        ).fetchone()[0]
    assert before == count
    assert poison_reason == "observed provider cost exceeds frozen reservation"
    assert reservation == 104_880

    again = recover_saved_overrun(
        execution,
        entry=entry,
        cache_path=cache,
        ledger_path=ledger,
        ceiling_microusd=20_000_000,
    )
    assert again.already_recovered is True

    class _NoCall:
        def __call__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            raise AssertionError("recovery must not repurchase cached summaries")

    monkeypatch.setattr(prepare, "Agent", _NoCall())
    resumed = prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=cache,
        ledger_path=ledger,
        ceiling_microusd=20_000_000,
    )
    assert resumed == {"created": 0, "reused": count, "spent_microusd": 106_160}


def test_recovery_rejects_source_mismatch(tmp_path: Path) -> None:
    execution, entry, cache, ledger, _count, _identity = _seed(tmp_path)
    payload = json.loads(cache.read_text())
    first_case = next(iter(payload["records"].values()))
    first_summary = next(iter(first_case.values()))
    first_summary["source_sha256"] = "0" * 64
    cache.write_text(json.dumps(payload))
    with pytest.raises(SummaryRecoveryError, match="source"):
        recover_saved_overrun(
            execution,
            entry=entry,
            cache_path=cache,
            ledger_path=ledger,
            ceiling_microusd=20_000_000,
        )


def test_prepare_reconcile_hook_repairs_before_cache_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    execution, entry, cache, ledger, count, _identity = _seed(tmp_path)

    class _NoCall:
        def __call__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            raise AssertionError("recovery must not repurchase cached summaries")

    monkeypatch.setattr(prepare, "Agent", _NoCall())
    resumed = prepare.prepare_summaries(
        execution,
        entry=entry,
        cache_path=cache,
        ledger_path=ledger,
        ceiling_microusd=20_000_000,
        reconcile_saved_overrun=True,
    )
    assert resumed == {"created": 0, "reused": count, "spent_microusd": 106_160}
    with sqlite3.connect(ledger) as connection:
        assert (
            connection.execute(
                "SELECT authority_poisoned FROM provider_spend_metadata"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT status FROM provider_attempts WHERE output_tokens = 15167"
            ).fetchone()[0]
            == "settled"
        )


def test_recovery_rejects_ambiguous_reservations(tmp_path: Path) -> None:
    execution, entry, cache, ledger, _count, _identity = _seed(tmp_path)
    with sqlite3.connect(ledger) as connection:
        attempt_id = connection.execute(
            "SELECT attempt_id FROM provider_attempts WHERE status = 'settled' LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            "UPDATE provider_attempts SET status = 'reserved' WHERE attempt_id = ?",
            (attempt_id,),
        )
        connection.commit()
    with pytest.raises(SummaryRecoveryError, match="reserved"):
        recover_saved_overrun(
            execution,
            entry=entry,
            cache_path=cache,
            ledger_path=ledger,
            ceiling_microusd=20_000_000,
        )


def test_recovery_rejects_cache_cost_mismatch(tmp_path: Path) -> None:
    execution, entry, cache, ledger, _count, _identity = _seed(tmp_path)
    payload = json.loads(cache.read_text())
    for documents in payload["records"].values():
        for summary in documents.values():
            if summary["output_tokens"] == 15167:
                summary["estimated_cost_usd"] = 0.2
    cache.write_text(json.dumps(payload))
    with pytest.raises(SummaryRecoveryError, match="estimated cost"):
        recover_saved_overrun(
            execution,
            entry=entry,
            cache_path=cache,
            ledger_path=ledger,
            ceiling_microusd=20_000_000,
        )


def test_recovery_rejects_saved_cost_that_would_exceed_cap(tmp_path: Path) -> None:
    execution, entry, cache, ledger, _count, _identity = _seed(tmp_path)
    with sqlite3.connect(ledger) as connection:
        connection.execute("UPDATE provider_spend_metadata SET cap_microusd = 100_000")
        connection.commit()
    with pytest.raises(SummaryRecoveryError, match="cap"):
        recover_saved_overrun(
            execution,
            entry=entry,
            cache_path=cache,
            ledger_path=ledger,
            ceiling_microusd=100_000,
        )
    with sqlite3.connect(ledger) as connection:
        assert (
            connection.execute(
                "SELECT authority_poisoned FROM provider_spend_metadata"
            ).fetchone()[0]
            == 1
        )
