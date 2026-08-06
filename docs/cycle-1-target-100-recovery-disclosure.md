# Cycle 1 target-100 recovery disclosure continuation

Recovered CourtListener material remains quarantined until the disclosure pipeline authenticates its public provenance and scans every PDF for structural disclosure markers.

The supported continuation uses the reviewer-neutral v3 contract:

1. `plan-disclosure-provenance --schema-version v3` replays the exact recovery run card, purchase state, selection, restriction evidence, document bytes, and cohort policy.
2. If the resulting worksheet contains model-review-eligible marker-only exceptions, `review-disclosure-exceptions` uses the frozen Gemini 3.5 Flash authority described in [disclosure-model-review-v1.md](schemas/disclosure-model-review-v1.md), and `finalize-provenance-quarantine` independently replays that authority.
3. If the completed plan proves that the exact worksheet contains no model-review-eligible exceptions, the provider-free finalizer may instead use `--plan-run-card` together with `--require-no-model-review-eligible-exceptions`.
4. `resolve-post-recovery-documents` consumes only the finalizer's authenticated clearance run card.

The two initial-recovery templates are:

- `manifests/cycle-1-target-100.initial-recovery-disclosure.template.json` for the authenticated model-review path.
- `manifests/cycle-1-target-100.initial-recovery-disclosure-no-review.template.json` for the plan-proven empty-eligible-set path.

Both templates are partial cycle continuations and begin with `init-cycle`. Render them with `uv run legalforecast acquisition render-cycle-config --help`; the renderer validates every stage against the current CLI before publishing the config.

Ranked-reserve replacement recovery has the same two closed branches:

- `manifests/cycle-1-target-100.replacement-purchase-tranche.template.json` for authenticated model review when the v3 plan identifies eligible exceptions.
- `manifests/cycle-1-target-100.replacement-purchase-tranche-no-review.template.json` when the authenticated v3 plan proves the eligible set is empty.

Both replacement templates preserve the exact successor purchase authority and attempt policy through purchase, recovery, disclosure finalization, resolution, and cumulative-clearance publication.

## Fail-closed routing

The plan-proven provider-free branch is not a general operator override. The finalizer replays the completed plan run card, its source and output commitments, the current document tree, and any recovered-public authority. It rejects the branch if even one exact exception is eligible for model review.

The older quarantine-all workflow remains available only through the explicit `--quarantine-all-exceptions-without-review` compatibility flag. It quarantines every exception and is not the supported target-100 continuation. Omitting model authority, the empty-set proof, and that explicit compatibility flag fails closed.

Positive restriction evidence, incomplete scan coverage, missing affirmative CourtListener provenance, and other model-ineligible exceptions remain quarantined. They are never cleared merely because the model-review set is empty. A case that cannot satisfy the corpus gates must be excluded or replaced; an unresolved legal ambiguity is filed for John rather than self-adjudicated.

The model path does not accept caller-selected model identities. Its frozen source root binds the disclosure reviewer registry, evaluated-model registry, provider-cycle caps, and pricing. Provider journals and private model records remain below the configured private root and are not packet inputs.

The same plan, optional authenticated review, provider-free finalization, and resolution sequence applies to each ranked-reserve replacement recovery. The replacement template must bind its own replacement purchase authority and attempt policy; it must not reuse the initial purchase authority.

Neither continuation authorizes evaluation, freeze, or dispatch.
