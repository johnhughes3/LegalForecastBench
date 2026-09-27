# Claude Opus 5.5 audit: Draft Litigation Hold Notice for New Product Liability Class Action (Medical Device)

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 61. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric's facts match the record: case name and number, court, GC, the January 1, 2017 start date, the June 16/20/23/30 and July 15 deadlines, custodians, systems, Ashford, and Corestone. Its preservation law is reasonable. The clear defect is C-045. It requires ordering actions by event date, and outside counsel's own urgency-ordered Section VI and the XLSX Urgency Matrix would both fail it, so it can zero out competent memos under all-pass scoring. The lesser risks are structural or formal. Several criteria require system directives to appear in the notice rather than the memo (C-020, C-022, C-026, C-027, C-056, C-059). C-061 requires a June 2 date the instructions never give. C-053 has a PASS/FAIL gap, and C-002 imposes an addressee requirement. Some supplied documents conflict (tapes, Petrosian's imaging deadline, the Q3 2022 purge claim), but the criteria mostly tolerate this. I agree with Sol on C-061, rate C-045 higher than Sol does, and do not consider C-032 a defect.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | unrequested_requirement | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L386) | C-045 requires ordering by event date, which fails memos that follow the record's own urgency or action-deadline order | blind |
| [O2](#o2) | arguable | internal_inconsistency | [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L172), [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L189), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L224), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L232), [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L474), [C-059](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L498) | System-level IT directives must appear in the custodian hold notice, while related criteria accept either document | blind |
| [O3](#o3) | arguable | unrequested_requirement | [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L514) | C-061 requires a June 2, 2025 date that the instructions never give, and fails undated drafts | blind |
| [O4](#o4) | arguable | ambiguous_or_unjudgeable | [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L450) | C-053 has a gap: a notice that omits the service date fits neither PASS nor FAIL | blind |
| [O5](#o5) | arguable | unrequested_requirement | [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L28) | C-002 requires the memo to be addressed to or for the General Counsel, a recipient the instructions never name | blind |
| [O6](#o6) | arguable | document_defect | [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L189), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L215), [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L301) | Supplied documents conflict on backup tapes, Petrosian's imaging deadline, and what the June 30 purge reaches | blind |

<a id="o1"></a>
### O1. C-045 requires ordering by event date, which fails memos that follow the record's own urgency or action-deadline order

**Status:** problematic · **Category:** unrequested_requirement · **Criteria:** [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L386)

C-045 fails a memo that lists the June 30 email purge before the June 20 Petrosian departure or the June 23 device wipe. The instructions ask for no ordering. The record orders these items differently. Outside counsel's Section VI, expressly 'in order of urgency', lists SAP, email purge, mobile, Petrosian, so counsel's own memo would fail C-045. The XLSX Urgency Matrix orders by action deadline, and there disabling the purge (June 4) comes before scheduling Petrosian's imaging (June 6) and halting the device refresh (June 6). A competent memo that puts a same-week admin task (purge suspension) first, or groups actions by responsible team while stating every deadline, is logical and follows the record. It would still be graded 'clearly illogical'. Under all-pass scoring, that zeroes the run.

Evidence:
- `C-045`: “SAP migration (June 16) and Petrosian departure (June 20) are both listed before mobile device wipe (June 23) and email purge (June 30)”
- `outside-counsel-case-assessment.docx.txt`: “We have identified four time-critical preservation risks that require action within the next 30 days. Each is discussed below in order of urgency.”
- `outside-counsel-case-assessment.docx.txt`: “## VI.B. Email Auto-Purge (CRITICAL --- Deadline: June 30, 2025)”
- `custodian-data-inventory.xlsx.txt`: “C3='Disable email auto-purge rule in Microsoft 365 Exchange Online Admin Center to prevent destruction of emails older than 3 years' \| D3='June 4, 2025'”

Suggested fix: PASS if the memo gives each time-sensitive action its correct deadline and presents the actions in any reasoned order (event date, action deadline, urgency, or owner). FAIL only if deadlines are missing or misstated.

Related GPT-6 Sol findings: arguable/0.

<a id="o2"></a>
### O2. System-level IT directives must appear in the custodian hold notice, while related criteria accept either document

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L172), [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L189), [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L224), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L232), [C-056](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L474), [C-059](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L498)

The instructions ask for a hold notice plus an 'accompanying preservation action memo'. A common, competent split puts custodian obligations in the notice and system directives (halt the SAP migration, disable the purge job, stop the MDM wipe) in the action memo or an IT directive. It would also send the 85 field reps a separate abbreviated notice, as outside counsel recommends. C-020, C-022, C-026, C-027, C-056 and C-059 are limited to the notice, yet C-021, C-023, C-024, C-025 and C-035 on the same issues accept either document. A solver who puts the SAP carve-out and purge suspension only in the memo fails several criteria despite doing the work. It is arguable because outside counsel and VNT-POL-007 §(d) say the notice should list the specific systems and go to Tilden as ESI coordinator.

Evidence:
- `C-020`: “PASS if the notice specifically addresses the SAP ECC 6.0 to S/4HANA migration”
- `C-021`: “PASS if either document mentions the July 15, 2025 legacy SAP decommissioning deadline”
- `outside-counsel-case-assessment.docx.txt`: “All 85 field sales representatives should receive a separate, abbreviated hold notice tailored to their specific preservation obligations”

Suggested fix: Let C-020, C-022, C-026, C-027, C-056 and C-059 pass on either deliverable, or accept a notice that cross-references IT directives set out in the memo.

<a id="o3"></a>
### O3. C-061 requires a June 2, 2025 date that the instructions never give, and fails undated drafts

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L514)

The instructions say only 'just served on us' and give no current date. June 2 can be inferred from outside counsel's recommended issuance deadline and the Urgency Matrix baseline. But a competent drafter could leave a '[Date]' placeholder for the GC to fill at issuance. Or they could date the notice from the latest document dates (May 29–31), since the hold issues 'immediately'. C-061 fails both, and a date is a formality rather than substance.

Evidence:
- `task.json instructions`: “Draft a litigation hold notice and accompanying preservation action memo based on the attached materials for the class action just served on us.”
- `C-061`: “FAIL if the notice is dated significantly differently or not dated at all.”
- `outside-counsel-case-assessment.docx.txt`: “issued by General Counsel Priya Chandrasekaran no later than **June 2, 2025**”

Suggested fix: PASS if the notice is dated between May 28 and early June 2025 or carries a date placeholder for issuance. Or drop the criterion.

Related GPT-6 Sol findings: arguable/2.

<a id="o4"></a>
### O4. C-053 has a gap: a notice that omits the service date fits neither PASS nor FAIL

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-053](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L450)

C-053 passes if the notice 'states or implies' service on May 28, 2025, and fails only if a 'materially different service date is stated'. A notice that identifies the case but does not mention service, or says 'recently served', falls between the two. Judges may split on whether that implies May 28. The instructions do not require a service date.

Evidence:
- `C-053`: “PASS if the notice states or implies the complaint was served on May 28, 2025. FAIL if a materially different service date is stated.”

Suggested fix: Make it one-sided: PASS unless an incorrect service date is stated.

<a id="o5"></a>
### O5. C-002 requires the memo to be addressed to or for the General Counsel, a recipient the instructions never name

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L28)

The instructions ask only for an 'accompanying preservation action memo'. Because the hold issues from the GC, a solver may reasonably write the action memo from the GC to the action owners (IT, HR, Manufacturing, Sales) or to the executive team. A strict judge could treat that as 'no such memo'. Addressing it to the GC is natural, which keeps this arguable, but the recipient is a judgment call, not a standard part of the document type.

Evidence:
- `C-002`: “PASS if the agent produces a separate cover memo / preservation action memo addressed to or for the General Counsel.”

Suggested fix: PASS if a separate preservation action memo is produced, whoever it is addressed to.

<a id="o6"></a>
### O6. Supplied documents conflict on backup tapes, Petrosian's imaging deadline, and what the June 30 purge reaches

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-022](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L189), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L215), [C-035](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L301)

