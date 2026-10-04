# Claude Opus 5.5 (low): Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 47 of 49 criteria; GPT-5.5 passed 46 of 49 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [invoice-compliance-deviation-report.docx](output/invoice-compliance-deviation-report.docx) ([read as Markdown](output/invoice-compliance-deviation-report.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Identifies Timothy Kwan as unapproved summer associate timekeeper | Pass | Pass |
| [C-002](#c-002) | Cites Guidelines §3.1 for Kwan summer associate billing prohibition | Pass | Pass |
| [C-003](#c-003) | Calculates correct disallowance for Timothy Kwan: $10,177.50 | Pass | Pass |
| [C-004](#c-004) | Identifies Pryce-Hall Oct 22 entry as block billing | Pass | Pass |
| [C-005](#c-005) | Applies 30% reduction to Pryce-Hall block billing: ~$1,276.50 | Pass | Pass |
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
| [C-020](#c-020) | Notes ambiguity of 4-hour flight threshold for business class | Pass | Pass |
| [C-021](#c-021) | Identifies hotel rate exceeds $325/night cap | Pass | Pass |
| [C-022](#c-022) | Calculates correct hotel overage: $984.00 | Pass | Pass |
| [C-023](#c-023) | Identifies black car service as prohibited | Pass | Pass |
| [C-024](#c-024) | Recommends full disallowance of black car service: $387.00 | Pass | Pass |
| [C-025](#c-025) | Identifies unapproved local counsel retention (Brixton & Associates) | Pass | Pass |
| [C-026](#c-026) | Identifies Elaine Cho's expired contract attorney approval | Pass | Pass |
| [C-027](#c-027) | Calculates correct amount at risk for Cho: $36,270.00 | **Fail** | **Fail** |
| [C-028](#c-028) | Identifies Messina Oct 3 entry as block billing | Pass | Pass |
| [C-029](#c-029) | Applies 30% reduction to Messina block billing: ~$1,557.30 | Pass | Pass |
| [C-030](#c-030) | Identifies missing 75% budget threshold notification | Pass | Pass |
| [C-031](#c-031) | Identifies missing written explanation for invoice exceeding $350,000 | Pass | Pass |
| [C-032](#c-032) | Identifies Messina meals exceeding $75/day cap | Pass | Pass |
| [C-033](#c-033) | Calculates correct meal overage for Messina: $87.40 | Pass | Pass |
| [C-034](#c-034) | Identifies travel time billed at full rate instead of 50% | Pass | Pass |
| [C-035](#c-035) | Calculates correct travel time overcharge: ~$3,087.00 | Pass | Pass |
| [C-036](#c-036) | Identifies e-discovery vendor expense exceeding $10,000 approval threshold | Pass | Pass |
| [C-037](#c-037) | Provides summary table of all violations | Pass | **Fail** |
| [C-038](#c-038) | Calculates total recommended adjustment to the invoice | Pass | Pass |
| [C-039](#c-039) | Calculates proposed revised invoice total | **Fail** | **Fail** |
| [C-040](#c-040) | Notes budget concerns re: cumulative spend vs. 2024 budget | Pass | Pass |
| [C-041](#c-041) | Categorizes violations by severity levels | Pass | Pass |
| [C-042](#c-042) | Classifies business class airfare as borderline/requires discussion | Pass | Pass |
| [C-043](#c-043) | Recommends communication to Blackwell Stanhope identifying violations and requesting adjustments | Pass | Pass |
| [C-044](#c-044) | Recommends requesting retroactive approval for Elaine Cho | Pass | Pass |
| [C-045](#c-045) | Recommends demanding budget threshold notifications from counsel | Pass | Pass |
| [C-046](#c-046) | Cites correct Guidelines section numbers for violations | Pass | Pass |
| [C-047](#c-047) | Correctly states original invoice total as $487,329.14 | Pass | Pass |
| [C-048](#c-048) | Identifies administrative support ($2,345.00) as non-reimbursable overhead | Pass | Pass |
| [C-049](#c-049) | Identifies technology surcharge ($4,853.74) as non-reimbursable overhead | Pass | Pass |

## Judge reasoning

### C-001

Identifies Timothy Kwan as unapproved summer associate timekeeper ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L20))

- **Sonnet 4.6: Pass.** The report explicitly identifies Timothy Kwan as an unapproved summer associate in multiple places: D-2 in the Deviation Register states 'Summer associate Timothy Kwan --- 8 entries, 34.5 hrs' with a disallowance of $10,177.50, and Section 4.2 provides detailed analysis explaining that Kwan is not on Exhibit A or in the Prior Approval Log, that §3.1 prohibits billing summer associates without prior written approval, and that no approval exists.
- **GPT-5.5: Pass.** The report explicitly identifies Timothy Kwan as a summer associate, states he is not on Exhibit A or in the Prior Approval Log, and recommends disallowing his time as an unapproved timekeeper.

### C-002

Cites Guidelines §3.1 for Kwan summer associate billing prohibition ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L28))

- **Sonnet 4.6: Pass.** In Section 4.2 (D-2), the report explicitly states: 'Kwan is not on Exhibit A or in the Prior Approval Log. §3.1 says summer associates "are not billable to VIH matters without prior written approval," and that time from non-approved timekeepers "will be disallowed in their entirety without exception."' Additionally, in the Deviation Register (Section 3), D-2 lists '§3.1; EL §2; Ex. A n.4' as the authority for the Kwan summer associate issue. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The report identifies Timothy Kwan as an unapproved summer associate and explicitly cites §3.1 as the authority, including stating that §3.1 says summer associates are not billable without prior written approval.

### C-003

Calculates correct disallowance for Timothy Kwan: $10,177.50 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L36))

- **Sonnet 4.6: Pass.** The report explicitly states in D-2 that Timothy Kwan's 8 entries totaling 34.5 hours are disallowed in full at $10,177.50 (34.5 hrs × $295/hr). This matches the criterion exactly. The amount appears consistently in the deviation register, the detailed findings section, and the recommended adjustment schedule.
- **GPT-5.5: Pass.** The report recommends full disallowance of Timothy Kwan's time, identifies 34.5 hours at $295/hour, and states the disallowance amount as $10,177.50.

### C-004

Identifies Pryce-Hall Oct 22 entry as block billing ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L44))

- **Sonnet 4.6: Pass.** The report's block billing section (D-9) lists entry 88 attributed to Jonathan Pryor-Hall at 7.4 hours with the narrative 'Draft motion for protective order regarding Clearwater's expert discovery requests; research applicable standards; draft supporting memorandum; compil[e]...' This matches the October 22 entry combining drafting motion, researching standards, drafting memorandum, compiling exhibit list, and reviewing prior orders. It is explicitly flagged as block billing with a 30% reduction of $1,276.50 applied. The criterion is satisfied.
- **GPT-5.5: Pass.** The report's block billing section (D-9) expressly flags Entry 88 for Jonathan Pryor-Hall, 7.4 hours, describing the combined drafting motion, researching standards, drafting memorandum, compiling materials, etc., and applies a 30% block-billing reduction under §4.2. This matches the October 22 entry described in the criterion.

### C-005

Applies 30% reduction to Pryce-Hall block billing: ~$1,276.50 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L52))

- **Sonnet 4.6: Pass.** The agent's output includes entry 88 (Jonathan Pryor-Hall, 7.4 hours) in the block billing table (D-9). The billed amount is $4,255.00 (7.4 × $575 = $4,255.00) and the 30% reduction is listed as $1,276.50. This matches the criterion exactly. The entry is described as 'Draft motion for protective order regarding Clearwater's expert discovery requests; research applicable standards; draft supporting memorandum; compil...' which is a block-billed entry combining distinct tasks. The calculation is correct: $4,255.00 × 0.30 = $1,276.50.
- **GPT-5.5: Pass.** The report’s block-billing section (D-9) lists Jonathan Pryor-Hall entry 88 for 7.4 hours billed at $4,255.00 and applies a 30% reduction of $1,276.50, matching the specified remedy and calculation.

### C-006

Identifies three attorneys at Michael Torres deposition as violation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L60))

- **Sonnet 4.6: Pass.** The report in section 4.3 (D-4) explicitly identifies that at the Michael Torres deposition on 10/15, four attorneys billed attendance: Messina (entry 61), Pryor-Hall (entry 62), Tanaka (entry 63), and DeVries (entry 64, 'monitor remotely'). It identifies Messina and Pryor-Hall as the two allowed attendees and disallows Tanaka (entry 63, 7.2h) and DeVries (entry 64, 4.0h) as excess. This means the report identifies three attorneys (Messina, Pryor-Hall, Tanaka) plus DeVries as attending, with Tanaka being one of the violating attorneys. The criterion asks whether the report identifies that three attorneys (Messina, Pryor-Hall, and Tanaka) attended, exceeding the two-attorney cap. The report does identify all three of these attorneys as attendees and flags the violation under §5.1. The criterion is satisfied.
- **GPT-5.5: Pass.** The report expressly identifies the Michael Torres deposition on 10/15 as having Sandra Messina, Jonathan Pryor-Hall, and Rebecca Tanaka billing attendance, cites the §5.1 maximum of two attorneys, and treats Rebecca Tanaka as an excess attorney staffing violation.

### C-007

Recommends disallowance of one attorney's deposition time ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L68))

- **Sonnet 4.6: Pass.** The report explicitly addresses the Torres deposition (10/15) in section 4.3 (D-4), identifying that four attorneys billed for attendance (Messina, Pryor-Hall, Tanaka, DeVries) and recommending disallowance of Tanaka's 7.2h (entry 63) and DeVries's 4.0h (entry 64), totaling $4,360.00. This clearly recommends disallowance of at least one attorney's deposition time for the October 15 Torres deposition.
- **GPT-5.5: Pass.** The report specifically identifies the October 15 Michael Torres deposition and recommends disallowing attorney deposition attendance time for Tanaka (7.2 hours) and DeVries (4.0 hours), totaling $4,360 for that deposition.

### C-008

Identifies Oct 28 internal conference exceeds attorney-hour cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L76))

- **Sonnet 4.6: Pass.** The report explicitly identifies the October 28 internal strategy conference violation in D-5, noting that five attorneys attended (Messina, Pryor-Hall, Tanaka, DeVries, Kwan), each billing 3.8 hours, for 19.0 attorney-hours total. It states this breaks both independent limits in §5.1: the 4-attendee cap and the 4 attorney-hour cap. The remaining 15.2 hours are then reduced to 4.0 attorney-hours, resulting in a $6,216.00 reduction. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report expressly flags the October 28 internal strategy conference as involving five attorneys billing 3.8 hours each, totaling 19.0 attorney-hours, and states this violates §5.1’s 4-attendee and 4 total attorney-hour caps, with a recommended reduction.

### C-009

Calculates reduction for Oct 28 conference overage ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L84))

- **Sonnet 4.6: Pass.** The report explicitly addresses the October 28 conference in D-5. It identifies that 5 attorneys attended, each billing 3.8 hours (19.0 total attorney-hours). It notes Kwan's entry is already disallowed under D-2. For the remaining 4 attorneys, it calculates 15.2 hours, reduces to the 4.0 attorney-hour cap, allocates pro rata by value, allows $2,220.00, and recommends a specific dollar reduction of $6,216.00. This satisfies the criterion of calculating excess attorney-hours and recommending a specific dollar reduction.
- **GPT-5.5: Pass.** The report specifically analyzes the October 28 conference, notes that excluding Kwan the remaining four attorneys billed 15.2 hours against a 4 attorney-hour cap, and recommends reducing the charge by $6,216.00 to conform to the cap.

### C-010

Identifies Oct 28 conference exceeds attorney attendance cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L92))

- **Sonnet 4.6: Pass.** The report explicitly addresses the October 28 internal strategy conference in D-5, stating that five attorneys attended (Messina, Pryor-Hall, Tanaka, DeVries, Kwan) and that this 'breaks both independent limits in §5.1: the 4-attendee cap and the 4 attorney-hour cap.' The report clearly identifies the attendance count issue (5 attorneys vs. the 4-attendee cap) separately from the attorney-hour cap issue.
- **GPT-5.5: Pass.** The report expressly identifies the October 28 internal strategy conference as having five attorney attendees (Messina, Pryor-Hall, Tanaka, DeVries, and Kwan), notes Kwan as the fifth attendee, and states that §5.1 imposes a 4-attendee cap for internal meetings.

### C-011

Identifies photocopying rate overcharge ($0.25 vs. $0.15) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L100))

- **Sonnet 4.6: Pass.** The report explicitly identifies the photocopying rate overcharge in D-13: 'Photocopying at $0.25/page vs $0.15 cap (48,200 pp.)' and in Section 4.6 expense table: 'In-house copying 48,200 pp @ $0.25 ... Capped at $0.15/page, so $7,230. The excess is a markup (§7.3).'
- **GPT-5.5: Pass.** The report explicitly identifies the photocopying overcharge: D-13 states photocopying was billed at $0.25/page versus a $0.15 cap, and Section 4.6 repeats that in-house copying of 48,200 pages at $0.25 should be capped at $0.15/page under §7.1.

### C-012

Calculates correct photocopying overcharge: $4,820.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L108))

- **Sonnet 4.6: Pass.** The report explicitly states in D-13: 'Photocopying at $0.25/page vs $0.15 cap (48,200 pp.)' with a reduction of '($4,820.00)'. In section 4.6, it states 'Capped at $0.15/page, so $7,230. The excess is a markup (§7.3).' This confirms 48,200 × ($0.25 - $0.15) = $4,820.00, which matches the criterion exactly.
- **GPT-5.5: Pass.** The report correctly identifies the photocopying charge as 48,200 pages billed at $0.25/page ($12,050.00), applies the $0.15/page cap ($7,230.00), and calculates the overcharge/reduction as $4,820.00.

### C-013

Identifies Westlaw charges exceed $3,500 monthly cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L116))

- **Sonnet 4.6: Pass.** The report explicitly identifies in D-14 that Westlaw charges of $4,218.60 exceed the $3,500 monthly cap under §7.1, with a recommended reduction of $718.60. This is also reflected in the expense table in section 4.6 and the adjustment schedule in section 7.
- **GPT-5.5: Pass.** The report explicitly flags D-14: “Westlaw $4,218.60 vs $3,500 monthly cap,” cites §7.1, and recommends a $718.60 reduction. It also repeats this in the expense analysis and adjustment schedule.

### C-014

Calculates correct Westlaw overage: $718.60 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L124))

- **Sonnet 4.6: Pass.** The report explicitly states in D-14: 'Westlaw $4,218.60 vs $3,500 monthly cap' with a reduction of '($718.60)'. This matches the criterion of $4,218.60 − $3,500.00 = $718.60.
- **GPT-5.5: Pass.** The report identifies Westlaw billed at $4,218.60 against a $3,500 monthly cap and calculates the reduction/overage as $718.60.

### C-015

Identifies Administrative Support/Word Processing as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L132))

- **Sonnet 4.6: Pass.** The report explicitly identifies E-018 'After-hours word processing / admin' at $2,345.00 as disallowed under §7.1(a),(d) and Engagement Letter §5, and includes it in D-12 as a prohibited overhead charge. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags E-018 “After-hours word processing / admin” billed at $2,345.00, marks it “Disallow,” and cites §7.1(a),(d) and the Engagement Letter. It also includes the amount in D-12 as prohibited overhead/admin support plus tech surcharge.

### C-016

Identifies Technology Infrastructure Surcharge as non-reimbursable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L140))

- **Sonnet 4.6: Pass.** The report explicitly identifies the technology surcharge (2% = $4,853.74) as prohibited overhead in D-12, citing §7.1(b) and §7.3, and recommends disallowing it in full. It appears in the deviation register, the expense analysis table (E-019), and the recommended adjustment schedule.
- **GPT-5.5: Pass.** The report explicitly flags E-019, the Technology surcharge 2% in the amount of $4,853.74, and marks it for disallowance as prohibited under Guidelines §7.1(b) and §7.3. It also describes technology surcharges/overhead as non-reimbursable elsewhere in the report.

### C-017

Identifies Document Hosting Platform (Relativity) as non-reimbursable or flags for discussion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L148))

- **Sonnet 4.6: Pass.** The agent's output explicitly addresses the $18,500.00 Relativity hosting charge in deviation D-15 and in the expense table (E-017). It flags the charge as requiring scrutiny: it notes the vendor is unidentified, the amount exceeds the PA-004 approved estimate, and critically states 'If this is a firm-internal platform, it is not reimbursable at all (§7.1(c)).' This satisfies criterion (b) — flagging it as a borderline issue requiring discussion because it could be characterized as either a substantive e-discovery tool or overhead/file storage. The report recommends a partial disallowance and withholding the balance pending documentation.
- **GPT-5.5: Pass.** The report specifically addresses the $18,500 Relativity hosting charge, flags vendor/platform uncertainty, notes that if it is a firm-internal platform it is not reimbursable under §7.1(c), disallows the excess over the approved range, and withholds the balance pending documentation. This satisfies the criterion by flagging it as a potential non-reimbursable overhead/file-storage issue requiring discussion.

### C-018

Identifies San Francisco travel as unapproved travel outside forum ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L156))

