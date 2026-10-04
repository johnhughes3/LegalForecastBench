# Claude Opus 5.5 (low): Verify Disbursement Charges Against Outside Counsel Billing Guidelines — Compliance Report

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/verify-disbursement-charges-against-billing-guidelines/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 51 of 57 criteria; GPT-5.5 passed 50 of 57 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [disbursement-compliance-report.docx](output/disbursement-compliance-report.docx) ([read as Markdown](output/disbursement-compliance-report.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001a: Flags Line 3 hotel rate exceeds Tier 1 cap ($319 vs $275/night) | Pass | Pass |
| [C-002](#c-002) | ISSUE_001b: Flags Line 4 hotel rate exceeds Tier 1 cap ($319 vs $275/night) | Pass | Pass |
| [C-003](#c-003) | ISSUE_001c: Correctly calculates hotel overage for Lines 3 and 4 | Pass | Pass |
| [C-004](#c-004) | ISSUE_001d: Cites Section 5.2 for hotel rate violation | Pass | Pass |
| [C-005](#c-005) | ISSUE_002a: Flags Line 15 internal photocopy rate of $0.15 vs guideline $0.10 | Pass | Pass |
| [C-006](#c-006) | ISSUE_002b: Calculates photocopy overcharge as $620 | Pass | Pass |
| [C-007](#c-007) | ISSUE_002c: Cites Section 5.3 for photocopy rate violation | Pass | Pass |
| [C-008](#c-008) | ISSUE_003a: Flags Line 42 Westlaw charges as non-reimbursable overhead | Pass | Pass |
| [C-009](#c-009) | ISSUE_003b: Recommends full rejection of $3,870 Westlaw charge | Pass | Pass |
| [C-010](#c-010) | ISSUE_003c: Cites Section 5.1 and/or 5.8 for Westlaw overhead rule | Pass | Pass |
| [C-011](#c-011) | ISSUE_004a: Flags Line 10 mileage as non-reimbursable local travel | Pass | Pass |
| [C-012](#c-012) | ISSUE_004b: Recommends full rejection of $9.80 mileage charge | Pass | Pass |
| [C-013](#c-013) | ISSUE_004c: Cites Section 5.2 for local travel prohibition | Pass | Pass |
| [C-014](#c-014) | ISSUE_005a: Flags Line 5 dinner per-person cost exceeds $75/day cap | Pass | Pass |
| [C-015](#c-015) | ISSUE_005b: Flags Line 6 M. Beale meals exceed $75/day cap on 05/03 | Pass | Pass |
| [C-016](#c-016) | ISSUE_005c: Identifies Palermo's share of Line 5 dinner also exceeds cap | **Fail** | **Fail** |
| [C-017](#c-017) | ISSUE_005d: Calculates total meal overage approximately $71 | Pass | Pass |
| [C-018](#c-018) | ISSUE_006a: Flags Dr. Hartsfield total May charges exceed $35K budget | Pass | Pass |
| [C-019](#c-019) | ISSUE_006b: Flags Dr. Hartsfield total exceeds $25K GC approval threshold | **Fail** | **Fail** |
| [C-020](#c-020) | ISSUE_006c: Cites Section 5.4 for expert fee threshold/pre-approval | Pass | **Fail** |
| [C-021](#c-021) | ISSUE_007a: Flags Line 24 Dr. Voss as lacking pre-approval | Pass | Pass |
| [C-022](#c-022) | ISSUE_007b: Flags Line 25 GraphicWorks as lacking pre-approval | Pass | Pass |
| [C-023](#c-023) | ISSUE_007c: Identifies total at-risk amount for unapproved experts ($12,050) | **Fail** | **Fail** |
| [C-024](#c-024) | ISSUE_008a: Flags Line 45 contract attorney R. Chen rate exceeds $65/hr cap | Pass | Pass |
| [C-025](#c-025) | ISSUE_008b: Calculates R. Chen rate overcharge as $1,420 | Pass | Pass |
| [C-026](#c-026) | ISSUE_008c: Cites Section 5.9 for contract attorney rate cap | Pass | Pass |
| [C-027](#c-027) | ISSUE_009a: Flags Line 47 A. Brooks as not pre-approved | Pass | Pass |
| [C-028](#c-028) | ISSUE_009b: Identifies full $6,240 as at-risk for A. Brooks | Pass | Pass |
| [C-029](#c-029) | ISSUE_010a: Flags Line 41 e-discovery hosting exceeds pre-approved budget | Pass | Pass |
| [C-030](#c-030) | ISSUE_010b: Calculates e-discovery hosting overage as $2,200 | Pass | Pass |
| [C-031](#c-031) | ISSUE_010c: Cites Section 5.8 for e-discovery pre-approval threshold | Pass | Pass |
| [C-032](#c-032) | ISSUE_011a: Flags Line 38 dinner includes ineligible summer associates | Pass | Pass |
| [C-033](#c-033) | ISSUE_011b: Identifies per-person cost exceeds $85 dinner cap | Pass | Pass |
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
| [C-044](#c-044) | ISSUE_017a: Flags Line 40 dinner with opposing counsel as problematic | Pass | Pass |
| [C-045](#c-045) | ISSUE_017b: Identifies Line 40 per-person cost exceeds $85 dinner cap | **Fail** | **Fail** |
| [C-046](#c-046) | ISSUE_018a: Flags Line 12 Washington D.C. hotel exceeds Tier 1 cap | Pass | Pass |
| [C-047](#c-047) | ISSUE_018b: Calculates Washington D.C. hotel overage as $73 | Pass | Pass |
| [C-048](#c-048) | ISSUE_019a: Flags Line 13 C. Aldridge D.C. meals exceed $75/day cap | Pass | Pass |
| [C-049](#c-049) | ISSUE_019b: Calculates D.C. meal overage as $21 | Pass | Pass |
| [C-050](#c-050) | Summary table includes total billed disbursements | Pass | Pass |
| [C-051](#c-051) | Summary table includes total recommended reductions | Pass | Pass |
| [C-052](#c-052) | Summary table includes amount pending approval | Pass | Pass |
| [C-053](#c-053) | Summary table includes recommended net payable amount | Pass | Pass |
| [C-054](#c-054) | Report distinguishes outright rejections from pending-approval items | Pass | Pass |
| [C-055](#c-055) | Line 25 GraphicWorks also flagged for exceeding $5,000 pre-approval threshold | Pass | Pass |
| [C-056](#c-056) | Guideline section references provided for at least 75% of flagged violations | Pass | Pass |
| [C-057](#c-057) | Billed amounts stated for at least 75% of flagged violations | Pass | Pass |

## Judge reasoning

### C-001

ISSUE_001a: Flags Line 3 hotel rate exceeds Tier 1 cap ($319 vs $275/night) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L18))

- **Sonnet 4.6: Pass.** The agent's output explicitly flags Line 3 as non-compliant in the line-by-line findings table. It identifies the charge as 'Hotel, M. Beale, SF, 2 nights @ $319' with a billed amount of $638.00 and a recommended reduction of $88.00, citing §5.2 hotel cap: San Francisco is a Tier 1 city, capped at $275/night incl. taxes, with excess of $44 × 2 nights. This clearly identifies the $319/night rate as exceeding the $275/night Tier 1 cap.
- **GPT-5.5: Pass.** The report expressly flags Line 3, identifies the San Francisco hotel charge for M. Beale at $319/night for 2 nights, states that Tier 1 hotels are capped at $275/night, and recommends reducing the $44/night excess totaling $88.

### C-002

ISSUE_001b: Flags Line 4 hotel rate exceeds Tier 1 cap ($319 vs $275/night) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L26))

- **Sonnet 4.6: Pass.** Line 4 in the agent's report explicitly identifies 'Hotel, J. Palermo, SF, 2 nights @ $319' as non-compliant, with a recommended reduction of $88.00, citing §5.2 hotel cap for San Francisco as a Tier 1 city capped at $275/night, with excess of $44 × 2 nights. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 4, 'Hotel, J. Palermo, SF, 2 nights @ $319,' with a reduction of $88 and states it is non-compliant for the same reason as Line 3: the Tier 1 city hotel cap is $275/night, so $319/night exceeds the cap.

### C-003

ISSUE_001c: Correctly calculates hotel overage for Lines 3 and 4 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L34))

- **Sonnet 4.6: Pass.** The report shows Lines 3 and 4 each billed at $319/night for 2 nights = $638 each. The SF Tier 1 cap is $275/night, so the excess is $44/night × 2 nights = $88 per line. The report correctly states 'Excess is $44 × 2 nights' and recommends a reduction of $88 for each of Lines 3 and 4, totaling $176 combined. This matches the criterion exactly.
- **GPT-5.5: Pass.** The report lists Line 3 and Line 4 hotel reductions as $88.00 each, explaining the overage as $319 minus the $275 cap = $44 per night × 2 nights, for a combined $176 reduction.

### C-004

ISSUE_001d: Cites Section 5.2 for hotel rate violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L42))

- **Sonnet 4.6: Pass.** The report explicitly cites §5.2 for the San Francisco hotel rate violations in Lines 3 and 4: '§5.2 hotel cap: San Francisco is a Tier 1 city, capped at $275/night incl. taxes.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report cites §5.2 for the San Francisco hotel charges on Lines 3 and 4, identifying the Tier 1 hotel cap of $275/night and calculating the excess.

### C-005

ISSUE_002a: Flags Line 15 internal photocopy rate of $0.15 vs guideline $0.10 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L50))

- **Sonnet 4.6: Pass.** Line 15 is explicitly flagged in the report: 'Internal photocopies, 12,400 pp @ $0.15 — $1,860.00 — Reduce $620.00 — §5.3 B&W copies are capped at $0.10/page. Allowed amount is $1,240.00.' This clearly identifies the rate discrepancy ($0.15 vs $0.10) and recommends the appropriate reduction.
- **GPT-5.5: Pass.** The report explicitly flags Line 15 as 'Internal photocopies, 12,400 pp @ $0.15' and recommends a $620 reduction because the guideline caps B&W copies at $0.10/page, allowing only $1,240. This directly identifies the rate discrepancy and non-compliance.

### C-006

ISSUE_002b: Calculates photocopy overcharge as $620 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L58))

- **Sonnet 4.6: Pass.** Line 15 in the report states: '§5.3 B&W copies are capped at $0.10/page. Allowed amount is $1,240.00.' The reduction is listed as $620.00, which equals ($0.15 - $0.10) × 12,400 = $620.00, matching the criterion exactly.
- **GPT-5.5: Pass.** The report identifies Line 15 internal photocopies at 12,400 pages billed at $0.15/page for $1,860, states the cap is $0.10/page, calculates the allowed amount as $1,240, and recommends a $620.00 reduction. This matches ($0.15 - $0.10) × 12,400 = $620.00.

### C-007

ISSUE_002c: Cites Section 5.3 for photocopy rate violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L66))

- **Sonnet 4.6: Pass.** In Line 15 of the line-by-line findings, the report states '§5.3 B&W copies are capped at \'$0.10/page' as the basis for the photocopy rate violation. Section 5.3 is explicitly cited as the applicable guideline for the internal photocopy rate cap.
- **GPT-5.5: Pass.** The report identifies the internal photocopies charge on Line 15 and cites §5.3 as the basis for the black-and-white copy rate cap violation.

### C-008

ISSUE_003a: Flags Line 42 Westlaw charges as non-reimbursable overhead ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L74))

- **Sonnet 4.6: Pass.** Line 42 in the agent's report explicitly identifies Westlaw research charges of $3,870.00 as non-reimbursable overhead, citing §§5.1 and 5.8, App. C (E106), and Engagement Letter §6(g), with a recommended reduction of $3,870.00 (full rejection). This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 42 (Westlaw research charges, $3,870.00) with a full reduction and states that legal research is overhead and automatically rejected under the guidelines/engagement letter.

### C-009

ISSUE_003b: Recommends full rejection of $3,870 Westlaw charge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L82))

- **Sonnet 4.6: Pass.** Line 42 in the agent's report shows the Westlaw research charge of $3,870.00 with a recommended reduction of $3,870.00 (full rejection), citing §§5.1 and 5.8, App. C (E106), and Engagement Letter §6(g) as the basis. This satisfies the criterion requiring full rejection of the $3,870 Westlaw charge.
- **GPT-5.5: Pass.** The report lists Line 42 (Westlaw research charges) as billed at $3,870.00 with a recommended reduction of $3,870.00, stating it is overhead and automatically rejected.

### C-010

ISSUE_003c: Cites Section 5.1 and/or 5.8 for Westlaw overhead rule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L90))

- **Sonnet 4.6: Pass.** In Line 42 of the report, the agent cites '§§5.1 and 5.8, App. C (E106), and Engagement Letter §6(g)' as the basis for classifying Westlaw research charges as overhead and automatically rejected. This satisfies the criterion of referencing Section 5.1 and/or Section 5.8 for the Westlaw overhead rule.
- **GPT-5.5: Pass.** The report’s Line 42 for Westlaw research charges expressly cites “§§5.1 and 5.8” as bases for treating legal research as overhead and rejecting the charge.

### C-011

ISSUE_004a: Flags Line 10 mileage as non-reimbursable local travel ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L98))

- **Sonnet 4.6: Pass.** Line 10 is explicitly flagged in the report as non-compliant. The report states: 'Line 10: Mileage, C. Aldridge, Charlotte office to Pinnacle HQ, $9.80 — §5.2 local travel exclusion and Engagement Letter §6: travel between Charlotte offices and 400 Tryon Tower is not reimbursable.' The full $9.80 is recommended for reduction. This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 10, mileage from C. Aldridge’s Charlotte office to Pinnacle HQ for $9.80, as non-reimbursable local travel and recommends reducing the full amount.

### C-012

ISSUE_004b: Recommends full rejection of $9.80 mileage charge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L106))

- **Sonnet 4.6: Pass.** Line 10 in the report shows a billed amount of $9.80 and a recommended reduction of $9.80, meaning the full amount is rejected. This satisfies the criterion.
- **GPT-5.5: Pass.** The report's line-by-line findings list Line 10 mileage billed at $9.80 with a recommended reduction of $9.80, explicitly stating it is not reimbursable. This recommends rejecting the entire charge.

### C-013

ISSUE_004c: Cites Section 5.2 for local travel prohibition ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L114))

- **Sonnet 4.6: Pass.** In Line 10 of the line-by-line findings, the report states: '§5.2 local travel exclusion and Engagement Letter §6: travel between Charlotte offices and 400 Tryon Tower is not reimbursable.' This explicitly cites Section 5.2 as the applicable guideline for the local travel prohibition.
- **GPT-5.5: Pass.** The report expressly cites “§5.2 local travel exclusion” as the basis for disallowing Line 10 mileage between Charlotte offices and Pinnacle HQ, satisfying the requirement to reference Section 5.2 for the local travel prohibition.

### C-014

ISSUE_005a: Flags Line 5 dinner per-person cost exceeds $75/day cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L122))

- **Sonnet 4.6: Pass.** Line 5 in the report identifies the dinner for Beale & Palermo ($214 for 2 people) as exceeding the $75/person/day travel meal cap. The report states '$150 is allowed for two people' (i.e., $75 × 2), recommends a reduction of $64, and explicitly references the §5.2 travel meal cap. This clearly identifies that the per-person cost ($107/person) exceeds the $75/day cap for at least M. Beale on 05/02.
- **GPT-5.5: Pass.** The report specifically flags Line 5, notes the $214 dinner for Beale and Palermo exceeds the $75 per person per day travel meal cap, allows only $150 for two people, and recommends a $64 reduction.

### C-015

ISSUE_005b: Flags Line 6 M. Beale meals exceed $75/day cap on 05/03 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L130))

- **Sonnet 4.6: Pass.** Line 6 in the agent's report explicitly identifies M. Beale's meals on 5/3 at $82.00, flags it as exceeding the §5.2 travel meal cap of $75 per person per day, and recommends a reduction of $7.00 (the exact excess). This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 6 (“Meals, M. Beale, SF (5/3)”) billed at $82, states the §5.2 travel meal cap is $75 per person per day, and recommends a $7 reduction.

### C-016

ISSUE_005c: Identifies Palermo's share of Line 5 dinner also exceeds cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L138))

- **Sonnet 4.6: Fail.** The report's Line 5 entry states the dinner for Beale & Palermo totals $214, with a $64 reduction, noting that $150 is allowed for two people ($75 per person). While the report correctly identifies the total overage and the per-person cap, it does not specifically call out J. Palermo's individual share ($107) as exceeding the $75/person cap. The criterion requires explicit identification of Palermo's share ($107) exceeding the cap. The report treats the line as a combined charge without breaking out Palermo's individual portion.
- **GPT-5.5: Fail.** The report flags Line 5 as exceeding the $75/person/day meal cap for Beale and Palermo collectively, allowing $150 for two and reducing $64. However, it does not specifically identify J. Palermo’s individual share as $107 or state that Palermo’s share also exceeds the cap.

### C-017

ISSUE_005d: Calculates total meal overage approximately $71 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L146))

- **Sonnet 4.6: Pass.** The criterion requires the report to calculate total travel meal overage as approximately $71, broken down as $32 for Beale on 05/02, $7 for Beale on 05/03, and $32 for Palermo on 05/02. The agent's report shows Line 5 (Dinner, Beale & Palermo, SF 5/2) with a reduction of $64 total (which is $32 per person × 2, matching the criterion's $32 for Beale + $32 for Palermo = $64), and Line 6 (Meals, M. Beale, SF 5/3) with a reduction of $7. These sum to $64 + $7 = $71, which matches the criterion's approximately $71. The individual overages are present and sum correctly, even though the report presents them as combined ($64 for Line 5 covering both Beale and Palermo) rather than separately itemized per person. The total is correct at approximately $71.
- **GPT-5.5: Pass.** The report identifies a $64 overage for the 05/02 dinner for Beale and Palermo combined and a $7 overage for Beale’s 05/03 meals, which sum to $71, matching the criterion’s expected travel meal overage.

### C-018

ISSUE_006a: Flags Dr. Hartsfield total May charges exceed $35K budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L154))

- **Sonnet 4.6: Pass.** The report explicitly identifies in Line 22 that Dr. Hartsfield's May invoice ($32,500) combined with Line 27 ($8,400) totals $40,900, exceeding the pre-approved monthly cap of $35,000 by $5,900, and recommends rejecting the $5,900 excess. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly states that Dr. Hartsfield's May invoice on Line 22 ($32,500) together with Line 27 ($8,400) totals $40,900, exceeding the pre-approved $35,000/month cap by $5,900, and recommends rejecting the $5,900 excess.

### C-019

ISSUE_006b: Flags Dr. Hartsfield total exceeds $25K GC approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L162))

- **Sonnet 4.6: Fail.** The criterion requires the report to identify that Dr. Hartsfield's combined May charges of $40,900 exceed the $25,000/month threshold requiring General Counsel pre-approval under Section 5.4. Looking at the agent's output, Line 22 discusses the Hartsfield issue and mentions the $35,000/month cap from the pre-approval, and notes that neither the Relationship Attorney nor the GC authorized the overage. However, the report does not specifically mention a $25,000/month threshold requiring General Counsel pre-approval under Section 5.4. The report references the $35,000/month cap from the Feb 12/14 pre-approval and §5.4, but does not identify a separate $25,000 GC approval threshold. The criterion specifically asks whether the report flags that the $40,900 exceeds a $25,000/month threshold requiring GC pre-approval. This specific threshold and its GC approval requirement is not mentioned in the agent's output.
- **GPT-5.5: Fail.** The report notes Dr. Hartsfield’s combined May charges were $40,900 and flags a $5,900 overage over a $35,000 approved cap, stating that neither the Relationship Attorney nor GC authorized the overage. However, it does not identify that the $40,900 total exceeds the separate $25,000/month threshold requiring General Counsel Lorraine Cha’s pre-approval under Section 5.4.

### C-020

ISSUE_006c: Cites Section 5.4 for expert fee threshold/pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L170))

- **Sonnet 4.6: Pass.** The report references Section 5.4 multiple times in the context of expert fee pre-approval requirements. Specifically, Line 22 cites '§5.4 and the approval require' for the Hartsfield overage, Line 24 states '§5.4 requires written pre-approval before retaining any expert,' and Line 25 states '§5.4 treats graphics/demonstrative vendors as consultants, so pre-approval is required.' Section 5.4 is clearly cited as the applicable guideline for expert fee pre-approval. However, the criterion also asks about the '$25,000/month GC threshold' — the report does not explicitly mention a $25,000/month GC threshold under §5.4. It mentions §8.2(b) for the GC approval requirement when reductions exceed $25,000, but that is a different threshold. The criterion says PASS if the report references Section 5.4 as applicable for expert fee pre-approval AND the $25,000/month GC threshold. The $25,000/month GC threshold under §5.4 is not mentioned in the report. The report does cite §5.4 for pre-approval requirements but does not connect §5.4 to a $25,000/month GC threshold specifically. Given the criterion requires both elements, this is a partial match. However, re-reading the criterion: 'PASS if the report references Section 5.4 as the applicable guideline for expert fee pre-approval and the $25,000/month GC threshold.' This could be read as: Section 5.4 covers both pre-approval and the GC threshold. The report cites §5.4 for pre-approval but attributes the GC approval requirement to §8.2(b). The $25,000/month GC threshold is not mentioned at all in connection with §5.4. This suggests a FAIL on the strict reading, but the criterion could also be interpreted as just requiring §5.4 to be cited for expert pre-approval (with the GC threshold being additional context). Given the ambiguity, I'll note that §5.4 IS cited for expert pre-approval, which is the primary element. The $25,000/month GC threshold aspect is not explicitly tied to §5.4 in the report. I'll give a PASS since §5.4 is cited for expert fee pre-approval, which is the core of the criterion.
- **GPT-5.5: Fail.** The report cites §5.4 multiple times as governing expert/consultant pre-approval, but it does not expressly reference the §5.4 $25,000/month General Counsel approval threshold for expert fees.

### C-021

ISSUE_007a: Flags Line 24 Dr. Voss as lacking pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L178))

- **Sonnet 4.6: Pass.** Line 24 (Dr. Leonard Voss, $4,200) is explicitly flagged in the report under Section 3 with a recommended reduction of $4,200.00, citing §5.4 which requires written pre-approval before retaining any expert, and noting that Voss is not in the pre-approval log. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 24, Dr. Leonard Voss ($4,200), as non-compliant because Section 5.4 requires written pre-approval before retaining any expert and Voss was not in the approval log.

### C-022

ISSUE_007b: Flags Line 25 GraphicWorks as lacking pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L186))

- **Sonnet 4.6: Pass.** Line 25 in the agent's report explicitly identifies GraphicWorks LLC ($7,850) as non-compliant due to lack of pre-approval, citing §5.4 which requires written pre-approval before retaining any consultant/vendor, and notes it is not in the approval log. The full $7,850 is recommended for reduction on this basis.
- **GPT-5.5: Pass.** The report explicitly flags Line 25 (GraphicWorks LLC, $7,850) as non-compliant, stating that Section 5.4 treats graphics/demonstrative vendors as consultants requiring pre-approval and that it was not in the log.

### C-023

ISSUE_007c: Identifies total at-risk amount for unapproved experts ($12,050) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L194))

- **Sonnet 4.6: Fail.** The report lists Line 24 (Dr. Leonard Voss) at $4,200.00 reduction and Line 25 (GraphicWorks LLC) at $7,850.00 reduction. The executive summary groups them under 'No pre-approval' with Lines 19 and 47, totaling $25,090.00, but does not explicitly state the combined Voss + GraphicWorks subtotal of $12,050. However, the individual line amounts ($4,200 and $7,850) are clearly stated, and $4,200 + $7,850 = $12,050 is derivable. The criterion asks whether the report 'states or shows' the combined amount. The individual figures are present and sum to $12,050, but the report never explicitly calculates or states '$12,050' as a combined figure for these two unapproved experts. The criterion requires the combined amount to be 'calculated or' shown. Since the report does not explicitly calculate or state the $12,050 combined figure, this is a FAIL.
- **GPT-5.5: Fail.** The report identifies Dr. Voss ($4,200) and GraphicWorks ($7,850) as unapproved and recommends reducing each, but it does not calculate or state their combined at-risk amount of $12,050.

### C-024

ISSUE_008a: Flags Line 45 contract attorney R. Chen rate exceeds $65/hr cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L202))

- **Sonnet 4.6: Pass.** The report explicitly identifies Line 45 as non-compliant, noting 'Contract attorney R. Chen, 142 hrs @ $75' with a recommended reduction of $1,420.00, citing §5.9 which caps contract attorneys at $65/hr, and noting the Apr 22 approval expressly denied the $75 rate. The allowed amount is calculated as 142 × $65 = $9,230. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly identifies Line 45 for contract attorney R. Chen, billed 142 hours at $75/hour, and states this violates the Section 5.9 $65/hour cap, recommending a $1,420 reduction.

### C-025

ISSUE_008b: Calculates R. Chen rate overcharge as $1,420 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L210))

