# GPT-6 Luna (xhigh): Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-motion-to-dismiss-brief/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 59 of 89 criteria; GPT-5.5 passed 58 of 89 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-007](#c-007) | Motion brief — table of contents included | **Fail** | **Fail** |
| [C-008](#c-008) | Motion brief — table of authorities included | **Fail** | **Fail** |
| [C-009](#c-009) | Motion brief — cites Bell Atlantic Corp. v. Twombly | Pass | Pass |
| [C-010](#c-010) | Motion brief — cites Ashcroft v. Iqbal | Pass | Pass |
| [C-011](#c-011) | Motion brief — argument section organized by count | Pass | Pass |
| [C-012](#c-012) | Motion brief — conclusion/prayer for relief | **Fail** | **Fail** |
| [C-013](#c-013) | ISSUE_001 — Diversity jurisdiction defect identified in cover memo | Pass | Pass |
| [C-014](#c-014) | ISSUE_001 — Jurisdiction defect placed in cover memo, not MTD brief | **Fail** | **Fail** |
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
| [C-033](#c-033) | ISSUE_006 — Enforceability of limitation provisions between commercially sophisticated parties | **Fail** | **Fail** |
| [C-034](#c-034) | ISSUE_007 — Deemed acceptance under Section 5.3 argued | Pass | Pass |
| [C-035](#c-035) | ISSUE_007 — Correctly identifies the 30-day window dates | **Fail** | **Fail** |
| [C-036](#c-036) | ISSUE_008 — Integration clause / parol evidence rule argued | **Fail** | **Fail** |
| [C-037](#c-037) | ISSUE_008 — Cites Delaware parol evidence authority | **Fail** | **Fail** |
| [C-038](#c-038) | ISSUE_009 — Negligent misrepresentation requires independent duty | **Fail** | **Fail** |
| [C-039](#c-039) | ISSUE_009 — Notes absence of fiduciary/special relationship | **Fail** | **Fail** |
| [C-040](#c-040) | ISSUE_009 — Cites Texas negligent misrepresentation authority | Pass | Pass |
| [C-041](#c-041) | ISSUE_010 — Causation deficiency re: Linden Park responsibility | Pass | Pass |
| [C-042](#c-042) | ISSUE_010 — Notes SOW-1 Section 3.2 data migration allocation | Pass | Pass |
| [C-043](#c-043) | ISSUE_010 — References CO-004 as evidence of Linden Park errors | Pass | Pass |
| [C-044](#c-044) | ISSUE_010 — Notes FAC's failure to name Linden Park | **Fail** | **Fail** |
| [C-045](#c-045) | ISSUE_010 — References Arcadia's own delays contributing to Go-Live delay | **Fail** | **Fail** |
| [C-046](#c-046) | ISSUE_011 — Puffery defense raised for fraud/DTPA claims | Pass | Pass |
| [C-047](#c-047) | ISSUE_011 — References disclaimers in sales materials/proposal | Pass | Pass |
| [C-048](#c-048) | ISSUE_011 — Cites puffery case law | Pass | Pass |
| [C-049](#c-049) | ISSUE_012 — Choice of law addressed for contract claim | Pass | Pass |
| [C-050](#c-050) | ISSUE_012 — Addresses choice of law for tort claims | **Fail** | **Fail** |
| [C-051](#c-051) | ISSUE_012 — Recognizes DTPA is necessarily Texas law | Pass | Pass |
| [C-052](#c-052) | ISSUE_012 — Arguments work under both Delaware and Texas law | **Fail** | **Fail** |
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
| [C-065](#c-065) | Cover memo — notes that subject-matter jurisdiction cannot be waived | Pass | **Fail** |
| [C-066](#c-066) | Cover memo — discusses strategic implications of raising jurisdiction | Pass | Pass |
| [C-067](#c-067) | Factual accuracy — contract value stated as $14.7 million | Pass | Pass |
| [C-068](#c-068) | Factual accuracy — change orders total $2.35 million | Pass | Pass |
| [C-069](#c-069) | Factual accuracy — total claimed damages $47.3 million | **Fail** | **Fail** |
| [C-070](#c-070) | Factual accuracy — MSLSA execution date March 15, 2022 | **Fail** | **Fail** |
| [C-071](#c-071) | Factual accuracy — Go-Live date January 15, 2023 | Pass | Pass |
| [C-072](#c-072) | Factual accuracy — first written complaint March 8, 2023 | Pass | Pass |
| [C-073](#c-073) | Factual accuracy — Delaware governs per Section 12.7 | Pass | Pass |
| [C-074](#c-074) | Factual accuracy — Arcadia represented by counsel during negotiations | **Fail** | **Fail** |
| [C-075](#c-075) | Factual accuracy — 47 support tickets breakdown correct | **Fail** | **Fail** |
| [C-076](#c-076) | Motion brief — requests dismissal with prejudice rather than without | Pass | Pass |
| [C-077](#c-077) | Motion brief — identifies Rule 12(b)(6) as the procedural vehicle | Pass | Pass |
| [C-078](#c-078) | Motion brief — addresses post-answer motion practice authorization | Pass | Pass |
| [C-079](#c-079) | Motion brief — argues Count I breach of contract fails with specific contractual provisions | Pass | Pass |
| [C-080](#c-080) | Motion brief — argues fraud claim fails for lack of reliance | Pass | Pass |
| [C-081](#c-081) | Motion brief — cites Fifth Circuit authority beyond Twombly/Iqbal | Pass | Pass |
| [C-082](#c-082) | Motion brief — references negotiation emails showing Arcadia's awareness | **Fail** | **Fail** |
| [C-083](#c-083) | Motion brief — DTPA arguments beyond § 17.49(f) exemption | **Fail** | **Fail** |
| [C-084](#c-084) | Motion brief — addresses deemed acceptance impact on warranty claim | **Fail** | **Fail** |
| [C-085](#c-085) | Motion brief — correctly identifies all five counts by number and name | Pass | **Fail** |
| [C-086](#c-086) | Motion brief — argues Count II (Fraud) should be dismissed | Pass | Pass |
| [C-087](#c-087) | Motion brief — argues Count III (Negligent Misrepresentation) should be dismissed | Pass | Pass |
| [C-088](#c-088) | Motion brief — argues Count IV (Unjust Enrichment) should be dismissed | Pass | Pass |
| [C-089](#c-089) | Motion brief — argues Count V (DTPA) should be dismissed | Pass | Pass |

## Judge reasoning

### C-001

Motion to dismiss brief produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L18))

- **Sonnet 4.6: Pass.** The agent produced a detailed motion to dismiss brief (motion-to-dismiss.docx) as a primary deliverable. The brief includes a caption, case number, parties, legal arguments under Rule 12(b)(6)/12(c), citations to relevant case law, and a conclusion with requested relief. This clearly satisfies the criterion of producing a motion to dismiss brief.
- **GPT-5.5: Pass.** The agent produced a substantive motion to dismiss brief titled “Defendant Meridian Cloud Solutions, Inc.'s Motion to Dismiss First Amended Complaint Under Rule 12(b)(6), or Alternatively Rule 12(c),” along with a proposed order and cover memo. This satisfies the criterion requiring a motion to dismiss brief as a deliverable.

### C-002

Proposed order produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L28))

- **Sonnet 4.6: Pass.** The agent produced a proposed order as a separate deliverable labeled 'proposed-order.docx'. It includes a full proposed order with case caption, numbered paragraphs addressing each count, and signature block for the judge.
- **GPT-5.5: Pass.** The agent's output includes a separate deliverable labeled “proposed-order.docx” containing a proposed order on the motion to dismiss.

### C-003

Cover memorandum produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L38))

- **Sonnet 4.6: Pass.** The agent produced a cover memorandum (cover-memo.docx) addressed to the partner (Margaret 'Meg' Calloway) and senior associate, containing executive recommendations, threshold jurisdiction analysis, procedural requirements, merits analysis, and next steps. This clearly satisfies the criterion of producing a cover memorandum to the partner as a deliverable.
- **GPT-5.5: Pass.** The agent included a distinct deliverable labeled “cover-memo.docx,” formatted as an internal privileged memorandum to the partner/senior associate with recommendations and analysis. This satisfies the requirement to produce a cover memorandum to the partner.

### C-004

Motion brief — caption identifies court as W.D. Tex. Austin Division ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L48))

- **Sonnet 4.6: Pass.** The caption at the top of the motion brief clearly states 'UNITED STATES DISTRICT COURT' and 'WESTERN DISTRICT OF TEXAS' and 'AUSTIN DIVISION', which satisfies the criterion.
- **GPT-5.5: Pass.** The caption at the top identifies the court as “UNITED STATES DISTRICT COURT,” “WESTERN DISTRICT OF TEXAS,” and “AUSTIN DIVISION,” satisfying the required W.D. Tex. Austin Division identification.

### C-005

Motion brief — caption identifies parties correctly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L56))

- **Sonnet 4.6: Pass.** The caption clearly identifies ARCADIA HEALTH SYSTEMS, LLC as Plaintiff and MERIDIAN CLOUD SOLUTIONS, INC. as Defendant, matching the criterion exactly.
- **GPT-5.5: Pass.** The motion brief caption correctly lists Arcadia Health Systems, LLC as Plaintiff and Meridian Cloud Solutions, Inc. as Defendant.

### C-006

Motion brief — caption includes correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L64))

- **Sonnet 4.6: Pass.** The caption in the motion brief clearly states 'Civil Action No. 1:23-cv-00847-CMA', which matches the required case number exactly.
- **GPT-5.5: Pass.** The motion brief caption includes the civil action number stated as “1:23-cv-00847-CMA,” which matches the required case number exactly.

### C-007

Motion brief — table of contents included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L72))

- **Sonnet 4.6: Fail.** The motion brief does not include a table of contents. The document goes directly from the caption and title to the introductory paragraphs and then into the numbered sections (I through VII), without any table of contents listing the major sections and headings.
- **GPT-5.5: Fail.** The motion brief contains section headings but does not include a separate table of contents listing the major sections/headings.

### C-008

Motion brief — table of authorities included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L80))

- **Sonnet 4.6: Fail.** The motion brief does not include a table of authorities. While the brief cites numerous cases and statutes throughout the text (e.g., Twombly, Iqbal, Harvey v. Grey Wolf, Schlumberger, etc.), there is no separate table of authorities section listing cases, statutes, and other legal authorities cited in the document. The brief goes directly from the caption/title to the procedural posture section without any table of contents or table of authorities.
- **GPT-5.5: Fail.** The motion brief cites cases, statutes, and rules, but it does not include a separate table of authorities listing those authorities.

### C-009

Motion brief — cites Bell Atlantic Corp. v. Twombly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L88))

- **Sonnet 4.6: Pass.** The brief cites Bell Atl. Corp. v. Twombly, 550 U.S. 544, 555, 570 (2007) in Section I (Procedural Posture and Materials the Court May Consider), which is the legal standard section of the motion.
- **GPT-5.5: Pass.** The motion brief cites Bell Atlantic Corp. v. Twombly, 550 U.S. 544 (2007) in Section I, the legal standard/procedural posture section, stating the pleading standard and citing Twombly, 550 U.S. 544, 555, 570 (2007).

### C-010

Motion brief — cites Ashcroft v. Iqbal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L96))

- **Sonnet 4.6: Pass.** The brief cites Ashcroft v. Iqbal, 556 U.S. 662, 678-79 (2009) in Section I (Procedural Posture and Materials the Court May Consider), which serves as the legal standard section discussing the pleading standard under Rule 12(b)(6).
- **GPT-5.5: Pass.** The motion brief cites Ashcroft v. Iqbal, 556 U.S. 662, 678--79 (2009) in Section I, the legal standard/procedural posture section, alongside Twombly.

### C-011

Motion brief — argument section organized by count ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L104))

- **Sonnet 4.6: Pass.** The brief addresses all five counts with separate sections: Count I (Breach of Contract) in Section VI, Count II (Fraud) in Section V.B, Count III (Negligent Misrepresentation) in Section V.C, Count IV (Unjust Enrichment) in Section IV, and Count V (DTPA) in Section III. Each count has its own heading or clearly delineated subsection. The argument is organized by count, satisfying the criterion.
- **GPT-5.5: Pass.** The argument section addresses each of the five counts: Count I breach of contract, Count II fraud, Count III negligent misrepresentation, Count IV unjust enrichment, and Count V DTPA. Each is identified in headings or clearly delineated subsections, even though fraud and negligent misrepresentation are grouped under one main heading with separate analysis.

### C-012

Motion brief — conclusion/prayer for relief ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L112))

- **Sonnet 4.6: Fail.** The conclusion/prayer for relief in Section VII requests dismissal of Counts II through V and narrowing of Count I, but does not request dismissal of all five counts with prejudice. Specifically, Count I is not requested to be dismissed with prejudice (the brief explicitly says 'dismissal of Count I in its entirety is an aggressive request' and instead requests only partial dismissal of certain theories). Additionally, the conclusion does not uniformly request dismissal 'with prejudice' for all counts — it requests dismissal without prejudice where amendment could cure defects. The criterion requires the conclusion/prayer to request dismissal of all five counts with prejudice, which this brief does not do.
- **GPT-5.5: Fail.** The brief includes a conclusion/prayer, but it does not request dismissal of all five counts with prejudice. It requests dismissal of Counts II through V, only partial dismissal/narrowing of Count I, and even requests dismissal without prejudice where amendment could cure defects.

### C-013

ISSUE_001 — Diversity jurisdiction defect identified in cover memo ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L120))

- **Sonnet 4.6: Pass.** The cover memo clearly identifies the diversity jurisdiction defect. Section 1 ('THRESHOLD DIVERSITY PROBLEM') explicitly states that LLC citizenship must be traced through all members (citing Harvey v. Grey Wolf Drilling Co.), identifies that Arcadia's members include Apex Medical Ventures LP, whose partners include a Delaware corporation, making Arcadia a Delaware citizen. It also notes that the Notice of Removal incorrectly treated Arcadia as a Texas citizen based on formation/principal office rather than tracing through all members. The memo concludes that because both Arcadia (through Apex LP's Delaware corporate partner) and Meridian are Delaware citizens, complete diversity is destroyed. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The cover memo explicitly identifies a subject-matter jurisdiction defect based on LLC citizenship tracing. It states that Arcadia’s citizenship must be traced through all members, including Apex Medical Ventures, LP and its partners, identifies a Delaware corporate partner, and explains that this Delaware citizenship overlaps with Meridian’s Delaware citizenship, defeating complete diversity. It also notes the Notice of Removal incorrectly treated Arcadia as merely a Texas citizen rather than tracing all LLC members.

### C-014

ISSUE_001 — Jurisdiction defect placed in cover memo, not MTD brief ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L128))

- **Sonnet 4.6: Fail.** The criterion requires that the jurisdictional defect be flagged in the cover memo and NOT raised as a formal argument in the MTD brief (brief mention/acknowledgment is acceptable, but the substantive challenge should be routed to the cover memo). Looking at the agent's output: The cover memo (Section 1) contains a thorough, substantive analysis of the diversity defect and recommends filing a jurisdictional notice/motion to remand. However, the MTD brief also contains a full Section II titled 'THE COURT MUST FIRST CONFIRM SUBJECT-MATTER JURISDICTION' which goes well beyond brief mention or acknowledgment — it includes detailed legal analysis citing Harvey v. Grey Wolf, Carden v. Arkoma, walks through the citizenship chain, and requests remand under §1447(c). This is a substantive 12(b)(1)-style jurisdictional argument in the MTD brief itself, not merely an acknowledgment. The criterion says FAIL if the MTD brief includes a substantive jurisdictional argument. The MTD brief clearly does include such a substantive argument (an entire section dedicated to it), even though the cover memo also covers it. Therefore, the criterion is not satisfied.
- **GPT-5.5: Fail.** The cover memo does flag the lack of complete diversity in detail. However, the motion to dismiss brief also raises the jurisdiction defect as a substantive formal argument, including an introductory threshold discussion, a dedicated Section II arguing complete diversity is absent, and a request that the Court remand under § 1447(c). The criterion required routing the jurisdictional challenge to the cover memo and not presenting it as a formal MTD argument.

### C-015

ISSUE_001 — Cover memo recommends course of action on jurisdiction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L137))

- **Sonnet 4.6: Pass.** The cover memo clearly identifies the diversity jurisdiction defect and provides explicit recommendations: (1) file a jurisdictional notice/motion to remand or request the Court determine jurisdiction sua sponte before any merits decision; (2) immediately verify the full citizenship chain and then move for remand; (3) hold the all-count merits motion pending jurisdictional resolution. The Executive Recommendation section states 'Recommend filing a carefully supported jurisdictional notice/motion to remand or requesting that the Court determine jurisdiction sua sponte before any merits decision.' This satisfies the criterion of providing a recommended course of action regarding the jurisdictional defect.
- **GPT-5.5: Pass.** The cover memo not only identifies the diversity jurisdiction defect but expressly recommends a course of action: do not file the merits motion yet, verify the citizenship chain, file a jurisdictional notice/motion to remand or request that the Court determine jurisdiction sua sponte before any merits ruling, and prioritize remand if diversity is absent.

### C-016

ISSUE_001 — Correctly traces Arcadia's citizenship through LLC members ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L145))

- **Sonnet 4.6: Pass.** The criterion requires that the cover memo correctly explains that an LLC's citizenship is determined by the citizenship of all its members and addresses the need to trace through the LLC membership structure. The memo does this clearly: it cites Harvey v. Grey Wolf Drilling Co. for the proposition that 'an LLC takes the citizenship of every member,' identifies multiple Arcadia members (Okonkwo, Schreiber, and Apex Medical Ventures, LP), and traces through Apex LP's partners to find Delaware citizenship. It also criticizes the Notice of Removal for incorrectly basing Arcadia's citizenship on its state of formation/principal office rather than its members. The criterion notes that the Notice of Removal only identifies Dr. Okonkwo and does not mention Schreiber or Apex — the memo's identification of these additional members and the tracing analysis satisfies the criterion's requirement to address the need to trace through the LLC membership structure. The memo correctly applies the rule that all members' citizenships must be considered, not just the managing member's citizenship.
- **GPT-5.5: Pass.** The memo expressly states that an LLC takes the citizenship of every member and criticizes the removal notice for using formation/principal office instead of tracing all members. It also discusses tracing through an LP member and its partners. Although it appears to introduce unsupported member names, it satisfies the specified criterion by addressing the need to trace Arcadia’s citizenship through its LLC membership structure.

### C-017

ISSUE_001 — Notes Notice of Removal failed to properly analyze citizenship ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L153))

- **Sonnet 4.6: Pass.** The cover memo explicitly addresses the Notice of Removal's deficiency in Section 1: 'The Notice of Removal incorrectly alleges that Arcadia is a Texas citizen based on its formation/principal office and then treats Meridian's Delaware citizenship as the only relevant citizenship. LLC citizenship is determined by every member, not the LLC's state of formation or headquarters.' This directly notes that the removal papers failed to trace citizenship through all of Arcadia's members as required for an LLC under § 1332, satisfying the criterion.
- **GPT-5.5: Pass.** The cover memo explicitly states that the Notice of Removal incorrectly alleged Arcadia was a Texas citizen based on its formation/principal office and failed to apply the rule that an LLC’s citizenship is determined by every member, including tracing through Apex LP. This directly notes the removal-paper citizenship-analysis deficiency.

### C-018

ISSUE_002 — Fraud claim (Count II) challenged under Rule 9(b) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L161))

- **Sonnet 4.6: Pass.** Section V.B of the brief explicitly cites Rule 9(b) and applies it to Count II (Fraud). The brief states: 'Rule 9(b) requires the circumstances of fraud to be pleaded with particularity, including the statement, speaker, time, place, and why the statement was false or misleading,' citing Benchmark Electronics and Dorsey. It then applies this standard to the FAC's allegations, noting deficiencies in identifying speakers ('undifferentiated sales team'), basis for falsity, scienter, and the omissions theory. The section concludes: 'The fraud claim should be dismissed under Rule 9(b) and Twombly/Iqbal.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The brief expressly challenges the fraud count under Rule 9(b), citing the heightened pleading standard and explaining that the FAC fails to plead the statement, speaker, time, place, and why the statements were false or misleading. It applies this standard specifically to the fraud allegations in Count II.

### C-019

ISSUE_002 — Identifies FAC's failure to name specific individuals ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L169))

- **Sonnet 4.6: Pass.** In Section V.B, the brief explicitly states: 'the FAC gives dates for the October and November presentations, but attributes most statements to an undifferentiated "sales team," gives no particular basis that the performance metric was false as an aggregate statement when made.' This directly raises the group pleading deficiency under Rule 9(b), arguing that the FAC fails to identify specific individuals who made the alleged misrepresentations.
- **GPT-5.5: Pass.** The brief expressly raises a Rule 9(b) deficiency by stating that the FAC attributes most statements to an undifferentiated “sales team,” rather than identifying specific speakers, in its fraud pleading discussion.

### C-020

ISSUE_002 — Argues FAC fails to plead scienter with factual support ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L177))

- **Sonnet 4.6: Pass.** Section V.B of the brief explicitly argues that the FAC's scienter allegations are deficient. It states: 'The FAC's allegations that Meridian "knew or should have known" and acted "recklessly" are conclusions. Its "on information and belief" assertions about other customers and technical limitations are not accompanied by a factual basis that supports contemporaneous knowledge. Post-contract defects, project delay, and a commission incentive do not, without more, plausibly establish that the specific statements were knowingly or recklessly false when uttered.' This directly addresses the criterion — the brief argues that the 'knew or should have known' allegation is conclusory and lacks supporting factual allegations.
- **GPT-5.5: Pass.** The brief expressly argues that the fraud count fails to plead facts supporting scienter, stating that allegations Meridian 'knew or should have known' and acted 'recklessly' are conclusory, that information-and-belief assertions lack factual basis for contemporaneous knowledge, and that later defects/delay/commission incentives do not plausibly show the statements were knowingly or recklessly false when made.

### C-021

ISSUE_002 — Cites relevant Fifth Circuit Rule 9(b) authority ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L185))

- **Sonnet 4.6: Pass.** The brief cites both Benchmark Electronics, Inc. v. J.M. Huber Corp., 343 F.3d 719, 724 (5th Cir. 2003) and Dorsey v. Portfolio Equities, Inc., 540 F.3d 333, 339 (5th Cir. 2008) in Section V.B, both of which are Fifth Circuit cases applying Rule 9(b) to fraud claims.
- **GPT-5.5: Pass.** The brief cites Fifth Circuit cases applying Rule 9(b) to fraud claims, including Benchmark Electronics v. J.M. Huber Corp. and Dorsey v. Portfolio Equities, in its fraud pleading argument.

### C-022

ISSUE_003 — Economic loss rule argued against tort claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L193))

- **Sonnet 4.6: Fail.** The criterion requires the motion to argue that the economic loss rule bars Counts II (Fraud) and/or III (Negligent Misrepresentation) because all alleged damages are purely economic losses arising from the contractual relationship. Looking at Section V.C of the brief, the agent explicitly addresses the economic loss rule but does the opposite of what the criterion requires: it affirmatively states 'The Court should not, however, treat Texas's economic-loss rule as a categorical bar to every fraudulent-inducement claim' and cites Formosa Plastics to recognize an independent fraud claim. The brief explicitly declines to raise the economic loss rule as a ground for dismissal, instead relying on the non-reliance clause and Rule 9(b) pleading defects. The economic loss rule is mentioned only to disclaim reliance on it. Therefore, the criterion is not satisfied.
- **GPT-5.5: Fail.** The brief does not argue that the economic loss rule bars the fraud or negligent-misrepresentation claims. It expressly states that the Court should not treat Texas's economic-loss rule as a categorical bar to fraudulent inducement and that Meridian's argument rests instead on non-reliance and pleading defects. Therefore, the required ground for dismissal is not raised.

### C-023

ISSUE_003 — Economic loss rule argued under Delaware law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L201))

- **Sonnet 4.6: Fail.** The motion brief does not analyze the economic loss rule under Delaware law. In Section V.C, the brief briefly mentions the economic loss rule but explicitly states it is not relying on it as a categorical bar, and the analysis references Texas law (Formosa Plastics Corp. USA v. Presidio Eng'rs & Contractors, Inc., a Texas Supreme Court case). The brief does note in Section VI that Delaware law governs the agreement under §12.7, but it never applies Delaware's economic loss doctrine or cites Delaware authority such as Brasby v. Morris Dynamics or Kuhn Construction v. Diamond State Port Corp. The criterion specifically requires analysis of the economic loss rule under Delaware law with relevant Delaware authority, which is entirely absent from the brief.
- **GPT-5.5: Fail.** The brief does not analyze the economic loss rule under Delaware law or cite Delaware authorities such as Brasby v. Morris Dynamics or Kuhn Construction. It instead discusses Texas law and expressly avoids a categorical Texas economic-loss-rule argument for fraudulent inducement.

### C-024

ISSUE_003 — Economic loss rule argued under Texas law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L209))

- **Sonnet 4.6: Fail.** The criterion requires that the motion brief analyze the economic loss rule under Texas law, citing relevant authority such as Sharyland Water Supply Corp. v. City of Alton or Chapman Custom Homes v. Dallas Plumbing Co. The brief does mention the economic loss rule in Section V.C, stating 'The Court should not, however, treat Texas's economic-loss rule as a categorical bar to every fraudulent-inducement claim' and citing Formosa Plastics Corp. USA v. Presidio Eng'rs & Contractors, Inc., 960 S.W.2d 41, 46-47 (Tex. 1998). However, this is a brief disclaimer rather than an actual analysis of the economic loss rule. The brief does not cite Sharyland Water Supply Corp. v. City of Alton or Chapman Custom Homes v. Dallas Plumbing Co., nor does it provide a substantive analysis of when the economic loss rule applies or bars tort claims in Texas. The mention of the economic loss rule is merely a passing reference to note that Meridian is NOT relying on it as a categorical bar, rather than an affirmative analysis of the doctrine. The criterion requires analysis of the economic loss rule with relevant authority, which is absent here.
- **GPT-5.5: Fail.** The brief only briefly mentions Texas's economic-loss rule to say it should not be treated as a categorical bar to fraudulent inducement, citing Formosa, and then expressly bases the argument on non-reliance and pleading defects instead. It does not meaningfully analyze or argue the economic loss rule under Texas law or cite authorities such as Sharyland or Chapman.

### C-025

ISSUE_004 — DTPA consumer standing challenged under § 17.49(f) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L217))

- **Sonnet 4.6: Fail.** The criterion requires the motion to argue that Arcadia lacks standing as a 'consumer' under the DTPA due to the § 17.49(f) exemption for transactions exceeding $500,000 where the claiming party has assets of $25 million or more. The brief does raise § 17.49(f) and the $500,000 consideration threshold, but it explicitly rejects the $25 million asset threshold as irrelevant, stating: 'Arcadia's pre-suit response invokes a $25 million asset threshold. That threshold is not an element of § 17.49(f)'s more-than-$500,000 exemption.' The criterion specifically requires the argument to be based on the exemption for transactions exceeding $500,000 WHERE the claiming party has assets of $25 million or more. The brief argues only the consideration threshold, not the combined consideration + $25M asset threshold. The actual § 17.49(f) exemption requires BOTH: consideration over $500,000 AND assets of $25 million or more (or the claimant is a business consumer). The brief misapplies the statute by ignoring the asset requirement. The criterion requires the brief to argue the exemption including the $25 million asset component, which the brief explicitly dismisses as inapplicable. Therefore, the brief does not satisfy the criterion as described.
- **GPT-5.5: Pass.** The brief expressly raises Texas Business & Commerce Code § 17.49(f), argues the DTPA claim is barred because the transaction exceeded $500,000, and seeks dismissal of the DTPA count on that basis. Although it disputes rather than relies on a $25 million asset threshold, the § 17.49(f) exemption is clearly raised and applied to Arcadia’s DTPA claim.

### C-026

ISSUE_004 — Transaction value exceeds $500,000 threshold ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L225))

- **Sonnet 4.6: Pass.** The motion brief explicitly states in Section III: 'The FAC alleges a $14.7 million base contract and $2.35 million in Change Orders; the MSLSA confirms the $14.7 million base amount. FAC ¶¶ 34, 46--47, 100; MSLSA §§ 6.1--6.2. The transaction is far above the statutory threshold.' This identifies both the base contract value of $14.7 million and the change orders totaling $2.35 million, and explicitly argues the transaction exceeds the $500,000 threshold under § 17.49(f).
- **GPT-5.5: Pass.** The brief expressly states that the DTPA claim fails under Texas Business and Commerce Code § 17.49(f) because the transaction exceeds the $500,000 threshold, identifying a $14.7 million base contract plus $2.35 million in Change Orders, totaling far above the statutory threshold.

### C-027

ISSUE_004 — Exploits FAC/$30M infrastructure contradiction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L233))

- **Sonnet 4.6: Fail.** The motion brief's DTPA section (Count V) mentions that 'Arcadia's pre-suit response invokes a $25 million asset threshold' and that 'its assets were $23.8 million,' but it does not identify or exploit the FAC's own allegation of 'substantial infrastructure investments exceeding $30 million' or use the contradiction between the $30 million FAC allegation and the $23.8 million figure from the pre-suit letter. The brief dismisses the asset threshold argument by saying it is not an element of § 17.49(f)'s consideration-based exemption, which is correct, but the criterion specifically requires the brief to identify and exploit the $30M/$23.8M contradiction. The brief fails to mention the $30 million infrastructure allegation from the FAC at all, and does not use the inconsistency between the two figures to undermine Arcadia's credibility or support the DTPA argument.
- **GPT-5.5: Fail.** The brief mentions Arcadia’s DTPA reply letter assertion that assets were $23.8 million, but only to argue that the asset threshold is irrelevant to § 17.49(f)’s $500,000 consideration exemption. It does not identify or exploit the FAC’s alleged $30 million infrastructure investments, nor does it point out any inconsistency between that allegation and the $23.8 million asset figure to support the DTPA argument.

### C-028

ISSUE_005 — Unjust enrichment barred by express contract ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L241))

