# GPT-6 Luna (xhigh): Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 38 of 49 criteria; GPT-5.5 passed 41 of 49 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [invoice-compliance-deviation-report.docx](output/invoice-compliance-deviation-report.docx) ([read as Markdown](output/invoice-compliance-deviation-report.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Identifies Timothy Kwan as unapproved summer associate timekeeper | Pass | Pass |
| [C-002](#c-002) | Cites Guidelines §3.1 for Kwan summer associate billing prohibition | Pass | Pass |
| [C-003](#c-003) | Calculates correct disallowance for Timothy Kwan: $10,177.50 | Pass | Pass |
| [C-004](#c-004) | Identifies Pryce-Hall Oct 22 entry as block billing | **Fail** | Pass |
| [C-005](#c-005) | Applies 30% reduction to Pryce-Hall block billing: ~$1,276.50 | **Fail** | **Fail** |
| [C-006](#c-006) | Identifies three attorneys at Michael Torres deposition as violation | Pass | Pass |
| [C-007](#c-007) | Recommends disallowance of one attorney's deposition time | Pass | Pass |
| [C-008](#c-008) | Identifies Oct 28 internal conference exceeds attorney-hour cap | Pass | Pass |
| [C-009](#c-009) | Calculates reduction for Oct 28 conference overage | Pass | Pass |
| [C-010](#c-010) | Identifies Oct 28 conference exceeds attorney attendance cap | Pass | Pass |
| [C-011](#c-011) | Identifies photocopying rate overcharge ($0.25 vs. $0.15) | Pass | Pass |
| [C-012](#c-012) | Calculates correct photocopying overcharge: $4,820.00 | Pass | Pass |
| [C-013](#c-013) | Identifies Westlaw charges exceed $3,500 monthly cap | Pass | Pass |
| [C-014](#c-014) | Calculates correct Westlaw overage: $718.60 | Pass | Pass |
| [C-015](#c-015) | Identifies Administrative Support/Word Processing as non-reimbursable | Pass | Pass |
| [C-016](#c-016) | Identifies Technology Infrastructure Surcharge as non-reimbursable | Pass | Pass |
| [C-017](#c-017) | Identifies Document Hosting Platform (Relativity) as non-reimbursable or flags for discussion | Pass | Pass |
| [C-018](#c-018) | Identifies San Francisco travel as unapproved travel outside forum | Pass | Pass |
| [C-019](#c-019) | Identifies business class airfare issue for Messina | Pass | Pass |
| [C-020](#c-020) | Notes ambiguity of 4-hour flight threshold for business class | **Fail** | Pass |
| [C-021](#c-021) | Identifies hotel rate exceeds $325/night cap | Pass | Pass |
| [C-022](#c-022) | Calculates correct hotel overage: $984.00 | Pass | Pass |
| [C-023](#c-023) | Identifies black car service as prohibited | Pass | Pass |
| [C-024](#c-024) | Recommends full disallowance of black car service: $387.00 | Pass | Pass |
| [C-025](#c-025) | Identifies unapproved local counsel retention (Brixton & Associates) | Pass | Pass |
| [C-026](#c-026) | Identifies Elaine Cho's expired contract attorney approval | Pass | Pass |
| [C-027](#c-027) | Calculates correct amount at risk for Cho: $36,270.00 | **Fail** | **Fail** |
| [C-028](#c-028) | Identifies Messina Oct 3 entry as block billing | **Fail** | Pass |
| [C-029](#c-029) | Applies 30% reduction to Messina block billing: ~$1,557.30 | **Fail** | **Fail** |
| [C-030](#c-030) | Identifies missing 75% budget threshold notification | Pass | Pass |
| [C-031](#c-031) | Identifies missing written explanation for invoice exceeding $350,000 | Pass | Pass |
| [C-032](#c-032) | Identifies Messina meals exceeding $75/day cap | Pass | Pass |
| [C-033](#c-033) | Calculates correct meal overage for Messina: $87.40 | Pass | Pass |
| [C-034](#c-034) | Identifies travel time billed at full rate instead of 50% | Pass | Pass |
| [C-035](#c-035) | Calculates correct travel time overcharge: ~$3,087.00 | Pass | Pass |
| [C-036](#c-036) | Identifies e-discovery vendor expense exceeding $10,000 approval threshold | Pass | Pass |
| [C-037](#c-037) | Provides summary table of all violations | **Fail** | **Fail** |
| [C-038](#c-038) | Calculates total recommended adjustment to the invoice | **Fail** | **Fail** |
| [C-039](#c-039) | Calculates proposed revised invoice total | **Fail** | **Fail** |
| [C-040](#c-040) | Notes budget concerns re: cumulative spend vs. 2024 budget | **Fail** | **Fail** |
| [C-041](#c-041) | Categorizes violations by severity levels | Pass | Pass |
| [C-042](#c-042) | Classifies business class airfare as borderline/requires discussion | Pass | Pass |
| [C-043](#c-043) | Recommends communication to Blackwell Stanhope identifying violations and requesting adjustments | Pass | Pass |
| [C-044](#c-044) | Recommends requesting retroactive approval for Elaine Cho | **Fail** | **Fail** |
| [C-045](#c-045) | Recommends demanding budget threshold notifications from counsel | Pass | Pass |
| [C-046](#c-046) | Cites correct Guidelines section numbers for violations | Pass | Pass |
| [C-047](#c-047) | Correctly states original invoice total as $487,329.14 | Pass | Pass |
| [C-048](#c-048) | Identifies administrative support ($2,345.00) as non-reimbursable overhead | Pass | Pass |
| [C-049](#c-049) | Identifies technology surcharge ($4,853.74) as non-reimbursable overhead | Pass | Pass |

## Judge reasoning

### C-001

Identifies Timothy Kwan as unapproved summer associate timekeeper ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L20))

- **Sonnet 4.6: Pass.** The report explicitly identifies Timothy Kwan as a summer associate who is not listed in the approved-timekeeper schedule or prior-approval log, and recommends disallowing his charges in full under §§3.1 and 9.1. This appears in both the executive summary and Section 5.1.
- **GPT-5.5: Pass.** The report explicitly identifies Timothy Kwan as a summer associate who is not listed in the approved-timekeeper schedule or prior-approval log, and recommends disallowing his time in full.

### C-002

Cites Guidelines §3.1 for Kwan summer associate billing prohibition ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L28))

- **Sonnet 4.6: Pass.** The report explicitly cites Guidelines §3.1 in connection with Timothy Kwan: 'Summer associate; not listed in the approved-timekeeper schedule or prior-approval log. Guidelines §3.1 and engagement §2 require advance written approval. Disallow in full.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report specifically identifies Timothy Kwan as a summer associate lacking approval and states that Guidelines §3.1 requires advance written approval, recommending full disallowance. This directly connects §3.1 to the Kwan summer associate billing issue.

### C-003

Calculates correct disallowance for Timothy Kwan: $10,177.50 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L36))

- **Sonnet 4.6: Pass.** The report explicitly states in section 5.1: 'Timothy Kwan --- 058, 070, 078, 084, 097, 109, 116, 130: 34.5 h; $10,177.50; billed $295/h' and recommends 'Disallow in full.' The amount $10,177.50 (34.5 hours × $295/hour) is correctly stated and full disallowance is recommended.
- **GPT-5.5: Pass.** The report identifies Timothy Kwan as an unapproved summer associate, lists 34.5 hours at $295/hour for a total of $10,177.50, and recommends disallowing his time in full.

### C-004

Identifies Pryce-Hall Oct 22 entry as block billing ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L44))

- **Sonnet 4.6: Fail.** The criterion requires that the report specifically identifies Jonathan Pryor-Hall's October 22, 2024 time entry (7.4 hours combining drafting motion, researching standards, drafting memorandum, compiling exhibit list, and reviewing prior orders) as block billing. Looking at Section 5.4 of the agent's report, it lists block billing examples including entry 088 described as 'motion drafting, research, memorandum, exhibits and prior-order review.' This matches the description of Pryor-Hall's October 22 entry. However, the criterion specifically asks for Jonathan Pryor-Hall's October 22 entry to be identified. The report references entry 088 with the matching description but does not explicitly name it as Pryor-Hall's October 22 entry. The report does not mention the date October 22 or attribute entry 088 specifically to Pryor-Hall in the block billing section. While the description matches, the criterion requires explicit identification of this specific entry by timekeeper and/or date. The report fails to make this explicit connection.
- **GPT-5.5: Pass.** The report’s block-billing section expressly flags entry 088 as combining motion drafting, research, memorandum, exhibits, and prior-order review. This matches Jonathan Pryor-Hall’s October 22 7.4-hour entry described in the criterion, so it is identified as block billing under §4.2.

### C-005

Applies 30% reduction to Pryce-Hall block billing: ~$1,276.50 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L52))

- **Sonnet 4.6: Fail.** The criterion requires that the report specifically apply a 30% reduction to a Pryce-Hall (Pryor-Hall) Oct 22 block-billed entry of $4,255.00 (7.4h × $575), yielding a $1,276.50 reduction. The agent's report discusses block billing generally in §5.4, listing several example entries (008, 014, 054, 061-063, 069, 088, 105, 133) and stating the 30% remedy should be applied. However, the report does not specifically identify or calculate the 30% reduction for a Pryor-Hall October 22 entry at $4,255.00 or $1,276.50. The specific entry, amount, and calculated reduction are not present in the output.
- **GPT-5.5: Fail.** The report identifies block billing generally and includes entry 088 as an example, stating that a 30% remedy should be applied to block-billed entries. However, it does not specifically identify the Pryce/Pryor-Hall Oct. 22 entry, does not state the $4,255.00 amount, and does not calculate or apply the required $1,276.50 reduction. Therefore it does not satisfy the criterion as stated.

### C-006

Identifies three attorneys at Michael Torres deposition as violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L60))

- **Sonnet 4.6: Pass.** The criterion requires identifying three attorneys (Sandra Messina, Jonathan Pryor-Hall, and Rebecca Tanaka) at the Torres deposition as exceeding the two-attorney cap. The report in Section 5.3 identifies four attorneys at the Torres deposition (Messina, Pryor-Hall, Tanaka, and DeVries), notes the two-attorney cap under §5.1, and flags Tanaka and DeVries as excess attendees. The three attorneys named in the criterion (Messina, Pryor-Hall, Tanaka) are all identified, and the violation is clearly noted. The report actually goes further by identifying a fourth attorney (DeVries). The criterion is satisfied.
- **GPT-5.5: Pass.** The report expressly flags the Michael Torres deposition on Oct. 15, lists Messina, Pryor-Hall, and Tanaka among the attorneys billing attendance, and states that the two-attorney cap under §5.1 was exceeded. It even identifies a fourth attorney/monitoring entry, but that does not negate identifying the required staffing violation.

### C-007

Recommends disallowance of one attorney's deposition time ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L68))

- **Sonnet 4.6: Pass.** Section 5.3 of the report explicitly addresses the Torres deposition (Oct. 15) and identifies that four attorneys billed attendance, exceeding the two-attorney cap under §5.1. The report recommends disallowing Tanaka's attendance/summary ($3,060) and DeVries's remote monitoring ($1,300) as additional attorney attendance exposed to full disallowance. This clearly recommends disallowing at least one attorney's deposition time for the Torres deposition.
- **GPT-5.5: Pass.** The report specifically addresses the October 15 Michael Torres deposition and recommends disallowing excess attorney attendance, including Tanaka's $3,060 and DeVries's $1,300 time.

### C-008

Identifies Oct 28 internal conference exceeds attorney-hour cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L76))

- **Sonnet 4.6: Pass.** The report explicitly identifies the October 28 internal strategy meeting in Section 5.3, noting that five attorneys each billed 3.8 hours for 19 total attorney-hours, and that §5.1 caps attendance at four attorneys and total time at four attorney-hours. It recommends reducing to four aggregate attorney-hours and calculates the exposure accordingly.
- **GPT-5.5: Pass.** The report explicitly flags the Oct. 28 internal strategy meeting, stating that five attorneys each billed 3.8 hours for 19 total attorney-hours and that Guidelines §5.1 caps internal conference attendance at four aggregate attorney-hours.

### C-009

Calculates reduction for Oct 28 conference overage ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L84))

- **Sonnet 4.6: Pass.** The report identifies the October 28 conference issue and notes that the four approved attendees billed 15.2 hours totaling $8,436, and that the cap is four aggregate attorney-hours. It provides an illustrative dollar reduction: 'a proportional reduction to four of 15.2 hours would reduce $8,436 by $6,216 (illustrative allocation); accept no more than four aggregate attorney-hours.' This constitutes a specific dollar reduction calculation ($6,216) for the conference overage, satisfying the criterion.
- **GPT-5.5: Pass.** The report specifically addresses the October 28 internal strategy meeting, identifies that the four approved attorneys billed 15.2 hours against a 4 attorney-hour cap, and recommends a proportional dollar reduction of $6,216, with Kwan treated separately as unauthorized. This satisfies the requirement to calculate and recommend a specific reduction for the conference overage.

### C-010

Identifies Oct 28 conference exceeds attorney attendance cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L92))

- **Sonnet 4.6: Pass.** The report explicitly states in section 5.3 that five attorneys attended the October 28 internal strategy meeting (entries 112-116), and that §5.1 caps attendance at four attorneys. It notes Kwan is the fifth attendee and addresses the headcount issue directly, stating 'accept no more than four aggregate attorney-hours' and discussing the cap on attorney attendance. The report clearly identifies both the 5-attorney attendance count and the 4-attorney cap under §5.1.
- **GPT-5.5: Pass.** The report expressly states that the Oct. 28 internal strategy meeting had five attorneys each billing time, identifies Kwan as the fifth attendee, and cites §5.1 as capping attendance at four attorneys for the meeting.

### C-011

Identifies photocopying rate overcharge ($0.25 vs. $0.15) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L100))

- **Sonnet 4.6: Pass.** The report explicitly states in the E-007 printing line: '48,200 pages billed at $0.25/page; VIH cap is $0.15/page ($7,230 maximum).' This clearly identifies the photocopying rate overcharge of $0.25 vs. $0.15 per page as required by the criterion.
- **GPT-5.5: Pass.** The report explicitly identifies the printing/photocopying charge as 48,200 pages billed at $0.25/page and states that the VIH cap is $0.15/page, calculating the overcharge/cap reduction.

### C-012

Calculates correct photocopying overcharge: $4,820.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L108))

- **Sonnet 4.6: Pass.** The report explicitly states: 'E-007 printing --- $12,050.00: 48,200 pages billed at $0.25/page; VIH cap is $0.15/page ($7,230 maximum)... reduce by at least $4,820 to $7,230.' This correctly calculates the overcharge as $4,820.00 (48,200 × $0.10 = $4,820), matching the criterion exactly.
- **GPT-5.5: Pass.** The report correctly identifies the photocopying charge as 48,200 pages at $0.25/page, states the VIH cap is $0.15/page for a $7,230 maximum, and calculates the over-cap amount as $4,820.00.

### C-013

Identifies Westlaw charges exceed $3,500 monthly cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L116))

- **Sonnet 4.6: Pass.** The report explicitly identifies in the expense table (E-006) that the Westlaw charge of $4,218.60 exceeds the $3,500 monthly/matter cap by $718.60, and recommends reducing to $3,500 and disallowing $718.60 absent prior written approval. This satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags E-006 Westlaw charges of $4,218.60 as exceeding the $3,500 monthly/matter cap by $718.60 and recommends reducing to the cap absent approval.

### C-014

Calculates correct Westlaw overage: $718.60 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L124))

- **Sonnet 4.6: Pass.** The report explicitly states in the expense table for E-006 Westlaw: 'October legal-research charge exceeds $3,500 monthly/matter cap by $718.60' and in the expense adjustment snapshot: 'E-006 $718.60'. This correctly calculates $4,218.60 − $3,500.00 = $718.60.
- **GPT-5.5: Pass.** The report correctly states the Westlaw charge of $4,218.60 exceeds the $3,500 cap by $718.60 and recommends disallowing $718.60.

### C-015

Identifies Administrative Support/Word Processing as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L132))

- **Sonnet 4.6: Pass.** The agent's report explicitly identifies the E-018 admin support charge of $2,345.00 as non-reimbursable, stating 'After-hours word processing and administrative support are expressly non-reimbursable' and recommends 'Disallow full $2,345.' This clearly satisfies the criterion, even though the report cites it as a general guideline prohibition rather than specifically citing §7.1. The charge is flagged and the correct remedy is recommended.
- **GPT-5.5: Pass.** The report expressly flags E-018 Administrative Support / after-hours word processing in the amount of $2,345.00 as non-reimbursable and recommends disallowing the full amount.

### C-016

Identifies Technology Infrastructure Surcharge as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L140))

- **Sonnet 4.6: Pass.** The agent's output explicitly identifies the technology surcharge of $4,853.74 in expense line E-019, describing it as a '2% technology-infrastructure charge' that is a 'prohibited surcharge/overhead allocation and markup,' and recommends disallowing the full $4,853.74. This clearly satisfies the criterion of identifying the Technology Infrastructure Surcharge as non-reimbursable. The specific guideline cited is slightly different (the criterion mentions §7.1 while the report references general Guidelines sections), but the identification and recommended disallowance of this exact charge is present and clear.
- **GPT-5.5: Pass.** The report explicitly flags E-019 Technology surcharge of $4,853.74 as a 2% technology-infrastructure charge, describes it as a prohibited surcharge/overhead allocation, and recommends disallowing it in full.

### C-017

Identifies Document Hosting Platform (Relativity) as non-reimbursable or flags for discussion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L148))

- **Sonnet 4.6: Pass.** The agent's output explicitly addresses the $18,500.00 Relativity hosting charge in the expense table (E-017). It flags it as a borderline issue requiring discussion, noting uncertainty about whether it is an approved third-party pass-through or prohibited internal hosting/technology overhead, and recommends obtaining vendor invoices and confirming actual third-party cost and written authorization. This satisfies criterion (b) — flagging it as a borderline issue requiring discussion.
- **GPT-5.5: Pass.** The report specifically mentions E-017 Relativity hosting for $18,500 and flags it as unclear whether it is an approved third-party e-discovery pass-through or prohibited internal hosting/technology overhead, requiring further documentation and discussion.

### C-018

Identifies San Francisco travel as unapproved travel outside forum ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L156))

- **Sonnet 4.6: Pass.** The report explicitly identifies the San Francisco trip as outside the Chicago Litigation Forum, notes that no prior written travel approval appears in the log, and flags the full $6,174 in travel fees and $7,234 in travel expenses as exposed to disallowance under §9.1. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags the San Francisco trip as outside the Chicago litigation forum, states that no prior written travel approval appears in the approval log, identifies the transmittal as post-trip notice rather than prior approval, and cites §9.1 as exposing the related travel fees/expenses to disallowance.

### C-019

Identifies business class airfare issue for Messina ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L164))

- **Sonnet 4.6: Pass.** The report does mention business class airfare in the San Francisco travel section: 'Business class on the domestic Chicago--San Francisco itinerary is allowable only if scheduled flight duration was at least four hours; obtain itinerary.' This flags the business class airfare issue and notes the 4-hour threshold under §6.1, indicating it's a borderline case requiring verification of the flight duration. The criterion requires the report to note that the Chicago-to-San Francisco flight is approximately 4 hours and 20 minutes, making it borderline. The report doesn't specify the exact duration (4h20m) but does flag the issue and request the itinerary to confirm whether the 4-hour threshold is met, which effectively treats it as a borderline case. The business class airfare issue is flagged, even if the specific flight duration isn't stated explicitly. The criterion says FAIL only if 'the business class airfare is not flagged at all' - it is flagged here.
- **GPT-5.5: Pass.** The report flags the San Francisco domestic business-class airfare issue, stating that business class on the Chicago–San Francisco itinerary is allowable only if the scheduled flight duration was at least four hours and requesting the itinerary. Although it does not specifically name Messina, give the $2,847 amount, or note the approximate 4h20 borderline duration, it does identify the business-class airfare compliance issue rather than omitting it entirely.

### C-020

Notes ambiguity of 4-hour flight threshold for business class ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L172))

- **Sonnet 4.6: Fail.** The report states: 'Business class on the domestic Chicago--San Francisco itinerary is allowable only if scheduled flight duration was at least four hours; obtain itinerary.' This acknowledges that the 4-hour threshold is the determining factor and requests the itinerary to verify the duration, implying the question is not yet resolved. However, the criterion requires the report to acknowledge that the Chicago-to-San Francisco flight is approximately 4 hours 20 minutes (just over the threshold), making it borderline. The report does not note that the flight is approximately 4 hours 20 minutes or that it is borderline/close to the threshold—it simply states the rule and asks for the itinerary without acknowledging the borderline nature of this specific route. The criterion specifically requires noting the borderline nature of the ~4h20m flight relative to the 4-hour threshold.
- **GPT-5.5: Pass.** The report does not treat the Chicago–San Francisco business class airfare as clearly compliant or non-compliant. It specifically notes that business class is allowable only if the scheduled flight duration was at least four hours and requests the itinerary, thereby recognizing the threshold issue as requiring verification/discussion.

### C-021

Identifies hotel rate exceeds $325/night cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L180))

- **Sonnet 4.6: Pass.** The report explicitly identifies the hotel rate issue in section 6 under E-008--015: 'Hotels: $489/night × 3 for each traveler versus $325 cap, excess $984 total.' This clearly flags that both travelers' hotel rate of $489/night exceeds the $325/night cap, with a total excess of $984. The criterion is satisfied even though the report uses 'Pryor-Hall' rather than 'Pryce-Hall' (likely a name variation in the scenario).
- **GPT-5.5: Pass.** The report flags the San Francisco hotel charges as $489/night for three nights for each traveler versus the $325/night cap, calculates the total hotel excess, and notes the travel lacked prior written approval. Although it does not name The Pinnacle SF specifically, it clearly identifies the hotel rate overage for both travelers.

### C-022

Calculates correct hotel overage: $984.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L188))

- **Sonnet 4.6: Pass.** The report states: 'Hotels: $489/night × 3 for each traveler versus $325 cap, excess $984 total.' This correctly calculates ($489 − $325) × 6 nights = $164 × 6 = $984.00, matching the criterion exactly.
- **GPT-5.5: Pass.** The report correctly calculates the hotel overage as $984.00, stating $489/night for 3 nights for each of two travelers against a $325/night cap, and includes the $984.00 hotel excess in the expense adjustment snapshot.

### C-023

Identifies black car service as prohibited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L196))

- **Sonnet 4.6: Pass.** The report explicitly identifies Messina's $387 black car charge as prohibited in the San Francisco travel expenses section (E-008--015): 'Messina's $387 black car is prohibited; Pryor-Hall's $143.20 ride-share is an allowed mode.' This directly flags the charge as non-compliant with the Guidelines.
- **GPT-5.5: Pass.** The report expressly flags Messina's $387 black car charge during the San Francisco travel as prohibited, noting that ride-share was allowed and recommending disallowance/reduction of the $387 black car amount under the travel expense guidelines.

### C-024

Recommends full disallowance of black car service: $387.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L204))

- **Sonnet 4.6: Pass.** The report explicitly states in the expense table for E-011: 'Messina's $387 black car is prohibited' and includes the $387 black car in the expense adjustment snapshot as a recommended disallowance. This satisfies the criterion of recommending full disallowance of the $387 black car service.
- **GPT-5.5: Pass.** The report explicitly identifies Messina's $387 black car charge as prohibited and recommends reducing/disallowing the full $387.00, including it in the expense adjustment snapshot.

### C-025

Identifies unapproved local counsel retention (Brixton & Associates) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L212))

