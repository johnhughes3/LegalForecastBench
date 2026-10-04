# GPT-6 Luna (xhigh): Extract Key Terms from Counterparty Complaint — Litigation Summary Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-key-terms-from-counterparty-complaint/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 56 of 75 criteria; GPT-5.5 passed 58 of 75 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [litigation-summary-memo.docx](output/litigation-summary-memo.docx) ([read as Markdown](output/litigation-summary-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Case number correctly identified as 25-CVS-4471 | Pass | Pass |
| [C-002](#c-002) | Court identified as Superior Court of Mecklenburg County, NC | Pass | Pass |
| [C-003](#c-003) | Judge identified as Hon. Robert L. Vanderhorst | Pass | Pass |
| [C-004](#c-004) | Plaintiff correctly identified as Apex Industrial Solutions, LLC | **Fail** | Pass |
| [C-005](#c-005) | Defendant correctly identified as Greenfield Dynamics, Inc. | **Fail** | **Fail** |
| [C-006](#c-006) | Plaintiff's law firm identified as Whitlock Stein & Marsh, P.A. | **Fail** | **Fail** |
| [C-007](#c-007) | Plaintiff's lead attorney identified as Reginald Whitlock | **Fail** | **Fail** |
| [C-008](#c-008) | Defense counsel firm identified as Harmon & Lyle LLP | **Fail** | **Fail** |
| [C-009](#c-009) | Defense lead partner identified as Catherine Ng | **Fail** | **Fail** |
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
| [C-025](#c-025) | Section 4.2 auto-renewal provision extracted | **Fail** | Pass |
| [C-026](#c-026) | Section 4.2 180-day advance written notice requirement extracted | Pass | Pass |
| [C-027](#c-027) | Non-renewal notice deadline of August 31, 2023 identified | Pass | Pass |
| [C-028](#c-028) | Section 4.2 signatory requirement (CEO or General Counsel) extracted | Pass | Pass |
| [C-029](#c-029) | Section 5.1 minimum purchase commitments extracted | **Fail** | **Fail** |
| [C-030](#c-030) | Section 5.3 curable default and 60-day cure notice requirement extracted | Pass | Pass |
| [C-031](#c-031) | Section 16.1 Georgia choice of law extracted | Pass | Pass |
| [C-032](#c-032) | Section 16.3 Mecklenburg County forum selection extracted | **Fail** | **Fail** |
| [C-033](#c-033) | Section 14.2 prevailing party fee-shifting provision extracted | **Fail** | **Fail** |
| [C-034](#c-034) | Magnolia Foods Processing, Inc. identified as direct-sale customer | **Fail** | Pass |
| [C-035](#c-035) | Tidewater Pharmaceutical Group, LLC identified as direct-sale customer | **Fail** | **Fail** |
| [C-036](#c-036) | Clearwater Chemical Partners, LP identified as direct-sale customer | **Fail** | **Fail** |
| [C-037](#c-037) | Southeastern Bottling Co., Inc. identified as direct-sale customer | **Fail** | **Fail** |
| [C-038](#c-038) | Total alleged direct sales stated as $4,260,000 | Pass | Pass |
| [C-039](#c-039) | Brandon Kelsey identified as hired-away employee (former Southeast Regional Sales Manager at Apex) | **Fail** | **Fail** |
| [C-040](#c-040) | Lauren Ostrowski identified as hired-away employee (former Senior Technical Account Executive at Apex) | **Fail** | **Fail** |
| [C-041](#c-041) | Confidential Sales Information components described | Pass | Pass |
| [C-042](#c-042) | Injunctive relief: prohibition of further direct sales in Territory | Pass | Pass |
| [C-043](#c-043) | Injunctive relief: return/destruction of Confidential Sales Information | Pass | Pass |
| [C-044](#c-044) | Injunctive relief: prohibition on employing Kelsey/Ostrowski in Territory-related roles | Pass | Pass |
| [C-045](#c-045) | Attorneys' fees claim under Section 14.2 noted | **Fail** | **Fail** |
| [C-046](#c-046) | Attorneys' fees claim under Georgia Trade Secrets Act noted | Pass | Pass |
| [C-047](#c-047) | Eight-state exclusive territory identified | Pass | Pass |
| [C-048](#c-048) | ISSUE_001: Defective first notice — Hargrove not authorized signatory | Pass | Pass |
| [C-049](#c-049) | ISSUE_001: Greenfield did not cure the signatory defect until September 12 | Pass | Pass |
| [C-050](#c-050) | ISSUE_002: Second notice was only 169 days before expiration | Pass | Pass |
| [C-051](#c-051) | ISSUE_002: Auto-renewal through February 28, 2026 is Apex's position | Pass | Pass |
| [C-052](#c-052) | Year 2 shortfall of $2.1M identified ($7.1M actual vs. $9.2M minimum) | Pass | **Fail** |
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
| [C-070](#c-070) | 24-month non-compete/non-solicitation agreements of Kelsey and Ostrowski noted | **Fail** | **Fail** |
| [C-071](#c-071) | Apex's alleged renewal period identified as through February 28, 2026 | Pass | Pass |
| [C-072](#c-072) | Apex's 22% gross margin on Greenfield products noted | Pass | Pass |
| [C-073](#c-073) | Apex's 18% commission rate on Territory sales noted | Pass | Pass |
| [C-074](#c-074) | Greenfield's alleged 35% margin on direct sales noted | Pass | Pass |
| [C-075](#c-075) | Kelsey/Ostrowski employment agreements governed by Georgia law noted | Pass | Pass |

## Judge reasoning

### C-001

Case number correctly identified as 25-CVS-4471 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L19))

- **Sonnet 4.6: Pass.** The memorandum header clearly states 'Apex Industrial Solutions, LLC v. Greenfield Dynamics, Inc. | Mecklenburg County Superior Court | No. 25-CVS-4471', which matches the required case number exactly.
- **GPT-5.5: Pass.** The memorandum states the case number as “No. 25-CVS-4471” in the caption, which matches the required case number.

### C-002

Court identified as Superior Court of Mecklenburg County, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L27))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies the court as 'Mecklenburg County Superior Court' in the case caption and repeatedly references 'Mecklenburg County Superior Court' throughout the document, including in the procedural posture section and the TRO/PI hearing details. This matches the criterion of identifying the court as the Superior Court of Mecklenburg County, North Carolina.
- **GPT-5.5: Pass.** The memorandum identifies the forum in the caption as “Mecklenburg County Superior Court” and later as “North Carolina Superior Court, Mecklenburg County,” which materially identifies the court as the Superior Court of Mecklenburg County, North Carolina.

### C-003

Judge identified as Hon. Robert L. Vanderhorst ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L35))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the judge as 'Judge Robert L. Vanderhorst' in the Executive Assessment section and again in the TRO/PI hearing row of the procedural posture table, matching the criterion of Hon. Robert L. Vanderhorst.
- **GPT-5.5: Pass.** The memorandum identifies the May 9 hearing as before Judge Robert L. Vanderhorst, correctly naming the assigned judge.

### C-004

Plaintiff correctly identified as Apex Industrial Solutions, LLC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L43))

- **Sonnet 4.6: Fail.** The memorandum identifies the plaintiff as 'Apex Industrial Solutions, LLC' in the case caption ('Apex Industrial Solutions, LLC v. Greenfield Dynamics, Inc.') and throughout the document. However, the criterion requires identification as a Georgia LLC specifically. The memorandum does not identify Apex as a Georgia LLC anywhere in the text. In fact, Section 3C notes that 'Diversity cannot be assessed without Apex's members' citizenship,' and Section 8 asks about 'all members' citizenships of Apex for diversity,' suggesting the state of organization/citizenship is unknown or unconfirmed. The plaintiff is identified by name but not as a Georgia LLC.
- **GPT-5.5: Pass.** The memorandum identifies the plaintiff in the case caption and throughout as Apex Industrial Solutions, LLC. Although it does not expressly state that Apex is a Georgia LLC, it is not misidentified.

### C-005

Defendant correctly identified as Greenfield Dynamics, Inc. ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L51))

- **Sonnet 4.6: Fail.** The memorandum clearly identifies Greenfield Dynamics, Inc. as the defendant/client throughout the document. However, the criterion requires identification as a Delaware corporation, and the memorandum does not specify Greenfield Dynamics, Inc.'s state of incorporation. The document mentions that diversity jurisdiction cannot be assessed without Apex's members' citizenship, but never states Greenfield is a Delaware corporation. Since the criterion specifically requires identification as a Delaware corporation and the memo does not include this detail, the criterion is not fully satisfied.
- **GPT-5.5: Fail.** The memorandum identifies Greenfield Dynamics, Inc. as the defendant/client, but it does not identify Greenfield Dynamics, Inc. as a Delaware corporation. The criterion requires identification as Greenfield Dynamics, Inc., a Delaware corporation.

### C-006

Plaintiff's law firm identified as Whitlock Stein & Marsh, P.A. ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L59))

- **Sonnet 4.6: Fail.** The memorandum does not mention Whitlock Stein & Marsh, P.A. or any plaintiff's law firm name anywhere in the document.
- **GPT-5.5: Fail.** The memorandum does not identify plaintiff's counsel/law firm as Whitlock Stein & Marsh, P.A.; the firm name is absent.

### C-007

Plaintiff's lead attorney identified as Reginald Whitlock ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L67))

- **Sonnet 4.6: Fail.** The memorandum does not mention Reginald Whitlock anywhere. The document references Patricia Yuen (General Counsel), Marcus Ellsworth (CEO), Thomas Hargrove (VP of Sales), and other individuals, but Reginald Whitlock is not named as plaintiff's lead attorney or in any other capacity.
- **GPT-5.5: Fail.** The memorandum does not name Reginald Whitlock or identify him as the plaintiff's lead attorney.

### C-008

Defense counsel firm identified as Harmon & Lyle LLP ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L75))

- **Sonnet 4.6: Fail.** The memorandum does not identify any defense counsel firm name. The FROM line simply states 'Litigation Counsel' with no firm name mentioned anywhere in the document. There is no reference to 'Harmon & Lyle LLP' anywhere in the output.
- **GPT-5.5: Fail.** The memorandum does not identify defense counsel as Harmon & Lyle LLP; it only states 'Litigation Counsel' and contains no firm name.

### C-009

Defense lead partner identified as Catherine Ng ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L83))

- **Sonnet 4.6: Fail.** The memorandum does not mention Catherine Ng anywhere. The memo is addressed to Patricia Yuen (General Counsel) and Marcus Ellsworth (CEO), and is from 'Litigation Counsel' without naming a specific lead partner. Catherine Ng is not identified anywhere in the document.
- **GPT-5.5: Fail.** The memorandum does not identify Catherine Ng as the lead partner for the defense; her name does not appear in the output.

### C-010

Filing date of April 22, 2025 correctly stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L91))

- **Sonnet 4.6: Pass.** The memorandum explicitly states 'Apex filed its verified complaint and application for a temporary restraining order and preliminary injunction on April 22, 2025' in Section 1, and also references 'Complaint filed Apr. 22' in the chronology table. The filing date of April 22, 2025 is correctly stated.
- **GPT-5.5: Pass.** The memorandum explicitly states that Apex filed its verified complaint on April 22, 2025, and later reiterates that the complaint was filed Apr. 22.

### C-011

Service date of April 25, 2025 correctly stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L99))

- **Sonnet 4.6: Pass.** The memorandum explicitly states 'Service --- Apr. 25, 2025, 2:15 p.m.' in the procedural posture table and references 'the April 25 service affidavit' in the confidentiality notice, and 'service affidavit states service Apr. 25' in the chronology. The service date of April 25, 2025 is correctly and consistently stated throughout the document.
- **GPT-5.5: Pass.** The memorandum correctly states multiple times that service occurred on April 25, 2025, including noting the service affidavit and facially proper corporate service on April 25.

### C-012

Answer deadline correctly calculated as May 27, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L107))

- **Sonnet 4.6: Pass.** The memorandum explicitly states the answer deadline is May 27, 2025, and provides the correct reasoning: the 30-day period from April 25 runs to Sunday May 25, then Monday May 26 is Memorial Day, so the deadline extends to Tuesday May 27. This appears in both the procedural posture table and the action plan section.
- **GPT-5.5: Pass.** The memorandum explicitly states the answer/Rule 12 deadline is May 27, 2025, and explains that May 25 is Sunday and May 26 is Memorial Day, extending the deadline to Tuesday, May 27.

### C-013

TRO hearing date of May 9, 2025 correctly stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L115))

- **Sonnet 4.6: Pass.** The memorandum explicitly states the TRO/PI hearing is scheduled for May 9, 2025 at 10:00 a.m. before Judge Robert L. Vanderhorst, mentioned multiple times throughout the document.
- **GPT-5.5: Pass.** The memorandum repeatedly states that the TRO/preliminary-injunction hearing is scheduled for May 9, 2025, including the time of 10:00 a.m.

### C-014

Count I — Breach of Exclusive Distribution Agreement summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L123))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies Count I as 'breach of exclusive distribution agreement' in Section 4's claim-by-claim assessment table. It describes Apex's theory as invalid notices, direct sales, and failure to honor renewal, and explicitly frames this as a breach of contract claim under the Exclusive Distribution Agreement. The memo also discusses the non-renewal defense, direct sales during the Initial Term, and the contractual damages sought. This satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly identifies Count I as breach of the exclusive distribution agreement, describing Apex’s theory as invalid non-renewal notices/failure to honor renewal and direct sales, including direct sales in the exclusive Territory. It therefore satisfies the criterion.

### C-015

Count I lost profits damages stated as $7,084,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L131))

- **Sonnet 4.6: Pass.** The memorandum states in the damages table: 'Renewal lost profits: $16.1m annual sales × 22% × 2 years = $7.084m' and also references '$7.084m renewal lost profits' in the Count I row. This matches the criterion of $7,084,000 calculated as $16.1M × 22% × 2 years.
- **GPT-5.5: Pass.** The memorandum states Count I renewal lost profits as “$7.084m” and shows the calculation “$16.1m annual sales × 22% × 2 years = $7.084m,” which equals $7,084,000.

### C-016

Count I lost commissions damages stated as $766,800 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L139))

- **Sonnet 4.6: Pass.** The memorandum explicitly states '$766,800 direct-sale commissions' as part of Count I damages, and also states '18% × $4.26m = $766,800' in the damages table. This matches the criterion exactly.
- **GPT-5.5: Pass.** The memorandum expressly states Count I includes $766,800 in direct-sale/lost commissions and separately shows the calculation as 18% × $4.26m = $766,800.

### C-017

Count II — Tortious Interference legal theory summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L147))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies Count II as 'tortious interference with business relationships' and describes it as related to Greenfield's direct sales to four named Territory customers, alleged undercutting, and misuse of data. This appears in Section 4 (Claim-by-claim assessment) and is referenced in the executive assessment and other sections.
- **GPT-5.5: Pass.** The memorandum explicitly identifies Count II as “tortious interference with business relationships” and summarizes it as involving four named customer accounts and Greenfield’s direct sales/undercutting involving Apex accounts.

### C-018

Count II — Damages stated as $6,200,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L155))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the Count II row of the claim-by-claim assessment table: 'Four named customer accounts; alleged undercutting and misuse of data. $6.2m claimed NPV plus unspecified punitive damages.' $6.2m equals $6,200,000, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum identifies Count II (tortious interference) damages as “$6.2m claimed NPV,” which is equivalent to $6,200,000.

### C-019

Count III — Misappropriation of Trade Secrets summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L163))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies Count III as a trade-secret misappropriation claim under both the GTSA (Georgia Trade Secrets Act) and DTSA (federal Defend Trade Secrets Act), references the hiring of Kelsey and Ostrowski, and identifies the alleged confidential information (customer database, price matrices/discounts, and pipeline forecasts) as the subject of misappropriation. This appears in multiple sections including the claim-by-claim assessment table and the executive summary.
- **GPT-5.5: Pass.** The memorandum summarizes Count III as a trade-secret misappropriation claim under the GTSA/DTSA, identifies alleged confidential sales information such as customer databases, pricing/discount matrices, and pipeline forecasts, and discusses the hiring of Kelsey and Ostrowski in connection with the alleged misuse.

### C-020

Count III damages stated as $6,800,000 total ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L171))

- **Sonnet 4.6: Pass.** The memorandum states in the claim-by-claim assessment for Count III: '$3.4m replacement cost + $3.4m exemplary damages; injunction and fees.' This equals $6.8m total, which matches the $6,800,000 criterion. The damages table also lists '$3.4m replacement cost + $3.4m exemplary' for trade-secret damages. The $6.8m figure also appears in the damages arithmetic: '$7.8508m + $6.2m + $6.8m + $1.491m = $22.3418m', confirming Count III is stated as $6,800,000 total.
- **GPT-5.5: Pass.** The memorandum identifies Count III as seeking $3.4 million actual/replacement-cost damages plus $3.4 million exemplary damages, and elsewhere includes the Count III component as $6.8 million in the total arithmetic.

### C-021

Count IV — Unjust Enrichment summarized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L179))

- **Sonnet 4.6: Pass.** The memorandum clearly identifies Count IV as an unjust enrichment claim seeking disgorgement of Greenfield's estimated 35% profit on the $4.26m direct sales, calculating to $1,491,000. This appears in both the claim-by-claim assessment table and the damages framework section.
- **GPT-5.5: Pass.** The memorandum summarizes Count IV as an unjust enrichment claim seeking disgorgement of Greenfield's estimated 35% profit on $4.26 million in direct sales, totaling $1,491,000.

### C-022

Grand total damages verified as $22,341,800 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L187))

- **Sonnet 4.6: Pass.** The memorandum states the grand total as $22,341,800 (written as $22.3418m and $22.34m in various places) and verifies the arithmetic: '$7.8508m + $6.2m + $6.8m + $1.491m = $22.3418m.' However, the criterion requires verification as the sum of $7,084,000 + $766,800 + $6,200,000 + $6,800,000 + $1,491,000. The memo groups the first two items ($7,084,000 + $766,800 = $7,850,800) and presents the sum as $7.8508m, which matches. The total $22,341,800 is stated and the arithmetic is confirmed. The individual components are all present in the document (direct-sale commissions $766,800, renewal lost profits $7.084m, lost customer relationships $6.2m, trade-secret damages $3.4m + exemplary $3.4m = $6.8m, unjust enrichment $1.491m). The grand total of $22,341,800 is explicitly stated and the addition is verified in Section 5.
- **GPT-5.5: Pass.** The memorandum expressly states Apex pleads a total of $22,341,800 and independently confirms the arithmetic: $7.8508m ($7.084m renewal lost profits + $766,800 direct-sale commissions) + $6.2m + $6.8m + $1.491m = $22.3418m.

### C-023

Agreement effective date identified as March 1, 2019 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L195))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 2 (Key facts and chronology): 'Mar. 1, 2019 — Exclusive Distribution Agreement begins.' This correctly identifies the Distribution Agreement's effective date as March 1, 2019.
- **GPT-5.5: Pass.** The memorandum identifies March 1, 2019 as the date the Exclusive Distribution Agreement begins, satisfying the requirement to identify the effective date as March 1, 2019.

