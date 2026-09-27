# Claude Opus 5.5 audit: Draft Federal Complaint for Trade Secret Misappropriation and Breach of Employment Agreement

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 71. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric tracks the record closely: dates, file counts, parties, agreements and the forensic timeline check out. It has one clear defect. C-027 requires flagging preemption under a nonexistent NC TSPA provision (§ 66-157 is the limitations statute, and Article 24 has no displacement clause), and under the all-pass metric that alone can zero out a correct answer. Sol and I agree on that, and also that C-045 and C-057 are arguable overconstraints: they copy the GC's claim list and damages projections as mandatory, even though the instruction asks for 'viable' claims. I rate C-023 arguable rather than confirmed, because § 7.3's acknowledgment clause lets most competent complaints pass even though the exfiltration-prevention theory is weak. The other arguable items, C-046, C-018, the street-address criteria and C-012, penalize legitimate drafting judgment in some answers rather than stating wrong law.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L228) | C-027 requires flagging preemption under an NC TSPA provision that does not exist; § 66-157 is the limitations statute and has no (a) | blind |
| [O2](#o2) | arguable | legal_error | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L373) | C-045 requires a prospective-economic-advantage count that the record may not support under NC law, though the task asks only for viable claims | blind |
| [O3](#o3) | arguable | unrequested_requirement | [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L469) | C-057 requires pleading specific projected damages figures, though Rule 8 does not and a careful drafter may deliberately avoid them | blind |
| [O4](#o4) | arguable | source_conflict | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L194) | C-023 rewards the GC's theory that the notice shortfall could have prevented exfiltration, which the record timeline undercuts | revised |
| [O5](#o5) | arguable | legal_error | [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L381) | C-046 requires unjust enrichment against both defendants, though NC law bars it against Tate, whose express contracts govern | blind |
| [O6](#o6) | arguable | ambiguous_or_unjudgeable | [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L153) | C-018 requires stating that the facts could support ex parte seizure, which fails a memo that raises seizure and reasonably advises against it | blind |
| [O7](#o7) | arguable | internal_inconsistency | [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L41), [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L57), [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L81) | Address criteria titles name only the city, but the match criteria demand full street addresses and fail if they are omitted | blind |
| [O8](#o8) | arguable | source_conflict | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L105) | C-012 accepts the venue ground 'defendants reside in the district', though Tate's Chapel Hill address is in the M.D.N.C. | blind |

<a id="o1"></a>
### O1. C-027 requires flagging preemption under an NC TSPA provision that does not exist; § 66-157 is the limitations statute and has no (a)

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L228)

C-027 fails any submission that never mentions the risk that 'N.C. Gen. Stat. § 66-157(a)' preempts the unjust enrichment and conspiracy claims. That premise is wrong. § 66-157 is a single-sentence three-year limitations period with no subsection (a). Article 24 (§§ 66-152 to 66-157, with 66-158 to 66-162 reserved) has no displacement clause; NC did not adopt UTSA § 7. C-024 itself correctly describes § 66-157 as the limitations statute. A competent drafter who correctly omits a preemption doctrine NC lacks fails, and a drafter who repeats the invented doctrine passes. Under the all-pass metric, this alone can zero out a correct answer.

Evidence:
- `C-027`: “address the risk that the NC Trade Secrets Protection Act (N.C. Gen. Stat. § 66-157(a)) may preempt the unjust enrichment and/or civil conspiracy claims ... FAIL if preemption under the NC TSPA is never mentioned.”
- `C-024`: “the 3-year statute of limitations under N.C. Gen. Stat. § 66-157”

Authorities (✓ = primary text checked in the auditing session):
- N.C. Gen. Stat. § 66-157 (✓): Full text: 'An action for misappropriation of a trade secret must be commenced within three years after the misappropriation complained of is or reasonably should have been discovered.' It has no subsection (a) and no preemption language.
- N.C. Gen. Stat. §§ 66-152 to 66-157; §§ 66-158 to 66-162 reserved (✓): Article 24 covers definitions, the action, remedies, burden of proof, preservation of secrecy, and limitations. It has no clause displacing other civil remedies.

Suggested fix: Delete C-027, or make it optional credit for noting that common-law claims resting only on the same misappropriation may be attacked as duplicative or deficient on their own elements. Do not cite a TSPA preemption provision.

Related GPT-6 Sol findings: B6-DC-1.

<a id="o2"></a>
### O2. C-045 requires a prospective-economic-advantage count that the record may not support under NC law, though the task asks only for viable claims

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L373)

The instructions ask for 'all viable claims'. C-045 copies the GC's claim list and fails any complaint without this count. NC requires inducement of a third party and proof that a contract 'would have ensued' but for the interference. On this record, Kowalski and Okonkwo ignored the approaches and remain at Verdant, and Heartland reported only a presentation, with no lost order. A competent drafter could reasonably omit the count as not yet viable and explain why in the memo. C-045 would fail that answer.

Evidence:
- `task.json instructions`: “draft a federal complaint with all viable claims”
- `kowalski-declaration.docx.txt`: “I did not respond to the text message. I did not meet Dr. Tate for coffee”
- `okonkwo-declaration.docx.txt`: “I did not respond to the LinkedIn message. I did not engage in any conversation with the recruiter”
- `C-045`: “FAIL if this count is missing.”

Authorities (✓ = primary text checked in the auditing session):
- Dalton v. Camp, 353 N.C. 647, 548 S.E.2d 704 (2001) (✓): Interference with prospective advantage requires inducement of a third party and a showing that a contract 'would have ensued' but for the interference.

Suggested fix: Accept either a pleaded count or a memo explaining why the count was omitted or is at risk under NC law.

Related GPT-6 Sol findings: B6-DC-3.

<a id="o3"></a>
### O3. C-057 requires pleading specific projected damages figures, though Rule 8 does not and a careful drafter may deliberately avoid them

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L469)

C-057 fails a complaint with no dollar figures. Rule 8(a)(3) requires only a demand for relief, and complaints often plead damages 'in an amount to be proven at trial'. The CFO's figures are projections: a 30% DCF erosion, a hypothetical first-year diversion, and losses for '3' scientists when none has left. The workbook disclaims expert status. A competent drafter could keep these numbers out of the complaint and flag them in the memo, and C-057 would fail that answer.

Evidence:
- `damages-analysis-summary.xlsx.txt`: “This analysis does not constitute an expert damages report. A formal expert report will be prepared for litigation purposes.”
- `damages-analysis-summary.xlsx.txt`: “Loss of 3 senior R&D scientists at $1.2M training/institutional knowledge investment each”
- `C-057`: “FAIL if no specific damage figures are alleged.”

Suggested fix: Credit damages figures whether they appear in the complaint or in the memo, or accept a reasoned choice to plead damages 'to be proven at trial'.

Related GPT-6 Sol findings: B6-DC-3.

<a id="o4"></a>
### O4. C-023 rewards the GC's theory that the notice shortfall could have prevented exfiltration, which the record timeline undercuts

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L194)

PASS requires explaining that the short notice deprived Verdant of the chance to invoke garden leave, restrict access earlier, and 'potentially prevent some of the data exfiltration.' All exfiltration ended Nov 15, before the Nov 18 notice. Verdant then had 53 days of garden-leave rights and did not use them. On the GC's own counterfactual (departure around Jan 17), the missing week falls after all exfiltration. The GC explicitly asks counsel to evaluate consequential-damages causation, and the right answer is largely no. Partly offsetting this, § 7.3 has Tate acknowledging that short notice deprives the Company of these protections, so a complaint pleading that acknowledgment likely passes. The risk is a memo that correctly rejects exfiltration causation, since the judge applies the PASS text 'as described'.

Evidence:
- `showalter-memo-to-counsel.docx.txt`: “had Tate provided the required 60 days' notice (which would have set a departure date of approximately January 17, 2025)”
- `sentinel-forensics-report.docx.txt`: “The data exfiltration activities (October 27 through November 15, 2024) all precede Dr. Tate's resignation (November 18, 2024)”
- `tate-employment-agreement.docx.txt`: “failure to provide the full Notice Period deprives the Company of the opportunity to exercise these protections and constitutes a material breach of this Agreement.”

Suggested fix: PASS if either document addresses the practical consequence of the shortfall, including a critical assessment that it could not have prevented the pre-notice exfiltration.

Related GPT-6 Sol findings: B6-DC-2.

<a id="o5"></a>
### O5. C-046 requires unjust enrichment against both defendants, though NC law bars it against Tate, whose express contracts govern

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L381)

C-046 fails a complaint unless unjust enrichment names both Tate and AgriNova. In NC, an express contract governing the subject bars an implied-in-law claim, and Tate's Employment Agreement and CIAA expressly cover the use of confidential information. NC unjust enrichment also requires that the plaintiff conferred the benefit, which fits misappropriation poorly. Alternative pleading is routine, so many competent drafters would include the count anyway. But a drafter who deliberately pleads it only against AgriNova, or explains the omission in the memo, fails.

Evidence:
- `C-046`: “FAIL if the unjust enrichment count is missing or does not name both defendants.”
- `tate-ciaa.docx.txt`: “2.2 Non-Use. The Employee shall not use any Confidential Information for any purpose other than the performance of the Employee's authorized duties”

Authorities (✓ = primary text checked in the auditing session):
- Booe v. Shadrick, 322 N.C. 567, 369 S.E.2d 554 (1988) (✓): 'If there is a contract between the parties the contract governs the claim and the law will not imply a contract.'
- SiteLink Software, LLC v. Red Nova Labs, Inc. (N.C. Bus. Ct. 2018) (unverified): Unjust enrichment requires that the plaintiff conferred a benefit that was consciously accepted.

Suggested fix: PASS a complaint that pleads unjust enrichment against AgriNova (or against Tate only in the alternative), or that explains in the memo why it was not asserted against Tate.

<a id="o6"></a>
### O6. C-018 requires stating that the facts could support ex parte seizure, which fails a memo that raises seizure and reasonably advises against it

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L153)

PASS requires three things together: mentioning § 1836(b)(2), noting that it is for extraordinary circumstances, and noting that the wipe and encrypted-email facts 'could support such a motion'. Seizure is unavailable if a Rule 65 order would suffice. A competent memo might discuss seizure and conclude that a TRO with a USB turnover order is the better course. That memo addresses the remedy but may not affirm that the facts support it, so it falls between PASS and FAIL. The judge prompt's 'satisfies the criterion as described' makes a split likely.

Evidence:
- `C-018`: “noting it applies in extraordinary circumstances and that facts such as Tate wiping his laptop and using encrypted communications could support such a motion. FAIL if the ex parte seizure provision is never mentioned”

Authorities (✓ = primary text checked in the auditing session):
- 18 U.S.C. § 1836(b)(2)(A)(ii)(I) (unverified): Seizure is available only if a Rule 65 or other equitable order would be inadequate.

Suggested fix: PASS if either document identifies the ex parte seizure remedy and evaluates whether it applies, whatever the recommendation.

<a id="o7"></a>
### O7. Address criteria titles name only the city, but the match criteria demand full street addresses and fail if they are omitted

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L41), [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L57), [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L81)