- **Sonnet 4.6: Pass.** The report explicitly identifies E-021 Brixton & Associates ($1,500.00) as a San Francisco local counsel retainer requiring prior approval, notes that no local-counsel approval appears in the log, and recommends disallowing the full $1,500 absent prior written approval. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags E-021 Brixton & Associates for $1,500 as a San Francisco local counsel retainer requiring prior approval, states that no local-counsel approval appears in the log, and recommends disallowance absent prior written approval.

### C-026

Identifies Elaine Cho's expired contract attorney approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L220))

- **Sonnet 4.6: Pass.** The report clearly identifies Elaine Cho's expired approval in Section 5.1, noting that 'Approval Entry 5 and Rate Schedule authorize Phase II review only through September 30, 2024. All billed services are in October. No renewal appears in the log. Disallow all October time under §§3.1 and 9.1.' It also references the displayed subtotal of 186.0 h / $36,270.00 and flags the discrepancy with the detailed lines (214.0 h / $41,730.00). The criterion is satisfied.
- **GPT-5.5: Pass.** The report explicitly flags Elaine Cho's approval as expiring on September 30, 2024, notes that all October work lacked renewal/current authorization, references Guidelines §9.1, and identifies the invoice subtotal of 186.0 hours / $36,270.00 as well as higher detailed-line totals.

