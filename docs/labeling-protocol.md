# Labeling Protocol

LegalForecast-MTD labels each frozen prediction unit from the first written disposition of the motion to dismiss. The primary target is whether that claim-defendant unit was dismissed in full. The label is not an assessment of whether dismissal was legally correct, and it is not revised because of later events.

## Scope

A prediction unit is a challenged claim against a defendant or group of similarly situated defendants. Stage A freezes the prediction units from the pre-decision record. Stage B labels only those frozen units from the written disposition and may not create new scored units from the decision text.

Every scored label must cite a verbatim excerpt from the disposition. Excerpts are validation material: if the cited text is not present in the first written disposition text, the label is invalid.

## First Written Disposition

The benchmark locks labels to the first written disposition that resolves the relevant motion-to-dismiss issue. Reconsideration orders, appeals, amended complaints, settlements, and later voluntary dismissals can be recorded as later procedural changes, but they do not change the locked primary label.

If a later order changes the practical posture of the case, the label remains tied to what the first written disposition did to the frozen unit. This rule keeps scoring aligned with what the model was asked to forecast.

## Primary Outcome

The primary label is `fully_dismissed`.

- `true`: the first written disposition fully dismisses the frozen claim-defendant unit.
- `false`: the unit survives in any material respect, including a partial dismissal that leaves any theory, claim, defendant group, or requested relief in that unit alive.
- `null`: the disposition is ambiguous and the unit has no primary scoring outcome.

Micro-Brier scoring uses `primary_outcome`: `1` for fully dismissed, `0` for not fully dismissed, and no scored value for ambiguous units.

## Partial Dispositions

A partial dismissal is not a full dismissal. If the court dismisses one theory, one remedy, one defendant, or one portion of a claim but leaves the frozen unit alive in material respect, label the unit as not fully dismissed.

Examples:

- "The notice theory is dismissed, but Count IV survives" maps to `fully_dismissed = false`.
- "Count I is dismissed as to the issuer, but denied as to the officer defendants" maps separately by unit: issuer unit `true`, officer unit `false`.
- "Punitive damages are dismissed, but the claim proceeds" maps to `false` for a claim-level unit.

## Leave To Amend

Leave to amend is a secondary label, not the primary target. A claim dismissed in full with leave to amend is still `fully_dismissed = true` for the primary benchmark outcome.

For fully dismissed units, record one amendment class:

- express leave to amend or an express invitation to seek leave: `dismissed_with_express_amendment_opportunity`
- express denial of leave: `dismissed_with_express_denial_of_leave`
- dismissal silent on amendment: `dismissed_without_express_amendment_opportunity`

The conditional amendment target applies only to fully dismissed units. Units that survive in material respect use `not_fully_dismissed` and do not receive a conditional amendment target.

## Mooted Motions

If the first written disposition denies or terminates the MTD as moot without independently dismissing the frozen claim-defendant unit, label the unit as not fully dismissed. The benchmark target is whether the judge dismissed the frozen unit in full, not whether the original motion remained procedurally live.

If the same disposition both declares a motion moot and separately dismisses the frozen unit in full, label the unit as fully dismissed and record the applicable amendment class. If the text does not make the unit-level outcome clear, mark the unit ambiguous rather than guessing.

## Ambiguous Or Missing Coverage

Use `ambiguous` when the first written disposition cannot be mapped reliably to a frozen unit. Ambiguous labels omit `fully_dismissed`, use the ambiguous amendment class, and are excluded from primary scoring.

If the decision resolves a material unit that Stage A failed to freeze, do not create a new scored unit at Stage B. Record a missing-unit flag and exclude the affected frozen unit from scoring under the v0.1 policy below.

If a frozen unit is not addressed by the first written disposition, do not infer an outcome from silence. Route it for review or exclusion under the current cycle's adjudication policy.

## Frozen-Unit Repair Policy (v0.1: Exclusion-Only)

The v0.1 benchmark policy is **exclusion-only**. When Stage B reports that the decision resolved a material unit missing from the frozen Stage A set, the affected frozen unit is excluded from scoring rather than repaired. Exclusion is the conservative direction: it removes a unit the model was never given a fair chance to forecast instead of retroactively adding a scored unit informed by the decision text.

Blinded frozen-unit repair — reconstructing the missing unit from the pre-decision record only, without exposing the disposition to the Stage A unitizer — is planned as **future work**. The data structures for blinded repair exist (`BlindedUnitRepairRequest`, `repair_frozen_units` in `legalforecast/unitization/adjudication.py`), but v0.1 has no production repair path or CLI and does not invoke one. Until a blinded repair workflow is built and validated, every missing-Stage-A case takes the exclusion branch.

Each such exclusion is recorded in the exclusion ledger with the primary reason `unit_missing_from_stage_a`, so the count of frozen-unit exclusions is auditable rather than silent.

## Public Accounting

Released artifacts should let reviewers distinguish at least these categories:

- scored fully dismissed units
- scored surviving or partially surviving units
- ambiguous units excluded from primary scoring
- frozen units excluded because a material unit was missing from Stage A (exclusion ledger reason `unit_missing_from_stage_a`; blinded repair is future work, so v0.1 counts these as exclusions)
- units or cases excluded because the first written disposition did not support a reliable label

Frozen-unit exclusion counts, keyed by exclusion-ledger reason (including `unit_missing_from_stage_a`), should be reported as aggregate counts in the released public accounting so an auditor can see how many units were dropped and why, without exposing non-public candidate material. The underlying per-candidate exclusion ledger stays in the private audit bundle; only the aggregate counts are public. The public artifact should include enough citation metadata for an auditor to trace every scored label back to the first written disposition without exposing non-public material.