- **Sonnet 4.6: Pass.** The report explicitly identifies the San Francisco travel as outside the Litigation Forum (defined as Cook County and the five collar counties), notes that §9.1(3) and Engagement Letter §8(3) required prior written approval, and confirms that no such approval appears in the Prior Approval Log. This is captured in deviation D-6 and D-7, and elaborated in Section 4.4.
- **GPT-5.5: Pass.** The report explicitly flags San Francisco travel as outside the Litigation Forum, cites §9.1(3) as requiring prior written approval, states that no approval appears in the log, and applies this to Messina and Pryor-Hall/Pryce-Hall travel time and expenses.

### C-019

Identifies business class airfare issue for Messina ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L164))

- **Sonnet 4.6: Pass.** The report explicitly addresses Messina's business-class airfare of $2,847.00 in the travel section (D-6/D-7), noting under line E-008 that 'business class is allowed only if the scheduled flight is 4+ hours. ORD–SFO is typically scheduled at about 4h15m–4h45m, so it may qualify. Ask for the itinerary; if under 4 hours, reduce to the economy fare (Pryor-Hall paid $412).' This identifies the issue, references the §6.1 policy, and notes the borderline nature of the flight duration.
- **GPT-5.5: Pass.** The report expressly flags E-008, Sandra Messina’s $2,847 business-class ORD–SFO airfare, cites §6.1, explains business class is allowed only if the scheduled flight is 4+ hours, notes ORD–SFO is typically about 4h15m–4h45m, and recommends verifying the itinerary/reducing to economy if under 4 hours. This satisfies the criterion.