### C-024

Agreement initial term expiration identified as February 28, 2024 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L203))

- **Sonnet 4.6: Pass.** The memorandum explicitly states 'Five-year Initial Term ends Feb. 28, 2024' in the chronology section, and also references 'Feb. 28, 2024' as the date the Initial Term expires in multiple places throughout the document.
- **GPT-5.5: Pass.** The memorandum expressly states that the five-year Initial Term ends/expires on February 28, 2024 in multiple places, including the key facts chronology and renewal analysis.

### C-025

Section 4.2 auto-renewal provision extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L211))

- **Sonnet 4.6: Fail.** The memorandum references Section 4.2 multiple times, noting it requires notice at least 180 days before expiration, requires delivery by the CEO or General Counsel, and declares noncompliant notices void. However, the criterion specifically requires that Section 4.2 be identified as containing a 'two-year automatic renewal provision.' The memo does mention that if neither notice complied with Section 4.2, 'the Agreement automatically renewed through Feb. 28, 2026' (a two-year renewal from Feb. 28, 2024), but it attributes this automatic renewal to the agreement generally rather than specifically identifying Section 4.2 as the source of the auto-renewal provision. The memo discusses Section 4.2 primarily in the context of notice requirements and signatory requirements, not as the provision containing the auto-renewal mechanism. The auto-renewal consequence is mentioned but not tied explicitly to Section 4.2 as the auto-renewal provision itself. Given the criterion requires Section 4.2 to be identified as containing the two-year automatic renewal provision, and the memo does not make this explicit connection, this is a FAIL.
- **GPT-5.5: Pass.** The memorandum repeatedly references Section 4.2 and states that if the notices did not comply with it, the Agreement automatically renewed through February 28, 2026, i.e., a two-year renewal from the February 28, 2024 expiration date.