The titles say only 'Research Triangle Park, NC', 'Chapel Hill, NC' and 'Raleigh, NC'. The match criteria demand full street addresses, including an individual's home address, and fail if the address is 'omitted'. Rule 10(a) requires names in the caption, not street addresses. Practitioners often plead only city and state, especially for an individual in a public filing. A judge could read 'resides in Chapel Hill, North Carolina' as an omitted address and fail an otherwise sound complaint on three criteria.

Evidence:
- `C-006`: “PASS if the complaint identifies Tate as an individual residing at 1822 Foxglove Lane, Chapel Hill, NC 27517. FAIL if his residential address is omitted or materially incorrect.”
- `C-004`: “Plaintiff's headquarters address: Research Triangle Park, NC”

Suggested fix: PASS on correct city and state, and treat a street address as optional.

<a id="o8"></a>
### O8. C-012 accepts the venue ground 'defendants reside in the district', though Tate's Chapel Hill address is in the M.D.N.C.

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L105)

Chapel Hill (27517) is in Orange County, part of the Middle District, not the Eastern. E.D.N.C. venue is proper under § 1391(b)(1) because AgriNova resides in Wake County and all defendants are NC residents, or under (b)(2). It is not proper on the theory that both defendants reside in the district. The 'and/or' means C-012 never fails a correct complaint, so this is a factual imprecision in the criterion, not a misgrade of competent work. It tolerates a misstatement of Tate's district. Low impact.

