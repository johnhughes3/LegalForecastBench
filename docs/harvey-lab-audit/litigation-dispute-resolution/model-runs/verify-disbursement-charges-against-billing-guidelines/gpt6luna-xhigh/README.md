# GPT-6 Luna (xhigh): Verify Disbursement Charges Against Outside Counsel Billing Guidelines — Compliance Report

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/verify-disbursement-charges-against-billing-guidelines/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 38 of 57 criteria; GPT-5.5 passed 39 of 57 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [disbursement-compliance-report.docx](output/disbursement-compliance-report.docx) ([read as Markdown](output/disbursement-compliance-report.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001a: Flags Line 3 hotel rate exceeds Tier 1 cap ($319 vs $275/night) | Pass | Pass |
| [C-002](#c-002) | ISSUE_001b: Flags Line 4 hotel rate exceeds Tier 1 cap ($319 vs $275/night) | Pass | Pass |
| [C-003](#c-003) | ISSUE_001c: Correctly calculates hotel overage for Lines 3 and 4 | Pass | Pass |
| [C-004](#c-004) | ISSUE_001d: Cites Section 5.2 for hotel rate violation | **Fail** | **Fail** |
| [C-005](#c-005) | ISSUE_002a: Flags Line 15 internal photocopy rate of $0.15 vs guideline $0.10 | Pass | Pass |
| [C-006](#c-006) | ISSUE_002b: Calculates photocopy overcharge as $620 | Pass | Pass |
| [C-007](#c-007) | ISSUE_002c: Cites Section 5.3 for photocopy rate violation | **Fail** | **Fail** |
| [C-008](#c-008) | ISSUE_003a: Flags Line 42 Westlaw charges as non-reimbursable overhead | Pass | Pass |
| [C-009](#c-009) | ISSUE_003b: Recommends full rejection of $3,870 Westlaw charge | Pass | Pass |
| [C-010](#c-010) | ISSUE_003c: Cites Section 5.1 and/or 5.8 for Westlaw overhead rule | **Fail** | **Fail** |
| [C-011](#c-011) | ISSUE_004a: Flags Line 10 mileage as non-reimbursable local travel | Pass | Pass |
| [C-012](#c-012) | ISSUE_004b: Recommends full rejection of $9.80 mileage charge | Pass | Pass |
| [C-013](#c-013) | ISSUE_004c: Cites Section 5.2 for local travel prohibition | **Fail** | **Fail** |
| [C-014](#c-014) | ISSUE_005a: Flags Line 5 dinner per-person cost exceeds $75/day cap | Pass | Pass |
| [C-015](#c-015) | ISSUE_005b: Flags Line 6 M. Beale meals exceed $75/day cap on 05/03 | Pass | Pass |
| [C-016](#c-016) | ISSUE_005c: Identifies Palermo's share of Line 5 dinner also exceeds cap | **Fail** | **Fail** |
| [C-017](#c-017) | ISSUE_005d: Calculates total meal overage approximately $71 | **Fail** | **Fail** |
| [C-018](#c-018) | ISSUE_006a: Flags Dr. Hartsfield total May charges exceed $35K budget | Pass | Pass |
| [C-019](#c-019) | ISSUE_006b: Flags Dr. Hartsfield total exceeds $25K GC approval threshold | **Fail** | **Fail** |
| [C-020](#c-020) | ISSUE_006c: Cites Section 5.4 for expert fee threshold/pre-approval | **Fail** | **Fail** |
| [C-021](#c-021) | ISSUE_007a: Flags Line 24 Dr. Voss as lacking pre-approval | Pass | Pass |
| [C-022](#c-022) | ISSUE_007b: Flags Line 25 GraphicWorks as lacking pre-approval | Pass | Pass |
| [C-023](#c-023) | ISSUE_007c: Identifies total at-risk amount for unapproved experts ($12,050) | **Fail** | **Fail** |
| [C-024](#c-024) | ISSUE_008a: Flags Line 45 contract attorney R. Chen rate exceeds $65/hr cap | Pass | Pass |
| [C-025](#c-025) | ISSUE_008b: Calculates R. Chen rate overcharge as $1,420 | Pass | Pass |
| [C-026](#c-026) | ISSUE_008c: Cites Section 5.9 for contract attorney rate cap | **Fail** | **Fail** |
| [C-027](#c-027) | ISSUE_009a: Flags Line 47 A. Brooks as not pre-approved | Pass | Pass |
| [C-028](#c-028) | ISSUE_009b: Identifies full $6,240 as at-risk for A. Brooks | Pass | Pass |
| [C-029](#c-029) | ISSUE_010a: Flags Line 41 e-discovery hosting exceeds pre-approved budget | Pass | Pass |
| [C-030](#c-030) | ISSUE_010b: Calculates e-discovery hosting overage as $2,200 | **Fail** | Pass |
| [C-031](#c-031) | ISSUE_010c: Cites Section 5.8 for e-discovery pre-approval threshold | **Fail** | **Fail** |
| [C-032](#c-032) | ISSUE_011a: Flags Line 38 dinner includes ineligible summer associates | Pass | Pass |
| [C-033](#c-033) | ISSUE_011b: Identifies per-person cost exceeds $85 dinner cap | **Fail** | **Fail** |
| [C-034](#c-034) | ISSUE_011c: Calculates Line 38 recommended reduction accounting for both ineligible attendees and per-person cap | **Fail** | **Fail** |
| [C-035](#c-035) | ISSUE_012a: Flags Line 39 solo working lunch as non-reimbursable | Pass | Pass |
| [C-036](#c-036) | ISSUE_012b: Recommends full rejection of $24 for Line 39 | Pass | Pass |
| [C-037](#c-037) | ISSUE_013a: Flags Line 36 courier for office supplies as non-reimbursable | Pass | Pass |
| [C-038](#c-038) | ISSUE_013b: Recommends full rejection of $18.50 for Line 36 | Pass | Pass |
| [C-039](#c-039) | ISSUE_014a: Flags Line 19 scanning charge exceeds $5K without pre-approval | Pass | Pass |
| [C-040](#c-040) | ISSUE_014b: Identifies Line 19 as requiring retroactive approval or hold | Pass | Pass |
| [C-041](#c-041) | ISSUE_015: Flags invoice total arithmetic discrepancy ($0.11) | **Fail** | **Fail** |
| [C-042](#c-042) | ISSUE_016a: Flags Line 14 rental car as full-size exceeding mid-size limit | Pass | Pass |
| [C-043](#c-043) | ISSUE_016b: Provides a disposition recommendation for Line 14 rental car charge | Pass | Pass |
| [C-044](#c-044) | ISSUE_017a: Flags Line 40 dinner with opposing counsel as problematic | **Fail** | **Fail** |
| [C-045](#c-045) | ISSUE_017b: Identifies Line 40 per-person cost exceeds $85 dinner cap | **Fail** | **Fail** |
| [C-046](#c-046) | ISSUE_018a: Flags Line 12 Washington D.C. hotel exceeds Tier 1 cap | Pass | Pass |
| [C-047](#c-047) | ISSUE_018b: Calculates Washington D.C. hotel overage as $73 | Pass | Pass |
| [C-048](#c-048) | ISSUE_019a: Flags Line 13 C. Aldridge D.C. meals exceed $75/day cap | Pass | Pass |
| [C-049](#c-049) | ISSUE_019b: Calculates D.C. meal overage as $21 | Pass | Pass |
| [C-050](#c-050) | Summary table includes total billed disbursements | Pass | Pass |
| [C-051](#c-051) | Summary table includes total recommended reductions | Pass | Pass |
| [C-052](#c-052) | Summary table includes amount pending approval | Pass | Pass |
| [C-053](#c-053) | Summary table includes recommended net payable amount | **Fail** | **Fail** |
| [C-054](#c-054) | Report distinguishes outright rejections from pending-approval items | Pass | Pass |
| [C-055](#c-055) | Line 25 GraphicWorks also flagged for exceeding $5,000 pre-approval threshold | Pass | Pass |
| [C-056](#c-056) | Guideline section references provided for at least 75% of flagged violations | **Fail** | **Fail** |
| [C-057](#c-057) | Billed amounts stated for at least 75% of flagged violations | Pass | Pass |

## Judge reasoning

### C-001

ISSUE_001a: Flags Line 3 hotel rate exceeds Tier 1 cap ($319 vs $275/night) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L18))

- **Sonnet 4.6: Pass.** The report addresses Lines 3-4 together under 'San Francisco hotels,' noting a Tier 1 cap of $275/night and that 4 room-nights were billed at $319/night, with a reduction of $44 × 4 = $176. This covers Line 3 (M. Beale, 2 nights at $319/night) as non-compliant due to exceeding the $275/night Tier 1 cap. The criterion is satisfied.
- **GPT-5.5: Pass.** The report flags Lines 3–4 San Francisco hotels, stating they were billed at $319 per night and exceed the Tier 1 cap of $275/night, with a reduction calculated. This includes Line 3 and identifies the rate violation.

### C-002

ISSUE_001b: Flags Line 4 hotel rate exceeds Tier 1 cap ($319 vs $275/night) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L26))

- **Sonnet 4.6: Pass.** The report groups Lines 3–4 together under 'San Francisco hotels' and states: 'Tier 1 cap is $275/night inclusive of taxes: 4 room-nights billed at $319; reduce $44 × 4.' This identifies that the $319/night rate exceeds the $275/night Tier 1 cap, and the reduction of $44 × 4 room-nights = $176 covers both lines 3 and 4. Line 4 (J. Palermo, 2 nights at $319/night) is implicitly included in this grouping and the rate violation is identified. The criterion requires that Line 4 be flagged as non-compliant because $319/night exceeds the $275/night cap, which is satisfied by the combined Lines 3–4 entry.
- **GPT-5.5: Pass.** The report flags lines 3--4 San Francisco hotels as exceeding the Tier 1 cap, stating 4 room-nights were billed at $319 versus the $275/night cap and recommending a reduction. This includes Line 4 and identifies the rate violation.

### C-003

ISSUE_001c: Correctly calculates hotel overage for Lines 3 and 4 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L34))

- **Sonnet 4.6: Pass.** The report states for Lines 3-4: 'Tier 1 cap is $275/night inclusive of taxes: 4 room-nights billed at $319; reduce $44 × 4.' This calculates the overage as $44/night × 4 room-nights = $176 total. The criterion requires $44/night × 2 nights = $88 per person, totaling $176 for both lines combined. The total reduction of $176 matches, but the agent's calculation uses 4 room-nights rather than 2 nights × 2 persons. The criterion says '$44/night × 2 nights = $88 per person, totaling $176 for both Lines 3 and 4 combined (or $88 each).' The agent's math arrives at the same $176 total but describes it as 4 room-nights at $44 each. Whether it's 4 room-nights or 2 nights × 2 persons, the arithmetic is equivalent and the total is correct at $176. The criterion is satisfied as the calculation is correct ($176 total reduction).
- **GPT-5.5: Pass.** The report states Lines 3–4 should be reduced by $176, calculated as a $44 overage per night across 4 room-nights. This is equivalent to $88 per person for two people, totaling $176 combined.

### C-004

ISSUE_001d: Cites Section 5.2 for hotel rate violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L42))

- **Sonnet 4.6: Fail.** The report discusses the San Francisco hotel rate violation (lines 3-4) but does not cite Section 5.2 or any specific travel section for hotel rate caps. The basis given is simply 'Tier 1 cap is $275/night inclusive of taxes' without referencing a specific guideline section. The primary authorities section at the end references §§5.1-5.9 broadly, but no specific section (like 5.2) is cited for the hotel rate violation specifically.
- **GPT-5.5: Fail.** The report identifies the San Francisco hotel charges as exceeding the Tier 1 $275/night cap, but it does not cite Section 5.2 or otherwise expressly identify the travel/hotel-rate-cap guideline section as the applicable authority for that violation. A broad end citation to §§5.1--5.9 is not tied to the hotel issue.

### C-005

ISSUE_002a: Flags Line 15 internal photocopy rate of $0.15 vs guideline $0.10 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L50))

- **Sonnet 4.6: Pass.** The report explicitly addresses Line 15 in Section 1 (Recommended face-of-record reductions): '15 | Internal B&W copies | 1,860.00 | 620.00 | 12,400 pages × $0.10 cap = $1,240 allowable; billed at $0.15/page.' This clearly identifies the line, the page count, the guideline cap of $0.10/page, the billed rate of $0.15/page, and the resulting reduction of $620.00. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The report explicitly flags Line 15 as internal B&W copies billed at $1,860 for 12,400 pages at $0.15/page, states the guideline cap is $0.10/page, and recommends a $620 reduction.

### C-006

ISSUE_002b: Calculates photocopy overcharge as $620 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L58))

- **Sonnet 4.6: Pass.** Line 15 in the report states: '12,400 pages × $0.10 cap = $1,240 allowable; billed at $0.15/page.' The billed amount is $1,860.00 and the reduction is $620.00. This matches ($0.15 - $0.10) × 12,400 = $620.00, or equivalently $1,860 - $1,240 = $620.
- **GPT-5.5: Pass.** The report correctly identifies the photocopy charge as 12,400 pages billed at $0.15/page for $1,860, applies the $0.10/page cap for an allowable $1,240, and calculates the reduction as $620.00.

### C-007

ISSUE_002c: Cites Section 5.3 for photocopy rate violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L66))

- **Sonnet 4.6: Fail.** The criterion requires that Section 5.3 be cited as the applicable guideline for the internal photocopy rate violation (line 15, internal B&W copies). Looking at the report, line 15 (Internal B&W copies) in Section 1 does not cite any specific section number. The only mention of Section 5.3 in the report is in Section 2, where it references 'Section 5.3 / 5.1' for the DataScan Solutions scanning/OCR charge (line 19), not for the internal photocopy rate violation. Therefore, the report fails to cite Section 5.3 for the internal photocopy rate violation.
- **GPT-5.5: Fail.** The report identifies the internal B&W photocopy rate violation and calculates the reduction, but it does not cite Section 5.3 as the applicable guideline for that photocopy rate issue. Section 5.3 is cited elsewhere for pre-approval, and the general authorities list is not a specific citation for the photocopy violation.

### C-008

ISSUE_003a: Flags Line 42 Westlaw charges as non-reimbursable overhead ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L74))

- **Sonnet 4.6: Pass.** Line 42 (Westlaw research, $3,870.00) is explicitly flagged in Section 1 of the report as a recommended face-of-record reduction with the full $3,870.00 disallowed, with the basis stated as 'Legal research database charges are firm overhead, even if allocated to a particular matter.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 42, labeled 'Westlaw research' for $3,870.00, and states that legal research database charges are firm overhead and non-reimbursable, recommending a full $3,870.00 reduction.

### C-009

ISSUE_003b: Recommends full rejection of $3,870 Westlaw charge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L82))

- **Sonnet 4.6: Pass.** In Section 1 (Recommended face-of-record reductions), Line 42 (Westlaw research) shows a billed amount of $3,870.00 and a recommended reduction of $3,870.00 — the full amount — with the basis that legal research database charges are firm overhead. This satisfies the criterion of recommending full rejection of the $3,870 Westlaw charge.
- **GPT-5.5: Pass.** The report lists Line 42 Westlaw research billed at $3,870.00 with a recommended reduction of $3,870.00, stating legal research database charges are firm overhead. This is a full rejection of the charge.

### C-010

ISSUE_003c: Cites Section 5.1 and/or 5.8 for Westlaw overhead rule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L90))

- **Sonnet 4.6: Fail.** The report addresses Westlaw charges in line 42 of Section 1, stating 'Legal research database charges are firm overhead, even if allocated to a particular matter.' However, no specific guideline section (5.1, 5.8, or any other) is cited for this particular line item. The primary authorities section at the end mentions '§§5.1--5.9' broadly, but this is a general citation covering all recommendations, not a specific citation for the Westlaw overhead rule. The criterion requires that Section 5.1 and/or 5.8 be referenced as the basis for classifying Westlaw charges as non-billable overhead. Since no section-specific citation is provided for the Westlaw line item, this fails the criterion.
- **GPT-5.5: Fail.** The report classifies the Westlaw research charge as firm overhead, but the Westlaw line does not cite Guidelines Section 5.1 or 5.8 as the basis. A general end citation to §§5.1--5.9 is not tied to the Westlaw overhead determination.

### C-011

ISSUE_004a: Flags Line 10 mileage as non-reimbursable local travel ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L98))

- **Sonnet 4.6: Pass.** The report explicitly flags Line 10 (Charlotte local mileage, $9.80) in Section 1 as non-reimbursable, stating 'HWK Charlotte office to Pinnacle Charlotte HQ is expressly non-reimbursable local travel.' The full $9.80 is recommended for reduction.
- **GPT-5.5: Pass.** The report expressly flags Line 10 as “Charlotte local mileage” billed at $9.80, reduces the full $9.80, and states that travel from HWK Charlotte office to Pinnacle Charlotte HQ is expressly non-reimbursable local travel.

### C-012

ISSUE_004b: Recommends full rejection of $9.80 mileage charge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L106))

- **Sonnet 4.6: Pass.** Line 10 in the report shows Charlotte local mileage billed at $9.80 with a recommended reduction of $9.80, meaning the full amount is disallowed. The basis states it is expressly non-reimbursable local travel. This satisfies the criterion of recommending full rejection of the $9.80 mileage charge.
- **GPT-5.5: Pass.** The report identifies Line 10 as “Charlotte local mileage” with a billed amount of $9.80 and recommends reducing/rejecting the full $9.80 as non-reimbursable local travel.

### C-013

ISSUE_004c: Cites Section 5.2 for local travel prohibition ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L114))

- **Sonnet 4.6: Fail.** The report addresses local travel (line 10, Charlotte local mileage) but does not cite Section 5.2 as the applicable guideline. The only section references in the local travel entry are absent—no section number is cited for that line item. The report's general authority citation at the end references '§§5.1--5.9' broadly but does not specifically cite Section 5.2 for the local travel prohibition. The criterion requires a specific reference to Section 5.2 for the local travel prohibition.
- **GPT-5.5: Fail.** The report identifies the Charlotte local mileage as non-reimbursable local travel, but it does not cite Section 5.2 as the applicable guideline for that prohibition. A broad final reference to §§5.1--5.9 is not a specific citation to Section 5.2 for local travel.

### C-014

ISSUE_005a: Flags Line 5 dinner per-person cost exceeds $75/day cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L122))

- **Sonnet 4.6: Pass.** The report addresses Line 5 in the travel meals section: 'line 5 ($214 for 2) reduce $64'. This implies $214 / 2 = $107/person, which exceeds the $75/person/day cap, and the reduction of $64 = 2 × ($107 - $75) confirms the per-person overage was identified. The criterion requires identifying that Line 5 ($214 dinner for 2 people = $107/person) exceeds the $75/person/day cap, which the report does.
- **GPT-5.5: Pass.** The report explicitly flags Line 5 as a travel meal charge of $214 for 2 people and applies the $75/person/day cap, calculating a $64 reduction. This identifies the per-person overage required by the criterion.

### C-015

ISSUE_005b: Flags Line 6 M. Beale meals exceed $75/day cap on 05/03 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L130))

- **Sonnet 4.6: Pass.** The report explicitly addresses Line 6 in the travel meals section: 'line 6 ($82) reduce $7', which correctly identifies that Line 6 ($82) exceeds the $75/person/day cap by $7. This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 6 under travel meals, stating that the $82 charge exceeds the $75/person/day cap and should be reduced by $7.

### C-016

ISSUE_005c: Identifies Palermo's share of Line 5 dinner also exceeds cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L138))

- **Sonnet 4.6: Fail.** The report mentions line 5 ($214 for 2 people) with a reduction of $64, implying the total exceeds the $75/person/day cap by $64 ($214 - $150 = $64). However, it does not specifically identify J. Palermo or mention that Palermo's individual share ($107) exceeds the $75/person cap. The criterion requires explicit identification of Palermo's share exceeding the cap, which is not present in the report.
- **GPT-5.5: Fail.** The report notes Line 5 was $214 for 2 and applies a $64 reduction under the $75/person/day cap, but it does not mention J. Palermo or specifically identify Palermo's $107 share as exceeding the cap.

### C-017

ISSUE_005d: Calculates total meal overage approximately $71 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L146))

- **Sonnet 4.6: Fail.** The criterion requires the report to calculate total travel meal overage as approximately $71, broken down as $32 for Beale on 05/02, $7 for Beale on 05/03, and $32 for Palermo on 05/02. The agent's report shows travel meal reductions of $92 total across lines 5-7 and 13, with specific breakdowns: line 5 ($214 for 2) reduce $64; line 6 ($82) reduce $7; line 7 ($68) no reduction; line 13 ($96) reduce $21. These amounts ($64 + $7 + $21 = $92) do not match the expected ~$71 total, and the individual line overages don't correspond to the expected per-person breakdown ($32 + $7 + $32 = $71). The agent's calculation is significantly different from the criterion's expected values.
- **GPT-5.5: Fail.** The report calculates travel meal reductions as $92, including an extra $21 reduction for line 13. Although it includes reductions that partially correspond to the expected $64 + $7, it does not calculate the total travel meal overage as approximately $71 and states a significantly higher total.

### C-018

ISSUE_006a: Flags Dr. Hartsfield total May charges exceed $35K budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L154))

- **Sonnet 4.6: Pass.** The report explicitly identifies in Section 1 (Line 22, 27) that 'Hartsfield expert fees' total $40,900 ($32,500 + $8,400), that the approved monthly cap is $35,000 with GC concurrence, and recommends a reduction of $5,900 (the excess over the $35,000 cap). This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly identifies Lines 22 and 27 as Dr. Hartsfield expert fees totaling $40,900, notes the approved monthly cap is $35,000, and recommends a $5,900 reduction for the overrun.

### C-019

ISSUE_006b: Flags Dr. Hartsfield total exceeds $25K GC approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L162))

- **Sonnet 4.6: Fail.** The criterion requires the report to identify that Dr. Hartsfield's combined May charges of $40,900 exceed the $25,000/month threshold requiring General Counsel (Lorraine Cha) pre-approval under Section 5.4. Looking at the agent's output, in Section 1 (Recommended face-of-record reductions), lines 22 and 27 address the Hartsfield expert fees: 'Approved monthly cap is $35,000 with GC concurrence. May fees total $40,900; reduce the $8,400 rush-analysis line by $5,900 (leaving $2,500 under cap). No re-authorization located.' The report mentions a $35,000 monthly cap with GC concurrence, not a $25,000/month threshold requiring GC pre-approval under Section 5.4. The criterion specifically asks whether the report identifies that the $40,900 exceeds the $25,000/month threshold requiring GC pre-approval. The agent's report references a $35,000 cap (not $25,000) and mentions GC concurrence but does not specifically flag the $25,000/month threshold under Section 5.4 as the trigger for GC approval. The $25,000 threshold mentioned elsewhere in the report refers to per-invoice reduction authority, not the expert fee approval threshold. The criterion is specifically about the $25,000/month expert fee threshold requiring GC pre-approval under Section 5.4, which is not identified in the agent's output.
- **GPT-5.5: Fail.** The report flags Hartsfield’s combined May expert fees of $40,900 and notes GC concurrence in connection with the approved monthly cap, but it does not identify that the charges exceed the $25,000/month threshold requiring General Counsel Lorraine Cha pre-approval under Section 5.4. The specific threshold-based GC approval issue is therefore not adequately stated.

### C-020

ISSUE_006c: Cites Section 5.4 for expert fee threshold/pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L170))

- **Sonnet 4.6: Fail.** The report does not cite Section 5.4 anywhere. For expert fee pre-approval and the GC threshold, the report references 'Section 5.3 / 5.1' (in the holds table for line 19) and 'Billing Guidelines §§5.1--5.9, 6.6--6.7, 8.1--8.6 and Appendices A/C' in the primary authorities. Section 5.4 is never mentioned as the applicable guideline for expert fee pre-approval or the $25,000/month GC threshold.
- **GPT-5.5: Fail.** The report discusses expert fee approvals and caps, but it does not specifically cite Section 5.4 as the applicable guideline for expert fee pre-approval or the $25,000/month GC threshold. A broad reference to §§5.1--5.9 is insufficient under the criterion.

### C-021

ISSUE_007a: Flags Line 24 Dr. Voss as lacking pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L178))

- **Sonnet 4.6: Pass.** The report explicitly flags Line 24 (Dr. Leonard Voss vocational expert, $4,200) in Section 2 as lacking advance approval, noting 'Expert retention requires advance Relationship Attorney approval at any amount; no approval located. Hold in full pending retroactive approval and original invoice.' This satisfies the criterion of identifying Line 24 as non-compliant due to missing required written pre-approval for expert retention.
- **GPT-5.5: Pass.** The report specifically lists Line 24, Dr. Leonard Voss vocational expert for $4,200, and states that expert retention requires advance approval with no approval located, recommending the charge be held pending retroactive approval. This satisfies the requirement to flag Line 24 for missing written pre-approval.

### C-022

ISSUE_007b: Flags Line 25 GraphicWorks as lacking pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L186))

- **Sonnet 4.6: Pass.** The report explicitly flags Line 25 (GraphicWorks litigation graphics, $7,850) in Section 2 as lacking pre-approval, noting it exceeds $5,000 and no approval was located, recommending it be held pending approval, scope clarification, and vendor invoice. This satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags Line 25, GraphicWorks litigation graphics for $7,850, stating that no approval was located and recommending holding the charge pending approval, scope clarification, and vendor invoice. This satisfies the requirement to identify the charge as non-compliant for missing required pre-approval.

### C-023

ISSUE_007c: Identifies total at-risk amount for unapproved experts ($12,050) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L194))

- **Sonnet 4.6: Fail.** The criterion requires that the report states or shows the combined at-risk amount for Dr. Voss ($4,200) and GraphicWorks ($7,850) equals $12,050. The agent's report lists these two items separately in Section 2 but never explicitly calculates or states their combined total of $12,050. The total shown in Section 2 is $30,190, which includes all five unapproved charges (DataScan $6,800 + Dr. Voss $4,200 + GraphicWorks $7,850 + TechForensic $5,100 + A. Brooks $6,240 = $30,190). The specific sub-total of $12,050 for just the two expert/consultant charges is never identified.
- **GPT-5.5: Fail.** The report lists Dr. Voss at $4,200 and GraphicWorks at $7,850 as unapproved/held charges, but it does not calculate or state their combined at-risk amount of $12,050. The only total provided for the hold category is $30,190 including other items.

### C-024

ISSUE_008a: Flags Line 45 contract attorney R. Chen rate exceeds $65/hr cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L202))

- **Sonnet 4.6: Pass.** The report explicitly identifies Line 45 (R. Chen contract attorney) as billed at $75/hour for 142 hours ($10,650), notes the approval expressly limited Chen to $65/hour, calculates the allowable amount as 142 × $65 = $9,230, and recommends a reduction of $1,420. This clearly flags the rate violation as required by the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 45, R. Chen contract attorney, stating approval was limited to $65/hour but it was billed at $75 for 142 hours, allowing only 142 × $65 = $9,230 and recommending a $1,420 reduction. This satisfies the criterion.

### C-025

ISSUE_008b: Calculates R. Chen rate overcharge as $1,420 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L210))

- **Sonnet 4.6: Pass.** The report explicitly states for line 45 (R. Chen contract attorney): 'Approval expressly limited Chen to $65/hour; billed at $75 for 142 hours. Allow at most 142 × $65 = $9,230.' The reduction shown is $1,420, which matches ($75 - $65) × 142 = $1,420. The criterion is satisfied.
- **GPT-5.5: Pass.** The report explicitly calculates R. Chen's overcharge as billed at $75/hour for 142 hours versus approved $65/hour, allowing $9,230 and reducing $1,420 from the $10,650 billed amount.

### C-026

ISSUE_008c: Cites Section 5.9 for contract attorney rate cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L218))

- **Sonnet 4.6: Fail.** The report does not cite Section 5.9 specifically for the contract attorney rate cap. In Section 1 (recommended face-of-record reductions), the line for R. Chen contract attorney (line 45) mentions the rate cap of $65/hour but does not cite Section 5.9. In Section 2, the holds section cites 'Section 5.3 / 5.1' for the DataScan line but no section citation appears for contract attorney rate caps. The only reference to Section 5.9 in the entire document is in the 'Primary authorities' footer listing '§§5.1--5.9' as a range, which is not a specific citation of 5.9 for the contract attorney rate cap. The criterion requires Section 5.9 to be cited as the applicable guideline for the contract attorney rate cap of $65/hour, which is not done.
- **GPT-5.5: Fail.** The report discusses contract attorney charges and the $65/hour cap, but it does not specifically cite Section 5.9 as the applicable guideline for that rate cap. A broad end citation to §§5.1--5.9 is not tied to the contract attorney rate cap.

### C-027

ISSUE_009a: Flags Line 47 A. Brooks as not pre-approved ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L226))

- **Sonnet 4.6: Pass.** The agent's output explicitly flags Line 47 (A. Brooks contract attorney, $6,240) in Section 2 as lacking pre-approval. The report states: 'Each contract attorney requires separate advance approval. The log approves Chen and Mehta only; no Brooks approval located. Hold in full pending retroactive approval and staffing-agency invoice.' This directly satisfies the criterion of identifying Line 47 as non-compliant due to missing pre-approval.
- **GPT-5.5: Pass.** The report explicitly flags Line 47 for A. Brooks, a contract attorney billed at $6,240, stating that each contract attorney requires separate advance approval and that no Brooks approval was located. It recommends holding the charge pending retroactive approval, satisfying the criterion.

### C-028

ISSUE_009b: Identifies full $6,240 as at-risk for A. Brooks ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L234))

- **Sonnet 4.6: Pass.** In Section 2 (Charges to hold for missing pre-approval), Line 47 for A. Brooks contract attorney is listed with an amount of $6,240.00, and the recommendation states to hold the full amount pending retroactive approval. The total at-risk amount of $30,190.00 includes this $6,240. The criterion requires the report to identify the full $6,240 as at risk or requiring retroactive approval, which it does.
- **GPT-5.5: Pass.** The report lists line 47, A. Brooks contract attorney, with an amount of $6,240.00 and states it should be held in full pending retroactive approval, included in the total at risk.

### C-029

ISSUE_010a: Flags Line 41 e-discovery hosting exceeds pre-approved budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L242))

- **Sonnet 4.6: Pass.** The report explicitly addresses Lines 41 and 44 together in the face-of-record reductions table. It states the approved monthly cap is $12,000 for the Relativity workflow, that the two lines total $14,200 + $2,200 = $16,400, and recommends a $4,400 reduction. The e-discovery qualification section further clarifies that the $2,200 excess on line 41 over the approved Relativity cap 'remains unsupported.' This clearly identifies Line 41 as exceeding the pre-approved $12,000 budget.
- **GPT-5.5: Pass.** The report explicitly discusses Lines 41 and 44 for e-discovery/predictive coding, states the approved monthly cap is $12,000, and notes Line 41 is $14,200 with a $2,200 excess over the approved Relativity cap. This identifies Line 41 as exceeding the pre-approved $12,000/month budget.

### C-030

ISSUE_010b: Calculates e-discovery hosting overage as $2,200 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L250))