### C-020

Notes ambiguity of 4-hour flight threshold for business class ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L172))

- **Sonnet 4.6: Pass.** In Section 4.4, the report explicitly addresses the business class airfare for the ORD-SFO flight and notes: 'business class is allowed only if the scheduled flight is 4+ hours. ORD–SFO is typically scheduled at about 4h15m–4h45m, so it may qualify. Ask for the itinerary; if under 4 hours, reduce to the economy fare.' This directly acknowledges the borderline/ambiguous nature of the threshold, noting the flight is typically just over 4 hours but recommending verification rather than treating it as clearly compliant or clearly non-compliant.
- **GPT-5.5: Pass.** The report expressly flags the ORD–SFO business-class airfare as requiring verification, notes that business class is allowed only for scheduled flights of 4+ hours, and states that ORD–SFO is typically about 4h15m–4h45m so it may qualify, with a request for the itinerary. This acknowledges the borderline/ambiguous nature of the 4-hour threshold rather than treating it as clearly compliant or non-compliant.

### C-021

Identifies hotel rate exceeds $325/night cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L180))

- **Sonnet 4.6: Pass.** In section 4.4, the report explicitly identifies the hotel charge of $489/night × 3 × 2 travelers ($2,934.00) and states the §6.1 cap is $325/night, recommending a reduction to $1,950.00 (a $984.00 reduction). This clearly flags that the $489/night rate exceeds the $325/night cap.
- **GPT-5.5: Pass.** The report flags the San Francisco hotel charges (E-009/E-013) as billed at $489/night for two travelers, states the compliant cap is $325/night under §6.1, calculates the reduction, and separately notes the travel lacked prior approval. This satisfies the requirement to identify the hotel-rate overage for both travelers.