- **Sonnet 4.6: Pass.** Section IV of the brief explicitly argues that Count IV (unjust enrichment) must be dismissed because the MSLSA expressly governs the software license, implementation, support, training, and data-migration advisory services, and that under Texas law unjust-enrichment/quantum-meruit recovery is unavailable when a valid express contract covers the subject matter, citing Fortune Prod. Co. v. Conoco, Inc. and Excess Underwriters at Lloyd's v. Frank's Casing Crew & Rental Tools, Inc. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The brief expressly argues in Section IV that Count IV seeks equitable recovery for subject matter governed by the MSLSA, that the MSLSA/SOW/change orders govern the software license, implementation, support, training, and data-migration services, and that under Texas law unjust enrichment/quantum meruit is unavailable when a valid express contract covers the subject matter. It requests dismissal of Count IV on that basis.

### C-029

ISSUE_005 — Cites authority for express contract bar to unjust enrichment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L249))

- **Sonnet 4.6: Pass.** Section IV of the brief explicitly cites both Fortune Prod. Co. v. Conoco, Inc., 52 S.W.3d 671, 684 (Tex. 2000) and Excess Underwriters at Lloyd's v. Frank's Casing Crew & Rental Tools, Inc., 246 S.W.3d 42, 59 (Tex. 2008) for the proposition that unjust-enrichment/quantum-meruit recovery is unavailable when a valid express contract covers the subject matter.
- **GPT-5.5: Pass.** The brief expressly argues that unjust-enrichment/quantum-meruit recovery is unavailable when a valid express contract covers the subject matter and cites relevant authority: Fortune Production Co. v. Conoco, Inc. and Excess Underwriters at Lloyd's v. Frank's Casing Crew & Rental Tools, Inc.