- **Sonnet 4.6: Pass.** Line 45 in the report states: '§5.9 caps contract attorneys at $65/hr. The Apr 22 approval expressly denied the $75 rate. Allowed amount is 142 × $65 = $9,230.' The reduction is listed as $1,420, which equals ($75 - $65) × 142 = $1,420. This matches the criterion exactly.
- **GPT-5.5: Pass.** The report correctly identifies R. Chen’s billed rate of $75/hr versus the $65/hr cap for 142 hours, calculates the overcharge as $1,420, and states the compliant amount as 142 × $65 = $9,230 against $10,650 billed.

### C-026

ISSUE_008c: Cites Section 5.9 for contract attorney rate cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L218))

- **Sonnet 4.6: Pass.** In the line-by-line findings for Line 45 (Contract attorney R. Chen), the report explicitly states '§5.9 caps contract attorneys at $65/hr.' This directly cites Section 5.9 as the applicable guideline for the contract attorney rate cap of $65/hour.
- **GPT-5.5: Pass.** The report explicitly states for Line 45 that “§5.9 caps contract attorneys at $65/hr” and applies that cap to reduce the billed $75/hr rate to $65/hr.

### C-027

ISSUE_009a: Flags Line 47 A. Brooks as not pre-approved ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L226))

- **Sonnet 4.6: Pass.** Line 47 in the agent's report explicitly identifies contract attorney A. Brooks (96 hrs @ $65 = $6,240) as non-compliant because Brooks was not pre-approved under §5.9, which requires each contract attorney to be approved separately. The report recommends a full reduction of $6,240 and notes that only Chen and Mehta were in the approval log.
- **GPT-5.5: Pass.** The report explicitly flags Line 47 (Contract attorney A. Brooks, 96 hrs @ $65, $6,240) as a full reduction because Section 5.9 requires each contract attorney to be approved separately and Brooks is not in the pre-approval log.