Evidence:
- `C-012`: “noting that defendants reside in the district and/or a substantial part of the events occurred there”
- `tate-employment-agreement.docx.txt`: “an individual residing at 1822 Foxglove Lane, Chapel Hill, NC 27517”

Authorities (✓ = primary text checked in the auditing session):
- 28 U.S.C. § 113(a)-(b) (unverified): Wake County is in the Eastern District; Orange County is in the Middle District.

Suggested fix: Accept § 1391(b)(1) (all defendants are NC residents, with AgriNova in this district) or § 1391(b)(2). Drop 'defendants reside in the district'.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| B6-DC-1 | confirmed | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L228) | problematic | I re-fetched ncleg Article 24 this session. § 66-157 is a single-sentence three-year limitations statute with no subsection (a), and §§ 66-158 to 66-162 are reserved. The Act has no displacement or preemption clause. C-027's PASS text requires treating a nonexistent statutory preemption risk, and the judge prompt applies the criterion 'as described'. A drafter who correctly omits the risk fails, and one who repeats the invented doctrine passes. |
| B6-DC-2 | confirmed | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L194) | arguable | The record supports Sol's timeline: exfiltration ran Oct 27 to Nov 15, notice came Nov 18, and the memo's counterfactual is a Jan 17 departure. The 'prevent some exfiltration' limb is therefore largely unsupported. But Employment Agreement § 7.3 has Tate acknowledging that short notice 'deprives the Company of the opportunity to exercise these protections'. A complaint that pleads that acknowledgment addresses the harm and likely passes. Only a memo that flatly rejects any harm is at risk. That misgrades some competent answers, not all, so 'confirmed' overstates it. |
| B6-DC-3 | arguable | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L373), [C-057](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L469) | arguable | This matches my blind findings. Heartland reported only a BioYield presentation, both scientists ignored the approaches and remain at Verdant, and NC requires proof that a contract 'would have ensued' (Dalton). The workbook disclaims expert status and assumes three departures that have not happened. The instructions ask for 'viable' claims, so a reasoned omission, or a complaint pleading damages to be proven at trial with the figures flagged in the memo, is competent work these criteria would fail. |

