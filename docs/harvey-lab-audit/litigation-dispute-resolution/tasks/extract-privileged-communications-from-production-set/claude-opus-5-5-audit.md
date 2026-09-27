# Claude Opus 5.5 audit: Extract Privileged Communications from Production Set — Privilege Log and Clawback Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 66. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric tracks the record closely: case number, Bates ranges, dates, the NorthBridge error and the order's terms all check out. Its most serious defects are mechanical or factual. C-046 and C-062 grade by DOC labels that appear nowhere in the record, and the QC report numbers the same documents differently. C-038 adds a fact the record does not support, that Correa had already retained counsel in October 2023. C-017 draws the DOC_005 line so narrowly that it fails a careful partial redaction. C-006 and C-012 require the privilege log, which the order makes a document served on the government, to admit the very vulnerabilities C-004 says not to concede. Several other clusters turn on one defensible judgment call each: element-by-element 502(b) analysis under a 502(d) order, waiver of DOC_004 (weighted four times), work product in slides 1–8, logging DOC_003, and recommending a common-interest agreement with a witness whose interests may diverge. Under the all-pass metric these can zero out competent answers.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | ambiguous_or_unjudgeable | [C-062](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L512), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L384) | C-062/C-046 grade by internal DOC_00X labels absent from the record; QC report numbers the same docs 1–10 | revised |
| [O2](#o2) | problematic | unsupported_fact | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L320) | C-038 assumes Correa had already retained Kendrick Sable on Oct 8, 2023; the record does not show that | blind |
| [O3](#o3) | problematic | legal_error | [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L152), [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L160) | C-017/C-018 confine DOC_005 privilege to messages 9–10, though messages 8 and 11 request or relay the Nakamura advice | revised |
| [O4](#o4) | problematic | internal_inconsistency | [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L64), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L112) | C-006/C-012 require the served privilege log to admit crime-fraud and common-interest weaknesses, contrary to C-004 | adopted_after_reading_sol |
| [O5](#o5) | arguable | internal_inconsistency | [C-065](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L536) | C-065 assumes DOC_003 is logged, but no criterion requires that conclusion | revised |
| [O6](#o6) | arguable | legal_error | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L216), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L224), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L240), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L264), [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L272), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L280) | Rubric requires an element-by-element FRE 502(b) analysis though the 502(d) order largely displaces 502(b) | revised |
| [O7](#o7) | arguable | legal_error | [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L120), [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L128), [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L136), [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L496) | Four criteria require treating DOC_004 as waived, leaving no room for the authority-to-waive or protective-clawback argument | blind |
| [O8](#o8) | arguable | unsupported_fact | [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L176) | C-020 says slides 1–8 were 'predating any litigation threat', but the whole deck post-dates the CID | revised |
| [O9](#o9) | arguable | legal_error | [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L416) | C-050 requires recommending a common-interest agreement with Correa despite signs her interests diverge | revised |
| [O10](#o10) | arguable | document_defect | [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L56), [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L304) | Reply timestamps precede the original emails in DOC_006 and DOC_010; C-005 reverses DOC_006's direction | blind |

<a id="o1"></a>
### O1. C-062/C-046 grade by internal DOC_00X labels absent from the record; QC report numbers the same docs 1–10

**Status:** problematic · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-062](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L512), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L384)

The solver sees files flagged-doc-batch-a..j and a QC report that numbers the documents 1–10: Mullins–Nagarajan is #4, Nagarajan–Metcalf #6, the Audit Committee email #8, the draft policy #10. The labels DOC_003–DOC_012 appear nowhere in the record. C-062 names only 'DOC_006, DOC_008, and DOC_010' and gives no Bates numbers or descriptions. A judge who sees only this one criterion cannot map those labels to the memo. If the memo uses the QC numbering, the judge may read the labels as #6, #8 and #10, which is the wrong set. C-046 lists ten bare labels, so a complete memo that identifies documents by Bates number may be failed. C-062 also calls DOC_006 and DOC_008 'clearly privileged', although the rubric itself (C-002, C-008) treats them as vulnerable. The QC report says 'twelve (12)' documents but lists ten.

Evidence:
- `task.json C-062`: “PASS if the memo recommends clawback for DOC_006, DOC_008, and DOC_010.”
- `task.json C-046`: “a privilege determination for each of the following documents: DOC_003, DOC_004, DOC_005, DOC_006, DOC_007, DOC_008, DOC_009, DOC_010, DOC_011, and DOC_012”
- `northbridge-qc-report.docx.txt`: “**6.** --- *Common interest email (Nagarajan--Metcalf)* Bates RDGL-00020512 through RDGL-00020515.”
- `northbridge-qc-report.docx.txt`: “the following twelve (12) representative documents are identified individually”

Suggested fix: Add the Bates range and a short description after every DOC label in C-046 and C-062. Drop 'clearly' from C-062. Change the QC report's 'twelve' to 'ten'.

Related GPT-6 Sol findings: Arguable / rubric overconstraint: item 3.

<a id="o2"></a>
### O2. C-038 assumes Correa had already retained Kendrick Sable on Oct 8, 2023; the record does not show that

**Status:** problematic · **Category:** unsupported_fact · **Criteria:** [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L320)

C-038's PASS condition requires reasoning that Correa 'had already retained separate counsel (Kendrick Sable LLP)'. In DOC_011 (Oct 8) Correa says she does not know where to start and turns to Nagarajan. Metcalf first appears on Nov 2, 2023, introducing himself as her counsel. A careful memo would say she appeared unrepresented at the time, which makes the risk of an inadvertent attorney-client relationship worse. A judge applying C-038 literally may fail that memo for leaving out, or contradicting, the retained-counsel premise.

Evidence:
- `task.json C-038`: “a former employee (Correa) who had already retained separate counsel (Kendrick Sable LLP)”
- `flagged-doc-batch-i.eml.txt`: “I just don't know where to start with something like this, and you're the smartest lawyer I know.”
- `flagged-doc-batch-f.eml.txt`: “Date: November 2, 2023, 9:17 AM EST ... I am writing in my capacity as counsel to Janet Correa”

Suggested fix: Replace the clause with 'who was apparently unrepresented at the time and later retained Kendrick Sable LLP', or delete it.

Related GPT-6 Sol findings: Confirmed defects: item 3.

<a id="o3"></a>
### O3. C-017/C-018 confine DOC_005 privilege to messages 9–10, though messages 8 and 11 request or relay the Nakamura advice

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L152), [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L160)

Counting oldest-first, message 8 (Correa, Jul 22) asks in-house counsel for legal advice: 'Ray, Tom, can you weigh in on whether we can use this?' Message 11 (Mullins, Jul 26) relays counsel's conclusion to the business. Message 7 frames the question for counsel. Internal communications that request legal advice or pass it on are commonly protected, so a careful reviewer might redact the Nakamura passages in messages 7, 8 and 11 as well. C-017's PASS condition requires finding 'the remaining 12 messages' not privileged. Its FAIL condition covers only whole-thread claims, so that answer falls between PASS and FAIL. C-018 is softer, since it fails only a whole-thread claim, but its PASS text still says 'messages 9 and 10' (arguable). The record also shows the thread newest-first and never numbers the messages.

Evidence:
- `task.json C-017`: “only the specific legal exchange (messages 9 and 10 ...) is privileged, while the remaining 12 messages in the thread are not privileged”
- `flagged-doc-batch-c.eml.txt`: “Good question on the Nakamura study =E2=80=94 Ray, Tom, can you weigh in on whether we can use this?”
- `flagged-doc-batch-c.eml.txt`: “we=E2=80=99ll steer clear of the Nakamura data in the detail aid”

Suggested fix: Pass any answer that confines the claim to the Nakamura legal exchange (the Ochoa–Viklund messages, optionally plus the passages in messages 7, 8 and 11 that request or relay the advice) and releases the business content. Fail only whole-thread claims.

Related GPT-6 Sol findings: Confirmed defects: item 1.

<a id="o4"></a>
### O4. C-006/C-012 require the served privilege log to admit crime-fraud and common-interest weaknesses, contrary to C-004

**Status:** problematic · **Category:** internal_inconsistency · **Criteria:** [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L64), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L112)

Clawback Order IV.B.2(iv) requires the Clawback Notice to be accompanied or quickly followed by a privilege log entry for each document that complies with the Local Civil Rules. The log for clawback candidates is therefore a document served on AUSA Cooperman. The order asks the log for a basis and identifying facts, not an admission of weaknesses. C-004 itself warns against language that would concede substance to the government. A competent practitioner would keep the crime-fraud and common-interest risks in the internal memo and leave them out of the served log. That answer fails C-006 and C-012. Only an internal working log with a risk column passes. The instructions never say the log is internal.

Evidence:
- `clawback-order.docx.txt`: “Be accompanied by, or followed within five (5) business days by, a privilege log entry for each document that conforms to the requirements of the Local Civil Rules”
- `task.json C-006`: “PASS if the privilege log entry for DOC_006 notes a vulnerability, issue, or risk related to the crime-fraud exception.”
- `task.json C-004`: “should not include language that would inadvertently concede or reveal the substance of the DOC_006 communication”

Suggested fix: Let the vulnerability note appear in the memo, or in a separate internal annotation or appendix to the log. Alternatively, have the instructions say the log is an internal working draft.

Related GPT-6 Sol findings: Arguable / rubric overconstraint: item 1, Arguable / rubric overconstraint: item 2.

<a id="o5"></a>
### O5. C-065 assumes DOC_003 is logged, but no criterion requires that conclusion

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-065](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L536)

C-023 and C-024 require only an analysis of whether the September 2020 Ellsworth–Nagarajan emails were prospective-client consultations. Logging is defensible: Nagarajan was 'evaluating whether it makes sense to bring in outside regulatory counsel', and Ellsworth gave substantive advice. Excluding is also defensible: Ellsworth opened with a networking pitch ('no obligation, of course'), no engagement followed for three years, and the engagement letter disclaims any retroactive adoption of prior communications. A reviewer who excludes DOC_003 still passes C-058 and C-059 under their 6-of-8 tolerance but fails C-065, because there is no log entry to grade.

Evidence:
- `task.json C-065`: “PASS if the privilege log entry for DOC_003 correctly identifies Catherine Ellsworth (Harwick & Calloway LLP) and Priya Nagarajan”
- `engagement-letter.docx.txt`: “Nothing in this letter is intended to constitute a retroactive adoption or ratification of any prior communications as falling within the scope of this engagement.”
- `flagged-doc-batch-a.eml.txt`: “I'd be happy to share some general thoughts on best practices we've seen work well for companies at a similar stage — no obligation, of course.”

Suggested fix: Make C-065 conditional: PASS if DOC_003 is logged with the correct parties, or excluded with a stated reason.

<a id="o6"></a>
### O6. Rubric requires an element-by-element FRE 502(b) analysis though the 502(d) order largely displaces 502(b)

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L216), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L224), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L240), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L264), [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L272), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L280)

