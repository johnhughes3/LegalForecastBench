# Claude Opus 5.5 audit: Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 52. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is thorough and mostly grounded in the record. The deadlines, custodians, platforms, migration loss, and January 2025 destruction all check out. Two of its planted 'inconsistencies' are defective because the notice's own wording resolves them. ¶24's 'Without limiting any other provision' removes the supposed HCP-scope contradiction that C-004 and C-005 require. ¶47's 'Notwithstanding' ¶12, read with ¶12's 'unless otherwise specified,' makes the 2017 extension deliberate, yet C-002 still requires asking DOJ to clarify it. Under the all-pass metric, any of these can zero out a careful answer. I rate C-001 and C-006 arguable because of their framing. Several other criteria are also arguable: they adopt record errors uncritically ('8 of 23', the '2019–2021' summary), import civil backup-tape doctrine into a grand jury setting, require a particular action-list format, overstate the 'related compounds' expansion, or undercount the ¶43 vendors.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | source_conflict | [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L46), [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L54) | C-004 and C-005 require a 'contradiction' and a narrow reading that ¶24's opening words ('Without limiting any other provision') rule out | revised |
| [O2](#o2) | arguable | source_conflict | [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L62) | C-006 frames the broad HCP scope as a default adopted only 'pending clarification', though the notice makes it mandatory | revised |
| [O3](#o3) | problematic | source_conflict | [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L30) | C-002 requires asking DOJ to clarify an express carve-out (¶47 'Notwithstanding' ¶12) | revised |
| [O4](#o4) | arguable | source_conflict | [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L22) | C-001 calls the ¶47 extension a 'discrepancy'/'inconsistency' rather than a deliberate exception | revised |
| [O5](#o5) | arguable | document_defect | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L110) | The IT memo's '8 of 23' does not reconcile with the notice: 2 of the 8 are not named custodians, and 5 of the 23 have no Ridgeline mailbox | revised |
| [O6](#o6) | arguable | legal_error | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L214) | C-025 makes a civil-discovery backup-tape proportionality analysis (Zubulake) mandatory for a grand jury preservation demand | blind |
| [O7](#o7) | arguable | document_defect | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L70) | The destruction email's summary says '2019–2021', but its own Category 2 runs through December 2022 | adopted_after_reading_sol |
| [O8](#o8) | arguable | unrequested_requirement | [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L358), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L366) | A headed, urgency-tiered action list is required even though the instruction asks only for an obligation extraction memo | blind |
| [O9](#o9) | arguable | document_defect | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L166), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L174), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L342) | The notice body and Exhibit B number the subject-matter areas differently, which the rubric does not account for | blind |
| [O10](#o10) | arguable | source_conflict | [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L134) | C-015 calls ¶31 a 'massive' expansion to 4 pipeline compounds and ignores its subject-matter limiting clause | blind |
| [O11](#o11) | arguable | source_conflict | [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L158), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L278), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L334) | The rubric lists 3 third-party vendors, but ¶43 names 4 (it omits SAP SE) | blind |

<a id="o1"></a>
### O1. C-004 and C-005 require a 'contradiction' and a narrow reading that ¶24's opening words ('Without limiting any other provision') rule out

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L46), [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L54)

C-004 says ¶24 'limits the scope' to the 5 Exhibit D HCPs and so contradicts ¶23. The notice says the opposite. ¶24 opens 'Without limiting any other provision of this Preservation Notice', and ¶23 expressly covers all HCPs 'regardless of whether such Healthcare Professionals are identified by name.' ¶24 adds affirmative collection duties for a subset of ¶23; it does not narrow it. A careful memo that says there is no conflict fails C-004. C-005 then requires comparing document volume between the two readings. A memo that correctly finds no narrow reading has nothing to compare. C-005 also rewards an invented magnitude ('potentially millions'): the record has no count of HCP communications (the closest figures are 14,800 speaker events and 22,400 patients). The rubric rewards misreading the text.

Evidence:
- `task.json C-004`: “Paragraph 24 limits the scope to communications with the 5 HCPs named in Exhibit D. FAIL if this contradiction is not identified.”
- `doj-preservation-notice.docx.txt`: “Without limiting any other provision of this Preservation Notice, Ridgeline shall preserve all communications with the HCPs identified in Exhibit D”
- `doj-preservation-notice.docx.txt`: “This preservation obligation applies to Communications with all Healthcare Professionals, regardless of whether such Healthcare Professionals are identified by name in this Preservation Notice or any exhibit hereto”
- `task.json C-005`: “PASS if the memo explains that the broader reading (all HCPs) could encompass potentially millions of additional documents compared to the narrow reading (5 named HCPs in Exhibit D).”

Suggested fix: Change C-004 to PASS if the memo explains how ¶23 (all HCPs) and ¶24 (the Exhibit D HCPs plus affirmative collection steps) relate and concludes that they are cumulative, with the broad scope governing. Change C-005 to PASS if the memo explains that the ¶23 scope is far broader than the Exhibit D names alone, with no specific magnitude required, or delete it.

Related GPT-6 Sol findings: B6-LH-2.

<a id="o2"></a>
### O2. C-006 frames the broad HCP scope as a default adopted only 'pending clarification', though the notice makes it mandatory

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L62)

C-006's PASS condition asks the memo to default to the broad interpretation 'pending clarification from the DOJ.' In fact ¶23 requires the broad scope outright, so no clarification is needed. The FAIL condition, though, asks only whether the memo recommends the broad scope and ties it to spoliation risk. A memo that says the broad scope is mandatory and that anything narrower risks spoliation would very likely pass. The risk is limited to judges who read 'pending clarification' as required, which is why this is arguable.

Evidence:
- `task.json C-006`: “PASS if the memo recommends defaulting to the broader interpretation (all HCPs regarding Velcara) pending clarification from the DOJ to avoid spoliation risk.”
- `doj-preservation-notice.docx.txt`: “Without limiting any other provision of this Preservation Notice”

Suggested fix: Change C-006 to PASS if the memo concludes that all HCP communications about Velcara must be preserved and connects that to spoliation risk, with DOJ clarification optional.

Related GPT-6 Sol findings: B6-LH-2.

<a id="o3"></a>
### O3. C-002 requires asking DOJ to clarify an express carve-out (¶47 'Notwithstanding' ¶12)

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L30)

¶12 defines the Relevant Period 'unless otherwise specified herein.' ¶47 begins 'Notwithstanding the Relevant Period defined in Paragraph 12' and deliberately extends financial records back to January 1, 2017, down to the dates and the steps required. The drafting is internally consistent. C-002 fails any memo that correctly treats ¶47 as binding and simply plans to preserve from 2017 without asking DOJ to clarify 'conflicting date ranges.' That is a correct answer. The real drafting defect in ¶47 is a different one: it cites 'Subject-Matter Area 7 (Categories 24–27)', but Exhibit B labels Categories 24–27 as Area 6. A clarification request aimed at that would be sensible, but it would not match C-002's stated subject.

Evidence:
- `doj-preservation-notice.docx.txt`: “the "Relevant Period" shall mean the period from January 1, 2019 through the date of this Notice (March 3, 2025), unless otherwise specified herein.”
- `doj-preservation-notice.docx.txt`: “Notwithstanding the Relevant Period defined in Paragraph 12 of this Notice, Ridgeline shall preserve all financial records ... from January 1, 2017 to the present date. This extended preservation period applies to the document categories identified in Subject-Matter Area 7 (Categories 24--27) of Exhibit B.”
- `task.json C-002`: “FAIL if no recommendation to seek clarification is made.”

Suggested fix: Make C-002 optional, or have it accept either a clarification request or a correct reading of ¶47 as an express override. Optionally, credit spotting the Area 7 / Area 6 cross-reference error.

Related GPT-6 Sol findings: B6-LH-1.

<a id="o4"></a>
### O4. C-001 calls the ¶47 extension a 'discrepancy'/'inconsistency' rather than a deliberate exception

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L22)

C-001's PASS condition lists ¶12 (2019), ¶47 (2017), and the two-year difference. A memo that reports all three while correctly calling ¶47 an express exception gives the judge every listed element and will usually pass. But the FAIL condition turns on whether 'this inconsistency' is identified, and a strict judge could fail a memo that says there is no inconsistency. The risk comes from framing rather than a certain misgrade.

Evidence:
- `task.json C-001`: “creating a two-year discrepancy. FAIL if this inconsistency between the two paragraphs is not identified.”
- `doj-preservation-notice.docx.txt`: “Notwithstanding the Relevant Period defined in Paragraph 12 of this Notice”

Suggested fix: Change C-001 to PASS if the memo identifies that ¶47 extends the financial-records preservation period to January 1, 2017, beyond ¶12's 2019 start date.

Related GPT-6 Sol findings: B6-LH-1.

<a id="o5"></a>
### O5. The IT memo's '8 of 23' does not reconcile with the notice: 2 of the 8 are not named custodians, and 5 of the 23 have no Ridgeline mailbox

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L110)

The IT memo lists 8 affected custodians. Two of them are 'Jennifer Calloway, Regional Sales Manager — Mid-Atlantic' and 'David Yun, Regional Sales Manager — West Coast.' Neither appears in Exhibit C, which lists Tonya M. Bradshaw for Mid-Atlantic and has no West Coast region, or anywhere else in the record. Only 6 of the 8 match. The denominator is also off: under ¶15, 5 of the 23 custodians are external HCPs, yet the IT memo says post-migration email for 'all 23 named custodians' is intact in M365. A careful memo would report that 6 affected custodians are confirmed and 2 more need checking. C-012 rewards repeating '8 of 23' uncritically and could fail the more accurate memo.

Evidence:
- `it-migration-memo.eml.txt`: “7. Jennifer Calloway, Regional Sales Manager — Mid-Atlantic 8. David Yun, Regional Sales Manager — West Coast”
- `doj-preservation-notice.docx.txt`: “1              Tonya M. Bradshaw       Regional Sales Manager, Mid-Atlantic Region”
- `it-migration-memo.eml.txt`: “Post-migration emails (October 2021 onward) for all 23 named custodians are intact in the Microsoft 365 environment”
- `task.json C-012`: “FAIL if the number of affected custodians (8 of 23) is not identified.”

Suggested fix: Change C-012 to PASS if the memo reports the IT memo's figure of 8 affected custodians OR identifies the mismatch with the notice's custodian lists, and credit flagging the discrepancy.

<a id="o6"></a>
### O6. C-025 makes a civil-discovery backup-tape proportionality analysis (Zubulake) mandatory for a grand jury preservation demand

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L214)

C-025 fails any memo that lacks a proportionality analysis referring to the principle that backup tapes are disfavored when the same data is accessible elsewhere. That principle comes from civil discovery (Zubulake IV; FRCP 26). Here the demand comes from a criminal investigation backed by a § 1519 warning. Competent counsel may reasonably advise full compliance with ¶41 and a negotiated narrowing with the AUSA without relying on civil doctrine. The facts also cut against the principle. Zubulake itself makes an exception for key players' data that is not otherwise available, and here the migration loss and the January 2025 deletions mean the data may exist nowhere else. The criterion demands a particular framing rather than sound analysis.

Evidence:
- `task.json C-025`: “including reference to the general principle (or case law such as Zubulake v. UBS Warburg) that preservation of backup tapes is disfavored when the same data exists in accessible form. FAIL if no proportionality analysis of the backup tape preservation obligation is provided.”
- `doj-preservation-notice.docx.txt`: “Ridgeline's current ninety (90) day backup tape rotation and recycling cycle must be immediately suspended in its entirety.”

Authorities (✓ = primary text checked in the auditing session):
- Zubulake v. UBS Warburg LLC, 220 F.R.D. 212, 218 (S.D.N.Y. 2003) (✓): As a general rule, a litigation hold does not apply to inaccessible disaster-recovery backup tapes, but there is an exception for identifiable tapes storing key players' documents (civil discovery context).

Suggested fix: Change C-025 to PASS if the memo assesses the burden or scope of the ¶41 backup-tape obligation, whether that means full compliance or negotiating with the AUSA, with a reference to civil proportionality principles optional.

Related GPT-6 Sol findings: B6-LH-4.

<a id="o7"></a>
### O7. The destruction email's summary says '2019–2021', but its own Category 2 runs through December 2022

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L70)

The email summarizes 4.2M records 'spanning the date range 2019–2021.' But Category 2 (1.4M Salesforce and field records, 2-year retention) covers 'January 2019 through December 2022.' C-007 adopts the summary's date range. A memo that correctly reports 2019–2022, or notes the discrepancy, is more accurate. Because C-007's FAIL condition is only 'destruction event is not flagged', such a memo almost certainly still passes, so the misgrade risk is low.

Evidence:
- `records-destruction-confirmation.eml.txt`: “totaling approximately 4.2 million records spanning the date range 2019–2021”
- `records-destruction-confirmation.eml.txt`: “Approximately 1.4 million records from January 2019 through December 2022”
- `task.json C-007`: “identifies the January 15, 2025 scheduled destruction of approximately 4.2 million records from the 2019–2021 period as a critical issue”

Suggested fix: Change C-007 to accept 2019–2022 (or '2019–2021 per the summary') and credit noting the discrepancy.

Related GPT-6 Sol findings: B6-LH-3.

<a id="o8"></a>
### O8. A headed, urgency-tiered action list is required even though the instruction asks only for an obligation extraction memo

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L358), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L366)

The instruction asks only for 'a detailed obligation extraction memo.' A deadline chart is implicit in extracting obligations. A separately headed action-item section grouped by urgency tier is a formatting choice, not a standard part of an extraction memo. C-044 then requires that the three deadlines appear in chronological order in that action list specifically. A memo with a chronological deadline table plus action items arranged by workstream could fail both criteria while conveying the same content.

Evidence:
- `task.json instructions`: “prepare a detailed obligation extraction memo. Output: `obligation-extraction-memo.docx`.”
- `task.json C-043`: “FAIL if no such section exists or if action items are listed without any ordering by deadline or urgency.”

Suggested fix: Change C-043 and C-044 to PASS if the memo presents the key deadlines in chronological order anywhere (a deadline table, timeline, or action list).

<a id="o9"></a>
### O9. The notice body and Exhibit B number the subject-matter areas differently, which the rubric does not account for

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L166), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L174), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L342)

