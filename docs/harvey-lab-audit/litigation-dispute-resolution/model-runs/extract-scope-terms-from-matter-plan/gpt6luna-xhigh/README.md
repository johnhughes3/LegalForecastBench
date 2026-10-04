# GPT-6 Luna (xhigh): Extract Scope Terms from Matter Plan — Structured Extraction Report

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-scope-terms-from-matter-plan/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 63 of 76 criteria; GPT-5.5 passed 64 of 76 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [scope-extraction-report.docx](output/scope-extraction-report.docx) ([read as Markdown](output/scope-extraction-report.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Extracts WS-1: Federal MDL Defense with correct case number | Pass | Pass |
| [C-002](#c-002) | Extracts WS-2: State Court Defense with correct case number | Pass | Pass |
| [C-003](#c-003) | Extracts WS-3: Expert Retention and Management with named experts | Pass | Pass |
| [C-004](#c-004) | Extracts WS-4: Regulatory Response (CPSC) | Pass | Pass |
| [C-005](#c-005) | WS-4 origin noted as Revision 1 addendum (March 28, 2025) | Pass | Pass |
| [C-006](#c-006) | Extracts WS-4 sub-budget of $320,000 | Pass | Pass |
| [C-007](#c-007) | Extracts WS-4 coordinating/primary counsel distinction | Pass | Pass |
| [C-008](#c-008) | Extracts WS-5: Insurance Coverage Coordination with $95,000 sub-budget | Pass | Pass |
| [C-009](#c-009) | Extracts WS-5 liaison with Graystone Risk Advisors or relevant carriers | Pass | Pass |
| [C-010](#c-010) | Extracts WS-6: Document Review and E-Discovery with vendor restriction | Pass | Pass |
| [C-011](#c-011) | Extracts WS-7: Settlement Strategy and Mediation with pre-approved mediators | Pass | Pass |
| [C-012](#c-012) | Extracts scope exclusions EX-1 through EX-6 | Pass | Pass |
| [C-013](#c-013) | Extracts EX-6 exception for MDL consolidation | Pass | Pass |
| [C-014](#c-014) | Extracts blended hourly rates for rate categories | Pass | Pass |
| [C-015](#c-015) | Extracts contract reviewer rate of $55/hour | Pass | Pass |
| [C-016](#c-016) | Extracts monthly fee cap of $285,000 | Pass | Pass |
| [C-017](#c-017) | Extracts retroactive overage approval up to 10% by Deputy GC | Pass | Pass |
| [C-018](#c-018) | Extracts General Counsel approval required for overages exceeding 10% | Pass | Pass |
| [C-019](#c-019) | Extracts aggregate fee budget of $4,250,000 | Pass | Pass |
| [C-020](#c-020) | Extracts 50% budget checkpoint at $2,125,000 | Pass | Pass |
| [C-021](#c-021) | Extracts 75% budget checkpoint at $3,187,500 | Pass | Pass |
| [C-022](#c-022) | Extracts 10-business-day reconciliation requirement at budget checkpoints | Pass | Pass |
| [C-023](#c-023) | Extracts total disbursement budget of $1,350,000 | Pass | Pass |
| [C-024](#c-024) | Extracts disbursement sub-allocations (at least 3 of 4 categories) | Pass | Pass |
| [C-025](#c-025) | Extracts success fee rate of 7.5% | Pass | Pass |
| [C-026](#c-026) | Extracts Target Resolution Amount of $8,500,000 and success fee calculation method | Pass | Pass |
| [C-027](#c-027) | Extracts settlement authority tier: Deputy GC up to $3,000,000 | Pass | Pass |
| [C-028](#c-028) | Extracts settlement authority tier: General Counsel $3,000,001 to $6,000,000 | Pass | Pass |
| [C-029](#c-029) | Extracts settlement authority tier: Pinnacle Board above $6,000,000 | Pass | Pass |
| [C-030](#c-030) | Extracts staffing for Nathaniel Voss as Lead Trial Partner (40% max) | Pass | Pass |
| [C-031](#c-031) | Extracts staffing for Katherine Sinclair as Second Chair (75% max) | **Fail** | Pass |
| [C-032](#c-032) | Extracts junior associate headcount cap of 3 | Pass | Pass |
| [C-033](#c-033) | Extracts junior associate monthly billing limit of 160 hours | Pass | Pass |
| [C-034](#c-034) | Extracts Elaine Marchetti authorized for WS-4 and WS-5 only | Pass | Pass |
| [C-035](#c-035) | Extracts Elaine Marchetti billed at Partner rate ($685/hour) | Pass | Pass |
| [C-036](#c-036) | Extracts contract reviewer headcount cap of 15 | Pass | Pass |
| [C-037](#c-037) | Extracts Deputy GC approval for contract reviewer wave sizing | **Fail** | **Fail** |
| [C-038](#c-038) | Extracts staffing change requirements (15 business days notice, GC consent) | Pass | Pass |
| [C-039](#c-039) | Extracts key deadline: Initial disclosures April 15, 2025 | **Fail** | **Fail** |
| [C-040](#c-040) | Extracts key deadline: Damages expert by June 30, 2025 | Pass | Pass |
| [C-041](#c-041) | Extracts key deadline: Fact discovery closes August 1, 2025 | **Fail** | **Fail** |
| [C-042](#c-042) | Extracts key deadline: Expert reports September 15, 2025 | **Fail** | **Fail** |
| [C-043](#c-043) | Extracts key deadline: Trial date June 1, 2026 (estimated) | Pass | Pass |
| [C-044](#c-044) | Extracts key deadline: Daubert motion December 1, 2025 | **Fail** | **Fail** |
| [C-045](#c-045) | Extracts key deadline: Dispositive motions February 15, 2026 | **Fail** | **Fail** |
| [C-046](#c-046) | Extracts reporting: weekly Tuesday 3 PM ET call | Pass | Pass |
| [C-047](#c-047) | Extracts reporting: monthly written status report by 5th business day | Pass | Pass |
| [C-048](#c-048) | Extracts reporting: quarterly business review (QBR) in person | **Fail** | **Fail** |
| [C-049](#c-049) | Extracts $25,000 individual disbursement pre-approval threshold | Pass | Pass |
| [C-050](#c-050) | Extracts new expert retention approval requirement | Pass | Pass |
| [C-051](#c-051) | Extracts 30-day termination notice period | Pass | Pass |
| [C-052](#c-052) | Extracts 15-business-day file delivery upon termination | Pass | Pass |
| [C-053](#c-053) | Extracts success fee forfeiture on termination for cause or withdrawal | Pass | Pass |
| [C-054](#c-054) | Extracts wind-down fee of 2% after $2,000,000 billed | Pass | Pass |
| [C-055](#c-055) | Extracts prospective conflicts waiver: firm may represent clients adverse to Pinnacle affiliates but not Pinnacle Industrial Holdings or Pinnacle Hydraulics Solutions directly | Pass | Pass |
| [C-056](#c-056) | Extracts conflicts waiver restriction on hydraulic equipment matters | Pass | Pass |
| [C-057](#c-057) | Extracts conflicts waiver prohibition on use of confidential information | **Fail** | **Fail** |
| [C-058](#c-058) | ISSUE_001: Flags $780,000 vs. $760,000 expert budget discrepancy | Pass | Pass |
| [C-059](#c-059) | ISSUE_002: Flags WS-4 $320K sub-budget exceeds 5% threshold ($212,500) | Pass | Pass |
| [C-060](#c-060) | ISSUE_003: Flags Of Counsel rate not defined in rate schedule | **Fail** | **Fail** |
| [C-061](#c-061) | ISSUE_004: Flags contract reviewer rate missing from approved rate schedule | **Fail** | **Fail** |
| [C-062](#c-062) | ISSUE_005: Flags mediation deadline inconsistency (March 3 vs. Feb 28, 2026) | Pass | Pass |
| [C-063](#c-063) | ISSUE_006: Flags conflict between retroactive overage approval and OCG advance-approval rule | Pass | Pass |
| [C-064](#c-064) | ISSUE_007: Flags scope gap for non-HX-9000 claims consolidated into MDL | Pass | Pass |
| [C-065](#c-065) | ISSUE_008: Flags 'aggregate payments' in success fee is undefined | Pass | Pass |
| [C-066](#c-066) | ISSUE_010: Flags 'affiliates' undefined in prospective conflicts waiver | **Fail** | **Fail** |
| [C-067](#c-067) | Extracts rebuttal expert reserve amount of $230,000 | Pass | Pass |
| [C-068](#c-068) | Extracts mediation joint approval requirement | Pass | Pass |
| [C-069](#c-069) | Extracts accrued fees payment term of 45 days upon termination | Pass | Pass |
| [C-070](#c-070) | Extracts 5% threshold for post-engagement work stream additions | Pass | Pass |
| [C-071](#c-071) | Report includes document-specific references | Pass | Pass |
| [C-072](#c-072) | Extracts Marcus Oduya as lead paralegal | Pass | Pass |
| [C-073](#c-073) | Extracts key deadline: Rebuttal expert reports October 31, 2025 | **Fail** | **Fail** |
| [C-074](#c-074) | Extracts insurance coverage details (primary $5M/$10M, excess $15M) | Pass | Pass |
| [C-075](#c-075) | Extracts mediation deadline (90 days before trial) | Pass | Pass |
| [C-076](#c-076) | Correct matter number referenced (WC-2025-04381) | Pass | Pass |

## Judge reasoning

### C-001

Extracts WS-1: Federal MDL Defense with correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L19))

- **Sonnet 4.6: Pass.** The report clearly identifies WS-1 as 'Federal MDL Defense' in Section 3.2 and references MDL No. 3:24-md-02987 in the Northern District of Ohio in Section 3.1 under the Federal matter row. Both the work stream and the correct case number are present.
- **GPT-5.5: Pass.** The report explicitly identifies “WS-1 Federal MDL Defense” in the authorized work streams table and references MDL No. 3:24-md-02987 in the Northern District of Ohio in the proceedings/federal matter sections.

### C-002

Extracts WS-2: State Court Defense with correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L27))

- **Sonnet 4.6: Pass.** The report clearly identifies WS-2 as 'State Court Defense' in Section 3.2 and references Cuyahoga County Case No. CV-24-938471 in Section 3.1 under the state matter entry. Both elements required by the criterion are present and correct.
- **GPT-5.5: Pass.** The report identifies WS-2 as “State Court Defense” and references the Cuyahoga County Court of Common Pleas Case No. CV-24-938471 in the proceedings/state matter sections.

### C-003

Extracts WS-3: Expert Retention and Management with named experts ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L35))

- **Sonnet 4.6: Pass.** The report's Section 3.2 describes WS-3 Expert Retention & Management and names four experts: Yeoh ($120k), Nagarajan ($185k), Renner ($95k), and a damages expert TBD by Jun. 30, 2025 ($150k cap). Three named experts (Yeoh, Nagarajan, Renner) plus the damages expert placeholder are all present, satisfying the criterion of at least three named/referenced experts.
- **GPT-5.5: Pass.** The report expressly identifies WS-3 as “Expert Retention & Management” and lists the expert set/caps: Yeoh $120k, Nagarajan $185k, Renner $95k, and a damages expert TBD with a $150k cap. This satisfies the requirement to reference at least three of the four experts.

### C-004

Extracts WS-4: Regulatory Response (CPSC) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L43))

- **Sonnet 4.6: Pass.** The report extensively covers WS-4 (Regulatory Response / CPSC) in multiple sections, including Section 3.2 where it is listed as an authorized work stream with detailed description, budget allocation ($320,000), staffing, and boundaries. It is also addressed in the inconsistency register (items 2 and 3) and the checklist. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The report explicitly identifies Work Stream 4 as “Regulatory Response / CPSC,” including its scope, budget, staffing, and related CPSC addendum details.

### C-005

WS-4 origin noted as Revision 1 addendum (March 28, 2025) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L51))

- **Sonnet 4.6: Pass.** The report explicitly states in multiple places that WS-4 was added by the Revision 1 addendum dated March 28, 2025. For example, in Section 3.2 it states 'WS-4 was added after the CPSC opened an investigation on March 14, 2025' and the source table identifies 'Matter Plan Revision 1, Mar. 28, 2025 (MP-R1)' as adding WS-4. The documents reviewed section also lists 'CPSC Addendum (Mar. 28, 2025)' and the MP revision history is noted as 'showing WS-4 added Mar. 28, 2025.'
- **GPT-5.5: Pass.** The report explicitly states that Matter Plan Revision 1 dated March 28, 2025 adds CPSC WS-4, and elsewhere notes WS-4 was added by MP-R1/Revision 1.

### C-006

Extracts WS-4 sub-budget of $320,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L59))

- **Sonnet 4.6: Pass.** The report explicitly states WS-4 has a fee sub-budget of $320,000 in multiple places, including the work-stream table in Section 3.2 and the inconsistency register in Section 4, item 2.
- **GPT-5.5: Pass.** The report explicitly states WS-4 Regulatory Response / CPSC has an MP fee allocation of $320,000 and also describes it as a post-engagement $320,000 work stream / fee sub-budget.

### C-007

Extracts WS-4 coordinating/primary counsel distinction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L67))

- **Sonnet 4.6: Pass.** The report clearly states in the WS-4 work stream description: 'W&C coordinating counsel only; Meridian Compliance Law Group LLP is primary regulatory counsel.' This distinction is also repeated in Section 4, Issue 3, and in the recommended checklist. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The report explicitly states for WS-4 that W&C/Whitford & Callaway is coordinating counsel only and that Meridian Compliance Law Group LLP is primary regulatory counsel, including in the executive findings and WS-4 work-stream table.

### C-008

Extracts WS-5: Insurance Coverage Coordination with $95,000 sub-budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L75))

- **Sonnet 4.6: Pass.** The report clearly identifies WS-5 as 'Insurance Coverage Coordination' with a fee allocation of $95,000 in Section 3.2, and this is also confirmed in Appendix A where the work-stream fee allocations show $95k for WS-5.
- **GPT-5.5: Pass.** The report expressly lists “WS-5 Insurance Coverage Coordination” in the authorized work streams table and states its MP fee allocation as “$95,000.”

### C-009

Extracts WS-5 liaison with Graystone Risk Advisors or relevant carriers ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L83))

- **Sonnet 4.6: Pass.** The report explicitly mentions WS-5 Insurance Coverage Coordination with liaison with Graystone Risk Advisors (Simone Archer, SVP Claims), Fortitude Casualty & Surety Co. primary CGL policy, and Ridgeline Excess Insurance Company excess policy in Section 3.2.
- **GPT-5.5: Pass.** The report expressly describes WS-5 as involving liaison with Graystone Risk Advisors and identifies the relevant carriers Fortitude Casualty & Surety Co. and Ridgeline Excess Insurance Company.

### C-010

Extracts WS-6: Document Review and E-Discovery with vendor restriction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L91))

- **Sonnet 4.6: Pass.** The report explicitly identifies WS-6 (Document Review & E-Discovery) in Section 3.2, noting it involves collection, processing, hosting, review, privilege/QC and production coordinated with Precept Analytics, Inc., and states 'No alternate vendor without written DGC approval.' This satisfies both requirements of the criterion.
- **GPT-5.5: Pass.** The report explicitly identifies WS-6 as “Document Review & E-Discovery” and states it is coordinated with Precept Analytics, Inc., with no alternate vendor permitted without written DGC approval.

### C-011

Extracts WS-7: Settlement Strategy and Mediation with pre-approved mediators ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L99))

- **Sonnet 4.6: Pass.** The report clearly identifies WS-7 as 'Settlement Strategy & Mediation' in section 3.2 and lists all three pre-approved mediators: Ret. Judge Carolyn Fitzsimmons (Cleveland), Anthony Delmonico (Chicago), and Marissa Tran (Cincinnati). This satisfies the criterion of identifying WS-7 and naming at least two pre-approved mediators.
- **GPT-5.5: Pass.** The report identifies WS-7 as “Settlement Strategy & Mediation” and names all three pre-approved mediators: Ret. Judge Carolyn Fitzsimmons, Anthony Delmonico, and Marissa Tran.

### C-012

Extracts scope exclusions EX-1 through EX-6 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L107))

- **Sonnet 4.6: Pass.** The report's Section 3.3 explicitly lists all six exclusions: EX-1 (class actions), EX-2 (appellate work beyond trial level), EX-3 (affirmative claims/counterclaims), EX-4 (recall advice), EX-5 (lobbying/legislative advocacy), and EX-6 (non-HX-9000 claims unless consolidated into MDL). All 6 of the required exclusions are present, which exceeds the threshold of 5.
- **GPT-5.5: Pass.** The report expressly lists all six required scope exclusions in Section 3.3: EX-1 class actions, EX-2 appellate work, EX-3 affirmative claims/counterclaims, EX-4 recall advice, EX-5 lobbying/advocacy, and EX-6 non-HX-9000 claims unless consolidated/authorized. This meets the threshold of at least 5 of 6.

### C-013

Extracts EX-6 exception for MDL consolidation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L115))

- **Sonnet 4.6: Pass.** The report explicitly addresses EX-6 in Section 3.3 under 'Express exclusions and adjacent boundaries': 'Claims involving other hydraulic-press models excluded unless they enter proceedings covered by the EL (including MDL consolidation).' This clearly notes the MDL consolidation exception within EX-6. The report also elaborates on this in the inconsistency register (Item 1), further discussing the MDL consolidation exception and the additional MP requirement for a scope amendment even after consolidation.
- **GPT-5.5: Pass.** The report explicitly mentions the EX-6 exception, including that non-HX-9000 claims are excluded unless consolidated into the MDL/covered proceedings, and discusses the MDL-consolidation exception in multiple sections.

### C-014

Extracts blended hourly rates for rate categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L123))

- **Sonnet 4.6: Pass.** The agent's output in Section 3.4 lists all four blended rates: Partners $685/hr, Senior Associates (Years 5-8) $475/hr, Junior Associates (Years 1-4) $340/hr, and Paralegals $195/hr. All four rates are correctly stated, satisfying the criterion of >=3 correct rates.
- **GPT-5.5: Pass.** The output lists all four blended hourly rate categories correctly: Partners $685/hr, Senior Associates $475/hr, Junior Associates $340/hr, and Paralegals $195/hr. This exceeds the requirement of at least 3 correct rates and contains no incorrect listed rate among these categories.

### C-015

Extracts contract reviewer rate of $55/hour ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L131))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 (Staffing, rates, approvals and operating controls): 'reviewers $55/hr, separately itemized' and in the context of blended rates lists Partners, Senior Associates, Junior Associates, and Paralegals as the blended rate structure, with reviewers listed separately at $55/hr. Additionally, in the inconsistency register (item 7) and Appendix A, the $55/hour rate is referenced again with notes that reviewer costs are 'excluded from WS6 professional fees' and tracked separately. The report clearly states the $55/hour rate and indicates reviewers are not part of the blended rate structure (they are separately itemized/invoiced).
- **GPT-5.5: Pass.** The report states multiple times that contract reviewers are billed at $55/hour, describes them as separately itemized, and discusses that reviewer costs are treated separately/excluded from WS6 professional fees rather than simply part of the blended professional-fee structure.

### C-016

Extracts monthly fee cap of $285,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L139))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under Fee controls: 'monthly professional-fee cap $285,000'. It also references this cap in Appendix A where it notes 'no month above $285,000 (September 2025 is at cap)'. The $285,000 monthly fee cap is clearly extracted and present in the report.
- **GPT-5.5: Pass.** The report explicitly states under fee controls that the monthly professional-fee cap is $285,000, and references the same cap in the budget appendix.

### C-017

Extracts retroactive overage approval up to 10% by Deputy GC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L147))

- **Sonnet 4.6: Pass.** The report in Section 3.4 (Fee controls) states: 'EL allows up to 10% monthly overage retroactively approved by DGC within 15 business days; larger overage requires prior GC approval.' This captures the retroactive approval by the Deputy GC (DGC) for overages up to 10% above the $285,000 monthly cap. The criterion is satisfied.
- **GPT-5.5: Pass.** The report expressly states a $285,000 monthly professional-fee cap and that the Engagement Letter allows up to a 10% monthly overage to be retroactively approved by the Deputy GC within 15 business days. Although it does not calculate the resulting $313,500 figure, the required provision is present.

### C-018

Extracts General Counsel approval required for overages exceeding 10% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L155))

- **Sonnet 4.6: Pass.** The report states in Section 3.4 under 'Fee controls': 'EL allows up to 10% monthly overage retroactively approved by DGC within 15 business days; larger overage requires prior GC approval.' This clearly indicates that overages exceeding 10% above the monthly cap require General Counsel (GC) approval, satisfying the criterion.
- **GPT-5.5: Pass.** The report explicitly states under Fee controls that the monthly professional-fee cap is $285,000, that up to 10% overage may be approved by DGC, and that a larger overage requires prior General Counsel approval.

### C-019

Extracts aggregate fee budget of $4,250,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L163))

- **Sonnet 4.6: Pass.** The report clearly states the aggregate fee budget of $4,250,000 multiple times, including in Section 1 ('the $4.25 million aggregate fee budget'), Section 3.1 ('$4.25 million aggregate fee budget'), Section 3.4 ('Aggregate fee budget $4.25m through trial (excludes success fee, expert fees and other disbursements)'), and Appendix A where all three sources agree on $4,250,000. The report explicitly notes this excludes success fee, expert fees, and other disbursements.
- **GPT-5.5: Pass.** The report explicitly states: “Aggregate fee budget $4.25m through trial (excludes success fee, expert fees and other disbursements),” satisfying the required extraction.

### C-020

Extracts 50% budget checkpoint at $2,125,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L171))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Fee controls': 'checkpoints $2.125m (50%) and $3.1875m (75%), reconciliation due within 10 business days.' This clearly identifies the 50% budget checkpoint at $2,125,000.
- **GPT-5.5: Pass.** The report explicitly identifies the fee checkpoints as "$2.125m (50%) and $3.1875m (75%)" in the Fee controls section, satisfying the requirement to extract the 50% budget checkpoint at $2,125,000.

### C-021

Extracts 75% budget checkpoint at $3,187,500 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L179))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under Fee controls: 'checkpoints $2.125m (50%) and $3.1875m (75%), reconciliation due within 10 business days.' The 75% checkpoint at $3,187,500 (expressed as $3.1875m) is clearly identified.
- **GPT-5.5: Pass.** The report explicitly lists fee control checkpoints, including the 75% checkpoint as "$3.1875m," which equals $3,187,500.

### C-022

Extracts 10-business-day reconciliation requirement at budget checkpoints ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L187))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Fee controls': 'checkpoints $2.125m (50%) and $3.1875m (75%), reconciliation due within 10 business days.' This directly satisfies the criterion requiring the report to state that written budget reconciliation is required within 10 business days of reaching each budget checkpoint.
- **GPT-5.5: Pass.** The report includes the budget checkpoints at 50% and 75% and states that reconciliation is due within 10 business days. This captures the required 10-business-day reconciliation requirement at budget checkpoints.

### C-023

Extracts total disbursement budget of $1,350,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L195))

- **Sonnet 4.6: Pass.** The report explicitly states the total disbursement budget of $1,350,000 in multiple places. In Section 4 (item 6), it states 'EL §4.1 / Exhibit B: experts $780k; total disbursements $1.35m.' In Appendix A, the budget cross-check table shows 'Total disbursement budget' with '$1,350,000' under the Engagement Letter column. The report also notes this figure in the recommended checklist (item 4): 'Make all documents reflect $4.25m fee / $1.35m disbursement totals unless formally amended.'
- **GPT-5.5: Pass.** The report explicitly states the total disbursement budget is $1,350,000 in multiple places, including the budget conflict discussion and Appendix A.

### C-024

Extracts disbursement sub-allocations (at least 3 of 4 categories) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L203))

- **Sonnet 4.6: Pass.** The report lists the following disbursement sub-categories in Appendix A under 'Other disbursement categories': $340k e-discovery, $155k travel/depositions, $75k court reporting. Expert witness disbursements are listed separately as $780,000 (EL) / $760,000 (MP/workbook). All four sub-categories are present, satisfying the requirement of at least 3 of 4.
- **GPT-5.5: Pass.** The report lists all four disbursement sub-categories: expert witness fees ($780,000, though noting conflicts), e-discovery vendor costs ($340,000), travel/depositions ($155,000), and court reporting/transcripts ($75,000).

### C-025

Extracts success fee rate of 7.5% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L211))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.5: 'Success fee formula: if all claims within the engagement are finally resolved for aggregate payments at or below $8,500,000, W&C earns 7.5% × ($8,500,000 − actual aggregate payments)'. The 7.5% rate is clearly present.
- **GPT-5.5: Pass.** The report explicitly states the success fee is “7.5% of savings below $8.5 million” and provides the formula “7.5% × ($8,500,000 − actual aggregate payments).”

### C-026

Extracts Target Resolution Amount of $8,500,000 and success fee calculation method ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L219))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.5: 'Success fee formula: if all claims within the engagement are finally resolved for aggregate payments at or below $8,500,000, W&C earns 7.5% × ($8,500,000 − actual aggregate payments); no fee if aggregate payments are at or above $8.5m, and no negative fee/refund.' This clearly identifies the $8,500,000 threshold, the 7.5% percentage, the calculation method (percentage of the difference between $8.5m and actual aggregate payments), and the trigger condition (only if aggregate payments are at or below $8.5m). The criterion is fully satisfied.
- **GPT-5.5: Pass.** The output expressly identifies the $8,500,000 target/threshold and states the success fee formula as 7.5% × ($8,500,000 minus actual aggregate payments), triggered only when aggregate payments are at or below $8,500,000, with no fee at or above that amount.

### C-027

Extracts settlement authority tier: Deputy GC up to $3,000,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L227))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Settlement authority': 'DGC Ronan Giles: up to $3m', which corresponds to the Deputy GC having settlement authority up to $3,000,000. This matches the criterion exactly.
- **GPT-5.5: Pass.** The report explicitly states under settlement authority that DGC Ronan Giles has authority “up to $3m,” which matches Deputy GC up to $3,000,000.

### C-028

Extracts settlement authority tier: General Counsel $3,000,001 to $6,000,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L235))

- **Sonnet 4.6: Pass.** In Section 3.4 under 'Settlement authority', the report states: 'DGC Ronan Giles: up to $3m; GC Meg Stanhope: $3,000,001--$6m; Board: above $6m.' This correctly identifies the General Counsel's settlement authority tier as $3,000,001 to $6,000,000.
- **GPT-5.5: Pass.** The report explicitly states in the settlement authority section that GC Meg Stanhope has authority for $3,000,001--$6m, which matches the required tier.

### C-029

Extracts settlement authority tier: Pinnacle Board above $6,000,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L243))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Settlement authority': 'DGC Ronan Giles: up to $3m; GC Meg Stanhope: $3,000,001--$6m; Board: above $6m.' This correctly identifies the Pinnacle Board's settlement authority threshold as above $6,000,000.
- **GPT-5.5: Pass.** The report explicitly states in the settlement authority row that the Board has authority for amounts “above $6m,” which matches the required Pinnacle Board tier above $6,000,000.

### C-030

Extracts staffing for Nathaniel Voss as Lead Trial Partner (40% max) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L251))

- **Sonnet 4.6: Pass.** The report explicitly identifies 'Nate Voss lead trial partner (max 40% time)' in Section 3.4 under the Core team staffing control. This satisfies the criterion of identifying Nathaniel Voss as Lead Trial Partner with a maximum 40% personal time allocation.
- **GPT-5.5: Pass.** The report lists “Nate Voss” as “lead trial partner” with “max 40% time,” satisfying the requirement to identify Nathaniel Voss as Lead Trial Partner with a 40% maximum allocation.

### C-031

Extracts staffing for Katherine Sinclair as Second Chair (75% max) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L259))

- **Sonnet 4.6: Fail.** The report in Section 3.4 states 'Kate Sinclair second chair (up to 75%)' which identifies Katherine 'Kate' Sinclair as Second Chair with the 75% time cap. However, the criterion also requires identification of her as 'Senior Associate, Year 7.' The report does not mention her year level or classification as Senior Associate. The 75% cap is present and she is named as Second Chair, but the Year 7 / Senior Associate detail is missing. The criterion states PASS requires identifying her as 'Second Chair (Senior Associate, Year 7) with up to 75% time allocation.' Since the Senior Associate Year 7 classification is absent, the criterion is not fully satisfied.
- **GPT-5.5: Pass.** The report lists “Kate Sinclair” as second chair with “up to 75%” time allocation. Although it does not explicitly state Senior Associate, Year 7, the criterion’s essential fail triggers—Sinclair missing or 75% cap missing—are not present.

### C-032

Extracts junior associate headcount cap of 3 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L267))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Core team': 'up to 3 rotating junior associates (160 hours/person/month absent Billing Partner approval)'. This clearly captures the junior associate headcount cap of 3.
- **GPT-5.5: Pass.** The report explicitly states in the staffing/core team section that the core team includes “up to 3 rotating junior associates,” satisfying the required headcount cap extraction.

### C-033

Extracts junior associate monthly billing limit of 160 hours ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L275))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Core team': 'up to 3 rotating junior associates (160 hours/person/month absent Billing Partner approval)'. This directly captures the 160-hour monthly billing limit for junior associates and the condition requiring Billing Partner approval to exceed it.
- **GPT-5.5: Pass.** The report includes the staffing control: “up to 3 rotating junior associates (160 hours/person/month absent Billing Partner approval),” which states the required 160-hour monthly limit and approval condition.

### C-034

Extracts Elaine Marchetti authorized for WS-4 and WS-5 only ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L283))

- **Sonnet 4.6: Pass.** The report in Section 3.4 states: 'Elaine Marchetti authorized for regulatory/insurance streams only at Partner rate.' This identifies Marchetti as authorized for regulatory (WS-4) and insurance (WS-5) streams only, which matches the criterion. However, the criterion specifies she should be identified as 'Of Counsel, Washington, D.C.' — the report does not include her title or location. That said, the core requirement is that her work stream limitation (WS-4 and WS-5 only) is stated, which it is. The criterion says PASS if the report identifies her as authorized for WS-4 and WS-5 only, and FAIL if omitted or limitation not stated. The limitation is clearly stated ('regulatory/insurance streams only'), so this satisfies the criterion.
- **GPT-5.5: Pass.** The report names Elaine Marchetti and states she is “authorized for regulatory/insurance streams only,” which corresponds to WS-4 Regulatory Response/CPSC and WS-5 Insurance Coverage Coordination. The work-stream limitation is therefore stated.

### C-035

Extracts Elaine Marchetti billed at Partner rate ($685/hour) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L291))

- **Sonnet 4.6: Pass.** The report states in Section 3.4 under 'Core team': 'Elaine Marchetti authorized for regulatory/insurance streams only at Partner rate.' The Partner rate is defined as $685/hr in the 'Blended rates' row of the same section. Thus the report does establish that Elaine Marchetti is billed at the Partner rate of $685/hour.
- **GPT-5.5: Pass.** The report states that Elaine Marchetti is authorized for certain streams “at Partner rate,” and the adjacent blended rates row defines the Partner rate as $685/hr.

### C-036

Extracts contract reviewer headcount cap of 15 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L299))

- **Sonnet 4.6: Pass.** The report explicitly states 'Up to 15 reviewers' in the WS-6 work stream description under Section 3.2, and also mentions 'up to 15 contract reviewers per approved wave' in Section 3.4 under Core team. The 15-person cap is clearly present in the output.
- **GPT-5.5: Pass.** The report explicitly states under WS-6 that there may be “Up to 15 reviewers” and repeats in staffing that there are “up to 15 contract reviewers per approved wave,” satisfying the 15-person cap requirement.

### C-037

Extracts Deputy GC approval for contract reviewer wave sizing ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L307))

- **Sonnet 4.6: Fail.** The criterion requires the report to state that the exact number of contract reviewers per wave requires Deputy GC (DGC) approval. Looking at the report, in Section 3.2 under WS-6, it states 'each review wave requires advance DGC approval.' In Section 3.4 under 'Core team,' it mentions 'up to 15 contract reviewers per approved wave.' However, the report does not explicitly state that the exact number of contract reviewers per wave requires DGC approval. It says each wave requires advance DGC approval (which could be interpreted as approval of the wave itself, not specifically the number of reviewers), and separately notes the cap of 15 reviewers per approved wave. The criterion specifically asks whether the report states that the exact number of contract reviewers per wave requires Deputy GC approval. The report does not clearly articulate this specific requirement - it mentions DGC approval for waves and a cap of 15 reviewers, but does not explicitly connect DGC approval to the specific number/sizing of reviewers per wave.
- **GPT-5.5: Fail.** The report mentions that each review wave requires advance DGC approval and that up to 15 reviewers may be used, but it does not state that the exact number of contract reviewers per wave requires Deputy GC approval.

### C-038

Extracts staffing change requirements (15 business days notice, GC consent) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L315))

- **Sonnet 4.6: Pass.** In Section 3.4 (Staffing, rates, approvals and operating controls), the report states: 'EL/MP staffing changes also restrict new partner or lead-partner changes to prior GC consent and 15 business days' notice.' This directly captures the requirement that adding new partners or replacing the Lead Trial Partner requires General Counsel written consent with 15 business days' notice.
- **GPT-5.5: Pass.** The report expressly states in Section 3.4 that staffing changes restrict “new partner or lead-partner changes” to “prior GC consent and 15 business days’ notice,” which captures the required GC written consent and notice for adding partners or replacing the Lead Trial Partner.

### C-039

Extracts key deadline: Initial disclosures April 15, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L323))

