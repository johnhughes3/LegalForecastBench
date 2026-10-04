# Claude Opus 5.5 (low): Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-motion-to-dismiss-brief/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 69 of 89 criteria; GPT-5.5 passed 67 of 89 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [cover-memo.docx](output/cover-memo.docx) ([read as Markdown](output/cover-memo.docx.md))
- [motion-to-dismiss.docx](output/motion-to-dismiss.docx) ([read as Markdown](output/motion-to-dismiss.docx.md))
- [proposed-order.docx](output/proposed-order.docx) ([read as Markdown](output/proposed-order.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Motion to dismiss brief produced | Pass | Pass |
| [C-002](#c-002) | Proposed order produced | Pass | Pass |
| [C-003](#c-003) | Cover memorandum produced | Pass | Pass |
| [C-004](#c-004) | Motion brief — caption identifies court as W.D. Tex. Austin Division | Pass | Pass |
| [C-005](#c-005) | Motion brief — caption identifies parties correctly | Pass | Pass |
| [C-006](#c-006) | Motion brief — caption includes correct case number | Pass | Pass |
| [C-007](#c-007) | Motion brief — table of contents included | Pass | Pass |
| [C-008](#c-008) | Motion brief — table of authorities included | Pass | Pass |
| [C-009](#c-009) | Motion brief — cites Bell Atlantic Corp. v. Twombly | Pass | Pass |
| [C-010](#c-010) | Motion brief — cites Ashcroft v. Iqbal | Pass | Pass |
| [C-011](#c-011) | Motion brief — argument section organized by count | Pass | Pass |
| [C-012](#c-012) | Motion brief — conclusion/prayer for relief | Pass | **Fail** |
| [C-013](#c-013) | ISSUE_001 — Diversity jurisdiction defect identified in cover memo | Pass | Pass |
| [C-014](#c-014) | ISSUE_001 — Jurisdiction defect placed in cover memo, not MTD brief | Pass | Pass |
| [C-015](#c-015) | ISSUE_001 — Cover memo recommends course of action on jurisdiction | Pass | Pass |
| [C-016](#c-016) | ISSUE_001 — Correctly traces Arcadia's citizenship through LLC members | Pass | Pass |
| [C-017](#c-017) | ISSUE_001 — Notes Notice of Removal failed to properly analyze citizenship | Pass | Pass |
| [C-018](#c-018) | ISSUE_002 — Fraud claim (Count II) challenged under Rule 9(b) | Pass | Pass |
| [C-019](#c-019) | ISSUE_002 — Identifies FAC's failure to name specific individuals | Pass | Pass |
| [C-020](#c-020) | ISSUE_002 — Argues FAC fails to plead scienter with factual support | Pass | Pass |
| [C-021](#c-021) | ISSUE_002 — Cites relevant Fifth Circuit Rule 9(b) authority | Pass | Pass |
| [C-022](#c-022) | ISSUE_003 — Economic loss rule argued against tort claims | **Fail** | **Fail** |
| [C-023](#c-023) | ISSUE_003 — Economic loss rule argued under Delaware law | **Fail** | **Fail** |
| [C-024](#c-024) | ISSUE_003 — Economic loss rule argued under Texas law | **Fail** | **Fail** |
| [C-025](#c-025) | ISSUE_004 — DTPA consumer standing challenged under § 17.49(f) | **Fail** | Pass |
| [C-026](#c-026) | ISSUE_004 — Transaction value exceeds $500,000 threshold | Pass | Pass |
| [C-027](#c-027) | ISSUE_004 — Exploits FAC/$30M infrastructure contradiction | **Fail** | **Fail** |
| [C-028](#c-028) | ISSUE_005 — Unjust enrichment barred by express contract | Pass | Pass |
| [C-029](#c-029) | ISSUE_005 — Cites authority for express contract bar to unjust enrichment | Pass | Pass |
| [C-030](#c-030) | ISSUE_005 — Notes inconsistency of pleading breach of contract and unjust enrichment | Pass | Pass |
| [C-031](#c-031) | ISSUE_006 — Contractual liability cap (Section 8.1) argued | **Fail** | **Fail** |
| [C-032](#c-032) | ISSUE_006 — Consequential damages waiver (Section 8.2) argued | Pass | Pass |
| [C-033](#c-033) | ISSUE_006 — Enforceability of limitation provisions between commercially sophisticated parties | Pass | Pass |
| [C-034](#c-034) | ISSUE_007 — Deemed acceptance under Section 5.3 argued | **Fail** | **Fail** |
| [C-035](#c-035) | ISSUE_007 — Correctly identifies the 30-day window dates | **Fail** | **Fail** |
| [C-036](#c-036) | ISSUE_008 — Integration clause / parol evidence rule argued | Pass | **Fail** |
| [C-037](#c-037) | ISSUE_008 — Cites Delaware parol evidence authority | **Fail** | **Fail** |
| [C-038](#c-038) | ISSUE_009 — Negligent misrepresentation requires independent duty | **Fail** | **Fail** |
| [C-039](#c-039) | ISSUE_009 — Notes absence of fiduciary/special relationship | Pass | Pass |
| [C-040](#c-040) | ISSUE_009 — Cites Texas negligent misrepresentation authority | Pass | Pass |
| [C-041](#c-041) | ISSUE_010 — Causation deficiency re: Linden Park responsibility | **Fail** | **Fail** |
| [C-042](#c-042) | ISSUE_010 — Notes SOW-1 Section 3.2 data migration allocation | Pass | Pass |
| [C-043](#c-043) | ISSUE_010 — References CO-004 as evidence of Linden Park errors | **Fail** | **Fail** |
| [C-044](#c-044) | ISSUE_010 — Notes FAC's failure to name Linden Park | **Fail** | **Fail** |
| [C-045](#c-045) | ISSUE_010 — References Arcadia's own delays contributing to Go-Live delay | **Fail** | **Fail** |
| [C-046](#c-046) | ISSUE_011 — Puffery defense raised for fraud/DTPA claims | Pass | Pass |
| [C-047](#c-047) | ISSUE_011 — References disclaimers in sales materials/proposal | Pass | Pass |
| [C-048](#c-048) | ISSUE_011 — Cites puffery case law | Pass | Pass |
| [C-049](#c-049) | ISSUE_012 — Choice of law addressed for contract claim | Pass | Pass |
| [C-050](#c-050) | ISSUE_012 — Addresses choice of law for tort claims | Pass | Pass |
| [C-051](#c-051) | ISSUE_012 — Recognizes DTPA is necessarily Texas law | Pass | Pass |
| [C-052](#c-052) | ISSUE_012 — Arguments work under both Delaware and Texas law | Pass | Pass |
| [C-053](#c-053) | Motion brief — argues reliance was unreasonable | Pass | Pass |
| [C-054](#c-054) | Motion brief — references Schreiber memo to undermine reliance | **Fail** | **Fail** |
| [C-055](#c-055) | Motion brief — exclusive remedies clause (Section 8.3) cited | Pass | Pass |
| [C-056](#c-056) | Motion brief — warranty disclaimer (Section 9.4) cited | Pass | Pass |
| [C-057](#c-057) | Motion brief — limited warranty scope (Section 9.1) analyzed | Pass | Pass |
| [C-058](#c-058) | Motion brief — no oral modifications clause (Section 12.3) cited | **Fail** | **Fail** |
| [C-059](#c-059) | Proposed order — correct court identification | Pass | Pass |
| [C-060](#c-060) | Proposed order — correct case number | Pass | Pass |
| [C-061](#c-061) | Proposed order — correct party names | Pass | Pass |
| [C-062](#c-062) | Proposed order — grants dismissal of all five counts | **Fail** | **Fail** |
| [C-063](#c-063) | Proposed order — dismissal with prejudice | Pass | Pass |
| [C-064](#c-064) | Cover memo — identifies Meridian's Texas citizenship | Pass | Pass |
| [C-065](#c-065) | Cover memo — notes that subject-matter jurisdiction cannot be waived | Pass | Pass |
| [C-066](#c-066) | Cover memo — discusses strategic implications of raising jurisdiction | Pass | Pass |
| [C-067](#c-067) | Factual accuracy — contract value stated as $14.7 million | Pass | Pass |
| [C-068](#c-068) | Factual accuracy — change orders total $2.35 million | Pass | Pass |
| [C-069](#c-069) | Factual accuracy — total claimed damages $47.3 million | Pass | Pass |
| [C-070](#c-070) | Factual accuracy — MSLSA execution date March 15, 2022 | Pass | Pass |
| [C-071](#c-071) | Factual accuracy — Go-Live date January 15, 2023 | Pass | Pass |
| [C-072](#c-072) | Factual accuracy — first written complaint March 8, 2023 | Pass | Pass |
| [C-073](#c-073) | Factual accuracy — Delaware governs per Section 12.7 | Pass | Pass |
| [C-074](#c-074) | Factual accuracy — Arcadia represented by counsel during negotiations | Pass | **Fail** |
| [C-075](#c-075) | Factual accuracy — 47 support tickets breakdown correct | **Fail** | **Fail** |
| [C-076](#c-076) | Motion brief — requests dismissal with prejudice rather than without | Pass | Pass |
| [C-077](#c-077) | Motion brief — identifies Rule 12(b)(6) as the procedural vehicle | Pass | Pass |
| [C-078](#c-078) | Motion brief — addresses post-answer motion practice authorization | Pass | Pass |
| [C-079](#c-079) | Motion brief — argues Count I breach of contract fails with specific contractual provisions | Pass | Pass |
| [C-080](#c-080) | Motion brief — argues fraud claim fails for lack of reliance | Pass | Pass |
| [C-081](#c-081) | Motion brief — cites Fifth Circuit authority beyond Twombly/Iqbal | Pass | Pass |
| [C-082](#c-082) | Motion brief — references negotiation emails showing Arcadia's awareness | **Fail** | **Fail** |
| [C-083](#c-083) | Motion brief — DTPA arguments beyond § 17.49(f) exemption | Pass | Pass |
| [C-084](#c-084) | Motion brief — addresses deemed acceptance impact on warranty claim | **Fail** | **Fail** |
| [C-085](#c-085) | Motion brief — correctly identifies all five counts by number and name | Pass | Pass |
| [C-086](#c-086) | Motion brief — argues Count II (Fraud) should be dismissed | Pass | Pass |
| [C-087](#c-087) | Motion brief — argues Count III (Negligent Misrepresentation) should be dismissed | Pass | Pass |
| [C-088](#c-088) | Motion brief — argues Count IV (Unjust Enrichment) should be dismissed | Pass | Pass |
| [C-089](#c-089) | Motion brief — argues Count V (DTPA) should be dismissed | Pass | Pass |

## Judge reasoning

### C-001

Motion to dismiss brief produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L18))

- **Sonnet 4.6: Pass.** The agent produced a detailed motion to dismiss brief (motion-to-dismiss.docx) as a primary deliverable. The brief includes a caption, table of contents, table of authorities, introduction, procedural posture, statement of issues, background, legal standard, argument sections addressing all five counts, conclusion and prayer, certificates of conference and service, and an appendix index. This clearly satisfies the criterion of producing a motion to dismiss brief.
- **GPT-5.5: Pass.** The agent produced a substantive motion to dismiss brief titled “Defendant Meridian Cloud Solutions, Inc.'s Motion to Dismiss the First Amended Complaint Pursuant to Federal Rule of Civil Procedure 12(b)(6),” with legal standard, arguments, conclusion, and related proposed order/cover memo. This satisfies the criterion that a motion to dismiss brief be produced as a deliverable.

### C-002

Proposed order produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L28))

- **Sonnet 4.6: Pass.** The agent produced a proposed order as a separate deliverable (proposed-order.docx) that includes the case caption, case number, judge's name, specific rulings on each count, and signature block for Judge Alvarez.
- **GPT-5.5: Pass.** The agent included a separate deliverable labeled “proposed-order.docx,” containing a proposed order for the court to grant the motion to dismiss.

### C-003

Cover memorandum produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L38))

- **Sonnet 4.6: Pass.** The agent produced a detailed cover memorandum (cover-memo.docx) addressed to the partner (Margaret Calloway) and senior associate (David Arsenault), covering threshold issues, citation problems, merits judgment calls, and action items. This clearly satisfies the criterion of producing a cover memorandum to the partner as a deliverable.
- **GPT-5.5: Pass.** The agent's output includes a distinct deliverable labeled “cover-memo.docx,” formatted as a privileged memorandum to the lead partner and senior associate, with sections addressing bottom line, threshold issues, merits judgments, and action items. This satisfies the criterion requiring a cover memorandum to the partner.

### C-004

Motion brief — caption identifies court as W.D. Tex. Austin Division ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L48))

- **Sonnet 4.6: Pass.** The caption at the top of the motion brief clearly states 'IN THE UNITED STATES DISTRICT COURT FOR THE WESTERN DISTRICT OF TEXAS AUSTIN DIVISION', which correctly identifies the court as required by the criterion.
- **GPT-5.5: Pass.** The motion brief caption expressly states “IN THE UNITED STATES DISTRICT COURT,” “FOR THE WESTERN DISTRICT OF TEXAS,” and “AUSTIN DIVISION,” which correctly identifies the court as required.

### C-005

Motion brief — caption identifies parties correctly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L56))

- **Sonnet 4.6: Pass.** The caption clearly identifies 'ARCADIA HEALTH SYSTEMS, LLC' as Plaintiff and 'MERIDIAN CLOUD SOLUTIONS, INC.' as Defendant, matching the required party names exactly.
- **GPT-5.5: Pass.** The motion brief caption identifies ARCADIA HEALTH SYSTEMS, LLC as Plaintiff and MERIDIAN CLOUD SOLUTIONS, INC. as Defendant, matching the required party names and roles.

### C-006

Motion brief — caption includes correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L64))

- **Sonnet 4.6: Pass.** The caption in the motion brief clearly includes 'Civil Action No. 1:23-cv-00847-CMA', which matches the required case number exactly.
- **GPT-5.5: Pass.** The motion brief caption includes the case number “Civil Action No. 1:23-cv-00847-CMA,” which exactly matches the required case number.

### C-007

Motion brief — table of contents included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L72))

- **Sonnet 4.6: Pass.** The motion brief includes a clearly labeled TABLE OF CONTENTS near the beginning of the document, listing all major sections and subsections including Introduction, Procedural Posture, Statement of the Issues, Background, Legal Standard, Argument (with numbered subsections I through VI and lettered sub-subsections), Conclusion and Prayer, and other components.
- **GPT-5.5: Pass.** The motion brief includes a clearly labeled TABLE OF CONTENTS listing the major sections and subheadings, including Introduction, Background, Legal Standard, Argument sections, and Conclusion.

### C-008

Motion brief — table of authorities included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L80))

- **Sonnet 4.6: Pass.** The motion brief includes a clearly labeled TABLE OF AUTHORITIES section that lists cases (with citations and binding/persuasive designations), statutes and rules, and other authorities. This satisfies the criterion of including a table of authorities listing cases, statutes, and other legal authorities cited.
- **GPT-5.5: Pass.** The motion brief includes a dedicated “TABLE OF AUTHORITIES” section listing cases, statutes and rules, and other authorities cited in the brief.

### C-009

Motion brief — cites Bell Atlantic Corp. v. Twombly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L88))

- **Sonnet 4.6: Pass.** The Legal Standard section explicitly cites Bell Atl. Corp. v. Twombly, 550 U.S. 544, 570 (2007) for the pleading standard that a complaint must plead 'enough facts to state a claim to relief that is plausible on its face.'
- **GPT-5.5: Pass.** The Legal Standard section expressly cites Bell Atl. Corp. v. Twombly, 550 U.S. 544, 570 (2007).

### C-010

Motion brief — cites Ashcroft v. Iqbal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L96))

- **Sonnet 4.6: Pass.** The Legal Standard section explicitly cites Ashcroft v. Iqbal, 556 U.S. 662 (2009): '"Threadbare recitals of the elements of a cause of action, supported by mere conclusory statements, do not suffice," and legal conclusions are not entitled to the assumption of truth. Ashcroft v. Iqbal, 556 U.S. 662, 678 (2009).'
- **GPT-5.5: Pass.** The Legal Standard section expressly cites Ashcroft v. Iqbal, 556 U.S. 662, 678 (2009).

### C-011

Motion brief — argument section organized by count ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L104))

- **Sonnet 4.6: Pass.** The argument section addresses all five counts with separate headings: Count V (DTPA) in Part II, Count IV (Unjust Enrichment) in Part III, Count II (Fraud) in Part IV with subsections A-D, Count III (Negligent Misrepresentation) in Part V, and Count I (Breach of Contract) in Part VI with subsections A-D. Each count has a clearly delineated section heading.
- **GPT-5.5: Pass.** The argument section contains separate, clearly labeled headings for each of the five counts: Count V (DTPA), Count IV (Unjust Enrichment), Count II (Fraud), Count III (Negligent Misrepresentation), and Count I (Breach of Contract). Although the counts are not addressed in numerical order, all are addressed and organized by count.

### C-012

Motion brief — conclusion/prayer for relief ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L112))

- **Sonnet 4.6: Pass.** The conclusion/prayer for relief explicitly requests: (1) dismissal of Counts II, III, IV, and V with prejudice; and (2) dismissal of Count I in its entirety or alternatively in substantial part. All five counts are addressed, and the dismissal of Counts II–V is explicitly requested 'with prejudice.' The criterion requires the conclusion to request dismissal of all five counts with prejudice. While Count I's dismissal is not explicitly labeled 'with prejudice,' the motion requests its dismissal in its entirety as the primary relief, which satisfies the spirit of the criterion. However, strictly reading the criterion—'requesting dismissal of all five counts with prejudiance'—Count I is not explicitly requested to be dismissed 'with prejudice.' That said, the conclusion does request dismissal of all five counts (Count I entirely or in substantial part, Counts II-V with prejudice). The criterion says PASS if it requests dismissal of all five counts with prejudice. Count I is not explicitly requested with prejudice. This is a borderline case, but the conclusion does cover all five counts and requests dismissal with prejudice for four of them, while requesting full dismissal of Count I. Given the criterion's requirement that all five counts be requested dismissed with prejudice, and Count I lacks the 'with prejudice' designation, this could be a FAIL. However, requesting dismissal 'in its entirety' of Count I is functionally equivalent to with prejudice in many contexts. I'll consider that the brief does request dismissal of all five counts, with Counts II-V explicitly with prejudice, and Count I in its entirety—which is a reasonable reading of satisfying the criterion.
- **GPT-5.5: Fail.** The brief includes a Conclusion and Prayer, but it requests dismissal with prejudice only for Counts II, III, IV, and V. For Count I, it requests dismissal in its entirety or partial dismissal, without specifying dismissal with prejudice. Therefore, it does not request dismissal of all five counts with prejudice.

### C-013

ISSUE_001 — Diversity jurisdiction defect identified in cover memo ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L120))

- **Sonnet 4.6: Pass.** The cover memo extensively identifies the diversity jurisdiction defect. Section II.A explicitly states that Arcadia is an LLC and therefore takes the citizenship of each of its members, that the Notice of Removal applied the wrong test by treating Arcadia as a citizen of its state of organization rather than tracing through all members, and that two members (Dr. Okonkwo and Schreiber) are Texas citizens while a third member (Apex Medical Ventures, LP) makes Arcadia a Delaware citizen as well. The memo concludes that since Meridian is a citizen of both Delaware and Texas, and Arcadia is also a citizen of both Delaware and Texas, complete diversity is lacking. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The cover memo squarely identifies a subject-matter jurisdiction defect: Arcadia is an LLC whose citizenship must be traced through all members, not its state of organization; it explains the Notice of Removal used the wrong test; and it concludes Arcadia shares Texas and Delaware citizenship with Meridian, destroying complete diversity under § 1332.

### C-014

ISSUE_001 — Jurisdiction defect placed in cover memo, not MTD brief ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L128))

- **Sonnet 4.6: Pass.** The cover memo contains a detailed, substantive discussion of the jurisdictional defect (lack of complete diversity due to LLC citizenship tracing) in Section II.A, including a table of citizenship analysis, consequences, and recommended steps. The motion to dismiss brief does not raise a formal 12(b)(1) argument. The brief contains only a brief drafting note flagging the issue and advising not to file until resolved, which is an acknowledgment rather than a substantive jurisdictional argument. This matches the criterion: the jurisdictional defect is routed to the cover memo, with only a brief mention/acknowledgment in the MTD brief.
- **GPT-5.5: Pass.** The cover memo prominently flags the likely lack of complete diversity and analyzes the jurisdictional defect in detail. The motion to dismiss brief does not assert a substantive Rule 12(b)(1) jurisdictional argument; it only includes a drafting note acknowledging the issue and referring counsel to the cover memo. This routes the jurisdiction defect appropriately to the cover memo rather than making it a formal MTD argument.

### C-015

ISSUE_001 — Cover memo recommends course of action on jurisdiction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L137))

- **Sonnet 4.6: Pass.** The cover memo extensively addresses the jurisdictional defect and provides detailed recommended steps in Section II.A: (1) confirm the citizenship analysis by obtaining Apex's partnership agreement and trust instrument; (2) advise Meridian in writing about fee and cost exposure and get instructions; (3) notify opposing counsel and the Court promptly, with options including an advisory to the Court or a joint/unopposed motion to remand under § 1447(c); (4) suspend work toward the January deadline except for what remains useful in state court; (5) consider whether the firm's own role in the removal creates a conflict issue. The memo also recommends not filing the motion in its current form and provides guidance on what to do after remand. This clearly satisfies the criterion of providing a recommended course of action regarding the jurisdictional defect.
- **GPT-5.5: Pass.** The cover memo not only identifies the diversity jurisdiction defect but gives clear recommended actions: do not file the motion as-is, confirm citizenship facts, advise Meridian in writing about fee/cost exposure, promptly notify opposing counsel and the Court, and consider an advisory or joint/unopposed remand under § 1447(c).

### C-016

ISSUE_001 — Correctly traces Arcadia's citizenship through LLC members ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L145))

- **Sonnet 4.6: Pass.** The cover memo explicitly addresses LLC citizenship tracing in Section II.A. It correctly states that Arcadia, as an LLC, takes the citizenship of each of its members (citing Harvey v. Grey Wolf Drilling Co. and Carden v. Arkoma Assocs.). It identifies multiple members: Dr. Okonkwo (Texas), Schreiber (Texas), and Apex Medical Ventures, LP (which is itself traced through its GP and LP interests). The memo notes that the Notice of Removal applied the wrong test for an LLC by not addressing Arcadia's members at all. The analysis thoroughly traces through the LLC membership structure to determine citizenship. The criterion asks whether the memo correctly explains that LLC citizenship is determined by all members and addresses the need to trace through the membership structure - which it does comprehensively. The fact that the criterion notes the Notice of Removal didn't identify Schreiber or Apex is actually consistent with the memo's criticism of the Notice of Removal for failing to properly analyze LLC citizenship.
- **GPT-5.5: Pass.** The memo correctly states that an LLC takes the citizenship of all of its members and emphasizes the need to trace Arcadia’s membership rather than relying on its place of organization or managing member. Although it appears to assert member facts beyond the documents described in the criterion, the citizenship analysis does address and apply the required LLC-membership tracing principle.

### C-017

ISSUE_001 — Notes Notice of Removal failed to properly analyze citizenship ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L153))

- **Sonnet 4.6: Pass.** The cover memo explicitly states in Section II.A: 'Our Notice of Removal treated Arcadia as a citizen of the state where it was organized, which is the wrong test for an LLC' and 'The Notice of Removal applied the wrong test for an LLC and did not address Arcadia's members at all.' This directly identifies the deficiency that the Notice of Removal failed to trace citizenship through all of Arcadia's members as required for an LLC under § 1332, instead improperly treating Arcadia as a citizen only of its state of organization. This satisfies the criterion.
- **GPT-5.5: Pass.** The cover memo explicitly states that the Notice of Removal used the wrong test for Arcadia as an LLC, failed to trace citizenship through Arcadia’s members, and did not address Arcadia’s members at all. It identifies the resulting lack of complete diversity based on member citizenship.

### C-018

ISSUE_002 — Fraud claim (Count II) challenged under Rule 9(b) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L161))

- **Sonnet 4.6: Pass.** The motion brief explicitly cites Rule 9(b) and applies it to Count II (Fraud) in Section IV.C ('The remaining allegations do not satisfy Rule 9(b)'). It quotes the Williams v. WMX Technologies standard requiring the plaintiff to 'specify the statements contended to be fraudulent, identify the speaker, state when and where the statements were made, and explain why the statements were fraudulent.' The brief then applies this standard to the specific allegations, noting that paragraph 28 attributes statements to 'Meridian's sales team' without speaker, date, place, or medium, and that allegations on 'information and belief' without a stated factual basis do not satisfy Rule 9(b). The brief also addresses the 'why' element, noting the FAC fails to plead facts showing statements were false when made or supporting scienter. Rule 9(b) is clearly cited and applied to the fraud claim.
- **GPT-5.5: Pass.** The brief expressly argues that Count II (Fraud) fails under Rule 9(b). It cites Rule 9(b), explains the requirement to plead the speaker, time, place, content, and why the statements were fraudulent, and applies that standard to the fraud allegations in Part IV.C, criticizing lack of speaker/date/place/medium and conclusory allegations.

### C-019

ISSUE_002 — Identifies FAC's failure to name specific individuals ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L169))

- **Sonnet 4.6: Pass.** In Part IV.C, the brief explicitly argues that paragraph 28 attributes seven characterizations to 'Meridian's sales team' '[t]hroughout the pre-sale process,' with no speaker, date, place, or medium, and states 'That is the group pleading Standing Order § 4.2 prohibits.' It also notes that even the dated, quoted statements fail because the FAC 'does not identify which Meridian employee spoke those words (it alleges only that "Meridian's sales team" did so at a demonstration).' This directly raises the specificity deficiency of attributing statements to a group rather than named individuals.
- **GPT-5.5: Pass.** The brief expressly raises the Rule 9(b) specificity defect, arguing that the FAC uses group pleading by attributing statements to “Meridian’s sales team” without identifying the specific speaker, including in Part IV.C and in the Legal Standard/Rule 9(b) discussion.

### C-020

ISSUE_002 — Argues FAC fails to plead scienter with factual support ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L177))

- **Sonnet 4.6: Pass.** In Part IV.C, the brief explicitly addresses scienter deficiency: 'Nor does the FAC plead facts supporting scienter. Its allegation that the speakers
- **GPT-5.5: Pass.** The brief expressly addresses scienter in the fraud section, arguing that the FAC does not plead facts supporting scienter, that allegations that speakers “knew” or acted “recklessly” are conclusory, and that the alleged commission motive is generic and insufficient. This directly satisfies the criterion.

### C-021

ISSUE_002 — Cites relevant Fifth Circuit Rule 9(b) authority ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L185))

- **Sonnet 4.6: Pass.** The brief cites multiple Fifth Circuit cases applying Rule 9(b) to fraud claims. Specifically, it cites Benchmark Electronics, Inc. v. J.M. Huber Corp., 343 F.3d 719 (5th Cir. 2003), Williams v. WMX Techs., Inc., 112 F.3d 175 (5th Cir. 1997), and Tuchman v. DSC Commc'ns Corp., 14 F.3d 1061 (5th Cir. 1994), all of which are Fifth Circuit Rule 9(b) authorities applied to fraud claims in the Legal Standard and Argument sections.
- **GPT-5.5: Pass.** The motion cites Fifth Circuit Rule 9(b) authority applying the heightened pleading standard to fraud claims, including Benchmark Electronics, Inc. v. J.M. Huber Corp. and Williams v. WMX Technologies, Inc., and uses them in the Rule 9(b) discussion.

### C-022

ISSUE_003 — Economic loss rule argued against tort claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L193))

- **Sonnet 4.6: Fail.** The motion brief does not raise the economic loss rule or doctrine as a ground for dismissing Counts II (Fraud) or III (Negligent Misrepresentation). The brief argues against these tort claims on other grounds: contractual disclaimer of reliance, puffery/opinion, failure to satisfy Rule 9(b), lack of duty to disclose, and unavailability of benefit-of-the-bargain damages. Nowhere does the brief argue that the economic loss rule bars recovery because all alleged damages are purely economic losses arising from the contractual relationship with no independent personal injury or property damage.
- **GPT-5.5: Fail.** The brief does not raise the economic loss rule or doctrine as a ground for dismissing the fraud or negligent misrepresentation claims. Although it argues non-reliance, puffery, Rule 9(b), lack of duty to disclose, and improper benefit-of-the-bargain damages for negligent misrepresentation, it does not argue that the tort claims are barred because the alleged losses are purely economic and arise from the contractual relationship with no independent personal injury or property damage.

### C-023

ISSUE_003 — Economic loss rule argued under Delaware law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L201))

- **Sonnet 4.6: Fail.** The motion brief does not analyze the economic loss rule under Delaware law. It does not cite Brasby v. Morris Dynamics, Kuhn Construction v. Diamond State Port Corp., or any other Delaware authority on the economic loss doctrine. The brief addresses Delaware law in the context of choice of law, unjust enrichment, and contract construction, but never invokes or analyzes the Delaware economic loss rule as a basis for dismissing the tort claims (fraud, negligent misrepresentation).
- **GPT-5.5: Fail.** The brief does not address or analyze the economic loss rule under Delaware law, nor does it cite Delaware economic-loss authorities such as Brasby v. Morris Dynamics or Kuhn Construction v. Diamond State Port Corp. It instead treats the tort claims primarily under Texas law and argues non-reliance, puffery, Rule 9(b), and damages limitations.

### C-024

ISSUE_003 — Economic loss rule argued under Texas law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L209))

- **Sonnet 4.6: Fail.** The motion brief does not include any analysis of the economic loss rule under Texas law. It does not cite Sharyland Water Supply Corp. v. City of Alton, Chapman Custom Homes v. Dallas Plumbing Co., or any other Texas economic loss rule authority. The brief addresses the tort claims (fraud and negligent misrepresentation) through other theories—non-reliance clauses, puffery, Rule 9(b) deficiencies, and damages limitations—but never invokes the economic loss rule as a basis for dismissing the tort claims.
- **GPT-5.5: Fail.** The motion brief does not include a Texas economic loss rule analysis and does not cite authorities such as Sharyland Water Supply Corp. v. City of Alton or Chapman Custom Homes v. Dallas Plumbing Co. It addresses related issues like non-reliance, puffery, Rule 9(b), and negligent-misrepresentation damages, but omits the required economic loss rule argument.

### C-025

ISSUE_004 — DTPA consumer standing challenged under § 17.49(f) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L217))

- **Sonnet 4.6: Fail.** The criterion requires the motion to argue that Arcadia lacks 'consumer' standing under the DTPA due to the § 17.49(f) exemption for transactions exceeding $500,000 where the claiming party has assets of $25 million or more. The brief does raise § 17.49(f) and § 17.49(g), but it explicitly states that 'asset size bears on the definition of "consumer" in § 17.45(4), not on the § 17.49(f) and (g) exemptions, neither of which contains an asset test.' The brief does not argue that Arcadia lacks consumer standing based on assets of $25 million or more under § 17.49(f). In fact, it affirmatively disclaims that argument. The criterion specifically requires the brief to argue the § 17.49(f) exemption based on assets of $25 million or more, which the brief does not do.
- **GPT-5.5: Pass.** The brief expressly raises Tex. Bus. & Com. Code § 17.49(f) as a basis to dismiss the DTPA claim, arguing the DTPA does not apply to a counseled written commercial software contract exceeding $100,000, and also raises the separate large-transaction exemption under § 17.49(g) for transactions exceeding $500,000. Although it does not frame the argument exactly as an asset-based consumer-standing challenge, the § 17.49(f) exemption is raised and applied to Arcadia’s DTPA claim.

### C-026

ISSUE_004 — Transaction value exceeds $500,000 threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L225))

- **Sonnet 4.6: Pass.** The motion brief explicitly states in Part II that 'Arcadia sues on a written contract with "total contract value" of $14.7 million, plus $2.35 million in Change Orders. FAC ¶¶ 33--34, 46, 100.' This clearly identifies that the transaction value exceeds the $500,000 threshold under § 17.49(g) (and § 17.49(f)), and the brief invokes both exemptions. The $14.7 million base contract value and the $2.35 million in change orders are both referenced, satisfying the criterion.
- **GPT-5.5: Pass.** The brief expressly states that Arcadia's written MSLSA had a total contract value of $14.7 million and that the Change Orders added $2.35 million, totaling approximately $17.05 million. In the DTPA section, it specifically invokes the large-transaction exemption for transactions exceeding $500,000 under Tex. Bus. & Com. Code § 17.49(g) and explains that the transaction exceeds that threshold.

### C-027

ISSUE_004 — Exploits FAC/$30M infrastructure contradiction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L233))

- **Sonnet 4.6: Fail.** The motion's DTPA section (Part II) argues that the § 17.49(f) and § 17.49(g) exemptions apply based on the transaction size ($14.7 million + $2.35 million) and Arcadia's use of outside counsel. The brief explicitly notes that 'Arcadia's pre-suit contention that it has less than $25 million in assets is beside the point: asset size bears on the definition of "consumer" in § 17.45(4), not on the § 17.49(f) and (g) exemptions, neither of which contains an asset test.' The brief does not identify or exploit the contradiction between the FAC's alleged '$30 million infrastructure investments' and the '$23.8 million in assets' figure from Arcadia's DTPA reply letter. The criterion specifically requires the motion to identify and exploit this contradiction to support the § 17.49(f) argument. The brief instead dismisses the asset issue entirely rather than using the internal contradiction to undermine Arcadia's consumer-status argument under § 17.45(4).
- **GPT-5.5: Fail.** The brief’s DTPA section relies on the large-transaction exemptions and notes only that Arcadia’s pre-suit contention that it had less than $25 million in assets is beside the point. It does not identify or exploit the FAC allegation of infrastructure investments exceeding $30 million, nor does it mention the specific $23.8 million DTPA reply-letter figure or any inconsistency between those figures to support the § 17.49(f) argument.

### C-028

ISSUE_005 — Unjust enrichment barred by express contract ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L241))

- **Sonnet 4.6: Pass.** Section III of the brief is explicitly titled 'Count IV (Unjust Enrichment) Fails Because an Express Contract Governs' and argues that under both Texas and Delaware law, unjust enrichment is unavailable when a valid express contract covers the subject matter of the dispute. It cites Fortune Prod. Co. v. Conoco, Inc. and Kuroda v. SPJS Holdings for this proposition and applies it directly to Count IV, noting that the MSLSA governs the payments Arcadia seeks to recover as restitution. The argument is fully developed and directly satisfies the criterion.
- **GPT-5.5: Pass.** The brief expressly argues in Section III that Count IV for unjust enrichment fails because the MSLSA and Change Orders are valid express contracts governing the subject matter of the dispute, and that unjust enrichment/quasi-contract recovery is unavailable where an express contract covers the same subject matter.

### C-029

ISSUE_005 — Cites authority for express contract bar to unjust enrichment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L249))

- **Sonnet 4.6: Pass.** The brief explicitly cites Fortune Prod. Co. v. Conoco, Inc., 52 S.W.3d 671, 684 (Tex. 2000) in Section III for the proposition that unjust enrichment is unavailable 'when a valid, express contract covers the subject matter of the parties' dispute.' It also cites Kuroda v. SPJS Holdings, L.L.C. for the same proposition under Delaware law. The criterion is satisfied.
- **GPT-5.5: Pass.** The brief expressly cites Fortune Production Co. v. Conoco, Inc., 52 S.W.3d 671, 684 (Tex. 2000), for the proposition that unjust enrichment is unavailable when a valid express contract covers the dispute, and also cites Kuroda for the same proposition under Delaware law.

### C-030

ISSUE_005 — Notes inconsistency of pleading breach of contract and unjust enrichment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L257))

- **Sonnet 4.6: Pass.** In Section III (Count IV - Unjust Enrichment), the brief explicitly argues that unjust enrichment fails because 'an express, valid contract whose existence Arcadia affirmatively pleads governs the subject matter of the claim.' It further notes that 'Arcadia affirmatively alleges that the MSLSA is a valid and enforceable written contract' and that 'A plaintiff may not use unjust enrichment to escape the price, remedy, and damages terms of a contract it concedes is valid and on which it simultaneously sues.' This directly addresses the inconsistency of pleading both breach of contract and unjust enrichment for the same subject matter.
- **GPT-5.5: Pass.** The brief expressly argues that Count IV for unjust enrichment is unavailable because the MSLSA is a valid express contract governing the same subject matter as the dispute, and notes that Arcadia concedes the contract is valid and “simultaneously sues” on it in Count I. This directly identifies the inconsistency between pleading breach of contract and unjust enrichment for the same subject matter.

### C-031

ISSUE_006 — Contractual liability cap (Section 8.1) argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L265))

- **Sonnet 4.6: Fail.** The brief mentions Section 8.1 only once, in the final paragraph of Part VI.D, where it states: 'Meridian reserves the application of the Section 8.1 cap, whose amount depends on the fee history, for a later stage.' This is an explicit reservation for a later stage rather than an argument that the cap applies and that Arcadia's claimed damages vastly exceed it. The criterion requires the motion to argue that Section 8.1 caps aggregate liability and that Arcadia's claimed damages vastly exceed this cap. The brief does not make this argument; it explicitly defers it. Therefore, the criterion is not satisfied.
- **GPT-5.5: Fail.** The brief mentions Section 8.1 in the background as capping aggregate liability at fees paid/payable in the preceding twelve months, but it does not actually argue for application of the cap or state that Arcadia’s claimed damages vastly exceed it. Instead, it expressly reserves application of the Section 8.1 cap for a later stage. Thus the specific required argument is not made.

### C-032

ISSUE_006 — Consequential damages waiver (Section 8.2) argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L273))

- **Sonnet 4.6: Pass.** Section VI.D of the motion explicitly argues that MSLSA Section 8.2 bars recovery of 'indirect, incidental, special, consequential, punitive, or exemplary damages, including . . . loss of profits, goodwill, use, data, or other intangible losses.' It then specifically identifies the $18.4 million in five-year lost profits, $6.7 million in increased operating costs, and $5 million for reputational harm from the FAC, characterizes each as consequential damages, and requests dismissal of those categories. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The brief expressly raises MSLSA § 8.2 multiple times and argues in Part VI.D that it bars indirect, incidental, special, consequential, punitive, or exemplary damages, specifically identifying Arcadia’s $18.4M lost profits, $6.7M increased operating costs, and $5M reputational harm as consequential or waived categories.

### C-033

ISSUE_006 — Enforceability of limitation provisions between commercially sophisticated parties ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L281))

- **Sonnet 4.6: Pass.** The motion brief explicitly argues that the limitation of liability and consequential damages waiver provisions are enforceable. In Part IV.A, the brief discusses the non-reliance clause and notes that every Forest Oil circumstance appears on the face of the FAC, including that Arcadia 'retained outside counsel who negotiated the agreement over several weeks and sought changes to the liability and warranty terms.' In Part VI.D, the brief argues that Section 8.2 bars consequential damages and that Delaware 'respects the parties' freedom to define and limit contractual remedies,' citing Abry Partners. The Background section also establishes that Arcadia is a sophisticated $62 million-revenue enterprise that engaged outside counsel during negotiation. The MSLSA § 12.1 is quoted as recording that 'each party has been represented by counsel.' These arguments collectively establish enforceability of the limitation provisions based on the parties' sophistication and counsel representation.
- **GPT-5.5: Pass.** The brief argues that the MSLSA’s risk-allocation terms, including the consequential-damages waiver and liability limitations, should be enforced/dismiss damages claims under §§ 8.1–8.2. It expressly frames the agreement as negotiated by sophisticated commercial parties with counsel, notes Arcadia engaged outside counsel and negotiated liability/warranty terms, and later relies on the contractual waiver to bar lost profits, goodwill/reputational damages, increased costs, and punitive damages.

### C-034

ISSUE_007 — Deemed acceptance under Section 5.3 argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L289))

- **Sonnet 4.6: Fail.** The motion brief does not raise any argument about deemed acceptance under Section 5.3. While the brief mentions that Arcadia reported problems in writing on March 8, 2023, it does not argue that Arcadia is deemed to have accepted the software because it failed to deliver written notice of material nonconformity within a 30-day acceptance testing window (January 15 to February 14, 2023). The Section 5.3 deemed acceptance argument is entirely absent from the brief.
- **GPT-5.5: Fail.** The brief mentions Go-Live on January 15, 2023 and a written complaint on March 8, 2023, but it does not raise or argue a deemed-acceptance defense under MSLSA § 5.3, nor does it state that Arcadia failed to provide written notice of material nonconformity within the January 15–February 14, 2023 acceptance testing window. The required deemed acceptance argument is absent.

### C-035

ISSUE_007 — Correctly identifies the 30-day window dates ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L297))

- **Sonnet 4.6: Fail.** The criterion requires the motion to correctly identify: (1) Go-Live as January 15, 2023, (2) the acceptance window end as approximately February 14, 2023 (30 days later), and (3) the first written complaint as March 8, 2023. The brief correctly identifies Go-Live as January 15, 2023 (FAC ¶ 45) and the first written complaint as March 8, 2023 (FAC ¶¶ 49-53). However, the brief does not mention or calculate the 30-day acceptance window end date of approximately February 14, 2023. The brief references the § 9.1 warranty and its 90-day post-Go-Live period, and notes that Arcadia reported issues in writing on March 8, 2023, but it never identifies or discusses the 30-day acceptance window or the February 14, 2023 date. Since the criterion requires the brief to correctly identify all three dates including the acceptance window end date, and the brief omits the February 14, 2023 date entirely, this fails the criterion.
- **GPT-5.5: Fail.** The brief identifies Go-Live as January 15, 2023 and the first written complaint as March 8, 2023, but it does not identify the 30-day acceptance window ending approximately February 14, 2023 or state that March 8 was 22 days after the window expired. Thus it does not satisfy the specified date-window criterion.

### C-036

ISSUE_008 — Integration clause / parol evidence rule argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L305))

- **Sonnet 4.6: Pass.** The motion brief extensively argues that MSLSA Section 12.1 (the integration/merger clause) bars Arcadia from relying on pre-sale oral representations and extra-contractual statements. In the Introduction, the brief notes that Section 12.1 'supersedes all prior . . . proposals, representations, and understandings, whether oral or written,' specifically including 'marketing materials, product descriptions, brochures, presentations, and demonstrations.' In Part IV.A, the brief argues that the non-reliance/integration clause bars the fraud claim, citing Italian Cowboy and Forest Oil, and explaining that Section 12.1 enumerates the exact categories on which Count II is built—'proposals,' 'marketing materials, product descriptions, brochures, presentations, and demonstrations,' and 'oral discussions, negotiations, and representations.' The brief also invokes Section 12.1 to bar the DTPA express-warranty theory (Part II), the unjust enrichment claim (Part III), the negligent misrepresentation claim (Part V), and the nondisclosure theory (Part IV.D). While the brief frames this primarily as a non-reliance/disclaimer argument rather than explicitly labeling it 'parol evidence rule,' the substance of the argument—that Section 12.1 bars Arcadia from relying on pre-sale oral representations or promises as contractual terms by superseding all prior agreements—satisfies the criterion.
- **GPT-5.5: Fail.** The brief discusses MSLSA § 12.1 extensively as a merger/non-reliance clause to defeat fraud, negligent misrepresentation, and DTPA theories, and notes that prior marketing materials and presentations were superseded. But it does not make the required contract/parol-evidence argument that § 12.1 bars Arcadia from treating pre-sale oral representations or promises as contractual terms, nor does it invoke the parol evidence rule to exclude prior or contemporaneous agreements. The integration clause is used mainly as an anti-reliance defense, not as the specified parol-evidence/contract-terms argument.

### C-037

ISSUE_008 — Cites Delaware parol evidence authority ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L313))

- **Sonnet 4.6: Fail.** The criterion requires citation of relevant Delaware authority on the parol evidence rule and integration clauses, specifically mentioning cases like SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care. The motion cites Delaware cases including Abry Partners V, L.P. v. F & W Acquisition LLC (891 A.2d 1032, Del. Ch. 2006), Kuroda v. SPJS Holdings, L.L.C. (971 A.2d 872, Del. Ch. 2009), and VLIW Tech., LLC v. Hewlett-Packard Co. (840 A.2d 606, Del. 2003). While Abry Partners and Kuroda are cited for anti-reliance/non-reliance clauses and unjust enrichment, neither SIGA Technologies v. PharmAthene nor Eagle Industries v. DeVilbiss Health Care (the specific cases mentioned in the criterion) are cited. The criterion explicitly asks for those specific cases or similar Delaware parol evidence rule authority. The cases cited (Abry Partners, Kuroda) touch on related but distinct issues (anti-reliance clauses, unjust enrichment) rather than the parol evidence rule and integration clauses specifically. The criterion fails because the specifically named cases are not present and no Delaware authority specifically addressing the parol evidence rule and integration clauses is cited.
- **GPT-5.5: Fail.** The brief cites Delaware cases such as Abry, Kuroda, and VLIW, but it does not cite Delaware parol-evidence/integration-clause authority like SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care, nor any equivalent Delaware parol evidence rule case.

### C-038

ISSUE_009 — Negligent misrepresentation requires independent duty ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L321))

- **Sonnet 4.6: Fail.** The motion's treatment of Count III (Section V) does not raise an independent duty argument. It argues Count III fails because: (1) Rule 9(b) applies and the claim fails for the same reasons as fraud; (2) the non-reliance clause negates justifiable reliance; (3) puffery and future predictions are not actionable; and (4) the damages sought are benefit-of-the-bargain damages unavailable for negligent misrepresentation. Nowhere does the brief argue that Meridian owed no duty to Arcadia independent of the contractual relationship, or that arm's-length commercial transactions between sophisticated parties give rise to no such independent duty. The independent duty argument is simply not raised.
- **GPT-5.5: Fail.** The brief's Count III section argues Rule 9(b), lack of justifiable reliance due to non-reliance, puffery/future predictions, and unavailable benefit-of-the-bargain damages. It does not argue that Meridian owed no duty independent of the contract or that no such independent duty exists in an arm's-length transaction between sophisticated commercial parties. Although the brief discusses lack of a disclosure duty in the fraud-by-omission section, it does not raise the required independent-duty argument for negligent misrepresentation.

### C-039

ISSUE_009 — Notes absence of fiduciary/special relationship ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L329))

- **Sonnet 4.6: Pass.** In Part IV.D, the brief explicitly states: 'Texas generally imposes no such duty between parties dealing at arm's length absent a confidential or fiduciary relationship. See Bombardier Aerospace Corp. v. SPEP Aircraft Holdings, LLC, 572 S.W.3d 213, 219–20 (Tex. 2019). The FAC pleads no such relationship.' This directly addresses the absence of a fiduciary or special relationship and characterizes the parties as dealing at arm's length. Additionally, throughout the brief (Parts IV.A, II, etc.), the parties are described as sophisticated commercial parties with Arcadia represented by counsel, reinforcing the arm's-length nature of their relationship.
- **GPT-5.5: Pass.** The brief expressly argues that Meridian and Arcadia were sophisticated commercial parties dealing at arm’s length, that Arcadia was represented by outside counsel, and that the FAC pleads no confidential or fiduciary relationship. It specifically uses this point to defeat the fraud-by-omission duty-to-disclose theory.

### C-040

ISSUE_009 — Cites Texas negligent misrepresentation authority ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L337))

- **Sonnet 4.6: Pass.** The brief cites both McCamish, Martin, Brown & Loeffler v. F.E. Appling Interests, 991 S.W.2d 787 (Tex. 1999) and Fed. Land Bank Ass'n of Tyler v. Sloane, 825 S.W.2d 439 (Tex. 1991) in Count V (negligent misrepresentation) section, using them to support arguments about justifiable reliance and the limitation of damages to out-of-pocket reliance losses rather than benefit-of-the-bargain damages.
- **GPT-5.5: Pass.** The brief cites Texas negligent misrepresentation authorities, including McCamish, Martin, Brown & Loeffler v. F.E. Appling Interests and Federal Land Bank Ass'n of Tyler v. Sloane, and discusses elements/damages for negligent misrepresentation in Count III.

### C-041

ISSUE_010 — Causation deficiency re: Linden Park responsibility ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L345))

- **Sonnet 4.6: Fail.** The motion brief addresses data migration responsibility and SOW-1 Section 3.2 in Part VI.A, arguing that Arcadia bore sole responsibility for data migration. However, the brief does not mention Linden Park Consulting at all, nor does it argue that implementation failures were attributable to Linden Park as a third party. The causation argument is framed solely as a contractual allocation issue (Arcadia's own responsibility) rather than as a third-party causation deficiency pointing to Linden Park. The criterion specifically requires the brief to note that many implementation failures are attributable to Linden Park Consulting. Since Linden Park is never mentioned, this argument is not raised.
- **GPT-5.5: Fail.** The brief argues that data migration responsibility was allocated to Arcadia under SOW-1 § 3.2 and related provisions, but it does not raise a third-party causation/proximate-cause argument involving Linden Park Consulting, nor does it argue that many implementation failures are attributable to Linden Park rather than Meridian. The criterion expressly requires the Linden Park/third-party causation argument.

### C-042

ISSUE_010 — Notes SOW-1 Section 3.2 data migration allocation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L353))

- **Sonnet 4.6: Pass.** The motion brief explicitly references SOW-1 Section 3.2 in multiple places. In the Background section (Part A), it states: 'Data migration is assigned to Arcadia: Arcadia must "perform all data migration activities . . . using qualified personnel or a third-party systems integrator retained by Licensee," and Meridian's role is "advisory" only, with "no responsibility or liability" for migrated-data integrity. Id. § 3.4(e) & Ex. C §§ C.1--C.2; SOW-1 §§ 1.2(a), 3.2.' In Part VI.A, it again cites 'MSLSA § 3.4(e) & Ex. C §§ C.1--C.2; SOW-1 §§ 1.2(a), 3.2' when arguing that data migration theories are foreclosed by the contract. SOW-1 Section 3.2 is specifically cited in connection with the allocation of data migration responsibility to Arcadia.
- **GPT-5.5: Pass.** The brief specifically cites SOW-1 § 3.2 multiple times in connection with data migration and states that data migration was assigned to Arcadia, including that Arcadia must perform all data migration activities and that Meridian’s role was only advisory/no responsibility. This satisfies the requirement to reference SOW-1 Section 3.2 and its allocation of data migration responsibility to Arcadia.

### C-043

ISSUE_010 — References CO-004 as evidence of Linden Park errors ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L361))

- **Sonnet 4.6: Fail.** The motion brief mentions Change Orders CO-001 through CO-004 collectively in several places (e.g., in the argument about mutually executed Change Orders not constituting a breach, and in the conclusion/prayer), but it never specifically references CO-004 ($900,000 for data remediation) as evidence that implementation failures were caused by Linden Park's (or Arcadia's) data migration errors rather than by Meridian's software or services. The data migration argument in Part VI.A relies on the MSLSA contract language assigning responsibility to Arcadia, not on CO-004 as evidentiary support for that position. The criterion requires CO-004 to be cited in this specific context, which it is not.
- **GPT-5.5: Fail.** The brief mentions Change Orders CO-001 through CO-004 generally and argues data migration was Arcadia's responsibility, but it does not specifically cite CO-004, does not identify it as a $900,000 data-remediation change order, and does not use it as evidence that implementation failures were caused by Linden Park's data migration errors rather than Meridian's software or services.

### C-044

ISSUE_010 — Notes FAC's failure to name Linden Park ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L369))

- **Sonnet 4.6: Fail.** The motion brief does not mention Linden Park Consulting or argue that the FAC improperly attributes implementation failures to 'Meridian and its agents' while failing to acknowledge Arcadia's own independently retained third-party integrator. The brief discusses data migration obligations being assigned to Arcadia and references that Arcadia could retain 'a third-party systems integrator retained by Licensee,' but never specifically identifies Linden Park Consulting or highlights the FAC's omission of naming that entity as Arcadia's own contractor responsible for implementation failures.
- **GPT-5.5: Fail.** The brief argues that data migration was Arcadia’s responsibility and references a possible third-party systems integrator retained by Arcadia, but it does not name Linden Park Consulting or specifically highlight that the FAC attributes implementation failures to “Meridian and its agents” while omitting Arcadia’s independently retained integrator.

### C-045

ISSUE_010 — References Arcadia's own delays contributing to Go-Live delay ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L377))

- **Sonnet 4.6: Fail.** The motion brief does not mention Arcadia's own contributing delays to the Go-Live delay, such as the 45-day Project Manager gap (Kevin Liu's departure) or the 75-day late API specifications. The brief discusses the Go-Live delay (September 1, 2022 target vs. January 15, 2023 actual) but does not attribute any portion of that delay to Arcadia's own failures or contributory conduct.
- **GPT-5.5: Fail.** The brief mentions that Go-Live occurred later than the target date and argues generally that data migration was Arcadia’s responsibility, but it does not identify Arcadia’s own contributing delay facts, such as the 45-day Project Manager gap from Kevin Liu’s departure or the 75-day late API specifications, as causes of the Go-Live delay.

### C-046

ISSUE_011 — Puffery defense raised for fraud/DTPA claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L385))

- **Sonnet 4.6: Pass.** The motion brief explicitly raises the puffery defense in Section IV.B ('The core statements are non-actionable puffery or opinion'). It specifically addresses the 'industry-leading performance for healthcare analytics' statement, calling it 'a quintessential unverifiable claim of superiority,' and addresses the '30-40% improvement' statement, noting it was qualified in the written proposal as a 'performance metric offered for planning purposes only' that did 'not constitute a guarantee.' The brief cites relevant authority including Pizza Hut, Prudential, and Presidio for the puffery doctrine. The puffery defense is also incorporated by reference into the DTPA analysis in Section II.
- **GPT-5.5: Pass.** The brief expressly raises a puffery/non-actionable opinion defense for fraud, identifying “industry-leading performance” as “quintessential” unverifiable superiority puffery and addressing the “30-40% improvement” statement as qualified, planning-only, and not a guarantee. It also applies the same puffery argument to the DTPA claim, stating the DTPA characteristics-and-quality theories rest on the same non-actionable puffery.

### C-047

ISSUE_011 — References disclaimers in sales materials/proposal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L393))

- **Sonnet 4.6: Pass.** The motion brief explicitly quotes the disclaimer from the December 9, 2021 written proposal: 'estimated timelines and performance metrics are provided for planning purposes only and do not constitute guarantees,' and also notes that the proposal described integration 'with major EHR platforms through our standard API framework, subject to proper configuration.' These are cited in the Background section and again in Part IV.B when arguing that the '30-40% improvement' statement was expressly qualified in the written proposal Arcadia received before signing, undercutting reasonable reliance.
- **GPT-5.5: Pass.** The brief expressly cites Meridian’s December 9, 2021 written proposal disclaimer that estimated timelines and performance metrics were for planning purposes only and did not constitute guarantees, and uses it in the fraud/reliance discussion to undercut Arcadia’s reliance on pre-sale statements.

### C-048

ISSUE_011 — Cites puffery case law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L401))

- **Sonnet 4.6: Pass.** The brief cites Pizza Hut, Inc. v. Papa John's Int'l, Inc., 227 F.3d 489 (5th Cir. 2000) and Presidio Enters., Inc. v. Warner Bros. Distrib. Corp., 784 F.2d 674 (5th Cir. 1986) in Part IV.B on puffery, satisfying the criterion.
- **GPT-5.5: Pass.** The motion brief cites multiple puffery cases, including Pizza Hut, Inc. v. Papa John's Int'l, Inc. and Presidio Enterprises, Inc. v. Warner Bros. Distrib. Corp., and applies them in the puffery argument.

### C-049

ISSUE_012 — Choice of law addressed for contract claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L409))