### C-027

Calculates correct amount at risk for Cho: $36,270.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L228))

- **Sonnet 4.6: Fail.** The criterion requires the report to state that $36,270.00 (186.0 hours × $195/hour) is at risk due to Cho's expired approval. The agent's report instead states that Cho's detailed lines show 214.0 hours / $41,730.00, and notes the displayed subtotal is 186.0 hours / $36,270.00. The report disallows all October time based on the detailed lines ($41,730.00), not $36,270.00. While $36,270.00 is mentioned as the 'displayed subtotal,' the report treats $41,730.00 as the amount at risk and explicitly states the disallowance exposure is $51,907.50 (combining Kwan's $10,177.50 and Cho's $41,730.00 from detailed lines). The report does not state that $36,270.00 is the amount at risk; rather it identifies $41,730.00 as the correct figure from detailed lines. The criterion asks for $36,270.00 to be identified as the amount at risk, which the report does not do — it treats $41,730.00 as the correct at-risk amount.
- **GPT-5.5: Fail.** The report identifies Cho’s expired-approval time as 214.0 hours / $41,730.00 and recommends disallowing that amount, while referring to $36,270.00 only as the displayed subtotal it considers incorrect. It does not state that $36,270.00 is the amount at risk for Cho as required by the criterion.

### C-028