### C-030

ISSUE_005 — Notes inconsistency of pleading breach of contract and unjust enrichment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L257))

- **Sonnet 4.6: Pass.** Section IV of the brief explicitly argues that unjust enrichment/quantum meruit recovery is unavailable when a valid express contract covers the subject matter, citing Fortune Prod. Co. v. Conoco and Excess Underwriters at Lloyd's. It notes that the MSLSA expressly governs the same subject matter as Count IV, and that Arcadia 'affirmatively sues to enforce it' while simultaneously seeking unjust enrichment. The brief directly addresses the inconsistency of pleading both breach of contract and unjust enrichment for the same subject matter, satisfying the criterion.
- **GPT-5.5: Pass.** The brief expressly argues that Count IV for unjust enrichment seeks recovery for the same payments and subject matter governed by the MSLSA/SOW/Change Orders, while Arcadia also sues to enforce that express contract in Count I. It states unjust enrichment is unavailable where a valid express contract covers the same subject matter and characterizes Count IV as duplicative despite alternative pleading.

### C-031

ISSUE_006 — Contractual liability cap (Section 8.1) argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L265))

- **Sonnet 4.6: Fail.** The brief does reference Section 8.1 in Section VI.D, noting that 'Sections 8.1–8.3 cap aggregate liability, exclude specified consequential and exemplary damages, and provide exclusive contractual remedies' and that 'the cap also applies regardless of the form of action.' It also mentions that 'The amount of the §8.1 cap depends on the event giving rise and the fees paid/payable in the preceding twelve months.' However, the criterion specifically requires that the brief argue that Arcadia's claimed damages 'vastly exceed this cap.' The brief does not make this argument — it explicitly states 'the current pleadings do not establish a single undisputed cap figure' and reserves the cap calculation. The brief raises Section 8.1 but does not argue that Arcadia's claimed damages vastly exceed the cap, which is a required element of the criterion.
- **GPT-5.5: Fail.** The brief raises Section 8.1 and states that it caps aggregate liability based on fees paid/payable in the preceding twelve months. However, it does not argue that Arcadia's claimed damages vastly exceed that cap; instead, it says the current pleadings do not establish a single undisputed cap figure. Thus the full criterion is not satisfied.