- **Sonnet 4.6: Pass.** The motion brief explicitly addresses choice of law in Section I (Choice of Law), stating: 'A federal court sitting in diversity applies the forum state's choice-of-law rules. Klaxon Co. v. Stentor Elec. Mfg. Co., 313 U.S. 487, 496 (1941). Texas enforces contractual choice-of-law clauses under Restatement (Second) of Conflict of Laws § 187. DeSantis v. Wackenhut Corp., 793 S.W.2d 670, 677–78 (Tex. 1990). Delaware law therefore governs construction of the MSLSA and Count I. MSLSA § 12.7.' This directly addresses that Delaware law governs Count I (Breach of Contract) pursuant to the MSLSA's Section 12.7 choice-of-law clause. Additionally, Section VI on Count I applies Delaware breach-of-contract law, citing VLIW Tech., LLC v. Hewlett-Packard Co., 840 A.2d 606, 612 (Del. 2003).
- **GPT-5.5: Pass.** The brief includes a dedicated Choice of Law section stating that Section 12.7 of the MSLSA selects Delaware law and that Delaware law therefore governs construction of the MSLSA and Count I for breach of contract.

### C-050

ISSUE_012 — Addresses choice of law for tort claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L417))

- **Sonnet 4.6: Pass.** The motion explicitly addresses choice of law in Section I. It cites Klaxon and DeSantis for the framework, then specifically notes that the Fifth Circuit has read a clause governing 'this Agreement' as not necessarily reaching related tort claims (citing Benchmark, 343 F.3d at 726-27), and acknowledges that the FAC pleads Texas law for Counts II-V. Meridian accepts that framing for the motion but notes the result is the same under either state's law, citing both Texas and Delaware authorities on non-reliance clauses and quasi-contract. This directly addresses the choice-of-law question for the tort claims and argues under both Delaware and Texas law.
- **GPT-5.5: Pass.** The brief expressly includes a Choice of Law section acknowledging that the MSLSA’s Delaware choice-of-law clause may govern only the agreement and may not extend to related tort claims under Fifth Circuit authority. It states that the FAC pleads Texas law for Counts II–V and Meridian accepts that framing for the motion, while also noting the result would be the same under Delaware law. The fraud argument further addresses Delaware law in the alternative. This satisfies the requirement to address choice of law for the tort claims.