### C-026

Section 4.2 180-day advance written notice requirement extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L219))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the 180-day advance written notice requirement under Section 4.2 multiple times. For example, it states 'Section 4.2 requires notice at least 180 days before expiration' and discusses how Ellsworth's September 12 letter was '169 days before February 28, 2024---short of the 180-day requirement.' The requirement is clearly extracted and analyzed throughout the document.
- **GPT-5.5: Pass.** The memorandum expressly identifies that Section 4.2 requires non-renewal notice at least 180 days before expiration and analyzes the timing of the July and September notices against that requirement.

### C-027

Non-renewal notice deadline of August 31, 2023 identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L227))

- **Sonnet 4.6: Pass.** The memorandum mentions August 31 multiple times. In the executive assessment it states 'Apex's August 3 warning, followed by Greenfield's silence until after the deadline, is unfavorable evidence' and in the chronology section it states 'Apex counsel objects in writing to the signatory defect and identifies an Aug. 31 deadline.' The Section 3A analysis also states 'August 31 is 181 days before February 28' and 'The complaint's Aug. 31 deadline is one day early.' The memo explicitly identifies August 31, 2023 as the notice deadline (as pleaded in the complaint), even while noting it is one day off from the mathematically correct September 1 date. The criterion asks whether August 31, 2023 is mentioned as the notice deadline, and it clearly is.
- **GPT-5.5: Pass.** The memorandum explicitly mentions an “Aug. 31 deadline” in the chronology and discusses the complaint’s August 31 cutoff, even though it later disputes the date calculation.

### C-028