- **Sonnet 4.6: Fail.** The agent's output does not mention April 15, 2025 as a deadline for initial disclosures in the MDL anywhere in the report. The report covers many deadlines and milestones (e.g., MDL trial June 1, 2026; mediation 90 days before trial; damages expert by June 30, 2025; QBR by May 15, 2025), but the April 15, 2025 initial disclosures deadline is entirely absent.
- **GPT-5.5: Fail.** The report does not mention an April 15, 2025 deadline for initial disclosures in the MDL. The date and deadline are missing.

### C-040

Extracts key deadline: Damages expert by June 30, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L331))

- **Sonnet 4.6: Pass.** In Section 3.2, under WS-3 Expert Retention & Management, the report states: 'damages expert TBD by Jun. 30, 2025, cap $150k.' This clearly identifies June 30, 2025 as the deadline to identify the damages expert.
- **GPT-5.5: Pass.** The report explicitly states that the damages expert is TBD/by June 30, 2025 in the WS-3 Expert Retention & Management section and notes the deadline to identify the damages expert.

### C-041

Extracts key deadline: Fact discovery closes August 1, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L339))

- **Sonnet 4.6: Fail.** The agent's output does not mention August 1, 2025 as the close of fact discovery in the MDL anywhere in the report. The timeline section references an estimated MDL trial date of June 1, 2026 and a mediation deadline of approximately March 3, 2026, but the fact discovery cutoff of August 1, 2025 is not listed anywhere in the document.
- **GPT-5.5: Fail.** The report does not list August 1, 2025 as the close of fact discovery in the MDL; that deadline is missing from the output.