- **Sonnet 4.6: Fail.** The criterion requires the report to calculate the e-discovery hosting overage as $14,200 - $12,000 = $2,200. Looking at the agent's output, in Section 1 under lines 41 and 44, it states 'Lines total $14,200 + $2,200' which appears to mean line 41 is $14,200 and line 44 is $2,200, totaling $16,400. The report does not calculate an overage of $14,200 - $12,000 = $2,200. Instead, it calculates a total reduction of $4,400 (allowing $12,000 of the $16,400 total). The $2,200 figure appears in the qualification section but in a different context: 'revisit $2,200 of that recommendation' referring to line 44's amount, not as an overage calculation of $14,200 - $12,000. The criterion specifically requires the overage to be calculated as $14,200 - $12,000 = $2,200, which is not present in the report.
- **GPT-5.5: Pass.** The report explicitly states that line 41 was billed at $14,200 against the approved $12,000 Relativity cap and identifies the resulting excess as $2,200, satisfying the required calculation.

### C-031

ISSUE_010c: Cites Section 5.8 for e-discovery pre-approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L258))

- **Sonnet 4.6: Fail.** The criterion requires the report to reference Section 5.8 (and/or Section 5.1) as the applicable guideline for e-discovery hosting pre-approval. Looking at the agent's output, the e-discovery lines (41 and 44) are discussed in Section 1 (face-of-record reductions) and in the executive summary, but no specific guideline section is cited for those lines. The only section citations in the disbursement table are 'Section 5.3 / 5.1' for line 19 (DataScan scanning/OCR). Section 5.8 is never mentioned anywhere in the report. The primary authorities listed at the end reference '§§5.1--5.9' as a range but does not specifically call out 5.8 for e-discovery pre-approval. The criterion specifically asks for Section 5.8 to be cited for e-discovery hosting pre-approval, and it is not cited in connection with the e-discovery lines.
- **GPT-5.5: Fail.** The report discusses e-discovery charges and an approved cap, but it does not cite Section 5.8 or Section 5.1 as the applicable pre-approval guideline for e-discovery hosting. The only Section 5.1 references are general or tied to other charges, not the e-discovery pre-approval threshold.