Several facts differ across the documents. (1) Tapes: the IT memo says 90-day rotation, oldest tape early March 2025. The IT systems summary lists annual tapes back to January 2019 kept 7 years, while VNT-POL-007 says annual tapes are kept 3 years. (2) Petrosian: counsel says image by June 13; the XLSX says June 18. (3) Counsel and the XLSX say the June 30 purge destroys the Q3 2022 metallurgical-analysis emails, but July–September 2022 emails postdate the June 30, 2022 cutoff. (4) Minor: Ashford is described as making femoral components in some documents and tibial tray components in the XLSX, and Teams retention is 3 years in one document and 1 year in another. The criteria mostly tolerate these conflicts. But solvers must choose a version, and a judge may treat a careful answer's choice, or its correction of the Q3 2022 error, as a misstatement.

Evidence:
- `it-migration-memo.eml.txt`: “The current oldest available backup tape dates from approximately early March 2025.”
- `it-systems-summary.docx.txt`: “The current tape inventory includes annual archive tapes dating back to January 2019”
- `retention-policy-vnt-pol-007.docx.txt`: “Annual backup tapes that have reached the end of their 3-year retention period are destroyed”
- `custodian-data-inventory.xlsx.txt`: “Emergency imaging deadline: June 18, 2025.”

Suggested fix: Reconcile the documents, or add grader notes that either version of a conflicting fact is acceptable and that flagging the Q3 2022 timing error is correct.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| arguable/0 | arguable | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L386) | problematic | Stronger than arguable. Outside counsel's own Section VI, which it says is 'in order of urgency', runs SAP, then the June 30 email purge, then mobile, then Petrosian. Under C-045 that order puts a later deadline first. The XLSX Urgency Matrix orders by action deadline: purge disabled June 4, SAP halt June 4, Petrosian imaging scheduled June 6, device halt June 6. A memo that follows either source-endorsed order fails C-045 as 'clearly illogical', and the instructions never ask for any ordering. |
| arguable/1 | arguable | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L275) | not_a_defect | Outside counsel VI.C explicitly recommends tiering: blanket imaging of all 85 is 'neither required nor proportionate'. The XLSX has tiered actions (ACT-011, ACT-016). The PASS condition is broad ('or by otherwise discussing proportional preservation'). FAIL applies only if the output treats all 85 identically with no proportionality discussion, so a justified uniform plan that discusses proportionality already passes. Sol's concern is already accommodated. |
| arguable/2 | arguable | [C-061](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L514) | arguable | June 2, 2025 can be inferred: it is counsel's recommended issuance date (Section IX and the timeline) and the Urgency Matrix baseline. But the instructions give no date. A draft left with a '[Date]' placeholder for the GC to sign, or dated the day of drafting, is competent and fails C-061's 'not dated at all' clause. |

