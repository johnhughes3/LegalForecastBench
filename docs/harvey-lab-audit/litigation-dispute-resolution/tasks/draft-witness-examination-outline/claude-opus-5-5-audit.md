# Claude Opus 5.5 audit: Draft Direct and Cross-Examination Outlines for Key Fact Witness in Breach of Contract and Fraud Action

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 62. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is factually careful. Figures, dates, entity names, email content and the pretrial rulings mostly check out, and several criteria Sol questioned (C-007, C-025, the date and unit-count items) track the record and the binding rulings closely. The clearest defect is C-040. It requires a separate 'Part 3' issue-flags section that the one-line instructions never request, and it fails integrated strategic notes outright. C-059, C-037/C-017 (threat ratings) and C-060 (subject lines) are milder hidden-format requirements. Several criteria turn tactical choices the court left open into pass/fail rules: raising the Trimble dispute on direct (C-010, contrary to Ridgeline's own representation), putting the carve-out on direct (C-001/C-002), and claiming personal knowledge of a relayed instruction (C-014). The supplied spreadsheet also has an unacknowledged integrity defect: shipments dated after the Sept 28 email and a note citing the December 2024 deposition. Under all-pass scoring, C-040 alone can zero out a strong outline.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | unrequested_requirement | [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L331) | C-040 requires a separate 'Part 3' issue-flags section and fails integrated strategic notes | revised |
| [O2](#o2) | arguable | unrequested_requirement | [C-059](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L483), [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L307), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L147) | Hidden format: a Part 3 / equivalent section (C-059) and threat or severity ratings (C-037, C-017) | revised |
| [O3](#o3) | arguable | unrequested_requirement | [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L491) | C-060 requires quoting at least two email subject lines, and its PASS/FAIL conditions leave a gap | adopted_after_reading_sol |
| [O4](#o4) | arguable | source_conflict | [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L91) | C-010 requires raising the Trimble commission dispute on direct, though Ridgeline told the court it would not | blind |
| [O5](#o5) | arguable | internal_inconsistency | [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L19), [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L27) | The severance carve-out must be elicited on direct, though the court already barred the release argument | blind |
| [O6](#o6) | arguable | legal_error | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L123) | C-014 demands 'personal knowledge' of a hold instruction that Elliston only heard about from Karen Cho | revised |
| [O7](#o7) | arguable | source_conflict | [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L435) | C-053 dates the VP role from August 2018, but Elliston testified he became VP in early 2019 | blind |
| [O8](#o8) | arguable | legal_error | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L107) | C-012 offers FRE 803(6) as an electronic-authentication consideration | blind |
| [O9](#o9) | arguable | document_defect | [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L99) | The supplied Q3 spreadsheet cannot be the Sept 28 attachment: it has Sept 29-30 shipments and a note citing the 2024 deposition | blind |

<a id="o1"></a>
### O1. C-040 requires a separate 'Part 3' issue-flags section and fails integrated strategic notes

**Status:** problematic · **Category:** unrequested_requirement · **Criteria:** [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L331)

The instructions say only 'Prepare a complete trial witness examination outline', and the solver system prompt adds nothing about structure. Direct and cross/redirect prep are implicit in the document type. A standalone 'Part 3 Issue Flags and Strategic Notes' section is not. Many competent outlines put evidentiary notes, pretrial-ruling references and objection responses inline beside each topic block, which is what C-033 rewards. C-040 expressly FAILs such an outline 'even if some strategic notes appear within Parts 1 and 2.' The 'Part 3' label shows the criterion tracks a hidden spec. Under all-pass scoring, a thorough integrated outline scores zero.

Evidence:
- `task.json instructions`: “Prepare a complete trial witness examination outline for Marcus Elliston using the attached case materials and pretrial rulings.”
- `C-040`: “FAIL if there is no separate section for issue flags and strategic notes (even if some strategic notes appear within Parts 1 and 2).”

Suggested fix: Pass when evidentiary, procedural and strategic issues, with FRE and pretrial-ruling references, are covered anywhere in the outline, inline or in a separate section.

Related GPT-6 Sol findings: confirmed_defects/1.

<a id="o2"></a>
### O2. Hidden format: a Part 3 / equivalent section (C-059) and threat or severity ratings (C-037, C-017)

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-059](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L483), [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L307), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L147)

C-059 requires a 'Part 3 (Issue Flags and Strategic Notes) or clearly equivalent section'. It is more lenient than C-040 (FAIL only if 'entirely missing'), but it still demands a structural element the instructions never mention. C-037 FAILs an outline with no high/medium/low 'or equivalent' rating on any attack vector. C-017 separately requires the outline to 'assess the threat level'. Rating attacks is a practitioner's style choice, not a standard component of an examination outline. An outline that anticipates every attack, maps the impeachment sources and scripts redirect could fail on format alone. These are only arguable because 'clearly equivalent' and 'or equivalent' may let judges accept prose prioritization or a strategic subsection.

Evidence:
- `C-059`: “PASS if the output document contains a Part 3 (Issue Flags and Strategic Notes) or clearly equivalent section”
- `C-037`: “FAIL if no threat/severity assessments are provided for any attack vector.”
- `C-017`: “assesses the threat level, and proposes redirect questions”

Suggested fix: Fold C-059 into a substantive check that strategic issues are covered anywhere. Drop C-037 or replace it with 'identifies which attacks are most damaging'. Remove 'assesses the threat level' from C-017.

Related GPT-6 Sol findings: confirmed_defects/1.

<a id="o3"></a>
### O3. C-060 requires quoting at least two email subject lines, and its PASS/FAIL conditions leave a gap

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L491)

The instructions never ask for subject lines. A competent outline can identify the three emails by date, exhibit number or Bates range (CASCADE_EMAIL_003847-59) without quoting subject lines, and it would fail. There is also a gap between PASS (at least two correct) and FAIL (none, or substantially incorrect), so an outline with exactly one correct subject line fits neither condition. The judge prompt passes only when the output 'satisfies the criterion as described', so that case most likely FAILs. The gap therefore matters less than the hidden requirement.

Evidence:
- `C-060`: “PASS if the outline references at least two of the three correct email subject lines”
- `C-060`: “FAIL if none of the email subject lines are referenced or they are substantially incorrect.”
- `rubric_criterion.txt`: “**PASS**: The agent's output satisfies the criterion as described”

Suggested fix: Pass if the outline accurately identifies the Sept 28, Oct 5 and Nov 15 emails by date, subject, exhibit or Bates number, and make PASS and FAIL complementary.

Related GPT-6 Sol findings: confirmed_defects/0.

<a id="o4"></a>
### O4. C-010 requires raising the Trimble commission dispute on direct, though Ridgeline told the court it would not

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L91)

The pretrial order records Ridgeline's position that it 'does not intend to introduce the commission dispute on direct examination but reserves the right to address it on redirect.' The court leaves the timing to each party. An outline that follows plaintiff's own representation holds the dispute for redirect, with the 'predates by months / different subject' points scripted there. That is a defensible choice. C-010 FAILs it because the direct examination does not address the conflict proactively. The USB issue (C-007) is different: there Ridgeline sought to inoculate on direct and the court allowed it.

Evidence:
- `pretrial-order-evidentiary-rulings.docx.txt`: “Ridgeline responds that it does not intend to introduce the commission dispute on direct examination but reserves the right to address it on redirect if Cascade raises it on cross-examination”
- `pretrial-order-evidentiary-rulings.docx.txt`: “both parties may address this issue at the time and in the manner each deems appropriate”
- `C-010`: “FAIL if the direct examination does not address the Trimble conflict proactively.”

Suggested fix: Pass if the outline makes a reasoned choice between direct and redirect, provided the defusing points (timing, different subject matter) appear somewhere.

<a id="o5"></a>
### O5. The severance carve-out must be elicited on direct, though the court already barred the release argument

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L19), [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L27)

C-001 and C-002 require direct-exam questions on the §8(b) carve-out to 'preempt' a non-disparagement argument. But the court has already held that the carve-out 'expressly permits' the testimony and that it 'will not entertain any argument at trial that Elliston's testimony is barred by or inconsistent with the terms of his release.' Cascade's counsel conceded the point at deposition. A competent outline could rely on the ruling and hold the carve-out for redirect, which C-039's own example contemplates ('the severance agreement to show the carve-out'). Such an outline fails C-002.

Evidence:
- `pretrial-order-evidentiary-rulings.docx.txt`: “the Court will not entertain any argument at trial that Elliston's testimony is barred by or inconsistent with the terms of his release.”
- `elliston-deposition-excerpts.docx.txt`: “For the record, Cascade does not dispute that the carve-out permits the witness to testify.”
- `C-002`: “FAIL if the direct examination does not include questions about the severance release and its carve-out.”

Suggested fix: Pass if the outline identifies the carve-out and the court's ruling and deploys them on direct or redirect.

<a id="o6"></a>
### O6. C-014 demands 'personal knowledge' of a hold instruction that Elliston only heard about from Karen Cho

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L123)

C-014's title and PASS condition require establishing Elliston's personal knowledge of Trimble's instruction to 'hold' the Q3 royalty report. He admits he did not hear it: Cho told him the same day. Cascade moved to strike that testimony as hearsay, and Ridgeline's counsel said it was offered for state of mind, adding that the instruction 'may also be admissible as a party-opponent statement through Ms. Trimble.' A careful outline limits Elliston to what he saw (the Oct 10 closed-door meeting, his experience that reports were never late) and flags the hearsay issue and alternative witnesses. Its FAIL wording ('personally observed or learned of') may save that outline, but the PASS wording demands personal knowledge that the record contradicts. (I dropped C-023 from this finding: the court denied Cascade's motion to exclude refill testimony, treating the Feb 5 refill as something the jury will hear.)

Evidence:
- `elliston-deposition-excerpts.docx.txt`: “I did not personally hear Ms. Trimble give the instruction. Karen Cho told me about it the same day.”
- `elliston-deposition-excerpts.docx.txt`: “At trial, the instruction itself may also be admissible as a party-opponent statement through Ms. Trimble.”
- `C-014`: “establishing Elliston's personal knowledge of the Voss-Trimble closed-door meeting on October 10, 2023, and Trimble's subsequent instruction to accounting to 'hold' the Q3 royalty report”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Evid. 602, 801(c), 802 (unverified): A lay witness must testify from personal knowledge, and a coworker's relayed out-of-court statement offered for its truth is hearsay unless an exclusion applies.

Suggested fix: Reword it to 'addresses how Elliston learned of the hold instruction and the resulting hearsay issue (Cho as source, state-of-mind purpose, or an alternative witness)'.

<a id="o7"></a>
### O7. C-053 dates the VP role from August 2018, but Elliston testified he became VP in early 2019

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L435)

C-053 requires establishing Elliston's 'role as VP of Sales Operations at Cascade (August 2018 to January 2024).' At deposition he said he was 'promoted to VP of Sales Operations in approximately early 2019.' August 2018 is when he joined Cascade. An outline that correctly states 'joined August 2018; VP from early 2019' could be failed by a literal judge. Low risk, but the criterion states a fact the record contradicts.

Evidence:
- `elliston-deposition-excerpts.docx.txt`: “From the time I was promoted to VP of Sales Operations in approximately early 2019 --- so roughly four and a half years.”
- `C-053`: “establishing Elliston's role as VP of Sales Operations at Cascade (August 2018 to January 2024)”

Suggested fix: Change it to 'employment at Cascade (August 2018 to January 12, 2024) and his role as VP of Sales Operations'.

<a id="o8"></a>
### O8. C-012 offers FRE 803(6) as an electronic-authentication consideration

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L107)

FRE 803(6) is a hearsay exception, not an authentication rule. Elliston's one-off investigative spreadsheet is a doubtful fit for 'regularly conducted activity' in any case, so the criterion can reward a misapplied citation. The court held that creator testimony under FRE 901(b)(1) suffices. An outline that follows that roadmap exactly (which C-011 rewards) could still be judged as treating the file 'identically to a simple paper document.' Most answers will mention metadata because of the date issue, so misgrading is limited.

Evidence:
- `C-012`: “(e.g., referencing FRE 803(6) business records exception, metadata, or chain of custody for the spreadsheet file)”
- `pretrial-order-evidentiary-rulings.docx.txt`: “Elliston, as the creator of the spreadsheet, is competent to authenticate it by testifying that he personally created the document”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Evid. 901(b)(1); 803(6) (unverified): Authentication by a witness with knowledge is sufficient; 803(6) governs hearsay, not authenticity.

Suggested fix: Drop the 803(6) example. Pass if the outline addresses electronic-file integrity (native file, metadata, USB custody) or follows the court's 901(b)(1) roadmap including the unaltered-condition element.

<a id="o9"></a>
### O9. The supplied Q3 spreadsheet cannot be the Sept 28 attachment: it has Sept 29-30 shipments and a note citing the 2024 deposition

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L99)

Elliston swears the exhibit is 'the same version I attached to my September 28 email,' and C-011 requires foundation that the data 'has not been altered since creation.' But the Shipment Detail tab has 13 rows dated Sept 29-30, 2023, including a Sept 29 MidAmerican shipment. The Summary tab covers 'Q3 2023 (July 1 – September 30, 2023)', and its D3 note cites 'Elliston's deposition testimony (p. 72)', given in December 2024. That note is on Elliston's own Summary sheet, not a separate annotation tab. A careful solver must flag a serious authentication and impeachment risk. The rubric assumes a clean exhibit and gives no credit for spotting the problem.

Evidence:
- `q3-unit-discrepancy-spreadsheet.xlsx.txt`: “A111='110' \| B111='09/29/2023' \| C111='DN-2023-04808' \| D111='PO-MDA-23-0082' \| E111='MidAmerican Distribution Services, LLC'”
- `q3-unit-discrepancy-spreadsheet.xlsx.txt`: “which is inconsistent with Elliston's deposition testimony (p. 72) that he first discovered the MidAmerican POs on September 25, 2023.”
- `elliston-deposition-excerpts.docx.txt`: “The version I provided to your firm --- to Ridgeline's counsel --- is the same version I attached to my September 28 email.”

Suggested fix: Remove the post-Sept-28 rows and the anachronistic note from the exhibit, or keep them deliberately and add a criterion rewarding identification of the integrity problem.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| confirmed_defects/0 | confirmed | [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L491) | arguable | The PASS/FAIL gap is real: with exactly one correct subject line, neither condition is met. But the judge prompt says PASS only when the output 'satisfies the criterion as described', so one line will reliably FAIL and the gap causes little misgrading by itself. The stronger problem is the requirement itself. A competent outline can cite the emails by date, exhibit number or Bates range without quoting subject lines, and the instructions never ask for subject lines. That makes it arguable, not confirmed. |
| confirmed_defects/1 | confirmed | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L307) (arguable), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L331) (problematic), [C-059](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L483) (arguable) | mixed | The instructions are one line with no structure, and the system prompt adds none. C-040 expressly FAILs integrated strategic notes 'even if some strategic notes appear within Parts 1 and 2', so it is a hidden-format requirement that fails a competent inline outline. C-059 is more lenient ('clearly equivalent section'; FAIL only if 'entirely missing'). C-037's severity ratings are one practitioner's style, but 'or equivalent' may admit prose prioritization. Both are arguable. |
| arguable/0 | arguable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L67) | not_a_defect | The pretrial order denied Cascade's attempt to stop Ridgeline from inoculating on USB during direct. It calls the Nov 15, Nov 20 and Dec 8 timing 'relevant context'. Elliston himself says 'I considered it self-preservation' and that he was 'afraid the evidence would be deleted' (pp.147-152). The FAIL condition ('self-preservation/whistleblower context') matches his own testimony. Favorable framing on your own direct is basic advocacy, and it does not require dropping candor about the policy. This is unlike C-010, where Ridgeline told the court it would not raise the issue on direct. |
| arguable/1 | arguable | [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L35), [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L43), [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L51), [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L411) | not_a_defect | None of these criteria requires conceding a material contradiction. Each requires identifying and preparing for attacks the defense brief explicitly lists (the date inconsistency; 1,100 vs 1,113, which C-050 itself calls 'minor'). C-004's 'last week of September' is Elliston's own deposition phrasing (p.74). Deposition p.78 ties the Sept 28 email to having 'identified the MidAmerican purchase orders', so C-003's phrasing is defensible. Its 'and/or' passes any outline that names the date conflict. |
| arguable/2 | arguable | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-witness-examination-outline/task.json#L211) | not_a_defect | The pretrial order expressly admits Voss's statement under FRE 801(d)(2)(A), quoting the 'representative capacity' text. The rulings bind this exercise, so a competent outline follows them. The FAIL condition does not depend on the subsection ('FRE 801(d)(2) is not referenced'), so an outline citing (D) together with the ruling avoids FAIL. The doctrinal point that agent statements usually fall under (C)/(D) is real, but it misgrades nobody here. |