The order says there is no waiver 'regardless of whether such disclosure was inadvertent or intentional' if its procedures are followed, and deems compliance to satisfy 502(b) 'as a matter of law'. The Explanatory Note to 502(d) likewise allows orders that return documents without waiver irrespective of the care taken. A strong memo could center the order's own tests (the 10-business-day notice, the constructive-knowledge Discovery Date, diligence) and treat 502(b) briefly. The six criteria tie credit to named 502(b) subsections or to a 502(b)(3) framing. C-027, C-029 and C-030 track the order and are sound. Many memos will include 502(b) as a fallback, so this is arguable.

Evidence:
- `clawback-order.docx.txt`: “Compliance with the procedures set forth in this Section IV shall be deemed to satisfy the requirements of Federal Rule of Evidence 502(b) as a matter of law”
- `task.json C-031`: “PASS if the memo addresses FRE 502(b)(1) by explaining that the disclosure was inadvertent”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Evid. 502(d) & Explanatory Note (✓): A 502(d) order may provide for return of documents without waiver irrespective of the care taken by the disclosing party.

Suggested fix: Let an analysis of the order's own non-waiver, deadline and diligence terms satisfy the timeliness, preventive-steps and rectification criteria, without requiring each 502(b) subsection by name.

Related GPT-6 Sol findings: Arguable / rubric overconstraint: item 4.

