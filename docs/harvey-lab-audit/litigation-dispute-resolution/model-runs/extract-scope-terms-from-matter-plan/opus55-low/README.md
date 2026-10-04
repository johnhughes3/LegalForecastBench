# Claude Opus 5.5 (low): Extract Scope Terms from Matter Plan — Structured Extraction Report

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-scope-terms-from-matter-plan/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 59 of 76 criteria; GPT-5.5 passed 57 of 76 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-007](#c-007) | Extracts WS-4 coordinating/primary counsel distinction | **Fail** | Pass |
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
| [C-022](#c-022) | Extracts 10-business-day reconciliation requirement at budget checkpoints | Pass | **Fail** |
| [C-023](#c-023) | Extracts total disbursement budget of $1,350,000 | Pass | Pass |
| [C-024](#c-024) | Extracts disbursement sub-allocations (at least 3 of 4 categories) | Pass | Pass |
| [C-025](#c-025) | Extracts success fee rate of 7.5% | Pass | Pass |
| [C-026](#c-026) | Extracts Target Resolution Amount of $8,500,000 and success fee calculation method | Pass | **Fail** |
| [C-027](#c-027) | Extracts settlement authority tier: Deputy GC up to $3,000,000 | Pass | Pass |
| [C-028](#c-028) | Extracts settlement authority tier: General Counsel $3,000,001 to $6,000,000 | Pass | Pass |
| [C-029](#c-029) | Extracts settlement authority tier: Pinnacle Board above $6,000,000 | Pass | Pass |
| [C-030](#c-030) | Extracts staffing for Nathaniel Voss as Lead Trial Partner (40% max) | Pass | Pass |
| [C-031](#c-031) | Extracts staffing for Katherine Sinclair as Second Chair (75% max) | Pass | Pass |
| [C-032](#c-032) | Extracts junior associate headcount cap of 3 | Pass | Pass |
| [C-033](#c-033) | Extracts junior associate monthly billing limit of 160 hours | Pass | Pass |
| [C-034](#c-034) | Extracts Elaine Marchetti authorized for WS-4 and WS-5 only | Pass | Pass |
| [C-035](#c-035) | Extracts Elaine Marchetti billed at Partner rate ($685/hour) | Pass | Pass |
| [C-036](#c-036) | Extracts contract reviewer headcount cap of 15 | Pass | Pass |
| [C-037](#c-037) | Extracts Deputy GC approval for contract reviewer wave sizing | Pass | Pass |
| [C-038](#c-038) | Extracts staffing change requirements (15 business days notice, GC consent) | Pass | Pass |
| [C-039](#c-039) | Extracts key deadline: Initial disclosures April 15, 2025 | **Fail** | **Fail** |
| [C-040](#c-040) | Extracts key deadline: Damages expert by June 30, 2025 | Pass | Pass |
| [C-041](#c-041) | Extracts key deadline: Fact discovery closes August 1, 2025 | **Fail** | **Fail** |
| [C-042](#c-042) | Extracts key deadline: Expert reports September 15, 2025 | **Fail** | **Fail** |
| [C-043](#c-043) | Extracts key deadline: Trial date June 1, 2026 (estimated) | Pass | Pass |
| [C-044](#c-044) | Extracts key deadline: Daubert motion December 1, 2025 | **Fail** | **Fail** |
| [C-045](#c-045) | Extracts key deadline: Dispositive motions February 15, 2026 | **Fail** | **Fail** |
| [C-046](#c-046) | Extracts reporting: weekly Tuesday 3 PM ET call | **Fail** | **Fail** |
| [C-047](#c-047) | Extracts reporting: monthly written status report by 5th business day | Pass | Pass |
| [C-048](#c-048) | Extracts reporting: quarterly business review (QBR) in person | **Fail** | **Fail** |
| [C-049](#c-049) | Extracts $25,000 individual disbursement pre-approval threshold | Pass | Pass |
| [C-050](#c-050) | Extracts new expert retention approval requirement | Pass | **Fail** |
| [C-051](#c-051) | Extracts 30-day termination notice period | Pass | Pass |
| [C-052](#c-052) | Extracts 15-business-day file delivery upon termination | Pass | Pass |
| [C-053](#c-053) | Extracts success fee forfeiture on termination for cause or withdrawal | **Fail** | **Fail** |
| [C-054](#c-054) | Extracts wind-down fee of 2% after $2,000,000 billed | Pass | Pass |
| [C-055](#c-055) | Extracts prospective conflicts waiver: firm may represent clients adverse to Pinnacle affiliates but not Pinnacle Industrial Holdings or Pinnacle Hydraulics Solutions directly | **Fail** | **Fail** |
| [C-056](#c-056) | Extracts conflicts waiver restriction on hydraulic equipment matters | **Fail** | **Fail** |
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
| [C-072](#c-072) | Extracts Marcus Oduya as lead paralegal | **Fail** | **Fail** |
| [C-073](#c-073) | Extracts key deadline: Rebuttal expert reports October 31, 2025 | **Fail** | **Fail** |
| [C-074](#c-074) | Extracts insurance coverage details (primary $5M/$10M, excess $15M) | Pass | Pass |
| [C-075](#c-075) | Extracts mediation deadline (90 days before trial) | Pass | Pass |
| [C-076](#c-076) | Correct matter number referenced (WC-2025-04381) | Pass | Pass |

## Judge reasoning

### C-001

Extracts WS-1: Federal MDL Defense with correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L19))

- **Sonnet 4.6: Pass.** The report identifies WS-1 as 'Federal MDL' (labeled 'WS-1 Federal MDL' in the budget table and referenced throughout) and explicitly states MDL No. 3:24-md-02987 (N.D. Ohio) in the header and in the covered matters row of the cross-document matrix. Both the work stream name and the correct case number are present.
- **GPT-5.5: Pass.** The report identifies WS-1 as the Federal MDL work stream (e.g., “WS-1 Federal MDL” and references to WS-1 covering the MDL) and includes MDL No. 3:24-md-02987 in the Northern District of Ohio in the header.

### C-002

Extracts WS-2: State Court Defense with correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L27))

- **Sonnet 4.6: Pass.** The report identifies WS-2 as 'State Court Defense' (visible in the budget tables and cross-document matrix) and references Cuyahoga County Case No. CV-24-938471 in the header/matter identification section. The case number CV-24-938471 appears in the document header under 'Covered matters' and the matter identification. WS-2 is referenced throughout as 'WS-2 State Court' with budget figures. However, I need to check if the case number is explicitly linked to WS-2. The covered matters row in the matrix shows 'MDL 3:24-md-02987 and CV-24-938471 (§1)' and WS-2 is described as 'State Court Defense' in the budget table. The case number CV-24-938471 is the Cuyahoga County case number listed in the header and in the covered matters row. WS-2 is identified as State Court Defense and the Cuyahoga County case number CV-24-938471 is present in the report. The criterion requires WS-2 to be identified and the case number CV-24-938471 to be referenced - both conditions are met.
- **GPT-5.5: Pass.** The report identifies WS-2 as the state-court work stream, including in the budget table as “WS-2 State Court,” and it references the correct Cuyahoga County Case No. CV-24-938471 in the matter heading.

### C-003

Extracts WS-3: Expert Retention and Management with named experts ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L35))

- **Sonnet 4.6: Pass.** The report identifies WS-3 (Expert Retention and Management) in the work streams table and budget reconciliation. In the Expert caps row of the cross-document matrix, it explicitly names Yeoh ($120K), Nagarajan ($185K), Renner ($95K), and a damages expert (TBD $150K). All four experts are named/referenced, satisfying the criterion of at least three.
- **GPT-5.5: Pass.** The report identifies WS-3 as Expert Management/Expert Mgmt and lists the expert caps for Yeoh ($120K), Nagarajan ($185K), Renner ($95K), and a damages expert TBD ($150K), satisfying the requirement to name/reference at least three of the four experts.

### C-004

Extracts WS-4: Regulatory Response (CPSC) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L43))

- **Sonnet 4.6: Pass.** The report extensively covers WS-4 (CPSC Regulatory Response) throughout, including in the cross-document matrix, the inconsistency register (H-2, H-11, M-1, M-14), budget reconciliation tables, and recommended actions. WS-4 is clearly identified and analyzed in detail.
- **GPT-5.5: Pass.** The report explicitly identifies WS-4 as the CPSC Regulatory Response / Regulatory Response work stream, including its addition by Revision 1 and budget.

### C-005

WS-4 origin noted as Revision 1 addendum (March 28, 2025) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L51))

- **Sonnet 4.6: Pass.** The report explicitly states in multiple places that WS-4 was added by Revision 1 (dated March 28, 2025). For example, in the Cross-Document Matrix under 'Work streams': 'WS-4 added by R1' and in the source document table R1 is dated 'Mar. 28, 2025'. Finding H-2 also states 'WS-4 is $320,000 (7.5%). R1 was agreed and signed only by Layton and Giles.' The origin of WS-4 in the Revision 1 addendum dated March 28, 2025 is clearly noted.
- **GPT-5.5: Pass.** The report explicitly identifies R1 as the Matter Plan Revision 1 addendum dated March 28, 2025 and states multiple times that WS-4 was added by R1/Revision 1.

### C-006

Extracts WS-4 sub-budget of $320,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L59))

- **Sonnet 4.6: Pass.** The report explicitly states WS-4 has a sub-budget of $320,000 in multiple places, including the executive summary ('Its $320,000 sub-budget'), the cross-document matrix (WS-4 $320K in both MP and XLS columns), finding H-2, and the budget reconciliation table in Section 5.1.
- **GPT-5.5: Pass.** The report explicitly states that WS-4 has a $320,000 sub-budget, including in the Executive Summary, matrix, inconsistency register, and budget reconciliation table.

### C-007

Extracts WS-4 coordinating/primary counsel distinction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L67))

- **Sonnet 4.6: Fail.** The report discusses WS-4 and mentions that Revision 1 calls the firm 'coordinating counsel only' with no direct CPSC contact, and that 'all substantive work is Meridian's.' However, the criterion specifically requires the report to state that Whitford & Callaway serves as coordinating counsel AND Meridian Compliance Law Group LLP as primary regulatory counsel. The report references Meridian in the context of the address discrepancy (L-4) and mentions 'Meridian's' substantive work in H-11, but never explicitly names Meridian Compliance Law Group LLP as 'primary regulatory counsel' for WS-4. The distinction is partially present but not fully articulated as required by the criterion.
- **GPT-5.5: Pass.** The report identifies WS-4 as involving Whitford & Callaway as “coordinating counsel only” and states that substantive work is Meridian’s, thereby capturing the coordinating/primary regulatory counsel distinction for WS-4 even though the exact phrase “primary regulatory counsel” is not used.

### C-008

Extracts WS-5: Insurance Coverage Coordination with $95,000 sub-budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L75))

- **Sonnet 4.6: Pass.** The agent's output explicitly identifies WS-5 as the Insurance Coverage Coordination work stream with a $95,000 sub-budget. This appears in the cross-document matrix table (WS-5 Insurance: $95,000 in MP, $95,000 in XLS), in the budget reconciliation table (WS-5 Insurance $95,000 across MP, XLS Fee tab, XLS Forecast column sum, and XLS Forecast stated TOTAL), and in finding H-10 which discusses WS-5's carrier communication scope.
- **GPT-5.5: Pass.** The report identifies WS-5 as Insurance/Insurance Coverage Coordination and lists its sub-budget as $95,000 in the cross-document matrix and budget reconciliation table.

### C-009

Extracts WS-5 liaison with Graystone Risk Advisors or relevant carriers ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L83))

- **Sonnet 4.6: Pass.** The report mentions Fortitude and Ridgeline in connection with WS-5 (insurance work stream) multiple times: in the cross-document matrix row for 'Insurance' it states 'WS-5 authorizes direct communication with carriers' and lists 'Fortitude $5M / $10M; Ridgeline $15M follow-form', and in finding H-10 it explicitly states 'The MP authorizes direct communication with Fortitude and Ridgeline on all matters, including coverage positions.' However, Graystone Risk Advisors is never mentioned anywhere in the report. The criterion requires mention of Graystone Risk Advisors and/or the relevant carriers. Since the carriers (Fortitude and Ridgeline) are mentioned in connection with WS-5, the criterion is satisfied.
- **GPT-5.5: Pass.** The report repeatedly identifies WS-5 as involving insurance/carrier communications, including direct communication with Fortitude and Ridgeline and a finding on WS-5 carrier contact. This satisfies the requirement to mention liaison with relevant carriers in connection with WS-5.

### C-010

Extracts WS-6: Document Review and E-Discovery with vendor restriction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L91))

- **Sonnet 4.6: Pass.** The report explicitly identifies WS-6 as 'E-Discovery' in multiple places (the fee allocation table, the budget reconciliation, and the cross-document matrix). It also clearly states that 'Precept Analytics only, absent DGC approval' is the authorized e-discovery vendor restriction in the 'E-discovery vendor' row of the cross-document matrix, noting the same across EL, MP, R1, OCG, and XLS. The disbursement budget table also lists 'E-discovery (Precept)' with its budget amount. Both the work stream identification and the vendor restriction with approval requirement are present.
- **GPT-5.5: Pass.** The report identifies WS-6 as the e-discovery/document review work stream in the budget and related findings, and it separately states that Precept Analytics is the only authorized e-discovery vendor absent DGC approval, noting the vendor approval restriction for alternatives.

### C-011

Extracts WS-7: Settlement Strategy and Mediation with pre-approved mediators ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L99))

- **Sonnet 4.6: Pass.** The report identifies WS-7 as 'Settlement Strategy and Mediation' (and notes the R1 name variant 'Settlement Evaluation and Mediation Preparation') and explicitly lists all three pre-approved mediators: Fitzsimmons, Delmonico, and Tran in the mediators/deadline row of the cross-document matrix. This satisfies the criterion of identifying WS-7 and naming at least two of the three pre-approved mediators.
- **GPT-5.5: Pass.** The report identifies WS-7 as the settlement/mediation work stream and lists the pre-approved mediators in the Mediators/deadline row: Fitzsimmons, Delmonico, and Tran, satisfying the requirement to name at least two of the three mediators.

### C-012

Extracts scope exclusions EX-1 through EX-6 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L107))

- **Sonnet 4.6: Pass.** The report explicitly lists all six exclusions in the cross-document matrix under 'Exclusions EX-1 to EX-6': EX-1 class action, EX-2 appellate, EX-3 affirmative claims, EX-4 recall, EX-5 lobbying, EX-6 non-HX-9000 unless consolidated. All six are present, satisfying the criterion of >=5.
- **GPT-5.5: Pass.** The report expressly lists all six exclusions in the cross-document matrix: EX-1 class action, EX-2 appellate, EX-3 affirmative claims, EX-4 recall, EX-5 lobbying, and EX-6 non-HX-9000 claims unless consolidated/part of covered proceedings. It therefore satisfies the requirement of at least five exclusions.

### C-013

Extracts EX-6 exception for MDL consolidation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L115))

- **Sonnet 4.6: Pass.** The report explicitly discusses EX-6 in multiple places. In the Cross-Document Matrix, EX-6 is described as 'non-HX-9000 unless consolidated "or otherwise become part of the proceedings"'. In Finding H-6, the report states: 'The EL carve-back covers claims consolidated into the MDL "or [that] otherwise become part of the proceedings covered by this letter"'. This clearly notes that EX-6 contains an exception for claims consolidated into the MDL.
- **GPT-5.5: Pass.** The report explicitly states that EX-6 excludes non-HX-9000 claims unless they are consolidated into the MDL or otherwise become part of the covered proceedings, including noting that EX-6 'carves consolidated MDL claims back in.'

### C-014

Extracts blended hourly rates for rate categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L123))

- **Sonnet 4.6: Pass.** The agent's output in the Cross-Document Matrix under 'Blended rates' states: 'Partner $685 / Senior Associate $475 / Junior Associate $340 / Paralegal $195 (Ex. A)'. All four rates are correctly stated, satisfying the criterion of >=3 correct rates.
- **GPT-5.5: Pass.** The output explicitly lists all four blended hourly rates correctly: Partner $685/hour, Senior Associate $475/hour, Junior Associate $340/hour, and Paralegal $195/hour.

### C-015

Extracts contract reviewer rate of $55/hour ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L131))

- **Sonnet 4.6: Pass.** The report explicitly states in the Contract reviewers row of the cross-document matrix: '$55/hr; separate line item; up to 15; each wave approved by DGC' under the EL column, and notes it is a 'separate line item' outside the blended rates. This satisfies both parts of the criterion: the $55/hour rate is stated and it is noted as separate from (not counted toward) the blended rate structure.
- **GPT-5.5: Pass.** The report expressly states contract reviewers are billed at $55/hr and notes they are a separate line item outside the blended rates, with further discussion of classification issues.

### C-016

Extracts monthly fee cap of $285,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L139))

- **Sonnet 4.6: Pass.** The report explicitly states the monthly fee cap of $285,000 in the cross-document matrix under 'Monthly fee cap': '$285,000; overage up to 10% ($313,500) approvable retroactively by DGC within 15 business days of invoice'. It is also referenced in the inconsistency register under H-5 and in Section 5.3 where the overage ceiling is computed as 10% = $28,500 (implying the cap is $285,000).
- **GPT-5.5: Pass.** The report explicitly states the monthly fee cap is $285,000 in the cross-document matrix and discusses related overage rules.

### C-017

Extracts retroactive overage approval up to 10% by Deputy GC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L147))

- **Sonnet 4.6: Pass.** The report explicitly states in the Monthly fee cap row of the cross-document matrix: '$285,000; overage up to 10% ($313,500) approvable retroactively by DGC within 15 business days of invoice' and in finding H-5 it again states 'EL: DGC may approve overages up to 10% retroactively within 15 business days of invoice submission'. Both the cap amount ($285,000), the ceiling ($313,500), the 10% threshold, and the retroactive Deputy GC approval are clearly present.
- **GPT-5.5: Pass.** The report expressly states under the monthly fee cap that the $285,000 cap allows overages up to 10% ($313,500) to be approved retroactively by the Deputy GC, including the timing details.

### C-018

Extracts General Counsel approval required for overages exceeding 10% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L155))

- **Sonnet 4.6: Pass.** The report explicitly states in the Monthly fee cap row of the cross-document matrix: '">10% needs GC prior approval; unapproved excess credited" and in finding H-5: "EL: DGC may approve overages up to 10% retroactively within 15 business days of invoice submission; any unapproved excess becomes a credit." and "any overage up to 10% (\ $313,500) approvable retroactively by DGC within 15 business days of invoice; >10% needs GC prior approval". This clearly states that overages exceeding 10% above the $285,000 monthly cap require General Counsel (GC) prior approval.
- **GPT-5.5: Pass.** The report explicitly states in the Monthly fee cap row that the $285,000 cap allows overages up to 10% with DGC retroactive approval, but overages greater than 10% require General Counsel prior approval.

### C-019

Extracts aggregate fee budget of $4,250,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L163))

- **Sonnet 4.6: Pass.** The report clearly states the Aggregate Fee Budget (AFB) is $4,250,000 through end of trial, excluding success fee, expert fees, and disbursements. This appears in the cross-document matrix row 'Aggregate Fee Budget (AFB)' and is confirmed in multiple sections including the executive summary, budget reconciliation, and Section 5.3.
- **GPT-5.5: Pass.** The report explicitly states the Aggregate Fee Budget is $4,250,000 through the end of trial and notes that it excludes the success fee, expert fees, and disbursements.

### C-020

Extracts 50% budget checkpoint at $2,125,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L171))

- **Sonnet 4.6: Pass.** The report explicitly mentions the 50% budget checkpoint at $2,125,000 in multiple places: in the cross-document matrix under 'Budget checkpoints' ("50% $2,125,000; 75% $3,187,500"), in Section 5.3 ("50% and 75% checkpoints = $2,125,000 and $3,187,500"), and in the XLS row noting "forecast reaches 50% in Oct. 2025".
- **GPT-5.5: Pass.** The report explicitly identifies the 50% budget checkpoint as $2,125,000 in the cross-document matrix and again in the figures checked section.

### C-021

Extracts 75% budget checkpoint at $3,187,500 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L179))