### C-042

Extracts key deadline: Expert reports September 15, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L347))

- **Sonnet 4.6: Fail.** The agent's output does not mention September 15, 2025 as a deadline for expert reports anywhere in the document. While expert witnesses and their caps are discussed (Yeoh $120k, Nagarajan $185k, Renner $95k, damages expert TBD by Jun. 30, 2025), no September 15, 2025 expert report deadline appears in the extraction report.
- **GPT-5.5: Fail.** The report mentions expert-related items such as retaining a damages expert by June 30, 2025, but it does not list September 15, 2025 as the deadline for expert reports.

### C-043

Extracts key deadline: Trial date June 1, 2026 (estimated) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L355))

- **Sonnet 4.6: Pass.** The report explicitly mentions June 1, 2026 as the estimated MDL trial date in multiple places, including Section 3.1 ('estimated MDL trial June 1, 2026') and Section 4 item 10 ('90 days before June 1, 2026').
- **GPT-5.5: Pass.** The report explicitly lists the estimated MDL trial date as June 1, 2026 in the term/endpoint section and elsewhere.

### C-044

Extracts key deadline: Daubert motion December 1, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L363))

- **Sonnet 4.6: Fail.** The agent's output does not mention December 1, 2025 as the Daubert motion filing deadline anywhere in the report. While Daubert challenges are mentioned as part of WS-1's authorized work, no specific deadline date of December 1, 2025 is listed.
- **GPT-5.5: Fail.** The report mentions Daubert-related work generally but does not list December 1, 2025 as the Daubert motion filing deadline.

