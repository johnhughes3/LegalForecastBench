# Claude Opus 5.5 audit: Extract Key Admissions from Deposition Transcript — Admission Summary Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 46. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is broadly sound. Its core factual anchors match the record: the dates, 3,847 files / 2.3 GB, 47 patent accesses against a ~3/month baseline, 142 miles against radii of 150 and 100 miles, and the Aug. 22 C&D letter against the Sept. 1 reset. I found nothing I would call problematic. The defects are arguable. Two factual premises are overstated: June 22 as the 'first contact', and an 'initial denial' of the Blue Book email when Yoon only claimed no recollection. C-009 mislabels an exhibit and has a checklist-style PASS clause. Two requirements go beyond an admission summary: the enforceability analysis with Michigan law (C-027/C-028), and a mandatory table (C-032). The table is the likeliest to fail a competent narrative memo under all-pass scoring. Two of Sol's five findings (C-017, C-014) are not defects on the full record.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | arguable | source_conflict | [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L19), [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L35) | Rubric treats the June 22 dinner as Yoon's first contact with PAG; Vol. II shows first contact was ~June 8-9 | blind |
| [O2](#o2) | arguable | source_conflict | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L67), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L75) | Criteria say Yoon 'initially denied' the Blue Book email; he claimed no recollection and expressly refused to deny | blind |
| [O3](#o3) | arguable | ambiguous_or_unjudgeable | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L83) | C-009 mislabels Exhibit 15 as the forensic report and lists four report features that could be read as a checklist | blind |
| [O4](#o4) | arguable | unrequested_requirement | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L227), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L235) | Non-compete enforceability analysis and Michigan law citation go beyond an admission summary memo | blind |
| [O5](#o5) | arguable | unrequested_requirement | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L267) | Mandatory summary table is a format requirement the instructions never state | blind |
| [O6](#o6) | arguable | document_defect | [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L27), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L323), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L227), [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L347) | Record misquotes Interrogatory No. 4 and changes Section 7(a)'s 'or' to 'and'; both bear on criteria premises | blind |

<a id="o1"></a>
### O1. Rubric treats the June 22 dinner as Yoon's first contact with PAG; Vol. II shows first contact was ~June 8-9

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L19), [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L35)

C-001's title says Yoon's 'first contact with PAG was June 22, 2024 dinner'. C-003 requires noting that Yoon was CTO 'when he first contacted PAG/Adwell' at the dinner. Judges see titles. In Vol. II, Yoon accepts that his first communication with Adwell was around June 8-9 at the Michigan Automation Council event, and Adwell's email confirms that meeting. The operative tests (the dinner occurred, and Yoon was still CTO) are met by an accurate memo, so misgrading is unlikely. But the rubric builds in a premise the record contradicts: a memo that correctly calls the dinner the second contact sits awkwardly with the title, and a memo that repeats the error is rewarded.

Evidence:
- `task.json C-001`: “ISSUE_001: Identifies Yoon's first contact with PAG was June 22, 2024 dinner”
- `task.json C-003`: “meaning Yoon was still employed as CTO of CMS when he first contacted PAG/Adwell”
- `yoon-deposition-vol2.docx.txt`: “So your first communication with 7 Mr. Adwell was actually around June 8 or 9, 2024, at 8 the Michigan Automation Council event? 9 A. I suppose so.”

Suggested fix: Retitle C-001 to call the June 22 dinner an admitted pre-resignation contact. In C-003, refer to 'his pre-resignation contacts with Adwell (the ~June 8-9 event and the June 22 dinner)'.

Related GPT-6 Sol findings: F2.

<a id="o2"></a>
### O2. Criteria say Yoon 'initially denied' the Blue Book email; he claimed no recollection and expressly refused to deny

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L67), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L75)

C-007's PASS clause, and C-008's title and PASS clause, describe an initial denial followed by a qualified admission. In the transcript, Yoon said he did not recall the email. Asked whether he was denying it, he said 'I'm saying I don't recall it.' An accurate memo describes a shift from no recollection to 'may have ... inadvertently' forwarded it. That framing matters for impeachment, because a no-recall answer is harder to prove false than a denial. C-008's 'and/or' route through the 'inadvertently' explanation protects most accurate answers, and C-007's FAIL clause is broad. A literal judge could still fault a memo that correctly says there was no denial, and the rubric rewards the mischaracterization.

Evidence:
- `task.json C-007`: “PASS if the memo identifies that Yoon, after initially denying it, admitted (or conceded he 'may have')”
- `task.json C-008`: “PASS if the memo notes that Yoon initially denied emailing the Blue Book and later changed his testimony to a qualified admission”
- `yoon-deposition-vol1.docx.txt`: “Q. Are you denying that you sent this email?  A. I\'m saying I don\'t recall it.”

Suggested fix: In C-007 and C-008, replace 'initially denying/denied' with 'initially claiming no recollection of'.

Related GPT-6 Sol findings: F1.

<a id="o3"></a>
### O3. C-009 mislabels Exhibit 15 as the forensic report and lists four report features that could be read as a checklist

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L83)

C-009 calls Exhibit 15 'the forensic examination report'. Exhibit 15 is actually the CMS email server log; the Ridgepoint report is Exhibit 14. The PASS clause requires the report to be shown 'showing the email header, attachment metadata, sender/recipient addresses, and attachment filename'. The FAIL clause is generic. A judge who reads the PASS clause as a checklist could fail a memo that relies on Ridgepoint Finding 2 without listing all four features, which leaves a gap between PASS and FAIL. The criterion also leaves out the most probative point in the report: the email was a new standalone message, not a forward, which rebuts Yoon's 'inadvertently forwarded' account.

Evidence:
- `task.json C-009`: “against the forensic examination report (Exhibit 15 or the Ridgepoint Digital Forensics report) showing the email header, attachment metadata, sender/recipient addresses, and attachment filename”
- `yoon-deposition-vol1.docx.txt`: “Exhibit 15              CMS Email Server Log showing email from dyoon@corbinmachining.com to derek.yoon.personal@gmail.com”
- `forensic-report.docx.txt`: “The email was composed as a new standalone message; it was not a forward of a prior email chain or a reply to an existing message thread.”

Suggested fix: PASS if the memo cross-references the Blue Book testimony against the forensic or documentary evidence (the Ridgepoint report, Ex. 14, and/or the CMS server log, Ex. 15) confirming the Aug. 12 email and attachment. Optionally credit noting the standalone-message finding.

<a id="o4"></a>
### O4. Non-compete enforceability analysis and Michigan law citation go beyond an admission summary memo

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L227), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L235)