<a id="o7"></a>
### O7. Four criteria require treating DOC_004 as waived, leaving no room for the authority-to-waive or protective-clawback argument

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L120), [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L128), [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L136), [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L496)

Lassiter forwarded Viklund's memo despite the express instruction 'do not forward... without my prior approval'. Courts disagree on whether an employee's unauthorized disclosure waives a privilege that management controls. The rubric's view (waived, no clawback) is mainstream and defensible. But a competent memo that makes a low-cost protective clawback under the 502(d) order, with the waiver risk flagged, fails four criteria. Under the all-pass metric, one judgment call carries four criteria of weight.

Evidence:
- `flagged-doc-batch-b.eml.txt`: “Please do not forward or distribute this analysis outside the legal department without my prior approval.”
- `task.json C-014`: “FAIL if the memo recommends clawing back DOC_004.”

Authorities (✓ = primary text checked in the auditing session):
- Commodity Futures Trading Comm'n v. Weintraub, 471 U.S. 343 (1985) (unverified): Power to waive the corporate attorney-client privilege rests with corporate management.

Suggested fix: Merge C-014, C-015 and C-060. Pass memos that find waiver likely and either decline clawback or make an explained protective claim.

Related GPT-6 Sol findings: Arguable / rubric overconstraint: item 5.