### C-022

Calculates correct hotel overage: $984.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L188))

- **Sonnet 4.6: Pass.** The report states in the travel expenses table: 'E-009 / E-013 Hotel $489/night × 3 × 2 travelers $2,934.00 $1,950.00 $984.00 §6.1 — $325/night cap.' This matches the criterion exactly: billed $2,934.00, allowed $1,950.00 ($325 × 6 nights), overage $984.00 = ($489 − $325) × 6 = $164 × 6 = $984.00.
- **GPT-5.5: Pass.** The report correctly states the hotel charges as $2,934 billed, $1,950 compliant, and a $984.00 reduction/overage, matching (($489 - $325) × 6 nights).

### C-023

Identifies black car service as prohibited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L196))

- **Sonnet 4.6: Pass.** In Section 4.4, the report explicitly identifies 'E-011 Messina black car service $387.00' as non-compliant, stating '$387.00 | $0.00 | $387.00 | §6.1 --- never reimbursable'. This clearly flags the black car service charge as prohibited under §6.1.
- **GPT-5.5: Pass.** The report specifically identifies E-011 as “Messina black car service” billed at $387.00, states the compliant amount is $0.00, cites §6.1, and says it is “never reimbursable.”

### C-024

Recommends full disallowance of black car service: $387.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L204))

- **Sonnet 4.6: Pass.** In Section 4.4, the report explicitly addresses E-011 (Messina black car service) and recommends a full disallowance of $387.00, citing §6.1 which states it is 'never reimbursable'. The adjustment schedule in Section 7 also includes this amount within the SF travel expenses disallowance (D-7, $7,234.00 total). The criterion is satisfied.
- **GPT-5.5: Pass.** The report specifically identifies E-011 as “Messina black car service” billed at $387.00, marks the compliant amount as $0.00, and recommends a $387.00 reduction because it is never reimbursable. It also disallows all related SF travel expenses in the main adjustment schedule.

### C-025

Identifies unapproved local counsel retention (Brixton & Associates) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L212))

