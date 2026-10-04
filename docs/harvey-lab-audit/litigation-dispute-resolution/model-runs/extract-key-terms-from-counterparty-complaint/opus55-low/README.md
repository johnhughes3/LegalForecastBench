# Claude Opus 5.5 (low): Extract Key Terms from Counterparty Complaint — Litigation Summary Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-key-terms-from-counterparty-complaint/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 67 of 75 criteria; GPT-5.5 passed 66 of 75 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [litigation-summary-memo.docx](output/litigation-summary-memo.docx) ([read as Markdown](output/litigation-summary-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Case number correctly identified as 25-CVS-4471 | Pass | Pass |
| [C-002](#c-002) | Court identified as Superior Court of Mecklenburg County, NC | Pass | Pass |
| [C-003](#c-003) | Judge identified as Hon. Robert L. Vanderhorst | Pass | Pass |
| [C-004](#c-004) | Plaintiff correctly identified as Apex Industrial Solutions, LLC | Pass | Pass |
| [C-005](#c-005) | Defendant correctly identified as Greenfield Dynamics, Inc. | Pass | Pass |
| [C-006](#c-006) | Plaintiff's law firm identified as Whitlock Stein & Marsh, P.A. | Pass | Pass |
| [C-007](#c-007) | Plaintiff's lead attorney identified as Reginald Whitlock | Pass | Pass |
| [C-008](#c-008) | Defense counsel firm identified as Harmon & Lyle LLP | **Fail** | **Fail** |
| [C-009](#c-009) | Defense lead partner identified as Catherine Ng | Pass | **Fail** |
| [C-010](#c-010) | Filing date of April 22, 2025 correctly stated | Pass | Pass |
| [C-011](#c-011) | Service date of April 25, 2025 correctly stated | Pass | Pass |
| [C-012](#c-012) | Answer deadline correctly calculated as May 27, 2025 | Pass | Pass |
| [C-013](#c-013) | TRO hearing date of May 9, 2025 correctly stated | Pass | Pass |
| [C-014](#c-014) | Count I — Breach of Exclusive Distribution Agreement summarized | Pass | Pass |
| [C-015](#c-015) | Count I lost profits damages stated as $7,084,000 | Pass | Pass |
| [C-016](#c-016) | Count I lost commissions damages stated as $766,800 | Pass | Pass |
| [C-017](#c-017) | Count II — Tortious Interference legal theory summarized | Pass | Pass |
| [C-018](#c-018) | Count II — Damages stated as $6,200,000 | Pass | Pass |
| [C-019](#c-019) | Count III — Misappropriation of Trade Secrets summarized | Pass | Pass |
| [C-020](#c-020) | Count III damages stated as $6,800,000 total | Pass | Pass |
| [C-021](#c-021) | Count IV — Unjust Enrichment summarized | Pass | Pass |
| [C-022](#c-022) | Grand total damages verified as $22,341,800 | Pass | Pass |
| [C-023](#c-023) | Agreement effective date identified as March 1, 2019 | Pass | Pass |
| [C-024](#c-024) | Agreement initial term expiration identified as February 28, 2024 | Pass | Pass |
| [C-025](#c-025) | Section 4.2 auto-renewal provision extracted | Pass | **Fail** |
| [C-026](#c-026) | Section 4.2 180-day advance written notice requirement extracted | Pass | Pass |
| [C-027](#c-027) | Non-renewal notice deadline of August 31, 2023 identified | Pass | Pass |
| [C-028](#c-028) | Section 4.2 signatory requirement (CEO or General Counsel) extracted | Pass | Pass |
| [C-029](#c-029) | Section 5.1 minimum purchase commitments extracted | **Fail** | **Fail** |
| [C-030](#c-030) | Section 5.3 curable default and 60-day cure notice requirement extracted | Pass | Pass |
| [C-031](#c-031) | Section 16.1 Georgia choice of law extracted | Pass | Pass |
| [C-032](#c-032) | Section 16.3 Mecklenburg County forum selection extracted | Pass | Pass |
| [C-033](#c-033) | Section 14.2 prevailing party fee-shifting provision extracted | Pass | Pass |
| [C-034](#c-034) | Magnolia Foods Processing, Inc. identified as direct-sale customer | **Fail** | **Fail** |
| [C-035](#c-035) | Tidewater Pharmaceutical Group, LLC identified as direct-sale customer | **Fail** | Pass |
| [C-036](#c-036) | Clearwater Chemical Partners, LP identified as direct-sale customer | **Fail** | **Fail** |
| [C-037](#c-037) | Southeastern Bottling Co., Inc. identified as direct-sale customer | Pass | Pass |
| [C-038](#c-038) | Total alleged direct sales stated as $4,260,000 | Pass | Pass |
| [C-039](#c-039) | Brandon Kelsey identified as hired-away employee (former Southeast Regional Sales Manager at Apex) | **Fail** | **Fail** |
| [C-040](#c-040) | Lauren Ostrowski identified as hired-away employee (former Senior Technical Account Executive at Apex) | **Fail** | **Fail** |
| [C-041](#c-041) | Confidential Sales Information components described | Pass | Pass |
| [C-042](#c-042) | Injunctive relief: prohibition of further direct sales in Territory | Pass | Pass |
| [C-043](#c-043) | Injunctive relief: return/destruction of Confidential Sales Information | Pass | Pass |
| [C-044](#c-044) | Injunctive relief: prohibition on employing Kelsey/Ostrowski in Territory-related roles | Pass | Pass |
| [C-045](#c-045) | Attorneys' fees claim under Section 14.2 noted | Pass | Pass |
| [C-046](#c-046) | Attorneys' fees claim under Georgia Trade Secrets Act noted | Pass | Pass |
| [C-047](#c-047) | Eight-state exclusive territory identified | Pass | Pass |
| [C-048](#c-048) | ISSUE_001: Defective first notice — Hargrove not authorized signatory | Pass | Pass |
| [C-049](#c-049) | ISSUE_001: Greenfield did not cure the signatory defect until September 12 | Pass | Pass |
| [C-050](#c-050) | ISSUE_002: Second notice was only 169 days before expiration | Pass | Pass |
| [C-051](#c-051) | ISSUE_002: Auto-renewal through February 28, 2026 is Apex's position | Pass | Pass |
| [C-052](#c-052) | Year 2 shortfall of $2.1M identified ($7.1M actual vs. $9.2M minimum) | Pass | Pass |
| [C-053](#c-053) | Greenfield's failure to send 60-day cure notice for Year 2 shortfall identified | Pass | Pass |
| [C-054](#c-054) | Waiver implication from absent cure notice discussed | Pass | Pass |
| [C-055](#c-055) | ISSUE_003: Year 2 shortfall undermines Greenfield's material breach defense | Pass | Pass |
| [C-056](#c-056) | ISSUE_004: Exemplary damages statutory characterization flagged | **Fail** | **Fail** |
| [C-057](#c-057) | ISSUE_005: Double recovery risk between Counts I and II | Pass | Pass |
| [C-058](#c-058) | ISSUE_006: Choice of law vs. forum selection complexity identified | Pass | Pass |
| [C-059](#c-059) | ISSUE_007: TRO hearing precedes answer deadline — urgency flagged | Pass | Pass |
| [C-060](#c-060) | ISSUE_008: Unjust enrichment generally unavailable alongside express contract | Pass | Pass |
| [C-061](#c-061) | ISSUE_009: Count I lost profits calculation verified ($16.1M × 22% × 2 = $7,084,000) | Pass | Pass |
| [C-062](#c-062) | ISSUE_009: Count I lost commissions verified ($4,260,000 × 18% = $766,800) | Pass | Pass |
| [C-063](#c-063) | ISSUE_009: Count IV unjust enrichment verified ($4,260,000 × 35% = $1,491,000) | Pass | Pass |
| [C-064](#c-064) | ISSUE_010: Enforceability of 24-month non-competes flagged | Pass | Pass |
| [C-065](#c-065) | Chronological timeline of material events included | Pass | Pass |
| [C-066](#c-066) | Damages analysis presented in structured format (table or breakdown) | Pass | Pass |
| [C-067](#c-067) | Immediate action items section with TRO preparation prioritized | Pass | Pass |
| [C-068](#c-068) | Answer filing identified as an action item by May 27, 2025 | Pass | Pass |
| [C-069](#c-069) | Client GC admissions from email extracted | Pass | Pass |
| [C-070](#c-070) | 24-month non-compete/non-solicitation agreements of Kelsey and Ostrowski noted | Pass | Pass |
| [C-071](#c-071) | Apex's alleged renewal period identified as through February 28, 2026 | Pass | Pass |
| [C-072](#c-072) | Apex's 22% gross margin on Greenfield products noted | Pass | Pass |
| [C-073](#c-073) | Apex's 18% commission rate on Territory sales noted | Pass | Pass |
| [C-074](#c-074) | Greenfield's alleged 35% margin on direct sales noted | Pass | Pass |
| [C-075](#c-075) | Kelsey/Ostrowski employment agreements governed by Georgia law noted | Pass | Pass |

## Judge reasoning

### C-001

Case number correctly identified as 25-CVS-4471 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L19))

- **Sonnet 4.6: Pass.** The memorandum clearly states the case number as 'No. 25-CVS-4471' in the RE line of the memo header and again in the Case Snapshot table under 'Court / Case No.' as 'N.C. Superior Court, Mecklenburg County, No. 25-CVS-4471'. The case number is correctly identified.
- **GPT-5.5: Pass.** The memorandum identifies the case as No. 25-CVS-4471 in the RE line and in the Case Snapshot section.

### C-002

Court identified as Superior Court of Mecklenburg County, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L27))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies the court in multiple places. In the RE line of the header it states 'Mecklenburg Cty. Super. Ct.' and in the Case Snapshot table it states 'N.C. Superior Court, Mecklenburg County, No. 25-CVS-4471'. This correctly identifies the court as the Superior Court of Mecklenburg County, North Carolina.
- **GPT-5.5: Pass.** The memorandum identifies the forum as “N.C. Superior Court, Mecklenburg County” and also references “Mecklenburg Cty. Super. Ct.” in the case caption/RE line, satisfying the requirement to identify the court as the Superior Court of Mecklenburg County, North Carolina.

### C-003

Judge identified as Hon. Robert L. Vanderhorst ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L35))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the assigned judge as 'Hon. Robert L. Vanderhorst' in multiple places, including the Executive Summary ('before the Hon. Robert L. Vanderhorst') and the Case Snapshot table ('Hon. Robert L. Vanderhorst').
- **GPT-5.5: Pass.** The memorandum identifies the assigned judge as the Hon. Robert L. Vanderhorst in the Executive Summary and Case Snapshot.

### C-004

Plaintiff correctly identified as Apex Industrial Solutions, LLC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L43))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies the plaintiff as 'Apex Industrial Solutions, LLC (Georgia LLC; Atlanta)' in the Case Snapshot section, and refers to Apex Industrial Solutions, LLC throughout the document. This matches the criterion requiring identification as a Georgia LLC.
- **GPT-5.5: Pass.** The memorandum identifies the plaintiff as Apex Industrial Solutions, LLC and specifies it is a Georgia LLC in the Case Snapshot.

### C-005

Defendant correctly identified as Greenfield Dynamics, Inc. ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L51))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies the defendant/client as Greenfield Dynamics, Inc., a Delaware corporation, in multiple places including the Case Snapshot table ('Defendant: Greenfield Dynamics, Inc. (Delaware corp.; PPB Charlotte, NC)') and the RE line ('CLIENT: Greenfield Dynamics, Inc. (Defendant)').
- **GPT-5.5: Pass.** The memorandum identifies the client/defendant as Greenfield Dynamics, Inc. and specifically states it is a Delaware corporation in the case snapshot.

### C-006

Plaintiff's law firm identified as Whitlock Stein & Marsh, P.A. ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L59))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies plaintiff's counsel as 'Reginald Whitlock and Priya Nandakumar, Whitlock Stein & Marsh, P.A. (Atlanta)' in the Case Snapshot section (Part II).
- **GPT-5.5: Pass.** The memorandum identifies plaintiff's counsel as Reginald Whitlock and Priya Nandakumar of Whitlock Stein & Marsh, P.A., which matches the required firm name.

### C-007

Plaintiff's lead attorney identified as Reginald Whitlock ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L67))

- **Sonnet 4.6: Pass.** The memorandum's Case Snapshot section lists 'Plaintiff's counsel' as 'Reginald Whitlock and Priya Nandakumar, Whitlock Stein & Marsh, P.A. (Atlanta)'. Reginald Whitlock is named first and is identified as plaintiff's counsel. The criterion asks whether Reginald Whitlock is identified as lead attorney for the plaintiff, and he is indeed named (listed first among plaintiff's counsel).
- **GPT-5.5: Pass.** The memorandum names Reginald Whitlock under Plaintiff's counsel (with Priya Nandakumar) and references him as signing the Certificate of Service, satisfying the requirement that Reginald Whitlock be identified for the plaintiff.

### C-008

Defense counsel firm identified as Harmon & Lyle LLP ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L75))

- **Sonnet 4.6: Fail.** The memorandum identifies the defense counsel firm as 'HARMON LYLE' (shown in the header of the memo). The criterion requires the firm to be identified as 'Harmon & Lyle LLP'. The memo omits the ampersand '&' and 'LLP' from the firm name, making it 'HARMON LYLE' rather than 'Harmon & Lyle LLP'. This is an incorrect firm name per the criterion.
- **GPT-5.5: Fail.** The memorandum header says “HARMON LYLE” and does not identify the defense counsel firm as “Harmon & Lyle LLP.” The required firm name is missing/incorrect.

### C-009

Defense lead partner identified as Catherine Ng ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L83))

- **Sonnet 4.6: Pass.** The memorandum lists 'Catherine Ng; Jonathan Breyer' in the TO field, and in the action items table, Catherine Ng is listed as the owner for the removal/Business Court designation decision (item 6) and co-owner of other items. However, the criterion asks whether Catherine Ng is identified as the 'lead partner for the defense.' The memo addresses the memo TO Catherine Ng and Jonathan Breyer, and in the action items, Ng is listed as the decision-maker for the removal question. The memo does not explicitly use the title 'lead partner' for anyone, but Catherine Ng is named as a primary recipient and decision-maker. The criterion simply asks if Catherine Ng is named as lead partner. She is named prominently as a recipient and decision-maker, which is consistent with being the lead partner, though the memo doesn't use that exact phrase. Given the criterion states 'PASS if the memorandum identifies Catherine Ng as lead partner for the defense' and she is listed first in the TO line and as owner of key strategic decisions, this satisfies the criterion.
- **GPT-5.5: Fail.** The memorandum names Catherine Ng in the TO line and assigns actions to Ng, but it does not expressly identify her as the lead partner for the defense.

### C-010

Filing date of April 22, 2025 correctly stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L91))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the Case Snapshot table: 'Filed April 22, 2025; personally served April 25, 2025' and also in the chronology table: 'Apr. 22, 2025 - Complaint filed (verified by Colford)'. The filing date of April 22, 2025 is correctly stated.
- **GPT-5.5: Pass.** The memorandum states the complaint was filed on April 22, 2025 in multiple places, including the Case Snapshot and chronology.

### C-011

Service date of April 25, 2025 correctly stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L99))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in multiple places that service was perfected on April 25, 2025. In the Case Snapshot table it states 'Filed April 22, 2025; personally served April 25, 2025, 2:15 p.m.' and in Part III it discusses the service-date discrepancy, concluding 'the affidavit is the better evidence, and April 25 is very likely the operative date.' The deadline table also references 'from Apr. 25 service' for the answer deadline.
- **GPT-5.5: Pass.** The memorandum expressly states that Greenfield was served on April 25, 2025, including in the Executive Summary and Case Snapshot, and treats April 25 as the likely operative service date despite noting a discrepancy.

### C-012

Answer deadline correctly calculated as May 27, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L107))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the Critical Deadlines table: 'Answer / Rule 12 motion (state court): Tues., May 27, 2025 (from Apr. 25 service)' and explains 'N.C. R. Civ. P. 12(a)(1): 30 days. Day 30 (May 25) is a Sunday and May 26 is Memorial Day, so Rule 6(a) rolls it to May 27.' This matches the criterion exactly.
- **GPT-5.5: Pass.** The memorandum expressly states the answer/Rule 12 deadline is Tuesday, May 27, 2025, and explains that the 30-day period from April 25 falls on Sunday, May 25, with Memorial Day on May 26, so the deadline rolls to May 27.

### C-013

TRO hearing date of May 9, 2025 correctly stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L115))

- **Sonnet 4.6: Pass.** The memorandum explicitly states the TRO hearing date multiple times, including in the Executive Summary ('The hearing is set for Friday, May 9, 2025 at 10:00 a.m.'), in the Case Snapshot table, in the Critical Deadlines table, and in the TRO/PI analysis section.
- **GPT-5.5: Pass.** The memorandum explicitly states the TRO/preliminary injunction hearing is set for Friday, May 9, 2025 at 10:00 a.m., and repeats the May 9, 2025 date in the deadlines and chronology sections.

### C-014

Count I — Breach of Exclusive Distribution Agreement summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L123))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies Count I as a breach of contract claim based on the Exclusive Distribution Agreement. Section V.A is titled 'Count I: Breach of the Exclusive Distribution Agreement ($7,850,800 claimed)' and explains Apex's theory that both non-renewal notices were void under § 4.2, causing the Agreement to renew through February 28, 2026, and that Greenfield breached by repudiating, selling directly in the Territory, and refusing to honor the Renewal Term. The memo also discusses the direct sales during the Initial Term as a separate basis for breach of exclusivity. This fully satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly identifies Count I as breach of the Exclusive Distribution Agreement, summarizes Apex’s theory that Greenfield’s non-renewal notices were void/improper and that the Agreement renewed, and discusses Greenfield’s alleged direct sales in the Territory as breaches of exclusivity.

### C-015

Count I lost profits damages stated as $7,084,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L131))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the damages table: 'Count I: Renewal lost profits $16.1M × 22% × 2 = $7,084,000' with the note 'Math correct'. This matches the criterion exactly.
- **GPT-5.5: Pass.** The memorandum expressly states Count I renewal lost profits as “$16.1M × 22% × 2 = $7,084,000” in the damages table.

### C-016

Count I lost commissions damages stated as $766,800 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L139))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the damages arithmetic verification table: 'Count I: Lost commissions | $4.26M × 18% = $766,800' and also references this figure in the Count I analysis section ('the same sales underlying Count I's $766,800 commission claim'). This matches the criterion exactly.
- **GPT-5.5: Pass.** The memorandum explicitly states Count I lost commissions as “$4.26M × 18% = $766,800” in the damages verification table.

### C-017

Count II — Tortious Interference legal theory summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L147))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies Count II as 'Tortious Interference with Business Relationships' claiming $6,200,000 plus punitive damages, and provides a detailed analysis of the legal theory including the non-stranger/party privilege defense, the connection to Greenfield's direct sales in Apex's exclusive territory, and the relationship to the distribution agreement. This satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly identifies Count II as “Tortious Interference with Business Relationships” and summarizes it as arising from Greenfield’s alleged interference/direct sales involving Apex’s customer relationships, including damages tied to the four customers.

### C-018

Count II — Damages stated as $6,200,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L155))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the Case Snapshot section and in the Count II analysis header: 'Count II: Tortious Interference with Business Relationships ($6,200,000 + punitive damages)'. The $6,200,000 figure is clearly stated as the damages for Count II.
- **GPT-5.5: Pass.** The memorandum explicitly states Count II damages as "$6,200,000 + punitive damages" in the Count II heading and also lists "Count II: Customer NPV $6,200,000" in the damages table.

### C-019

Count III — Misappropriation of Trade Secrets summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L163))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies Count III as a trade secret misappropriation claim under both the Georgia Trade Secrets Act (GTSA) and the federal Defend Trade Secrets Act (DTSA), with specific statutory references (O.C.G.A. § 10-1-763, § 10-1-764, § 10-1-767; 18 U.S.C. § 1836). It discusses the hiring of Kelsey and Ostrowski and the alleged taking of Apex's Confidential Sales Information, including the timeline analysis showing that most direct sales predated the hires. The claim amount ($6,800,000) and the legal basis are both clearly identified.
- **GPT-5.5: Pass.** The memorandum expressly identifies Count III as a trade secret misappropriation claim under both the Georgia Trade Secrets Act (GTSA) and the federal Defend Trade Secrets Act (DTSA), and summarizes that it involves Greenfield’s hiring of Kelsey and Ostrowski and alleged use/taking of Apex’s Confidential Sales Information.

### C-020

Count III damages stated as $6,800,000 total ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L171))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Part VII.A: 'Count III: Actual + exemplary: $3.4M + $3.4M = $6,800,000' and in Part V.C: 'Count III: Trade Secret Misappropriation, GTSA and DTSA ($6,800,000 claimed)'. This matches the criterion of $3,400,000 actual plus $3,400,000 exemplary totaling $6,800,000.
- **GPT-5.5: Pass.** The memorandum expressly states Count III trade secret damages as $6,800,000, consisting of $3.4M actual plus $3.4M exemplary damages, including in the damages table.

### C-021

Count IV — Unjust Enrichment summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L179))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses Count IV under Section V.D, identifying it as an unjust enrichment claim pleaded in the alternative to Count I. It states the measure as Greenfield's ~35% margin on $4.26M = $1,491,000, and notes the math is verified. This satisfies the criterion requiring identification of Count IV as an unjust enrichment/disgorgement claim seeking $1,491,000 calculated as $4,260,000 × 35% margin.
- **GPT-5.5: Pass.** The memorandum expressly summarizes Count IV as an unjust enrichment claim, states it seeks $1,491,000, and explains the calculation as Greenfield’s approximately 35% margin on $4.26M in sales.

### C-022

Grand total damages verified as $22,341,800 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L187))

- **Sonnet 4.6: Pass.** The memorandum states in the Executive Summary that Apex 'seeks at least $22,341,800' and in the damages table (Part VII.A) lists all five components: Count I lost profits ($7,084,000), Count I lost commissions ($766,800), Count II customer NPV ($6,200,000), Count III actual + exemplary ($6,800,000), and Count IV unjust enrichment ($1,491,000), with the total row showing '$22,341,800' and noting 'Sum correct.' The memo also verifies the math on each line item (marking them 'Math correct' or 'Correct'). However, the criterion specifically requires verification that $22,341,800 equals the sum of those five components ($7,084,000 + $766,800 + $6,200,000 + $6,800,000 + $1,491,000 = $22,341,800). The memo does state the total is '$22,341,800' and confirms 'Sum correct' in the table, and it lists all five components with their amounts. This constitutes stating and verifying the grand total as $22,341,800.
- **GPT-5.5: Pass.** The memorandum expressly states Apex seeks at least $22,341,800 and, in the damages verification table, lists the component amounts including $7,084,000, $766,800, $6,200,000, $6,800,000, and $1,491,000, then confirms the total as $22,341,800 with 'Sum correct.'

### C-023

Agreement effective date identified as March 1, 2019 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L195))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the chronology table: 'Mar. 1, 2019 — Exclusive Distribution Agreement executed. 8-state Territory (GA, AL, TN, SC, NC, FL, MS, LA); Initial Term to Feb. 28, 2024.' This correctly identifies the Distribution Agreement's effective date as March 1, 2019.
- **GPT-5.5: Pass.** The memorandum identifies the Exclusive Distribution Agreement as executed on March 1, 2019 in the chronology, satisfying the criterion that the agreement effective date be identified as March 1, 2019.

### C-024

Agreement initial term expiration identified as February 28, 2024 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L203))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in multiple places that the Initial Term expires on February 28, 2024. For example, in the Case Snapshot table: 'Initial Term to Feb. 28, 2024' and in the chronology: 'Feb. 28, 2024 - Initial Term expires.' This date is correctly and clearly identified throughout the document.
- **GPT-5.5: Pass.** The memorandum repeatedly identifies the Distribution Agreement’s Initial Term as expiring on February 28, 2024, including in the executive summary, chronology, and claim analysis.

### C-025

Section 4.2 auto-renewal provision extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L211))

- **Sonnet 4.6: Pass.** The memorandum references Section 4.2 multiple times, identifying it as the provision governing non-renewal notice requirements (signatory and timing rules) and stating that void notices result in automatic renewal. For example, it states 'The Agreement therefore renewed through February 28, 2026' and discusses how both notices failed § 4.2's requirements, causing auto-renewal. However, the criterion specifically requires that Section 4.2 be identified as containing a 'two-year automatic renewal provision.' The memo references § 4.1 for the renewal term ('Ex. A § 4.1') and discusses § 4.2 only in the context of notice requirements and the consequence of void notices (auto-renewal). The memo does not explicitly identify § 4.2 as containing the two-year automatic renewal provision itself — it attributes the renewal term to § 4.1. The auto-renewal consequence is discussed in connection with § 4.2's notice requirements, but § 4.2 is characterized as the notice provision, not the auto-renewal provision. That said, the criterion says PASS if the memo 'references Section 4.2 and identifies it as containing a two-year automatic renewal provision.' The memo does reference § 4.2 extensively and connects it to the auto-renewal outcome (the Agreement renewing through Feb. 28, 2026, a two-year renewal). The memo states § 4.2 requires notice and that failure voids the notice causing renewal — this implicitly identifies § 4.2 as the auto-renewal provision. Given the close connection drawn between § 4.2 and the two-year renewal, and that the memo does reference § 4.2 in the context of auto-renewal, this likely satisfies the criterion.
- **GPT-5.5: Fail.** The memorandum repeatedly references § 4.2 for non-renewal notice requirements and states that defective notices caused the Agreement to renew through February 28, 2026. However, it does not identify Section 4.2 itself as containing a two-year automatic renewal provision; it even attributes the renewal term in the chronology to Ex. A § 4.1. Therefore the specific criterion is not satisfied.

### C-026

Section 4.2 180-day advance written notice requirement extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L219))

- **Sonnet 4.6: Pass.** The memorandum explicitly mentions the 180-day advance written notice requirement under Section 4.2 multiple times. For example, it states 'the September 12, 2023 notice came 169 days before expiration, not the required 180' and 'A timely notice had to be delivered by September 1, 2023' (180 days before February 28, 2024). It also references the requirement in the context of the Renewal Term non-renewal notice deadline.
- **GPT-5.5: Pass.** The memorandum repeatedly identifies Section 4.2’s requirement that non-renewal notice be delivered at least 180 days before expiration, including analysis of the September 12 notice being only 169 days before expiration and therefore untimely.

### C-027

Non-renewal notice deadline of August 31, 2023 identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L227))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Part V.A: 'Apex (and Ms. Yuen) use August 31. That is 181 days out, which is more conservative and immaterial here.' It also states in the chronology table: 'Sept. 1, 2023 - Actual last day for a 180-day notice (Feb. 28, 2024 minus 180 days). Apex and Yuen say Aug. 31, which is 181 days.' The memo references August 31, 2023 as the deadline date used by Apex and Ms. Yuen (noting it is actually 181 days, with September 1 being the exact 180-day mark). The August 31, 2023 date is mentioned as the notice deadline. The criterion asks whether August 31, 2023 is identified as the deadline, and it is mentioned in the memo as the date Apex and Yuen use for the deadline.
- **GPT-5.5: Pass.** The memorandum expressly mentions an August 31, 2023 non-renewal notice deadline, including that Apex counsel flagged the “Aug. 31 deadline” and that Apex/Yuen used August 31 as the deadline.

### C-028

Section 4.2 signatory requirement (CEO or General Counsel) extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L235))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section V.A (Count I analysis): 'Section 4.2 requires notice "delivered by the Chief Executive Officer or General Counsel"' and further discusses the signatory defect of the July 15 notice being signed by the VP of Sales rather than the CEO or General Counsel. This clearly identifies the Section 4.2 signatory requirement.
- **GPT-5.5: Pass.** The memorandum expressly identifies the Section 4.2 signatory requirement, noting that the July 15 notice was defective because it was signed by the VP of Sales rather than the CEO or General Counsel, and repeatedly states that compliant non-renewal notice must be signed/delivered by the CEO or GC.

### C-029

Section 5.1 minimum purchase commitments extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L243))

- **Sonnet 4.6: Fail.** The memorandum does not reference Section 5.1 or the annual minimum purchase commitments for Years 1-5 ($8.0M, $9.2M, $10.6M, $12.2M, $14.0M). While it mentions a Year 2 shortfall ($7.1M against a $9.2M minimum) and cumulative figures ($55.7M vs. $54.0M), it never cites Section 5.1 or lists the year-by-year minimum purchase schedule.
- **GPT-5.5: Fail.** The memorandum discusses purchase history and mentions a Year 2 minimum of $9.2M and cumulative minimums of $54.0M, but it does not reference Section 5.1 or extract the full annual minimum purchase commitments for Years 1–5 ($8.0M, $9.2M, $10.6M, $12.2M, $14.0M).

### C-030

Section 5.3 curable default and 60-day cure notice requirement extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L251))

- **Sonnet 4.6: Pass.** The memorandum explicitly references Section 5.3 in Part V.A under Count I analysis: 'Section 5.3 makes a single-year miss a "Curable Default" and bars § 12.1(b) termination unless written notice and a 60-day cure period were first provided. None was given.' This directly satisfies the criterion by mentioning Section 5.3, characterizing the shortfall as a 'Curable Default,' and explaining the 60-day written notice requirement before termination under Section 12.1(b).
- **GPT-5.5: Pass.** The memorandum explicitly references Section 5.3, states that a single-year minimum purchase shortfall is a “Curable Default,” and explains that termination under Section 12.1(b) is barred unless written notice and a 60-day cure period were provided.

### C-031

Section 16.1 Georgia choice of law extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L259))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies Section 16.1 as the choice of law provision selecting Georgia law in multiple places. In the Case Snapshot table, it states 'Governing law: Georgia (Agreement § 16.1; Employment Agreements § 12).' In Section VIII on Choice of Law, it states 'The Distribution Agreement's § 16.1 and § 16.3 do not govern the employment agreements' and references § 16.1 selecting Georgia law for 'interpretation, validity, performance, and enforcement of this Agreement' in Section V.B. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memorandum expressly identifies “Governing law: Georgia (Agreement § 16.1...)” in the Case Snapshot and later discusses Section 16.1 selecting Georgia law for interpretation, validity, performance, and enforcement of the Agreement.

### C-032

Section 16.3 Mecklenburg County forum selection extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L267))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies Section 16.3 as the forum selection clause in the Case Snapshot table: 'Forum: exclusive to state or federal courts in Mecklenburg County (§ 16.3)'. It is also referenced again in Part IX under 'Removal to W.D.N.C.' where it states 'Section 16.3 permits "state or federal courts located in Mecklenburg County."'
- **GPT-5.5: Pass.** The memorandum expressly identifies § 16.3 as the forum clause, stating that the forum is exclusive to state or federal courts in Mecklenburg County and later noting that § 16.3 permits state or federal courts located in Mecklenburg County.

### C-033

Section 14.2 prevailing party fee-shifting provision extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L275))

- **Sonnet 4.6: Pass.** The memorandum explicitly references Section 14.2 multiple times as the prevailing party fee-shifting provision. In Count I analysis it states 'Apex also seeks specific performance and § 14.2 fees' and 'Fee shifting (§ 14.2) runs in both directions and covers "attorneys\ fees, expert witness fees, and costs."' It is also referenced in the damages section under 'Additional exposure items.'
- **GPT-5.5: Pass.** The memorandum expressly references § 14.2 as a fee-shifting provision, including that Apex seeks § 14.2 fees and that fee shifting under § 14.2 runs both directions for attorneys’ fees, expert witness fees, and costs.

### C-034

Magnolia Foods Processing, Inc. identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L283))

- **Sonnet 4.6: Fail.** The memorandum refers to the customer as 'Magnolia Foods' (e.g., 'Invoice GDI-2023-10847: Magnolia Foods (Savannah, GA), $870,000') but never uses the full name 'Magnolia Foods Processing, Inc.' The criterion specifically requires that 'Magnolia Foods Processing, Inc.' be named. Since the memo only uses 'Magnolia Foods' without the 'Processing, Inc.' suffix, it does not satisfy the criterion as described.
- **GPT-5.5: Fail.** The memorandum identifies “Magnolia Foods” as a customer associated with a direct-sale invoice, but it does not name the entity as “Magnolia Foods Processing, Inc.” as specified by the criterion.

### C-035

Tidewater Pharmaceutical Group, LLC identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L291))

- **Sonnet 4.6: Fail.** The memorandum refers to 'Tidewater Pharmaceutical' (e.g., 'Invoice GDI-2023-11203: Tidewater (Jacksonville, FL)' and 'Invoice GDI-2024-00341: Tidewater, $480,000') but never uses the full name 'Tidewater Pharmaceutical Group, LLC'. The criterion specifically requires that 'Tidewater Pharmaceutical Group, LLC' be named. The memo uses only 'Tidewater' or 'Tidewater Pharmaceutical' as shorthand, not the full legal entity name 'Tidewater Pharmaceutical Group, LLC'.
- **GPT-5.5: Pass.** The memorandum identifies Tidewater as a direct-sale customer, including listing “Tidewater Pharmaceutical” among key customer non-parties and invoice/direct-sales entries for “Tidewater.”

### C-036

Clearwater Chemical Partners, LP identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L299))

- **Sonnet 4.6: Fail.** The memorandum refers to 'Clearwater Chemical' (Birmingham, AL) multiple times, including in the chronology table and the trade secret analysis. However, the criterion specifically requires identification of 'Clearwater Chemical Partners, LP.' The memo only uses the name 'Clearwater Chemical' without the 'Partners, LP' designation. The entity name does not match exactly as specified in the criterion.
- **GPT-5.5: Fail.** The memorandum refers to “Clearwater Chemical” and “Clearwater,” but it does not name the customer as “Clearwater Chemical Partners, LP.”

### C-037

Southeastern Bottling Co., Inc. identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L307))

- **Sonnet 4.6: Pass.** The memorandum identifies 'Southeastern Bottling (Nashville, TN), $1,550,000' as one of the direct-sale customers in the chronology table (Feb. 5, 2024 entry) and also lists 'Southeastern Bottling' as a key non-party in the Case Snapshot section. The name used is 'Southeastern Bottling' rather than 'Southeastern Bottling Co., Inc.', but it is clearly identified as one of the four direct-sale customers.
- **GPT-5.5: Pass.** The memorandum lists Southeastern Bottling as a key customer/non-party and includes a Feb. 5, 2024 invoice/direct sale to Southeastern Bottling in Nashville for $1,550,000, identifying it as one of the alleged direct-sale customers.

### C-038

Total alleged direct sales stated as $4,260,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L315))

- **Sonnet 4.6: Pass.** The memorandum repeatedly states the total alleged direct sales as $4.26M (e.g., 'All four invoices in Exhibit E (Nov. 15, 2023 to Feb. 5, 2024; $4.26M total)' and '$870K + $1.2M + $640K + $1.55M = $4.26M'). However, the criterion requires the total to be stated as $4,260,000, which is the sum of $870,000 + $1,200,000 + $640,000 + $1,550,000. The memo uses $4.26M as shorthand, which equals $4,260,000. The individual invoices listed are $870,000 + $720,000 + $640,000 + $480,000 + $1,550,000 = $4,260,000 (five invoices). The criterion specifies the sum as $870,000 + $1,200,000 + $640,000 + $1,550,000 = $4,260,000 (four items). The memo's arithmetic table shows '$870K + $1.2M + $640K + $1.55M = $4.26M' which matches the criterion's formula. The total $4.26M = $4,260,000 is correctly stated in the memorandum.
- **GPT-5.5: Pass.** The memorandum repeatedly states the alleged direct sales total as $4.26M, including the sum of $870K + $1.2M + $640K + $1.55M, which is equivalent to $4,260,000.

### C-039

Brandon Kelsey identified as hired-away employee (former Southeast Regional Sales Manager at Apex) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L323))