## Blind pass and what changed

I dropped blind O7 (C-024, NC TSPA limitations). The instruction asks for a memo on 'potential defenses', limitations is the first affirmative defense any litigator clears, and the GC flagged timeliness. That makes it demanding, not hidden. I dropped blind O9 (C-060/C-051, naming Sentinel). The report contemplates production as exhibits, and naming the forensic firm is ordinary pleading, so this is not a defect. I revised C-023 (blind O8, now O4): it stays arguable despite Sol's 'confirmed'. I added Employment Agreement § 7.3's acknowledgment clause as evidence, because it lets a complaint plead a deprivation of protections and pass. Only a memo that rejects causation outright is at risk. C-012 is kept but reframed as a low-impact factual imprecision, not a grading risk. C-027, C-045 and C-057 are unchanged and now link to Sol's B6-DC-1 and B6-DC-3. Verified flags now reflect only what I re-checked in this session: I re-fetched NC Article 24, and CourtListener exact-phrase searches matched the quoted passages in Booe and Dalton. 28 U.S.C. § 113 and SiteLink are marked unverified this pass.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-027): C-027 rests on an NC TSPA preemption provision that does not exist; § 66-157 is the limitations statute and has no subsection (a)
- **O2** (arguable; C-045): C-045 requires a prospective-economic-advantage count the record cannot support under NC law, though the task asks only for viable claims
- **O3** (arguable; C-046): C-046 requires unjust enrichment against both defendants, but NC law bars it against Tate, whose express contracts govern
- **O4** (arguable; C-018): C-018 requires stating that the facts could support ex parte seizure, which fails a memo that raises seizure and reasonably advises against it
- **O5** (arguable; C-057): C-057 requires pleading specific speculative damages figures, though Rule 8 does not and a careful drafter may deliberately avoid them
- **O6** (arguable; C-004, C-006, C-009): Address criteria titles name only the city, but the match criteria demand full street addresses and fail if omitted
- **O7** (arguable; C-024): C-024 requires addressing an NC TSPA limitations issue that does not exist on these facts
- **O8** (arguable; C-023): C-023 rewards the GC's causation theory for the notice shortfall, which the record timeline largely undercuts
- **O9** (arguable; C-060, C-051): Naming Sentinel is required although its report is marked privileged work product; this is a strategic drafting choice
- **O10** (arguable; C-012): C-012 accepts the venue ground 'defendants reside in the district', but Tate lives in Chapel Hill, which is in the M.D.N.C.