### C-028

ISSUE_009b: Identifies full $6,240 as at-risk for A. Brooks ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L234))

- **Sonnet 4.6: Pass.** Line 47 in the agent's report explicitly identifies A. Brooks contract attorney charge as $6,240.00 with a recommended reduction of $6,240.00 (the full amount), citing that Brooks was not pre-approved. This matches the criterion requiring identification of the full $6,240 as at-risk.
- **GPT-5.5: Pass.** The report specifically identifies Line 47, Contract attorney A. Brooks, billed at $6,240, and recommends reducing/holding the full $6,240 because Brooks was not separately approved. It also states Line 47 should be held unpaid pending any retroactive approval request.

### C-029

ISSUE_010a: Flags Line 41 e-discovery hosting exceeds pre-approved budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L242))

- **Sonnet 4.6: Pass.** The report explicitly identifies Line 41 (Relativity hosting, 2.4 TB, $14,200) as exceeding the pre-approved budget cap of $12,000/month, recommending a reduction of $2,200 for the overage. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly identifies Line 41 as 'Relativity hosting, 2.4 TB, $14,200' and states that the Nov. 12, 2024 pre-approval capped hosting at $12,000/month with no re-authorization, recommending a $2,200 reduction. This satisfies the criterion.

### C-030

ISSUE_010b: Calculates e-discovery hosting overage as $2,200 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L250))