Section 4.2 signatory requirement (CEO or General Counsel) extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L235))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 3A: 'Section 4.2 requires notice at least 180 days before expiration, requires the notice to be delivered by the terminating party's CEO or General Counsel, and declares a notice that fails the signatory or timing requirements void and of no force or effect.' This clearly identifies the Section 4.2 signatory requirement (CEO or General Counsel).
- **GPT-5.5: Pass.** The memorandum explicitly states that Section 4.2 requires non-renewal notice to be delivered by the terminating party's CEO or General Counsel and notes that Hargrove was not an authorized signatory.

### C-029

Section 5.1 minimum purchase commitments extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L243))

- **Sonnet 4.6: Fail.** The memorandum references Section 5.2 (renewal minimum) and mentions the Year 2 shortfall ($7.1m purchases against a $9.2m minimum) and cumulative five-year purchases ($55.7m against $54m), but it never explicitly references Section 5.1 or lists the annual minimum purchase commitments for Years 1-5 ($8.0M, $9.2M, $10.6M, $12.2M, $14.0M). The criterion requires both the section reference and the specific year-by-year figures.
- **GPT-5.5: Fail.** The memorandum discusses minimum purchases in general and mentions some figures (e.g., Year 2 $9.2M, Year 5 $14M, cumulative $54M), but it does not reference Section 5.1 or extract the full annual minimum purchase commitments for Years 1-5 ($8.0M, $9.2M, $10.6M, $12.2M, $14.0M).

### C-030

Section 5.3 curable default and 60-day cure notice requirement extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L251))

- **Sonnet 4.6: Pass.** The memorandum references Section 5.3 multiple times. In Section 3A it states: 'Section 5.3 required written notice and a 60-day cure opportunity before termination rights could be exercised; Yuen confirms none was sent.' It also notes in the chronology that 'Section 5.3 characterizes a single-year shortfall as curable and requires 60 days' written notice and an opportunity to cure.' The criterion requires mention of Section 5.3 and explanation that a single-year minimum shortfall is a curable default requiring 60 days' written notice and opportunity to cure before termination. The memo satisfies this criterion.
- **GPT-5.5: Pass.** The memorandum expressly references Section 5.3 several times and explains that a single-year minimum-purchase shortfall is curable and required 60 days’ written notice and an opportunity to cure before termination rights could be exercised. Although it does not specifically cite Section 12.1(b), it satisfies the core extraction requirement.

### C-031

Section 16.1 Georgia choice of law extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L259))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 3C: 'Contract: Section 16.1 selects Georgia substantive law for interpretation, validity, performance, and enforcement.' This directly identifies Section 16.1 as the choice of law provision selecting Georgia law.
- **GPT-5.5: Pass.** The memorandum expressly states that “Section 16.1 selects Georgia substantive law for interpretation, validity, performance, and enforcement,” thereby identifying the Georgia choice-of-law provision.

### C-032

Section 16.3 Mecklenburg County forum selection extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L267))

- **Sonnet 4.6: Fail.** The memorandum mentions the forum selection clause in Section 3C ('the agreement's broad forum clause selects state or federal courts in Mecklenburg County and consents to jurisdiction'), but it does not identify the specific section number as Section 16.3. The criterion requires that the memo identify 'Section 16.3 as the forum selection clause.' The memo only references 'Section 16.1' (choice of law) by number, while the forum clause is mentioned without a section number. Therefore, the criterion is not satisfied.
- **GPT-5.5: Fail.** The memorandum mentions a forum clause selecting state or federal courts in Mecklenburg County, but it does not identify it as Section 16.3 as required by the criterion.

### C-033

Section 14.2 prevailing party fee-shifting provision extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L275))

- **Sonnet 4.6: Fail.** The memorandum references 'contractual prevailing-party fees' in Count I and mentions 'Contract fees are prevailing-party reciprocal' in the damages section, but it does not specifically cite Section 14.2 as the prevailing party attorneys' fees provision. The criterion requires explicit mention of Section 14.2.
- **GPT-5.5: Fail.** The memorandum mentions contractual/prevailing-party fee exposure generally, but it does not reference Section 14.2 as the prevailing party attorneys' fees provision.

### C-034

Magnolia Foods Processing, Inc. identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L283))

- **Sonnet 4.6: Fail.** The memorandum refers to 'Magnolia' as one of the four named Territory customers with an invoice of $870k (Nov. 15), but it does not include the full name 'Magnolia Foods Processing, Inc.' — it only says 'Magnolia $870k (Nov. 15)'. The criterion requires that 'Magnolia Foods Processing, Inc.' be identified by that full name. Since the memo only uses 'Magnolia' without the complete company name, the criterion is not satisfied.
- **GPT-5.5: Pass.** The memorandum identifies “Magnolia” among the Exhibit E invoices/direct sales, listing a $870k sale on Nov. 15, which identifies Magnolia as one of the alleged direct-sale customers.

### C-035

Tidewater Pharmaceutical Group, LLC identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L291))

- **Sonnet 4.6: Fail.** The memorandum refers to 'Tidewater' as one of the four named Territory customers with invoices totaling $720k (Dec. 8) plus $480k (Jan. 22), but it does not include the full name 'Tidewater Pharmaceutical Group, LLC' — it only says 'Tidewater'. The criterion requires identification as 'Tidewater Pharmaceutical Group, LLC'. The memo uses only the shortened name 'Tidewater' without the 'Pharmaceutical Group, LLC' designation.
- **GPT-5.5: Fail.** The memorandum references “Tidewater” as a direct-sales customer with invoice amounts, but it does not name “Tidewater Pharmaceutical Group, LLC” specifically.

### C-036

Clearwater Chemical Partners, LP identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L299))

- **Sonnet 4.6: Fail.** The memorandum refers to 'Clearwater' as one of the four named Territory customers with an invoice of $640k (Jan. 18), but it does not identify the full name 'Clearwater Chemical Partners, LP.' The criterion specifically requires identification of 'Clearwater Chemical Partners, LP.' The memo only uses the shortened name 'Clearwater.'
- **GPT-5.5: Fail.** The memorandum references a direct-sale invoice to “Clearwater” for $640k, but it does not name the customer as “Clearwater Chemical Partners, LP.” The criterion requires that Clearwater Chemical Partners, LP be identified/named.

### C-037

Southeastern Bottling Co., Inc. identified as direct-sale customer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L307))

- **Sonnet 4.6: Fail.** The memorandum refers to 'Southeastern' as one of the four named Territory customers with an invoice of $1.55m (Feb. 5), but it does not include the full name 'Southeastern Bottling Co., Inc.' — it only says 'Southeastern.' The criterion requires that 'Southeastern Bottling Co., Inc.' be identified by that specific name. Since the full company name is not present in the memo, the criterion is not satisfied.
- **GPT-5.5: Fail.** The memorandum refers to a direct-sale customer as “Southeastern” and lists a $1.55m invoice, but it does not name the customer as “Southeastern Bottling Co., Inc.” as required by the criterion.

### C-038

Total alleged direct sales stated as $4,260,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L315))

- **Sonnet 4.6: Pass.** The memorandum states 'Exhibit E invoices total $4.26m' and also references 'at least $4.26 million of direct sales to four named Territory customers.' The individual invoice amounts listed are: Magnolia $870k, Tidewater $720k + $480k, Clearwater $640k, Southeastern $1.55m. The sum of these is $870k + $720k + $480k + $640k + $1,550k = $4,260k = $4.26m. The criterion requires the total to be stated as $4,260,000 (sum of $870,000 + $1,200,000 + $640,000 + $1,550,000). However, the Tidewater breakdown in the memo is $720k + $480k = $1,200k, which matches the criterion's $1,200,000 for that customer. The total $4.26m = $4,260,000 is correctly stated in the memorandum. The criterion is satisfied.
- **GPT-5.5: Pass.** The memorandum repeatedly states the direct-sales invoices total $4.26 million / $4.26m, which is equivalent to $4,260,000 and matches the required sum.