### C-051

ISSUE_012 — Recognizes DTPA is necessarily Texas law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L425))

- **Sonnet 4.6: Pass.** The brief explicitly treats Count V (DTPA) as governed by Texas law. In the Choice of Law section (Part I), the brief notes that 'the FAC pleads Texas law for Counts II–V' and that 'Meridian accepts that framing for this motion.' The DTPA analysis in Part II then applies Texas statutory standards throughout, citing Tex. Bus. & Com. Code §§ 17.49(f) and (g) and Texas case law. The brief never suggests Delaware law governs the DTPA claim.
- **GPT-5.5: Pass.** The brief treats Count V (DTPA) as governed by Texas law, expressly citing and applying Texas Business & Commerce Code §§ 17.49(f) and (g) and other Texas DTPA standards. It does not argue that the DTPA claim is governed by Delaware law.

### C-052

ISSUE_012 — Arguments work under both Delaware and Texas law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L433))

- **Sonnet 4.6: Pass.** The brief explicitly addresses the choice-of-law question in Section I and then argues in the alternative throughout. In the Choice of Law section, it notes that Delaware law governs the MSLSA (Count I) while Texas law governs Counts II-V per the FAC's own framing, but then states 'The result is the same under either State's law' and cites both Texas and Delaware authorities for the non-reliance/disclaimer and unjust enrichment points. For Count IV (unjust enrichment), it cites both Fortune Prod. (Texas) and Kuroda (Delaware). For Count II (fraud/non-reliance), it addresses Texas law in Part IV.A and then adds 'The same result follows under Delaware law, should the Court apply it,' citing Abry Partners. The brief consistently demonstrates that the arguments succeed under both states' laws where the choice matters.
- **GPT-5.5: Pass.** The brief includes a choice-of-law section and, for key disputed issues, expressly argues that the result is the same under Texas and Delaware law. It cites both Texas and Delaware authorities for non-reliance/anti-reliance and unjust enrichment, and it separately notes that Delaware law would also bar the fraud theory if applied. Although not every sub-argument is developed under both states’ law, the brief does not rely exclusively on one state’s law and does provide alternative-law treatment where most relevant.