- **Sonnet 4.6: Fail.** The memorandum identifies Brandon Kelsey as a former Apex employee hired by Greenfield (e.g., 'Brandon Kelsey and Lauren Ostrowski (former Apex employees, now at Greenfield)'). However, the criterion requires that Kelsey be identified specifically as the 'Southeast Regional Sales Manager' at Apex. The memo never mentions his title or role at Apex. It only identifies him as a former Apex employee. Therefore, the criterion is not fully satisfied.
- **GPT-5.5: Fail.** The memorandum identifies Brandon Kelsey as a former Apex employee hired by Greenfield, but it does not identify him as Apex’s former Southeast Regional Sales Manager as required by the criterion.

### C-040

Lauren Ostrowski identified as hired-away employee (former Senior Technical Account Executive at Apex) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L331))

- **Sonnet 4.6: Fail.** The memorandum identifies Lauren Ostrowski as a former Apex employee hired by Greenfield in multiple places (e.g., 'Brandon Kelsey and Lauren Ostrowski (former Apex employees, now at Greenfield)' in the Case Snapshot, and references throughout). However, the criterion specifically requires that she be identified as a 'Senior Technical Account Executive at Apex.' The memo never mentions her job title at Apex. It only identifies her as a 'former Apex employee.' Since the specific title 'Senior Technical Account Executive' is not present in the memo, the criterion is not fully satisfied.
- **GPT-5.5: Fail.** The memorandum identifies Lauren Ostrowski as a former Apex employee hired by/now at Greenfield, but it does not identify her specific former role as Senior Technical Account Executive at Apex.