- **Sonnet 4.6: Pass.** The report explicitly identifies the $1,500.00 Brixton & Associates local counsel retainer as D-11 in the deviation register, noting it requires prior approval per §9.1(5) and EL §8(5), and that no approval exists in the log. This is further detailed in Section 4.6 (expense line E-021) and included in the recommended adjustment schedule.
- **GPT-5.5: Pass.** The report explicitly flags Brixton & Associates as a $1,500 local counsel retainer, states that engaging local counsel required prior approval under §9.1(5), and notes that no approval is in the log/on file.

### C-026

Identifies Elaine Cho's expired contract attorney approval ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L220))

- **Sonnet 4.6: Pass.** The report clearly identifies Elaine Cho's expired contract attorney approval in deviation D-3. It notes that approval PA-005 covered July 22 to September 30, 2024 only, that no renewal was requested, and that all 21 October entries (214.0 hrs) should be disallowed at $41,730.00. The report also notes the invoice subtotal shows only 186.0 hrs / $36,270.00, which understates her time. The criterion requires identification of the expired approval and that her 186.0 hours ($36,270.00) lack current authorization per §9.1 — the report satisfies this, referencing §9.1(6) as the authority for disallowance.
- **GPT-5.5: Pass.** The report expressly flags Elaine Cho as a contract attorney whose approval expired on September 30, 2024, cites Guidelines §9.1(6), and states that her October time lacks renewal/current authorization and should be disallowed. Although it calculates line-item time as 214.0 hours/$41,730, it also identifies the invoice-stated 186.0 hours/$36,270.00 and notes that this subtotal is understated.

### C-027

Calculates correct amount at risk for Cho: $36,270.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L228))

- **Sonnet 4.6: Fail.** The criterion requires the report to state that $36,270.00 (186.0 hours × $195/hour) is at risk due to Cho's expired approval. The agent's report identifies the correct amount at risk differently: it disallows $41,730.00 (214.0 hours × $195) for the post-expiry October entries, not $36,270.00. The $36,270.00 figure appears in the report as the understated subtotal shown on the invoice (186.0 hrs), while the agent correctly identifies that the actual line-item hours are 214.0 and disallows $41,730.00. The report does not state that $36,270.00 is the amount at risk; rather, it treats $41,730.00 as the disallowance. The criterion specifically asks for $36,270.00 to be identified as the amount at risk, which the agent does not do — instead it uses $41,730.00 as the disallowance figure.
- **GPT-5.5: Fail.** The report identifies Cho's expired approval but quantifies the disallowance/amount at risk as $41,730.00 based on 214.0 hours, not the required $36,270.00 based on 186.0 hours × $195/hour. Although it mentions $36,270.00 as the invoice subtotal, it does not state that amount is the at-risk amount due to the expired approval.

### C-028

Identifies Messina Oct 3 entry as block billing ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L236))

- **Sonnet 4.6: Pass.** The report identifies entry 14 as Sandra Messina's 5.8-hour block billing entry with the narrative 'Review and analyze expert report materials; conference with J. Pryce-Hall and R. Tanaka regarding expert discovery strategy and deposition preparation.' This matches the description of combining review of expert report materials with a conference with associates. The entry is listed in the D-9 block billing table with a 30% reduction of $1,557.30. However, the criterion specifies this is an October 3 entry that also includes 'review of opposing counsel correspondence,' which is not mentioned in the narrative shown. The report's narrative for entry 14 does not mention opposing counsel correspondence. That said, the criterion asks whether the entry is flagged as block billing - entry 14 (Messina, 5.8h) is indeed flagged as block billing in the D-9 section. The date is not explicitly stated in the report for entry 14, but given the sequential numbering and context, it plausibly corresponds to an early October entry. The core question is whether Messina's 5.8-hour entry combining expert report review and conference is identified as block billing - and it clearly is (entry 14 in the D-9 table).
- **GPT-5.5: Pass.** The report flags Sandra Messina’s 5.8-hour entry as block billing in D-9, listing it as Entry 14 with a narrative combining expert report review and a conference regarding expert discovery/deposition preparation, and applies a 30% reduction under §4.2. This matches the required October 3 Messina block-billing issue.

### C-029

Applies 30% reduction to Messina block billing: ~$1,557.30 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L244))

- **Sonnet 4.6: Pass.** The agent's output includes entry 14 (Sandra Messina, 5.8 hours) in the block billing table (D-9) with a billed amount of $5,191.00 and a 30% reduction of $1,557.30. This matches exactly the criterion's expected calculation (5.8 × $895 = $5,191.00; 30% of $5,191.00 = $1,557.30). The reduction is applied and correctly calculated.
- **GPT-5.5: Pass.** The report identifies Sandra Messina’s 5.8-hour block-billed entry billed at $5,191.00 and applies a 30% reduction of $1,557.30 in the block billing table.

### C-030

Identifies missing 75% budget threshold notification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L252))

- **Sonnet 4.6: Pass.** The report explicitly identifies in Section 4.7 (D-18) that cumulative 2024 spend has reached $2,230,941.14 (or $2,257,818.14 on line-item figures), exceeding the 75% budget threshold of $2,100,000, and that Blackwell Stanhope failed to provide the required written notification per §10.1 and Engagement Letter §7. This is also listed as deviation D-18 in the Deviation Register with 'High' severity.
- **GPT-5.5: Pass.** The report explicitly flags the 75% budget threshold issue: it states that cumulative 2024 spend reached $2,230,941.14 on the firm’s figures, exceeding the $2,100,000 threshold, and that no required written notification was provided under §10.1 / Engagement Letter §7.

### C-031

Identifies missing written explanation for invoice exceeding $350,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L260))