### C-053

Motion brief — argues reliance was unreasonable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L441))

- **Sonnet 4.6: Pass.** The brief extensively argues that Arcadia's reliance on pre-sale representations was unreasonable/unjustifiable as a matter of law. In Section IV.A, it cites Italian Cowboy and Forest Oil to argue that the non-reliance clause bars fraud claims, and specifically identifies the Forest Oil factors: Arcadia is a $62 million-revenue enterprise, it conducted its own due diligence (reference calls), it retained outside counsel who negotiated the agreement and sought changes to liability and warranty terms, and the parties dealt at arm's length. Section 9.4 of the MSLSA records Arcadia's acknowledgment that it 'relied on its own due diligence and evaluation in selecting the Licensed Software.' The brief also notes the written proposal's disclaimers (App. 3) and the integration/merger clause (MSLSA § 12.1). These arguments collectively challenge the reasonableness/justifiability of Arcadia's reliance based on due diligence, counsel representation, written disclaimers, and the integration clause.
- **GPT-5.5: Pass.** The brief expressly challenges justifiable/reasonable reliance as a matter of law. It argues that Arcadia contractually disclaimed reliance on pre-sale representations, cites the integration/non-reliance clause and written proposal disclaimers, and invokes factors including Arcadia's independent due diligence, representation by outside counsel during negotiations, sophistication, and arm's-length negotiations. It also applies these arguments to the fraud and negligent misrepresentation claims.