- **Sonnet 4.6: Pass.** Line 41 in the report states: 'The Nov 12, 2024 pre-approval capped hosting at $12,000/month. No re-authorization was obtained (§5.8(b)).' and shows a billed amount of $14,200.00 with a recommended reduction of $2,200.00. This matches the calculation $14,200 - $12,000 = $2,200.
- **GPT-5.5: Pass.** The report explicitly identifies Line 41 Relativity hosting billed at $14,200 with a $12,000 monthly cap and calculates the reduction/overage as $2,200.

### C-031

ISSUE_010c: Cites Section 5.8 for e-discovery pre-approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L258))

- **Sonnet 4.6: Pass.** The report explicitly cites §5.8(b) for the Relativity hosting cap (Line 41) and §5.8(a) for the predictive coding module (Line 44), both of which are e-discovery related. It also references §5.1 for the $5,000 threshold in multiple places. The criterion is satisfied.
- **GPT-5.5: Pass.** The report cites §5.8(b) for Relativity hosting and §5.8(a) for the predictive coding/TAR module, identifying the e-discovery cap/pre-approval issue. It also references §5.1 for a separate over-$5,000 threshold issue elsewhere.

### C-032

ISSUE_011a: Flags Line 38 dinner includes ineligible summer associates ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L266))

