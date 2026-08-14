"""Per-cycle acquisition/selection configuration (dn9.3).

This is the blessed home for post-Cycle-1 knobs. It is a Python import
registry, not the frozen ``legalforecast.acquisition_cycle_config.v1``
orchestrator plan.

## What lives here

Each cycle has one ``CycleConfig`` with:

- evaluation-registry pin (path and optional raw SHA-256)
- selector-model policy (primary + ordered alternates, exact callable IDs)
- per-document price cap (PACER page / cap / reservation)
- free-first policy
- cohort-policy version pin
- document-need bucket definitions
- ranking / tiebreak policy
- stratification option (off by default)
- spend ceilings
- typed-confirmation parameters
- retry / RECAP Fetch queue-lag tolerances
- ``activated`` (live-path gate)

## Cycle 1

``cycle-1`` is **legacy-pinned and not activated**. It documents current values
and points at the modules that remain authoritative for frozen paths. Cycle 1
code keeps reading those existing constants.

## Cycle 2

``cycle-2`` is a **draft** that may name ``gpt-5.6-luna`` primary with
``claude-sonnet-5`` and ``gemini-3.5-flash`` alternates (dn9.2). It is not
activated. ``load_activated_cycle("cycle-2")`` refuses until Cycle 1 results
are published (``LegalForecastBench-dm0g.7.3``). Do not close dn9.2 from this
plumbing.

## Selection entrypoints (dn9.1)

```python
from legalforecast.config import load_activated_cycle, preflight_selector_models

config = load_activated_cycle("cycle-2")  # refuses while activated=false
preflight_selector_models(config)         # same config supplies both sides
```

Tests and inert inspection use ``load_cycle`` (no activation gate) or
``dataclasses.replace`` on a registered config. Never look up an evaluation
registry except through ``config.evaluation_registry``.

## Lint fence

``uv run python -m legalforecast.config.fence`` fails CI when new
acquisition/selection constants or ``CycleConfig`` construction appear outside
this package. Cycle 1 holdovers are allowlisted in
``legalforecast/config/fence_baseline.json``; that list may only shrink.