### C-045

Extracts key deadline: Dispositive motions February 15, 2026 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L371))

- **Sonnet 4.6: Fail.** The agent's output does not mention February 15, 2026 as a dispositive motion filing deadline anywhere in the report. The report discusses various dates and deadlines (e.g., MDL trial June 1, 2026; mediation deadline March 3/February 28, 2026; damages expert retention by June 30, 2025; first QBR by May 15, 2025), but the specific deadline of February 15, 2026 for dispositive motions is entirely absent from the extraction report.
- **GPT-5.5: Fail.** The report does not list February 15, 2026 as the dispositive motion filing deadline. It mentions other dates such as the estimated June 1, 2026 trial and mediation timing, but not the required dispositive motions deadline.

### C-046

Extracts reporting: weekly Tuesday 3 PM ET call ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L379))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Mediator / reporting': 'Weekly Tuesday 3:00 p.m. ET calls between Voss and Giles; Sinclair may substitute for Voss no more than twice per quarter.' This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly states: “Weekly Tuesday 3:00 p.m. ET calls between Voss and Giles,” and elsewhere identifies them as Nate Voss and Ronan Giles.

### C-047

Extracts reporting: monthly written status report by 5th business day ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L387))

- **Sonnet 4.6: Pass.** Section 3.4 of the agent's output explicitly states under 'Mediator / reporting': 'Monthly report by fifth business day.' This directly captures the monthly written status report due by the 5th business day obligation.
- **GPT-5.5: Pass.** The report includes the reporting obligation in Section 3.4, stating: “Monthly report by fifth business day.” This captures the monthly status report deadline by the 5th business day, satisfying the criterion.