### C-032

ISSUE_006 — Consequential damages waiver (Section 8.2) argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L273))

- **Sonnet 4.6: Pass.** The brief does reference Section 8.2 and the exclusion of consequential damages, including lost profits, goodwill, and intangible losses. In Section VI.D, the brief states: 'Sections 8.1–8.3 cap aggregate liability, exclude specified consequential and exemplary damages, and provide exclusive contractual remedies. The §8.2 text expressly identifies lost profits, goodwill, and intangible losses.' However, the criterion requires that the brief specifically argue that Section 8.2 bars Arcadia's claims for lost profits ($18.4M), increased operating costs ($6.7M), and reputational harm ($5.0M). The brief mentions lost profits and goodwill/intangible losses generally but does not specifically identify the dollar amounts ($18.4M, $6.7M, $5.0M) or explicitly call out 'increased operating costs' as a category barred by Section 8.2. That said, the criterion says 'PASS if the motion brief argues that Section 8.2 of the MSLSA bars Arcadia's claims for lost profits, increased operating costs, and reputational harm as consequential, indirect, or incidental damages that were expressly waived.' The brief does argue that Section 8.2 excludes lost profits and intangible losses (which would encompass reputational harm). The brief also references 'consequential and exemplary damages' being excluded. The specific dollar figures are not mentioned, but the categories are addressed. The criterion does not strictly require the dollar figures to be cited—it requires the argument that Section 8.2 bars those categories. The brief makes this argument, though somewhat briefly and without the specific dollar amounts. Given that the criterion is met in substance (the argument is raised), this should pass.
- **GPT-5.5: Pass.** The brief raises and argues the MSLSA Section 8.2 consequential-damages waiver, stating that Sections 8.1–8.3 exclude consequential damages and that Section 8.2 expressly identifies lost profits, goodwill, and intangible losses, and asks the Court to dismiss barred damages categories. Although it does not list all dollar amounts or expressly mention increased operating costs, the consequential damages waiver is clearly raised and applied to lost profits/reputational-type damages.

### C-033

ISSUE_006 — Enforceability of limitation provisions between commercially sophisticated parties ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L281))

- **Sonnet 4.6: Fail.** The criterion requires the brief to argue that limitation of liability and consequential damages waiver provisions are enforceable based on Arcadia's sophistication or counsel representation (specifically Wexford Hale LLP). The brief does mention in Section V.A that 'Arcadia pleads it was a commercial healthcare-IT provider, conducted due diligence and engaged outside counsel' and that 'the agreement memorializes no reliance on extra-contractual statements.' However, this argument about sophistication and outside counsel is made in the context of the non-reliance/fraud claims (Counts II and III), not specifically in the context of enforcing the limitation of liability and consequential damages provisions. In Section VI.D, the brief discusses the liability cap and consequential damages exclusion provisions (§§8.1-8.3) but does not argue their enforceability based on the parties' sophistication or counsel representation. The brief simply states the Court should 'enforce the text and dismiss barred categories' without connecting the enforceability argument to party sophistication or outside counsel. Additionally, the specific law firm 'Wexford Hale LLP' is not mentioned anywhere in the brief. The criterion specifically requires the argument about enforceability of limitation provisions to be tied to sophistication/counsel representation, and this connection is not made in the limitation of liability section.
- **GPT-5.5: Fail.** The brief asks the Court to enforce the MSLSA’s liability cap and consequential-damages waiver, but it does not argue that those limitation provisions are enforceable because Arcadia was represented by outside counsel/Wexford Hale or because sophisticated commercial parties negotiated them at arm’s length. The sophistication/counsel discussion appears only in connection with the non-reliance clause, not the limitation provisions.

### C-034

ISSUE_007 — Deemed acceptance under Section 5.3 argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L289))

- **Sonnet 4.6: Pass.** Section VI.D of the brief explicitly addresses the deemed acceptance argument under Section 5.3. It states that Section 5.3 provides for deemed acceptance absent a sufficiently detailed written Nonconformity Notice within 30 days after the applicable Deployment Notice, and notes that the FAC alleges Go-Live on January 15, 2023 and a written email complaint on March 8, 2023. The brief argues this provision forecloses an untimely rejection/full-refund theory. The 30-day window from January 15 to February 14, 2023 is implicitly established (Go-Live January 15 + 30 days = February 14), and the March 8 complaint is identified as coming after that window. This satisfies the criterion.
- **GPT-5.5: Pass.** The brief raises the Section 5.3 deemed-acceptance argument, stating that acceptance is deemed absent a sufficiently detailed written Nonconformity Notice within 30 days after the Deployment Notice and that this forecloses an untimely rejection/full-refund theory. It also identifies Go-Live as January 15, 2023 and the written complaint as March 8, 2023, which supports the argument that no timely notice was given within the 30-day window, even though it does not expressly name February 14 as the deadline.

### C-035

ISSUE_007 — Correctly identifies the 30-day window dates ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L297))

- **Sonnet 4.6: Fail.** The brief states Go-Live on January 15, 2023 and a written email complaint on March 8, 2023, both of which are correct. However, the brief does not explicitly state the 30-day acceptance window end date (approximately February 14, 2023). The criterion requires the brief to correctly identify all three dates: Go-Live (January 15, 2023), acceptance window end (~February 14, 2023), and first written complaint (March 8, 2023). The brief only mentions two of these dates explicitly. The acceptance window end date is not stated. The criterion says PASS if the brief 'correctly identifies' all three dates. Since the February 14 date is absent, this is a failure to satisfy the criterion as described.
- **GPT-5.5: Fail.** The brief identifies Go-Live as January 15, 2023 and the first written complaint as March 8, 2023, but it does not identify the 30-day acceptance window end as approximately February 14, 2023 or state that March 8 was about 22 days after the window expired.

### C-036

ISSUE_008 — Integration clause / parol evidence rule argued ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L305))

- **Sonnet 4.6: Fail.** The brief discusses Section 12.1 extensively in Section V, arguing that it contains an express non-reliance acknowledgment that defeats justifiable reliance on pre-contract statements. However, the criterion specifically requires that the brief argue Section 12.1 bars Arcadia from relying on pre-sale oral representations as contractual terms by invoking the parol evidence rule to exclude extrinsic evidence. The brief's argument is framed around the non-reliance clause defeating the fraud/misrepresentation claims' justifiable reliance element, not around the parol evidence rule excluding extrinsic evidence from varying or supplementing the contract's terms. The brief explicitly distinguishes its argument from a 'generic merger clause' and focuses on the non-reliance/disclaimer aspect rather than the parol evidence rule. The parol evidence rule is never mentioned, and the argument is not framed as barring pre-sale representations from being treated as contractual terms. The criterion requires the parol evidence rule argument specifically, which is absent.
- **GPT-5.5: Fail.** The brief discusses Section 12.1 primarily as an express non-reliance clause defeating justifiable reliance for fraud and negligent misrepresentation, and notes that it supersedes proposals and pre-contract discussions. But it does not make the required parol-evidence/integration-clause argument that pre-sale oral representations or promises cannot be used as contractual terms or to vary the written MSLSA. It also does not invoke the parol evidence rule.

### C-037

ISSUE_008 — Cites Delaware parol evidence authority ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L313))

- **Sonnet 4.6: Fail.** The motion brief does not cite any Delaware parol evidence authority such as SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care. While the brief mentions that Delaware law governs the agreement under §12.7, it only cites Texas cases (Schlumberger, Forest Oil, Italian Cowboy Partners) for the non-reliance/integration clause arguments. No Delaware parol evidence rule cases are cited anywhere in the brief.
- **GPT-5.5: Fail.** The brief notes that Delaware law governs the agreement but does not cite any Delaware authority on the parol evidence rule or integration clauses, such as SIGA Technologies v. PharmAthene or Eagle Industries v. DeVilbiss Health Care.

### C-038

ISSUE_009 — Negligent misrepresentation requires independent duty ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L321))

- **Sonnet 4.6: Fail.** The brief's treatment of Count III (negligent misrepresentation) in Section V.C focuses on justifiable reliance and damages limitations. It does not argue that Meridian owed no duty to Arcadia independent of the contractual relationship, nor does it argue that no such independent duty exists between sophisticated parties in arm's-length commercial transactions. The independent duty argument is entirely absent from the brief.
- **GPT-5.5: Fail.** The brief challenges Count III based on lack of justifiable reliance, non-reliance language, failure to identify specific false information, and damages limitations. It does not argue that Meridian owed no duty independent of the contract, nor that no such duty exists in an arm’s-length transaction between sophisticated commercial parties.

### C-039

ISSUE_009 — Notes absence of fiduciary/special relationship ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L329))

- **Sonnet 4.6: Fail.** The brief mentions that Arcadia 'was represented by counsel' and 'conducted due diligence and engaged outside counsel' in Section V.A, and describes the parties as sophisticated commercial parties negotiating at arm's length. However, the brief does not explicitly argue that no fiduciary or special relationship existed between Meridian and Arcadia. The mention of counsel and sophistication is made in the context of the non-reliance clause analysis, not as a standalone argument about the absence of a fiduciary or special relationship. The criterion requires the brief to argue that no fiduciary or special relationship existed — this specific legal argument is not made anywhere in the brief.
- **GPT-5.5: Fail.** The brief describes the parties as sophisticated commercial entities, notes negotiation and counsel, and relies on a non-reliance clause, but it does not specifically note or argue the absence of a fiduciary or special relationship between Meridian and Arcadia.