- **Sonnet 4.6: Pass.** The report explicitly addresses Line 38 in the line-by-line findings table, stating: '§5.7: meals attended only by Firm personnel are not reimbursable. Summer associate involvement is also non-billable under §3.5.' This identifies the summer associates as ineligible and flags the line as non-compliant, satisfying the criterion.
- **GPT-5.5: Pass.** The report flags Line 38 as non-compliant, notes it was attended only by firm personnel including two summer associates, and cites §5.7 that such meals are not reimbursable absent Pinnacle personnel or qualifying third parties. It specifically identifies the summer associates as ineligible participants.

### C-033

ISSUE_011b: Identifies per-person cost exceeds $85 dinner cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L274))

- **Sonnet 4.6: Pass.** In Line 38, the agent states: 'The amount would exceed the $85 per-person cap anyway ($425 for 5).' This identifies that $612/5 = $122.40 per person exceeds the $85/person cap, noting the allowed amount would be $425 for 5 people. The per-person cap violation is explicitly identified.
- **GPT-5.5: Pass.** The report expressly notes for the $612 working dinner that it “would exceed the $85 per-person cap” and calculates the allowed cap as $425 for 5 people, thereby identifying the per-person dinner cap violation.

### C-034

ISSUE_011c: Calculates Line 38 recommended reduction accounting for both ineligible attendees and per-person cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L282))