### C-048

Extracts reporting: quarterly business review (QBR) in person ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L395))

- **Sonnet 4.6: Fail.** The criterion requires the report to state that QBRs are required to Meg Stanhope (GC) and Jonas Whitmore (CFO) in person at Pinnacle HQ. The agent's output in Section 3.4 states: 'QBRs quarterly at Pinnacle HQ for GC/CFO (MP also includes DGC), first no later than May 15, 2025.' While it mentions GC/CFO and Pinnacle HQ, it does not name Meg Stanhope as GC or Jonas Whitmore as CFO. The criterion specifically requires naming Meg Stanhope (GC) and Jonas Whitmore (CFO). The agent only uses the generic titles GC/CFO without identifying Jonas Whitmore as CFO. Therefore, the criterion is not fully satisfied.
- **GPT-5.5: Fail.** The report mentions QBRs quarterly at Pinnacle HQ for GC/CFO, but it does not specifically state that QBR presentations are required to Meg Stanhope and Jonas Whitmore, nor does it expressly identify Jonas Whitmore. The required QBR obligation as specified is therefore incomplete.

### C-049

Extracts $25,000 individual disbursement pre-approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L403))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'E-discovery / other spend': 'Individual disbursement >$25,000 requires DGC pre-approval; reallocation across disbursement categories >$25,000 requires prior written DGC approval.' This directly satisfies the criterion of extracting the $25,000 individual disbursement pre-approval threshold requiring Deputy GC approval.
- **GPT-5.5: Pass.** The report explicitly states: “Individual disbursement >$25,000 requires DGC pre-approval,” satisfying the required extraction of the $25,000 individual disbursement pre-approval threshold from the Deputy GC.