### C-040

ISSUE_009 — Cites Texas negligent misrepresentation authority ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L337))

- **Sonnet 4.6: Pass.** The brief cites both McCamish, Martin, Brown & Loeffler v. F.E. Appling Interests, 991 S.W.2d 787, 791 (Tex. 1999) and Federal Land Bank Ass'n v. Sloane, 825 S.W.2d 439, 442–43 (Tex. 1991) in Section V.C, which addresses Count III (negligent misrepresentation). These are exactly the Texas authorities specified in the criterion.
- **GPT-5.5: Pass.** The brief cites relevant Texas negligent misrepresentation authorities, including McCamish, Martin, Brown & Loeffler v. F.E. Appling Interests and Federal Land Bank Ass'n v. Sloane, in its discussion of Count III.

### C-041

ISSUE_010 — Causation deficiency re: Linden Park responsibility ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L345))

- **Sonnet 4.6: Pass.** The brief explicitly addresses the Linden Park causation issue in Section VI.A, arguing that SOW-1 §3.2 made Arcadia 'solely responsible' for data extraction, transformation, loading, validation, and integrity, limiting Meridian to advisory consulting. It also cites CO-004, which states that data-integrity issues arose from errors in Linden Park's migration scripts, not a NexusCore defect or Meridian act or omission. The brief argues the contract count should be dismissed insofar as it seeks to impose liability on Meridian for data corruption or migration errors attributable to Arcadia or Linden Park. This directly satisfies the criterion requiring the motion to argue that the FAC fails to adequately plead that Meridian (rather than Linden Park or Arcadia) was the proximate cause of the alleged damages.
- **GPT-5.5: Pass.** The brief raises the Linden Park/third-party causation issue. It specifically cites SOW-1 § 3.2 as making Arcadia solely responsible for data extraction, transformation, loading, validation, and integrity; states Arcadia was responsible for its SI Partner; and argues CO-004 attributes data-integrity issues to Linden Park’s migration scripts rather than Meridian. It seeks dismissal of contract theories imposing liability on Meridian for data corruption or migration errors attributable to Arcadia or Linden Park. Although it does not use the exact phrase “proximate cause,” it substantively makes the required causation/responsibility argument.

### C-042

ISSUE_010 — Notes SOW-1 Section 3.2 data migration allocation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L353))

- **Sonnet 4.6: Pass.** The motion brief explicitly references SOW-1 §3.2 in Section VI.A, stating 'SOW-1 §3.2 makes Arcadia "solely responsible" for data extraction, transformation, loading, validation, and integrity, and limits Meridian to advisory consulting.' This directly cites the specific section and its allocation of data migration responsibility to Arcadia, satisfying the criterion.
- **GPT-5.5: Pass.** The brief specifically cites SOW-1 §3.2 and states that it makes Arcadia “solely responsible” for data extraction, transformation, loading, validation, and integrity, which satisfies the requirement to note the data migration allocation to Arcadia.

### C-043

ISSUE_010 — References CO-004 as evidence of Linden Park errors ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L361))

- **Sonnet 4.6: Pass.** The brief explicitly references CO-004 in Section VI.A, stating: 'CO-004, signed by both parties, states that the identified data-integrity issues arose from errors in Linden Park's migration scripts, not a NexusCore defect or Meridian act or omission, and confirms Meridian did not assume migration responsibility.' This directly cites CO-004 as evidence that implementation failures were caused by Linden Park's data migration errors rather than Meridian's software or services. The $900,000 amount is not explicitly mentioned, but the criterion only requires that CO-004 be cited in this context, which it clearly is.
- **GPT-5.5: Pass.** The brief expressly cites CO-004 in the contract section, stating that it documented data-integrity issues arising from Linden Park’s migration-script errors, not a NexusCore defect or Meridian act/omission, and uses it to argue Meridian is not liable for data migration failures.

### C-044

ISSUE_010 — Notes FAC's failure to name Linden Park ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L369))

- **Sonnet 4.6: Fail.** The brief does mention Linden Park Consulting in several places (SOW-1 §3.2, CO-004, and the data-migration section), but the criterion specifically asks whether the brief argues or notes that the FAC attributes all implementation failures to 'Meridian and its agents' without acknowledging or naming Linden Park as Arcadia's own independently retained third-party integrator. The brief does not make this specific argument — it does not point out that the FAC fails to name Linden Park or that the FAC improperly attributes Linden Park's failures to Meridian. Instead, the brief simply references Linden Park in the context of the contract documents. The criterion requires highlighting the FAC's omission of Linden Park and its improper attribution of failures to Meridian, which the brief does not do.
- **GPT-5.5: Fail.** The brief mentions Linden Park in discussing data-migration responsibility and Change Order CO-004, but it does not highlight the specific pleading omission required by the criterion: that the FAC attributes implementation failures to “Meridian and its agents” while failing to acknowledge or name Linden Park Consulting as Arcadia’s independently retained third-party integrator.

### C-045

ISSUE_010 — References Arcadia's own delays contributing to Go-Live delay ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L377))

- **Sonnet 4.6: Fail.** The brief mentions MSLSA §3.5 adjusting milestones 'day-for-day when Arcadia's failure to perform its responsibilities causes delay,' but does not specifically identify the 45-day Project Manager gap (Kevin Liu's departure) or the 75-day late API specifications as concrete examples of Arcadia's contributory delays. The criterion requires that these specific contributing failures be identified. The brief's general reference to Arcadia's failure to perform responsibilities is insufficient to satisfy the criterion's requirement for specific mention of these delays.
- **GPT-5.5: Fail.** The brief generally notes that milestones could adjust for Arcadia-caused delays, but it does not identify the specific Arcadia contributing failures required by the criterion, such as the 45-day Project Manager gap after Kevin Liu’s departure or the 75-day late API specifications.

### C-046

ISSUE_011 — Puffery defense raised for fraud/DTPA claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L385))

- **Sonnet 4.6: Pass.** The brief explicitly addresses puffery in Section V.B: 'Industry-leading performance' is generalized promotional opinion, not a measurable fact. See Pizza Hut, Inc. v. Papa John's Int'l, Inc., 227 F.3d 489, 497 (5th Cir. 2000). The '30-40%' statement is also addressed as a qualified, aggregate statement that cannot support fraud. Both statements are characterized as non-actionable, satisfying the criterion.
- **GPT-5.5: Pass.** The brief raises a puffery/qualified-statement defense: it argues that “industry-leading performance” is generalized promotional opinion rather than measurable fact, and that the “30–40%” improvement statement was qualified as typical, variable results and not an unqualified guarantee on which reliance was plausible. Although the DTPA count is primarily attacked on the statutory high-value exemption, the puffery defense is clearly raised in the motion for the alleged misrepresentations.

### C-047

ISSUE_011 — References disclaimers in sales materials/proposal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L393))

- **Sonnet 4.6: Pass.** The brief explicitly references disclaimers in the sales materials and proposal in Section V.A: 'The sales materials and proposal also qualify the relevant statements: the "30–40%" figure describes typical results, says results vary with client environment/data quality/implementation, and is not a guarantee; integration is described as integration with major EHR platforms subject to configuration and accurate specifications.' It further states in Section V.B that 'the proposal and slide deck describe client-base results and expressly explain that actual results vary' and in Section V.B again references that 'The proposal and contract also describe EHR integration as subject to configuration and interface specifications, not an unconditional promise.' These references to disclaimers in the written proposal and sales materials as undercutting reasonable reliance satisfy the criterion.
- **GPT-5.5: Pass.** The brief expressly references qualifications/disclaimers in Meridian's sales materials, proposal, and slide deck, including that the 30–40% metric described typical results, that actual results vary with client environment/data quality/implementation, and that the statement was not a guarantee. It uses those disclaimers to argue reliance was unjustified or implausible.

### C-048

ISSUE_011 — Cites puffery case law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L401))

- **Sonnet 4.6: Pass.** The brief cites Pizza Hut, Inc. v. Papa John's Int'l, Inc., 227 F.3d 489, 497 (5th Cir. 2000) in Section V.B when discussing that 'industry-leading performance' is generalized promotional opinion (puffery), not a measurable fact. This satisfies the criterion of citing at least one puffery case.
- **GPT-5.5: Pass.** The brief cites puffery case law: it states that “Industry-leading performance” is generalized promotional opinion and cites Pizza Hut, Inc. v. Papa John's Int'l, Inc., 227 F.3d 489, 497 (5th Cir. 2000). This satisfies the criterion.

### C-049

ISSUE_012 — Choice of law addressed for contract claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L409))

- **Sonnet 4.6: Pass.** In Section VI of the brief, the agent explicitly states: 'The MSLSA and SOW-1 are the source of Meridian's contractual duties... Delaware law governs the agreement under §12.7; the Court should enforce the unambiguous allocation of responsibilities reflected in the writings.' This directly addresses the choice-of-law issue for Count I (Breach of Contract) by citing the MSLSA's Section 12.7 choice-of-law clause and identifying Delaware law as governing.
- **GPT-5.5: Pass.** The brief expressly addresses choice of law for Count I, stating in the breach-of-contract section that “Delaware law governs the agreement under §12.7” and arguing the Court should enforce the contract accordingly.

### C-050

ISSUE_012 — Addresses choice of law for tort claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L417))

- **Sonnet 4.6: Fail.** The brief mentions in Section VI that 'Delaware law governs the agreement under §12.7' but this is only in the context of the contract count (Count I). For the tort claims (Counts II and III - fraud and negligent misrepresentation), the brief analyzes them entirely under Texas law without ever addressing whether the contractual choice-of-law clause (Delaware law) extends to these non-contractual claims, or arguing under both Delaware and Texas law. The choice-of-law question for the tort claims is entirely ignored.
- **GPT-5.5: Fail.** The brief discusses Texas law for fraud and negligent misrepresentation and notes that Delaware law governs the contract, but it does not address the choice-of-law issue for the tort claims, does not analyze whether the contractual Delaware choice-of-law clause extends to non-contractual claims, and does not argue the tort issues under both Delaware and Texas law.

### C-051

ISSUE_012 — Recognizes DTPA is necessarily Texas law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L425))

- **Sonnet 4.6: Pass.** Section III of the brief explicitly addresses Count V (DTPA) by citing Texas Business and Commerce Code § 17.49(f) and applying Texas statutory standards throughout. The brief treats the DTPA claim as governed by Texas law, not Delaware law (which is noted as governing the contract under §12.7 but is not applied to the DTPA count).
- **GPT-5.5: Pass.** The brief treats Count V (DTPA) as governed by Texas law by applying the Texas Business and Commerce Code § 17.49(f) high-value-transaction exemption and Texas statutory DTPA standards. It does not argue that the DTPA claim is governed by Delaware law.