<a id="o8"></a>
### O8. C-020 says slides 1–8 were 'predating any litigation threat', but the whole deck post-dates the CID

**Status:** arguable · **Category:** unsupported_fact · **Criteria:** [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L176)

The deck was created Dec 5, 2023, after the Nov 1 CID. Slide 8 is dated 'as of November 30, 2023'. Slide 2 frames the deck as responding to 'recent government interest'. The deck's own Part I/Part II split and the QC report's 'Work Product (Partial)' code support the conclusion that the routine slides are not work product. But the stated reason is false. A reasoned claim over slide 2 or the whole deck (prepared by counsel after the CID) fails C-020. C-019 and C-022 rest on the deck's own split and are sound.

Evidence:
- `task.json C-020`: “slides 1-8 of DOC_009 (covering routine regulatory risk matters predating any litigation threat)”
- `flagged-doc-batch-g.docx.txt`: “FY2023 Veratrine XR Compliance Scorecard (as of November 30, 2023)”
- `flagged-doc-batch-g.docx.txt`: “**Part I (Slides 3--8):** Routine regulatory compliance posture”

Suggested fix: Replace the reason with 'routine compliance content that would have been prepared in substantially similar form regardless of the investigation'. Do not fail a reasoned claim over slide 2.

Related GPT-6 Sol findings: Confirmed defects: item 2.

<a id="o9"></a>
### O9. C-050 requires recommending a common-interest agreement with Correa despite signs her interests diverge

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L416)

The record repeatedly flags divergence. Viklund's deck warns that Correa's interests 'may diverge'. The Audit Committee is probing her separation terms and any side letters. DOC_008 itself seeks a 'consistent narrative to the government', which could draw scrutiny as witness alignment. A competent memo might advise reassessing the coordination, or formalizing it only with conflict-waiver and withdrawal terms, instead of a flat recommendation to sign an agreement. C-050's PASS wording could fail that memo.

Evidence:
- `flagged-doc-batch-g.docx.txt`: “recognize that Ms. Correa's interests may diverge from the company's”
- `flagged-doc-batch-f.eml.txt`: “how our respective clients can present a consistent narrative to the government”

Suggested fix: Pass any forward-looking recommendation on the common-interest gap: formalize it with protective terms, or reassess the coordination.

Related GPT-6 Sol findings: Arguable / rubric overconstraint: item 2.

<a id="o10"></a>
### O10. Reply timestamps precede the original emails in DOC_006 and DOC_010; C-005 reverses DOC_006's direction

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L56), [C-036](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L304)

In DOC_006, Nagarajan's reply header reads 03 Aug 2022 02:23 UTC (the evening of Aug 2 Eastern), yet Mullins's original is Aug 3 at 10:47 AM. In DOC_010, Pak-Morrison's reply (15 Feb 2024 03:42 UTC, i.e. Feb 14 Eastern) likewise precedes Greenwald's email. A log that lists the top message's author (Nagarajan) or the local date could be read as not matching C-005's 'from Sandra Mullins to Priya Nagarajan' or C-036's 'February 15'. Bates ranges probably let judges match anyway, so impact is low.

Evidence:
- `flagged-doc-batch-d.eml.txt`: “Date: Wed, 03 Aug 2022 02:23:00 -0000”
- `flagged-doc-batch-d.eml.txt`: “Sent: Wednesday, August 3, 2022 10:47 AM”
- `task.json C-005`: “dated August 3, 2022, from Sandra Mullins to Priya Nagarajan”