### C-050

Extracts new expert retention approval requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L411))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.2 under WS-3: 'Any unlisted expert and rebuttal-reserve use requires prior written GC approval and a budget estimate.' This directly satisfies the criterion that the report states retention of any new expert witness not listed in the Matter Plan requires General Counsel approval with a written budget estimate.
- **GPT-5.5: Pass.** The report explicitly states under “Expert approval” that any unlisted expert requires prior written GC approval and a budget estimate, satisfying the criterion.

### C-051

Extracts 30-day termination notice period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L419))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.5: 'Termination: either party may terminate on 30 calendar days' written notice.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly states under Section 3.5: “Termination: either party may terminate on 30 calendar days' written notice,” satisfying the criterion.

### C-052

Extracts 15-business-day file delivery upon termination ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L427))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.5: 'files/work product due within 15 business days' after termination notice. This directly satisfies the criterion requiring the report to state that the firm must deliver all files within 15 business days of termination.
- **GPT-5.5: Pass.** The report expressly states under termination economics that “files/work product [are] due within 15 business days” after termination, satisfying the required extraction.

### C-053

Extracts success fee forfeiture on termination for cause or withdrawal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L435))

- **Sonnet 4.6: Pass.** In Section 3.5, the report explicitly states: 'Success fee forfeited on termination for cause or W&C voluntary withdrawal.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly states in Section 3.5 that the “Success fee [is] forfeited on termination for cause or W&C voluntary withdrawal,” which matches the required provision.

### C-054

Extracts wind-down fee of 2% after $2,000,000 billed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L443))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.5: 'Wind-down fee: 2% of aggregate professional fees billed if Client terminates without cause after fees are "in excess of" $2m; EL says payable within 45 days.' It also notes the discrepancy between EL ('in excess of') and MP ('$2,000,000 or more') in item 11 of the inconsistency register. Both the 2% rate and the $2,000,000 threshold are clearly present in the report.
- **GPT-5.5: Pass.** The report expressly states: “Wind-down fee: 2% of aggregate professional fees billed if Client terminates without cause after fees are ‘in excess of’ $2m,” and also discusses the $2,000,000 threshold inconsistency. This includes both the 2% fee and the more-than-$2,000,000 billed trigger.

### C-055

Extracts prospective conflicts waiver: firm may represent clients adverse to Pinnacle affiliates but not Pinnacle Industrial Holdings or Pinnacle Hydraulics Solutions directly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L451))

- **Sonnet 4.6: Pass.** The report does address the conflicts boundary in Section 3.3 under 'Conflicts boundary': 'Prospective waiver reaches unrelated matters adverse to Pinnacle affiliates only with screens; it does not permit direct adversity to Pinnacle/PHS or any matter involving hydraulic equipment without GC written consent.' This describes the limited prospective waiver — the firm may represent clients adverse to Pinnacle affiliates (with screens) but not directly adverse to Pinnacle Industrial Holdings or Pinnacle Hydraulics Solutions. This satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly describes the prospective conflicts waiver, stating that it reaches unrelated matters adverse to Pinnacle affiliates only, and that it does not permit direct adversity to Pinnacle Industrial Holdings or PHS without GC consent. This captures the required core limitation.

### C-056

Extracts conflicts waiver restriction on hydraulic equipment matters ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L459))

- **Sonnet 4.6: Pass.** The report explicitly mentions in Section 3.3 under 'Conflicts boundary': 'Prospective waiver reaches unrelated matters adverse to Pinnacle affiliates only with screens; it does not permit direct adversity to Pinnacle/PHS or any matter involving hydraulic equipment without GC written consent.' This directly addresses the restriction that the conflicts waiver does not extend to matters involving hydraulic equipment of any manufacturer.
- **GPT-5.5: Pass.** The report includes a conflicts boundary stating that the prospective waiver “does not permit ... any matter involving hydraulic equipment without GC written consent,” which captures the hydraulic-equipment restriction required by the criterion.

### C-057

Extracts conflicts waiver prohibition on use of confidential information ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L467))

- **Sonnet 4.6: Fail.** The report mentions the conflicts waiver in Section 3.3 under 'Conflicts boundary': 'Prospective waiver reaches unrelated matters adverse to Pinnacle affiliates only with screens; it does not permit direct adversity to Pinnacle/PHS or any matter involving hydraulic equipment without GC written consent.' However, the report does not mention any condition that the prospective conflicts waiver is conditioned on no confidential information being used. The criterion specifically requires noting that the waiver is conditioned on no confidential information being used, which is absent from the report.
- **GPT-5.5: Fail.** The report discusses the prospective conflicts waiver and mentions screens and limits on direct adversity, but it does not state that the waiver is conditioned on no confidential information being used.

### C-058

ISSUE_001: Flags $780,000 vs. $760,000 expert budget discrepancy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L475))

- **Sonnet 4.6: Pass.** The agent's output explicitly identifies the $780,000 vs $760,000 expert budget discrepancy in multiple places. In Section 4, Issue #6 ('Expert and total disbursement budgets differ by $20k [HIGH]') states: 'EL §4.1 / Exhibit B: experts $780k; total disbursements $1.35m. MP §3.3 narrative calculates $780k ($550k named/anticipated + $230k rebuttal reserve), but MP §7.2 table says expert $760k / total $1.33m. Workbook disbursement tab says $760k, $210k reserve and $1.33m.' It also flags this in Appendix A where the finding states '$20,000 difference; table/workbook conflict with their own narrative and EL.' The report clearly identifies the $20,000 discrepancy and flags it as needing resolution.
- **GPT-5.5: Pass.** The report explicitly identifies the WS-3 expert budget discrepancy: it states the narrative calculates $780,000 from $550,000 named/anticipated experts plus a $230,000 rebuttal reserve, while the MP table and workbook show $760,000 with a $210,000 reserve, a $20,000 difference, and recommends resolving/correcting it.

### C-059

ISSUE_002: Flags WS-4 $320K sub-budget exceeds 5% threshold ($212,500) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L483))