- **Sonnet 4.6: Pass.** The report explicitly states in Section 5.3: '50% and 75% checkpoints = $2,125,000 and $3,187,500' and also in the Budget checkpoints row of the cross-document matrix: '50% $2,125,000; 75% $3,187,500; report to DGC within 10 business days'. The 75% budget checkpoint at $3,187,500 is clearly identified.
- **GPT-5.5: Pass.** The report explicitly identifies the 75% budget checkpoint as $3,187,500 in the cross-document matrix and again in the budget reconciliation section.

### C-022

Extracts 10-business-day reconciliation requirement at budget checkpoints ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L187))

- **Sonnet 4.6: Pass.** The report explicitly states in the Budget checkpoints row of the cross-document matrix: '50% $2,125,000; 75% $3,187,500; report to DGC within 10 business days'. This directly captures the 10-business-day reconciliation/reporting requirement at each budget checkpoint.
- **GPT-5.5: Fail.** The report identifies the 50% and 75% budget checkpoints and says to “report to DGC within 10 business days,” but it does not state that a written budget reconciliation is required within 10 business days of reaching each checkpoint.

### C-023

Extracts total disbursement budget of $1,350,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L195))

- **Sonnet 4.6: Pass.** The report explicitly states the total disbursement budget of $1,350,000 in multiple places, including the cross-document matrix row for 'Disbursement budget' (EL §4.1: '$1,350,000: experts $780K; Precept $340K; travel $155K; court reporting $75K'), the disbursement budget reconciliation table in Section 5.2, and the executive summary noting the $20,000 gap between $1,350,000 and $1,330,000.
- **GPT-5.5: Pass.** The report explicitly states the disbursement budget is $1,350,000 in multiple places, including the executive summary, cross-document matrix, and disbursement budget table.