The body treats HCP Communications as Area 4 (¶¶23–24) and numbers Patient Assistance as Area 5 and Compliance as Area 6. Exhibit B has no HCP Communications area and shifts everything up one (Patient Assistance is Area 4, Financial is Area 6), while ¶47 cites Financial as 'Area 7.' This is the likely source of the category-count gap. C-020 allows for that reading, and C-041 follows Exhibit B's numbering, so the misgrade risk is small. But a memo that catalogues areas using the body's numbering could confuse a judge applying C-041.

Evidence:
- `doj-preservation-notice.docx.txt`: “**26. Subject-Matter Area 6: Compliance Monitoring and Audit Reports (Categories 20--23).**”
- `doj-preservation-notice.docx.txt`: “**Subject-Matter Area 4: Patient Assistance Fund Operations**”

Suggested fix: State in C-041 that either numbering scheme is acceptable, and credit memos that flag the numbering mismatch and the uncategorized HCP Communications area.

<a id="o10"></a>
### O10. C-015 calls ¶31 a 'massive' expansion to 4 pipeline compounds and ignores its subject-matter limiting clause

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L134)

The org chart does confirm 4 pipeline compounds. But ¶31 reaches 'related compounds' only 'to the extent such documents ... also relate to the subject matter of this investigation' (the KOL Program, RPAF, and Velcara marketing). A memo could reasonably conclude that the incremental scope is modest for unmarketed preclinical and clinical compounds, while still preserving conservatively. If the judge requires the memo to call ¶31 a 'potentially massive' expansion, it could fail that memo.