### C-032

ISSUE_011a: Flags Line 38 dinner includes ineligible summer associates ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L266))

- **Sonnet 4.6: Pass.** The agent's report addresses Line 38 ($612) in Section 1 under 'Non-travel working meals,' stating it is 'firm-only, including summer associates: disallow all.' This identifies the charge as non-compliant and recommends full disallowance. However, the criterion requires that the report identify the ineligibility specifically because Section 5.7 limits reimbursable working meals to those involving Pinnacle personnel or third-party witnesses, and summer associates qualify as neither. The agent's report does flag Line 38 as non-compliant due to summer associates being included, but the reasoning given is 'firm-only, including summer associates: disallow all' — which captures the essence that the meal was internal firm-only (not involving Pinnacle personnel or third-party witnesses). The criterion asks whether the ineligibility of summer associates is identified, which it is. The specific section citation (5.7) is not mentioned, but the substantive reason (firm-only meal including summer associates) aligns with the criterion's requirement. The criterion says PASS if the report identifies Line 38 as non-compliant because summer associates qualify as neither Pinnacle personnel nor third-party witnesses — the agent does identify this by noting it's 'firm-only, including summer associates.' This satisfies the criterion.
- **GPT-5.5: Pass.** The report specifically flags Line 38, describes it as a firm-only meal including summer associates, and recommends disallowing the full $612. This identifies the summer associates as ineligible participants for a reimbursable working meal, satisfying the criterion.