### C-024

Extracts disbursement sub-allocations (at least 3 of 4 categories) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L203))

- **Sonnet 4.6: Pass.** The report's Section 5.2 (Disbursement budget table) lists all four sub-categories: Expert witness fees ($780,000), E-discovery (Precept) ($340,000), Travel and deposition ($155,000), and Court reporting ($75,000). All four are present, which satisfies the requirement of at least 3 of 4.
- **GPT-5.5: Pass.** The report lists all four required disbursement sub-categories: expert witness fees ($780,000, noting discrepancies), e-discovery/Precept costs ($340,000), travel and deposition costs ($155,000), and court reporting/transcripts ($75,000).

### C-025

Extracts success fee rate of 7.5% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L211))

- **Sonnet 4.6: Pass.** The report explicitly states in the Cross-Document Matrix under 'Success fee': '7.5% × ($8.5M − "Actual Aggregate Payments")'. This clearly identifies the success fee rate as 7.5% of savings (the difference between the target and actual aggregate payments).
- **GPT-5.5: Pass.** The report explicitly states the success fee as “7.5% × ($8.5M − Actual Aggregate Payments)” and includes a checked example using 7.5%, satisfying the requirement to extract the 7.5% success fee rate.

### C-026

Extracts Target Resolution Amount of $8,500,000 and success fee calculation method ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L219))

