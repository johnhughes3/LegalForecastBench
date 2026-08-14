"""D2's typed view of D1's per-cycle acquisition config.

Knobs live in ``legalforecast.config``. This module projects
``CycleConfig.as_public_record()`` into the fields document-need triage
consumes, and wraps D1's activation gate and registry preflight so selection
never side-channels a different evaluation registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Final, cast

from legalforecast.config import (
    CycleConfig,
    CycleConfigNotActivatedError,
    EvaluationRegistryPinError,
    SelectorRegistryCollisionError,
    require_activated,
)
from legalforecast.config import (
    preflight_selector_models as preflight_cycle_selector_models,
)

BUCKET_IDS: Final[tuple[str, str, str]] = (
    "clearly_required",
    "conditional",
    "clearly_not_required",
)
RANKING_PRIMARY: Final[str] = "max_cost"
RANKING_KEYS: Final[tuple[str, str, str]] = ("max_cost", "min_cost", "candidate_id")
_CENTS = Decimal("0.01")
_SHARE_QUANTUM = Decimal("0.0001")
_D1_PHRASE_TOKENS: Final[tuple[str, ...]] = (
    "{DECISION}",
    "{cycle_id}",
    "{request_sha256}",
    "{projected_cost_usd}",
    "{rule}",
    "{target_case_count}",
    "{session_scope_token}",
)


class DocumentNeedConfigError(ValueError):
    """Raised when a cycle config view cannot be used for document-need triage."""


def _require_text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise DocumentNeedConfigError(f"{label} must be a nonempty string")
    return value.strip()


def _require_bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise DocumentNeedConfigError(f"{label} must be boolean")
    return value


def parse_usd(value: object, label: str) -> Decimal:
    """Parse a nonnegative USD amount with at most cent precision."""

    if isinstance(value, Decimal):
        amount = value
    elif type(value) is str:
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise DocumentNeedConfigError(f"{label} is not a USD amount") from exc
    else:
        raise DocumentNeedConfigError(f"{label} must be a USD string")
    if not amount.is_finite() or amount < 0:
        raise DocumentNeedConfigError(
            f"{label} must be a nonnegative finite USD amount"
        )
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -2:
        raise DocumentNeedConfigError(f"{label} must have at most cent precision")
    return amount.quantize(_CENTS)


def format_usd(amount: Decimal) -> str:
    """Render a quantized USD amount as a two-decimal string."""

    return f"{amount.quantize(_CENTS):.2f}"


@dataclass(frozen=True, slots=True)
class NeedSelectorIdentity:
    """Exact callable identity: provider, model ID, and pinned snapshot."""

    provider: str
    model_id: str
    model_version_or_snapshot: str

    def __post_init__(self) -> None:
        _require_text(self.provider, "selector provider")
        _require_text(self.model_id, "selector model_id")
        _require_text(
            self.model_version_or_snapshot, "selector model_version_or_snapshot"
        )

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.provider, self.model_id, self.model_version_or_snapshot)


@dataclass(frozen=True, slots=True)
class NeedSelectorIds:
    """Exact selector IDs for one cycle. Primary first, then ordered alternates."""

    primary: str
    alternates: tuple[str, ...]
    identities: tuple[NeedSelectorIdentity, ...]

    def __post_init__(self) -> None:
        _require_text(self.primary, "selector_model_policy.primary")
        for index, model_id in enumerate(self.alternates):
            _require_text(model_id, f"selector_model_policy.alternates[{index}]")
        expected = (self.primary, *self.alternates)
        got = tuple(item.model_id for item in self.identities)
        if got != expected:
            raise DocumentNeedConfigError(
                "selector identities must match primary and alternates in order"
            )
        seen: set[tuple[str, str]] = set()
        for item in self.identities:
            key = (item.provider, item.model_id)
            if key in seen:
                raise DocumentNeedConfigError(
                    f"duplicate selector identity: {item.provider}:{item.model_id}"
                )
            seen.add(key)

    def all_model_ids(self) -> tuple[str, ...]:
        return (self.primary, *self.alternates)

    def allowed_identities(self) -> set[tuple[str, str, str]]:
        return {item.as_tuple() for item in self.identities}


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    """Cheapest-first ranking. Primary is always max_cost (dn9.1 / D1 cycle-2)."""

    primary: str
    tiebreak: tuple[str, ...]
    purchase_rule: str

    def __post_init__(self) -> None:
        if self.primary != RANKING_PRIMARY:
            raise DocumentNeedConfigError(
                f"ranking.keys[0] must be {RANKING_PRIMARY!r}"
            )
        if tuple(self.tiebreak) != RANKING_KEYS[1:]:
            raise DocumentNeedConfigError(
                "ranking.keys after max_cost must be "
                f"{list(RANKING_KEYS[1:])!r} (documented deterministic order)"
            )
        _require_text(self.purchase_rule, "ranking.purchase_rule")


@dataclass(frozen=True, slots=True)
class CaseMixStratification:
    """Optional cap on the share of bottom-decile-cost cases in the admitted set.

    Off by default: cheapest-first proceeds without mixing constraints. John
    accepts or declines the cap at selection time. The cap is always present on
    D1's CycleConfig; ``enabled`` is the switch. When enabled, admission
    freezes the quota for each drop+backfill pair, then revalidates the share
    against the new admitted size until it is within the cap.
    """

    enabled: bool
    bottom_decile_share_cap: Decimal

    def __post_init__(self) -> None:
        _require_bool(self.enabled, "stratification.enabled")
        cap = self.bottom_decile_share_cap
        if not cap.is_finite() or cap < 0 or cap > 1:
            raise DocumentNeedConfigError(
                "bottom_decile_share_cap must be in the closed interval [0, 1]"
            )
        exponent = cap.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -4:
            raise DocumentNeedConfigError(
                "bottom_decile_share_cap must have at most four decimal places"
            )


@dataclass(frozen=True, slots=True)
class TypedConfirmationParameters:
    """D1 typed-confirmation phrase for the single admitted-set ceiling."""

    decisions: tuple[str, ...]
    phrase_template: str
    session_scope_token: str

    def __post_init__(self) -> None:
        if not self.decisions:
            raise DocumentNeedConfigError(
                "typed_confirmation.decisions must not be empty"
            )
        seen: set[str] = set()
        for decision in self.decisions:
            token = _require_text(decision, "typed_confirmation.decision")
            if token != token.lower() or token in seen:
                raise DocumentNeedConfigError(
                    "typed_confirmation.decisions must be unique lowercase tokens"
                )
            seen.add(token)
        if "approve" not in seen:
            raise DocumentNeedConfigError(
                "typed_confirmation.decisions must include 'approve'"
            )
        template = _require_text(
            self.phrase_template, "typed_confirmation.phrase_template"
        )
        for token in _D1_PHRASE_TOKENS:
            if token not in template:
                raise DocumentNeedConfigError(
                    f"typed_confirmation.phrase_template must include {token}"
                )
        _require_text(
            self.session_scope_token, "typed_confirmation.session_scope_token"
        )


@dataclass(frozen=True, slots=True)
class DocumentNeedCycleView:
    """Subset of one cycle config consumed by document-need triage."""

    cycle_id: str
    activated: bool
    evaluation_registry_pin: str
    selector_model_policy: NeedSelectorIds
    per_document_price_cap_usd: Decimal
    pacer_per_page_usd: Decimal
    reservation_usd: Decimal
    free_first: bool
    cohort_policy_version_pin: str
    document_need_buckets: Mapping[str, str]
    ranking_policy: RankingPolicy
    spend_ceiling_usd: Decimal | None
    max_per_case_usd: Decimal | None
    typed_confirmation: TypedConfirmationParameters
    case_mix_stratification: CaseMixStratification

    def __post_init__(self) -> None:
        _require_text(self.cycle_id, "cycle_id")
        _require_bool(self.activated, "activated")
        _require_text(self.evaluation_registry_pin, "evaluation_registry_pin")
        _require_bool(self.free_first, "free_first")
        _require_text(self.cohort_policy_version_pin, "cohort_policy_version_pin")
        if self.per_document_price_cap_usd <= 0:
            raise DocumentNeedConfigError("per_document_price_cap_usd must be positive")
        if self.pacer_per_page_usd <= 0:
            raise DocumentNeedConfigError("pacer_per_page_usd must be positive")
        if self.reservation_usd <= 0:
            raise DocumentNeedConfigError("reservation_usd must be positive")
        if self.per_document_price_cap_usd > self.reservation_usd:
            raise DocumentNeedConfigError(
                "per_document_price_cap_usd must not exceed reservation_usd"
            )
        if self.spend_ceiling_usd is not None and self.spend_ceiling_usd < 0:
            raise DocumentNeedConfigError("spend_ceiling_usd must be nonnegative")
        if self.max_per_case_usd is not None and self.max_per_case_usd < 0:
            raise DocumentNeedConfigError("max_per_case_usd must be nonnegative")
        if (
            self.spend_ceiling_usd is not None
            and self.max_per_case_usd is not None
            and self.max_per_case_usd > self.spend_ceiling_usd
        ):
            raise DocumentNeedConfigError(
                "max_per_case_usd must not exceed spend.hard_cap_usd"
            )
        if set(self.document_need_buckets) != set(BUCKET_IDS):
            raise DocumentNeedConfigError(
                "document_need_buckets must define exactly " + ", ".join(BUCKET_IDS)
            )
        for bucket_id in BUCKET_IDS:
            _require_text(
                self.document_need_buckets[bucket_id],
                f"document_need_buckets.{bucket_id}",
            )
        object.__setattr__(
            self,
            "document_need_buckets",
            {key: self.document_need_buckets[key] for key in BUCKET_IDS},
        )


def document_need_view_from_cycle_config(
    config: CycleConfig,
) -> DocumentNeedCycleView:
    """Project D1's ``CycleConfig`` into the document-need view."""

    return document_need_view_from_cycle_record(config.as_public_record())