The instructions ask for an admission summary with contradictions and next steps. Judging whether the non-compete is reasonable, and citing Michigan law or its reformation doctrine, is merits analysis that a competent digest could leave out. It is only arguable for three reasons. The record points toward the issue: Yoon admits he received no separate consideration, and his interrogatory answers reserve overbreadth defenses. The Agreement itself cites MCL 445.774a (§11) and contains a reformation clause (§7(c)). And the legal proposition is correct: MCL 445.774a(1) applies a reasonableness test and lets a court limit an unreasonable covenant. A memo focused strictly on admissions would still fail both criteria.

Evidence:
- `task.json instructions`: “prepare an admission summary memo with contradictions and recommended next steps.”
- `task.json C-028`: “FAIL if the memo does not reference Michigan non-compete law or the possibility of judicial reformation.”
- `yoon-employment-agreement.docx.txt`: “including without limitation MCL 445.774a, which governs the enforceability of covenants not to compete in the employment context.”

Authorities (✓ = primary text checked in the auditing session):
- MCL 445.774a(1) (✓): A post-employment non-compete is enforceable if reasonable as to duration, geographical area, and type of employment or line of business, and a court may limit an unreasonable covenant and enforce it as limited.

Suggested fix: Either tell the solver to flag enforceability risks that affect the value of the admissions, or merge C-027 and C-028 into one optional credit.

<a id="o5"></a>
### O5. Mandatory summary table is a format requirement the instructions never state

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L267)

C-032 fails any memo that lacks 'a summary table (or structured tabular listing)'. The instructions specify no format. Admission charts are common in deposition digests but are not a necessary part of a memo. A well-organized narrative memo with numbered, headed sections for each admission and pinpoint cites to the transcript, interrogatories, Agreement and forensic report would do the substantive work and still fail. Under all-pass scoring, this style preference alone can zero out a complete answer.

Evidence:
- `task.json C-032`: “FAIL if the memo does not include any summary table or structured tabular listing of admissions.”
- `task.json instructions`: “Review the attached deposition transcripts and supporting documents, and prepare an admission summary memo with contradictions and recommended next steps.”