- **Sonnet 4.6: Pass.** The report explicitly identifies D-19 as a 'High' severity deviation titled 'Monthly threshold,' stating 'Invoice > $350,000 without written explanation' with the authority '§10.1; EL §7' and action 'Require explanation.' Section 4.7 further elaborates: '$350,000 monthly threshold (D-19). Any invoice over $350,000 must be accompanied by a written explanation of the cost drivers, why the work was necessary and the expected spending trajectory. None was provided. The email simply states the total.' The invoice total of $487,329.14 is clearly identified throughout the report. This fully satisfies the criterion.
- **GPT-5.5: Pass.** The report states the invoice total is $487,329.14, flags that it exceeds the $350,000 monthly threshold under §10.1, and explicitly notes that no written explanation was provided/submitted.

### C-032

Identifies Messina meals exceeding $75/day cap ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L268))

- **Sonnet 4.6: Pass.** The report explicitly identifies in section 4.4 (Travel) that Messina's meals of $312.40 over 3 days exceed the $75/person/day cap, with a maximum allowed of $225.00 and an overage of $87.40. This is captured in the travel expense table under E-010.
- **GPT-5.5: Pass.** The report explicitly flags E-010 Messina meals of $312.40 over 3 days, states the compliant amount is $225.00 under the $75/person/day cap, and calculates the reduction/overage as $87.40.

### C-033

Calculates correct meal overage for Messina: $87.40 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L276))

- **Sonnet 4.6: Pass.** The report explicitly states in the travel expenses table (D-7 section): E-010 Messina meals $312.40 / 3 days, billed $312.40, compliant $225.00, reduction $87.40, with the basis '§6.1 — $75/person/day'. This matches exactly the criterion: $312.40 − $225.00 ($75 × 3 days) = $87.40.
- **GPT-5.5: Pass.** The report explicitly calculates Messina's meals as $312.40 billed, $225.00 compliant at $75/day for 3 days, with a reduction/overage of $87.40.

### C-034

Identifies travel time billed at full rate instead of 50% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L284))

- **Sonnet 4.6: Pass.** In Section 4.4 (Travel, D-6, D-7), the report explicitly identifies that Messina's travel time (4.2h @ $895) and Pryor-Hall's travel time (4.2h @ $575) were billed at full rates instead of the 50% rate required by §6.1. The table shows Fee 25 (Messina) billed at $3,759.00 with a compliant amount of $1,879.50 (50% reduction of $1,879.50) and Fee 26 (Pryor-Hall) billed at $2,415.00 with a compliant amount of $1,207.50 (50% reduction of $1,207.50). This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly flags the San Francisco travel time entries for Messina and Pryor-Hall/Pryce-Hall: 4.2 hours each billed at full rates ($895 and $575) and states that under §6.1 they should be billed at 50%, with calculated reductions.

### C-035

Calculates correct travel time overcharge: ~$3,087.00 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L292))

- **Sonnet 4.6: Pass.** The agent's report in Section 4.4 explicitly calculates the travel time overcharge: Messina 4.2h @ $895 full rate = $3,759.00, reduced to $1,879.50 (50%), overcharge $1,879.50; Pryor-Hall 4.2h @ $575 full rate = $2,415.00, reduced to $1,207.50 (50%), overcharge $1,207.50. The report then states 'travel time would be reduced by $3,087.00' which is exactly $1,879.50 + $1,207.50 = $3,087.00. This matches the criterion's expected calculation precisely.
- **GPT-5.5: Pass.** The report correctly calculates the 50% travel-time reductions: Messina overcharge $1,879.50 and Pryor-Hall overcharge $1,207.50, totaling $3,087.00.

### C-036

Identifies e-discovery vendor expense exceeding $10,000 approval threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L300))

- **Sonnet 4.6: Pass.** The report explicitly identifies Forrest Data Solutions at $48,250 in deviation D-10, noting it is a single expense over $10,000 requiring prior approval under §9.1(2),(7) and §7.1(c), and that no approval appears in the log. This is further detailed in Section 4.6 (E-020) and included in the recommended adjustment schedule.
- **GPT-5.5: Pass.** The report explicitly flags Forrest Data Solutions as an unapproved vendor/e-discovery expense of $48,250.00, states it is over the $10,000 threshold requiring prior approval under Guidelines §9.1, and notes that no approval is documented in the log.

### C-037

Provides summary table of all violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L308))

- **Sonnet 4.6: Pass.** The report includes a comprehensive Deviation Register (Section 3) that lists all violations with their IDs, severity, category, deviation description, amounts, authority, and recommended actions. Section 7 (Recommended Adjustment Schedule) provides a detailed summary table listing each deviation reference, the adjustment description, type (fees/expenses), and dollar amount, including subtotals and a total recommended disallowance. The expense table in Section 4.6 also shows billed amounts, actions, and adjustments for each expense line. Together these tables satisfy the criterion of listing individual violations with original charged amounts and recommended adjustments/reductions. While 'compliant/allowed amounts' are not always shown as a separate column in every table, the combination of billed amounts and recommended reductions effectively communicates the same information, and the executive summary table shows line-item totals vs. recommended disallowances vs. currently supportable amounts.
- **GPT-5.5: Fail.** The report includes a deviation register and recommended adjustment schedule summarizing individual violations and reductions, but it does not provide a summary table that consistently lists each violation with original charged amount, compliant/allowed amount, and recommended adjustment/reduction. Many entries include only an adjustment amount or non-monetary action, and allowed amounts are generally absent.

### C-038

Calculates total recommended adjustment to the invoice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L316))

- **Sonnet 4.6: Pass.** The report provides a total recommended disallowance of $156,652.79 in Section 7 (Recommended Adjustment Schedule). The individual fee adjustments sum to: $10,177.50 + $41,730.00 + $5,660.00 + $6,216.00 + $6,174.00 + $2,715.50 + $10,758.45 = $83,431.45 (matches stated subtotal). The individual expense adjustments sum to: $7,234.00 + $48,250.00 + $1,500.00 + $7,198.74 + $4,820.00 + $718.60 + $3,500.00 = $73,221.34 (matches stated subtotal). Total: $83,431.45 + $73,221.34 = $156,652.79 (matches stated total). The arithmetic is internally consistent and a clear total is provided.
- **GPT-5.5: Pass.** The report provides a clear total recommended disallowance/reduction of $156,652.79. The listed fee adjustments sum to $83,431.45, the listed expense adjustments sum to $73,221.34, and those subtotals reconcile exactly to the stated total. Separately withheld amounts are also itemized and internally consistent, but not included in the recommended adjustment total.