- **Sonnet 4.6: Pass.** The report states the success fee is '7.5% × ($8.5M − "Actual Aggregate Payments")' in the cross-document matrix row for 'Success fee'. This captures both the $8,500,000 Target Resolution Amount and the calculation method (percentage of the difference between $8.5M and actual aggregate payments). The report also notes the term 'aggregate payments' is undefined and disputed. The criterion requires the report to state the success fee is calculated as a percentage of the difference between $8,500,000 and the actual aggregate resolution amount, and triggered only if aggregate payments are at or below $8,500,000. The formula '7.5% × ($8.5M − Actual Aggregate Payments)' implicitly means it is only positive (and thus triggered) when aggregate payments are below $8.5M. The $8,500,000 threshold and calculation method are both present.
- **GPT-5.5: Fail.** The report identifies the $8,500,000 Target Resolution Amount and states the success fee formula as 7.5% × ($8.5M − Actual Aggregate Payments). However, it does not expressly state that the success fee is triggered only if aggregate payments are at or below $8,500,000.

### C-027

Extracts settlement authority tier: Deputy GC up to $3,000,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L227))

- **Sonnet 4.6: Pass.** The report's cross-document matrix under 'Settlement authority' states: 'DGC ≤$3M; GC $3,000,001--$6M; Board >$6M; offers received passed to DGC within 24 hrs'. This clearly identifies the Deputy GC (DGC) as having settlement authority up to $3,000,000, which satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly states in the settlement authority row that the Deputy GC has authority “≤$3M,” i.e., up to $3,000,000.

### C-028

Extracts settlement authority tier: General Counsel $3,000,001 to $6,000,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L235))

- **Sonnet 4.6: Pass.** The report explicitly states in the Settlement authority row of the cross-document matrix: 'DGC ≤$3M; GC $3,000,001--$6M; Board >$6M', which correctly identifies the General Counsel's settlement authority tier as $3,000,001 to $6,000,000.
- **GPT-5.5: Pass.** The report explicitly states in the Settlement authority row that the General Counsel has authority for "$3,000,001--$6M," which matches the required tier.

### C-029

Extracts settlement authority tier: Pinnacle Board above $6,000,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L243))

- **Sonnet 4.6: Pass.** The report's cross-document matrix under 'Settlement authority' states: 'DGC ≤$3M; GC $3,000,001--$6M; Board >$6M; offers received passed to DGC within 24 hrs'. This clearly identifies the Pinnacle Board as having settlement authority above $6,000,000.
- **GPT-5.5: Pass.** The report explicitly states in the settlement authority row that authority is DGC ≤ $3M, GC $3,000,001–$6M, and Board > $6M, which matches Pinnacle Board authority above $6,000,000.

### C-030

Extracts staffing for Nathaniel Voss as Lead Trial Partner (40% max) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L251))

- **Sonnet 4.6: Pass.** The report explicitly identifies Nathaniel Voss as Lead Trial Partner with a maximum 40% time allocation in the staffing matrix row ('Lead Trial Partner (Voss): Max 40% of time unless GC approves; replacement needs GC consent and 15 business days' notice') and again in finding M-6 ('EL: the GC's prior approval is required' for adjusting the 40% cap). Both the role and the cap are clearly present.
- **GPT-5.5: Pass.** The report includes a staffing row stating “Lead Trial Partner (Voss)” and specifies “Max 40% of time unless GC approves,” satisfying the requirement to identify Voss as Lead Trial Partner with a 40% cap.

### C-031

Extracts staffing for Katherine Sinclair as Second Chair (75% max) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L259))

- **Sonnet 4.6: Pass.** The report's cross-document matrix includes a row for 'Second Chair (Sinclair)' that states 'Year 7 Senior Associate; up to 75%' in the EL column, satisfying the criterion's requirement to identify Sinclair as Second Chair with the 75% cap. The 'Katherine' first name is used in the row header as 'Sinclair' but the full name appears implicitly; the criterion asks for identification of Katherine/Kate Sinclair as Second Chair with 75% max, and the report does identify her by surname with Year 7 Senior Associate designation and up to 75% allocation.
- **GPT-5.5: Pass.** The report includes a staffing matrix row for “Second Chair (Sinclair)” stating “Year 7 Senior Associate; up to 75%,” satisfying the requirement to identify Sinclair as Second Chair with the 75% cap.

### C-032

Extracts junior associate headcount cap of 3 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L267))

- **Sonnet 4.6: Pass.** The report explicitly states in the Cross-Document Matrix under 'Associates / paralegals': 'Up to 3 junior associates, 160 hrs/month cap; up to 2 paralegals; changes notified to DGC' in the EL column. This clearly captures the junior associate headcount cap of 3.
- **GPT-5.5: Pass.** The report expressly states in the staffing matrix that the EL authorizes “Up to 3 junior associates,” satisfying the required headcount cap extraction.

### C-033

Extracts junior associate monthly billing limit of 160 hours ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L275))

- **Sonnet 4.6: Pass.** The report explicitly states in the staffing row of the cross-document matrix: 'Up to 3 junior associates, 160 hrs/month cap; up to 2 paralegals; changes notified to DGC' under the EL column. This directly captures the 160-hour monthly billing limit for junior associates. The criterion asks whether the report states individual junior associate billing must not exceed 160 hours/month; the report does state this limit, though it attributes it to the EL rather than explicitly mentioning 'Billing Partner approval' for overages. However, the criterion's PASS condition is met as the 160-hour monthly limit is present in the report.
- **GPT-5.5: Pass.** The report includes the junior associate monthly billing limit in the staffing matrix: “Up to 3 junior associates, 160 hrs/month cap.” Although it does not expressly mention the Billing Partner approval qualifier, the 160-hour monthly limit is present.

### C-034

Extracts Elaine Marchetti authorized for WS-4 and WS-5 only ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L283))

- **Sonnet 4.6: Pass.** The report explicitly states in the cross-document matrix under 'Of Counsel (Marchetti)' that her authorization is 'WS-4 and WS-5 only' (per the MP column), and this is corroborated in the XLS column as well. The report identifies Marchetti as Of Counsel and clearly states her work stream limitation to WS-4 and WS-5.
- **GPT-5.5: Pass.** The report includes an 'Of Counsel (Marchetti)' row stating that Marchetti is authorized for 'WS-4 and WS-5 only' in the Matter Plan, satisfying the required work-stream limitation.

### C-035

Extracts Elaine Marchetti billed at Partner rate ($685/hour) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L291))

- **Sonnet 4.6: Pass.** The report explicitly states in the cross-document matrix under 'Blended rates' that Marchetti bills at the Partner rate, and the Partner rate is listed as $685. Additionally, under finding M-7, the report states 'Marchetti bills at the Partner rate'. The $685/hour rate is specified in the blended rates row of the matrix.
- **GPT-5.5: Pass.** The report lists the blended Partner rate as $685/hour and specifically notes that Marchetti is billed at the Partner rate, including in the staffing/billing rows and related findings.

### C-036

Extracts contract reviewer headcount cap of 15 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L299))

- **Sonnet 4.6: Pass.** The report explicitly states in the Cross-Document Matrix under 'Contract reviewers': '$55/hr; separate line item; up to 15; each wave approved by DGC'. This clearly captures the 15-person headcount cap for contract reviewers.
- **GPT-5.5: Pass.** The report expressly states in the Contract reviewers row that contract reviewers are authorized at $55/hr, as a separate line item, 'up to 15,' with each wave approved by the DGC.

### C-037

Extracts Deputy GC approval for contract reviewer wave sizing ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L307))