### C-041

Confidential Sales Information components described ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L339))

- **Sonnet 4.6: Pass.** The memorandum discusses the alleged trade secrets under Count III and in the context of Count II. In the Count III analysis, it states: 'What remains potentially secret is Apex's resale pricing, discounts, and pipeline data.' This references pricing (pricing matrices/customer-specific discount structures) and pipeline data (sales pipeline forecasts). It also references 'Confidential Sales Information' explicitly in Count II ('Paragraph 90(b) relies on misuse of Apex's Confidential Sales Information') and in the TRO section ('return or destruction of Apex's Confidential Sales Information'). The memo identifies at least two specific components: resale pricing/discounts and pipeline data, satisfying the criterion of referencing at least two of the listed components.
- **GPT-5.5: Pass.** The memorandum refers to Apex's alleged Confidential Sales Information and describes specific components including Apex's resale pricing/discounts and pipeline data, which correspond to pricing/discount structures and sales pipeline forecasts. This satisfies the requirement to identify at least two specific alleged trade secret components.

### C-042

Injunctive relief: prohibition of further direct sales in Territory ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L347))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies that Apex seeks 'a ban on all Greenfield direct sales to any customer in the eight-state Territory' as part of the TRO/PI relief sought (Section VI). This is clearly described as component (a) of the injunctive relief Apex is seeking.
- **GPT-5.5: Pass.** The memorandum expressly states that Apex seeks a TRO/PI including “a ban on all Greenfield direct sales to any customer in the eight-state Territory” and elsewhere notes the requested relief is a ban on all direct sales in eight states.

