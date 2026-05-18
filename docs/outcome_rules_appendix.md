# Outcome Rules Appendix

This appendix fixes recurring Stage B outcome-label rules for
LegalForecast-MTD v1.0. It is grounded in the current synthetic fixtures,
motion-linkage tests, the Phase 0 case.dev smoke result, and the
post-feasibility pilot. The post-feasibility pilot produced zero live clean packets:
case.dev search found candidate dockets, but docket-entry listing remained
unavailable, so no live candidate reached clean-packet construction or legal
review. Search-only hits are therefore not used as outcome-rule examples below.
Rows without a legitimate fixture or reviewed clean candidate are marked
unobserved in the v1 live pilot.

The primary label remains:

```text
1 = the challenged claim is fully dismissed as to the challenged defendant or defendant group
0 = the challenged claim survives in any material respect as to that defendant or defendant group
```

For fully dismissed units, the secondary amendment track records whether the
first written disposition expressly gives, denies, or is silent about amendment
opportunity. Later amendment, reconsideration, settlement, or appeal activity
does not change the primary label.

## Routing Rules

| Edge-case class | Rule | Rationale | Route | Example / pilot status |
| --- | --- | --- | --- | --- |
| Rule 12(b)(1) subject-matter jurisdiction | Include when the target motion challenges a pleaded claim or theory and the first written disposition fully resolves the unit. Label fully dismissed only when dismissal leaves no material part of that unit pending against the defendant/group. | Jurisdictional dismissal is a common MTD disposition and is operationally equivalent for survival forecasting when tied to a pleaded unit. | Include; route to review if dismissal is jurisdiction-only but the same unit survives on an alternative basis. | Unobserved in v1 live pilot: no clean/reviewed candidate containing a 12(b)(1) dismissal reached packet review. |
| Rule 12(b)(2) personal jurisdiction | Include as a defendant-specific unit. If the court dismisses all claims against a defendant for lack of personal jurisdiction, label each challenged claim-defendant unit fully dismissed for that defendant. | Personal-jurisdiction rulings often vary by defendant, so defendant-level unitization is essential. | Include; group defendants only when the motion and ruling treat them identically. | Unobserved in v1 live pilot: no clean/reviewed candidate with a defendant-specific personal-jurisdiction ruling reached packet review. |
| Rule 12(b)(6) failure to state a claim | Include as the ordinary core target. Label 1 only when the claim is dismissed in full as to that defendant/group; label 0 when any material part of the claim survives. | This is the central LegalForecast-MTD target. Partial theory rejection should not be inflated into claim dismissal. | Include. | Synthetic fixture: `test_ingestion_discovery_extraction_and_linkage_happy_path` uses a motion-to-dismiss disposition linked to ECF No. 12. |
| Rule 12(c) judgment on the pleadings | Include when the motion is functionally an MTD-equivalent attack on the pleadings. Apply the same claim-defendant labeling rules. | Rule 12(c) tests pleadings after answer and is close enough to the MTD skill for v1 when the record remains pleadings-focused. | Include; flag as Rule 12(c) in metadata. | Unobserved in v1 live pilot: Phase 0 search found 8 `12(c)` hits, but none became a clean/reviewed packet because docket-entry listing was unavailable. |
| Arbitration or stay orders | Exclude units resolved only by a stay, referral to arbitration, or compelled arbitration without a dismissal of the claim. Include only if the court expressly dismisses the claim or action as to the unit. | The primary target is dismissal, not forum sequencing or litigation pause. | Exclude or route to review if the order mixes dismissal and compelled arbitration. | Unobserved in v1 live pilot: no clean/reviewed arbitration or stay candidate reached packet review. |
| Venue | Exclude pure venue transfer or venue-stay rulings. Include only if the venue ruling dismisses the claim/action as to the unit. | A transfer is not claim survival or dismissal on the merits or pleadings sufficiency. | Exclude transfer-only outcomes; review mixed dismissal/transfer orders. | Unobserved in v1 live pilot: no clean/reviewed Rule 12(b)(3) or venue candidate reached packet review. |
| Transfer | Exclude orders transferring the case without dismissing the target units. Do not infer dismissal from transfer or consolidation. | Transfer changes forum, not claim-defendant survival. | Exclude as not an MTD outcome; record transfer reason. | Unobserved in v1 live pilot: no clean/reviewed transfer-only candidate reached packet review. |
| Forum non conveniens | Include if the court dismisses the action or claim on forum non conveniens grounds. Label fully dismissed for affected units, with amendment track not applicable unless the court expressly grants repleading leave. | Forum non conveniens can terminate the unit even though it is not a Rule 12(b)(6) merits ruling. | Include; flag doctrine in metadata. | Unobserved in v1 live pilot: no clean/reviewed forum non conveniens dismissal reached packet review. |
| Personal jurisdiction | Apply the Rule 12(b)(2) defendant-specific rule. If some defendants are dismissed and others remain, label per defendant/group. | The benchmark unit is claim x defendant/group, so asymmetric jurisdiction rulings should not be averaged at motion level. | Include with defendant-specific units. | Unobserved in v1 live pilot: no clean/reviewed split personal-jurisdiction result reached packet review. |
| Anti-SLAPP | Include only when the anti-SLAPP ruling is packaged with or functionally resolves a Rule 12-style attack on the pleaded claim. Exclude fee-only, discovery-stay-only, or state-procedure rulings that do not dismiss the unit. | Anti-SLAPP mechanisms vary and can measure a different skill unless tied to claim dismissal. | Review by default; include only with clear dismissal. | Unobserved in v1 live pilot: no clean/reviewed anti-SLAPP candidate reached packet review. |
| Report and recommendation adoption | If the R&R itself was available pre-decision and already recommended the target outcome, exclude the later adoption order as leaked. If the target forecast point is before the R&R and the first written disposition is the R&R, include the R&R as the decision. | An R&R can be the outcome-revealing document; adoption after an available R&R is not a clean forecast target. | Exclude adoption-after-R&R leakage; include first R&R disposition only if packet freeze precedes it. | Existing role classification treats report-and-recommendation text as decision/outcome material. |
| Mixed MTD/MSJ orders | Include only the Rule 12-style units that can be separated from summary-judgment or evidentiary rulings. Exclude the case if the order converts the target motion to summary judgment or the unit cannot be cleanly separated. | MSJ introduces a different record and skill. Mixed orders can contaminate v1 unless unit-specific treatment is clear. | Review; include separable MTD units, exclude converted or inseparable units. | Motion-linkage fixture covers mixed MTD/preliminary-injunction order routing. No clean/reviewed live MSJ-mixed candidate reached packet review in the v1 pilot. |
| Voluntary withdrawal | Exclude claims or motions withdrawn voluntarily before disposition. Do not label withdrawal as court dismissal. | The benchmark predicts court action, not party abandonment. | Exclude with voluntary-withdrawal reason. | Synthetic false-positive fixture: voluntary dismissal docket text is excluded as a false-positive dismissal signal. |
| Mootness | Include if the court dismisses the target claim as moot. Exclude if mootness only removes the motion from decision without dismissing the claim-defendant unit. | Mootness can be a dismissal outcome, but not every mootness order resolves the claim. | Review; include only express unit dismissal. | Unobserved in v1 live pilot: no clean/reviewed mootness candidate reached packet review. |
| Dismissal without prejudice | Label primary outcome as fully dismissed when the claim is dismissed in full, even without prejudice. Record amendment class according to express leave, express denial, or silence. | The primary target asks whether the claim survives the first written disposition, not whether it can be refiled or amended later. | Include; secondary amendment label required. | Unobserved in v1 live pilot: Phase 0 search found 10 `dismissed without prejudice` hits, but none became a clean/reviewed packet because docket-entry listing was unavailable. |
| Partial theory dismissal | Label 0 when the claim survives in any material respect, even if some theories, statements, predicates, damages theories, or requested remedies are dismissed. | The prediction unit is a claim-defendant unit, not every legal theory. | Include as surviving unless all material bases for the claim are dismissed. | Unobserved in v1 live pilot: no clean/reviewed partial-theory dismissal reached packet review; the rule is retained from fixture stress cases and the human-reliability pilot pain-point report. |
| Generic granted-in-part orders | Route to review unless the order text clearly maps each challenged claim-defendant unit to survival or dismissal. Exclude unresolved units if the mapping cannot be reconstructed without speculation. | Generic "granted in part" language is a label-noise source. | Review; include resolvable units, exclude ambiguous units. | Unobserved in v1 live pilot: Phase 0 search found 8 `granting in part and denying in part` hits, but none became a clean/reviewed packet because docket-entry listing was unavailable. |
| Successive amended complaints | Freeze Stage A units from the operative complaint and target motion before the first written disposition. Later amended complaints do not change the original label. If the target motion is mooted by an amended complaint before decision, exclude. | Later pleadings can otherwise rewrite the unit set after the outcome is known. | Include if first disposition resolves frozen units; exclude if amended complaint moots the target motion. | Unobserved in v1 live pilot: no clean/reviewed successive-amendment candidate reached packet review. |
| Multiple motions resolved in one order | Link each target motion to the shared disposition. Include units only when the order clearly identifies which motion/defendant/claim it resolves; otherwise route to review or exclusion. | Multiple motions create linkage ambiguity and can duplicate or misassign units. | Review; include clean links, exclude ambiguous links. | Synthetic linkage fixture covers multiple MTDs resolved together and ambiguous multi-motion exclusion. |

## Amendment Track

| Disposition language | Primary label | Amendment label |
| --- | --- | --- |
| Claim dismissed in full with express leave to amend, amendment deadline, or express invitation to seek leave | 1 | dismissed with express amendment opportunity |
| Claim dismissed in full with express denial of leave, futility finding, or dismissal with prejudice | 1 | dismissed with express denial/no amendment opportunity |
| Claim dismissed in full without amendment discussion | 1 | dismissed without express amendment opportunity |
| Claim survives in any material respect | 0 | not applicable |
| Court cannot map ruling to the frozen unit | none | route to review or exclude |

## Pilot Follow-Up Requirements

The live case.dev smoke and the post-feasibility pilot found candidate dockets
but no clean packets. The attempted pilot therefore supplies retrieval-blocker
evidence, not clean outcome-rule examples. The next fallback reconstruction
pilot should replace an "unobserved in v1 live pilot" note only when a candidate
reaches one of these states:

- reviewed clean packet with a candidate ID and case reference;
- excluded after record review with a documented exclusion reason tied to the
  row; or
- adjudicated lawyer-review example for the edge class.

Search-only candidate IDs must stay out of this appendix. If no reviewed
example exists for a row, keep the rule and keep the unobserved note rather than
inventing or over-reading a search hit.