- **Sonnet 4.6: Pass.** The criterion requires the report to state that the exact number of contract reviewers per wave requires Deputy GC approval. The report mentions in the cross-document matrix that the EL specifies 'up to 15; each wave approved by DGC' for contract reviewers. This states that each wave is approved by the DGC (Deputy GC), and the number per wave ('up to 15') is specified. The report does capture that wave-level DGC approval is required and references the headcount limit. However, the criterion asks specifically whether the report states that the 'exact number of contract reviewers per wave requires Deputy GC approval.' The EL entry says 'up to 15; each wave approved by DGC,' which indicates wave-level DGC approval exists but frames it as headcount approval per wave rather than explicitly stating the exact number per wave needs DGC approval. The finding H-8 notes the EL 'approves only headcount per review wave' and the OCG requires individual name approval. The report does state DGC approval is required per wave with a headcount limit, which satisfies the criterion's requirement that the exact number per wave requires Deputy GC approval.
- **GPT-5.5: Pass.** The report includes the contract reviewer term: “$55/hr; separate line item; up to 15; each wave approved by DGC,” which captures that Deputy GC approval is required for contract reviewer waves and their sizing framework.

### C-038

Extracts staffing change requirements (15 business days notice, GC consent) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L315))

- **Sonnet 4.6: Pass.** The report explicitly states in the 'Lead Trial Partner (Voss)' row of the cross-document matrix: 'Max 40% of time unless GC approves; replacement needs GC consent and 15 business days' notice.' This directly captures the requirement that replacing the Lead Trial Partner requires General Counsel written consent with 15 business days' notice. The criterion is satisfied.
- **GPT-5.5: Pass.** The report’s staffing matrix states that the Lead Trial Partner’s replacement “needs GC consent and 15 business days’ notice.” Although it does not use the word “written” in that specific line, it captures the required GC consent and 15-business-day notice for replacing the Lead Trial Partner.

### C-039

Extracts key deadline: Initial disclosures April 15, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L323))

- **Sonnet 4.6: Fail.** The agent's output does not mention April 15, 2025 as a deadline for initial disclosures in the MDL anywhere in the report. The report covers many scope terms, budget figures, and inconsistencies, but this specific deadline is absent.
- **GPT-5.5: Fail.** The report does not list April 15, 2025 as the deadline for initial disclosures in the MDL; the date and deadline appear to be missing.

### C-040

Extracts key deadline: Damages expert by June 30, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L331))

- **Sonnet 4.6: Pass.** The report mentions in the Expert caps row of the cross-document matrix: 'damages TBD $150K (by June 30, 2025)' under the MP column, explicitly identifying June 30, 2025 as the deadline to identify/cap the damages expert.
- **GPT-5.5: Pass.** The report includes the damages expert deadline in the Expert caps row: "damages TBD $150K (by June 30, 2025)."

### C-041

Extracts key deadline: Fact discovery closes August 1, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L339))

- **Sonnet 4.6: Fail.** The agent's output does not mention August 1, 2025 as the close of fact discovery in the MDL anywhere in the report. The report covers many scope terms, deadlines, and findings, but this specific date is absent.
- **GPT-5.5: Fail.** The report does not list August 1, 2025 as the close of fact discovery in the MDL; that deadline is missing.

### C-042

Extracts key deadline: Expert reports September 15, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L347))

- **Sonnet 4.6: Fail.** The agent's output does not mention September 15, 2025 as a deadline for expert reports anywhere in the document. The report discusses expert caps, expert budgets, and a damages expert TBD deadline of June 30, 2025, but the specific date of September 15, 2025 for expert reports is absent.
- **GPT-5.5: Fail.** The report discusses expert budgets and expert-related procedures, but it does not list September 15, 2025 as the deadline for expert reports.

### C-043

Extracts key deadline: Trial date June 1, 2026 (estimated) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L355))

- **Sonnet 4.6: Pass.** The agent's output mentions June 1, 2026 in the context of the mediation completion deadline: 'completion 90 days before trial: Mar. 3, 2026 (narrative) vs Feb. 28, 2026 (chart)' and in finding M-11: 'The narrative says Mar. 3, 2026, which is correct (90 days before June 1, 2026).' This explicitly identifies June 1, 2026 as the trial date, satisfying the criterion.
- **GPT-5.5: Pass.** The report includes June 1, 2026 in the mediation deadline analysis, stating that March 3, 2026 is 90 days before June 1, 2026, thereby identifying the trial date.

### C-044

Extracts key deadline: Daubert motion December 1, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L363))

- **Sonnet 4.6: Fail.** The agent's output does not mention December 1, 2025 as a Daubert motion filing deadline anywhere in the report. The report covers many dates and deadlines but this specific deadline is absent.
- **GPT-5.5: Fail.** The report does not mention a Daubert motion filing deadline, and December 1, 2025 does not appear as such a deadline.

### C-045

Extracts key deadline: Dispositive motions February 15, 2026 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L371))

- **Sonnet 4.6: Fail.** The agent's output does not mention February 15, 2026 as a dispositive motion filing deadline anywhere in the report. The report references various dates (March 28, 2025 for R1, June 1, 2026 as trial date, March 3/February 28, 2026 for mediation completion, October 2025 and February 2026 for budget checkpoints), but the specific date of February 15, 2026 for dispositive motions is not listed anywhere in the document.
- **GPT-5.5: Fail.** The report does not list February 15, 2026 as the dispositive motion filing deadline; that specific deadline is missing.

### C-046

Extracts reporting: weekly Tuesday 3 PM ET call ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L379))

- **Sonnet 4.6: Fail.** The agent's output mentions 'Weekly Tuesday 3pm ET calls' in the Reporting row of the cross-document matrix, but it does not specify that these calls are between Nate Voss and Ronan Giles. The criterion requires the report to state that the weekly call is between those two specific individuals. The output only notes the time/day of the call without identifying the participants as Voss and Giles.
- **GPT-5.5: Fail.** The report mentions “Weekly Tuesday 3pm ET calls,” but it does not state that the weekly Tuesday 3:00 PM ET status call is between Nate Voss and Ronan Giles.

### C-047

Extracts reporting: monthly written status report by 5th business day ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L387))

- **Sonnet 4.6: Pass.** The agent's output explicitly states in the Reporting row of the cross-document matrix: 'Weekly Tuesday 3pm ET calls; monthly report by 5th business day; QBR by May 15, 2025 (GC and CFO; Layton and Voss attend)'. This clearly captures the monthly written status report due by the 5th business day obligation.
- **GPT-5.5: Pass.** The report includes the reporting obligation in the cross-document matrix, stating: “monthly report by 5th business day,” which satisfies the requirement to extract that monthly written status reports are due by the 5th business day.

### C-048

Extracts reporting: quarterly business review (QBR) in person ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L395))

- **Sonnet 4.6: Fail.** The criterion requires the report to state that QBR presentations are required to Meg Stanhope (GC) and Jonas Whitmore (CFO) in person at Pinnacle HQ. The agent's output mentions QBRs in the Reporting row of the cross-document matrix ('QBR by May 15, 2025 (GC and CFO; Layton and Voss attend)') and in finding M-13, but it does not specify that the QBRs are in person at Pinnacle HQ, nor does it name Meg Stanhope or Jonas Whitmore in connection with the QBR obligation. The criterion specifically requires these details to be present.
- **GPT-5.5: Fail.** The report mentions QBRs involving the GC and CFO, but it does not state that QBR presentations are required to Meg Stanhope and Jonas Whitmore in person at Pinnacle HQ. The specific in-person HQ obligation is missing.

### C-049

Extracts $25,000 individual disbursement pre-approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L403))

- **Sonnet 4.6: Pass.** The report explicitly states in the cross-document matrix under 'Disbursement approval': '>$25K needs DGC pre-approval; reallocations >$25K need DGC approval' and in finding M-9 it discusses the '$10K–$25K disbursement notice' and states 'The MP says disbursements under $25K need no pre-approval'. The $25,000 individual disbursement pre-approval threshold requiring Deputy GC approval is clearly extracted and present in the report.
- **GPT-5.5: Pass.** The report explicitly states in the cross-document matrix that disbursements over $25,000 need DGC pre-approval, and repeats this in related findings.

### C-050

Extracts new expert retention approval requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L411))

