# Claude Opus 5.5 audit: Review Outside Counsel Engagement Letter for Problematic Terms — Issue Identification Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 45. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is mostly sound and closely tied to the record. The OCG itself supplies concrete bases for the rate caps, escalation ban, retainer, conflicts (the §2.2(b) 5% material-financial-interest rule squarely covers MedBridge's 8% stake), success-fee terms, budget and staffing criteria. Two criteria are problematic. C-014 rests on the false premise that the OCG does not address contract attorneys (§6.3 does, with a $225 document-review expectation). C-008 requires an extra-record, doubtful '3-4% market' comparison that a memo relying on the OCG's categorical ban would not make, and it alone can zero out an excellent memo under all-pass. Five others are arguable because they grade framing, provenance or hidden quotas rather than substance: C-029's appeals 'contradiction', C-036's staffing-plan attribution, C-026's 'uncapped' wording, C-023's duplicated MedBridge linkage, and C-033's 75%/three-type quota.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | source_conflict | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L122) | C-014 rests on the false premise that the OCG does not address contract attorneys; OCG §6.3 sets approval rules and rate caps | blind |
| [O2](#o2) | problematic | unsupported_fact | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L74) | C-008 requires a comparison to a 3-4% 'market standard' escalation that is not in the record and is doubtful as fact | blind |
| [O3](#o3) | arguable | ambiguous_or_unjudgeable | [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L242) | C-029 requires calling the appeals scope an 'internal contradiction' although the express appellate carve-out plausibly controls | blind |
| [O4](#o4) | arguable | unrequested_requirement | [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L298) | C-036 fails a correct rate analysis unless the memo cites the staffing plan, although the letter and Exhibit A list the same rates | blind |
| [O5](#o5) | arguable | internal_inconsistency | [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L218) | C-026 calls the success fee 'uncapped' but in the same breath says it maxes out at $1.42M | blind |
| [O6](#o6) | arguable | unrequested_requirement | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L194) | C-023 fails a memo that rejects the advance waiver under OCG §2.2 unless it also ties the waiver to MedBridge, duplicating C-034 | revised |
| [O7](#o7) | arguable | unrequested_requirement | [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L274) | C-033 imposes a hidden 75% coverage threshold and a three-recommendation-type quota | adopted_after_reading_sol |

<a id="o1"></a>
### O1. C-014 rests on the false premise that the OCG does not address contract attorneys; OCG §6.3 sets approval rules and rate caps

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L122)

The title ('unaddressed by OCG') and the first PASS route ('because contract attorneys are not addressed in the OCG') contradict the record. OCG §6.3 requires prior written approval for contract attorneys, expects document-review rates of no more than $225/hr, and caps substantive work at $425. The correct analysis is that $350/hr for document review exceeds the $225 expectation and needs prior approval. As written, the criterion rewards a memo that wrongly says the OCG is silent. A correct memo probably still passes through the 'require separate approval' route.

Evidence:
- `C-014`: “problematic because contract attorneys are not addressed in the OCG”
- `pinnacle-ocg-2024.docx.txt`: “Pinnacle expects that contract attorney rates for document review and similar non-substantive tasks will not exceed \$225 per hour.”
- `pinnacle-ocg-2024.docx.txt`: “The use of contract attorneys, temporary attorneys, or staff augmentation personnel on Pinnacle matters requires prior written approval”

Suggested fix: PASS if the memo flags the contract-attorney provision as noncompliant with OCG §6.3 (prior written approval required; $350/hr exceeds the $225/hr document-review expectation). Delete the 'not addressed in the OCG' premise and fix the title.

Related GPT-6 Sol findings: Confirmed defects: item 2.

<a id="o2"></a>
### O2. C-008 requires a comparison to a 3-4% 'market standard' escalation that is not in the record and is doubtful as fact

**Status:** problematic · **Category:** unsupported_fact · **Criteria:** [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L74)

No document supplies a market escalation benchmark. The OCG's objection is categorical: automatic or formulaic increases 'of any kind' have no effect (§3.2), and C-007 already credits that. A competent reviewer applying the OCG would call the clause void and not argue about the percentage, and would fail C-008 ('FAIL if no comparison to market-standard escalation rates is made'). The premise is also shaky: large-firm annual rate increases in recent years have been widely reported above 3-4%, though I could not verify current figures this session. Under the all-pass metric, this criterion alone can zero out a memo that is correct on the OCG.

Evidence:
- `C-008`: “above typical market rates (which are generally 3-4% annually) ... FAIL if no comparison to market-standard escalation rates is made.”
- `pinnacle-ocg-2024.docx.txt`: “Pinnacle does not agree to automatic, across-the-board, or formulaic rate increases of any kind.”

Authorities (✓ = primary text checked in the auditing session):
- Industry law-firm rate surveys (e.g., Thomson Reuters Law Firm Financial Index), 2023-2025 (unverified): Large-firm annual rate increases have commonly exceeded 3-4%, so 5% is not clearly above market

Suggested fix: Delete C-008 or fold it into C-007 as optional. At minimum, drop the 3-4% benchmark and accept any explanation of why the escalation is objectionable.

Related GPT-6 Sol findings: Confirmed defects: item 1.

<a id="o3"></a>
### O3. C-029 requires calling the appeals scope an 'internal contradiction' although the express appellate carve-out plausibly controls

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L242)

Section 1 says representation 'shall extend through trial' and that appellate work 'shall be scoped separately.' The staffing plan repeats the carve-out twice. Under the specific-over-general canon, many practitioners would read appeals as clearly excluded. They would address appeals through the budget's missing appeals phase (OCG §4.1(h)) or through interlocutory appeals being treated as an excluded extraordinary expense. The criterion fails any memo that does not frame 'all matters/related proceedings' as ambiguous. Some residual ambiguity (undefined 'related proceedings', interlocutory appeals) makes flagging defensible, so this is arguable, not problematic.

Evidence:
- `engagement-letter-hbc.docx.txt`: “The Firm\'s representation shall extend through trial. ... Appellate work, if any, shall be scoped separately pursuant to a supplemental engagement letter.”
- `C-029`: “The memo should note that 'all matters' and 'related proceedings' could logically include appeals, creating ambiguity.”

Suggested fix: PASS on any memo that addresses appellate or post-trial coverage (scope carve-out clarification, OCG §4.1(h) budget omission, or interlocutory appeals). Also permit a reasoned conclusion that appeals are excluded.

Related GPT-6 Sol findings: Confirmed defects: item 3.

<a id="o4"></a>
### O4. C-036 fails a correct rate analysis unless the memo cites the staffing plan, although the letter and Exhibit A list the same rates

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L298)

The timekeeper rates are identical in Engagement Letter §3.1/Exhibit A and the staffing plan. A memo that compares Exhibit A rates to the OCG §3.1 caps has done the same analysis as one citing the staffing plan. Yet C-036 fails it if the comparison 'appears to be based solely on the engagement letter.' This grades citation provenance rather than substance, and it re-penalizes work already credited by the rate-cap criteria (C-001 to C-005). The instructions never ask for rates to be sourced to a particular document.

Evidence:
- `C-036`: “FAIL if the rate comparison appears to be based solely on the engagement letter without reference to the staffing plan.”
- `engagement-letter-hbc.docx.txt`: “Sandra K. Morrow                   Equity Partner / Lead Counsel           24 years                  \$1,050”

Suggested fix: Reward a real cross-document insight (e.g., using staffing-plan hours or contract-attorney rates that appear only in the staffing plan), or accept a comparison citing either document.

<a id="o5"></a>
### O5. C-026 calls the success fee 'uncapped' but in the same breath says it maxes out at $1.42M

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L218)

The formula, 10% × ($14.2M − resolution amount), is bounded at $1,420,000. What it lacks is the express dollar cap OCG §9.2(c) requires. The criterion asks the memo to note the fee is 'uncapped' while also stating its bounded maximum. A precise memo that says 'formula-bounded at $1.42M but no stated cap as §9.2(c) requires' could be failed by a literal judge. The 'similar calculation' alternative reduces but does not remove that risk.

Evidence:
- `C-026`: “notes that the success fee is uncapped and could be very large—up to approximately $1,420,000”
- `pinnacle-ocg-2024.docx.txt`: “(c) A maximum cap on the success fee expressed as a specific dollar amount;”

Suggested fix: PASS if the memo notes the absence of an express dollar cap (OCG §9.2(c)) and quantifies the potential size (up to about $1.42M), however it describes the formula's bound.

Related GPT-6 Sol findings: Arguable concerns, not confirmed legal defects: item 2.

<a id="o6"></a>
### O6. C-023 fails a memo that rejects the advance waiver under OCG §2.2 unless it also ties the waiver to MedBridge, duplicating C-034

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L194)

OCG §2.2 independently bans blanket or advance waivers ('not acceptable'). So a competent memo can correctly reject the letter's §11 waiver on that ground and handle the MedBridge 8% stake separately under §2.2(b). C-023's FAIL ('not connected to the conflict concern') fails that memo, and C-034 then fails it again for the same missing cross-reference. The linkage is reasonable, since Morrow raises the waiver 'on a related note,' and it belongs in C-034. Requiring it in C-023 as well double-penalizes one analytical choice under all-pass.

Evidence:
- `C-023`: “FAIL if the broad adverse-representation waiver is not flagged or not connected to the conflict concern.”
- `pinnacle-ocg-2024.docx.txt`: “Blanket or advance waivers of future conflicts are not acceptable.”

Suggested fix: Let C-023 pass whenever the memo flags the advance waiver as noncompliant with OCG §2.2. Keep the cross-document linkage only in C-034.

Related GPT-6 Sol findings: Arguable concerns, not confirmed legal defects: item 1.

<a id="o7"></a>
### O7. C-033 imposes a hidden 75% coverage threshold and a three-recommendation-type quota

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L274)