Evidence:
- `doj-preservation-notice.docx.txt`: “relating to ridgenostat and all related compounds developed, tested, manufactured, or marketed by Ridgeline, to the extent such documents, records, materials, communications, or ESI also relate to the subject matter of this investigation.”
- `ridgeline-org-chart.docx.txt`: “Ridgeline maintains a pipeline of 4 additional oncology compounds in various stages of preclinical and clinical development.”

Suggested fix: Change C-015 to PASS if the memo identifies that 'related compounds' is ambiguous and could reach the pipeline compounds, whether or not it calls the expansion 'massive'.

<a id="o11"></a>
### O11. The rubric lists 3 third-party vendors, but ¶43 names 4 (it omits SAP SE)

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L158), [C-033](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L278), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L334)

¶43 requires preservation notices by March 13 to four named vendors: Veeva Systems, SAP SE, Concur, and IntegriCall. C-040 is titled 'three specific third-party vendors,' and C-018 and C-033 follow suit. A memo listing all four still passes, so correct answers are not failed. But the rubric rewards an incomplete extraction, because a memo omitting SAP passes.

Evidence:
- `doj-preservation-notice.docx.txt`: “(a) Veeva Systems (Veeva CRM and Veeva Vault); (b) SAP SE (SAP ERP); (c) Concur Technologies (Concur expense management); and (d) IntegriCall Services (compliance hotline).”
- `task.json C-040`: “identifies all three third-party vendors/platforms requiring preservation notices: Veeva CRM, Concur expense system, and IntegriCall Services”