Suggested fix: Accept any organized per-admission listing (a table, numbered list or headed sections) with source cross-references, or add 'include a summary chart' to the instructions.

Related GPT-6 Sol findings: F5.

<a id="o6"></a>
### O6. Record misquotes Interrogatory No. 4 and changes Section 7(a)'s 'or' to 'and'; both bear on criteria premises

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L27), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L323), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L227), [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L347)

(a) The served Interrogatory No. 4 asks when Yoon first communicated with anyone at PAG, with no subject limit. Vol. II quotes it as limited to communications 'regarding potential employment', and the defense's 'social vs. formal' explanation relies on that narrower version. The criteria's contradiction holds under the actual interrogatory, but a memo working from the transcript quotes could describe it as weaker. (b) The operative text of §7(a)(i) restricts 'CNC toolpath optimization software or robotic end-effector design'. The deposition, the Separation Acknowledgment, the C&D letter and C-027 all say 'and'. That matters because PAG is software-only, so an 'and' reading gives Yoon an argument that PAG is not a Competing Business. Neither discrepancy should fail a correct answer, but the rubric's framing rests on paraphrases rather than the controlling text.

Evidence:
- `yoon-interrogatory-answers.docx.txt`: “State the date on which you first communicated with any officer, director, member, manager, employee, or agent of Pinnacle Automation Group, LLC”
- `yoon-deposition-vol2.docx.txt`: “\"State the date on which you first 3 communicated with any representative of Pinnacle 4 Automation Group regarding potential employment.\"”
- `yoon-employment-agreement.docx.txt`: “design, development, manufacture, marketing, sale, or distribution of CNC toolpath optimization software or robotic end-effector design for industrial machining applications”
- `task.json C-027`: “broad activity restriction ('CNC toolpath optimization software and robotic end-effector design for industrial machining applications')”