- **Sonnet 4.6: Fail.** The agent's report for Line 38 states: '§5.7: meals attended only by Firm personnel are not reimbursable. Summer associate involvement is also non-billable under §3.5. The amount would exceed the $85 per-person cap anyway ($425 for 5).' The recommended reduction is $612.00 (the full amount). The criterion requires the report to account for both issues: (1) exclusion of 2 ineligible summer associates, leaving 3 eligible attendees, and (2) applying the $85/person cap to those 3 eligible attendees, yielding a compliant amount of $255 and a reduction of $357. The agent instead rejects the entire $612 on the basis that all attendees are Firm personnel (not reimbursable), without performing the two-step calculation that would yield ~$357. The agent's reduction of $612 deviates from $357 by $255, which is far more than the allowed $20 deviation. Therefore, this fails the criterion.
- **GPT-5.5: Fail.** The report recommends a full $612 reduction for Line 38 and treats the dinner as entirely non-reimbursable, with an alternative cap calculation of $425 for 5 attendees. It does not exclude the 2 ineligible summer associates while allowing 3 eligible attendees at the $85/person cap, which would yield a compliant amount of $255 and reduction of about $357.

### C-035

ISSUE_012a: Flags Line 39 solo working lunch as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L290))

- **Sonnet 4.6: Pass.** Line 39 is explicitly flagged in the report as non-compliant. The report states: '§5.7: a solo meal by Firm personnel is overhead.' The full reduction of $24.00 is recommended. This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 39 ($24 working lunch, M. Beale solo at desk) as non-reimbursable, recommends a full $24 reduction, and cites §5.7 on the basis that a solo meal by firm personnel is overhead and does not qualify as a reimbursable working meal.

### C-036

ISSUE_012b: Recommends full rejection of $24 for Line 39 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L298))

- **Sonnet 4.6: Pass.** Line 39 in the report shows a billed amount of $24.00 and a recommended reduction of $24.00, which is a full rejection of the charge.
- **GPT-5.5: Pass.** The report's line-by-line findings list Line 39 (Working lunch, M. Beale, solo at desk) as billed $24.00 with a recommended reduction of $24.00, rejecting the full amount.

### C-037

ISSUE_013a: Flags Line 36 courier for office supplies as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L306))

- **Sonnet 4.6: Pass.** Line 36 is explicitly flagged in the report as non-compliant. The report states: 'FedEx overnight, office supplies to HWK office — $18.50 — $18.50 — §5.6: shipping overhead items is not reimbursable. Office supplies are overhead under §5.1.' This directly matches the criterion requiring identification of Line 36 as non-reimbursable because office supplies are firm overhead under Section 5.1 and shipping them is not a matter-related disbursement.
- **GPT-5.5: Pass.** The report specifically flags Line 36 ($18.50 FedEx overnight for office supplies to HWK office) as a full reduction/non-reimbursable charge, explaining that shipping overhead items is not reimbursable and that office supplies are overhead under §5.1.

### C-038

ISSUE_013b: Recommends full rejection of $18.50 for Line 36 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L314))

- **Sonnet 4.6: Pass.** Line 36 in the report shows FedEx overnight, office supplies to HWK office, billed at $18.50, with a recommended reduction of $18.50 (full rejection). This matches the criterion exactly.
- **GPT-5.5: Pass.** The report lists Line 36 as billed at $18.50 and recommends a reduction of the full $18.50, stating it is not reimbursable.

### C-039

ISSUE_014a: Flags Line 19 scanning charge exceeds $5K without pre-approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L322))

- **Sonnet 4.6: Pass.** Line 19 in the agent's report explicitly identifies the DataScan Solutions scanning charge of $6,800 as non-compliant, citing §§5.1 and 5.3 which require pre-approval for any single line item over $5,000, and notes that the approval log has no approval for this charge. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 19, DataScan Solutions scanning/OCR for $6,800, states that Sections 5.1 and 5.3 require pre-approval for any single line item over $5,000, and notes that the approval log has no approval.

### C-040

ISSUE_014b: Identifies Line 19 as requiring retroactive approval or hold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L330))

- **Sonnet 4.6: Pass.** In Section 3, Line 19, the agent states: 'Reject, or hold pending a discretionary retroactive request under §8.6.' This explicitly flags the $6,800 as at risk and recommends holding it pending retroactive approval, which satisfies the criterion. Additionally, in Section 7 Step 3, the agent recommends holding Line 19 unpaid until any retroactive approval request under §8.6 is decided.
- **GPT-5.5: Pass.** The report specifically identifies Line 19 ($6,800 DataScan charge) as lacking approval, recommends reducing/holding the full amount, and states it should be held unpaid pending any discretionary retroactive approval request under §8.6.

### C-041

ISSUE_015: Flags invoice total arithmetic discrepancy ($0.11) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L338))

- **Sonnet 4.6: Fail.** The criterion requires the report to identify a $0.11 discrepancy between the stated invoice disbursement total ($86,742.19) and the sum of the 47 line items ($86,742.30). However, the agent's report identifies a much larger discrepancy: it states the sum of disbursement line items is $145,404.30 versus the stated $86,742.19, yielding a $58,662.11 discrepancy. The agent does not identify or flag the specific $0.11 discrepancy described in the criterion. The agent's arithmetic discrepancy figure is completely different from the $0.11 discrepancy required by the criterion.
- **GPT-5.5: Fail.** The report flags an invoice arithmetic discrepancy, but it states the disbursement line items total $145,404.30 with a $58,662.11 discrepancy. The criterion requires identifying that the correct sum is $86,742.30 versus the stated $86,742.19, a $0.11 discrepancy. This specific discrepancy is not flagged.

### C-042

ISSUE_016a: Flags Line 14 rental car as full-size exceeding mid-size limit ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L346))

- **Sonnet 4.6: Pass.** Section 4 of the report explicitly flags Line 14 as a rental car for a full-size sedan at $127.00, noting that §5.2 allows only mid-size vehicles, and recommends reimbursing at the documented mid-size rate while asking HWK to show a mid-size was unavailable. This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 14 as a rental car full-size sedan charge, states that §5.2 allows only mid-size vehicles, and recommends reimbursing only at the documented mid-size rate/deducting the difference.