### C-039

Brandon Kelsey identified as hired-away employee (former Southeast Regional Sales Manager at Apex) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L323))

- **Sonnet 4.6: Fail.** The memorandum mentions 'Kelsey' and 'Ostrowski' multiple times as employees hired by Greenfield in February 2024, but never identifies Kelsey's former role at Apex (Southeast Regional Sales Manager). The criterion requires that Brandon Kelsey be identified as a former Apex employee with the title 'Southeast Regional Sales Manager.' The memo does not provide this identification — it only refers to 'Kelsey' without a first name and without specifying their prior role at Apex.
- **GPT-5.5: Fail.** The memorandum mentions Kelsey and Ostrowski as employees hired by Greenfield and discusses their covenants, but it does not identify Brandon Kelsey by full name or state that he was a former Apex Southeast Regional Sales Manager.

### C-040

Lauren Ostrowski identified as hired-away employee (former Senior Technical Account Executive at Apex) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L331))

- **Sonnet 4.6: Fail.** The memorandum mentions 'Kelsey and Ostrowski' multiple times as employees hired by Greenfield in February 2024, but never identifies Lauren Ostrowski's former role at Apex as 'Senior Technical Account Executive.' The document simply refers to them as hired employees without specifying their previous employer or job title at Apex.
- **GPT-5.5: Fail.** The memorandum mentions Kelsey and Ostrowski as employees hired by Greenfield and refers generally to former employees, but it does not identify Lauren Ostrowski by first name or as a former Apex Senior Technical Account Executive.

### C-041

Confidential Sales Information components described ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L339))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the alleged trade secrets in Count III: 'Customer database, price matrices/discounts, and pipeline forecasts.' This references at least three of the four components listed in the criterion: (1) proprietary customer database, (2) pricing matrices/discount structures, and (3) sales pipeline forecasts. The criterion requires at least two of these components to be identified, and the memo clearly identifies three.
- **GPT-5.5: Pass.** The memorandum specifically identifies alleged trade-secret components including a customer database, price matrices/discounts, and pipeline forecasts, satisfying the requirement to reference at least two Confidential Sales Information components.

### C-042

Injunctive relief: prohibition of further direct sales in Territory ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L347))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies in Section 6 that Apex seeks '(1) bar all direct Greenfield sales to any customer in the eight-state Territory during the action' as one of the four principal forms of injunctive relief. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly states that Apex seeks injunctive relief to “bar all direct Greenfield sales to any customer in the eight-state Territory during the action,” which describes the requested prohibition on further direct sales in the Territory.

### C-043

Injunctive relief: return/destruction of Confidential Sales Information ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L355))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 6 that Apex seeks '(2) return or destroy Apex sales information, under neutral supervision and with sworn certification' as one of the four principal forms of injunctive relief. This clearly identifies the return/destruction of Confidential Sales Information component of the injunctive relief sought.
- **GPT-5.5: Pass.** The memorandum expressly states that Apex seeks injunctive relief requiring Greenfield to “return or destroy Apex sales information, under neutral supervision and with sworn certification,” which covers the return/destruction of Confidential Sales Information.

### C-044

Injunctive relief: prohibition on employing Kelsey/Ostrowski in Territory-related roles ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L363))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 6 that Apex seeks '(3) prohibit Greenfield from employing Kelsey and Ostrowski in Territory-related or information-access roles' as one of the four principal forms of injunctive relief. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memorandum expressly states that Apex seeks injunctive relief to “prohibit Greenfield from employing Kelsey and Ostrowski in Territory-related or information-access roles,” which identifies the required component.

### C-045

Attorneys' fees claim under Section 14.2 noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L371))

- **Sonnet 4.6: Fail.** The memorandum mentions 'contractual prevailing-party fees' in the Count I assessment and references 'Contract fees are prevailing-party reciprocal' in the damages table, but it does not specifically cite Section 14.2 of the Distribution Agreement as the basis for the attorneys' fees claim. The criterion requires that the memo note Apex seeks attorneys' fees under Section 14.2 specifically. Since the section number is never mentioned, the criterion is not satisfied.
- **GPT-5.5: Fail.** The memorandum mentions contractual/prevailing-party fee exposure, but it does not identify Section 14.2 of the Distribution Agreement as the basis for Apex's attorneys' fees claim.

### C-046

Attorneys' fees claim under Georgia Trade Secrets Act noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L379))

- **Sonnet 4.6: Pass.** Looking through the memorandum for any mention of attorneys' fees under the Georgia Trade Secrets Act specifically. In Section 4 (Claim-by-claim assessment), under Count III, the memo mentions 'injunction and fees' as part of Apex's relief sought. In Section 5 (Damages), under 'Additional relief,' it states 'GTSA fee/exemplary relief requires statutory predicates.' This references GTSA fees but does so in the context of noting that statutory predicates are required, not explicitly noting that Apex seeks attorneys' fees under the Georgia Trade Secrets Act as a specific claim. However, the memo does reference 'GTSA fee/exemplary relief' which implicitly acknowledges that Apex seeks fees under the GTSA. The criterion asks whether the memo notes that Apex seeks attorneys' fees under the Georgia Trade Secrets Act. The memo does mention 'fees' in the Count III row and references 'GTSA fee/exemplary relief requires statutory predicates' in the damages section. This is a reference to GTSA attorneys' fees, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum's Count III discussion identifies the GTSA/DTSA trade-secret claim and states that Apex seeks “injunction and fees,” and the damages section further notes that “GTSA fee/exemplary relief requires statutory predicates.” This sufficiently notes attorneys' fee exposure tied to the Georgia Trade Secrets Act.

### C-047

Eight-state exclusive territory identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L387))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 2 (Key facts and chronology): 'Greenfield grants Apex exclusive distribution rights across GA, AL, TN, SC, NC, FL, MS, and LA (as alleged).' This identifies all eight states: Georgia, Alabama, Tennessee, South Carolina, North Carolina, Florida, Mississippi, and Louisiana. The eight-state territory is also referenced multiple times throughout the document (e.g., 'eight-state Territory' in Sections 6 and 7).
- **GPT-5.5: Pass.** The memorandum explicitly identifies the exclusive distribution territory as eight states: GA, AL, TN, SC, NC, FL, MS, and LA, corresponding to Georgia, Alabama, Tennessee, South Carolina, North Carolina, Florida, Mississippi, and Louisiana.

### C-048

ISSUE_001: Defective first notice — Hargrove not authorized signatory ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L395))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies that Thomas Hargrove (VP of Sales) sent the July 15, 2023 non-renewal notice, that Section 4.2 requires delivery by the CEO or General Counsel, and that Hargrove was not an authorized signatory, rendering the notice void. This is flagged multiple times throughout the document as a key vulnerability.
- **GPT-5.5: Pass.** The memorandum explicitly identifies that Thomas Hargrove, VP of Sales, sent the July 15, 2023 non-renewal notice and that Section 4.2 required delivery by the CEO or General Counsel, making Hargrove's notice noncompliant/void and a weakness for Greenfield.

### C-049

ISSUE_001: Greenfield did not cure the signatory defect until September 12 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L403))

- **Sonnet 4.6: Pass.** The memorandum clearly addresses the timeline: it notes that Hargrove's July 15, 2023 notice was defective (wrong signatory), that Apex counsel objected in writing on August 3, 2023 identifying the signatory defect, and that Ellsworth's September 12, 2023 notice was the attempted cure (with the correct signer). The memo explicitly states that Greenfield did not respond before the later notice and that the September 12 letter 'expressly supersedes/replaces the July letter.' The gap between the defective notice and the cure attempt is directly addressed in both the chronology table and the contract analysis section.
- **GPT-5.5: Pass.** The memorandum expressly states that Hargrove’s July 15 notice had a signatory defect, that Apex objected in writing on August 3, 2023, and that Greenfield did not respond/cure until Ellsworth’s September 12, 2023 notice, which was too late. The timeline gap between the defective notice and attempted cure is addressed.

