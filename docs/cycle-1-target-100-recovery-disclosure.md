# Cycle 1 target-100 recovery disclosure continuation

Recovered CourtListener material remains quarantined until the disclosure pipeline authenticates its public provenance and scans every PDF for structural disclosure markers.

The supported continuation uses the reviewer-neutral v3 contract:

1. `plan-disclosure-provenance --schema-version v3` replays the exact recovery run card, purchase state, selection, restriction evidence, document bytes, and cohort policy.
2. The provider-free finalizer uses the completed `--plan-run-card` and the frozen [public-marker owner policy](schemas/provenance-public-marker-clearance-v1.md) to clear marker-only exceptions only when the plan already proves fresh recovered-public CourtListener provenance, complete scan coverage, valid visibility, and no positive restriction evidence.
3. Structural markers remain diagnostics; every exception outside that closed rule remains quarantined.
4. `resolve-post-recovery-documents` consumes only the finalizer's authenticated clearance run card.

The two initial-recovery templates are:

- `manifests/cycle-1-target-100.initial-recovery-disclosure.template.json` for the authenticated model-review path.
- `manifests/cycle-1-target-100.initial-recovery-disclosure-no-review.template.json` for the policy-bound provider-free public-marker path.

Both templates are partial cycle continuations and begin with `init-cycle`. Render them with `uv run legalforecast acquisition render-cycle-config --help`; the renderer validates every stage against the current CLI before publishing the config.

The disclosure artifact root and controlled private root must both be outside and disjoint from the frozen authority source root. Use sibling roots: neither writable root may equal, contain, or be contained by the frozen root. The renderer and cycle orchestrator reject an overlapping layout before any stage runs, while `review-disclosure-exceptions` repeats the containment checks immediately before provider activity.

Both continuations consume the initial recovery v2 outputs in place: `recap-fetch-quarantine-downloads.jsonl`, `purchased-case-relevance.jsonl`, `post-recovery-restriction-evidence.jsonl`, and `documents/recap-fetch-quarantine` beneath `RECOVERY_ROOT`. These paths are the exact outputs committed by `cycle-1-target-100.exact100-initial-recovery.template.json`; no compatibility alias, hand-copy, or alternate recovery root is part of the supported flow.

Ranked-reserve replacement recovery first uses one shared, closed prefix:

- `manifests/cycle-1-target-100.replacement-recovery-disclosure-plan.template.json` records the exact successor authority, purchases and recovers only that tranche, and completes the immutable v3 plan and worksheet under `PLAN_ROOT`.

Only after that plan run card is completed may the operator select exactly one post-plan continuation:

- `manifests/cycle-1-target-100.replacement-disclosure-model-continuation.template.json` when the authenticated worksheet contains model-review-eligible exceptions.
- `manifests/cycle-1-target-100.replacement-disclosure-empty-continuation.template.json` for the policy-bound provider-free public-marker continuation.

Both continuations bind the same `PLAN_ROOT`, begin after planning, and cannot recreate or overwrite the plan outputs. They preserve the exact successor purchase authority and attempt policy through disclosure finalization, resolution, and cumulative-clearance publication. Re-rendering or resuming a suffix therefore cannot purchase the tranche again.

## Fail-closed routing

The policy-bound provider-free branch is not a general operator override. The finalizer replays the completed plan run card, its source and output commitments, the current document tree, any recovered-public authority, and the canonical owner policy bound to the exact cohort policy. It clears only exact recovered-public marker-only rows and quarantines every other exception. The model suffix and provider-free suffix are mutually exclusive authority modes; a continuation must never combine them or silently omit both.

The older quarantine-all workflow remains available only through the explicit `--quarantine-all-exceptions-without-review` compatibility flag. It quarantines every exception and is not the supported target-100 continuation. Omitting model authority, a recognized provider-free proof mode, and that explicit compatibility flag fails closed.

Positive restriction evidence, incomplete scan coverage, missing affirmative CourtListener provenance, and other model-ineligible exceptions remain quarantined. They are never cleared merely because the model-review set is empty. A case that cannot satisfy the corpus gates must be excluded or replaced; an unresolved legal ambiguity is filed for John rather than self-adjudicated.

Purchased recovery rows do not require a synthetic public URL. A verifier-issued recovered-public lineage supplies their closed CourtListener source identity; that lineage remains attached when a structural-marker exception is model-reviewed so resolution can replay the exact purchase operation and fresh public-status evidence.

The model path does not accept caller-selected model identities. Its frozen source root binds the disclosure reviewer registry, evaluated-model registry, provider-cycle caps, and pricing. Provider journals and private model records remain below the configured private root and are not packet inputs.

The same plan, optional authenticated review, provider-free finalization, and resolution sequence applies to each ranked-reserve replacement recovery. The replacement template must bind its own replacement purchase authority and attempt policy; it must not reuse the initial purchase authority.

Neither continuation authorizes evaluation, freeze, or dispatch.