### C-043

Injunctive relief: return/destruction of Confidential Sales Information ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L355))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Part VI (TRO/Preliminary Injunction Analysis) that Apex seeks '(b) return or destruction of Apex's Confidential Sales Information, supervised by a neutral.' This directly identifies the injunctive relief component requiring return or destruction of Confidential Sales Information.
- **GPT-5.5: Pass.** The memorandum expressly states in the TRO/PI section that Apex seeks “return or destruction of Apex’s Confidential Sales Information, supervised by a neutral,” satisfying the criterion.

### C-044

Injunctive relief: prohibition on employing Kelsey/Ostrowski in Territory-related roles ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L363))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in Part VI (TRO/Preliminary Injunction Analysis) that Apex seeks '(c) a bar on employing Kelsey and Ostrowski in any Territory-related role.' This is further discussed in the TRO analysis table under 'Relief (c): employees' and in the recommended TRO strategy section, which advises opposing this relief outright.
- **GPT-5.5: Pass.** The memorandum expressly states that Apex seeks injunctive relief including “a bar on employing Kelsey and Ostrowski in any Territory-related role,” satisfying the criterion.

### C-045

Attorneys' fees claim under Section 14.2 noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L371))

- **Sonnet 4.6: Pass.** The memorandum explicitly mentions Section 14.2 in multiple places. In Count I analysis: 'Apex also seeks specific performance and § 14.2 fees.' In the partial defenses section: 'Fee shifting (§ 14.2) runs in both directions and covers "attorneys\ fees, expert witness fees, and costs." If Apex prevails on Count I, fee exposure could be significant.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly states under Count I that Apex seeks “§ 14.2 fees” and later describes § 14.2 as a fee-shifting provision covering attorneys’ fees, expert fees, and costs if Apex prevails.