Identifies Messina Oct 3 entry as block billing ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L236))

- **Sonnet 4.6: Fail.** The criterion requires that the report specifically identifies Sandra Messina's October 3, 2024 time entry (5.8 hours combining review of expert report materials, conference with associates, and review of opposing counsel correspondence) as block billing. Looking at Section 5.4 of the agent's report, the block billing examples listed are entries 008, 014, 054, 061-063, 069, 088, 105, and 133. Entry 014 is mentioned as 'expert material review, internal conference, opposing-counsel correspondence' which sounds similar to what Messina's Oct 3 entry contains, but the report does not explicitly identify it as Messina's October 3 entry or entry number corresponding to that date. The report does not specifically call out 'Sandra Messina's October 3' entry by name, date, or a specific entry number that can be confirmed as that entry. The criterion specifically asks for the Messina Oct 3 entry to be flagged, and while entry 014 description matches, the report doesn't confirm this is Messina's entry or dated October 3. Without explicit identification of this specific entry as Messina's October 3 block billing violation, the criterion is not satisfied.
- **GPT-5.5: Pass.** The report’s block-billing section expressly lists entry 014 as a clear example, describing it as combining “expert material review, internal conference, opposing-counsel correspondence,” which matches the Sandra Messina Oct. 3 5.8-hour entry at issue. Although it does not repeat Messina’s name/date/hours there, it flags the specific combined-task entry as block billing under §4.2.