### C-052

ISSUE_012 — Arguments work under both Delaware and Texas law ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L433))

- **Sonnet 4.6: Fail.** The brief mentions that Delaware law governs the agreement under §12.7 in Section VI, but then proceeds to cite exclusively Texas law throughout the entire brief for all substantive arguments (DTPA, unjust enrichment, fraud, negligent misrepresentation, contract interpretation). The brief does not argue in the alternative that the same results would follow under Delaware law, nor does it address whether Delaware law would reach the same conclusions on any of the key issues (e.g., unjust enrichment when an express contract exists, non-reliance clauses defeating fraud claims, DTPA applicability). The criterion requires the brief to demonstrate that even if Texas law governs rather than Delaware law (or vice versa), the result is the same. The brief fails to do this — it simply applies Texas law to tort and statutory claims without acknowledging the choice-of-law issue for those claims, and acknowledges Delaware law governs the contract without then arguing the contract points under Delaware law or showing the results are the same under both.
- **GPT-5.5: Fail.** The brief does not consistently argue in the alternative under both Delaware and Texas law. It relies on Texas law for DTPA, unjust enrichment, fraud, and negligent misrepresentation, and on Delaware law for the contract interpretation section, without demonstrating that the same dismissal results would follow if the other state’s law governed. Therefore it fails the criterion.

### C-053

Motion brief — argues reliance was unreasonable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L441))

- **Sonnet 4.6: Pass.** Section V.A of the brief explicitly argues that Arcadia's reliance was not justifiable as a matter of law. It cites: (1) Arcadia's status as a sophisticated commercial healthcare-IT provider, (2) that Arcadia conducted due diligence and engaged outside counsel during negotiations, (3) the express non-reliance acknowledgment in MSLSA §12.1 (which is more than a generic merger clause), (4) written disclaimers in the sales materials qualifying the '30-40%' figure and integration capabilities, and (5) the 'as is/as available' disclaimer and limited written performance warranty. The brief also cites Schlumberger and Forest Oil for the proposition that clear non-reliance provisions negotiated by sophisticated parties defeat justifiable reliance. This satisfies the criterion requiring the brief to argue reliance was unreasonable as a matter of law citing factors such as due diligence, counsel representation, written disclaimers, and integration clause.
- **GPT-5.5: Pass.** The brief expressly challenges Arcadia's justifiable/reasonable reliance on pre-sale representations, arguing that reliance is defeated by a negotiated non-reliance provision, superseding/integration language, disclaimers, Arcadia's sophistication, due diligence, and representation by counsel. This satisfies the criterion even though it does not specifically name Schreiber's POC trial or reference checks.

### C-054

Motion brief — references Schreiber memo to undermine reliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L449))

- **Sonnet 4.6: Fail.** The motion brief does not reference Martin Schreiber's internal due diligence memo or the specific quote 'Integration complexity is manageable but will require a skilled SI partner' anywhere in the document. The brief mentions Martin Schreiber only as one of Arcadia's LLC members in the jurisdictional section (FAC ¶¶ 7-8), not in connection with any due diligence memo or reliance arguments.
- **GPT-5.5: Fail.** The brief does not cite or reference Martin Schreiber's internal due diligence memo or the quoted acknowledgment about integration complexity and needing a skilled SI partner. It only generally mentions due diligence and Schreiber in the citizenship allegations.

### C-055

Motion brief — exclusive remedies clause (Section 8.3) cited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L457))

- **Sonnet 4.6: Pass.** The brief mentions Section 8.3 in Section VI.D: 'Sections 8.1--8.3 cap aggregate liability, exclude specified consequential and exemplary damages, and provide exclusive contractual remedies.' This references Section 8.3 as providing exclusive contractual remedies, which satisfies the criterion of citing Section 8.3 (Exclusive Remedies) as limiting Arcadia to the remedies set forth in the MSLSA.
- **GPT-5.5: Pass.** The motion brief expressly cites “Sections 8.1--8.3” and states they “provide exclusive contractual remedies,” and later requests enforcement of the MSLSA’s “exclusive-remedy” provisions. This references Section 8.3 as limiting remedies under the agreement.

### C-056

Motion brief — warranty disclaimer (Section 9.4) cited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L465))

- **Sonnet 4.6: Pass.** The brief mentions Section 9.4 in Section V.A: 'It is paired with the "as is/as available" disclaimer and a limited, written performance warranty. MSLSA §§ 9.1, 9.4, 12.1.' This references Section 9.4 in the context of the warranty disclaimer paired with the non-reliance clause, which is relevant to barring or limiting warranty-based claims. The criterion requires that Section 9.4 be mentioned as barring or limiting warranty-based claims, and it is cited in that context.
- **GPT-5.5: Pass.** The brief expressly cites “MSLSA §§ 9.1, 9.4, 12.1” and describes Section 9.4 as part of an “as is/as available” disclaimer paired with a limited written performance warranty, thereby referencing the warranty disclaimer as limiting claims.

### C-057

Motion brief — limited warranty scope (Section 9.1) analyzed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L473))

- **Sonnet 4.6: Pass.** Section VI.D of the brief explicitly discusses Section 9.1, noting 'The limited warranty in §9.1 runs 90 days from Go-Live' and that 'The warranty remedy is repair/replacement and, after an uncured notice period, a pro-rata refund of prepaid license fees, not automatic restitution of every fee paid.' This directly addresses the 90-day warranty period and the repair/replace/pro-rata refund remedy structure in the breach of contract analysis.
- **GPT-5.5: Pass.** The brief discusses MSLSA Section 9.1 in the breach-of-contract section, noting the 90-day warranty period, repair/replacement remedy, and pro-rata refund after an uncured notice period, and argues that any warranty-based claim should be limited to that remedy structure.

### C-058

Motion brief — no oral modifications clause (Section 12.3) cited ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L481))

- **Sonnet 4.6: Fail.** The motion brief does not reference Section 12.3 (No Oral Modifications) anywhere in the document. The brief discusses Section 12.1 (non-reliance acknowledgment), Section 12.7 (governing law), and various other contract provisions, but never cites Section 12.3 as supporting the argument that pre-sale oral statements cannot modify or supplement the written agreement.
- **GPT-5.5: Fail.** The motion brief does not cite or reference Section 12.3 or a No Oral Modifications clause in support of the argument that pre-sale oral statements cannot modify or supplement the written agreement. It cites Section 12.1 and other provisions, but not 12.3.

### C-059

Proposed order — correct court identification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L489))

- **Sonnet 4.6: Pass.** The proposed order clearly identifies the court as 'UNITED STATES DISTRICT COURT, WESTERN DISTRICT OF TEXAS, AUSTIN DIVISION' in the header, which matches the required court identification exactly.
- **GPT-5.5: Pass.** The proposed order heading identifies the court as the United States District Court, Western District of Texas, Austin Division, which matches the required court identification.

### C-060

Proposed order — correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L497))

- **Sonnet 4.6: Pass.** The proposed order includes the case number '1:23-cv-00847-CMA' in the caption, which matches the correct case number specified in the criterion.
- **GPT-5.5: Pass.** The proposed order caption includes the civil action number '1:23-cv-00847-CMA,' which matches the required correct case number.

### C-061

Proposed order — correct party names ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L505))

- **Sonnet 4.6: Pass.** The proposed order clearly includes both correct party names: 'ARCADIA HEALTH SYSTEMS, LLC' as Plaintiff and 'MERIDIAN CLOUD SOLUTIONS, INC.' as Defendant, appearing in the caption and throughout the order.
- **GPT-5.5: Pass.** The proposed order correctly identifies the parties as Arcadia Health Systems, LLC and Meridian Cloud Solutions, Inc. in the caption and throughout the order.

### C-062

Proposed order — grants dismissal of all five counts ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L513))

- **Sonnet 4.6: Fail.** The criterion requires the proposed order to grant dismissal of ALL five counts. However, the proposed order grants the motion only in part. Specifically, paragraph 7 states the motion is DENIED insofar as it seeks dismissal of any remaining contract claim (Count I - Breach of Contract) alleging a nonconforming software or implementation/support obligation. Thus, Count I (Breach of Contract) is not fully dismissed - only certain theories within it are dismissed. The order does not grant dismissal of all five counts as required by the criterion.
- **GPT-5.5: Fail.** The proposed order addresses all five counts, but it does not grant dismissal of the breach-of-contract count in full; it expressly denies dismissal as to remaining contract claims. Therefore it does not grant dismissal of all five counts.

### C-063

Proposed order — dismissal with prejudice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L521))

- **Sonnet 4.6: Pass.** The proposed order specifies dismissal with prejudice for at least two claims: Count V (Texas DTPA claim) is 'DISMISSED WITH PREJUDICE' and Count I is 'DISMISSED WITH PREJUDICE' insofar as it asserts certain theories. The criterion asks whether the proposed order specifies dismissal with prejudice, which it does.
- **GPT-5.5: Pass.** The proposed order expressly specifies dismissal with prejudice for the Texas DTPA claim and portions of Count I, even though other claims are dismissed without prejudice.

### C-064

Cover memo — identifies Meridian's Texas citizenship ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L529))

- **Sonnet 4.6: Pass.** In Section 1 of the cover memo, the agent explicitly states: 'Meridian is incorporated in Delaware with its principal place of business in Texas.' This correctly identifies both of Meridian's citizenships — Delaware (state of incorporation) and Texas (principal place of business). The criterion requires that Meridian's Texas citizenship be noted, and it is clearly noted here.
- **GPT-5.5: Pass.** The cover memo states that Meridian is incorporated in Delaware and has its principal place of business in Texas, which identifies Texas citizenship in addition to Delaware citizenship for diversity purposes.

### C-065

Cover memo — notes that subject-matter jurisdiction cannot be waived ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L537))

- **Sonnet 4.6: Pass.** The cover memo explicitly states in Section 1: 'If the complete diversity defect is confirmed, the federal court must remand; it cannot dismiss the state-law claims on the merits.' and recommends 'requesting that the Court determine jurisdiction sua sponte before any merits decision.' The memo also cites Arbaugh v. Y & H Corp. and 28 U.S.C. § 1447(c) in the context of the court's obligation to address jurisdiction. The executive recommendation section states the Court 'must address subject-matter jurisdiction before merits.' The mention of the court raising jurisdiction sua sponte directly addresses the non-waivable nature of subject-matter jurisdiction and the court's ability to raise it at any time.
- **GPT-5.5: Fail.** The memo identifies subject-matter jurisdiction as a threshold issue and says the court may address it sua sponte, but it does not state that subject-matter jurisdiction is non-waivable or can be raised at any time. The required legal point is therefore not fully mentioned.

### C-066

Cover memo — discusses strategic implications of raising jurisdiction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L545))