### C-033

ISSUE_011b: Identifies per-person cost exceeds $85 dinner cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L274))

- **Sonnet 4.6: Fail.** The report addresses line 38 ($612) by stating it is 'firm-only, including summer associates: disallow all.' It does not identify or calculate the per-person cost of $612/5 = $122.40 exceeding an $85/person working dinner cap. The basis for rejection is that it's a firm-only meal, not a per-person cap violation. The criterion specifically requires identification of the per-person cap violation ($122.40 vs $85 cap).
- **GPT-5.5: Fail.** The report mentions the $612 line and recommends disallowing it because it is firm-only and includes summer associates, but it does not identify that $612 for 5 attendees equals $122.40 per person and exceeds the $85/person working dinner cap.

### C-034

ISSUE_011c: Calculates Line 38 recommended reduction accounting for both ineligible attendees and per-person cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L282))

- **Sonnet 4.6: Fail.** The agent's report for Line 38 states: 'Line 38 ($612) is firm-only, including summer associates: disallow all.' The agent recommends a full $612 reduction by treating the charge as entirely disallowable because it is a firm-only meal including summer associates. The criterion requires the report to calculate a reduction that accounts for BOTH the exclusion of 2 ineligible summer associates AND the $85/person dinner cap for the 3 eligible attendees, arriving at approximately $357 ($612 - $255 = $357). The agent instead disallows the entire $612 without applying the per-person cap to eligible attendees. This deviates from the required $357 reduction by $255, which is well beyond the $20 tolerance. Therefore, the criterion is not satisfied.
- **GPT-5.5: Fail.** The report does not calculate Line 38 as $612 minus the compliant amount for 3 eligible attendees at the $85/person dinner cap ($255), i.e. an approximately $357 reduction. Instead, it disallows Line 38 in full as a firm-only meal, reducing $612 and failing to account for the 3 eligible attendees and applicable cap.

