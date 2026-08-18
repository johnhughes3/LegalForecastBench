# pyright: reportPrivateUsage=false
"""The pinned caps digest and the account-alias check must be satisfiable together.

``lineage.py`` requires the replay spec's ``provider_caps_sha256`` to equal the
digest the predecessor Stage A run cards committed, and the predecessor cohort
was executed against a *legacy base* caps artifact.
``provider_cycle_caps_materializer`` requires a base artifact to omit account
aliases, so ``ProviderCycleCaps.account`` cannot answer for it — leaving the
digest pin and the account check jointly unsatisfiable.

The canonical alias is nonetheless authenticated one artifact along: the pinned
provider journal's immutable identity row commits to the same cycle id and the
same caps digest.  These tests pin that fallback narrowly — it may only fill an
alias the caps artifact never carried, and it may never weaken the digest
binding, the exact-match requirement, or the publishable-alias rule.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
from legalforecast.ingestion.stage_a_replay_executor.provider import (
    _canonical_provider_account,
    _validated_provider_accounts,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    StageAReplayExecutorError,
)
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
    ProviderCycleCaps,
    load_provider_cycle_caps_bytes,
)

_CYCLE_ID = "cycle-1-fixture"
_CAPS_SHA256 = "a" * 64


def _caps(*, with_account: bool) -> ProviderCycleCaps:
    """Build caps in the two shapes production actually emits.

    ``with_account=False`` is the legacy base shape the predecessor cohort was
    executed against; ``True`` is the successor shape that carries the alias.
    """

    entry: dict[str, object] = {
        "provider": "anthropic",
        "cycle_reservation_cap_usd": "100.00",
    }
    if with_account:
        entry["account"] = "default"
    payload = json.dumps(
        {
            "schema_version": "legalforecast.provider_cycle_caps.v1",
            "cycle_id": _CYCLE_ID,
            "providers": [entry],
        }
    ).encode("utf-8")
    return load_provider_cycle_caps_bytes(payload, source="fixture-caps.json")


def _spec(journal_path: Path, *, caps_sha256: str = _CAPS_SHA256) -> ReplaySpec:
    return ReplaySpec(
        path=Path("/nonexistent/replay-spec.json"),
        spec_sha256="0" * 64,
        record=MappingProxyType({}),
        candidate_ids=("cand-1",),
        per_candidate_ceiling_usd=MappingProxyType({"cand-1": Decimal("1")}),
        aggregate_ceiling_usd=Decimal("1"),
        invocation_reservations_usd=MappingProxyType(
            {"unitizer": Decimal("1"), "reviewer": Decimal("1")}
        ),
        code_commit="0" * 40,
        config_hashes=MappingProxyType({}),
        model_ids=MappingProxyType({}),
        provider_journal_path=journal_path.resolve(),
        provider_caps_sha256=caps_sha256,
        model_registry_sha256="b" * 64,
        cycle_id=_CYCLE_ID,
        output_paths=MappingProxyType({}),
        input_paths=(),
        synthetic_fixture=False,
    )


def _journal(
    path: Path,
    *,
    accounts: Mapping[str, str],
    cycle_id: str = _CYCLE_ID,
    caps_sha256: str = _CAPS_SHA256,
) -> Path:
    """Author one authenticated journal committing ``accounts`` per provider.

    The identity row is written by ``ProviderAttemptJournal`` itself, so the
    fixture cannot drift from the production schema or identity rules.  Attempt
    rows are inserted directly because these tests care only about which
    aliases the journal commits, not about attempt accounting.
    """

    first_provider, first_account = next(iter(accounts.items()))
    with ProviderAttemptJournal(
        path,
        identity=ProviderCallIdentity(
            stage="llm-unitize",
            candidate_id="cand-1",
            model_key=f"{first_provider}:fixture",
            prompt="fixture prompt",
            model_registry_sha256="b" * 64,
            account=first_account,
        ),
        provider=first_provider,
        reservation_usd=0.1,
        cycle_cap_usd=100.0,
        cycle_id=cycle_id,
        provider_cycle_caps_sha256=caps_sha256,
    ):
        pass
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        for ordinal, (provider, account) in enumerate(accounts.items(), start=1):
            connection.execute(
                "INSERT OR IGNORE INTO provider_ledgers(provider, account, "
                "cycle_cap_usd) VALUES (?, ?, ?)",
                (provider, account, 100.0),
            )
            connection.execute(
                "INSERT INTO provider_attempts(logical_call_key, attempt_ordinal, "
                "stage, candidate_id, model_key, provider, account, prompt_text, "
                "prompt_sha256, model_registry_sha256, reservation_usd, status, "
                "reserved_at) VALUES (?, 1, 'llm-unitize', 'cand-1', ?, ?, ?, "
                "'fixture prompt', ?, ?, 0.1, 'succeeded', '2026-08-17T00:00:00Z')",
                (
                    f"logical-{ordinal}",
                    f"{provider}:fixture",
                    provider,
                    account,
                    "c" * 64,
                    "b" * 64,
                ),
            )
    finally:
        connection.close()
    return path


def test_legacy_accountless_caps_bind_the_alias_the_journal_commits(
    tmp_path: Path,
) -> None:
    """The unsatisfiable pair resolves without relaxing the digest binding."""

    journal = _journal(tmp_path / "journal.sqlite3", accounts={"anthropic": "default"})

    assert (
        _canonical_provider_account(
            _caps(with_account=False), _spec(journal), "anthropic"
        )
        == "default"
    )


def test_a_mixed_case_journal_provider_still_binds(tmp_path: Path) -> None:
    """Case is not a reason to re-create the unsatisfiable pair.

    Caps provider keys and the replay's provider names are both lower-cased,
    but the journal records the model-registry entry's provider verbatim.  A
    registry that spelled the provider ``Anthropic`` would otherwise match zero
    journal rows and refuse a run that should have succeeded.
    """

    journal = _journal(tmp_path / "journal.sqlite3", accounts={"Anthropic": "default"})

    assert (
        _canonical_provider_account(
            _caps(with_account=False), _spec(journal), "anthropic"
        )
        == "default"
    )


def test_caps_that_carry_the_alias_never_consult_the_journal(tmp_path: Path) -> None:
    """The fallback fills a missing alias; it never overrides a committed one."""

    absent_journal = tmp_path / "missing" / "journal.sqlite3"

    assert (
        _canonical_provider_account(
            _caps(with_account=True), _spec(absent_journal), "anthropic"
        )
        == "default"
    )
    assert not absent_journal.exists()


def test_a_provider_absent_from_caps_still_refuses(tmp_path: Path) -> None:
    """The journal answers only for a provider the caps artifact already caps."""

    journal = _journal(tmp_path / "journal.sqlite3", accounts={"google": "default"})

    with pytest.raises(StageAReplayExecutorError, match="has no entry for 'google'"):
        _canonical_provider_account(_caps(with_account=False), _spec(journal), "google")


def test_a_journal_pinned_to_other_caps_refuses(tmp_path: Path) -> None:
    """The alias is authenticated only by the caps digest the journal commits."""

    journal = _journal(
        tmp_path / "journal.sqlite3",
        accounts={"anthropic": "default"},
        caps_sha256="d" * 64,
    )

    with pytest.raises(
        StageAReplayExecutorError, match="caps artifact identity differs"
    ):
        _canonical_provider_account(
            _caps(with_account=False), _spec(journal), "anthropic"
        )


def test_a_journal_with_no_rows_for_the_provider_refuses(tmp_path: Path) -> None:
    """Silence is not a commitment, so an empty journal cannot supply an alias."""

    journal = _journal(tmp_path / "journal.sqlite3", accounts={"google": "default"})

    with pytest.raises(
        StageAReplayExecutorError,
        match="does not commit exactly one account alias for 'anthropic'",
    ):
        _canonical_provider_account(
            _caps(with_account=False), _spec(journal), "anthropic"
        )


def test_two_aliases_for_one_provider_refuse(tmp_path: Path) -> None:
    """An ambiguous journal must never have its alias chosen for it."""

    journal = tmp_path / "journal.sqlite3"
    _journal(journal, accounts={"anthropic": "default"})
    connection = sqlite3.connect(journal, isolation_level=None)
    try:
        connection.execute(
            "INSERT INTO provider_ledgers(provider, account, cycle_cap_usd) "
            "VALUES ('anthropic', 'secondary', 100.0)"
        )
        connection.execute(
            "INSERT INTO provider_attempts(logical_call_key, attempt_ordinal, "
            "stage, candidate_id, model_key, provider, account, prompt_text, "
            "prompt_sha256, model_registry_sha256, reservation_usd, status, "
            "reserved_at) VALUES ('logical-2', 1, 'llm-unitize', 'cand-1', "
            "'anthropic:fixture', 'anthropic', 'secondary', 'fixture prompt', "
            f"'{'c' * 64}', '{'b' * 64}', 0.1, 'succeeded', "
            "'2026-08-17T00:00:00Z')"
        )
    finally:
        connection.close()

    with pytest.raises(
        StageAReplayExecutorError,
        match="does not commit exactly one account alias for 'anthropic'",
    ):
        _canonical_provider_account(
            _caps(with_account=False), _spec(journal), "anthropic"
        )


def test_a_credential_shaped_journal_alias_refuses(tmp_path: Path) -> None:
    """A journal-sourced alias faces the same publishable-alias rule as caps.

    The refusal must also name the journal rather than the caps artifact, so an
    incident report points at the artifact that actually carried the value.
    """

    journal = _journal(
        tmp_path / "journal.sqlite3", accounts={"anthropic": "sk-live-secret"}
    )

    with pytest.raises(
        StageAReplayExecutorError,
        match="pinned provider journal account must be a public account alias",
    ):
        _canonical_provider_account(
            _caps(with_account=False), _spec(journal), "anthropic"
        )


class _Entry:
    """Minimal stand-in for the one ``ModelRegistryEntry`` field read here."""

    def __init__(self, provider: str) -> None:
        self.provider = provider


def test_a_request_alias_that_differs_from_the_journal_refuses(
    tmp_path: Path,
) -> None:
    """Deriving the alias does not make the request's own claim advisory."""

    journal = _journal(tmp_path / "journal.sqlite3", accounts={"anthropic": "default"})
    entries: Any = (_Entry("anthropic"),)

    assert _validated_provider_accounts(
        {"anthropic": "default"}, entries, _caps(with_account=False), _spec(journal)
    ) == {"anthropic": "default"}

    with pytest.raises(
        StageAReplayExecutorError,
        match="provider account alias differs from pinned caps: anthropic",
    ):
        _validated_provider_accounts(
            {"anthropic": "primary"},
            entries,
            _caps(with_account=False),
            _spec(journal),
        )