## Blind pass and what changed

I dropped blind O4 (C-036, backup-tape accessibility). The record makes accessibility central to the tape question. Outside counsel Section VIII and VNT-POL-007 §6.2 discuss 'reasonably accessible' at length. Counsel also says 'Do not restore backup tapes at this time'. C-036's PASS includes 'recommends preserving backup tapes while deferring restoration decisions', so a competent memo that follows the record passes easily. Counsel misstates Rule 26(b)(2)(B) as excusing preservation. But C-036 does not require that misstatement, and C-035 fails any memo that lets tapes be destroyed, so no misgrading remains. For O1 (C-045) I confirmed that counsel's own Section VI ordering would fail the criterion, which strengthens 'problematic' over Sol's 'arguable'. I rejected Sol's C-032 finding: counsel explicitly recommends tiering, and the criterion's broad PASS clause already accepts a uniform plan if it discusses proportionality. I narrowed O6 (document defects) and added the Petrosian June 13/June 18 conflict and the 7-year versus 3-year annual tape conflict. I renumbered the findings.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-045): C-045 requires ordering by event date, which fails memos that follow the record's own order by action deadline or urgency
- **O2** (arguable; C-020, C-022, C-026, C-027, C-056, C-059): System-level IT directives must appear in the custodian hold notice, while related criteria accept either document
- **O3** (arguable; C-061): C-061 requires a June 2, 2025 date that the instructions never give, and fails undated drafts
- **O4** (arguable; C-036): C-036 requires a discussion of backup-tape accessibility, and the record's premise that such sources need not be preserved is wrong law
- **O5** (arguable; C-053): C-053 has a gap: a notice that omits the service date fits neither PASS nor FAIL
- **O6** (arguable; C-002): C-002 requires the memo to be addressed to or for the General Counsel, a recipient the instructions never name
- **O7** (arguable; C-022, C-035, C-028, C-032): Supplied documents conflict on tapes, Teams retention, Ashford's components, device batches and purge reach

## Coverage and limits

Blind pass: I read all 61 criteria and the instructions. I read these documents in full: the complaint, the outside counsel assessment, the IT migration memo, the Petrosian HR email and the IT systems summary. For the custodian inventory XLSX, I read the Custodians sheet and the Urgency Matrix in full, and I checked the Data Sources sheet with targeted reads and greps (tapes, dates, Ashford, Teams retention). I did not fully read the retention policy VNT-POL-007. I relied on the other documents' descriptions of its purge terms and did not check it independently. I verified the text of FRCP 26(b)(2)(B) on LII. The 2006 advisory committee note on preservation did not appear on the fetched page, so I did not verify it. I did not open the judge prompt or the system prompt beyond what the task description says about them. I did no case-law verification on the Rule 34 'control' standard because the criterion (C-029) is permissive enough that it does not turn on that standard.

Reconciliation: I read all 61 criteria and the instructions, and Sol's index entry and audit report (markdown/JSON). On this pass I re-checked the record for each disputed criterion. That covered outside counsel Sections IV, VI (full ordering and the VI.C tiers), VIII (backup tapes) and the IX timeline; the XLSX Urgency Matrix in full; and the tape passages in the IT memo, IT systems summary and VNT-POL-007 §6. In the blind pass I read the complaint, outside counsel memo, IT migration memo, Petrosian email and IT systems summary in full, plus the XLSX Custodians and Urgency sheets. I verified FRCP 26(b)(2)(B) text on LII in the blind pass. The 2006 committee note was not verified, and the finding that relied on it has been dropped. I did no case-law verification because no remaining finding turns on contested case law.