### C-035

ISSUE_012a: Flags Line 39 solo working lunch as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L290))

- **Sonnet 4.6: Pass.** The agent's output does flag Line 39 as non-reimbursable. In Section 1 (Recommended face-of-record reductions), the table entry for lines 37-39 states: 'Line 39 ($24) is a solo firm meal: disallow all.' This identifies the solo meal as non-reimbursable. However, the criterion specifies that the report must identify it as non-compliant because Section 5.7 requires working meals to involve Pinnacle personnel or third-party witnesses. The agent's report does flag Line 39 and recommends disallowing it, but the reasoning given is simply that it is 'a solo firm meal' without explicitly citing Section 5.7 or the specific requirement that working meals must involve Pinnacle personnel or third-party witnesses. The criterion says PASS if the report identifies Line 39 as non-compliant because Section 5.7 requires working meals to involve Pinnacle personnel or third-party witnesses. The agent does flag it as non-compliant (solo firm meal, disallow all), but does not explicitly cite Section 5.7 or articulate the specific rule about Pinnacle personnel or third-party witnesses. The criterion's PASS condition requires identification of the specific reason (Section 5.7 / Pinnacle personnel or third-party witnesses requirement). The agent's output does not mention Section 5.7 or the specific requirement about Pinnacle personnel or third-party witnesses for Line 39. However, the criterion also says FAIL only if 'Line 39 is not flagged.' Since Line 39 IS flagged as non-reimbursable, this suggests the PASS condition is met even without the specific citation. Reading the criterion carefully: 'PASS if the report identifies Line 39 ($24 solo working lunch for M. Beale at desk) as non-compliant because Section 5.7 requires working meals to involve Pinnacle personnel or third-party witnesses, and a solo lunch does not qualify. FAIL if Line 39 is not flagged.' The FAIL condition is simply 'if Line 39 is not flagged.' Since Line 39 IS flagged, the verdict should be PASS.
- **GPT-5.5: Pass.** The report explicitly includes Line 39 in the non-travel working meals reductions and states that the $24 solo firm meal should be disallowed in full, with a later note that Lines 38–39 are recommended for full rejection.