- **Sonnet 4.6: Pass.** The cover memo does discuss the strategic implications of raising the jurisdictional defect. It notes that if the diversity defect is confirmed, the federal court must remand under 28 U.S.C. § 1447(c) and cannot dismiss the state-law claims on the merits. It also notes that removal and subsequent transfer to Austin do not create jurisdiction, and that the Court must address subject-matter jurisdiction before merits. The memo recommends filing a jurisdictional notice/motion to remand or requesting the Court determine jurisdiction sua sponte. It also mentions that if remanded, Texas state-court procedures and deadlines must be assessed, including that Texas Rule of Civil Procedure 91a may no longer be available. However, the memo does not discuss the strategic implications in the fuller sense described in the criterion — it does not discuss whether state court is a less favorable forum, whether the federal judge is known for rigorous Twombly/Iqbal application, or the risk of the court discovering the defect independently if not raised. The memo focuses primarily on the legal obligation to raise jurisdiction and the procedural consequences of remand, rather than the strategic calculus of raising vs. not raising the issue. The criterion specifically asks for discussion of implications such as remand to a potentially less favorable forum, different procedural rules, loss of a federal judge known for rigorous pleading standards, or the risk of the court discovering it independently. The memo does mention remand to state court and notes Texas Rule 91a procedural differences, which partially addresses the 'different procedural rules' aspect. It also implicitly addresses the risk of the court discovering it by recommending proactive filing. On balance, the memo does provide some strategic analysis — it recommends raising the issue proactively (implying the risk of court discovery), notes the procedural differences in state court (Rule 91a), and discusses the consequence of remand. This satisfies the criterion at least partially, and the criterion says 'e.g.' suggesting these are examples, not requirements. The memo's recommendation to raise the issue and its discussion of remand consequences and state court procedural differences constitutes strategic analysis of the implications of raising the jurisdictional defect.
- **GPT-5.5: Pass.** The cover memo identifies the jurisdictional defect as a threshold issue, explains that confirming it would require remand under 28 U.S.C. § 1447(c) and prevent a federal merits ruling, recommends raising it before filing a merits motion, and notes downstream strategic consequences if remanded, including different Texas state-court procedures and potential unavailability of Rule 91a. This satisfies the requirement to discuss strategic implications of raising the defect.

### C-067

Factual accuracy — contract value stated as $14.7 million ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L553))

- **Sonnet 4.6: Pass.** The motion brief explicitly states 'The FAC alleges a $14.7 million base contract and $2.35 million in Change Orders; the MSLSA confirms the $14.7 million base amount.' This correctly identifies the MSLSA total contract value as $14.7 million, matching the criterion.
- **GPT-5.5: Pass.** The motion brief states that the FAC alleges a "$14.7 million base contract" and that the MSLSA confirms the "$14.7 million base amount," correctly identifying the MSLSA total contract value as $14,700,000 / $14.7 million.

### C-068

Factual accuracy — change orders total $2.35 million ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L561))

- **Sonnet 4.6: Pass.** The motion brief states in Section III: 'The FAC alleges a $14.7 million base contract and $2.35 million in Change Orders.' This correctly identifies the total change order value as $2.35 million, which matches the criterion ($680,000 + $420,000 + $350,000 + $900,000 = $2,350,000).
- **GPT-5.5: Pass.** The motion brief correctly states that the Change Orders total $2.35 million, matching the required $2,350,000 total.

### C-069

Factual accuracy — total claimed damages $47.3 million ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L569))

- **Sonnet 4.6: Fail.** The motion brief does not mention the total claimed damages figure of $47.3 million (or $47,300,000) anywhere in the document. The brief references the $14.7 million base contract and $2.35 million in Change Orders, but never states the total claimed damages amount of $47.3 million. The criterion requires the brief to correctly state this figure.
- **GPT-5.5: Fail.** The motion brief does not state that Arcadia claims $47,300,000 or $47.3 million in total damages; it only references other amounts such as the $14.7 million base contract and $2.35 million in change orders. Therefore it fails the specified factual-accuracy criterion.

### C-070

Factual accuracy — MSLSA execution date March 15, 2022 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L577))

- **Sonnet 4.6: Fail.** The motion brief does not mention the MSLSA execution date of March 15, 2022 anywhere in the document. The criterion requires that the brief correctly states the MSLSA was executed on March 15, 2022. Since the date is entirely absent from the brief, it fails to satisfy the criterion.
- **GPT-5.5: Fail.** The motion brief does not state that the MSLSA was executed on March 15, 2022. Because the criterion requires the brief to correctly state that execution date, the output does not satisfy it.

### C-071

Factual accuracy — Go-Live date January 15, 2023 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L585))

- **Sonnet 4.6: Pass.** In Section VI.D of the brief, the agent explicitly states: 'The FAC alleges Go-Live on January 15, 2023 and a written email complaint on March 8, 2023---within the 90-day warranty period.' This correctly identifies the Go-Live date as January 15, 2023.
- **GPT-5.5: Pass.** The brief expressly states that the FAC alleges Go-Live occurred on January 15, 2023, which matches the required actual Go-Live date.

### C-072

Factual accuracy — first written complaint March 8, 2023 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L593))

- **Sonnet 4.6: Pass.** In Section VI.D, the brief states: 'The FAC alleges Go-Live on January 15, 2023 and a written email complaint on March 8, 2023---within the 90-day warranty period.' This correctly identifies the first written complaint as occurring on March 8, 2023, matching the criterion.
- **GPT-5.5: Pass.** The brief states that Arcadia made a written email complaint on March 8, 2023, and treats that as the first notice/complaint for warranty purposes. The date is not materially incorrect, though the sender is not expressly named in that sentence.

### C-073

Factual accuracy — Delaware governs per Section 12.7 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L601))

- **Sonnet 4.6: Pass.** In Section VI of the brief, the agent explicitly states: 'Delaware law governs the agreement under §12.7; the Court should enforce the unambiguous allocation of responsibilities reflected in the writings.' This correctly identifies Section 12.7 as the governing law clause and correctly states that it specifies Delaware law.
- **GPT-5.5: Pass.** The brief correctly states that Delaware law governs the agreement under MSLSA Section 12.7, satisfying the criterion.

### C-074

Factual accuracy — Arcadia represented by counsel during negotiations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L609))

- **Sonnet 4.6: Fail.** The criterion requires that the motion brief specifically mention that Arcadia was represented by outside counsel (Wexford Hale LLP) during contract negotiations. The brief does mention that Arcadia 'engaged outside counsel' in Section V.A, but it does not name the firm 'Wexford Hale LLP.' The criterion specifically states to PASS if the brief notes Arcadia was represented by outside counsel (Wexford Hale LLP). Since the specific firm name is not mentioned, this fails the criterion as stated.
- **GPT-5.5: Fail.** The brief states that Arcadia “engaged outside counsel” and that the parties were represented by counsel, but it does not identify the outside counsel as Wexford Hale LLP during contract negotiations.

### C-075

Factual accuracy — 47 support tickets breakdown correct ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L617))

- **Sonnet 4.6: Fail.** The motion brief does not reference the support ticket data at all — there is no mention of 47 total tickets, 31 resolved within SLA, 12 related to data quality/Linden Park Consulting, or 4 software defects patched anywhere in the document. The criterion states FAIL if the ticket data is cited but materially misstated, but it also implicitly requires the data to be present. Since the data is entirely absent rather than misstated, the brief fails to satisfy the criterion of referencing the support ticket data with substantially correct figures.
- **GPT-5.5: Fail.** The brief does not reference the support ticket breakdown at all—no mention of 47 total tickets, 31 resolved within SLA, 12 data quality/Linden Park tickets, or 4 patched software defects—so it does not satisfy the criterion requiring substantially correct figures.

### C-076

Motion brief — requests dismissal with prejudice rather than without ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L625))

- **Sonnet 4.6: Pass.** The brief explicitly requests dismissal with prejudice for Count V (DTPA): 'Count V should be dismissed with prejudice.' For Count IV (unjust enrichment), it requests dismissal 'at least without prejudice to any properly supported alternative restitution theory,' which is a qualified dismissal without prejudice. For the fraud and negligent misrepresentation counts, it requests dismissal but does not specify with or without prejudice in the conclusion. The conclusion section requests 'dismissal without prejudice where amendment could cure a pleading defect.' However, the criterion states PASS if the brief requests dismissal with prejudice for all counts OR at minimum for the counts where it is appropriate (DTPA and unjust enrichment). The DTPA count is explicitly requested to be dismissed with prejudice. The unjust enrichment count is requested to be dismissed (at least without prejudice), which is not with prejudice. However, the criterion specifically calls out DTPA as a key count where with-prejudice dismissal is appropriate, and the brief does request that. The criterion says 'PASS if the motion brief requests dismissal with prejudice for all counts (or at minimum for the counts where dismissal with prejudice is appropriate, such as unjust enrichment and DTPA).' The DTPA count gets with-prejudice treatment explicitly. The unjust enrichment count gets dismissal without prejudice. Since the criterion uses 'such as' suggesting these are examples, and the DTPA clearly gets with-prejudice treatment, this satisfies at least the minimum threshold described in the criterion.
- **GPT-5.5: Pass.** The brief expressly requests dismissal with prejudice for the DTPA count, and it does not request dismissal without prejudice across the board. Although it suggests unjust enrichment be dismissed at least without prejudice, the criterion is satisfied because the brief includes a with-prejudice dismissal request for an appropriate count rather than only seeking without-prejudice dismissal.

### C-077

Motion brief — identifies Rule 12(b)(6) as the procedural vehicle ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L633))

- **Sonnet 4.6: Pass.** The motion brief is explicitly framed as a motion under Federal Rule of Civil Procedure 12(b)(6). The title states 'MOTION TO DISMISS FIRST AMENDED COMPLAINT UNDER RULE 12(B)(6), OR ALTERNATIVELY RULE 12(C)'. The introductory paragraph states 'Defendant Meridian Cloud Solutions, Inc. moves to dismiss...under Federal Rule of Civil Procedure 12(b)(6)'. Section I also references Rule 12(b)(6) explicitly. The procedural rule is clearly identified throughout the document.
- **GPT-5.5: Pass.** The motion is explicitly titled as a motion to dismiss under Rule 12(b)(6), and the opening paragraph states Meridian moves to dismiss under Federal Rule of Civil Procedure 12(b)(6) for failure to state a claim, with Rule 12(c) only as an alternative procedural vehicle.

### C-078

Motion brief — addresses post-answer motion practice authorization ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L641))