### C-046

Attorneys' fees claim under Georgia Trade Secrets Act noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L379))

- **Sonnet 4.6: Pass.** The memorandum explicitly mentions attorneys' fees under the Georgia Trade Secrets Act in Part V.C: 'Fees are available for willful and malicious misappropriation (O.C.G.A. § 10-1-764) and, reciprocally, for a claim made in bad faith.' It also references this in Part VII.B: 'prevailing-party fees and expert costs under § 14.2 and fees under O.C.G.A. § 10-1-764.' This satisfies the criterion that the memo notes Apex seeks attorneys' fees under the Georgia Trade Secrets Act.
- **GPT-5.5: Pass.** The memo discusses Count III under the GTSA/DTSA and expressly notes that fees are available for willful and malicious misappropriation under O.C.G.A. § 10-1-764, and later lists fee exposure under that statute. This identifies the Georgia Trade Secrets Act basis for Apex’s attorneys’ fees claim.

### C-047

Eight-state exclusive territory identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L387))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the eight-state exclusive territory in the Case Snapshot section: '8-state Territory (GA, AL, TN, SC, NC, FL, MS, LA)' and also references 'eight Southeastern states' in the Executive Summary. All eight states (Georgia, Alabama, Tennessee, South Carolina, North Carolina, Florida, Mississippi, and Louisiana) are correctly listed.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the exclusive distribution territory as an eight-state Territory and lists GA, AL, TN, SC, NC, FL, MS, and LA, corresponding to Georgia, Alabama, Tennessee, South Carolina, North Carolina, Florida, Mississippi, and Louisiana.