- **Sonnet 4.6: Pass.** The report explicitly states in the Expert caps row of the cross-document matrix: 'Non-MP experts require GC approval (§4.2)' under the EL column. Additionally, finding H-7 references expert caps and the disbursement budget, and finding L-10 notes that 'The OCGs add 15 business days' advance notice, a CV, and certification of expert invoices.' The matrix also notes under OCG: 'Individual caps required; new expert needs GC approval, 15 business days' advance notice and CV (§5.3).' The requirement for GC approval for new experts not listed in the Matter Plan is clearly stated, along with the written budget estimate aspect (the named experts have individual caps listed). This satisfies the criterion that retention of any new expert witness not listed in the Matter Plan requires General Counsel approval with a written budget estimate.
- **GPT-5.5: Fail.** The report notes that non-Matter Plan/new experts require General Counsel approval, but it does not state the required written budget estimate for retaining any new expert witness not listed in the Matter Plan.

### C-051

Extracts 30-day termination notice period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L419))

- **Sonnet 4.6: Pass.** The report explicitly states '30 days' notice' in the Termination row of the Cross-Document Matrix (Section 3) and also references '30 days' notice' in the Inconsistency Register under M-16/M-17 analysis. The termination section states: 'EL §9: 30 days' notice; files within 15 business days; accrued fees paid in 45 days...' and the OCG entry notes '30 days default; files within 30 business days if no timeframe set.' This clearly satisfies the criterion of stating that either party may terminate on 30 days' written notice.
- **GPT-5.5: Pass.** The report includes the termination term and states “30 days’ notice” in the termination row, so the 30-day termination notice period is not missing.

### C-052

Extracts 15-business-day file delivery upon termination ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L427))

- **Sonnet 4.6: Pass.** The report explicitly states in the Termination row of the cross-document matrix: 'files within 15 business days' (under the EL column), and in finding M-16/M-17 the termination terms are discussed. The matrix entry for Termination reads: '30 days' notice; files within 15 business days; accrued fees paid in 45 days...' This clearly captures the 15-business-day file delivery requirement upon termination.
- **GPT-5.5: Pass.** The report’s Termination row expressly states that files must be delivered “within 15 business days” upon termination.

### C-053

Extracts success fee forfeiture on termination for cause or withdrawal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L435))

- **Sonnet 4.6: Fail.** The report discusses termination and success fee provisions in several places (the cross-document matrix row on 'Termination', finding M-17, and Section 6 action item 2), but it only addresses the success fee treatment on termination *without cause* (pro rata vs. 'remains available'). It never states that the success fee is forfeited when the firm is terminated *for cause* or voluntarily withdraws. The forfeiture-on-cause/withdrawal provision is absent from the report.
- **GPT-5.5: Fail.** The report includes a generic termination entry saying the success fee is “forfeited or pro-rated,” but it does not state the specific provision that the success fee is forfeited if the firm is terminated for cause or voluntarily withdraws.

### C-054

Extracts wind-down fee of 2% after $2,000,000 billed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L443))

- **Sonnet 4.6: Pass.** The report explicitly mentions the wind-down fee in the termination row of the cross-document matrix: 'wind-down fee 2% if billed "in excess of" $2M' (EL) vs '$2,000,000 or more' (MP). Finding M-16 also addresses this discrepancy. Additionally, Section 5.3 confirms the wind-down fee example calculation: '2% × $2.5M = $50,000'. The report clearly states the 2% wind-down fee and the $2,000,000 threshold, satisfying the criterion.
- **GPT-5.5: Pass.** The report identifies the wind-down fee term multiple times, including that the EL provides a wind-down fee of 2% if fees billed are “in excess of” $2,000,000, and gives an example of 2% × $2.5M = $50,000. Although the termination-without-cause context is not stated in the exact phrasing requested, the required 2% fee and $2,000,000 threshold are present.

### C-055

Extracts prospective conflicts waiver: firm may represent clients adverse to Pinnacle affiliates but not Pinnacle Industrial Holdings or Pinnacle Hydraulics Solutions directly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L451))

- **Sonnet 4.6: Fail.** The agent's output is a detailed scope extraction report covering 42 inconsistencies across six documents. It addresses parties, work streams, exclusions, budgets, rates, staffing, approval thresholds, reporting, success fees, termination, insurance, and document hierarchy. However, nowhere in the report is there any mention of a prospective conflicts waiver, nor any description of a limitation on the firm representing clients adverse to Pinnacle affiliates (but not Pinnacle Industrial Holdings or Pinnacle Hydraulics Solutions directly). This specific term is entirely absent from the report.
- **GPT-5.5: Fail.** The report does not describe any prospective conflicts waiver allowing the firm to represent clients adverse to Pinnacle affiliates while prohibiting direct adversity to Pinnacle Industrial Holdings or Pinnacle Hydraulics Solutions in unrelated matters. The core waiver limitation is absent.

### C-056

Extracts conflicts waiver restriction on hydraulic equipment matters ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L459))

- **Sonnet 4.6: Fail.** The agent's output is a detailed scope extraction report covering 42 inconsistencies across six documents. It addresses parties, work streams, exclusions, budgets, rates, staffing, approval thresholds, reporting, success fees, termination, insurance, and document hierarchy. However, nowhere in the report is there any mention of a prospective conflicts waiver or any restriction on that waiver relating to hydraulic equipment matters (of any manufacturer). The criterion requires the report to note that the prospective conflicts waiver does not extend to matters involving hydraulic equipment of any manufacturer. This specific restriction is entirely absent from the agent's output.
- **GPT-5.5: Fail.** The report does not mention any prospective conflicts waiver, nor does it note that such a waiver does not extend to matters involving hydraulic equipment of any manufacturer.

### C-057

Extracts conflicts waiver prohibition on use of confidential information ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L467))

- **Sonnet 4.6: Fail.** The agent's report is extensive and covers 42 inconsistencies across many scope terms, but it does not mention any prospective conflicts waiver or the condition that such a waiver is conditioned on no confidential information being used. This specific condition is entirely absent from the report.
- **GPT-5.5: Fail.** The report does not mention any prospective conflicts waiver, nor does it state that such a waiver is conditioned on no confidential information being used.

### C-058

ISSUE_001: Flags $780,000 vs. $760,000 expert budget discrepancy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L475))

- **Sonnet 4.6: Pass.** The agent's output clearly identifies the $780,000 vs $760,000 expert budget discrepancy in multiple places. In the Executive Summary, it states: 'The expert and disbursement budget has a $20,000 gap. The EL and MP §3.3 set expert fees at $780,000 (rebuttal reserve $230,000). MP §7.2 and the XLS use $760,000 (reserve $210,000).' This is also flagged as finding H-7 (HIGH severity) in the Inconsistency and Gap Register, and detailed in Section 5.2 (Disbursement budget reconciliation table). The recommended action is to correct MP §7.2 and the XLS to $780,000/$1,350,000 with a $230,000 rebuttal reserve. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The report explicitly identifies the expert/disbursement budget discrepancy: $780,000 in the EL/MP narrative based on $550K named experts plus $230K rebuttal reserve versus $760,000 in MP §7.2/XLS based on a $210K reserve, creating a $20,000 gap. It flags this as H-7 and recommends correcting the documents, so it satisfies the criterion.

### C-059

ISSUE_002: Flags WS-4 $320K sub-budget exceeds 5% threshold ($212,500) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L483))

- **Sonnet 4.6: Pass.** The agent's output explicitly identifies in finding H-2 that WS-4's $320,000 sub-budget exceeds the 5% threshold of $212,500 (5% of $4,250,000 AFB), that this requires GC prior written re-approval per EL §§1, 7, 12(a), and that Revision 1 was signed only by Layton and Giles (Billing Partner and Deputy GC) without GC approval. This is also highlighted in the Executive Summary and the cross-document matrix. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The report expressly flags WS-4/CPSC as a $320,000 new work stream exceeding the 5% of AFB threshold ($212,500), states that the Engagement Letter requires GC prior written re-approval for such work, and notes Revision 1 was signed only by Layton/Giles without GC approval and only permits MP amendments at or below 5%. This adequately identifies the conflict between Revision 1 and the Engagement Letter threshold.