def document_need_view_from_cycle_record(
    record: Mapping[str, object],
) -> DocumentNeedCycleView:
    """Build the D2 view from D1's ``CycleConfig.as_public_record()`` shape."""

    policy = _mapping(record.get("selector_model_policy"), "selector_model_policy")
    ranking = _mapping(record.get("ranking"), "ranking")
    buckets = _mapping(record.get("document_need_buckets"), "document_need_buckets")
    confirmation = _mapping(record.get("typed_confirmation"), "typed_confirmation")
    mix = _mapping(record.get("stratification"), "stratification")
    price = _mapping(record.get("per_document_price_cap"), "per_document_price_cap")
    free_first = _mapping(record.get("free_first"), "free_first")
    cohort = _mapping(record.get("cohort_policy"), "cohort_policy")
    registry = _mapping(record.get("evaluation_registry"), "evaluation_registry")
    spend = _mapping(record.get("spend"), "spend")
    raw_alternates = policy.get("alternates")
    if not isinstance(raw_alternates, list) or isinstance(raw_alternates, str):
        raise DocumentNeedConfigError("selector_model_policy.alternates must be a list")
    raw_keys = ranking.get("keys")
    if not isinstance(raw_keys, list) or isinstance(raw_keys, str):
        raise DocumentNeedConfigError("ranking.keys must be a list")
    attributes = tuple(
        _ranking_attribute(item, index)
        for index, item in enumerate(cast(list[object], raw_keys))
    )
    if attributes != RANKING_KEYS:
        raise DocumentNeedConfigError(
            f"ranking.keys must be {list(RANKING_KEYS)!r} for document-need triage"
        )
    hard_cap_raw = spend.get("hard_cap_usd")
    hard_cap = (
        None if hard_cap_raw is None else parse_usd(hard_cap_raw, "spend.hard_cap_usd")
    )
    per_case_raw = spend.get("max_per_case_usd")
    max_per_case = (
        None
        if per_case_raw is None
        else parse_usd(per_case_raw, "spend.max_per_case_usd")
    )
    bucket_text = {
        key: _require_text(buckets.get(key), f"document_need_buckets.{key}")
        for key in BUCKET_IDS
    }
    identities = (
        _selector_identity(policy.get("primary"), "primary"),
        *(
            _selector_identity(item, f"selector_model_policy.alternates[{index}]")
            for index, item in enumerate(cast(list[object], raw_alternates))
        ),
    )
    return DocumentNeedCycleView(
        cycle_id=_require_text(record.get("cycle_id"), "cycle_id"),
        activated=_require_bool(record.get("activated"), "activated"),
        evaluation_registry_pin=_require_text(
            registry.get("path"), "evaluation_registry.path"
        ),
        selector_model_policy=NeedSelectorIds(
            primary=identities[0].model_id,
            alternates=tuple(item.model_id for item in identities[1:]),
            identities=identities,
        ),
        per_document_price_cap_usd=parse_usd(
            price.get("pacer_document_cap_usd"),
            "per_document_price_cap.pacer_document_cap_usd",
        ),
        pacer_per_page_usd=parse_usd(
            price.get("pacer_page_usd"), "per_document_price_cap.pacer_page_usd"
        ),
        reservation_usd=parse_usd(
            price.get("reservation_usd"), "per_document_price_cap.reservation_usd"
        ),
        free_first=_require_bool(free_first.get("required"), "free_first.required"),
        cohort_policy_version_pin=_require_text(
            cohort.get("schema_version"), "cohort_policy.schema_version"
        ),
        document_need_buckets=bucket_text,
        ranking_policy=RankingPolicy(
            primary=attributes[0],
            tiebreak=attributes[1:],
            purchase_rule=_require_text(
                ranking.get("purchase_rule"), "ranking.purchase_rule"
            ),
        ),
        spend_ceiling_usd=hard_cap,
        max_per_case_usd=max_per_case,
        typed_confirmation=TypedConfirmationParameters(
            decisions=_confirmation_decisions(confirmation.get("decisions")),
            phrase_template=_require_text(
                confirmation.get("phrase_template"),
                "typed_confirmation.phrase_template",
            ),
            session_scope_token=_require_text(
                confirmation.get("session_scope_token"),
                "typed_confirmation.session_scope_token",
            ),
        ),
        case_mix_stratification=CaseMixStratification(
            enabled=_require_bool(mix.get("enabled"), "stratification.enabled"),
            bottom_decile_share_cap=_parse_share(
                mix.get("bottom_decile_share_cap"),
                "stratification.bottom_decile_share_cap",
            ),
        ),
    )