### C-048

ISSUE_001: Defective first notice — Hargrove not authorized signatory ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L395))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the July 15, 2023 non-renewal letter signed by Hargrove (VP Sales) as defective under Section 4.2, which requires the CEO or General Counsel. This is discussed in detail in Section V.A under 'July 15 notice (signatory defect)' and also flagged in the Executive Summary and the chronology table.
- **GPT-5.5: Pass.** The memorandum explicitly flags that the July 15, 2023 non-renewal notice was signed by Thomas Hargrove, VP of Sales, rather than the CEO or General Counsel as required by Section 4.2, and treats this as a signatory defect rendering the notice void/defective and a key liability vulnerability.

### C-049

ISSUE_001: Greenfield did not cure the signatory defect until September 12 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L403))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the timeline: it notes the July 15, 2023 notice was signed by the VP of Sales (signatory defect), that Apex's counsel sent a letter on August 3, 2023 objecting to the signatory defect and flagging the August 31 deadline, that Greenfield never responded to that letter, and that the second notice was sent on September 12, 2023 (signed by CEO Ellsworth, 'supersedes and replaces' the July 15 letter). The memo also notes the failure to respond to the August 3 letter is 'a bad fact' and that Apex will use it to show Greenfield had nearly four weeks' warning. The timeline gap between the defective notice (July 15), Apex's objection (August 3), and the attempted cure (September 12) is clearly addressed.
- **GPT-5.5: Pass.** The memorandum identifies the July 15 notice as defective because it was signed by the VP of Sales, states that Apex objected by letter on August 3, 2023, and notes that Greenfield did not send the CEO-signed second notice until September 12, 2023. It also discusses the gap and missed opportunity to send a compliant notice before the deadline.

### C-050

ISSUE_002: Second notice was only 169 days before expiration ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L411))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in multiple places that the September 12, 2023 notice was sent 169 days before the February 28, 2024 expiration, which is 11 days short of the required 180-day period. In Part V.A it states: 'We confirm the math: September 12, 2023 to February 28, 2024 is 169 days' and 'The shortfall against the 180-day requirement is 11 days.' The Executive Summary also notes 'the September 12, 2023 notice came 169 days before expiration, not the required 180.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum explicitly states that the September 12, 2023 notice was 169 days before the February 28, 2024 expiration and identifies this as 11 days short of the required 180-day notice period, making it untimely.

### C-051

ISSUE_002: Auto-renewal through February 28, 2026 is Apex's position ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L419))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the Executive Summary: 'We should plan on the Agreement being found to have renewed through February 28, 2026.' It also states in Count I analysis: 'Both non-renewal notices were void under § 4.2. The Agreement therefore renewed through February 28, 2026.' The Case Snapshot table also notes: 'Under Apex's theory, the Agreement renews through Feb. 28, 2026.' The auto-renewal consequence of the defective notices is clearly explained as Apex's position.
- **GPT-5.5: Pass.** The memorandum explicitly states Apex's theory that both non-renewal notices were void/defective and that the Agreement therefore automatically renewed through February 28, 2026.

### C-052

Year 2 shortfall of $2.1M identified ($7.1M actual vs. $9.2M minimum) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L427))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the chronology table: 'Mar. 2020--Feb. 2021: Contract Year 2: Apex purchases $7.1M against a $9.2M minimum ($2.1M shortfall). No § 5.3 cure notice sent.' This directly identifies the Year 2 shortfall of $2.1M with the actual vs. minimum figures as required by the criterion.
- **GPT-5.5: Pass.** The memorandum expressly states that in Contract Year 2 Apex purchased $7.1M against a $9.2M minimum, resulting in a $2.1M shortfall, and reiterates the Year 2 shortfall elsewhere.

### C-053

Greenfield's failure to send 60-day cure notice for Year 2 shortfall identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L435))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section V.A under Count I analysis: 'Section 5.3 makes a single-year miss a "Curable Default" and bars § 12.1(b) termination unless written notice and a 60-day cure period were first provided. None was given.' This directly identifies that Greenfield never sent the required 60-day cure notice for the Year 2 shortfall.
- **GPT-5.5: Pass.** The memorandum explicitly notes the Year 2 shortfall and states that no § 5.3 cure notice was sent, and later explains that termination based on the shortfall is unavailable because no written notice and 60-day cure period were provided.

### C-054

Waiver implication from absent cure notice discussed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L443))

- **Sonnet 4.6: Pass.** The memorandum explicitly discusses the Year 2 shortfall and waiver in Section V.A under Count I. It states: 'Greenfield also kept accepting performance for three more years, and Apex exceeded its cumulative minimums ($55.7M vs. $54.0M, a $1.7M surplus; math verified). Apex will argue waiver or estoppel by course of dealing, and it will probably succeed.' It also notes that no cure notice was sent ('Section 5.3 makes a single-year miss a "Curable Default" and bars § 12.1(b) termination unless written notice and a 60-day cure period were first provided. None was given.') and that the shortfall is 'effectively unavailable' as a termination ground. The memo clearly connects the failure to send a cure notice with the waiver implication, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum expressly discusses the Year 2 shortfall, states that no § 5.3 cure notice was sent, explains that termination was barred absent written notice and a 60-day cure period, and concludes Apex would likely succeed on waiver/estoppel due to Greenfield continuing to accept performance.

### C-055

ISSUE_003: Year 2 shortfall undermines Greenfield's material breach defense ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L451))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the Year 2 shortfall in Section V.A under Count I. It states: 'As a termination ground, the shortfall is effectively unavailable. Section 5.3 makes a single-year miss a "Curable Default" and bars § 12.1(b) termination unless written notice and a 60-day cure period were first provided. None was given.' This directly addresses the criterion that because Greenfield never sent the cure notice, it would be difficult to assert Apex was in material breach. The memo further notes that Greenfield kept accepting performance for three more years and that Apex exceeded cumulative minimums, and concludes 'A single cured-in-substance shortfall four years before the dispute is unlikely to show that Apex materially breached first.'
- **GPT-5.5: Pass.** The memorandum expressly discusses the Year 2 shortfall, states that no § 5.3 cure notice was sent, and concludes that the shortfall is effectively unavailable as a termination/material-breach defense and unlikely to show Apex materially breached first.

### C-056

ISSUE_004: Exemplary damages statutory characterization flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L459))