### C-029

Applies 30% reduction to Messina block billing: ~$1,557.30 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L244))

- **Sonnet 4.6: Fail.** The criterion requires that the report specifically apply the 30% reduction remedy to the Messina Oct 3 block-billed entry (entry 014, 5.8h × $895 = $5,191.00, with a 30% reduction of $1,557.30). The agent's report discusses block billing generally in §5.4 and lists entry 014 as one of the examples ('014 (expert material review, internal conference, opposing-counsel correspondence)'), but it does not calculate or state the specific 30% reduction amount of $1,557.30 for that entry. The report only provides a general instruction to 'Apply the 30% remedy to block-billed entries' without performing the specific calculation for the Messina Oct 3 entry. The criterion requires the report to actually apply the 30% reduction with the specific calculation (~$1,557.30), which is not present in the output.
- **GPT-5.5: Fail.** The report identifies entry 008 as block billed and generally says to apply the 30% remedy to block-billed entries, but it does not specifically apply the reduction to Messina’s Oct. 3 entry or calculate the required ~$1,557.30 reduction from the $5,191.00 charge.

### C-030

Identifies missing 75% budget threshold notification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L252))

- **Sonnet 4.6: Pass.** Section 7 of the report explicitly states: 'The annual budget is $2,800,000; 75% is $2,100,000. The invoice's Matter Status tab reports year-to-date spend through October of $2,230,941.14 (79.7%), $130,941.14 above the 75% threshold. Section 10.1 requires written notice within five business days of the date cumulative invoiced fees and expenses reached $2.1 million... No such contemporaneous notice or revised forecast is in the approval log or transmittal materials.' This directly identifies the cumulative spend figure, the threshold, the exceedance, and the failure to provide required written notification under §10.1.
- **GPT-5.5: Pass.** The report expressly states that YTD spend is $2,230,941.14, exceeding the 75% threshold of $2,100,000, and notes that no timely written 75% threshold notice/reforecast was provided as required by Guidelines §10.1.