### C-050

ISSUE_002: Second notice was only 169 days before expiration ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L411))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the executive assessment: 'Ellsworth's September 12 letter was 169 days before February 28, 2024---short of the 180-day requirement.' It also states 'September 12 remains 11 days late' in Section 3A. Both the 169-day calculation and the 11-day shortfall are clearly identified.
- **GPT-5.5: Pass.** The memorandum expressly states that Ellsworth's September 12 notice was 169 days before the February 28, 2024 expiration and therefore 11 days short of the 180-day requirement, identifying the untimeliness of the second notice.

### C-051

ISSUE_002: Auto-renewal through February 28, 2026 is Apex's position ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L419))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 2 (Key facts and chronology): 'If neither notice complied with Section 4.2, the Agreement automatically renewed through Feb. 28, 2026. On current text, this is Apex's strong position.' This directly addresses the criterion that the memo explains the auto-renewal consequence as Apex's position due to both defective/untimely non-renewal notices.
- **GPT-5.5: Pass.** The memorandum explicitly states that Hargrove’s July notice was defective, Ellsworth’s September notice was untimely, and that if neither notice complied with Section 4.2, the Agreement automatically renewed through February 28, 2026, which it identifies as Apex’s strong position.

### C-052

Year 2 shortfall of $2.1M identified ($7.1M actual vs. $9.2M minimum) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L427))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 2 (Key facts and chronology): 'Apex purchases approximately $7.1m against a $9.2m Year 2 minimum.' This identifies both the actual purchases ($7.1M) and the minimum ($9.2M), from which the $2.1M shortfall is directly calculable. The criterion requires these figures to be mentioned, and they are present in the document.
- **GPT-5.5: Fail.** The memorandum mentions the Year 2 figures—Apex purchased approximately $7.1M against a $9.2M minimum—but it does not expressly identify the resulting shortfall amount as $2.1M.

### C-053

Greenfield's failure to send 60-day cure notice for Year 2 shortfall identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L435))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 3A: 'Section 5.3 required written notice and a 60-day cure opportunity before termination rights could be exercised; Yuen confirms none was sent.' This directly identifies that Greenfield never sent the required 60-day cure notice under Section 5.3 for the Year 2 shortfall.
- **GPT-5.5: Pass.** The memorandum explicitly states that Section 5.3 required 60 days' written notice and an opportunity to cure for the Year 2 shortfall, and that Greenfield sent no such notice / Yuen confirms none was sent.

### C-054

Waiver implication from absent cure notice discussed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L443))

- **Sonnet 4.6: Pass.** The memorandum explicitly discusses the waiver implication in Section 3A: 'The omission is likely a substantial waiver/notice problem.' It states that Greenfield failed to send the required written notice and 60-day cure opportunity under Section 5.3, and that the record reflects acceptance of later performance and cumulative purchases above the five-year total. The memo concludes that 'The Year 2 shortfall is not a persuasive present defense to the renewal' and that 'The omission is likely a substantial waiver/notice problem.' This directly addresses the waiver implication from the absent cure notice.
- **GPT-5.5: Pass.** The memorandum expressly states that Section 5.3 required written notice and a 60-day cure opportunity, that Greenfield sent no such notice, and that the omission is “likely a substantial waiver/notice problem,” weakening any termination defense based on the Year 2 shortfall.

### C-055

ISSUE_003: Year 2 shortfall undermines Greenfield's material breach defense ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L451))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses the Year 2 shortfall defense in multiple places. In Section 3A, it states: 'Section 5.3 required written notice and a 60-day cure opportunity before termination rights could be exercised; Yuen confirms none was sent.' It further notes 'The omission is likely a substantial waiver/notice problem' and that 'The shortfall may be relevant to breach, but cannot safely be treated as automatically terminating the agreement or excusing Greenfield's direct sales.' The executive assessment also states 'The non-renewal defense is materially weak on the current documents' and in the claim-by-claim table notes 'Section 5.3 makes Year 2 shortfall a weak termination defense.' This clearly satisfies the criterion that the memo notes Greenfield never sent the cure notice and therefore cannot assert Apex was in material breach as a defense.
- **GPT-5.5: Pass.** The memorandum expressly discusses the Year 2 shortfall, states that Section 5.3 required written notice and a 60-day cure opportunity, notes that Greenfield sent no such notice, and concludes the shortfall is a weak/not persuasive defense that cannot safely be used to terminate the agreement or excuse Greenfield’s conduct.

### C-056

ISSUE_004: Exemplary damages statutory characterization flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L459))

- **Sonnet 4.6: Fail.** The memorandum mentions that 'Apex claims one times its asserted actual amount' regarding the exemplary damages cap, and notes the $3.4m exemplary figure, but it does not specifically identify that the complaint characterizes exemplary damages as 'double damages' or 'double the actual damages,' nor does it flag that this is an imprecise or misleading characterization of O.C.G.A. § 10-1-763. The memo simply notes the statutory cap exists without addressing whether the complaint used misleading language about it. The criterion requires the memo to identify the complaint's specific characterization as 'double damages' and flag it as imprecise/misleading relative to the statute. This specific statutory nuance is not addressed.
- **GPT-5.5: Fail.** The memorandum notes that Count III seeks $3.4 million in actual/replacement-cost damages plus $3.4 million in exemplary damages, and states that exemplary damages are statutorily capped and require proof. However, it does not identify that the complaint characterized the remedy as “double damages” or “double the actual damages,” nor does it flag that characterization as imprecise or misleading under O.C.G.A. § 10-1-763 because the statute caps exemplary damages at the amount of actual damages rather than creating a double-damages multiplier. The required statutory nuance is therefore not addressed.

### C-057

ISSUE_005: Double recovery risk between Counts I and II ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L467))

- **Sonnet 4.6: Pass.** The memorandum explicitly identifies the double-recovery risk between Counts I and II. In Section 4 (Claim-by-claim assessment), under Count II, it states: 'The complaint's customer NPV may duplicate contract lost profits and commission damages.' In Section 5 (Damages and exposure framework), it further states: 'The same four transactions and customer relationships underlie (i) commission/lost-profit contract damages, (ii) the $6.2m customer-relationship valuation, (iii) the $1.491m Greenfield profit estimate, and potentially (iv) the trade-secret valuation. Courts generally prevent duplicative compensation for one injury.' This directly flags that Count I lost profits and Count II NPV of customer relationships overlap and create an impermissible double-recovery risk because both seek the economic value of the same lost customer relationships.
- **GPT-5.5: Pass.** The memorandum expressly identifies that Count II's $6.2m lost customer relationship/NPV theory may duplicate Count I's contract lost profits and commission damages, and further explains that the same transactions and customer relationships underlie both contract damages and the customer-relationship valuation, creating a non-duplicative recovery/double-counting issue.

### C-058

ISSUE_006: Choice of law vs. forum selection complexity identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L475))