- **Sonnet 4.6: Pass.** The report explicitly identifies in Section 4, Issue 2 ('WS-4 is >5% and approval/effectiveness is unverified [HIGH]') that the $320,000 WS-4 sub-budget exceeds 5% of $4.25m (which equals $212,500), that EL §§1, 7, 12 require prior written GC re-approval for a new work stream above this threshold, and that MP-R1 identifies Layton and Giles as signatories rather than the GC, with signature lines blank. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags that MP-R1 adds a $320,000 WS-4 work stream, that this exceeds 5% of the $4.25M aggregate budget ($212,500), and that the engagement letter requires prior written GC re-approval. It also notes MP-R1 does not evidence GC approval, identifying only Layton and Giles/signature issues, and recommends confirming a separate GC approval. Although it does not use the exact words “does not reference or amend the threshold,” it identifies the substantive addendum-vs-engagement-letter conflict required by the criterion.

### C-060

ISSUE_003: Flags Of Counsel rate not defined in rate schedule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L491))

- **Sonnet 4.6: Fail.** The report mentions Elaine Marchetti and states she is authorized 'for regulatory/insurance streams only at Partner rate,' and it lists the rate schedule (Partners $685/hr, Senior Associates $475/hr, Junior Associates $340/hr, Paralegals $195/hr, reviewers $55/hr). However, the report does not flag the gap that 'Of Counsel' is not a defined category in the rate schedule, and that billing Marchetti at the Partner rate creates ambiguity because the rate schedule has no Of Counsel category. The criterion specifically requires flagging this omission/ambiguity, which the report fails to do.
- **GPT-5.5: Fail.** The report notes that Elaine Marchetti is authorized for regulatory/insurance work at the Partner rate and lists the rate categories, but it does not identify her as Of Counsel or flag that the rate schedule lacks an Of Counsel category, creating ambiguity or potential billing disputes.

### C-061

ISSUE_004: Flags contract reviewer rate missing from approved rate schedule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L499))

- **Sonnet 4.6: Fail.** The criterion requires the report to flag that the $55/hour contract reviewer rate is not listed in the engagement letter's approved rate schedule, and that OCG v6.2 requires all timekeepers to be listed in the approved rate schedule and approved by the Deputy GC prior to billing — creating a compliance gap. The agent's report does address contract reviewer issues in several places (Section 3.4, Issue #7, Issue #14, Appendix A), but the specific issue flagged is about the classification and budget treatment of reviewer costs, not about the $55/hour rate being absent from the approved rate schedule. Issue #14 mentions that OCG §§3.1–3.2 require each individual's name, classification and rate approved before billing, and that EL/MP authorize unnamed reviewers without satisfying the named-timekeeper process. However, the report does not specifically flag that the $55/hour rate itself is missing from the engagement letter's rate schedule (Exhibit A), which lists rate categories for Partners, Senior Associates, Junior Associates, and Paralegals but not contract reviewers. The report treats the reviewer rate as established ($55/hr per EL §3.2) rather than identifying it as absent from the approved rate schedule. The specific compliance gap — that the rate is not in the rate schedule and OCG requires it to be there before billing — is not clearly articulated.
- **GPT-5.5: Fail.** The report flags that contract reviewers are generically authorized and that OCG §§3.1–3.2 require each individual’s name, classification, and rate to be approved in the rate schedule or later in writing before invoicing, and it recommends DGC approval for every reviewer. However, it does not specifically identify that the $55/hour contract reviewer rate is missing from the engagement letter’s approved rate schedule; instead it states the EL sets the $55/hour rate. The precise ISSUE_004 gap is therefore not fully flagged.

### C-062

ISSUE_005: Flags mediation deadline inconsistency (March 3 vs. Feb 28, 2026) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L507))

- **Sonnet 4.6: Pass.** The report explicitly identifies the mediation deadline inconsistency in Issue #10 (Section 4, item 10): 'MP §§3.7 and 6.1 calculate 90 days before June 1, 2026 as approximately March 3, 2026; MP §6.2 timeline chart states February 28, 2026.' This matches the criterion exactly, noting the ~3-day discrepancy between the calculated date (March 3, 2026) and the chart date (February 28, 2026).
- **GPT-5.5: Pass.** The report explicitly identifies the inconsistency: the Matter Plan sections calculating 90 days before the June 1, 2026 trial date as approximately March 3, 2026, while the timeline chart states February 28, 2026, and recommends correcting/confirming the intended date.

### C-063

ISSUE_006: Flags conflict between retroactive overage approval and OCG advance-approval rule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L515))

- **Sonnet 4.6: Pass.** The report explicitly addresses this conflict in Issue #8 ('Retroactive monthly overages conflict with OCG [HIGH]'). It identifies that EL §7.3 permits up to 10% over cap to be approved retroactively by DGC within 15 business days, while OCG §§4.3 prohibits all retroactive fee-cap overage approvals and requires advance written approval for any amount. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags “Retroactive monthly overages conflict with OCG,” stating that EL §7.3 permits up to 10% over the monthly cap to be approved retroactively by the DGC, while OCG §§4.3 and hierarchy prohibit retroactive fee-cap overage approvals and require advance written approval for any amount.

### C-064

ISSUE_007: Flags scope gap for non-HX-9000 claims consolidated into MDL ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L523))

- **Sonnet 4.6: Pass.** The report explicitly identifies this gap in multiple places. In Section 1 (Executive Findings), it notes that 'EX-6's MDL-consolidation exception does not line up with WS-1's "as currently constituted" limit' and that 'later consolidated non-HX-9000 claims are not authorized until review and a scope amendment.' In Section 3.3, EX-6 is extracted with the note that 'consolidation alone is not affirmative authority: review and an executed scope amendment are required first.' In Section 4, Issue #1 ('Later non-HX-9000/tag-along claims [HIGH]') directly addresses the conflict between EL §2(EX-6) and MP §§3.1/4.6, noting that WS-1 is limited to the MDL 'as currently constituted' and that even consolidated claims are not authorized without review and an executed amendment, with no automatic scope/budget expansion documented. This precisely matches the criterion's description of the gap between EX-6's MDL-consolidation exception and WS-1's lack of affirmative authorization or budget allocation for such claims.
- **GPT-5.5: Pass.** The report expressly identifies the non-HX-9000/tag-along authorization gap, explaining that EX-6’s MDL-consolidation exception conflicts with WS-1’s limitation to the MDL “as currently constituted,” and states that later consolidated non-HX-9000 claims are not affirmatively authorized absent review/scope amendment and budget approval.

### C-065

ISSUE_008: Flags 'aggregate payments' in success fee is undefined ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L531))

- **Sonnet 4.6: Pass.** The report explicitly addresses the undefined 'aggregate payments' term in multiple places. In the Executive Findings (Section 1), it notes 'the undefined "Actual Aggregate Payments" basis for the success fee.' In Section 3.5, it describes the success fee formula and notes the term is used without definition. Most importantly, in the inconsistency register (Issue 4, HIGH severity), the report states: 'EL §3.5 uses "aggregate payments," "actual aggregate payments" and "actual aggregate resolution amount" without defining included amounts. Emails Jan. 15--31 record W&C's indemnity-only proposal excluding defense/coverage/ALAE and carrier defense-cost reimbursement versus Client's broader total-cost preference including carrier payments.' The resolution section explicitly calls for defining 'treatment of settlements/judgments, insurer-paid amounts, defense costs, defense-cost reimbursement, allocated loss-adjustment expenses, fees/costs, multiple policies and non-cash consideration.' This directly satisfies the criterion requiring identification of the definitional gap and the ambiguity about whether it includes only settlements/judgments or also defense costs, insurer indemnity payments, or allocated loss adjustment expenses.
- **GPT-5.5: Pass.** The report explicitly flags that the success-fee terms “aggregate payments,” “actual aggregate payments,” and “actual aggregate resolution amount” are undefined, and it notes ambiguity over whether the base includes settlements/judgments, insurer-paid amounts/indemnity, defense costs, defense-cost reimbursement, and allocated loss-adjustment expenses.