### C-031

Identifies missing written explanation for invoice exceeding $350,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L260))

- **Sonnet 4.6: Pass.** The report explicitly identifies in Section 7 that the invoice total of $487,329.14 exceeds the $350,000 monthly threshold by $137,329.14, and notes that while the transmittal identifies activity drivers, it does not provide the separate contemporaneous written explanation required by the engagement letter §7 and Guidelines §10.1. This is also flagged in the summary table under 'Moderate --- budget and expense substantiation.'
- **GPT-5.5: Pass.** The report explicitly states that the reported invoice total of $487,329.14 exceeds the $350,000 monthly threshold and that the transmittal did not provide the separate written explanation required by Guidelines §10.1/engagement terms.

### C-032

Identifies Messina meals exceeding $75/day cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L268))

- **Sonnet 4.6: Pass.** The report explicitly identifies Messina's meal expenses of $312.40 over three days versus a $225 cap, with an excess of $87.40, in the San Francisco travel expenses section (E-008--015). This matches the criterion exactly: $312.40 over 3 days, $225 maximum allowed, $87.40 overage flagged.
- **GPT-5.5: Pass.** The report explicitly flags Messina’s meals as $312.40 over three days against a $225 cap, identifying the $87.40 overage under the travel expense findings and adjustment snapshot.

### C-033

Calculates correct meal overage for Messina: $87.40 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L276))

- **Sonnet 4.6: Pass.** The report explicitly states 'Messina meals $312.40 over three days versus $225 cap, excess $87.40' in the expense deviation table for E-008--015 San Francisco travel expenses. This matches the criterion: $312.40 billed − $225.00 allowed ($75/day × 3 days) = $87.40 overage.
- **GPT-5.5: Pass.** The report explicitly calculates Messina's meals as $312.40 over three days against a $225 cap, resulting in an excess/overage of $87.40, and repeats the $87.40 adjustment in the expense snapshot.

### C-034

Identifies travel time billed at full rate instead of 50% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L284))

- **Sonnet 4.6: Pass.** The report explicitly identifies in Section 5.2 that entries 025--026 charge Messina 4.2 hours at $895 and Pryor-Hall 4.2 hours at $575 for travel to San Francisco at 100% rates, and states that if VIH elects to allow the travel, §6.1 and the engagement letter require 50% rates, with a $3,087 reduction. This directly flags the full-rate billing issue for both timekeepers' travel time entries.
- **GPT-5.5: Pass.** The report expressly flags the San Francisco travel time entries for Messina and Pryor-Hall/Pryce-Hall, noting each billed 4.2 hours at full rates and that Guidelines §6.1 requires travel time to be billed at 50%, with a $3,087 reduction if the travel is allowed.

### C-035

Calculates correct travel time overcharge: ~$3,087.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L292))

- **Sonnet 4.6: Pass.** The agent's report states in §5.2: 'If VIH elects to allow the travel notwithstanding the missing approval, §6.1 and the engagement letter require 50% rates: total payable would be $3,087, so reduce $3,087.' This correctly identifies the $3,087 overcharge (the difference between the full billed amount of $6,174 and the 50%-rate amount of $3,087). The underlying math is: Messina 4.2h × $895 = $3,759 billed vs. $1,879.50 at 50%, overcharge $1,879.50; Pryor-Hall 4.2h × $575 = $2,415 billed vs. $1,207.50 at 50%, overcharge $1,207.50; total overcharge $3,087. The report arrives at the correct $3,087 figure, satisfying the criterion.
- **GPT-5.5: Pass.** The report correctly identifies the two San Francisco travel time entries totaling $6,174.00 at full rates and states that, if travel is allowed, they should be billed at 50%, making the payable amount $3,087.00 and the required reduction/overcharge $3,087.00.

### C-036

Identifies e-discovery vendor expense exceeding $10,000 approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L300))

- **Sonnet 4.6: Pass.** The report explicitly identifies the Forrest Data Solutions charge of $48,250.00 in expense line E-020, noting it 'exceeds $10,000 and no approval for Forrest appears' and recommends disallowing the full $48,250 absent prior written approval. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags E-020 Forrest Data Solutions for $48,250.00, describes it as a third-party collection/processing/hosting charge exceeding the $10,000 approval threshold, and states that no specific prior written approval for Forrest is documented.

### C-037

Provides summary table of all violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L308))