Suggested fix: Correct the header timestamps. Describe DOC_006 as a Mullins–Nagarajan chain and accept either party order and either adjacent date.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Confirmed defects: item 1 | confirmed | [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L144) (not_a_defect), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L152) (problematic), [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L160) (arguable) | mixed | Counted oldest-first, batch C's message 8 is Correa's Jul 22 note: 'Ray, Tom, can you weigh in on whether we can use this?' Message 11 is Mullins's Jul 26 reply: 'we'll steer clear of the Nakamura data.' Those passages ask for and relay the legal advice. C-017's PASS requires finding 'the remaining 12 messages' not privileged, so a broader partial redaction falls between its PASS and FAIL conditions. C-018's FAIL applies only to a whole-thread claim, so it is softer. C-016 only asks the memo to recognise that the thread is mixed, and a broader redaction still does that. |
| Confirmed defects: item 2 | confirmed | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L168) (not_a_defect), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L176) (arguable), [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L192) (not_a_defect) | mixed | The deck divides itself: slide 2 labels Part I (slides 3–8) 'Routine regulatory compliance posture'. The QC report codes it 'Work Product (Partial)'. So the split in C-019 and C-022 has support in the record. C-020's premise that slides 1–8 were 'predating any litigation threat' is false: the whole deck was created Dec 5, 2023, after the CID, and slide 8 is dated 'as of November 30, 2023'. The rubric's conclusion is defensible, but a reasoned claim over the whole deck, or over slides 1–2, could fail. That makes C-020 arguable, not confirmed. |
| Confirmed defects: item 3 | confirmed | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L320) | problematic | In DOC_011 (Oct 8, 2023), Correa says she does not know where to start and turns to Nagarajan. Metcalf first appears as her counsel on Nov 2, 2023 (batch F). Nothing in the record shows she had retained Kendrick Sable by Oct 8. C-038 builds that unsupported fact into its PASS condition. |
| Arguable / rubric overconstraint: item 1 | arguable | [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L48) (not_a_defect), [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L64) (problematic), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L112) (problematic) | mixed | Clawback Order IV.B.2(iv) requires the Clawback Notice to be 'accompanied by, or followed within five (5) business days by, a privilege log entry for each document'. The log is therefore served on AUSA Cooperman. C-006 and C-012 require log entries that admit crime-fraud and common-interest weaknesses, which contradicts C-004's own warning against conceding substance. A competent log ready for service, with the risks kept in the memo, fails both. C-004 is itself sound. |
| Arguable / rubric overconstraint: item 2 | arguable | [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L80) (not_a_defect), [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L96) (not_a_defect), [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L112) (problematic), [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L408) (not_a_defect), [C-050](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L416) (arguable) | mixed | The record contains no written agreement, and Nagarajan proposes only to 'formalize coordination' later. Saying the absence 'weakens' protection is a fair practical point, not a claim that a writing is legally required, so C-008, C-010 and C-049 are sound. C-012 fails for the served-log reason given above. C-050 requires recommending an agreement even though the record flags that Correa's interests may diverge. A memo that recommends reassessing the coordination instead could fail. |
| Arguable / rubric overconstraint: item 3 | arguable | [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L40) (not_a_defect), [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L88) (not_a_defect), [C-062](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L512) (problematic) | mixed | The 502(d) order makes a clawback cheap and preserves the government's right to challenge it, so asserting privilege over DOC_006 and DOC_008 while flagging the risks is the mainstream course. C-003 and C-009 are reasonable. Calling these documents 'clearly privileged' in C-062 overstates it. C-062's larger problem is that it names bare DOC_006/008/010 labels the judge cannot map; the QC report numbers the same documents #4, #6 and #8. |
| Arguable / rubric overconstraint: item 4 | arguable | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L216) (arguable), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L224) (arguable), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L232) (not_a_defect), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L240) (arguable), [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L248) (not_a_defect), [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L256) (not_a_defect), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L264) (arguable), [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L272) (arguable), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L280) (arguable) | mixed | The order protects disclosures 'regardless of whether such disclosure was inadvertent or intentional' and deems compliance with its procedures to satisfy 502(b). The criteria tied to 502(b) subsections can therefore fail a memo built around the order. C-027 (promptness) and C-029/C-030 (the order and its 10-business-day deadline) track the order itself and are sound. |
| Arguable / rubric overconstraint: item 5 | arguable | [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L120), [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L128), [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L136), [C-060](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-privileged-communications-from-production-set/task.json#L496) | arguable | Waiver through voluntary disclosure to an outside KOL is the mainstream view. But Viklund's memo said 'do not forward... without my prior approval'. That supports an argument that the employee had no authority to waive, and a protective clawback under the 502(d) order is a defensible choice. Four criteria all turn on this one judgment call. |

## Blind pass and what changed

Added one finding from Sol (O4, C-006/C-012). I checked the Clawback Order: IV.B.2(iv) requires a privilege log entry to accompany the Clawback Notice, so the log is served on the government. Criteria that require the log to admit weaknesses conflict with C-004 and with ordinary practice. Downgraded C-065 (blind O3) from problematic to arguable. Batch A shows Nagarajan 'evaluating whether it makes sense to bring in outside regulatory counsel', so logging DOC_003 is defensible and probably the majority course, and C-065 misgrades only reviewers who exclude it. Split C-018 out as arguable within the DOC_005 finding, because its FAIL condition covers only whole-thread claims. Added C-026 to the 502(b) finding. Dropped C-019 from the slides finding: the deck's own Part I/Part II split supports it. Only C-020's false chronology remains, as arguable, not confirmed as Sol has it. Dropped C-009 from the common-interest finding: asserting privilege under a 502(d) order is standard. Moved the 'clearly privileged' point into O1 (C-062). Narrowed the timestamp finding to C-005/C-036 and dropped C-001/C-059: C-059's 6-of-8 tolerance absorbs the date issue, and C-001 is description only. I considered Sol's points that C-008/C-010/C-049 are unsound and that C-016 is too restrictive, and rejected both. I also considered Sol's batch J packaging point and did not adopt it: the QC report describes the clean text and the tracked changes and comments as the rubric does, so C-041–C-043 remain judgeable.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-062, C-046): C-062 and C-046 rely on internal DOC_00X labels the solver never sees; the QC report's own numbering is off by two
- **O2** (problematic; C-038): C-038 assumes Correa had already retained Kendrick Sable by Oct 8, 2023; the record suggests she had not
- **O3** (problematic; C-065, C-023, C-024): C-065 assumes DOC_003 is on the privilege log, but the rubric leaves DOC_003's privilege status open
- **O4** (problematic; C-017, C-018): C-017/C-018 treat only messages 9–10 of DOC_005 as privileged, though other messages request or relay legal advice
- **O5** (arguable; C-025, C-028, C-031, C-032, C-033): The rubric requires an element-by-element FRE 502(b) analysis though the 502(d) order largely displaces 502(b)
- **O6** (arguable; C-013, C-014, C-015, C-060): Four criteria require treating DOC_004's privilege as waived, with no room for the authority-to-waive argument
- **O7** (arguable; C-020, C-019): C-020 describes slides 1–8 as 'predating any litigation threat', but the whole deck was prepared after the CID
- **O8** (arguable; C-050, C-062, C-009): C-050 requires recommending a formal common-interest agreement with Correa despite signs her interests diverge; C-062 calls DOC_008 'clearly privileged'
- **O9** (arguable; C-001, C-005, C-036, C-059): Reply timestamps come before the original emails in DOC_006 and DOC_010; criteria give DOC_006's direction backwards

## Coverage and limits

Blind pass: I read all 66 criteria, the instructions, the judge prompt and the solver system prompt. I read all 15 documents in full: flagged batches a–j, the NorthBridge QC report, the clawback order, the engagement letter, the Production 3 cover letter and the grand jury subpoena. I checked the text of FRE 502(b) and 502(d), and the Explanatory Note to 502(d), through a web fetch of the Cornell LII page. That fetch returned a model summary with quotes, not the raw page. A CourtListener search for Third Circuit common-interest authority (Teleglobe) returned nothing, so no case law is cited as verified. Limits: I did not independently research whether a vice president has authority to waive a corporate privilege, or the Third Circuit's dual-purpose work-product standard. Those points are flagged as judgment calls, not verified law.

Reconciliation: In the blind pass I read all 66 criteria and all 15 documents in full. In this pass I re-read the criteria and checked Sol's claims against batch A (the prospective-client emails), batch C (I re-derived the message order: Correa's Jul 22 'weigh in' is message 8, Viklund's advice message 10, Mullins's relay message 11), batch F (it contains no written common-interest agreement, only a proposal to formalize later), batch G (slide 2's Part I/II split, slide 8 dated as of Nov 30, 2023, created Dec 5, 2023), batch J (Viklund's comments appear as inline text), the QC report's review subset and timeline, and Clawback Order IV.B.1–3 (Discovery Date, the notice's contents, and the log entry that accompanies the notice). I read the FRE 502(d) Explanatory Note in the blind pass through a web summary. I did not verify case law in this session. Weintraub is cited unverified, and I did not re-read Teleglobe, Cendant or the Third Circuit crime-fraud authority that Sol cites. The advisor tool was rate-limited and not consulted.