Suggested fix: Make the transcript quotes match the served interrogatory and the Agreement's 'or', or quote the operative text in C-027 and credit memos that spot the discrepancies.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| F1 | confirmed | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L67), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L75) | arguable | The record agrees with Sol. Vol. I: 'Are you denying that you sent this email? A. I'm saying I don't recall it.' There was no denial. Both criteria still leave a way to pass. C-007's FAIL clause only asks whether the memo 'address[es] the Blue Book email admission', and C-008 has an 'and/or' route through the 'inadvertently' explanation. So an accurate memo will rarely fail. The defect is a mischaracterization built into the rubric, plus a small risk from a literal-minded judge. That makes it arguable, not confirmed. |
| F2 | confirmed | [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L19) | arguable | In Vol. II, Yoon accepts that his first communication with Adwell was around June 8-9 at the Michigan Automation Council event, and Adwell's June 15 email confirms it. The C-001 title, 'first contact ... was June 22', is therefore contradicted by the record. The operative match_criteria only require the dinner admission, so an accurate memo passes. The error sits in the title, and the judge does see the title. Arguable, not problematic. C-003 has the same 'first contacted' premise, which I include in my finding. |
| F3 | arguable | [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L147) | not_a_defect | Sol relied on Vol. I's 'It's possible' and a compound recross question, and missed Vol. II's direct examination. There: 'When specifically did you tell him? A. (Pause.) I believe it came up during our dinner. Q. The June 22 dinner? A. Yes, I think so. Q. So Mr. Adwell knew about your non-compete as early as June 22, 2024? A. I told him I had a non-compete.' That is a direct, lightly hedged admission of June 22 timing, so C-017 is supported by the record. |
| F4 | arguable | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L123) | not_a_defect | This is a deposition digest for CMS's side: CMS counsel examined, a CMS corporate representative observed, and the record includes CMS's C&D letter. Flagging that a claimed mistake is convenient is standard impeachment commentary, and the examining attorney made the same point herself ('Isn't it convenient that PAG set up shop at a distance outside the radius...'). The FAIL clause turns on connecting 142 miles to both the 100-mile and 150-mile radii, which any competent memo does. This is reasonable judgment, not a hidden requirement. |
| F5 | arguable | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-admissions-from-deposition-transcript/task.json#L267) | arguable | The instructions ask only for 'an admission summary memo'. They say nothing about a table. Admission charts are common but not a necessary part of the memo, and a well-organized narrative memo with pinpoint cites would fail C-032. Under all-pass scoring, that alone zeroes the run. My blind pass reached the same view (O5). |

## Blind pass and what changed

None of my findings changed in substance. I checked Sol's F1 (C-007/C-008) and F2 (C-001), which match my O2 and O1; I left both at arguable rather than confirmed, because the operative PASS/FAIL clauses give accurate memos a way to pass. Sol's F5 matches my O5 (C-032, arguable), and I added it as a Sol link. I rejected Sol's F3 (C-017). Sol missed Vol. II's direct testimony ('I believe it came up during our dinner. Q. The June 22 dinner? A. Yes, I think so.'), which supports the June 22 timing. I rejected Sol's F4 (C-014). The memo is a CMS-side digest, and calling the 100-mile 'mistake' convenient repeats the examining attorney's own impeachment point. It is a reasonable criterion, not a hidden advocacy requirement. My O3, O4 and O6 have no counterpart in Sol's audit, and I keep them.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (arguable; C-001, C-003): Rubric treats the June 22 dinner as Yoon's first contact with PAG; Vol. II shows first contact was ~June 8-9
- **O2** (arguable; C-007, C-008): Criteria say Yoon 'initially denied' the Blue Book email; he actually claimed no recollection and refused to deny
- **O3** (arguable; C-009): C-009 mislabels Exhibit 15 as the forensic report and lists four report features that could be read conjunctively
- **O4** (arguable; C-027, C-028): Non-compete enforceability analysis and Michigan law citation go beyond an admission summary memo
- **O5** (arguable; C-032): Mandatory summary table is a format requirement the instructions never state
- **O6** (arguable; C-002, C-039, C-027, C-042): Record misquotes Interrogatory No. 4 and changes Section 7(a)'s 'or' to 'and'; both bear on criteria premises

## Coverage and limits

Blind pass: I read all of these in full: task.json (instructions plus all 46 criteria), both deposition volumes, the interrogatory answers, the Separation Acknowledgment, the Ridgepoint forensic report, the cease-and-desist letter, the judge prompt and the solver system prompt. The judge prompt shows the criterion title as well as match_criteria, so titles matter. I read the Employment Agreement by section rather than cover to cover: recitals, §§1-2, 6, 7(a)-(c), 8, 9, 10, 11, 12(c). I found those sections with targeted searches. I verified MCL 445.774a against the Michigan Legislature site. I did not independently verify Michigan authority on when the duty to preserve attaches or what spoliation remedies are available (C-025/C-026/C-034). I also did not verify the knowledge element of tortious interference (C-018/C-031). Those propositions are standard and I have no reason to doubt them. The record has other inconsistencies that I judged did not move any criterion, so they are not findings: Yoon's date of birth, middle name, residential address and employment history differ between the interrogatory answers and Vol. I. His PhD year and dissertation topic differ between Vol. I p.7 and Vol. II p.338-339; that is useful impeachment of his 'common industry term' defense, but no criterion rewards it. The Blue Book email is timed 11:47 a.m. in the deposition (Ex. 15) but 14:22:17 EDT in the Ridgepoint report. Yoon testified he returned the laptop Aug. 30 (Vol. I p.89); the documents say Aug. 28. Vol. I is stated to run to 230 pages, while Vol. II says Vol. I ran to 287. The patent-access baseline is described as the 'prior 12 months' / ~10x in the deposition but 13 months / 10.4x in the report; C-015 says 'approximately', so this is harmless. The 142-mile distance is consistent across the C&D letter, Vol. I p.23 and Vol. II p.295, and I did not second-guess it against real-world geography.

Reconciliation: Blind pass: I read all of these in full: task.json (all 46 criteria), both deposition volumes, the interrogatory answers, the Separation Acknowledgment, the forensic report, the C&D letter and the judge and solver prompts. I read the relevant sections of the Employment Agreement. I verified MCL 445.774a. Second pass: I read Sol's index entry and audit markdown. I re-checked the testimony for Sol's F3 and F4 in Vol. I (pp.23-24 and 64-65) and in Vol. II (Adwell non-compete direct testimony, the recross, and the 100/150-mile exchange), and I re-read the instructions and the text of C-001, C-003, C-007-C-009, C-014, C-017, C-027, C-028 and C-032. I did not independently research Michigan spoliation or tortious-interference law.