- **Sonnet 4.6: Fail.** The criterion requires a summary table listing individual violations with their original charged amounts, compliant/allowed amounts, and recommended adjustments/reductions. The report contains several tables: a high-level 'Summary of Deviations' table (Section 3) that lists risk areas, findings, and recommended actions, and a detailed expense table (Section 6) that lists individual expense lines with findings and recommended adjustments. However, neither table consistently provides all three required columns: original charged amount, compliant/allowed amount, AND recommended adjustment/reduction for each violation. The Section 3 summary table lacks specific dollar amounts for original charges and compliant amounts in many rows. The expense table in Section 6 comes closest but still doesn't consistently show all three columns (original amount, allowed amount, adjustment) for each line. Section 6.1 provides an 'expense adjustment snapshot' but it's a narrative paragraph, not a table. The fee deviation tables in Section 5 show some amounts but not in a unified summary format with all three required columns. The criterion specifically asks for a summary table with original charged amounts, compliant/allowed amounts, and recommended adjustments. While there are multiple tables, none fully satisfies all three requirements in a single summary table format.
- **GPT-5.5: Fail.** The report includes several tables summarizing risk areas and discussing violations, and some tables include charged amounts and recommended actions. However, it does not provide a summary table of all individual violations with the required original charged amount, compliant/allowed amount, and recommended adjustment/reduction columns. Many violations are narrative-only or lack allowed amounts/reduction calculations in a summary table.

### C-038

Calculates total recommended adjustment to the invoice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L316))

- **Sonnet 4.6: Fail.** The criterion requires a total recommended adjustment figure that is the sum of all individual violation adjustments, with internally consistent arithmetic. The report provides an 'expense adjustment snapshot' of $71,175.74 (or $76,951.34 if full travel denial), but this only covers expenses. The report explicitly warns against mechanically adding fee adjustments, narrative exposure, block-billing reductions, staffing caps, and arithmetic corrections together. No single consolidated total recommended adjustment figure is provided that sums all individual violation adjustments (fees + expenses). The report intentionally avoids providing such a total, noting overlaps and double-counting risks. While the expense snapshot is internally consistent, the criterion requires a total adjustment figure covering all violations, which is absent.
- **GPT-5.5: Fail.** The report provides some subtotal figures (e.g., unapproved timekeeper exposure and an expense adjustment snapshot) but expressly states that figures overlap and should not be mechanically added, and it does not provide a single total recommended adjustment to the invoice that sums all individual violation adjustments. Therefore it does not meet the criterion.

### C-039

Calculates proposed revised invoice total ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L324))

- **Sonnet 4.6: Fail.** The report provides various adjustment figures and snapshots (e.g., $71,175.74 or $76,951.34 expense adjustments, fee disallowances of $51,907.50, etc.) but explicitly warns against mechanically adding them together and never presents a single proposed revised invoice total calculated as $487,329.14 minus total recommended adjustments. The report intentionally avoids providing a net revised payable amount, instead returning the invoice for correction. The criterion requires a proposed revised invoice total, which is absent.
- **GPT-5.5: Fail.** The report identifies various recommended adjustments and adjustment snapshots, but it does not calculate or state a proposed revised invoice total as $487,329.14 minus the total recommended adjustments.

### C-040

Notes budget concerns re: cumulative spend vs. 2024 budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L332))

- **Sonnet 4.6: Fail.** Section 7 of the report discusses the 2024 budget situation in detail. It notes the annual budget is $2,800,000, the 75% threshold is $2,100,000, and the YTD spend through October is $2,230,941.14 (79.7% of budget), which is $130,941.14 above the 75% threshold. The report also notes that no contemporaneous 75% threshold notice was provided. However, the criterion specifically requires discussion that 'remaining budget is insufficient for the work remaining through trial in April 2025.' The report does not mention trial in April 2025 or discuss whether the remaining budget (~$569,058.86) is insufficient for the work remaining through trial. The report only notes the threshold crossing and the missing notice, but does not address the forward-looking budget insufficiency concern relative to trial. This is a meaningful omission from the criterion's requirements.
- **GPT-5.5: Fail.** The report does discuss budget concerns and correctly notes the $2.8M annual budget, $2.1M 75% threshold, and $2,230,941.14 cumulative spend through October exceeding that threshold. However, it does not state that the remaining budget is insufficient for the work remaining through trial in April 2025, which the criterion specifically requires.

### C-041

Categorizes violations by severity levels ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L340))

- **Sonnet 4.6: Pass.** The report uses a severity categorization system in its summary table (Section 3) with labels: 'Critical,' 'High,' and 'Moderate' — three distinct severity levels. Critical covers invoice reconciliation failures, High covers unapproved personnel, unapproved/non-reimbursable expenses, outside-forum travel, and staffing caps, and Moderate covers time-entry/LEDES compliance, invoice identifiers, and budget/expense substantiation. This constitutes at least three severity levels categorizing the violations, satisfying the criterion.
- **GPT-5.5: Pass.** The report explicitly categorizes violation areas by severity in its summary table, using at least three levels: Critical, High, and Moderate. This satisfies the requirement to categorize violations by severity levels, even though the labels differ from the example categories.

### C-042

Classifies business class airfare as borderline/requires discussion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L348))

- **Sonnet 4.6: Pass.** The report states: 'Business class on the domestic Chicago–San Francisco itinerary is allowable only if scheduled flight duration was at least four hours; obtain itinerary.' This treats the business class airfare as a borderline/requires discussion issue rather than a clear mandatory reduction. It does not automatically disallow the business class fare; instead, it conditions allowability on whether the scheduled flight duration meets the 4-hour threshold and requests the itinerary to verify. This acknowledges the ambiguity (the flight duration is close to the threshold) and defers the determination pending documentation, which satisfies the criterion.
- **GPT-5.5: Pass.** The report does not treat Messina’s business-class airfare as a clear mandatory reduction or simply compliant. It flags the issue as conditional, stating that business class on the Chicago–San Francisco itinerary is allowable only if the scheduled flight duration was at least four hours and requests the itinerary, which effectively classifies it as requiring documentation/discussion given the threshold issue.

### C-043

Recommends communication to Blackwell Stanhope identifying violations and requesting adjustments ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L356))