Recommendations are implicit in an issues memo, so requiring them is fair. But the instructions set no percentage and no requirement for varied remedy types, and a judge cannot reliably count 'identified issues' against recommendations or classify 'types.' A memo that recommends 'require OCG compliance/GC approval' for most issues could be failed on the diversity quota despite being substantively complete. Most competent memos would satisfy it naturally, so this is arguable, not problematic.

Evidence:
- `C-033`: “PASS if the memo provides a recommended course of action for at least 75% of identified issues, and at least three distinct recommendation types are used”
- `task.json instructions`: “prepare a comprehensive issues memo.”

Suggested fix: PASS if the memo gives actionable recommendations for the material issues. Drop the percentage and the type-diversity quota.

Related GPT-6 Sol findings: Confirmed defects: item 4.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Confirmed defects: item 1 | confirmed | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L74) | problematic | No document gives a market escalation benchmark. OCG §3.2 bans automatic increases of any size ('formulaic rate increases of any kind'), which C-007 already credits. C-008 fails any memo that relies on that categorical OCG ground without adding an extra-record, doubtful '3-4%' market claim. |
| Confirmed defects: item 2 | confirmed | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L122) | problematic | OCG §6.3 expressly covers contract attorneys: prior written approval, a $225/hr document-review expectation, and a $425 cap for substantive work. The title and the first PASS route ('not addressed in the OCG') state a false fact and would reward a memo that misreads the OCG. The approval route stays valid, so correct memos probably still pass. |
| Confirmed defects: item 3 | confirmed | [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L242) | arguable | Letter §1 says 'shall extend through trial' and expressly carves out appellate work, and the staffing plan repeats this, so the specific term plausibly controls. Some real ambiguity remains, though. 'Related proceedings' is undefined, and the budget treats interlocutory appeals as an excluded extraordinary expense. Flagging it is reasonable drafting caution, but making it mandatory fails reasonable readings. That makes it arguable, not confidently problematic. |
| Confirmed defects: item 4 | confirmed | [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L274) | arguable | An issues memo normally carries recommendations, so recommendations are implicit. The 75% threshold and the three-distinct-types quota are hidden numeric requirements that a judge cannot count reliably. In practice, competent memos naturally use several remedy types (strike, revise, get GC waiver, request conflicts letter), so misgrading is possible but unlikely. |
| Arguable concerns, not confirmed legal defects: item 1 | arguable | [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L178) (not_a_defect), [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L186) (not_a_defect), [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L194) (arguable), [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L282) (not_a_defect), [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L306) (not_a_defect), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L330) (not_a_defect) | mixed | Sol's RPC 1.7 point misses the controlling OCG text. OCG §2.2(b) defines a 5%+ equity stake as a 'material financial interest' and bars the engagement without detailed written disclosure and informed written consent. MedBridge's 8% triggers this. Alcott's check ran only against NovaTech, its principals and opposing counsel. So C-021/022/037/040 are well grounded. Only C-023's duplicate linkage FAIL is arguable. C-034 is the proper home for that synthesis. |
| Arguable concerns, not confirmed legal defects: item 2 | arguable | [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L218) | arguable | 10% × ($14.2M − resolution) is bounded at $1.42M. What is missing is the express dollar cap OCG §9.2(c) requires. The criterion calls the fee 'uncapped' and in the same breath gives its maximum. A precise memo ('formula-bounded but lacks §9.2(c) cap') could be failed by a literal judge. The trailing 'similar calculation' route softens this. |
| Arguable concerns, not confirmed legal defects: item 3 | arguable | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-outside-counsel-engagement-letter-for-problematic-terms/task.json#L82) | not_a_defect | OCG §3.6 rejects non-refundable retainers, requires trust-account deposit and refundability, and expressly invokes professional-conduct rules. The letter puts the $250K in the operating account yet credits it against final invoices, so it is really an advance fee. The FAIL condition triggers only if the non-refundability is not flagged at all. A memo grounded in OCG §3.6 passes. |