### C-066

ISSUE_010: Flags 'affiliates' undefined in prospective conflicts waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L539))

- **Sonnet 4.6: Fail.** The agent's output discusses the conflicts boundary in Section 3.3, noting that the prospective waiver 'reaches unrelated matters adverse to Pinnacle affiliates only with screens' and requires GC written consent for direct adversity. However, the report does not flag that the term 'affiliates' is undefined in the prospective conflicts waiver, nor does it raise any concern about ambiguity regarding which entities are covered by the waiver given that Pinnacle has multiple subsidiaries beyond PHS. The criterion specifically requires identifying this undefined term as a problem. The report fails to raise this issue.
- **GPT-5.5: Fail.** The report mentions a prospective conflicts waiver involving “Pinnacle affiliates,” but it does not flag that the term “affiliates” is undefined or note ambiguity about which subsidiaries/entities are covered. Therefore it does not satisfy the specific criterion.

### C-067

Extracts rebuttal expert reserve amount of $230,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L547))

- **Sonnet 4.6: Pass.** The report explicitly mentions the $230,000 rebuttal reserve in multiple places. In Section 3.2 (WS-3 Expert Retention & Management), it states: 'MP narrative adds $230k rebuttal reserve (GC approval required).' In Section 4, Issue 6, it references '$230k rebuttal reserve' and contrasts it with the workbook's '$210k reserve.' The $550,000 named/anticipated experts figure is also mentioned in Section 4, Issue 6: 'MP §3.3 narrative calculates $780k ($550k named/anticipated + $230k rebuttal reserve).' The criterion is fully satisfied.
- **GPT-5.5: Pass.** The report explicitly identifies a $230,000 rebuttal reserve in the WS-3 description and again in the budget inconsistency section, noting it as part of the $780,000 expert allocation alongside $550,000 for named/anticipated experts.

### C-068

Extracts mediation joint approval requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L555))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 3.4 under 'Mediator / reporting': 'Mediator jointly approved by GC and Voss; Fitzsimmons, Delmonico and Tran pre-approved.' This clearly captures the joint approval requirement between the Pinnacle GC (Meg Stanhope) and the lead trial partner (Nate Voss).
- **GPT-5.5: Pass.** The report explicitly states under WS-7 that the mediator is to be jointly approved by the GC and Lead Trial Partner, and reiterates that mediator approval is jointly by GC and Voss.

### C-069

Extracts accrued fees payment term of 45 days upon termination ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L563))

- **Sonnet 4.6: Pass.** The report states in Section 3.5: 'accrued fees payable within 45 calendar days after final invoice. EL requires final invoice within 30 calendar days after termination.' This clearly captures the 45-day payment term for accrued fees upon termination.
- **GPT-5.5: Pass.** The report includes the termination term: “accrued fees payable within 45 calendar days after final invoice,” in the termination economics section. This satisfies the requirement to extract the 45-day accrued-fees payment term upon termination.

### C-070

Extracts 5% threshold for post-engagement work stream additions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L571))

- **Sonnet 4.6: Pass.** The report explicitly mentions the 5% threshold in Issue #2: 'EL §§1, 7, 12 require prior written GC re-approval for a new work stream above 5% of $4.25m ($212,500).' It also appears in the checklist item #1: 'Confirm signed Revision 1 and prior written General Counsel approval for the $320,000 WS-4 stream (above $212,500 threshold).' The criterion is fully satisfied.
- **GPT-5.5: Pass.** The report explicitly extracts the 5% post-engagement work-stream threshold, including the calculation ($4.25m × 5% = $212,500) and notes that WS-4 at $320,000 required prior written General Counsel re-approval.

### C-071

Report includes document-specific references ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L579))

- **Sonnet 4.6: Pass.** The report consistently provides document-specific references throughout all sections. In Section 3.1, each extracted term has a 'Source' column citing specific documents (e.g., 'EL §1; signature blocks', 'EL §1(a); MP §§1--2'). Section 3.2 references MP and MP-R1 for each work stream. Section 3.3 exclusions table cites specific sections of EL, MP, and MP-R1. Section 3.4 references EL, MP, OCG throughout. Section 3.5 cites EL and MP. Section 4 (inconsistency register) explicitly names documents and sections for every conflict item (e.g., 'EL §2(EX-6)', 'MP §3.1', 'MP-R1 §2.1', 'OCG §§4.3'). Appendix A cross-references EL, MP/R1, and workbook columns. Appendix B provides pinpoint references for each source. The citations are pervasive throughout the report, not confined to a single section.
- **GPT-5.5: Pass.** The report provides document-specific references throughout, including repeated citations to the Engagement Letter, Matter Plan, Revision 1 addendum, OCGs, budget workbook tabs, and negotiation emails. Extracted terms are sourced in tables and narrative sections, not confined to a single reference section.

### C-072

Extracts Marcus Oduya as lead paralegal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L587))

- **Sonnet 4.6: Pass.** The report's staffing section (Section 3.4) states: 'up to 2 paralegals led by Marcus Oduya.' This explicitly identifies Marcus Oduya as lead paralegal and notes up to 2 paralegals are authorized, satisfying the criterion.
- **GPT-5.5: Pass.** The report’s staffing section states: “up to 2 paralegals led by Marcus Oduya,” which names Marcus Oduya as lead paralegal and includes the authorization for up to two paralegals.

### C-073

Extracts key deadline: Rebuttal expert reports October 31, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L595))

- **Sonnet 4.6: Fail.** The agent's output does not mention October 31, 2025 as a deadline for rebuttal expert reports anywhere in the report. While the report discusses expert witnesses, budgets, and various deadlines, the specific date of October 31, 2025 for rebuttal expert reports is absent from the extraction.
- **GPT-5.5: Fail.** The report discusses expert retention and a rebuttal reserve, but it does not list October 31, 2025 as the deadline for rebuttal expert reports.

### C-074

Extracts insurance coverage details (primary $5M/$10M, excess $15M) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L603))

- **Sonnet 4.6: Pass.** The report explicitly mentions in WS-5 Insurance Coverage Coordination: 'Fortitude Casualty & Surety Co. primary CGL, Policy CGL-FCS-2024-07891 ($5m per occurrence / $10m aggregate); Ridgeline Excess Insurance Company, Policy XS-RID-2024-33045 ($15m follow-form excess).' Both the primary CGL coverage figures and the excess layer are clearly referenced in connection with WS-5.
- **GPT-5.5: Pass.** The report explicitly includes WS-5 Insurance Coverage Coordination and identifies Fortitude Casualty & Surety Co. primary CGL coverage at $5M per occurrence / $10M aggregate and Ridgeline Excess Insurance Company $15M follow-form excess coverage.

### C-075

Extracts mediation deadline (90 days before trial) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L611))

- **Sonnet 4.6: Pass.** The report explicitly references the mediation deadline in Section 3.4 ('Mediator / reporting'): 'MP says mediation at least 90 days before estimated trial.' It also addresses this in Issue #10 of the inconsistency register, noting that MP §§3.7 and 6.1 calculate 90 days before June 1, 2026 as approximately March 3, 2026, while MP §6.2 states February 28, 2026. The 90-days-before-trial mediation deadline is clearly extracted.
- **GPT-5.5: Pass.** The report explicitly references the mediation deadline as at least/no later than 90 days before the estimated June 1, 2026 trial date, and discusses the related date discrepancy in the Matter Plan.

### C-076

Correct matter number referenced (WC-2025-04381) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L619))

- **Sonnet 4.6: Pass.** The report clearly references the matter number WC-2025-04381 in the header table under 'Matter': 'W&C Matter WC-2025-04381'.
- **GPT-5.5: Pass.** The report references the firm's matter number as “W&C Matter WC-2025-04381” in the Matter field.