### C-054

Motion brief — references Schreiber memo to undermine reliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L449))

- **Sonnet 4.6: Fail.** The motion brief does not reference Martin Schreiber's internal due diligence memo or the quoted language 'Integration complexity is manageable but will require a skilled SI partner' anywhere in the document. The brief mentions Arcadia's CTO conducting due diligence and reference calls (FAC ¶ 31), but does not cite the Schreiber memo specifically.
- **GPT-5.5: Fail.** The motion brief discusses Arcadia's due diligence generally and cites FAC ¶ 31, but it does not reference Martin Schreiber's internal due diligence memo or the quoted acknowledgment that integration complexity was manageable but required a skilled SI partner. Therefore it does not satisfy the specified criterion.

### C-055

Motion brief — exclusive remedies clause (Section 8.3) cited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L457))

- **Sonnet 4.6: Pass.** In Section VI.C of the brief, the agent writes: 'MSLSA § 9.1(b); see id. §§ 8.3, 12.20.' This explicitly cites Section 8.3 in the context of the exclusive remedy provision, satisfying the criterion that Section 8.3 be referenced as limiting Arcadia to the remedies set forth in the MSLSA as its sole and exclusive remedies.
- **GPT-5.5: Pass.** The brief expressly mentions and cites MSLSA § 8.3 in the section arguing that software-performance theories are limited to the contract’s exclusive remedies, alongside § 9.1(b) and § 12.20. This satisfies the requirement that Section 8.3 be referenced as supporting exclusive-remedy limitations.