### C-060

ISSUE_003: Flags Of Counsel rate not defined in rate schedule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L491))

- **Sonnet 4.6: Fail.** The report mentions in the blended rates row that Marchetti bills at the Partner rate (M-7 references 'Marchetti bills at the Partner rate'), and the blended rates row notes 'Partner $685 / Senior Associate $475 / Junior Associate $340 / Paralegal $195 (Ex. A)' with 'Marchetti at Partner rate' under R1. Finding M-7 explicitly states 'Marchetti bills at the Partner rate, but the MP treats Of Counsel substitutions as notice-only. A substitute billing at the Partner rate is arguably a "new partner" addition requiring GC consent.' However, the criterion specifically asks whether the report flags that the rate schedule does not include an 'Of Counsel' category at all — creating ambiguity about whether billing Marchetti at the Partner rate is appropriate given the schedule only defines Partner, Senior Associate, Junior Associate, and Paralegal categories. The report notes Marchetti bills at the Partner rate and flags the substitution/approval issue, but does not explicitly flag that 'Of Counsel' is not a defined category in the rate schedule, leaving a gap in the rate schedule itself. The issue flagged (M-7) is about approval requirements for substitution, not about the missing Of Counsel category in the rate schedule. This is a distinct gap from what the criterion requires. The criterion requires flagging that the rate schedule lacks an Of Counsel category, creating ambiguity. The report does not make this specific observation.
- **GPT-5.5: Fail.** The report notes that Elaine Marchetti is Of Counsel and bills at the Partner rate, and it lists the rate schedule categories as Partner/Senior Associate/Junior Associate/Paralegal. However, it does not flag the specific gap that the engagement letter’s rate schedule lacks an Of Counsel category, creating ambiguity or a potential billing dispute for Marchetti’s rate. The related finding M-7 concerns substitution/approval, not the undefined Of Counsel rate category.

### C-061

ISSUE_004: Flags contract reviewer rate missing from approved rate schedule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L499))

- **Sonnet 4.6: Fail.** The criterion requires the report to flag that the $55/hour contract reviewer rate is not listed in the engagement letter's rate schedule, and that OCG v6.2 requires all timekeepers to be listed in the approved rate schedule and approved by the Deputy GC prior to billing. The agent's report does address contract reviewers in multiple places (H-8, M-4, and the cross-document matrix row for 'Contract reviewers'). However, the report focuses on: (1) the classification issue (fee vs. disbursement), (2) the lack of a budget line, (3) the OCG requirement for individual name approval, and (4) the wave-by-wave DGC approval. The report does not specifically flag that the $55/hour rate is absent from the EL's approved rate schedule (Exhibit A), nor does it frame the issue as a rate schedule compliance gap under the OCG requirement that all timekeepers be listed in the approved rate schedule. The OCG issue flagged is about individual name approval (§3.1), not about the rate schedule listing requirement. The specific framing required by the criterion — that the $55/hr rate is missing from the EL rate schedule and OCG requires all timekeepers in the approved rate schedule — is not present in the report.
- **GPT-5.5: Fail.** The report flags contract reviewers as a compliance/budget issue and notes the $55/hour rate, separate line-item treatment, and OCG requirements for individual approval before invoicing. However, it does not identify the specific criterion issue that the $55/hour contract reviewer rate is missing from the engagement letter’s approved rate schedule; in fact, it characterizes the EL as stating the $55/hour rate as a separate line item. Therefore the required issue is not flagged as stated.

### C-062

ISSUE_005: Flags mediation deadline inconsistency (March 3 vs. Feb 28, 2026) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L507))

- **Sonnet 4.6: Pass.** The agent's output explicitly identifies the mediation deadline inconsistency in finding M-11: 'The narrative says Mar. 3, 2026, which is correct (90 days before June 1, 2026). The chart says Feb. 28, 2026 (93 days). The XLS says "Mar. 2026".' This directly matches the criterion requiring identification of the March 3 vs. February 28, 2026 discrepancy.
- **GPT-5.5: Pass.** The report explicitly flags the mediation deadline inconsistency, stating that the narrative deadline is March 3, 2026 as 90 days before the June 1, 2026 trial date, while the Matter Plan chart shows February 28, 2026, a roughly three-day discrepancy.

### C-063

ISSUE_006: Flags conflict between retroactive overage approval and OCG advance-approval rule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L515))

- **Sonnet 4.6: Pass.** The report explicitly identifies this conflict in finding H-5 (HIGH severity), noting that the EL allows retroactive DGC approval of overages up to 10% within 15 business days of invoice submission, while OCG §4.3 bans retroactive approval outright with no de minimis exception. The conflict is also captured in the cross-document matrix under 'Monthly fee cap'. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags the conflict in multiple places, especially H-5: it states the EL allows Deputy GC retroactive approval of monthly cap overages up to 10%, while OCG §4.3 requires advance approval/no retroactive approvals. The executive summary also identifies this as a significant issue.

### C-064

ISSUE_007: Flags scope gap for non-HX-9000 claims consolidated into MDL ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L523))

- **Sonnet 4.6: Pass.** The agent's output explicitly identifies the scope gap between EX-6 and WS-1 in multiple places. In the Executive Summary, it notes: 'There is still a gap between the non-HX-9000 exclusion (EX-6) and WS-1. EX-6 carves consolidated MDL claims back in, but WS-1 covers only the MDL "as currently constituted". The MP says the carve-back does not authorize any work. The EL's version of EX-6 is broader than the MP's.' Finding H-6 elaborates: 'The EL carve-back covers claims consolidated into the MDL "or [that] otherwise become part of the proceedings covered by this letter", which is broader than the MP and the emails. The MP says the carve-back authorizes no work until a scope amendment is signed, and WS-1 covers only the MDL "as currently constituted"... Because the EL controls, it arguably authorizes work that the MP forbids.' The cross-document matrix also flags this as '◐ M-12' and '✖ H-6'. Finding M-12 further notes that WS-1 excludes later tag-alongs even for HX-9000 claims. The report clearly identifies the ambiguity/gap between EX-6's exception for consolidated claims and WS-1's limitation to the MDL 'as currently constituted', including the lack of budget allocation for such work.
- **GPT-5.5: Pass.** The report expressly identifies the EX-6 / WS-1 scope gap for non-HX-9000 claims, noting that EX-6’s carve-back may cover claims consolidated into the MDL while WS-1 is limited to the MDL “as currently constituted,” with no affirmative authorization, protocol, or budget for such later claims.

### C-065

ISSUE_008: Flags 'aggregate payments' in success fee is undefined ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L531))

- **Sonnet 4.6: Pass.** The report explicitly addresses the undefined 'aggregate payments' term in multiple places. In the Executive Summary, it states: 'Aggregate payments, the term that drives the success fee, is still undefined. The emails show the parties disagreed (the firm wanted indemnity-only; the client wanted total cost including carrier payments) and never resolved it.' Finding H-9 in the Inconsistency Register is dedicated entirely to this issue, noting the disputed definition between indemnity-only vs. total enterprise cost including carrier payments, defense costs, ALAE, and carrier defense reimbursements. The cross-document matrix also marks this as a gap (◐ H-9). The recommended actions include negotiating a definitional amendment covering indemnity, carrier-funded payments, defense costs and ALAE. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags the success-fee term “aggregate payments” / “Actual Aggregate Payments” as undefined in both the Engagement Letter and Matter Plan. It also describes the unresolved ambiguity, including whether the term is indemnity-only versus total enterprise cost, and specifically references defense costs, ALAE, carrier/insurer payments, and indemnity payments.

### C-066

ISSUE_010: Flags 'affiliates' undefined in prospective conflicts waiver ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L539))