- **Sonnet 4.6: Pass.** Section 3C of the memorandum explicitly addresses choice of law, venue, and removal. It identifies that Section 16.1 selects Georgia substantive law for contract interpretation while North Carolina procedure governs in state court. It also notes that the distribution agreement's Georgia clause does not conclusively resolve independent tort choice-of-law questions, and that the tortious-interference claim may require North Carolina conflicts rules. It separately addresses the employee covenants (Exhibit F agreements), noting they select Georgia law and that a North Carolina forum may apply North Carolina public policy/restrictive-covenant standards despite the selection clause. This satisfies all elements of the criterion: GA substantive law + NC forum tension, NC procedural law applying alongside GA substantive law, and different choice-of-law analyses for trade secret/non-compete claims vs. the Distribution Agreement.
- **GPT-5.5: Pass.** The memorandum expressly identifies the forum/choice-of-law tension: the case is in North Carolina state court under a Mecklenburg forum clause, while Section 16.1 selects Georgia substantive law for the Distribution Agreement. It also notes North Carolina procedural law applies, DTSA is federal, tort/trade-secret choice-of-law may require separate analysis, and the Kelsey/Ostrowski employment agreements have separate Georgia choice-of-law provisions with potential NC public policy implications.

### C-059

ISSUE_007: TRO hearing precedes answer deadline — urgency flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L483))

- **Sonnet 4.6: Pass.** The memorandum explicitly flags that the TRO/PI hearing on May 9, 2025 occurs before the answer deadline of May 27, 2025. In the Executive Assessment, it states 'The immediate priority is the May 9, 2025 hearing' and notes to 'prepare the evidentiary record now while separately protecting the responsive-pleading and removal deadlines.' The procedural table explicitly notes 'The May 9 hearing does not, by itself, extend that deadline' and the recommended sequencing states 'prepare and oppose the May 9 injunction request first, but concurrently develop a responsive pleading and make a deliberate forum/removal decision well before May 27.' This clearly flags the timing issue and urgency created by the TRO hearing preceding the answer deadline.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the May 9, 2025 TRO/PI hearing as the immediate priority, states that the evidentiary record must be prepared now, separately calendars the May 27 answer/Rule 12 deadline, and recommends preparing to oppose the May 9 injunction first while concurrently protecting the later responsive-pleading/removal deadlines. This clearly flags the hearing-before-answer timing pressure.

### C-060

ISSUE_008: Unjust enrichment generally unavailable alongside express contract ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L491))

- **Sonnet 4.6: Pass.** The memorandum explicitly addresses Count IV (unjust enrichment) in Section 4 and states: 'Pled expressly in the alternative to contract relief. If an enforceable agreement governs the same subject, an independent quasi-contract recovery may be unavailable.' This directly identifies the vulnerability that unjust enrichment is generally unavailable where an express contract covers the same subject matter. The criterion is satisfied.
- **GPT-5.5: Pass.** The memorandum expressly flags Count IV as pleaded in the alternative and states that if an enforceable agreement governs the same subject, independent quasi-contract/unjust-enrichment recovery may be unavailable. It also identifies Georgia law as the contract’s governing law. Although it could have been more explicit that the dismissal vulnerability arises under Georgia law, the required defense/vulnerability is identified.

### C-061

ISSUE_009: Count I lost profits calculation verified ($16.1M × 22% × 2 = $7,084,000) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L499))

- **Sonnet 4.6: Pass.** The memorandum states in the damages table: 'Renewal lost profits: $16.1m annual sales × 22% × 2 years = $7.084m'. This explicitly recites all three components ($16.1M, 22%, 2 years) and the resulting figure ($7.084m), which matches the criterion's required calculation of $16.1M × 22% × 2 = $7,084,000. The criterion asks whether the calculation is verified with components recited, and the memo does exactly that.
- **GPT-5.5: Pass.** The memorandum expressly recites and verifies the Count I renewal lost profits calculation as “$16.1m annual sales × 22% × 2 years = $7.084m,” i.e., $7,084,000, and identifies the components.

### C-062

ISSUE_009: Count I lost commissions verified ($4,260,000 × 18% = $766,800) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L507))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the damages table: 'Direct-sale commissions: 18% × $4.26m = $766,800' and in the executive assessment: 'The most supportable current dollar component may be the alleged direct-sale commission amount ($766,800) if the 18% term is verified.' This independently verifies the calculation $4,260,000 × 18% = $766,800.
- **GPT-5.5: Pass.** The memorandum explicitly identifies the invoices as totaling $4.26 million and separately verifies the Count I direct-sale commission calculation as “18% × $4.26m = $766,800.”

### C-063

ISSUE_009: Count IV unjust enrichment verified ($4,260,000 × 35% = $1,491,000) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L515))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the damages table: 'Unjust enrichment: $1.491m = 35% × $4.26m' and in the claim-by-claim assessment: 'Disgorgement of Greenfield's estimated 35% profit on the same $4.26m direct sales: $1,491,000.' This independently verifies the calculation $4,260,000 × 35% = $1,491,000.
- **GPT-5.5: Pass.** The memorandum expressly verifies the Count IV unjust enrichment calculation, stating that unjust enrichment is “$1.491m = 35% × $4.26m” and describing it as 35% profit on $4.26 million in direct sales, which equals $1,491,000.

### C-064

ISSUE_010: Enforceability of 24-month non-competes flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L523))

- **Sonnet 4.6: Pass.** The memorandum discusses the employee covenants (Exhibit F agreements) and notes that Georgia's Restrictive Covenants Act 'generally permits covenants for qualifying employees and can presume a restriction of two years or less reasonable in duration, but employee status, scope, geographic fit, consideration, and the full agreements remain material.' It also notes the noncompete's prohibition on work for a competitor 'in any capacity' across eight states is broad, and that a North Carolina forum may apply North Carolina public policy despite the selection clause. The memo flags enforceability as uncertain and relevant to injunctive relief. However, it does not specifically identify the agreements as '24-month' non-competes — it references 'two years or less' in the context of Georgia law presumptions but does not explicitly state the duration of Kelsey and Ostrowski's specific agreements. Despite this, the memo does flag enforceability under Georgia's Restrictive Covenants Act as an issue relevant to injunctive relief and the trade secret/interference claims, which satisfies the core requirement of the criterion. The criterion asks that enforceability 'depends on reasonableness under applicable law (Georgia Restrictive Covenants Act...)' be flagged, and this is done, even if the specific 24-month duration isn't called out by name.
- **GPT-5.5: Pass.** The memorandum discusses Kelsey and Ostrowski's employment covenants/noncompetes, notes that the Exhibit F agreements select Georgia law, flags Georgia Restrictive Covenants Act reasonableness considerations including the two-year duration presumption, and identifies issues with scope/geography/employee status and possible North Carolina public policy. It also ties these enforceability concerns to injunctive relief, employment restraints, and trade-secret/misappropriation theories. Although it does not repeatedly label them as '24-month' covenants, it sufficiently flags the enforceability issue required by the criterion.

### C-065

Chronological timeline of material events included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L531))

- **Sonnet 4.6: Pass.** The memorandum contains a detailed chronological timeline in Section 2 ('Key facts and chronology') that includes all ten required dates: March 1, 2019 (Agreement begins); July 15, 2023 (Hargrove's non-renewal notice); August 3, 2023 (Apex counsel objects); September 12, 2023 (Ellsworth's notice); October 2023 (direct-sales campaign begins); February 2024 (Kelsey and Ostrowski hired); April 22, 2025 (complaint filed); April 25, 2025 (service); May 9, 2025 (TRO/PI hearing); and May 27, 2025 (responsive pleading deadline). All ten dates are present in the chronological table, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum includes ordered chronological sections/tables covering the material dates. It includes March 1, 2019; July 15, 2023; August 3, 2023; September 12, 2023; October 2023; February 2024; April 22, 2025; April 25, 2025; May 9, 2025; and May 27, 2025, with descriptions of the relevant events.

### C-066

Damages analysis presented in structured format (table or breakdown) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L539))