- **Sonnet 4.6: Pass.** The brief explicitly addresses post-answer motion practice in the opening paragraph and in Section I. It notes that Meridian 'expressly preserved failure to state a claim in its Answer,' references the Court's case-specific Scheduling Order treating post-answer motions as Rule 12(c) motions, and specifically mentions that 'the Court's Standing Order separately permits a preserved post-answer Rule 12(b)(6) motion.' Section I further states that 'Meridian's Answer expressly preserved this defense. (Answer, First Affirmative Defense and reservation of Rule 12 rights.)' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The brief explicitly states that Meridian moves post-answer under Rule 12(b)(6) or alternatively Rule 12(c), that Meridian preserved failure to state a claim in its Answer, and that Judge Alvarez's Standing Order permits a preserved post-answer Rule 12(b)(6) motion. It also reiterates this in the procedural posture section.

### C-079

Motion brief — argues Count I breach of contract fails with specific contractual provisions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L649))

- **Sonnet 4.6: Pass.** The brief addresses Count I (Breach of Contract) in Section VI and explicitly references multiple specific contractual provisions: SOW-1 §3.2 (data migration responsibility/causation), §5.3 (deemed acceptance), §§8.1-8.3 (liability cap and consequential damages exclusion), and §12.1 (non-reliance/integration clause discussed in Section V). All four of the listed provisions are invoked in arguments for dismissal or narrowing of Count I.
- **GPT-5.5: Pass.** The brief addresses Count I in Section VI and argues it should be narrowed based on specific contractual provisions, including SOW-1 §3.2 assigning data migration responsibility to Arcadia, MSLSA §§ 8.1–8.3 limiting liability and excluding consequential damages, and §5.3 deemed acceptance. These are among the provisions identified in the criterion.

### C-080

Motion brief — argues fraud claim fails for lack of reliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L657))

- **Sonnet 4.6: Pass.** Section V of the brief directly addresses the fraud and negligent misrepresentation claims and argues that Arcadia cannot establish justifiable reliance. Specifically, Section V.A argues that the express, mutual non-reliance acknowledgment in MSLSA §12.1 (not merely a generic merger clause), combined with Arcadia's sophisticated status, engagement of outside counsel, and the qualified nature of the sales representations, defeats justifiable reliance. The brief cites Schlumberger and Forest Oil for the proposition that clear non-reliance provisions negotiated by sophisticated parties can defeat justifiable reliance. Section V.C similarly applies the non-reliance argument to the negligent misrepresentation count. The brief covers integration clause/non-reliance provision, disclaimers in the proposal and slide deck, Arcadia's due diligence and counsel engagement, and Arcadia's sophisticated commercial status — all elements specified in the criterion.
- **GPT-5.5: Pass.** The brief expressly argues the fraud claim fails because Arcadia cannot plead justifiable reliance. It relies on the MSLSA’s express non-reliance/integration clause, disclaimers and qualified statements, Arcadia’s due diligence, and Arcadia’s sophisticated commercial status with counsel.

### C-081

Motion brief — cites Fifth Circuit authority beyond Twombly/Iqbal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L665))

- **Sonnet 4.6: Pass.** The brief cites multiple Fifth Circuit cases beyond Twombly/Iqbal: Collins v. Morgan Stanley Dean Witter (5th Cir. 2000), Harvey v. Grey Wolf Drilling Co. (5th Cir. 2008), Benchmark Elecs., Inc. v. J.M. Huber Corp. (5th Cir. 2003), Dorsey v. Portfolio Equities, Inc. (5th Cir. 2008), and Pizza Hut, Inc. v. Papa John's Int'l, Inc. (5th Cir. 2000). This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The motion brief cites multiple Fifth Circuit authorities beyond Twombly/Iqbal, including Collins v. Morgan Stanley, Harvey v. Grey Wolf Drilling, Benchmark Electronics v. J.M. Huber, Dorsey v. Portfolio Equities, and Pizza Hut v. Papa John's.

### C-082

Motion brief — references negotiation emails showing Arcadia's awareness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L673))

- **Sonnet 4.6: Fail.** The motion brief does not reference the contract negotiation email chain (Exhibit D / Bates Nos. MCS-00004217 through MCS-00004248) or Jonathan Breckenridge of Wexford Hale LLP's attempts to negotiate removal of the consequential damages waiver and expanded warranty terms. While the brief does argue that Arcadia was a sophisticated party represented by counsel and that the non-reliance provision was negotiated, it does not cite this specific exhibit or the specific negotiation history showing Arcadia's awareness and acceptance of the contractual risk allocation.
- **GPT-5.5: Fail.** The brief mentions generally that Arcadia was represented by counsel and had an opportunity to negotiate, but it does not cite or reference the contract negotiation email chain, Exhibit D, Bates Nos. MCS-00004217 through MCS-00004248, Jonathan Breckenridge/Wexford Hale, or the attempted negotiation of the consequential damages waiver and warranty terms.

### C-083

Motion brief — DTPA arguments beyond § 17.49(f) exemption ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L681))

- **Sonnet 4.6: Fail.** The motion brief's DTPA section (Count V) relies solely on the § 17.49(f) high-value-transaction exemption as the basis for dismissal. The brief does not include any additional DTPA-specific arguments such as puffery, lack of producing cause, or that the DTPA claim is duplicative of the contract claim. The puffery and other arguments appear in the fraud/negligent misrepresentation sections (Counts II and III), not in the DTPA count. The criterion requires at least one additional argument for dismissing the DTPA claim beyond § 17.49(f).
- **GPT-5.5: Fail.** The brief’s DTPA-specific argument is limited to the Texas Business & Commerce Code § 17.49(f) high-value-transaction exemption. Although the brief discusses puffery, reliance, and contractual limitations in connection with fraud/negligent misrepresentation and contract claims, it does not present any additional argument for dismissing the DTPA claim itself, such as puffery under the DTPA, lack of producing cause, or duplication of the contract claim.

### C-084

Motion brief — addresses deemed acceptance impact on warranty claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L689))

- **Sonnet 4.6: Fail.** The brief discusses deemed acceptance under Section 5.3 and the warranty analysis in Section VI.D, but treats them as separate concepts. The deemed acceptance discussion focuses on foreclosing 'untimely rejection/full-refund theory,' while the warranty discussion separately addresses the 90-day warranty period and remedies. The brief does not draw the connection that deemed acceptance means Arcadia acknowledged the software performed substantially in accordance with documentation, which would undermine the warranty breach claim itself. The two concepts are discussed in the same paragraph but without the specific logical link required by the criterion — that deemed acceptance constitutes an acknowledgment of substantial conformance that undermines the warranty breach theory.
- **GPT-5.5: Fail.** The brief discusses Section 5.3 deemed acceptance and the limited warranty in the same subsection, but it does not argue that deemed acceptance constitutes Arcadia’s acknowledgment that the software substantially conformed to documentation or that this undermines a warranty breach claim. Instead, it states deemed acceptance forecloses untimely rejection/full-refund theories but does not erase post-acceptance warranty duties.

### C-085

Motion brief — correctly identifies all five counts by number and name ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L697))

- **Sonnet 4.6: Pass.** The brief references: Count I as breach of contract (Section VI heading and throughout), Count II as fraud (Section V heading references 'Counts II and III' and 'fraud count'), Count III as negligent misrepresentation (Section V.C explicitly), Count IV as unjust enrichment (Section IV heading: 'COUNT IV SEEKS EQUITABLE RECOVERY'), and Count V as DTPA (Section III heading: 'COUNT V FAILS BECAUSE THE TRANSACTION EXCEEDS THE DTPA'S HIGH-VALUE-TRANSACTION EXEMPTION'). All five counts are correctly numbered and labeled.
- **GPT-5.5: Fail.** The brief references the counts generally, but it does not correctly identify all five by both number and name. In particular, Count I is discussed as the “contract count” and “contractual obligations” but is not clearly labeled as Count I (Breach of Contract), and Count II is not expressly labeled as Count II (Fraud) in the count identification. Therefore it does not satisfy the criterion.

### C-086

Motion brief — argues Count II (Fraud) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L705))

- **Sonnet 4.6: Pass.** Section V.B of the brief explicitly argues that Count II (fraud) should be dismissed under Rule 9(b) and Twombly/Iqbal, citing lack of particularity regarding falsity when made and scienter. Section V.A also argues lack of justifiable reliance based on the non-reliance clause. The conclusion requests dismissal of 'Counts II through V.' Multiple grounds are presented for dismissing Count II.
- **GPT-5.5: Pass.** The motion brief explicitly requests dismissal of Count II/Fraud, including in the introduction, Section V addressing Counts II and III, Section V.B stating the fraud claim should be dismissed under Rule 9(b) and Twombly/Iqbal, and the conclusion requesting dismissal of Counts II through V.

### C-087

Motion brief — argues Count III (Negligent Misrepresentation) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L713))

- **Sonnet 4.6: Pass.** Section V.C of the motion brief explicitly addresses Count III (Negligent Misrepresentation) and argues it should be dismissed on grounds including: (1) lack of justifiable reliance due to the express non-reliance acknowledgment and qualification of estimates, (2) failure to separate specific false information from contractual performance failures, and (3) improper damages sought (benefit-of-the-bargain rather than reliance damages). The conclusion also requests dismissal of Counts II through V, which includes Count III.
- **GPT-5.5: Pass.** The brief explicitly addresses Count III (Negligent Misrepresentation), arguing it fails due to lack of justifiable reliance/non-reliance provisions and insufficient separation from contract duties, and requests dismissal of Counts II through V in the conclusion.

### C-088

Motion brief — argues Count IV (Unjust Enrichment) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L721))

- **Sonnet 4.6: Pass.** Section IV of the motion brief explicitly addresses Count IV (Unjust Enrichment) and argues it should be dismissed because the MSLSA (an express contract) governs the same subject matter, citing Fortune Prod. Co. v. Conoco, Inc. and Excess Underwriters at Lloyd's v. Frank's Casing Crew. The conclusion also requests dismissal of Counts II through V, which includes Count IV. The express contract bar is clearly articulated as the basis for dismissal.
- **GPT-5.5: Pass.** The brief expressly argues that Count IV for unjust enrichment/quantum meruit is barred because the MSLSA and related writings are valid express contracts governing the same subject matter, and it explicitly requests that the Court dismiss Count IV.

### C-089

Motion brief — argues Count V (DTPA) should be dismissed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-to-dismiss-brief/task.json#L729))

- **Sonnet 4.6: Pass.** Section III of the motion brief explicitly argues that Count V (DTPA) should be dismissed based on the Texas Business and Commerce Code § 17.49(f) exemption for transactions exceeding $500,000. The brief identifies the $14.7 million base contract plus $2.35 million in Change Orders as far exceeding the threshold, and concludes 'Count V should be dismissed with prejudice.'
- **GPT-5.5: Pass.** The motion brief explicitly argues that Count V (DTPA) should be dismissed, including a dedicated section titled 'COUNT V FAILS BECAUSE THE TRANSACTION EXCEEDS THE DTPA'S HIGH-VALUE-TRANSACTION EXEMPTION' and requests dismissal based on Texas Business and Commerce Code § 17.49(f) because the transaction exceeds $500,000 and does not involve a consumer residence.