### C-056

Motion brief — warranty disclaimer (Section 9.4) cited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L465))

- **Sonnet 4.6: Pass.** Section 9.4 is explicitly referenced multiple times in the brief. In the Background section, it is described as disclaiming all warranties other than the limited warranty of § 9.1 and recording Arcadia's acknowledgment that it 'relied on its own due diligence and evaluation in selecting the Licensed Software.' In Part IV.A, Section 9.4 is cited alongside Section 12.1 as part of the non-reliance/disclaimer framework. In Part VI.C, Section 9.4 is cited as disclaiming all other warranties, including any warranty that the software 'will meet Licensee's requirements or expectations' or 'operate without interruption or be error-free.' These references clearly satisfy the criterion of citing Section 9.4 as barring or limiting warranty-based claims.
- **GPT-5.5: Pass.** The brief references MSLSA § 9.4 multiple times as a warranty disclaimer, stating that it disclaims all warranties other than the limited § 9.1 warranty and using it to limit or bar warranty-based theories, including DTPA express-warranty and software-performance theories.

### C-057

Motion brief — limited warranty scope (Section 9.1) analyzed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L473))

- **Sonnet 4.6: Pass.** Section VI.C of the brief explicitly discusses MSLSA § 9.1, describing the 90-day post-Go-Live warranty that software will perform substantially in accordance with Documentation, and specifying that the 'sole and exclusive remedy' is repair, replacement, or a pro-rata refund of pre-paid license fees if cure fails within 60 days of written notice. It also references § 9.4's disclaimer of all other warranties and argues that software-performance breach theories are limited to this exclusive remedy. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The brief expressly analyzes MSLSA Section 9.1 in the breach-of-contract section, explaining that software-performance/warranty theories are subject to the 90-day limited warranty and limited to repair, replacement, or a pro-rata refund if Meridian cannot cure within 60 days, as the sole and exclusive remedy.

### C-058

Motion brief — no oral modifications clause (Section 12.3) cited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L481))

- **Sonnet 4.6: Fail.** The motion brief does not reference Section 12.3 (No Oral Modifications) anywhere in the document. The brief relies on Section 12.1 (integration/non-reliance clause) and Section 9.4 (warranty disclaimer) to argue that pre-sale statements cannot be relied upon, but never cites Section 12.3 as supporting the argument that pre-sale oral statements cannot modify or supplement the written agreement.
- **GPT-5.5: Fail.** The motion brief does not cite or reference MSLSA Section 12.3 (No Oral Modifications) anywhere, nor does it use that section to argue that pre-sale oral statements cannot modify or supplement the written agreement.

### C-059

Proposed order — correct court identification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L489))

- **Sonnet 4.6: Pass.** The proposed order clearly states 'IN THE UNITED STATES DISTRICT COURT FOR THE WESTERN DISTRICT OF TEXAS AUSTIN DIVISION' in the header, which matches the required court identification exactly.
- **GPT-5.5: Pass.** The proposed order caption states “IN THE UNITED STATES DISTRICT COURT” and “FOR THE WESTERN DISTRICT OF TEXAS” followed by “AUSTIN DIVISION,” which matches the required court identification.

### C-060

Proposed order — correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L497))

- **Sonnet 4.6: Pass.** The proposed order clearly includes the case number '1:23-cv-00847-CMA' in the caption header, which matches the correct case number specified in the criterion.
- **GPT-5.5: Pass.** The proposed order caption includes the case number “Civil Action No. 1:23-cv-00847-CMA,” which exactly matches the required case number.

### C-061

Proposed order — correct party names ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L505))

- **Sonnet 4.6: Pass.** The proposed order clearly includes both correct party names: 'ARCADIA HEALTH SYSTEMS, LLC' as Plaintiff and 'MERIDIAN CLOUD SOLUTIONS, INC.' as Defendant, appearing in the case caption and throughout the document.
- **GPT-5.5: Pass.** The proposed order caption and body include the correct party names: Arcadia Health Systems, LLC as Plaintiff and Meridian Cloud Solutions, Inc. as Defendant.

### C-062

Proposed order — grants dismissal of all five counts ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L513))

- **Sonnet 4.6: Fail.** The proposed order addresses all five counts: Count I (Breach of Contract) - dismissed with prejudice (at least partially, with an alternative provision for full dismissal); Count II (Fraud) - dismissed with prejudice; Count III (Negligent Misrepresentation) - dismissed with prejudice; Count IV (Unjust Enrichment) - dismissed with prejudice; Count V (DTPA) - dismissed with prejudice. However, Count I is only partially dismissed in the primary disposition (paragraphs 5-6), with a bracketed alternative for full dismissal. The criterion requires the proposed order to grant dismissal of all five counts. The primary disposition does not fully dismiss Count I - it only dismisses specific portions and leaves the remainder to proceed (as noted in the bracketed clause '[Except as provided in paragraphs 5 and 6, Count I shall proceed.]'). The full dismissal of Count I is only presented as an alternative. Since the primary order does not grant full dismissal of Count I, the criterion is not fully satisfied in the primary disposition. However, the order does include an alternative paragraph that would fully dismiss Count I. The criterion says 'grants dismissal of all five counts' - the primary order only partially dismisses Count I while the alternative fully dismisses it. This is a borderline case, but since the primary order does not fully dismiss all five counts (Count I survives in part), I'll consider this a FAIL.
- **GPT-5.5: Fail.** The proposed order dismisses Fraud, Negligent Misrepresentation, Unjust Enrichment, and DTPA, but it only partially dismisses the Breach of Contract count and states that Count I shall otherwise proceed. The bracketed alternative full dismissal does not make the operative order grant dismissal of all five counts.

### C-063