Suggested fix: Change C-040 (and the vendor lists in C-018 and C-033) to require the four ¶43 vendors, including SAP SE, and optionally credit identifying Sentinel Records Management under ¶¶41–42.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| B6-LH-1 | confirmed | [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L22) (arguable), [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L30) (problematic) | mixed | ¶12 defines the period 'unless otherwise specified herein.' ¶47 opens 'Notwithstanding the Relevant Period defined in Paragraph 12' and extends financial records to 2017. That is an express carve-out, not a conflict. C-002 fails any memo that correctly treats ¶47 as binding and asks DOJ nothing, so it is problematic. C-001 is only arguable: a memo that names both paragraphs and the two-year extension gives the judge everything the PASS text lists, and the risk is limited to the 'inconsistency' framing. |
| B6-LH-2 | confirmed | [C-004](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L46) (problematic), [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L54) (problematic), [C-006](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L62) (arguable) | mixed | ¶23 covers all HCPs 'regardless of whether ... identified by name.' ¶24 opens 'Without limiting any other provision' and adds duties for the Exhibit D HCPs. No narrow reading exists. C-004 requires the memo to identify a false contradiction. C-005 requires comparing volume against a nonexistent narrow reading and invents 'millions.' C-006's FAIL condition asks only for a broad default tied to spoliation, so a memo calling the broad scope mandatory very likely passes; it is arguable. |
| B6-LH-3 | confirmed | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L70) | arguable | This checks out. The destruction email's summary says 4.2M records 'spanning the date range 2019–2021,' but Category 2 (1.4M sales records) runs 'January 2019 through December 2022.' Its 2-year retention period makes the 2022 dates internally plausible, so this is a mislabeled summary. C-007's FAIL condition is only 'destruction event is not flagged,' so a memo that says 2019–2022 almost certainly passes. The misgrade risk is low; this is a document defect, not a confident misgrade. |
| B6-LH-4 | arguable | [C-021](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L182) (not_a_defect), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L214) (arguable) | mixed | C-021 lists alternatives (Fourth Amendment, state privacy law, consent, or court order) and fails only a memo that raises no privacy concern. A private employer imaging devices at a DOJ demand also gives a colorable government-agent theory, so C-021 is not a defect. C-025 is mandatory. It requires a proportionality analysis and invokes civil-discovery backup-tape doctrine (Zubulake) in a grand-jury/§1519 setting, where tapes may be the only copy. It is arguable. |