- **Sonnet 4.6: Fail.** The criterion requires the memo to flag that the complaint's characterization of exemplary damages as 'double damages' is imprecise or misleading under O.C.G.A. § 10-1-763, which caps exemplary damages at the amount of actual damages (not a multiplier). The memo does note that 'GTSA/DTSA exemplary damages can be up to twice actual damages (O.C.G.A. § 10-1-763; 18 U.S.C. § 1836(b)(3)(C))' and that 'Apex claimed only 1x ($3.4M), so the statutory ceiling on this count is $10.2M.' However, the memo does not flag that characterizing this as 'double damages' or a 'double the actual damages' multiplier is imprecise or misleading. The memo simply states the statutory cap is 'up to twice actual damages' without noting any nuance about the statute's actual language or that the complaint's characterization is imprecise. The criterion specifically requires identifying that the complaint characterizes exemplary damages as 'double damages' and flagging that this is an imprecise or misleading characterization of the statute. The memo does not address this specific nuance.
- **GPT-5.5: Fail.** The memorandum notes the arithmetic of $3.4M actual plus $3.4M exemplary, but it does not flag the complaint’s “double damages” characterization as imprecise or misleading. Instead, it affirmatively states that GTSA exemplary damages can be “up to twice actual damages” and describes a higher statutory ceiling, which is contrary to the specified nuance for O.C.G.A. § 10-1-763.

### C-057

ISSUE_005: Double recovery risk between Counts I and II ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L467))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the overlap between Count I and Count II damages. In Section V.B (Count II analysis), it states: 'The $6.2M NPV of the four customers' future revenue is embedded in Count I's $16.1M/year projection for the Renewal Term, which includes these same accounts.' It further notes in Section VII.A that the complaint 'Aggregates overlapping and alternative theories.' The memo also states in the favorable scenario that 'Count II subsumed' and in the damages table notes 'overlaps Count I' for Count II. This clearly flags the double-recovery risk between Counts I and II regarding the same lost customer relationships.
- **GPT-5.5: Pass.** The memorandum expressly identifies that Count II’s $6.2M NPV for the four customers overlaps with Count I’s renewal-term lost profits, stating that the same accounts are embedded in Count I’s projections and flagging the double-counting/damages overlap risk.

### C-058

ISSUE_006: Choice of law vs. forum selection complexity identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L475))

- **Sonnet 4.6: Pass.** The memorandum extensively addresses the choice-of-law vs. forum selection complexity. Section 16.1 selects Georgia law for the Distribution Agreement while Section 16.3 selects North Carolina courts. The memo discusses: (1) NC procedural law applying alongside GA substantive law; (2) that tort claims may follow lex loci delicti rather than the contractual choice of law (Part V.B); (3) that the employment agreements have their own Georgia choice-of-law clause (§12) separate from the Distribution Agreement (Part VIII); (4) the tension between Georgia's Restrictive Covenants Act and NC's stricter non-compete scrutiny; (5) GTSA/DTSA displacement issues; and (6) different choice-of-law analyses for trade secret vs. contract claims. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum identifies the Georgia governing-law clause for the Distribution Agreement and Mecklenburg/NC forum clause, applies North Carolina procedural rules and TRO standards, and separately discusses choice-of-law complexity for tort claims and the Kelsey/Ostrowski employment non-competes, including that those agreements are separate and may require a different analysis under NC choice-of-law rules. This satisfies the criterion.

### C-059

ISSUE_007: TRO hearing precedes answer deadline — urgency flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L483))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the timing relationship between the TRO hearing (May 9, 2025) and the answer deadline (May 27, 2025) in multiple places. In Part III, under 'Priority (response to Ms. Yuen),' it states: 'The TRO opposition takes priority' and 'The TRO hearing does not waive or shorten the answer deadline. Opposing the TRO without first answering does not box us in, as long as we: (i) preserve the removal option...; (ii) get a Rule 6(b) extension of the answer deadline; and (iii) avoid factual concessions in the TRO papers that would bind us in the answer.' The memo also notes in the deadlines table that the TRO/PI opposition brief should be filed by ~May 6-7, 2025, well before the May 27 answer deadline. The executive summary also flags the TRO hearing as an immediate deadline requiring priority attention. This clearly satisfies the criterion of flagging that the TRO hearing precedes the answer deadline and creates urgent time pressure.
- **GPT-5.5: Pass.** The memo identifies the TRO/PI hearing as May 9, 2025 and the answer deadline as May 27, 2025, lists TRO opposition/preparation as an immediate priority, and expressly states that the TRO opposition takes priority and must be prepared before the answer deadline. It also notes the TRO hearing does not waive or shorten the answer deadline, showing the timing issue was recognized.

### C-060

ISSUE_008: Unjust enrichment generally unavailable alongside express contract ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L491))

- **Sonnet 4.6: Pass.** In Section V.D (Count IV: Unjust Enrichment), the memorandum explicitly states: 'Under Georgia law, unjust enrichment is generally unavailable where an express contract covers the subject matter. Both sides agree the Agreement exists and governs exclusivity.' This directly satisfies the criterion requiring identification that Count IV is vulnerable to dismissal because an express contract (the Distribution Agreement) covers the same subject matter and that Georgia law generally bars unjust enrichment in such circumstances.
- **GPT-5.5: Pass.** The memorandum expressly states in the Count IV section that under Georgia law unjust enrichment is generally unavailable where an express contract covers the subject matter, and notes that both sides agree the Distribution Agreement exists and governs exclusivity. It also identifies Count IV as a strong candidate for dismissal.

### C-061

ISSUE_009: Count I lost profits calculation verified ($16.1M × 22% × 2 = $7,084,000) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L499))

- **Sonnet 4.6: Pass.** In Part VII.A, the memorandum includes a table row for 'Count I: Renewal lost profits' that states '$16.1M × 22% × 2 = $7,084,000' and marks it as 'Math correct,' explicitly verifying the calculation and reciting all three components ($16.1M, 22%, 2 years) along with the result ($7,084,000).
- **GPT-5.5: Pass.** The memorandum recites the Count I lost profits components and independently verifies the arithmetic in the damages table: “$16.1M × 22% × 2 = $7,084,000” and marks it “Math correct.”

### C-062

ISSUE_009: Count I lost commissions verified ($4,260,000 × 18% = $766,800) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L507))

- **Sonnet 4.6: Pass.** In Part VII.A (Arithmetic verification of the complaint), the memorandum includes a row for 'Count I: Lost commissions' showing '$4.26M × 18% = $766,800' with 'Math correct' in the Verified column. This explicitly and independently verifies the calculation $4,260,000 × 18% = $766,800.
- **GPT-5.5: Pass.** The memorandum includes an arithmetic verification table stating “Count I: Lost commissions $4.26M × 18% = $766,800” and marks the math as correct.

### C-063

ISSUE_009: Count IV unjust enrichment verified ($4,260,000 × 35% = $1,491,000) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L515))

- **Sonnet 4.6: Pass.** In Part VII.A (Arithmetic verification of the complaint), the memorandum includes a row for Count IV: Unjust Enrichment showing '$4.26M × 35% = $1,491,000' with 'Math correct' in the Verified column. This independently verifies the calculation as required by the criterion.
- **GPT-5.5: Pass.** The memorandum explicitly verifies the Count IV unjust enrichment calculation, stating Greenfield's ~35% margin on $4.26M equals $1,491,000 and marking the math as verified/correct in the damages table.

### C-064

ISSUE_010: Enforceability of 24-month non-competes flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L523))

- **Sonnet 4.6: Pass.** Section VIII of the memorandum explicitly addresses the Kelsey and Ostrowski 24-month non-competition agreements. It identifies the agreements (citing Ex. F, 24-month non-compete, non-solicit, confidentiality; GA law), discusses enforceability under the Georgia Restrictive Covenants Act (O.C.G.A. § 13-8-50 et seq., specifically referencing § 13-8-57 on the 2-year presumption, § 13-8-51/-53 on sales employees, and § 13-8-53(d)/-54 on blue-penciling), contrasts with North Carolina's stricter scrutiny, and flags relevance to the injunctive relief (requested employment restrictions) and the trade secret/tortious interference claims. This satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum identifies Kelsey’s and Ostrowski’s 24-month non-compete agreements, devotes a section to their choice-of-law/enforceability issues, discusses the Georgia Restrictive Covenants Act including reasonableness/blue-penciling considerations under O.C.G.A. § 13-8-53, contrasts North Carolina law, and ties the issue to Apex’s requested injunction and related litigation risks including trade secret/injunctive relief strategy.

### C-065

Chronological timeline of material events included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L531))