## Blind pass and what changed

I split blind O1. C-040 stays problematic, but C-059 drops to arguable, because its 'clearly equivalent section / FAIL only if entirely missing' wording is materially more lenient. I merged C-059 into the C-037/C-017 finding (now O2). I checked the solver system prompt, and it says nothing about structure, so O1 stands. I adopted Sol's C-060 finding as arguable (O3), recasting it mainly as a hidden subject-line requirement. The judge prompt passes only when the criterion is satisfied, so the PASS/FAIL gap alone rarely misgrades. I dropped blind O6 (C-003/C-004). C-004's 'last week of September' is Elliston's own deposition wording (p.74), and deposition p.78 links the Sept 28 email to the MidAmerican POs, so C-003's phrasing is defensible. Its 'and/or' also passes any outline naming the date conflict. From blind O5 I removed C-023 and C-013. The pretrial order denied Cascade's motion to exclude testimony about the Feb 5 Hoffman refill, so the court contemplates that fact reaching the jury. O5 now rests on C-014 alone (now O6). I rejected Sol's C-007, C-003/004/005/050 and C-025 findings as not defects (reasons in sol_verdicts). I confirmed that the O9 deposition-citing note sits on the Summary sheet itself, not an annotation tab.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-040, C-059): Hidden three-part structure: a separate 'Part 3 Issue Flags and Strategic Notes' section is required but never requested
- **O2** (arguable; C-037, C-017): Severity/threat ratings for cross-examination attacks are required but never requested
- **O3** (arguable; C-010, C-051): C-010 requires raising the Trimble commission dispute on direct, but the record shows Ridgeline told the court it would not
- **O4** (arguable; C-001, C-002, C-039): Severance carve-out must be elicited on direct, though the court already barred the argument and C-039 frames it as redirect material
- **O5** (arguable; C-014, C-013, C-023): Criteria require eliciting through Elliston facts he knows only secondhand (the hold instruction, Hoffman's promotion date)
- **O6** (arguable; C-003, C-004): Date-inconsistency criteria adopt the defense's framing ('discovered MidAmerican POs on Sept 25', 'last week of September')
- **O7** (arguable; C-053): C-053 dates the VP role from August 2018, but Elliston testified he was promoted to VP in early 2019
- **O8** (arguable; C-012): C-012 offers FRE 803(6) as an electronic-authentication consideration and requires more than the court's authentication roadmap
- **O9** (arguable; C-011, C-032, C-042): The supplied Q3 spreadsheet cannot be the Sept 28 attachment: it has Sept 29–30 shipments and a note citing the 2024 deposition

## Coverage and limits

Blind pass: I read the instructions and all 62 criteria. I read these documents in full: the pretrial order, the Cascade trial brief excerpt, the Elliston deposition excerpts and the email chain. I searched the rest for the facts the criteria rely on. Severance agreement: §6 and §8(b), dates, and the 21-day consideration period. EDA: §5.2 and §7.1–7.3. Forensic summary: $7,315,000, $456,975 and Kowalski. Q3 spreadsheet: I checked the Summary and Sales Comparison tabs in full and tallied the Shipment Detail rows with a script. I checked date arithmetic: Sept 28, 2023 was a Thursday; Oct 30 to Nov 17 is 18 days; Jan 12 to Feb 5 is 24 days. I did not open the harness system prompt or the judge prompt files. I verified no legal authority against primary sources. The FRE propositions below rely on rule text as the pretrial order quotes it and on general knowledge, so each is marked unverified. The advisor tool was rate-limited, so nobody else reviewed these findings.

Reconciliation: I read all 62 criteria, the instructions, the solver system prompt and the judge prompt. I read these documents in full: the pretrial order, the Cascade trial brief excerpt, the Elliston deposition excerpts and the email chain. I checked the severance agreement, the EDA, the forensic summary and the Q3 spreadsheet (all three tabs, including row-level Shipment Detail) for the facts the criteria rely on. In this pass I re-verified the pretrial rulings on 801(d)(2)(A), the USB copying, the severance carve-out, the termination and refill, and authentication. I also re-verified deposition pp.72-78 and 145-152 and the spreadsheet's sheet structure. I read Sol's audit markdown and index entry. I read no primary legal authority in this session: FRE propositions rely on the rule text as the pretrial order quotes it, and every authority is marked unverified.