def require_activated_cycle(config: CycleConfig) -> CycleConfig:
    """Refuse triage on an inert cycle config (draft Cycle 2 stays here)."""

    try:
        return require_activated(config)
    except CycleConfigNotActivatedError as exc:
        raise DocumentNeedConfigError(str(exc)) from exc


def preflight_selector_models(
    config: CycleConfig,
    *,
    repository_root_path: Path | None = None,
) -> None:
    """Refuse if any configured selector appears in this cycle's evaluation registry.

    Delegates to ``legalforecast.config.preflight_selector_models``. Both the
    selector policy and the registry pin come from *config* — there is no
    side-channel registry lookup.
    """

    try:
        preflight_cycle_selector_models(
            config, repository_root_path=repository_root_path
        )
    except (SelectorRegistryCollisionError, EvaluationRegistryPinError) as exc:
        raise DocumentNeedConfigError(str(exc)) from exc


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DocumentNeedConfigError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _confirmation_decisions(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or isinstance(value, str):
        raise DocumentNeedConfigError("typed_confirmation.decisions must be a list")
    return tuple(
        _require_text(item, f"typed_confirmation.decisions[{index}]")
        for index, item in enumerate(cast(list[object], value))
    )


def _selector_identity(value: object, label: str) -> NeedSelectorIdentity:
    if not isinstance(value, Mapping):
        raise DocumentNeedConfigError(f"{label} must be a selector-model object")
    record = cast(Mapping[str, object], value)
    return NeedSelectorIdentity(
        provider=_require_text(record.get("provider"), f"{label}.provider"),
        model_id=_require_text(record.get("model_id"), f"{label}.model_id"),
        model_version_or_snapshot=_require_text(
            record.get("model_version_or_snapshot"),
            f"{label}.model_version_or_snapshot",
        ),
    )


def _ranking_attribute(value: object, index: int) -> str:
    if not isinstance(value, Mapping):
        raise DocumentNeedConfigError(f"ranking.keys[{index}] must be an object")
    record = cast(Mapping[str, object], value)
    attribute = _require_text(
        record.get("attribute"), f"ranking.keys[{index}].attribute"
    )
    direction = _require_text(
        record.get("direction"), f"ranking.keys[{index}].direction"
    )
    if direction != "ascending":
        raise DocumentNeedConfigError(
            f"ranking.keys[{index}].direction must be 'ascending' for "
            "document-need cheapest-first ranking"
        )
    return attribute


def _parse_share(value: object, label: str) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    elif type(value) is str:
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise DocumentNeedConfigError(f"{label} is not a decimal share") from exc
    else:
        raise DocumentNeedConfigError(f"{label} must be a decimal string")
    if not amount.is_finite() or amount < 0 or amount > 1:
        raise DocumentNeedConfigError(f"{label} must be in [0, 1]")
    exponent = amount.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -4:
        raise DocumentNeedConfigError(f"{label} must have at most four decimal places")
    return amount.quantize(_SHARE_QUANTUM)
