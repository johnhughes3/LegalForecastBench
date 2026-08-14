"""Per-cycle acquisition and selection configuration.

This is the blessed home for post-Cycle-1 acquisition/selection knobs. Cycle 1
is documented here but not activated: frozen paths keep reading their existing
constants. Cycle 2 is a named draft and is unreachable from live acquisition
until ``legalforecastbench-dn9.2`` is unblocked.

Selection entrypoints should call ``load_activated_cycle`` then
``preflight_selector_models`` on the same config object.
"""

from legalforecast.config.errors import (
    CycleConfigError,
    CycleConfigNotActivatedError,
    EvaluationRegistryPinError,
    SelectorRegistryCollisionError,
    UnknownCycleConfigError,
)
from legalforecast.config.preflight import preflight_selector_models
from legalforecast.config.registry import (
    CYCLE_CONFIGS,
    load_activated_cycle,
    load_cycle,
    repository_root,
    require_activated,
)
from legalforecast.config.types import (
    CYCLE_1_ID,
    CYCLE_2_ID,
    CohortPolicyPin,
    CycleConfig,
    DocumentNeedBucket,
    DocumentNeedBucketDefinitions,
    EvaluationRegistryPin,
    FreeFirstPolicy,
    LegacyPointer,
    PerDocumentPriceCap,
    RankingSortKey,
    RankingTiebreakPolicy,
    RetryQueueLagTolerances,
    SelectorModel,
    SelectorModelPolicy,
    SortDirection,
    SpendCeiling,
    StratificationPolicy,
    TypedConfirmationParams,
    usd,
    usd_text,
)

__all__ = [
    "CYCLE_1_ID",
    "CYCLE_2_ID",
    "CYCLE_CONFIGS",
    "CohortPolicyPin",
    "CycleConfig",
    "CycleConfigError",
    "CycleConfigNotActivatedError",
    "DocumentNeedBucket",
    "DocumentNeedBucketDefinitions",
    "EvaluationRegistryPin",
    "EvaluationRegistryPinError",
    "FreeFirstPolicy",
    "LegacyPointer",
    "PerDocumentPriceCap",
    "RankingSortKey",
    "RankingTiebreakPolicy",
    "RetryQueueLagTolerances",
    "SelectorModel",
    "SelectorModelPolicy",
    "SelectorRegistryCollisionError",
    "SortDirection",
    "SpendCeiling",
    "StratificationPolicy",
    "TypedConfirmationParams",
    "UnknownCycleConfigError",
    "load_activated_cycle",
    "load_cycle",
    "preflight_selector_models",
    "repository_root",
    "require_activated",
    "usd",
    "usd_text",
]