## Blind pass and what changed

I split blind O1. C-004 and C-005 stay problematic. C-006 drops to arguable because its FAIL condition asks only for a broad default tied to spoliation, and it is now O2. I folded blind O4 ('millions' is unsupported) into the C-005 finding and retired it, so C-005 carries one status. I split blind O2: C-002 is problematic (O3) and C-001 arguable (O4). I also dropped C-003 there, since Sol and I both consider it valid. I adopted Sol's B6-LH-3 (C-007) as arguable, O7. I checked Category 2's retention period: it is 2 years, so the December 2022 dates are internally plausible and the problem is only a mislabeled summary. I dropped blind O5 (C-026). The IT memo flags the fragility of the powered-off servers and says it will investigate whether the legacy Exchange tapes still exist, which supports the rubric's link between backup tapes and the migration loss, and I could not identify a correct memo that would fail. I strengthened blind O3 (C-012): 5 of the 23 custodians are external HCPs with no Ridgeline mailbox. I found C-021 (Sol B6-LH-4) not to be a defect.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-004, C-005, C-006): The 'contradiction' in the HCP-communications scope misreads ¶24: that paragraph opens 'Without limiting any other provision'
- **O2** (problematic; C-001, C-002, C-003): The 2017 vs 2019 dates are a deliberate carve-out, not a conflict, yet C-002 requires asking DOJ to clarify
- **O3** (arguable; C-012): Two of the IT memo's '8 affected custodians' are not named custodians in the notice
- **O4** (arguable; C-005, C-004): The 'millions of additional documents' and 'thousands of HCPs' figures have no support in the record
- **O5** (arguable; C-026): C-026 ties backup tapes to the migration loss, but the record points to the servers for that loss and to the tapes for the January 2025 deletions
- **O6** (arguable; C-025): C-025 makes a civil-discovery proportionality analysis (Zubulake) mandatory for a grand jury preservation demand
- **O7** (arguable; C-043, C-044): A headed, urgency-tiered action list is required even though the instruction asks only for an obligation extraction memo
- **O8** (arguable; C-019, C-020, C-041): The notice body and Exhibit B number the subject-matter areas differently, which the rubric does not account for
- **O9** (arguable; C-015): C-015 calls ¶31 a 'massive' expansion to 4 pipeline compounds and ignores its limiting clause
- **O10** (arguable; C-018, C-033, C-040): The rubric lists 3 third-party vendors, but ¶43 names 4 (it omits SAP SE)