- **Sonnet 4.6: Fail.** The agent's report does not mention the limited prospective conflicts waiver or the undefined term 'affiliates' anywhere in the document. The report covers many issues including hierarchy conflicts, budget discrepancies, work stream approvals, and various other scope terms, but there is no discussion of the conflicts waiver or ambiguity about which entities are covered by it given Pinnacle's multiple subsidiaries.
- **GPT-5.5: Fail.** The report does not identify any issue with a limited prospective conflicts waiver or note that the term 'affiliates' is undefined. It only mentions clients/subsidiaries generally, without raising ambiguity about which affiliates are covered by a waiver.

### C-067

Extracts rebuttal expert reserve amount of $230,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L547))

- **Sonnet 4.6: Pass.** The report explicitly mentions the $230,000 rebuttal reserve multiple times. In Section 2 (Executive Summary): 'EL and MP §3.3 set expert fees at $780,000 (rebuttal reserve $230,000).' In Section 3 (Cross-Document Matrix), under Expert caps: 'rebuttal reserve $230K.' In Section 4 (Finding H-7): 'Rebuttal reserve: $230,000 (MP §3.3) vs $210,000 (XLS).' In Section 5.2 (Disbursement budget table): '$780,000 ($550K named + $230K reserve).' The calculation of $780,000 total minus $550,000 named experts equals $230,000 reserve is also explicitly shown in the disbursement table.
- **GPT-5.5: Pass.** The report explicitly identifies the rebuttal expert reserve as $230,000 in multiple places, including the executive summary, cross-document matrix, H-7 finding, and disbursement budget table, and ties it to the $780,000 expert allocation with $550,000 named experts.

### C-068

Extracts mediation joint approval requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L555))

- **Sonnet 4.6: Pass.** The report explicitly states in the Cross-Document Matrix under 'Mediators / deadline': 'Joint approval by GC and Lead Trial Partner; pre-approved list in MP'. Additionally, finding L-12 states: 'The EL and MP require joint approval by the GC and Voss, with no delegation.' This clearly captures the joint approval requirement for mediator selection.
- **GPT-5.5: Pass.** The report explicitly states under “Mediators / deadline” that mediator selection requires “Joint approval by GC and Lead Trial Partner,” and later reiterates that the EL and MP require joint approval by the GC and Voss.

### C-069

Extracts accrued fees payment term of 45 days upon termination ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L563))

- **Sonnet 4.6: Pass.** The report explicitly states in the Termination row of the cross-document matrix: '30 days' notice; files within 15 business days; accrued fees paid in 45 days; success fee forfeited or pro-rated; wind-down fee 2% if billed "in excess of" $2M'. This clearly captures the 45-day payment term for accrued fees upon termination.
- **GPT-5.5: Pass.** The report's Termination row explicitly states that accrued fees are paid in 45 days, satisfying the requirement to extract the accrued fees payment term upon termination.

### C-070

Extracts 5% threshold for post-engagement work stream additions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L571))

- **Sonnet 4.6: Pass.** The report explicitly mentions the 5% threshold multiple times. In the Executive Summary it states 'Its $320,000 sub-budget is above the 5% new-work-stream limit ($212,500) in EL §§1, 7 and 12.' In the Cross-Document Matrix under 'New work-stream threshold' it states '>5% of AFB ($212,500) requires GC prior written re-approval (§§1, 7, 12).' In finding H-2 it states 'The EL defines 5% of the AFB as $212,500 and requires the GC's prior written re-approval for any work stream added after Feb. 3, 2025 that exceeds it.' The calculation $4,250,000 × 5% = $212,500 is also confirmed in Section 5.3. This fully satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly extracts the EL provision that post-Feb. 3, 2025 work streams exceeding 5% of the $4,250,000 aggregate fee budget ($212,500) require the General Counsel’s prior written re-approval, including citations to EL §§1, 7, and 12 and discussion of WS-4 exceeding the threshold.

### C-071

Report includes document-specific references ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L579))

- **Sonnet 4.6: Pass.** The report consistently provides document-specific references throughout all sections. The cross-document matrix (Section 3) explicitly cites EL, MP, R1, OCG, XLS, and EML for every extracted term. The inconsistency register (Section 4) cites specific document sections for each finding (e.g., 'EL §§11, 12; MP §10; OCG preamble' for H-1, 'EL §§1, 7, 12(a); R1 §§1, 2.2' for H-2, etc.). The budget reconciliation (Section 5) references specific document sections like 'EL §4.1 / Ex. B', 'MP §3.3 text', 'MP §7.2 table', and 'XLS'. Document-specific references appear throughout the entire report, not just in one section.
- **GPT-5.5: Pass.** The report provides document-specific references throughout, including a source list, a cross-document matrix with columns for EL, MP, R1, OCG, XLS, and EML, and an inconsistency register citing specific documents and sections for each issue. Extracted terms are consistently tied to document names and often section numbers, not merely sourced in one place.

### C-072

Extracts Marcus Oduya as lead paralegal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L587))

- **Sonnet 4.6: Fail.** The report mentions Oduya only once, in finding L-8, where it notes the XLS lists WS-6 as led by 'junior associates and Oduya.' The staffing section (the cross-document matrix row for 'Associates / paralegals') does not identify Oduya as lead paralegal, nor does any staffing section explicitly name him as lead paralegal with the 'up to 2 paralegals authorized' detail. The criterion requires the report to identify Marcus Oduya as lead paralegal in the staffing section with up to 2 paralegals authorized. This is not done.
- **GPT-5.5: Fail.** The report notes up to 2 paralegals in the staffing row, but it does not identify Marcus Oduya as lead paralegal there. Oduya is only mentioned later in a low-severity XLS work-stream lead note, not as the extracted lead paralegal staffing term.

### C-073

Extracts key deadline: Rebuttal expert reports October 31, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L595))

- **Sonnet 4.6: Fail.** The agent's output does not mention October 31, 2025 as a deadline for rebuttal expert reports anywhere in the report. The report discusses expert caps, rebuttal reserves ($230K vs $210K), and various deadlines, but the specific date of October 31, 2025 for rebuttal expert reports is not listed anywhere in the document.
- **GPT-5.5: Fail.** The report mentions expert budgets and rebuttal reserves, but it does not list October 31, 2025 as the deadline for rebuttal expert reports.

### C-074

Extracts insurance coverage details (primary $5M/$10M, excess $15M) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L603))

- **Sonnet 4.6: Pass.** The report's cross-document matrix row for 'Insurance' explicitly states: 'Fortitude $5M / $10M; Ridgeline $15M follow-form; no direct carrier contact on coverage without DGC' under the EL column, and finding H-10 discusses direct communication with Fortitude and Ridgeline. This references both the primary coverage ($5M/$10M from Fortitude) and the excess layer ($15M follow-form from Ridgeline) in connection with WS-5 and the engagement scope.
- **GPT-5.5: Pass.** The report explicitly references WS-5/insurance coverage details: Fortitude with $5M/$10M limits and Ridgeline with a $15M follow-form excess layer.

### C-075

Extracts mediation deadline (90 days before trial) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L611))

- **Sonnet 4.6: Pass.** The report explicitly references the mediation completion deadline as 90 days before trial in finding M-11: 'The narrative says Mar. 3, 2026, which is correct (90 days before June 1, 2026).' It also appears in the cross-document matrix under 'Mediators / deadline': 'completion 90 days before trial: Mar. 3, 2026 (narrative) vs Feb. 28, 2026 (chart).'
- **GPT-5.5: Pass.** The report explicitly extracts the mediation completion deadline, stating it must be completed 90 days before trial and identifying the corresponding date discrepancy.

### C-076

Correct matter number referenced (WC-2025-04381) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-scope-terms-from-matter-plan/task.json#L619))

- **Sonnet 4.6: Pass.** The report references 'Whitford & Callaway LLP Matter No. WC-2025-04381' in the header section, which matches the required matter number exactly.
- **GPT-5.5: Pass.** The report references the firm's matter number as “Whitford & Callaway LLP Matter No. WC-2025-04381” in the header.