Proposed order — dismissal with prejudice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L521))

- **Sonnet 4.6: Pass.** The proposed order explicitly specifies 'DISMISSED WITH PREJUDICE' for all counts (Count I through Count V), including the partial dismissals of Count I and the alternative full dismissal of Count I. Every dismissal in the order is with prejudice, satisfying the criterion.
- **GPT-5.5: Pass.** The proposed order repeatedly specifies that the dismissed counts and claims are DISMISSED WITH PREJUDICE, including Counts II–V and portions or all of Count I.

### C-064

Cover memo — identifies Meridian's Texas citizenship ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L529))

- **Sonnet 4.6: Pass.** The cover memo explicitly identifies Meridian as 'a citizen of Delaware (where it is incorporated) and Texas (its principal place of business)' in the jurisdiction table, with the source cited as '28 U.S.C. § 1332(c)(1); Notice of Removal ¶¶ 9--11; Answer ¶ 5; Hertz Corp. v. Friend, 559 U.S. 77 (2010)'. It also notes Meridian's principal place of business is Austin in the procedural discussion. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The cover memo explicitly states that Meridian is a citizen of Delaware and Texas, noting it is a Delaware corporation with its principal place of business in Austin, Texas.

### C-065

Cover memo — notes that subject-matter jurisdiction cannot be waived ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L537))

- **Sonnet 4.6: Pass.** The cover memo explicitly states in Section II.A: 'Parties cannot waive, consent to, or cure a lack of subject-matter jurisdiction. The Court must remand "[i]f at any time before final judgment it appears that the district court lacks subject matter jurisdiction." 28 U.S.C. § 1447(c); Fed. R. Civ. P. 12(h)(3).' It also notes that 'The Court cannot decide the 12(b)(6) motion by assuming it has jurisdiction' and cites Steel Co. v. Citizens for a Better Env't. This clearly addresses both the non-waivable nature of subject-matter jurisdiction and the court's ability to raise it sua sponte (via Fed. R. Civ. P. 12(h)(3)).
- **GPT-5.5: Pass.** The cover memo expressly states that parties cannot waive, consent to, or cure a lack of subject-matter jurisdiction, cites remand/Rule 12(h)(3) provisions for raising it at any time, and notes the Court can raise the issue on its own.

### C-066

Cover memo — discusses strategic implications of raising jurisdiction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L545))

- **Sonnet 4.6: Pass.** The cover memo extensively discusses the strategic implications of the jurisdictional defect. Section II.A addresses: (1) the risk that the court can raise the issue on its own at any time including on appeal, making any merits ruling voidable; (2) fee and cost exposure under Martin v. Franklin Capital Corp. if remand is ordered; (3) Rule 11 exposure; (4) the ethical obligation not to continue litigating on the merits while knowing of the jurisdictional defect; (5) the consequences of remand to state court (Bexar County, 73rd District Court), including different procedural rules (Rule 91a likely unavailable, special exceptions instead, venue transfer issues, jury waiver enforceability). The memo also notes that the research memo suggested weighing whether Meridian 'benefits more' from federal or state court, and explicitly states that is not a legitimate option. The memo discusses what happens after remand in state court with different procedural mechanisms. This constitutes robust strategic analysis of the jurisdictional issue and its implications.
- **GPT-5.5: Pass.** The cover memo directly addresses the jurisdictional defect’s strategic consequences: likely remand under § 1447(c), inability to obtain a safe merits ruling in federal court, risk the court raises the issue sua sponte, potential fee/Rule 11 exposure, and practical implications after remand such as Texas venue, Rule 91a unavailability, special exceptions, and summary judgment strategy. This satisfies the criterion.

### C-067

Factual accuracy — contract value stated as $14.7 million ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L553))

- **Sonnet 4.6: Pass.** The motion brief correctly identifies the MSLSA total contract value as $14.7 million in multiple places, including the Introduction ('signed a $14.7 million agreement') and the Background section ('total contract value of $14.7 million').
- **GPT-5.5: Pass.** The motion brief correctly identifies the MSLSA total contract value as $14.7 million, including in the Introduction, Background, and DTPA argument.

### C-068

Factual accuracy — change orders total $2.35 million ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L561))

- **Sonnet 4.6: Pass.** The motion brief correctly identifies the change order total as $2,350,000 (or $2.35 million) in multiple places, including 'four Change Orders totaling $2.35 million' in the Introduction, '$2.35 million in Change Orders' in the Background, and 'Change Orders totaling $2,350,000' in the DTPA section and the breach of contract section. This matches the correct sum of CO-001 ($680,000) + CO-002 ($420,000) + CO-003 ($350,000) + CO-004 ($900,000) = $2,350,000.
- **GPT-5.5: Pass.** The motion brief repeatedly identifies the four Change Orders as totaling $2.35 million / $2,350,000, which matches the required total.

### C-069

Factual accuracy — total claimed damages $47.3 million ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L569))

- **Sonnet 4.6: Pass.** The motion brief correctly states the total claimed damages as $47.3 million (or $47,300,000) in multiple places: in the Introduction ('pursues a $47.3 million contract claim'), in the Background section ('Arcadia seeks $47.3 million'), and in the argument section on Count III ('seeks "no less than $47,300,000"'). This matches the criterion requirement.
- **GPT-5.5: Pass.** The motion brief repeatedly states that Arcadia seeks or pursues $47.3 million / $47,300,000 in damages, matching the required total claimed damages figure.

### C-070

Factual accuracy — MSLSA execution date March 15, 2022 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L577))

- **Sonnet 4.6: Pass.** The motion brief states in the Background section: 'On March 15, 2022, the parties executed the MSLSA and SOW-1, with a total contract value of $14.7 million.' This correctly states the MSLSA execution date as March 15, 2022. The Appendix index also references 'Master Software License and Services Agreement dated March 15, 2022.' The date is consistently and correctly stated throughout the document.
- **GPT-5.5: Pass.** The motion brief correctly states that the parties executed the MSLSA on March 15, 2022, including in the background section and appendix index.

### C-071

Factual accuracy — Go-Live date January 15, 2023 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L585))

- **Sonnet 4.6: Pass.** The brief explicitly states 'Go-Live occurred on January 15, 2023' in the Background section (Part C), which correctly identifies the actual Go-Live date as January 15, 2023.
- **GPT-5.5: Pass.** The motion brief correctly states that Go-Live occurred on January 15, 2023, including in the Background section: “Arcadia alleges that Go-Live occurred on January 15, 2023 rather than the September 1, 2022 target.”

### C-072

Factual accuracy — first written complaint March 8, 2023 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L593))

- **Sonnet 4.6: Pass.** The motion brief states at page 8 (Background section C): 'after Go-Live Arcadia experienced latency and report errors, which it reported in writing on March 8, 2023.' This correctly identifies March 8, 2023 as the date of the first written complaint. The criterion requires the brief to correctly identify Arcadia's first written complaint as the March 8, 2023 email. The brief does reference this date accurately, though it does not specifically name Dr. Okonkwo as the sender. However, the criterion only requires the date to be correctly identified, which it is.
- **GPT-5.5: Pass.** The brief states that Arcadia reported the post-Go-Live issues in writing on March 8, 2023. Although it does not name Dr. Okonkwo or specify that it was an email, the date is correctly identified and not materially incorrect.

### C-073

Factual accuracy — Delaware governs per Section 12.7 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L601))

- **Sonnet 4.6: Pass.** The brief explicitly states in the Background section: 'Section 12.7 selects Delaware law to govern "this Agreement."' It also references this in the Choice of Law section: 'Delaware law therefore governs construction of the MSLSA and Count I. MSLSA § 12.7.' The brief correctly identifies Section 12.7 as the governing law clause and correctly states that it specifies Delaware law.
- **GPT-5.5: Pass.** The brief correctly identifies MSLSA Section 12.7 as selecting Delaware law to govern the agreement and applies Delaware law to contract construction/Count I.

### C-074

Factual accuracy — Arcadia represented by counsel during negotiations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L609))

- **Sonnet 4.6: Pass.** The motion brief explicitly mentions that Arcadia engaged outside counsel during contract negotiations in multiple places. For example, in the Background section: 'Arcadia "engaged outside counsel to assist in the negotiation process," during which it sought "enhanced limitation of liability provisions and expanded warranty protections."' It also references this in the DTPA section and the fraud section. However, the brief does not specifically identify the outside counsel as Wexford Hale LLP during negotiations — it only identifies Wexford Hale LLP as current litigation counsel in the Certificate of Service. The criterion asks whether the brief notes that Arcadia was represented by outside counsel during contract negotiations, which it does clearly state, even if it doesn't name the firm as Wexford Hale LLP. The criterion says 'PASS if the motion brief notes that Arcadia was represented by outside counsel (Wexford Hale LLP) during contract negotiations' — the parenthetical appears to be identifying which firm, but the core requirement is that outside counsel representation is noted. The brief does note this fact clearly and repeatedly.
- **GPT-5.5: Fail.** The brief repeatedly states that Arcadia engaged or was represented by outside counsel during negotiations, but it does not identify that outside counsel as Wexford Hale LLP in connection with the negotiations. Wexford Hale LLP is mentioned only as current counsel in the certificate of service.

### C-075

Factual accuracy — 47 support tickets breakdown correct ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L617))

- **Sonnet 4.6: Fail.** The motion brief does not reference the support ticket data at all — there is no mention of 47 total tickets, 31 resolved within SLA, 12 related to data quality/Linden Park Consulting, or 4 software defects patched. The criterion states FAIL if the ticket data is cited but materially misstated, but the brief simply does not cite this data. However, the criterion asks to PASS only if the brief 'references the support ticket data with substantially correct figures.' Since the brief does not reference the ticket data at all, it does not satisfy the PASS condition.
- **GPT-5.5: Fail.** The brief does not reference the support-ticket breakdown at all—there is no mention of 47 total tickets, 31 resolved within SLA, 12 data-quality/Linden Park tickets, or 4 software defects patched. Thus it does not satisfy the criterion requiring the ticket data to be referenced with substantially correct figures.

### C-076

Motion brief — requests dismissal with prejudice rather than without ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L625))

- **Sonnet 4.6: Pass.** The Conclusion and Prayer section explicitly requests dismissal with prejudice for Counts II, III, IV, and V: 'dismiss Counts II, III, IV, and V of the First Amended Complaint with prejudice.' Additionally, within the body of the brief, Count V (DTPA) is specifically argued to warrant dismissal with prejudice because 'amendment cannot alter the size of the transaction or Arcadia's own allegation that it was represented by counsel,' and Count IV (unjust enrichment) is argued to be dismissed with prejudice. The brief satisfies the criterion by requesting dismissal with prejudice for the counts where it is appropriate.
- **GPT-5.5: Pass.** The motion expressly requests dismissal with prejudice for Counts II, III, IV, and V, and specifically argues that the DTPA and unjust enrichment counts should be dismissed with prejudice. It does not merely request dismissal without prejudice across the board.

### C-077

Motion brief — identifies Rule 12(b)(6) as the procedural vehicle ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L633))

- **Sonnet 4.6: Pass.** The motion brief explicitly identifies Federal Rule of Civil Procedure 12(b)(6) in its title ('MOTION TO DISMISS THE FIRST AMENDED COMPLAINT PURSUANT TO FEDERAL RULE OF CIVIL PROCEDURE 12(b)(6)'), in the opening paragraph ('Fed. R. Civ. P. 12(b)(6), 12(h)(2)'), in the Legal Standard section, and throughout the brief. The procedural vehicle is clearly and repeatedly identified.
- **GPT-5.5: Pass.** The brief is explicitly titled as a motion to dismiss pursuant to Federal Rule of Civil Procedure 12(b)(6), and the opening paragraph states that Meridian moves to dismiss for failure to state a claim under Rule 12(b)(6).