## Blind pass and what changed

I adopted C-033 as arguable from Sol: the 75% threshold and three-type quota are hidden and hard to count, though competent memos usually satisfy them. I narrowed blind O6 to C-023 only. C-034 is the proper home for the Morrow-email-to-waiver synthesis, and Morrow's own 'on a related note' invites that link, so C-034 is now not a defect. I dropped blind O7 (C-028): its FAIL condition triggers only if the e-discovery exclusion is not identified at all, and the $2.78M subtotal is trivial and legitimate, as Sol noted, so misgrading is unlikely. I kept C-029 at arguable rather than accepting Sol's 'confirmed': undefined 'related proceedings' and interlocutory appeals leave some real ambiguity. I rejected Sol's concerns on C-021/C-022/C-037/C-040 and C-009 because controlling OCG text supports them. OCG §2.2(b) defines a 5%+ equity stake as a material financial interest requiring disclosure and informed written consent, and OCG §3.6 rejects non-refundable retainers.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-014): C-014 rests on the false premise that the OCG does not address contract attorneys; OCG §6.3 sets approval rules and rate caps
- **O2** (problematic; C-008): C-008 requires a comparison to a 3-4% 'market standard' escalation that is not in the record and is doubtful as fact
- **O3** (arguable; C-029): C-029 requires calling the appeals scope an 'internal contradiction' although the specific appellate carve-out plausibly controls
- **O4** (arguable; C-036): C-036 fails a correct rate analysis unless the memo attributes the rates to the staffing plan, although the letter and Exhibit A list the same rates
- **O5** (arguable; C-026): C-026 calls the success fee 'uncapped' but in the same breath says it maxes out at $1.42M
- **O6** (arguable; C-023, C-034): C-023 and C-034 both fail a memo that flags the advance waiver (banned by OCG §2.2) without tying it to MedBridge
- **O7** (arguable; C-028): C-028's '$2.78M true total' framing may fail a memo that flags the e-discovery exclusion without doing the sum

## Coverage and limits

Blind pass: I read all 45 criteria, the instructions, and all six documents in full: the engagement letter with Exhibits A and B, the Pinnacle OCG (January 2024), the staffing plan, the CrossPoint proposal, and the Morrow and Alcott emails. I checked each factual premise against the record, and recomputed the staffing-plan arithmetic and the success-fee maximum. I did not read the system prompt or judge prompt files beyond what the task text says about them. Legal points (Model Rules 1.5, 1.8(h), 1.16; NC/DC treatment of retainers and liens) come from general knowledge. I read no primary sources this session. WebSearch failed on a spend-limit error, so I could not confirm current market rates for law-firm annual increases. That authority is marked unverified.

Reconciliation: I read all 45 criteria and the instructions. In the blind pass I read all six documents in full. In this pass I re-read the scope clause, the appellate references, OCG §§2.2, 3.2, 3.6 and 13-14, the retainer and waiver clauses, and both conflict emails to check Sol's findings. I read Sol's index entry and its full audit report. Legal points (RPC 1.5/1.7/1.16) come from general knowledge. I read no primary legal sources this session. The market-rate authority for C-008 is unverified.