### C-039

Calculates proposed revised invoice total ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L324))

- **Sonnet 4.6: Fail.** The report provides a financial disposition table showing 'Currently supportable (payable as undisputed once corrected invoice received)' of $206,941.31, and a 'Maximum potentially payable if all withheld items are substantiated' of $357,553.35. However, the criterion specifically asks for a proposed revised invoice total calculated as the original $487,329.14 minus the total recommended adjustments ($156,652.79), which would be $330,676.35. The report does not present this specific calculation. Instead, it works from the line-item total ($514,206.14) rather than the stated invoice total ($487,329.14), and the 'currently supportable' figure of $206,941.31 is derived differently (it excludes withheld items). The report explicitly states 'Payment should never exceed the stated invoice total of $487,329.14' but never subtracts the $156,652.79 disallowance from $487,329.14 to arrive at a revised invoice total. The criterion requires a proposed revised invoice total = original $487,329.14 minus total recommended adjustments, which is not provided.
- **GPT-5.5: Fail.** The report lists total recommended disallowances of $156,652.79 and other payable/supportable amounts based on line-item totals, but it does not provide a proposed revised invoice total calculated as the original stated invoice amount of $487,329.14 minus the recommended adjustments (which would be $330,676.35 if using disallowances only).

### C-040

Notes budget concerns re: cumulative spend vs. 2024 budget ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L332))

- **Sonnet 4.6: Pass.** The report extensively discusses budget concerns in Section 4.7. It notes that cumulative 2024 spend through September was $1,743,612.00 (62.3%), and that October takes it to $2,230,941.14 on the firm's figures or $2,257,818.14 on line items, both exceeding the $2,100,000 (75%) threshold of the $2,800,000 budget. It also notes the budget trajectory concern, that this invoice is more than twice the monthly average, that only $569,058.86 remains, and that with expert reports due December 20, 2024, the matter is likely to overrun the budget. It also mentions the 10% overrun trigger requiring a meeting between lead partner and General Counsel. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report clearly discusses the 2024 budget: it identifies the $2.8M budget, the 75% threshold of $2.1M, September YTD spend of $1,743,612.00, October cumulative spend of $2,230,941.14 / $2,257,818.14, and the required notice/revised budget. It also flags that the remaining budget is likely insufficient and requests a forecast, though it does not expressly mention trial in April 2025. Overall, the budget concern criterion is substantially satisfied.

### C-041

Categorizes violations by severity levels ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L340))

- **Sonnet 4.6: Pass.** The report uses a Deviation Register (Section 3) that explicitly categorizes each violation by severity: Critical, High, Medium, and Low-Med. This gives at least three distinct severity levels. Additionally, Section 5 separates 'Discretionary Review Items' (analogous to 'Requires Discussion'), and the main register covers mandatory reductions (Critical/High) and process failures (High items like budget notice, LEDES coding, monthly threshold). The structure maps well to the three-category framework described in the criterion, even if the labels differ slightly from the example labels provided.
- **GPT-5.5: Pass.** The report explicitly categorizes each deviation in a Deviation Register using multiple severity levels, including Critical, High, Medium, and Low--Med, and separates discretionary review items from recommended disallowances/holds. This satisfies the requirement to categorize violations by at least three severity levels.

### C-042

Classifies business class airfare as borderline/requires discussion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L348))

- **Sonnet 4.6: Pass.** In Section 4.4, the report explicitly addresses Messina's business-class airfare (E-008, $2,847.00) and states: 'business class is allowed only if the scheduled flight is 4+ hours. ORD–SFO is typically scheduled at about 4h15m–4h45m, so it may qualify. Ask for the itinerary; if under 4 hours, reduce to the economy fare.' This clearly treats the issue as borderline/requires discussion rather than a mandatory reduction or dismissing it as compliant. The action column says 'Verify' for both the compliant amount and the reduction, confirming the ambiguity is acknowledged.
- **GPT-5.5: Pass.** The report treats Messina’s $2,847 business-class airfare as a verification/discussion item, noting that business class is allowed only for scheduled flights of 4+ hours, that ORD–SFO typically may qualify, and requesting the itinerary before any reduction. It does not classify the airfare as a clear mandatory reduction or dismiss it as fully compliant.

### C-043

Recommends communication to Blackwell Stanhope identifying violations and requesting adjustments ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L356))

- **Sonnet 4.6: Pass.** Section 8 (Recommended Actions) explicitly states: 'Return the invoice (§8.1, §7.3, §11.2(f)). Send written notice to Sandra Messina and Howard Blackwell III listing the adjustments and their basis (§8.2). The firm has 15 days from notice to dispute them.' This clearly recommends communication to Blackwell Stanhope LLP identifying non-compliant charges and requesting adjustments. Additional actions also request documentation and disclosures from the firm.
- **GPT-5.5: Pass.** The report explicitly recommends returning the invoice and sending written notice to Blackwell Stanhope representatives listing the adjustments and their bases. It also requests a corrected invoice/LEDES submission, supporting documentation, required disclosures, and decisions on retroactive approvals for non-compliant charges.

### C-044

Recommends requesting retroactive approval for Elaine Cho ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L364))