### C-036

ISSUE_012b: Recommends full rejection of $24 for Line 39 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L298))

- **Sonnet 4.6: Pass.** In Section 1, the report states for lines 37-39: 'Line 39 ($24) is a solo firm meal: disallow all.' This clearly recommends full rejection of the $24.00 for Line 39.
- **GPT-5.5: Pass.** The report explicitly states for Lines 37--39 that Line 39 ($24) is a solo firm meal and should be disallowed in full, and later notes Lines 38--39 are already recommended for full rejection.

### C-037

ISSUE_013a: Flags Line 36 courier for office supplies as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L306))

- **Sonnet 4.6: Pass.** Line 36 is explicitly flagged in Section 1 (Recommended face-of-record reductions) as 'FedEx---office supplies' with a $18.50 reduction, with the basis stated as 'Shipment of firm office supplies is overhead / non-reimbursable.' This satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags Line 36 ($18.50 FedEx—office supplies), recommends reducing the full amount, and states that shipment of firm office supplies is overhead/non-reimbursable.

### C-038

ISSUE_013b: Recommends full rejection of $18.50 for Line 36 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L314))

- **Sonnet 4.6: Pass.** In Section 1 (Recommended face-of-record reductions), Line 36 (FedEx—office supplies) shows a billed amount of $18.50 and a recommended reduction of $18.50, with the basis being 'Shipment of firm office supplies is overhead / non-reimbursable.' This is a full rejection of the $18.50 charge.
- **GPT-5.5: Pass.** The report lists Line 36 (FedEx—office supplies) with billed amount $18.50 and a recommended reduction of $18.50, stating it is overhead/non-reimbursable, which is a full rejection.

### C-039

ISSUE_014a: Flags Line 19 scanning charge exceeds $5K without pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L322))

- **Sonnet 4.6: Pass.** The report explicitly identifies Line 19 (DataScan Solutions scanning/OCR, $6,800) in Section 2 as exceeding the $5,000 threshold with no advance approval located, citing Section 5.3/5.1, and recommends holding the entire charge pending retroactive approval and vendor invoice.
- **GPT-5.5: Pass.** The report explicitly flags Line 19, DataScan Solutions scanning/OCR for $6,800, states that the single line exceeds the $5,000 threshold, cites Section 5.1, and notes that no advance approval was located.

### C-040

ISSUE_014b: Identifies Line 19 as requiring retroactive approval or hold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L330))

- **Sonnet 4.6: Pass.** The report explicitly addresses Line 19 (DataScan Solutions scanning/OCR, $6,800.00) in Section 2, recommending it be held pending retroactive approval and vendor invoice, noting it exceeds the $5,000 threshold with no advance approval located. The full $6,800 is flagged as at risk if retroactive approval is denied. This satisfies the criterion.
- **GPT-5.5: Pass.** The report specifically identifies Line 19, the $6,800 DataScan Solutions scanning/OCR charge, and recommends holding the entire charge pending retroactive approval and vendor invoice. This satisfies the criterion.

### C-041

ISSUE_015: Flags invoice total arithmetic discrepancy ($0.11) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L338))

- **Sonnet 4.6: Fail.** The criterion requires the report to identify a specific $0.11 discrepancy between the stated invoice disbursement total of $86,742.19 and the sum of the 47 line items ($86,742.30). The agent's report identifies a discrepancy between the Summary sheet total ($86,742.19) and the sum of the 47 disbursement lines, but states the line items sum to $145,404.30, resulting in a $58,662.11 difference. The agent does not identify the specific $0.11 arithmetic discrepancy described in the criterion. The criterion is looking for a very specific, minor $0.11 discrepancy, not the large $58,662.11 discrepancy the agent found.
- **GPT-5.5: Fail.** The report flags a reconciliation issue, but it states the 47 line items total $145,404.30 and identifies a $58,662.11 discrepancy, rather than identifying the required $0.11 discrepancy between $86,742.19 and $86,742.30.

### C-042

ISSUE_016a: Flags Line 14 rental car as full-size exceeding mid-size limit ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L346))

- **Sonnet 4.6: Pass.** The report explicitly flags Line 14 as a full-size rental car at $127.00, noting that 'Only mid-size or smaller is reimbursable' and that no unavailability or mid-size comparison is shown. It recommends capping at the supported mid-size rate or rejecting if not substantiated. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report specifically flags Line 14, identifies it as a full-size rental car, states that only mid-size or smaller rentals are reimbursable, and recommends capping/rejecting absent support. This satisfies the criterion.

### C-043

ISSUE_016b: Provides a disposition recommendation for Line 14 rental car charge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L354))

- **Sonnet 4.6: Pass.** The report addresses Line 14 (full-size rental car, $127.00) in Section 3, stating 'Only mid-size or smaller is reimbursable. No unavailability or mid-size comparison is shown. Cap at supported mid-size rate; if not substantiated, reject.' This satisfies criterion (a) by requesting documentation of the mid-size rate for adjustment, and also includes a conditional rejection recommendation. The criterion is met.
- **GPT-5.5: Pass.** The report specifically addresses Line 14, notes that only mid-size or smaller rental cars are reimbursable, states that no mid-size comparison is shown, and recommends capping the charge at a supported mid-size rate or rejecting it if not substantiated. This satisfies the required disposition recommendation.