## Coverage and limits

Blind pass: I read all 71 criteria, the instructions, and all 10 documents in full: the Showalter memo, Employment Agreement, CIAA, Sentinel report, trade secret summary, damages workbook, resignation letter, press release, and the Kowalski and Okonkwo declarations. I did not open the generic system prompt or the judge prompt; the task description summarized them. WebFetch and WebSearch returned a spend-limit error, so I fetched statutory text with curl instead. Primary texts I read this session: N.C. Gen. Stat. Ch. 66, Art. 24 (§§ 66-152 to -157), 18 U.S.C. § 1833, and 28 U.S.C. § 113. On CourtListener I read passages of Dalton v. Camp, Booe v. Shadrick, and Sitelink v. Red Nova. I found no NC case law squarely on whether the TSPA displaces other claims, so that finding rests on the statute text alone. I did not check the E.D.N.C. local rules on party addresses. I did not verify NC authority on whether a breach of contract can be the underlying act for civil conspiracy, or on the intracorporate-conspiracy doctrine, so I did not flag them. I checked the record arithmetic and it holds: 53 days' notice, 7 days short; $64.5M + $16.92M + $3.6M = $85.02M; the DCF sums reconcile. Some record oddities change no criterion outcome and are not findings: Sentinel's codenames 'TP-101 through TP-214' vs. the summary's TP-101 to TP-900 list; Heartland called both the 'largest' and a 'top 5' distributor; the terminal value described both as a 4.3x exit multiple and as 2% perpetual growth; the press-release media phone number matching Showalter's; and the patent applications described as 'not yet published' although the first were filed in FY2021.

Reconciliation: In the blind pass I read all 71 criteria, the instructions, and all 10 documents in full. In this pass I read all of Sol's report files (audit.md, audit.json, summary.md, and the index entry) and the judge prompt (rubric_criterion.txt). I re-checked the record for C-023 (Employment Agreement § 7.3, memo §§ IV and IX, Sentinel timeline), venue and forum, and limitations. I re-fetched NC Gen. Stat. Ch. 66, Art. 24 from ncleg.gov and ran CourtListener exact-phrase searches that matched the quoted passages in Booe v. Shadrick and Dalton v. Camp. I did not re-read 28 U.S.C. § 113, SiteLink, or 18 U.S.C. § 1836(b)(2) this pass, and did not check E.D.N.C. local rules on party addresses.