- **Sonnet 4.6: Pass.** The memorandum includes Section 5 'Damages and exposure framework' which contains a structured table with columns for 'Pleading component,' 'Apex calculation,' and 'Exposure lens / immediate proof issue.' This table lists each damage component (direct-sale commissions, renewal lost profits, lost customer relationships, trade-secret damages/exemplary, unjust enrichment, and additional relief) with the calculation methodology and claimed dollar amounts. Additionally, Section 4 contains a claim-by-claim table that includes each count's pleaded amounts. These structured formats satisfy the criterion of showing damage components with calculation methodology and claimed dollar amounts in a non-prose organized format.
- **GPT-5.5: Pass.** The memorandum includes structured tables, including a claim-by-claim assessment for all four counts with pleaded amounts and a damages/exposure framework showing calculation methodology and dollar amounts such as $766,800, $7.084m, $6.2m, $3.4m + $3.4m, and $1.491m.

### C-067

Immediate action items section with TRO preparation prioritized ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L547))

- **Sonnet 4.6: Pass.** The memorandum includes a dedicated 'Immediate action plan' section (Section 7) with a detailed table of time-sensitive actions. TRO preparation is explicitly prioritized: the executive assessment opens by stating 'The immediate priority is the May 9, 2025 hearing,' and Section 7 includes a specific 'Before May 9' action item to 'Prepare declarations, documentary exhibits, response brief, proposed narrower order, bond evidence, and hearing outline.' Section 6 is entirely devoted to TRO/PI opposition strategy. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memorandum includes a dedicated “Immediate action plan” section with time-sensitive tasks, and repeatedly identifies preparation for the May 9, 2025 TRO/preliminary-injunction hearing as the immediate priority, including preparing declarations, exhibits, briefing, a proposed narrower order, and hearing outline before May 9.

### C-068

Answer filing identified as an action item by May 27, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L555))

- **Sonnet 4.6: Pass.** The memorandum explicitly lists in Section 7 (Immediate action plan) under 'By May 27': 'File an answer or appropriate Rule 12 motion; separately decide and, if chosen, file removal within the statutory deadline.' This clearly identifies filing the answer by May 27, 2025 as an action item.
- **GPT-5.5: Pass.** The memorandum’s Immediate Action Plan includes a row for “By May 27” stating to “File an answer or appropriate Rule 12 motion,” so the answer deadline is listed among the action items.

### C-069

Client GC admissions from email extracted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L563))

- **Sonnet 4.6: Pass.** The memorandum references Patricia Yuen's email multiple times. It notes that 'Yuen reports Hargrove acted without her review or Ellsworth's approval' regarding the July 15 notice, and that 'Yuen reports Greenfield hired Kelsey and Ostrowski' in February 2024. It also references 'Yuen confirms none was sent' regarding the Section 5.3 cure notice for the Year 2 shortfall. However, the criterion specifically asks whether the memo references the admission that the second letter was 'rushed out' and that the Year 2 shortfall was 'never formally addressed' — these specific phrasings are not present. The memo does reference Yuen's email regarding Hargrove sending the July notice without her review, which satisfies part of the criterion. The Year 2 shortfall is discussed but the specific admission that it was 'never formally addressed' (as a direct quote or paraphrase from Yuen's email) is not explicitly attributed to Yuen's email — instead it's framed as a legal analysis point. The 'rushed out' admission about the second letter is not mentioned at all. That said, the criterion says 'such as' these examples, indicating they are illustrative rather than exhaustive. The memo does reference candid admissions from Yuen's email (Hargrove acting without her review/approval, the direct sales initiative). This satisfies the criterion's core requirement of referencing candid admissions from the client email.
- **GPT-5.5: Pass.** The memorandum explicitly references Patricia Yuen's email/admissions, including that Hargrove sent the July notice without her review or Ellsworth's approval and that no formal Year 2 cure/notice was sent. These satisfy the criterion even though it does not quote every example such as 'rushed out.'

### C-070

24-month non-compete/non-solicitation agreements of Kelsey and Ostrowski noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L571))

- **Sonnet 4.6: Fail.** The memorandum discusses Kelsey and Ostrowski's employment agreements and restrictive covenants in several places, but it never specifies the duration of those agreements as 24 months. It references 'Exhibit F agreements,' 'employee covenants,' 'noncompete,' and 'restrictive covenants,' and notes that Georgia's Restrictive Covenants Act 'can presume a restriction of two years or less reasonable in duration,' but this is a general legal statement, not an identification that Kelsey and Ostrowski specifically had 24-month agreements. The criterion requires the memo to identify that each had 24-month post-employment non-competition and non-solicitation agreements. The memo fails to state this specific duration for these specific employees.
- **GPT-5.5: Fail.** The memorandum discusses Kelsey/Ostrowski employment covenants and notes Georgia law may presume restrictions of two years or less reasonable, but it does not identify that each had 24-month post-employment non-competition and non-solicitation agreements with Apex. The required duration and both covenant types are not clearly stated.

### C-071

Apex's alleged renewal period identified as through February 28, 2026 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L579))

- **Sonnet 4.6: Pass.** The memorandum explicitly states 'If neither notice complied with Section 4.2, the Agreement automatically renewed through Feb. 28, 2026.' This directly identifies the alleged renewal period end date as February 28, 2026, which is two years after the initial expiration of February 28, 2024.
- **GPT-5.5: Pass.** The memorandum explicitly states that if the notices were noncompliant, the Agreement automatically renewed through February 28, 2026, satisfying the criterion.

### C-072

Apex's 22% gross margin on Greenfield products noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L587))

- **Sonnet 4.6: Pass.** The memorandum explicitly states '22% gross margin' in multiple places, including in the damages section: '$16.1m annual sales × 22% × 2 years = $7.084m' and 'Apex's claimed $7.084m in future lost profits assumes $16.1m annual sales at a 22% gross margin for both renewal years.'
- **GPT-5.5: Pass.** The memorandum expressly identifies Apex's claimed margin as a 22% gross margin in the renewal lost-profits discussion and damages table.

### C-073

Apex's 18% commission rate on Territory sales noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L595))

- **Sonnet 4.6: Pass.** The memorandum explicitly mentions the 18% commission rate multiple times, including in the executive assessment ('the alleged 18% compensation term'), in the damages framework ('18% × $4.26m = $766,800'), and in the claim-by-claim assessment. The rate is clearly identified as applying to Territory sales.
- **GPT-5.5: Pass.** The memorandum repeatedly notes the alleged 18% rate, including stating the 'alleged 18% compensation term,' calculating direct-sale commissions as '18% × $4.26m = $766,800,' and advising confirmation of whether the agreement establishes the 18% rate for Territory/direct sales.

### C-074

Greenfield's alleged 35% margin on direct sales noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L603))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in the unjust enrichment row: 'Disgorgement of Greenfield's estimated 35% profit on the same $4.26m direct sales: $1,491,000.' It also repeats this in the damages table: '$1.491m = 35% × $4.26m'. The 35% margin figure is clearly identified.
- **GPT-5.5: Pass.** The memorandum expressly states that unjust enrichment is based on “Greenfield's estimated 35% profit” on the $4.26 million direct sales and repeats the 35% calculation in the damages table.

### C-075

Kelsey/Ostrowski employment agreements governed by Georgia law noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-terms-from-counterparty-complaint/task.json#L611))

- **Sonnet 4.6: Pass.** The memorandum explicitly states in Section 3C: 'both Exhibit F agreements separately select Georgia law; each employee is identified as a Georgia resident when signing.' This clearly notes that the employment agreements of Kelsey and Ostrowski are governed by Georgia law, satisfying the criterion.
- **GPT-5.5: Pass.** The memorandum expressly states that the Kelsey/Ostrowski employment agreements select Georgia law, noting that both Exhibit F agreements separately select Georgia law and discussing Georgia restrictive covenant standards.