### C-044

ISSUE_017a: Flags Line 40 dinner with opposing counsel as problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L362))

- **Sonnet 4.6: Fail.** The agent's output does address Line 40 in Section 3 (Documentation, description, and rate issues to resolve), but it does NOT flag it as potentially non-compliant on the grounds that a dinner with opposing counsel may constitute client entertainment (non-reimbursable under Section 5.7) or that it fails to meet working meal criteria requiring Pinnacle personnel or third-party witnesses. Instead, the agent treats Line 40 as facially within the per-person cap and only requests better documentation (itemized receipt, attendee names/titles, confirmation of no alcohol, tip within cap, revised narrative). The criterion requires the report to flag the dinner with plaintiff's counsel as potentially non-compliant due to the entertainment concern or the working meal criteria issue. The agent failed to raise this substantive compliance concern.
- **GPT-5.5: Fail.** The report mentions Line 40 only as a documentation/receipt issue and says it is within the dinner cap on its face. It does not flag the dinner with plaintiff’s counsel as potentially non-reimbursable client entertainment or as failing the working-meal criteria requiring Pinnacle personnel or third-party witnesses.

### C-045

ISSUE_017b: Identifies Line 40 per-person cost exceeds $85 dinner cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L370))

- **Sonnet 4.6: Fail.** The agent's report discusses Line 40 (working dinner, $247.00) but states 'at least 3 attendees are indicated, so $247 is within a $255 three-person dinner cap on its face.' The agent assumed 3 attendees and compared against a $255 cap (3 × $85). However, the criterion requires identifying that with 2 attendees, $247 / 2 = $123.50 per person exceeds the $85/person cap, for a total excess of $77. The agent did not identify this per-person cap violation for Line 40 as described in the criterion.
- **GPT-5.5: Fail.** The report does not identify the required Line 40 violation. Instead, it treats Line 40 as involving at least three attendees and says $247 is within a $255 cap, rather than calculating $247 / 2 = $123.50 per person and identifying the $77 excess over the $85 dinner cap.

### C-046

ISSUE_018a: Flags Line 12 Washington D.C. hotel exceeds Tier 1 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L378))

- **Sonnet 4.6: Pass.** The report explicitly flags Line 12 (Washington, D.C. hotel) as non-compliant, noting the Tier 1 cap of $275/night and recommending a reduction of $73 on the $348 one-night charge, with no exception approval located. This satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags Line 12, the Washington, D.C. hotel charge of $348, as exceeding the Tier 1 $275/night cap and recommends a $73 reduction.

### C-047

ISSUE_018b: Calculates Washington D.C. hotel overage as $73 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L386))

- **Sonnet 4.6: Pass.** The report explicitly states for line 12: 'Washington, D.C. hotel $348.00 $73.00 Tier 1 cap $275/night; reduce the $348 one-night charge by $73.' This correctly calculates $348 - $275 = $73.
- **GPT-5.5: Pass.** The report explicitly calculates the Washington, D.C. hotel overage as a $348 one-night charge minus the $275 Tier 1 cap, resulting in a $73 reduction.

### C-048

ISSUE_019a: Flags Line 13 C. Aldridge D.C. meals exceed $75/day cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L394))

- **Sonnet 4.6: Pass.** In Section 1, the agent's table for travel meals (lines 5–7, 13) explicitly states: 'line 13 ($96) reduce $21.' This identifies Line 13 as exceeding the $75/person/day cap (reducing $96 to $75, a $21 reduction). The criterion requires flagging Line 13 for the daily cap violation, which the agent has done.
- **GPT-5.5: Pass.** The report explicitly includes Line 13 in the travel meals reduction table, states it was billed at $96, and calculates a $21 reduction under the $75/person/day cap.

### C-049

ISSUE_019b: Calculates D.C. meal overage as $21 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L402))

- **Sonnet 4.6: Pass.** In Section 1, line 13 (Washington D.C. travel meal), the report states: 'line 13 ($96) reduce $21.' This matches the calculation $96 - $75 = $21 exactly.
- **GPT-5.5: Pass.** The report explicitly lists travel meals and states line 13 ($96) reduce $21, which matches the D.C. meal overage calculation $96 - $75 = $21.

### C-050

Summary table includes total billed disbursements ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L410))

- **Sonnet 4.6: Pass.** The report's summary table (AMOUNT CHECK section) explicitly states 'Disbursements stated on Summary sheet: $86,742.19' and 'Sum of the 47 listed Disbursement lines: $145,404.30'. The criterion asks whether the report includes a summary table or section that states the total billed disbursements (approximately $86,742.19 as stated on the invoice). This amount is clearly present in the report.
- **GPT-5.5: Pass.** The report includes an 'AMOUNT CHECK' summary table that states 'Disbursements stated on Summary sheet' as $86,742.19, satisfying the requirement to provide the total billed disbursements.

### C-051

Summary table includes total recommended reductions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L418))

- **Sonnet 4.6: Pass.** The report includes a summary table in Section 1 that shows 'TOTAL RECOMMENDED REDUCTIONS: $17,358.30' and Section 2 shows 'TOTAL AT RISK IF NOT RETROACTIVELY APPROVED: $30,190.00'. The executive determination section also summarizes these amounts. The criterion requires a total recommended reduction amount to be provided, which is clearly present in the report.
- **GPT-5.5: Pass.** The report includes summary/amount sections with a total recommended reductions figure of $17,358.30 and also identifies $30,190.00 in additional unapproved charges, noting cumulative reductions of $47,548.30 if those are rejected.

### C-052

Summary table includes amount pending approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L426))

- **Sonnet 4.6: Pass.** Section 2 of the report contains a table titled 'Charges to hold for missing pre-approval' that lists individual charges (lines 19, 24, 25, 26, 47) with their amounts and a total of $30,190.00 labeled 'TOTAL AT RISK IF NOT RETROACTIVELY APPROVED.' This clearly identifies a total amount held pending further approval or retroactive authorization.
- **GPT-5.5: Pass.** The report includes an amount check summary listing “Additional unapproved charges to hold; reject if retroactive approval is denied” as $30,190.00, and a dedicated section “Charges to hold for missing pre-approval” with a total at risk if not retroactively approved of $30,190.00.

### C-053

Summary table includes recommended net payable amount ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L434))

- **Sonnet 4.6: Fail.** The report provides various amounts (total billed disbursements of $145,404.30, recommended reductions of $17,358.30, holds of $30,190.00, and line-based disbursements after reductions of $128,046.00) but does not explicitly calculate or present a single recommended net payable disbursement amount in a summary table or section. The summary table at the top shows intermediate figures but stops short of presenting a final 'recommended net payable' figure. The $128,046.00 figure ('Line-based disbursements after those reductions; before holds / documentation issues') is the closest approximation, but it is explicitly noted as being 'before holds/documentation issues' and is not labeled as a recommended net payable amount. No final net payable figure combining all adjustments is presented.
- **GPT-5.5: Fail.** The report includes an amount-check table with total line-item disbursements, recommended reductions, and a post-reduction amount of $128,046.00, plus $30,190.00 in charges to hold. However, it does not provide or label a recommended net payable disbursement amount after subtracting reductions and held amounts; the stated post-reduction figure is expressly “before holds / documentation issues.”

### C-054

Report distinguishes outright rejections from pending-approval items ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L442))