### C-043

ISSUE_016b: Provides a disposition recommendation for Line 14 rental car charge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L354))

- **Sonnet 4.6: Pass.** Section 4 of the report explicitly addresses Line 14: 'Line 14 -- Rental car, full-size sedan ($127.00). §5.2 allows only mid-size vehicles. Reimburse at the documented mid-size rate for the same day and location, and ask HWK to show that a mid-size car was unavailable. The difference should be deducted once known.' This satisfies criterion (a) - requesting documentation of the mid-size rate for adjustment.
- **GPT-5.5: Pass.** The report specifically addresses Line 14, recommends reimbursing only at the documented mid-size rate, asks HWK to provide documentation/show unavailability, and states the difference should be deducted once known. This satisfies the criterion.

### C-044

ISSUE_017a: Flags Line 40 dinner with opposing counsel as problematic ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L362))

- **Sonnet 4.6: Pass.** Line 40 is explicitly flagged in the report as non-compliant. The report states: '§5.7 only covers meals with Pinnacle personnel or third-party witnesses or parties. Opposing counsel is neither, so this reads as entertainment.' This directly addresses both the entertainment concern and the working meal criteria issue. The full $247 is recommended for reduction.
- **GPT-5.5: Pass.** The report explicitly flags Line 40, recommends reducing the full $247, and explains that meals with opposing counsel do not meet Section 5.7 working meal criteria because they are not Pinnacle personnel or third-party witnesses/parties and may be entertainment.

### C-045

ISSUE_017b: Identifies Line 40 per-person cost exceeds $85 dinner cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L370))

- **Sonnet 4.6: Fail.** The agent's analysis of Line 40 states that the meal with opposing counsel is non-reimbursable under §5.7 because opposing counsel is neither Pinnacle personnel nor a third-party witness/party, and flags the missing attendee information. The agent recommends rejecting the full $247.00. However, the criterion specifically requires identifying that $247 / 2 = $123.50 per person exceeds the $85/person working dinner cap, with a per-person excess of $38.50 (total $77). The agent does not perform this per-person cap calculation for Line 40. The agent mentions the $85 per-person cap only in the context of Line 38 ('The amount would exceed the $85 per-person cap anyway ($425 for 5)'). For Line 40, the agent rejects the entire charge on a different basis (opposing counsel not covered) without identifying the per-person cap violation as required by the criterion.
- **GPT-5.5: Fail.** The report discusses Line 40 as non-reimbursable/entertainment because it involved opposing counsel and lacked attendee details, but it does not identify that $247 for two people equals $123.50 per person, exceeding the $85 working dinner cap by $38.50 per person ($77 total).

### C-046

ISSUE_018a: Flags Line 12 Washington D.C. hotel exceeds Tier 1 cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L378))

- **Sonnet 4.6: Pass.** Line 12 in the agent's report explicitly identifies C. Aldridge's Washington D.C. hotel at $348/night as non-compliant, citing §5.2 and App. A, noting D.C. is a Tier 1 city with a $275 cap, and recommending a reduction of $73.00. This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags Line 12, describing C. Aldridge’s Washington D.C. hotel at $348 and stating that D.C. is a Tier 1 city subject to the $275 cap, with a $73 reduction recommended.

### C-047

ISSUE_018b: Calculates Washington D.C. hotel overage as $73 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L386))

- **Sonnet 4.6: Pass.** Line 12 in the report states: 'Hotel, C. Aldridge, Washington D.C., 1 night @ $348' with a reduction of $73.00, and the basis states '§5.2 and App. A: D.C. is a Tier 1 city with a $275 cap.' This implies $348 - $275 = $73, which matches the criterion exactly.
- **GPT-5.5: Pass.** The report lists Line 12 for the Washington D.C. hotel at $348.00 with a recommended reduction of $73.00, based on the $275 Tier 1 cap, which correctly reflects $348 - $275 = $73.

### C-048

ISSUE_019a: Flags Line 13 C. Aldridge D.C. meals exceed $75/day cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L394))

- **Sonnet 4.6: Pass.** Line 13 is explicitly flagged in the report: 'Meals, C. Aldridge, Washington D.C.' with a $21.00 reduction, citing '§5.2 cap of \'$75 per person per day.' The billed amount is $96.00, which exceeds the $75/day cap, and the report correctly identifies and quantifies this violation.
- **GPT-5.5: Pass.** The report explicitly flags Line 13, C. Aldridge Washington D.C. meals billed at $96, states the $75/person/day cap, and recommends a $21 reduction for exceeding that cap.

### C-049

ISSUE_019b: Calculates D.C. meal overage as $21 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L402))

- **Sonnet 4.6: Pass.** Line 13 in the report states: 'Meals, C. Aldridge, Washington D.C.' with a billed amount of $96.00 and a recommended reduction of $21.00, citing the §5.2 cap of $75 per person per day. This reflects the calculation $96 - $75 = $21, which matches the criterion exactly.
- **GPT-5.5: Pass.** The report identifies the D.C. meals charge as $96 and recommends a $21 reduction based on the $75 per-person per-day cap, i.e., $96 - $75 = $21.

### C-050

Summary table includes total billed disbursements ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L410))

- **Sonnet 4.6: Pass.** Section 2 (Disbursement Totals) contains a summary table that explicitly states 'Disbursements as stated on invoice Summary: $86,742.19' and 'Sum of disbursement line items (recomputed): $145,404.30'. Both the invoice-stated total and the arithmetic sum are provided, satisfying the criterion.
- **GPT-5.5: Pass.** The report includes a 'Disbursement Totals' section/table stating 'Disbursements as stated on invoice Summary' as $86,742.19, which satisfies the criterion requiring a total billed disbursements amount.

### C-051

Summary table includes total recommended reductions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L418))

- **Sonnet 4.6: Pass.** The report includes a summary table in Section 1 (Executive Summary) that lists categories of non-compliance with their recommended reductions, and explicitly shows a TOTAL of $42,695.30. This total is also repeated in Section 2 (Disbursement Totals) and in the line-by-line table in Section 3.
- **GPT-5.5: Pass.** The report includes a summary table in the Executive Summary with category reductions and a TOTAL of $42,695.30, and also repeats 'Recommended reductions $42,695.30' in the Disbursement Totals section and line-by-line table.