- **Sonnet 4.6: Pass.** The report explicitly recommends returning the invoice for correction, requiring a corrected invoice and LEDES file, and requesting specific documentation and approvals from Blackwell Stanhope. Section 8 ('Additional Documentation Required') lists numerous items to be requested from outside counsel, and the Conclusion states 'The invoice should be returned for correction rather than paid at the amount stated' and that 'VIH can determine the undisputed payable amount and issue a line-specific adjustment notice under §§8.2 and 11.2.' The disposition banner at the top also states 'DISPOSITION --- RETURN FOR CORRECTION. Do not approve the stated invoice total as submitted.' Throughout the report, the recommended actions include requiring corrected submissions, obtaining approvals, and requesting documentation—all of which constitute communications to Blackwell Stanhope identifying violations and requesting adjustments. This satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly recommends returning the invoice to Blackwell Stanhope for correction, requiring a corrected invoice/LEDES file, supporting records, prior approvals, and line-specific adjustments/disallowances for identified non-compliant charges. This satisfies the requirement to recommend next-step communication to outside counsel requesting adjustments or approvals.

### C-044

Recommends requesting retroactive approval for Elaine Cho ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L364))

- **Sonnet 4.6: Fail.** The report consistently recommends disallowing all of Elaine Cho's October time due to her expired authorization, with no mention of seeking retroactive or renewed approval for her work. The report states 'Disallow all post-expiration/unapproved time under §§3.1, 9.1; reconcile Cho's line totals' and 'No renewal appears in the log. Disallow all October time under §§3.1 and 9.1.' There is no recommendation to seek retroactive approval or renewal for Cho's authorization, which the criterion requires for a PASS.
- **GPT-5.5: Fail.** The report identifies that Elaine Cho’s approval expired on September 30 and recommends disallowing her October time, with a request for any existing renewal documentation. It does not recommend seeking retroactive approval or renewed re-authorization for Cho’s continued work.

### C-045

Recommends demanding budget threshold notifications from counsel ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L372))

- **Sonnet 4.6: Pass.** Section 7 of the report explicitly addresses budget controls and recommends requesting the dated 75% budget-threshold notice/revised forecast and the separate written explanation required for invoices above $350,000. Section 8 (Additional Documentation Required) also lists 'The dated 75% budget-threshold notice/revised forecast and the separate written explanation/forecast required for an invoice above $350,000.' These recommendations clearly satisfy the criterion.
- **GPT-5.5: Pass.** The report expressly recommends requesting the dated 75% budget-threshold notice/revised forecast and the separate written explanation/forecast required for an invoice above $350,000, satisfying the criterion.

### C-046

Cites correct Guidelines section numbers for violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L380))

- **Sonnet 4.6: Pass.** The report consistently cites specific Guideline section numbers throughout. Checking coverage: unapproved timekeepers → §§3.1, 9.1; block billing → §4.2; staffing caps → §5.1; travel → §§6.1, 9.1; expenses/receipts → §§6.2, 7.1, 7.2; budget/threshold → §10.1; payment terms → §8.1, 8.2; prohibited admin time → §4.3; narrative minimum → §4.1. Nearly every violation category has at least one section citation, well above 75%. Checking accuracy: block billing = §4.2 ✓; staffing caps = §5.1 ✓; travel = §6.1 and §9.1 ✓; expenses/receipts = §7.1 ✓; prior approvals = §9.1 ✓; budget = §10.1 ✓; unapproved timekeepers = §3.1 ✓; narrative = §4.1 ✓; prohibited admin = §4.3 ✓. All cited sections align with the correct violation types. Both the coverage threshold (>75% of violations cited) and accuracy threshold (>75% of citations correct) are met.
- **GPT-5.5: Pass.** The report includes specific Guideline section citations for the major violation categories: unapproved/expired timekeepers (§§3.1, 9.1), travel approval and reduced-rate issues (§§9.1, 6.1), staffing caps (§5.1), block billing (§4.2), administrative/billing time (§4.3), budget thresholds (§10.1), and expense documentation/experts (§§7.1, 6.2/7.2). Some individual expense-line violations are described without a section number, and there are a few broad or arguably imprecise citations, but the principal violations are cited and the cited sections are largely accurate under the criterion’s examples.

### C-047

Correctly states original invoice total as $487,329.14 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L388))

- **Sonnet 4.6: Pass.** The report clearly states in multiple places that the original invoice total is $487,329.14. For example, in the Review parameters table: 'Invoice amount asserted: $487,329.14', and in Section 1: 'the invoice claims $487,329.14', and in Section 4.1 table: 'Invoice total $487,329.14'. This matches the criterion exactly.
- **GPT-5.5: Pass.** The report repeatedly states the original/asserted invoice total as $487,329.14, including in the review parameters, executive summary, and invoice reconciliation table.

### C-048

Identifies administrative support ($2,345.00) as non-reimbursable overhead ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L396))

- **Sonnet 4.6: Pass.** The report explicitly identifies E-018 admin support ($2,345.00) as 'After-hours word processing and administrative support are expressly non-reimbursable' and recommends 'Disallow full $2,345.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags E-018 administrative support ($2,345.00) as 'After-hours word processing and administrative support' that is 'expressly non-reimbursable' and recommends disallowing the full amount. It also lists the $2,345 administrative support charge among non-reimbursable expenses.

### C-049

Identifies technology surcharge ($4,853.74) as non-reimbursable overhead ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L404))

- **Sonnet 4.6: Pass.** The report explicitly identifies E-019 technology surcharge of $4,853.74 as a '2% technology-infrastructure charge is a prohibited surcharge/overhead allocation and markup' and recommends 'Disallow full $4,853.74.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags E-019 technology surcharge of $4,853.74 as a prohibited technology-infrastructure surcharge/overhead allocation and recommends disallowing it in full. It also includes it in the non-reimbursable/unapproved expense summary.