## Coverage and limits

Blind pass: I read all 52 criteria and the one-sentence instruction. I read four documents in full: the DOJ preservation notice (cover letter, ¶¶1–52, Exhibits A–D), the IT migration memo, the records-destruction confirmation, and the org chart. For the retention policy (RDG-LGL-007) I read the retention schedule (§3.2), §3.3, and the summary table, and searched the rest for backup tapes, litigation holds, the trigger for the duty to preserve, the BYOD policy, and the section numbers the destruction email cites. I did not read the system prompt or judge prompt beyond what the task summary says about them. On the law, I verified the Zubulake IV backup-tape passage (220 F.R.D. 212) on CourtListener. I did not independently research the Fourth Amendment/state-action point or 18 U.S.C. § 1519 case law. Where I discuss them, I rely on general knowledge and mark them unverified.

Reconciliation: I read all 52 criteria and the instruction. Across the two passes, I read the full DOJ notice, the IT migration memo, the destruction confirmation, and the org chart. For the retention policy I read the relevant sections and searched the rest. In this pass I re-checked ¶¶12, 13–16, 23–24, 31, 41, 43, and 47, Exhibits C and D, the IT memo's custodian list, and the destruction email's categories, including Category 2's 2-year retention period. I read all of Sol's report files. I verified Zubulake IV (220 F.R.D. 212) on CourtListener in the blind pass. I did not research Fourth Amendment private-search or agent doctrine or § 1519 case law; my C-021 verdict relies on the criterion's lenient FAIL condition, not on that research.