- **Sonnet 4.6: Pass.** The memorandum includes a detailed chronological timeline in Section IV ('Factual Background and Chronology') that covers all ten required dates: March 1, 2019 (Agreement executed), July 15, 2023 (non-renewal letter by Hargrove), August 3, 2023 (Apex counsel's letter), September 12, 2023 (second non-renewal letter), ~October 2023 (direct sales campaign begins), February 2024 (Kelsey and Ostrowski hired), April 22, 2025 (complaint filed), April 25, 2025 (service on registered agent), May 9, 2025 (TRO/PI hearing), and May 27, 2025 (answer deadline, referenced in Section III). All ten dates are present and presented in chronological order.
- **GPT-5.5: Pass.** The memorandum includes a dedicated chronological factual chronology with the required key events: March 1, 2019 agreement, July 15, 2023 first notice, August 3, 2023 Apex response, September 12, 2023 second notice, October 2023 direct sales, February 2024 hires, April 22, 2025 complaint, April 25, 2025 service, and May 9, 2025 TRO hearing. It also includes the May 27, 2025 answer deadline in the critical deadlines table. No required dates are missing.

### C-066

Damages analysis presented in structured format (table or breakdown) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L539))

- **Sonnet 4.6: Pass.** The memorandum includes Part VII (Damages and Exposure Assessment) which contains two structured tables: (1) 'Arithmetic verification of the complaint' — a table listing each count/component with the complaint's claimed amount, whether the math was verified, and issues with the methodology; and (2) 'Preliminary exposure range' — a table showing favorable, most likely adverse, and severe scenarios with key assumptions and estimated ranges. The first table explicitly covers Count I (renewal lost profits and lost commissions), Count II (customer NPV), Count III (actual + exemplary), Count IV (unjust enrichment), and the total, each with calculation methodology and claimed dollar amounts. This satisfies the criterion of a structured format (table) showing each count's damage components with calculation methodology and claimed dollar amount.
- **GPT-5.5: Pass.** The memorandum includes a structured damages table in Section VII.A that breaks down the claimed damages by count, including calculation methodology and dollar amounts for Count I, Count II, Count III, and Count IV.

### C-067

Immediate action items section with TRO preparation prioritized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L547))

- **Sonnet 4.6: Pass.** The memorandum includes a dedicated Section XI titled 'Recommended Immediate Action Items' with a numbered table of actions, owners, and timing. TRO preparation is explicitly prioritized: Action Item #5 is 'Draft TRO/PI opposition and declarations; evaluate a narrow stipulated confidentiality order' with a target filing of May 6-7. Additionally, the Executive Summary and Section III both emphasize the TRO opposition as the top priority, stating 'The TRO opposition takes priority.' The action items section clearly identifies TRO preparation as among the most urgent tasks, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum includes a dedicated 'Recommended Immediate Action Items' section and expressly states that the TRO opposition takes priority, with TRO/PI preparation, declarations, and filing targeted before the May 9 hearing identified as urgent tasks.

### C-068

Answer filing identified as an action item by May 27, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L555))

- **Sonnet 4.6: Pass.** In Section XI (Recommended Immediate Action Items), item #8 states: 'Answer / Rule 12 motions and counterclaim' with timing 'May 27 (or extended date)'. This clearly identifies filing the answer by May 27, 2025 as an action item.
- **GPT-5.5: Pass.** The memorandum lists “Answer / Rule 12 motions and counterclaim” as Immediate Action Item #8 with timing “May 27 (or extended date),” and also identifies the state-court answer deadline as May 27, 2025.

### C-069

Client GC admissions from email extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L563))

- **Sonnet 4.6: Pass.** The memorandum repeatedly references Patricia Yuen's email and extracts candid admissions from it. Specifically: (1) It notes that the July 15 notice was 'signed by the VP of Sales, not the CEO or General Counsel as § 4.2 requires' and that 'Ms. Yuen reports that Hargrove acted without authorization and that neither she nor the CEO knew of the letter until August 3' — directly referencing her admission that Hargrove sent it without her review. (2) It references 'Ms. Yuen's email concedes most of the key facts' regarding the notice defects. (3) It references the Year 2 shortfall and notes 'No § 5.3 cure notice sent' with 'Yuen email' as the source, indicating she acknowledged it was never formally addressed. (4) It notes Hargrove was 'eager to begin Greenfield's direct sales efforts' per Ms. Yuen's report. The memo does not explicitly use the phrase 'rushed out' for the second letter, but it does reference the timing defect and Yuen's email as a source for key admissions. The criterion is satisfied as the memo clearly references and extracts candid admissions from Yuen's email on the key points mentioned.
- **GPT-5.5: Pass.** The memorandum explicitly references Patricia Yuen’s email and extracts candid admissions, including that Hargrove sent the July 15 non-renewal letter on his own initiative without GC review and that no cure notice was sent for the Year 2 shortfall. This satisfies the criterion even though it does not specifically quote 'rushed out.'

### C-070

24-month non-compete/non-solicitation agreements of Kelsey and Ostrowski noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L571))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the chronology section: 'Mar. 15, 2020 - Kelsey Employment Agreement (24-mo. non-compete, non-solicit, confidentiality; GA law)' and 'June 1, 2021 - Ostrowski Employment Agreement (same terms)'. This clearly identifies that both Kelsey and Ostrowski had 24-month post-employment non-competition and non-solicitation agreements with Apex.
- **GPT-5.5: Pass.** The memorandum expressly notes that Kelsey had a “24-mo. non-compete, non-solicit” employment agreement and that Ostrowski’s agreement had the same terms, satisfying the requirement to identify both the existence and 24-month duration of their post-employment non-compete/non-solicitation agreements with Apex.

### C-071

Apex's alleged renewal period identified as through February 28, 2026 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L579))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in multiple places that Apex's theory is that the Agreement renewed through February 28, 2026. For example, in the Executive Summary: 'We should plan on the Agreement being found to have renewed through February 28, 2026.' It also appears in the Case Snapshot, Count I analysis, and other sections.
- **GPT-5.5: Pass.** The memorandum repeatedly states that Apex alleges the Agreement renewed through February 28, 2026, including in the Executive Summary, chronology, and Count I analysis.

### C-072

Apex's 22% gross margin on Greenfield products noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L587))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the damages table under Part VII.A: 'Count I: Renewal lost profits: $16.1M × 22% × 2 = $7,084,000' and in Part VII.B under the Favorable scenario: 'Liability limited to Initial-Term exclusivity breach on $4.26M (Apex margin 18–22%: ~$0.77M–$0.94M)'. The 22% gross margin figure attributed to Apex on Greenfield products is clearly identified in the memo.
- **GPT-5.5: Pass.** The memorandum explicitly states the 22% margin in the damages section: “$16.1M × 22% × 2” and describes it as a gross margin issue.

### C-073

Apex's 18% commission rate on Territory sales noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L595))

- **Sonnet 4.6: Pass.** The memorandum explicitly states the 18% commission rate multiple times. In the Executive Summary: 'It relies on an "18% commission rate" that does not fit a buy-resell distributor and does not appear in the Agreement excerpts.' In the damages table: 'Count I: Lost commissions $4.26M × 18% = $766,800' with the note '"Contractual commission rate" not in Ex. A excerpts.' The 18% rate on Territory sales is clearly identified.
- **GPT-5.5: Pass.** The memorandum explicitly notes an "18% commission rate" and calculates lost commissions as $4.26M × 18% for Territory direct sales.

### C-074

Greenfield's alleged 35% margin on direct sales noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L603))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Count IV analysis: 'The measure (Greenfield's ~35% margin on $4.26M = $1,491,000, math verified)' and in the damages table: 'Count IV: Unjust enrichment $4.26M × 35% = $1,491,000'. The 35% margin figure is clearly identified.
- **GPT-5.5: Pass.** The memorandum expressly notes Greenfield's alleged margin on direct sales as approximately 35%, including in the unjust enrichment discussion and damages table.

### C-075

Kelsey/Ostrowski employment agreements governed by Georgia law noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L611))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section VIII: 'Their own § 12 selects Georgia law' referring to the Kelsey and Ostrowski employment agreements. It also notes 'both employees resided in Georgia when they signed' and discusses the Georgia Restrictive Covenants Act as the applicable law. The memo clearly identifies that the employment agreements are governed by Georgia law.
- **GPT-5.5: Pass.** The memorandum expressly notes that Kelsey and Ostrowski's employment agreements are governed by Georgia law, including in the case snapshot, chronology, and a dedicated section stating their agreements select Georgia law.