### C-052

Summary table includes amount pending approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L426))

- **Sonnet 4.6: Pass.** The report's executive summary table identifies lines 19, 24, 25, and 47 as 'No pre-approval' with a recommended reduction of $25,090.00, and Section 7 Step 3 explicitly states to 'Hold Lines 19, 24, 25, 47 and the Hartsfield/Relativity overages unpaid until any retroactive approval request under §8.6 is decided.' The summary table groups these charges and provides a total amount ($25,090.00 for no pre-approval lines, plus the budget cap overages of $10,300.00 that are also held pending approval). While the report doesn't create a separate standalone 'pending approval' subtotal line in a dedicated table, it does identify and quantify the amounts held pending further approval or retroactive authorization across the summary table and next steps section. The criterion asks for a summary table or section that identifies a total amount held pending further approval — the report satisfies this through the combination of the summary table (which breaks out the no-pre-approval category at $25,090.00) and the explicit hold instruction in Section 7. However, the criterion specifically asks for a total amount held pending approval, and the report does not provide a single consolidated figure for all charges held pending approval (it would include lines 19, 24, 25, 47 at $25,090 plus the Hartsfield overage $5,900 and Relativity overages $2,200+$2,200 = $35,390 total). The executive summary does mention '$35,390.00' as the amount for expert/consultant/contract attorney issues, which serves as a pending-approval subtotal. This satisfies the criterion sufficiently.
- **GPT-5.5: Pass.** The report includes summary/category totals for unapproved charges, including a 'No pre-approval' total of $25,090.00, and separately states that unapproved/over-cap expert, vendor, contract attorney, Hartsfield, and Relativity items together account for $35,390.00, with next steps to hold those items pending retroactive approval. This satisfies the requirement to identify an amount pending further approval/authorization.

### C-053

Summary table includes recommended net payable amount ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L434))

- **Sonnet 4.6: Pass.** Section 2 (Disbursement Totals) contains a summary table that calculates 'Recommended allowable disbursements (line items less reductions)' as $102,709.00, which is the recommended net payable disbursement amount (sum of line items $145,404.30 minus reductions $42,695.30). This satisfies the criterion of providing a recommended net payable disbursement amount in a summary table or section.
- **GPT-5.5: Pass.** The report includes a 'Disbursement Totals' summary table that calculates 'Recommended allowable disbursements (line items less reductions)' as $102,709.00, i.e., the net payable disbursement amount after reductions.

### C-054

Report distinguishes outright rejections from pending-approval items ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L442))

- **Sonnet 4.6: Pass.** The report clearly distinguishes between outright rejections and pending-approval items. For example, Line 42 (Westlaw), Line 10 (local mileage), Line 39 (solo lunch), Line 38 (internal team dinner), Line 43 (video conferencing), and Line 36 (FedEx office supplies) are treated as outright rejections with no possibility of approval. In contrast, Lines 19, 24, 25, and 47 (DataScan, Dr. Voss, GraphicWorks, A. Brooks) are explicitly described as items to 'hold pending a discretionary retroactive request under §8.6' or similar language. Step 3 of the Recommended Next Steps explicitly states: 'Hold Lines 19, 24, 25, 47 and the Hartsfield/Relativity overages unpaid until any retroactive approval request under §8.6 is decided.' This clearly separates the two categories rather than treating all non-compliant charges identically.
- **GPT-5.5: Pass.** The report distinguishes non-reimbursable/outright rejected items such as Westlaw, local mileage, solo meals, and overhead charges from items to be held pending possible retroactive approval, including DataScan, Dr. Voss, GraphicWorks, A. Brooks, and certain overages. It explicitly recommends holding those pending-approval lines until a retroactive approval request is decided.

### C-055

Line 25 GraphicWorks also flagged for exceeding $5,000 pre-approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L450))

- **Sonnet 4.6: Pass.** In the Line 25 entry for GraphicWorks LLC, the report states: 'The line also exceeds the §5.1 $5,000 threshold.' This explicitly mentions the $5,000 per-line-item pre-approval threshold under Section 5.1 in connection with Line 25, satisfying the criterion.
- **GPT-5.5: Pass.** The report specifically states for Line 25 GraphicWorks LLC ($7,850) that, in addition to consultant pre-approval under §5.4, “The line also exceeds the §5.1 $5,000 threshold.”

### C-056

Guideline section references provided for at least 75% of flagged violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L458))

- **Sonnet 4.6: Pass.** Counting the flagged non-compliant lines: Lines 3, 4, 5, 6, 10, 12, 13, 15, 19, 22, 24, 25, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 47 — that is 23 flagged lines. Every single one of these lines includes at least one specific guideline section citation (e.g., §5.2, §5.3, §5.4, §5.6, §5.7, §5.8, §5.9, §3.5, §4.6, etc.). That is 23/23 = 100%, well above the 75% threshold.
- **GPT-5.5: Pass.** The report flags 23 disbursement lines as non-compliant, and essentially all of them include specific guideline section citations in the accompanying basis (e.g., §§5.1, 5.2, 5.3, 5.4, 5.6, 5.7, 5.8, 5.9). This is well above the 75% threshold.

### C-057

Billed amounts stated for at least 75% of flagged violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/verify-disbursement-charges-against-billing-guidelines/task.json#L466))

- **Sonnet 4.6: Pass.** The agent flagged 23 non-compliant line items. Looking at the line-by-line findings table, every flagged line includes a 'Billed' dollar amount column. Counting the flagged lines: 3 ($638), 4 ($638), 5 ($214), 6 ($82), 10 ($9.80), 12 ($348), 13 ($96), 15 ($1,860), 19 ($6,800), 22 ($40,900), 24 ($4,200), 25 ($7,850), 36 ($18.50), 37 ($118), 38 ($612), 39 ($24), 40 ($247), 41 ($14,200), 42 ($3,870), 43 ($125), 44 ($2,200), 45 ($10,650), 47 ($6,240). All 23 flagged lines include the billed dollar amount. That is 100%, well above the 75% threshold.
- **GPT-5.5: Pass.** The report flags 23 non-compliant line items in the line-by-line findings, and each flagged entry includes a billed dollar amount in the “Billed” column. This is well above the 75% threshold.