### C-078

Motion brief — addresses post-answer motion practice authorization ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L641))

- **Sonnet 4.6: Pass.** The brief explicitly addresses the post-answer motion practice authorization in the 'PROCEDURAL POSTURE AND PRESERVATION OF GROUNDS (STANDING ORDER § 3.4)' section. It notes that Meridian answered the FAC on October 2, 2023, that the Answer expressly asserted failure to state a claim and reserved the right to file a Rule 12(b)(6) motion, and that the grounds presented were preserved in the Answer. It also cites Rule 12(h)(2) and Standing Order § 3.4, and notes that the standard under Rule 12(b)(6) is identical to that under Rule 12(c). This directly addresses the propriety of a post-answer 12(b)(6) motion and confirms defenses were preserved in the Answer.
- **GPT-5.5: Pass.** The brief expressly includes a section titled “PROCEDURAL POSTURE AND PRESERVATION OF GROUNDS (STANDING ORDER § 3.4)” stating that Meridian answered the FAC, preserved failure-to-state-a-claim and related defenses in its Answer, and explaining that the post-answer motion may proceed under Rule 12(b)(6) or alternatively Rule 12(c) consistent with Judge Alvarez’s standing order.

### C-079

Motion brief — argues Count I breach of contract fails with specific contractual provisions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L649))

- **Sonnet 4.6: Pass.** The brief addresses Count I (Breach of Contract) in Section VI and explicitly invokes multiple specific contractual provisions. It references MSLSA § 12.1 (integration clause) in the Background and in Part IV.A, and it extensively cites MSLSA §§ 8.1–8.2 (limitation of liability and consequential damages exclusion) in Part VI.D, as well as SOW-1 §§ 1.2(a) and 3.2 (data migration causation/responsibility) in Part VI.A. These are among the specific provisions listed in the criterion (limitation of liability under Sections 8.1-8.3 and causation deficiencies under SOW-1 Section 3.2). The criterion requires at least one of the listed provisions to be invoked, and multiple are clearly referenced in the Count I argument.
- **GPT-5.5: Pass.** The brief specifically seeks to dismiss or narrow Count I and invokes qualifying contractual provisions, including SOW-1 § 3.2 for data-migration responsibility/causation issues and MSLSA §§ 8.1–8.2/8.3 for limitation of liability, exclusive remedies, and damages exclusions.

### C-080

Motion brief — argues fraud claim fails for lack of reliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L657))

- **Sonnet 4.6: Pass.** Section IV.A of the brief extensively argues that Arcadia cannot establish justifiable reliance on pre-sale representations. It cites the MSLSA § 12.1 non-reliance clause, notes that Arcadia was represented by outside counsel who negotiated the agreement, highlights Arcadia's sophisticated status as a $62 million-revenue enterprise, references Arcadia's own due diligence (reference calls, CTO evaluation), and applies the Italian Cowboy/Forest Oil framework to show the disclaimer bars the fraud claim as a matter of law. The brief also references § 9.4's acknowledgment that Arcadia 'relied on its own due diligence and evaluation.' All elements of the criterion—integration clause, disclaimers, due diligence, and sophisticated party with counsel—are addressed in the reliance challenge to the fraud claim.
- **GPT-5.5: Pass.** The brief expressly challenges the fraud claim’s justifiable reliance element, arguing that Arcadia disclaimed reliance on extra-contractual pre-sale statements through the MSLSA’s integration/non-reliance clause and warranty disclaimer. It also relies on Arcadia’s own due diligence, sophistication, arm’s-length negotiation, and representation by counsel to argue reliance was barred as a matter of law.

### C-081

Motion brief — cites Fifth Circuit authority beyond Twombly/Iqbal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L665))

- **Sonnet 4.6: Pass.** The brief cites multiple Fifth Circuit cases beyond Twombly/Iqbal, including Benchmark Electronics v. J.M. Huber Corp. (343 F.3d 719), Pizza Hut v. Papa John's Int'l (227 F.3d 489), Williams v. WMX Techs. (112 F.3d 175), Tuchman v. DSC Commc'ns Corp. (14 F.3d 1061), Collins v. Morgan Stanley Dean Witter (224 F.3d 496), Doe v. MySpace (528 F.3d 413), Presidio Enterprises (784 F.2d 674), and others. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The motion brief cites multiple Fifth Circuit authorities beyond Twombly/Iqbal, including Benchmark Electronics v. J.M. Huber Corp., Pizza Hut v. Papa John's, Doe v. MySpace, Collins v. Morgan Stanley, Presidio, Williams, and Tuchman.

### C-082

Motion brief — references negotiation emails showing Arcadia's awareness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L673))

- **Sonnet 4.6: Fail.** The motion brief does not reference the contract negotiation email chain (Exhibit D / Bates Nos. MCS-00004217 through MCS-00004248) showing that Arcadia's counsel Jonathan Breckenridge attempted to negotiate removal of the consequential damages waiver and expanded warranty terms. While the brief does reference that Arcadia engaged outside counsel and sought 'enhanced limitation of liability provisions and expanded warranty protections' (citing FAC ¶ 32), it does not cite the specific email chain exhibit or Bates numbers that would demonstrate Arcadia's awareness and acceptance of the contractual risk allocation through the negotiation history. The criterion specifically requires citation to this exhibit/Bates range, which is absent from the brief.
- **GPT-5.5: Fail.** The brief mentions generally that Arcadia engaged counsel and sought broader liability/warranty terms, but it does not cite or reference the contract negotiation email chain, Exhibit D, or Bates Nos. MCS-00004217 through MCS-00004248. The appendix also omits Exhibit D. Therefore the specific required negotiation-history citation is missing.

### C-083

Motion brief — DTPA arguments beyond § 17.49(f) exemption ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L681))

- **Sonnet 4.6: Pass.** The brief's DTPA section (Part II) includes multiple arguments beyond § 17.49(f). It also argues § 17.49(g) (the $500,000 threshold exemption), puffery (characteristics-and-quality theories under § 17.46(b)(5) and (7) are non-actionable puffery), that the express-warranty theory cannot rest on pre-sale statements disclaimed by the MSLSA, and that the unconscionability allegation is a conclusory recital insufficient under Iqbal. These constitute additional arguments beyond the § 17.49(f) exemption.
- **GPT-5.5: Pass.** The brief does not rely solely on the § 17.49(f) exemption. It also invokes the independent § 17.49(g) large-transaction exemption and, more importantly for the criterion, provides additional DTPA dismissal arguments: alleged representations are non-actionable puffery under the DTPA, the express-warranty theory is barred by the MSLSA’s disclaimers/exclusive remedy, and the unconscionability allegation is conclusory.

### C-084

Motion brief — addresses deemed acceptance impact on warranty claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L689))

- **Sonnet 4.6: Fail.** The motion brief discusses the warranty claim under Section 9.1 (Part VI.C) and the exclusive remedy provisions, but it never mentions Section 5.3 or any 'deemed acceptance' concept. The warranty analysis focuses on the exclusive remedy of repair/replacement/refund and the disclaimer of other warranties, but does not connect deemed acceptance to the argument that Arcadia acknowledged the software performed substantially in accordance with documentation. These two topics are not connected anywhere in the brief.
- **GPT-5.5: Fail.** The brief discusses the limited warranty under Section 9.1 and exclusive remedies, but it does not mention deemed acceptance under Section 5.3 or argue that deemed acceptance constitutes an acknowledgment of substantial conformity with documentation. Thus, it does not connect deemed acceptance to the warranty-breach analysis.

### C-085

Motion brief — correctly identifies all five counts by number and name ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L697))

- **Sonnet 4.6: Pass.** The brief correctly identifies all five counts: Count I (Breach of Contract), Count II (Fraud), Count III (Negligent Misrepresentation), Count IV (Unjust Enrichment), and Count V (DTPA). Each is referenced by both number and name throughout the brief, including in the Table of Contents, Statement of Issues, and Argument sections.
- **GPT-5.5: Pass.** The motion brief correctly identifies all five counts by number and name: Count I (Breach of Contract), Count II (Fraud), Count III (Negligent Misrepresentation), Count IV (Unjust Enrichment), and Count V (DTPA). No count is misnumbered or mislabeled.

### C-086

Motion brief — argues Count II (Fraud) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L705))

- **Sonnet 4.6: Pass.** The motion brief explicitly requests dismissal of Count II (Fraud) in Section IV, arguing multiple grounds: (A) contractual disclaimer of reliance on extra-contractual statements, (B) statements are non-actionable puffery or opinion, (C) remaining allegations fail Rule 9(b) particularity requirements, and (D) nondisclosure theory fails for lack of duty to disclose. The Conclusion and Prayer also explicitly requests dismissal of Count II with prejudice.
- **GPT-5.5: Pass.** The brief explicitly argues that Count II (Fraud) should be dismissed, including sections asserting lack of reliance due to contractual non-reliance, puffery/opinion, failure to satisfy Rule 9(b), and no duty to disclose, and the conclusion requests dismissal of Count II with prejudice.

### C-087

Motion brief — argues Count III (Negligent Misrepresentation) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L713))

- **Sonnet 4.6: Pass.** Section V of the motion brief is explicitly titled 'Count III (Negligent Misrepresentation) Fails' and argues for dismissal on multiple grounds: (1) Rule 9(b) pleading deficiencies (same as fraud), (2) lack of justifiable reliance negated by the non-reliance clause, (3) puffery/future predictions not actionable, and (4) damages sought are benefit-of-the-bargain damages unavailable for negligent misrepresentation. The Conclusion and Prayer also explicitly requests dismissal of Count III with prejudice.
- **GPT-5.5: Pass.** The motion brief explicitly argues that Count III (Negligent Misrepresentation) should be dismissed, including a dedicated section titled “Count III (Negligent Misrepresentation) Fails” asserting lack of justifiable reliance, Rule 9(b) deficiencies, puffery/future predictions, and improper benefit-of-the-bargain damages. The conclusion also requests dismissal of Count III with prejudice.

### C-088

Motion brief — argues Count IV (Unjust Enrichment) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L721))

- **Sonnet 4.6: Pass.** The motion brief contains an entire section (Section III) titled 'Count IV (Unjust Enrichment) Fails Because an Express Contract Governs,' which explicitly argues for dismissal of Count IV based on the express contract bar. The conclusion also explicitly requests dismissal of Count IV with prejudice. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The brief explicitly includes a section titled “Count IV (Unjust Enrichment) Fails Because an Express Contract Governs,” argues that unjust enrichment is unavailable where a valid express contract covers the dispute, and requests that “Count IV should be dismissed with prejudice.” The conclusion also requests dismissal of Counts II, III, IV, and V.

### C-089

Motion brief — argues Count V (DTPA) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L729))

- **Sonnet 4.6: Pass.** The motion brief explicitly addresses Count V (DTPA) in Section II, arguing it should be dismissed on multiple grounds including the §17.49(f) exemption (counseled transactions over $100,000) and the §17.49(g) exemption (transactions over $500,000), as well as puffery and other grounds. The Conclusion and Prayer also explicitly requests dismissal of Count V with prejudice.
- **GPT-5.5: Pass.** The motion brief explicitly argues that Count V (DTPA) should be dismissed, including a dedicated section asserting the DTPA large-transaction exemptions under Tex. Bus. & Com. Code § 17.49(f) and (g), plus additional puffery/warranty/unconscionability grounds, and the conclusion requests dismissal of Count V with prejudice.