- **Sonnet 4.6: Pass.** The report clearly distinguishes between two categories of non-compliant charges. Section 1 ('Recommended face-of-record reductions') lists charges that are outright rejected/reduced on the face of the record—such as Westlaw research (overhead, disallow entirely), local mileage (non-reimbursable, disallow), solo firm meal line 39 (disallow all), firm-only meal line 38 (disallow all), and other rate-cap excesses. Section 2 ('Charges to hold for missing pre-approval') separately identifies charges that should be held pending retroactive approval—including Dr. Leonard Voss (expert, no approval), GraphicWorks (no approval), DataScan Solutions (no approval), TechForensic ESI imaging (no approval), and A. Brooks contract attorney (no approval). The report explicitly states that retroactive approval is discretionary and not presumed, and that if approval is denied, the charges should be rejected. This is a clear structural and substantive distinction between outright rejections and pending-approval holds.
- **GPT-5.5: Pass.** The report clearly separates definite face-of-record reductions/outright non-reimbursable items (e.g., local mileage, Westlaw overhead, solo/firm meals, office supplies) from charges to be held pending retroactive approval or documentation (e.g., DataScan, Dr. Voss, GraphicWorks, TechForensic, A. Brooks). It explicitly states hold/reject-if-approval-denied treatment for the latter.

### C-055

Line 25 GraphicWorks also flagged for exceeding $5,000 pre-approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L450))

- **Sonnet 4.6: Pass.** In Section 2 of the report, Line 25 (GraphicWorks litigation graphics, $7,850) is described as: 'Line exceeds $5,000; graphics/demonstrative consulting can qualify as a consultant. No approval located.' This explicitly mentions that the line exceeds the $5,000 threshold, satisfying the criterion.
- **GPT-5.5: Pass.** The report specifically lists Line 25 GraphicWorks litigation graphics for $7,850 and states that the line exceeds $5,000, with no approval located, noting it may also qualify as a consultant. This satisfies the requirement to mention the $5,000 per-line-item pre-approval threshold in connection with the charge.

### C-056

Guideline section references provided for at least 75% of flagged violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L458))

- **Sonnet 4.6: Fail.** I need to count the flagged line items and check how many include specific guideline section citations. Flagged line items (non-compliant): Section 1 (Recommended reductions): 1. Lines 3-4: San Francisco hotels - no section cited 2. Line 12: Washington DC hotel - no section cited 3. Lines 5-7, 13: Travel meals - no section cited 4. Line 10: Charlotte local mileage - no section cited 5. Line 15: Internal B&W copies - no section cited 6. Lines 22, 27: Hartsfield expert fees - no section cited 7. Lines 37-39: Non-travel working meals - no section cited 8. Line 36: FedEx office supplies - no section cited 9. Line 42: Westlaw research - no section cited 10. Line 43: Routine video platform license - no section cited 11. Lines 41, 44: E-discovery/predictive coding - no section cited 12. Line 45: R. Chen contract attorney - no section cited Section 2 (Charges to hold): 13. Line 19: DataScan Solutions - cites "Section 5.3 / 5.1" ✓ 14. Line 24: Dr. Leonard Voss - no specific section cited 15. Line 25: GraphicWorks - no specific section cited 16. Line 26: TechForensic ESI - no specific section cited 17. Line 47: A. Brooks contract attorney - no specific section cited Section 3 (Documentation issues): 18. Lines 1-2: Airfare - no section cited 19. Lines 8-9: Rideshare - no section cited 20. Line 14: Full-size rental car - no section cited 21. Lines 17-18, 20: Outside print/binding - no section cited 22. Lines 32-35: Courier/express - no section cited 23. Line 40: Working dinner - no section cited 24. Lines 5-7, 13, 37-40: Meals/receipts - no section cited 25. Lines 16, 21: Color copies - no section cited 26. Lines 23, 46: Redmond/S. Mehta - no section cited 27. Lines 28-31: Routine court costs - no section cited Only 1 out of ~27 flagged items has a specific section citation (Line 19 with Section 5.3/5.1). The footer mentions general sections but these are not tied to specific violations. The criterion requires at least 75% of flagged violations to include specific guideline section numbers. Only approximately 1/27 (~3.7%) include specific section citations. This clearly fails the 75% threshold.
- **GPT-5.5: Fail.** Fewer than 75% of the flagged non-compliant disbursement items include specific Billing Guideline section citations in the item-level analysis. Most flagged reductions and holds describe the rule or cap but do not cite a section number; only a small number, such as line 19 and the reconciliation issue, include specific section references. The general authority list at the end does not provide item-specific citations for at least 75% of flagged violations.

### C-057

Billed amounts stated for at least 75% of flagged violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L466))

- **Sonnet 4.6: Pass.** Let me count the flagged line items and check whether each includes a billed dollar amount. Section 1 (Recommended face-of-record reductions): 1. Lines 3-4: San Francisco hotels - $1,276.00 ✓ 2. Line 12: Washington D.C. hotel - $348.00 ✓ 3. Lines 5-7, 13: Travel meals - $460.00 ✓ 4. Line 10: Charlotte local mileage - $9.80 ✓ 5. Line 15: Internal B&W copies - $1,860.00 ✓ 6. Lines 22, 27: Hartsfield expert fees - $40,900.00 ✓ 7. Lines 37-39: Non-travel working meals - $754.00 ✓ 8. Line 36: FedEx office supplies - $18.50 ✓ 9. Line 42: Westlaw research - $3,870.00 ✓ 10. Line 43: Routine video platform license - $125.00 ✓ 11. Lines 41, 44: E-discovery/predictive coding - $16,400.00 ✓ 12. Line 45: R. Chen contract attorney - $10,650.00 ✓ Section 2 (Charges to hold for missing pre-approval): 13. Line 19: DataScan Solutions - $6,800.00 ✓ 14. Line 24: Dr. Leonard Voss - $4,200.00 ✓ 15. Line 25: GraphicWorks - $7,850.00 ✓ 16. Line 26: TechForensic ESI imaging - $5,100.00 ✓ 17. Line 47: A. Brooks contract attorney - $6,240.00 ✓ Section 3 (Documentation issues): 18. Lines 1-2: Airfare - $974.00 ✓ 19. Lines 8-9: Rideshare - $181.50 ✓ 20. Line 14: Full-size rental car - $127.00 ✓ 21. Lines 17-18, 20: Outside print/binding - $6,015.00 ✓ 22. Lines 32-35: Courier/express - $140.50 ✓ 23. Line 40: Working dinner - $247.00 ✓ 24. Lines 5-7, 13, 37-40: Meals/receipts - no specific amount listed here (this is a general documentation note referencing already-listed lines) - this is a cross-reference, not a new flagged item 25. Lines 16, 21: Color copies - $265.00 ✓ 26. Lines 23, 46: Redmond/S. Mehta - $29,670.00 ✓ 27. Lines 28-31: Routine court costs - $511.00 ✓ The meals/receipts row in Section 3 is largely a cross-reference to already-flagged lines. Nearly all distinct flagged line items include billed dollar amounts. The count shows well over 75% (essentially all distinct flagged items) include billed amounts.
- **GPT-5.5: Pass.** The report provides billed amounts for the vast majority of flagged non-compliant items, including all face-of-record reductions in a BILLED column and all missing-preapproval holds in an AMOUNT column. Most documentation/rate issues also state dollar amounts. Even if a few grouped documentation items lack a separate aggregate amount, well over 75% of flagged violations include the billed dollar amount.