- **Sonnet 4.6: Pass.** The report addresses Elaine Cho's expired approval in D-3 and in Section 8 (Recommended Actions, item 5). In item 5, the report states: 'If Cho's review work is still needed, require a new PA request before any further contract-attorney time is billed.' This constitutes a recommendation regarding Cho's re-authorization — specifically, that if her work is still needed, a new prior approval request should be submitted. This satisfies the criterion of recommending seeking retroactive or renewed approval for Cho's continued work.
- **GPT-5.5: Pass.** The report explicitly addresses Elaine Cho’s expired approval and, in Recommended Action 5, advises deciding on retroactive approval for a “Cho extension” and requiring a new prior-approval request if her review work is still needed. This satisfies the criterion requiring a recommendation regarding Cho’s re-authorization.

### C-045

Recommends demanding budget threshold notifications from counsel ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L372))

- **Sonnet 4.6: Pass.** The report explicitly addresses budget threshold notifications in multiple places. Section 4.7 (D-18, D-19) identifies the 75% threshold crossing and the $350,000 monthly threshold as deviations, and Section 8 (Recommended Actions, item 4) explicitly states: 'Require the §10.1 disclosures: a 75%-threshold notice with a revised 2024 budget, and a written explanation for the invoice exceeding $350,000.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The report explicitly identifies missing budget notices (75% threshold and invoice over $350,000) and recommends requiring the §10.1 disclosures, including a revised budget and written explanation for exceeding the monthly threshold.

### C-046

Cites correct Guidelines section numbers for violations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L380))

- **Sonnet 4.6: Pass.** The report identifies 22 deviations (D-1 through D-22) and cites specific Guidelines section numbers for virtually all of them. Checking coverage: D-1 cites §8.1(d),(f); D-2 cites §3.1; D-3 cites §3.1, §9.1(6); D-4 cites §5.1; D-5 cites §5.1; D-6 cites §9.1(3), §6.1; D-7 cites §9.1(3), §6.1; D-8 cites §4.3(a),(b); D-9 cites §4.2; D-10 cites §9.1(2),(7), §7.1(c); D-11 cites §9.1(5); D-12 cites §7.1(a),(b),(d), §7.3; D-13 cites §7.1, §7.3; D-14 cites §7.1; D-15 cites §7.1(c), §9.1; D-16 cites §7.1, §7.2; D-17 cites §7.1; D-18 cites §10.1; D-19 cites §10.1; D-20 cites §4.4, §8.1; D-21 cites §4.1; D-22 cites §8.1(g), §1.2. That is 22/22 violations with section citations (100%). Checking accuracy of citations against the criterion's mapping: block billing (D-9) = §4.2 ✓; staffing (D-4, D-5) = §5.1 ✓; travel (D-6, D-7) = §6.1 ✓; expenses (D-10 through D-17) = §7.1 ✓; prior approvals (D-2, D-3, D-6, D-10, D-11) = §9.1 ✓; budget (D-18, D-19) = §10.1 ✓. All key citations align with the criterion's accuracy mapping. Both thresholds (75% coverage and 75% accuracy) are clearly met.
- **GPT-5.5: Pass.** The report identifies numerous violations and, in the deviation register and detailed findings, cites specific Guideline sections for essentially all of them (e.g., §3.1, §4.2, §5.1, §6.1, §7.1, §8.1, §9.1, §10.1). The key citation mappings are largely accurate: block billing is tied to §4.2, staffing to §5.1, travel to §6.1 and §9.1, expenses/documentation to §7.1/§7.2, prior approvals to §9.1, and budget/monthly-threshold issues to §10.1. Any minor questionable or supplemental citations do not approach 25% of the cited violations.

### C-047

Correctly states original invoice total as $487,329.14 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L388))

- **Sonnet 4.6: Pass.** The report clearly states the original invoice total as $487,329.14 in multiple places, including the summary table ('Invoice total as stated: $487,329.14 (Fees $242,687.00; Expenses $244,642.14)') and elsewhere throughout the document.
- **GPT-5.5: Pass.** The report explicitly states the original invoice total as $487,329.14 in the summary table and references the same stated total elsewhere.

### C-048

Identifies administrative support ($2,345.00) as non-reimbursable overhead ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L396))

- **Sonnet 4.6: Pass.** The report explicitly identifies E-018 'After-hours word processing / admin' at $2,345.00 as disallowed under §7.1(a),(d) and Engagement Letter §5, categorizing it as prohibited overhead (D-12). This appears in both the Deviation Register (D-12: 'Technology surcharge (2%) and after-hours word processing' disallowed under §7.1(a),(b),(d); §7.3) and in the expense table in Section 4.6 where E-018 'After-hours word processing / admin' at $2,345.00 is marked 'Disallow' with the full amount disallowed. The Recommended Adjustment Schedule also lists it under D-12 as 'Admin support + tech surcharge (E-018, E-019)' totaling $7,198.74.
- **GPT-5.5: Pass.** The report explicitly identifies E-018 “After-hours word processing / admin” billed at $2,345.00 and marks it “Disallow,” citing it as prohibited overhead/admin support under the guidelines. It also includes the charge in D-12 as prohibited overhead.

### C-049

Identifies technology surcharge ($4,853.74) as non-reimbursable overhead ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-litigation-invoice-against-outside-counsel-billing-guidelines/task.json#L404))

- **Sonnet 4.6: Pass.** The report explicitly identifies the technology surcharge of $4,853.74 as disallowed under §7.1(b) and §7.3 (surcharge prohibited) in both the Deviation Register (D-12) and the expense table in Section 4.6 (E-019). It is listed as a prohibited overhead charge and included in the recommended disallowance schedule.
- **GPT-5.5: Pass.** The report explicitly identifies the Technology Surcharge / Technology Infrastructure Surcharge of $4,853.74 as prohibited overhead, cites the billing guideline provisions, and recommends disallowing it.
