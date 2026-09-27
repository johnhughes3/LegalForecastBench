# Claude Opus 5.5 audit: Draft Opposition to Motion to Dismiss — Memorandum of Law in Opposition (Restrictive Covenant, Trade Secrets, Tortious Interference)

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 63. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is largely sound. Many of its apparently hidden requirements come straight from the supervising partner's strategy memo, which the solver receives: the Argument A-E headings, Twombly/Iqbal, complaint paragraph cites, the press-release 'quasi-admission' use, the 24-day gap, and the notification emails. So Sol's F1, F4 and F5 are not defects. The one clear defect is C-011. Its examples name Deming and Weiss as reformation authority; I re-read both this session, and neither holds that. The effect is that the criterion rewards the memo's planted miscitation instead of catching it. Three more issues are debatable. C-009 requires saying Connecticut courts 'routinely' reform covenants, which is contrary to the narrow Beit rule quoted in Deming. C-029 mandates a constructive-knowledge theory that Weiss itself undercuts. C-040 requires citing emails outside the pleadings whose senders conflict with the complaint. Because a run scores only if every criterion passes for both judges, these mainly put careful, pleading-bound briefs at risk.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L102) | C-011 names Deming and Weiss as Connecticut reformation authority, but neither case supports reformation | revised |
| [O2](#o2) | arguable | legal_error | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L86) | C-009's PASS condition requires arguing that Connecticut courts 'routinely' reform overbroad covenants, which overstates the law | revised |
| [O3](#o3) | arguable | legal_error | [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L246) | C-029 requires a constructive-knowledge theory; in Weiss a 'should have known' interference count was reversed | revised |
| [O4](#o4) | arguable | document_defect | [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L334) | C-040 requires citing notification emails that sit outside the pleadings and name different senders than the complaint | blind |

<a id="o1"></a>
### O1. C-011 names Deming and Weiss as Connecticut reformation authority, but neither case supports reformation

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L102)

C-011's examples copy the strategy memo's mischaracterization, which looks like a planted trap: the memo tells the associate to 'Pull the full Weiss and Deming opinions and read them carefully'. Weiss holds only that the covenant was reasonable. The opinion has no hits for 'modif' or 'divisib', and 'sever' appears only in the phrase 'severance of his employment'. Deming fn.21 expressly declines to reach the blue-pencil question. It quotes Beit, which allows severance only of distinct covenants and says a court may not split an entire covenant, because that 'would be to make an agreement for the parties.' Correct briefs that cite Beit or trial-court decisions under express reformation clauses still pass. But the criterion states wrong law and rewards a brief that repeats the memo's miscitation, and the judges have no reference answer to catch it.

Evidence:
- `C-011`: “cites Connecticut case law supporting reformation of restrictive covenants (e.g., Deming v. Nationwide Mutual Insurance Co., Robert S. Weiss & Associates v. Wiederlight”
- `litigation-strategy-memo.docx.txt`: “the Connecticut Supreme Court endorsed modification of overbroad non-competes, holding that courts should narrow unreasonable restrictions rather than refuse enforcement altogether.”
- `litigation-strategy-memo.docx.txt`: “Pull the full *Weiss* and *Deming* opinions and read them carefully.”

Authorities (✓ = primary text checked in the auditing session):
- Deming v. Nationwide Mut. Ins. Co., 279 Conn. 745, 769-70 n.21 (2006) (✓): 'we need not address the plaintiffs' challenge as to whether the trial court improperly applied the "blue pencil" rule'; the court adopts no reasonable-modification rule
- Robert S. Weiss & Assocs., Inc. v. Wiederlight, 208 Conn. 525 (1988) (✓): Affirms that the covenant was reasonable and valid; contains no modification or divisibility holding
- Beit v. Beit, 135 Conn. 195, 204-05 (1948), as quoted in Deming fn.21 (✓): Severance is permissible only for a covenant that is in effect several distinct covenants; a court may not divide an entire covenant

Suggested fix: Remove Deming and Weiss as examples. Require 'Connecticut authority on divisibility/partial enforcement (e.g., Beit v. Beit) or decisions enforcing express reformation clauses.'

Related GPT-6 Sol findings: F2.

<a id="o2"></a>
### O2. C-009's PASS condition requires arguing that Connecticut courts 'routinely' reform overbroad covenants, which overstates the law

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L86)

PASS requires arguing that Connecticut courts 'routinely' blue-pencil or reform overbroad covenants. The Supreme Court's only stated rule, the Beit rule quoted in Deming fn.21, is narrow: it allows severance of distinct undertakings but forbids splitting an entire covenant. Broader reformation appears in Superior Court decisions, mostly where the contract has an express modification clause like RCA § 8.5. A candid brief would rest on § 8.5 and say the court 'may' narrow the covenant, acknowledging the split. That brief does not match PASS ('routinely'), yet it does not trigger FAIL ('does not address ... at all') either. The lenient FAIL condition means most judges would pass it, so this is arguable rather than problematic. But the criterion rewards the memo's overstatement.

Evidence:
- `C-009`: “PASS if the brief argues that Connecticut courts routinely apply blue-pencil or reformation doctrines to modify overbroad restrictive covenants”
- `litigation-strategy-memo.docx.txt`: “Connecticut courts routinely apply reformation --- sometimes called \"reasonable modification\" --- to restrictive covenants rather than voiding them entirely.”

Authorities (✓ = primary text checked in the auditing session):
- Deming v. Nationwide Mut. Ins. Co., 279 Conn. 745, 769-70 n.21 (2006) (quoting Beit v. Beit, 135 Conn. 195, 204-05 (1948)) (✓): Blue-pencil question left open; severance only of distinct covenants

Suggested fix: PASS if the brief argues the court has authority, under Connecticut divisibility/reformation doctrine and RCA § 8.5, to narrow rather than void an overbroad covenant.

Related GPT-6 Sol findings: F2.

<a id="o3"></a>
### O3. C-029 requires a constructive-knowledge theory; in Weiss a 'should have known' interference count was reversed

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L246)

C-029 fails any brief that does not 'raise constructive knowledge as a basis for Lodestar's awareness of the RCA.' The rubric's own cited case cuts against that theory. In Weiss, the complaint alleged the new employer 'knew or in the exercise of reasonable care should have known' of the covenant, and the Supreme Court reversed the interference judgment. Weiss turned on improper means or malice, not on knowledge. Here the complaint separately pleads improper means (misappropriation), so the theory is not foreclosed. Still, a careful brief would argue that actual knowledge or willful blindness is plausibly inferred, and would not lead with 'should have known.' It might also note that Count III concerns the client relationships (Compl. ¶181). The 'and/or due diligence' language will rescue many such briefs, but a literal judge could fail one that deliberately avoids the constructive-knowledge label.

Evidence:
- `C-029`: “FAIL if the brief does not raise constructive knowledge as a basis for Lodestar's awareness of the RCA.”
- `verified-complaint.docx.txt`: “181\. Lodestar knew of Pinnacle\'s business relationships with these clients.”
- `litigation-strategy-memo.docx.txt`: “The failure to do so is either willful blindness or actual knowledge.”

Authorities (✓ = primary text checked in the auditing session):
- Robert S. Weiss & Assocs., Inc. v. Wiederlight, 208 Conn. 525, 535-36 (1988) (✓): An interference count alleging the defendant 'knew or in the exercise of reasonable care should have known' of the covenant and 'encouraged' its breach did not plead improper motive or means; judgment reversed

Suggested fix: PASS if the brief argues Lodestar's knowledge of the RCA (actual, inferred, or willful blindness) is plausibly pleaded from facts such as industry practice, sophistication, or failure to inquire.

Related GPT-6 Sol findings: F3.

<a id="o4"></a>
### O4. C-040 requires citing notification emails that sit outside the pleadings and name different senders than the complaint

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L334)

The memo does tell the associate to pull the emails, so the requirement is not hidden. But the emails are not attached to the complaint. On a 12(b)(6) motion the court is limited to the complaint and documents integral to it, and partner direction does not cure that. A pleading-bound brief would cite ¶¶122-123 instead. Those paragraphs describe the clients as having 'notified' Pinnacle 'through its principal', without calling the notices emails, so a literal judge may find the brief never 'references the emails.' The record also conflicts. The complaint names Michael Sorrento and Victoria Langford as the notifiers. The emails come from Gerald Harmon and Tamara Voss, and they add facts the complaint does not plead, such as a forwarded cover letter from Whitaker herself.

Evidence:
- `verified-complaint.docx.txt`: “Northridge Resorts LLC notified Pinnacle on or about March 5, 2025, through its principal Michael Sorrento”
- `client-notification-emails.eml.txt`: “Gerald Harmon President, Northridge Resorts LLC”
- `verified-complaint.docx.txt`: “through its managing partner Victoria Langford”
- `litigation-strategy-memo.docx.txt`: “please pull the client notification emails from **Northridge Resorts LLC (dated March 5, 2025)** and **Coastal Haven Properties LP (dated March 20, 2025)** from the client file.”

Authorities (✓ = primary text checked in the auditing session):
- Chambers v. Time Warner, Inc., 282 F.3d 147 (2d Cir. 2002) (unverified): 12(b)(6) review is limited to the complaint, attached exhibits, and documents incorporated by reference or integral to it

Suggested fix: PASS if the brief cites either the notification emails or the complaint's allegations of the client notifications (¶¶122-124). Make the sender names consistent across the complaint and the emails.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| F1 | confirmed | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L70) | not_a_defect | The PASS and FAIL wording do differ, but the gap is theoretical. PASS accepts 'both ... Twombly and ... Iqbal (or their plausibility standard)', so a brief that cites one case and states the plausibility test passes. Memo item 6 prescribes 'Legal Standard (1 page) --- Rule 12(b)(6), Twombly/Iqbal'. The only brief caught in the gap has no standard section at all, and under the partner's outline that is not competent work. |
| F2 | arguable | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L86) (arguable), [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L102) (problematic) | mixed | C-011 names Deming and Weiss as reformation authority. I re-read both this session. Weiss has no hits for 'modif' or 'divisib'; it holds only that the covenant was reasonable. Deming fn.21 declines to reach the blue-pencil question and quotes Beit's narrow rule on severing distinct covenants. So the criterion states wrong law and rewards the memo's miscitation. C-009's 'routinely' overstates the law, but its lenient FAIL condition limits misgrading, so it is arguable. |
| F3 | arguable | [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L246) (arguable), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L262) (not_a_defect) | mixed | C-029 requires a constructive-knowledge theory. In Weiss, a 'knew or ... should have known' interference count was reversed, although on improper means rather than knowledge. A careful brief would argue that actual knowledge can be inferred. C-031 fails a brief only if it does not use the 24-day timing as circumstantial evidence. Memo point 'Third' supplies that argument, and it is reasonable advocacy. |
| F4 | arguable | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L318), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L326) | not_a_defect | Memo §C is headed 'Press Release as Quasi-Admission'. It tells the associate to use the 'proprietary insights' language 'in the trade secrets argument, and in the tortious interference argument.' Defendants attached the release as Ex. C, so it is properly before the court. Calling a party-opponent's statement an admission is ordinary advocacy. Each criterion's FAIL condition is triggered only if the brief does not use the release at all. |
| F5 | arguable | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L342), [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L350), [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L358), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L366), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L374), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L382) | not_a_defect | None of these is hidden. Memo item 7 prescribes Argument sections A through E, one per count plus standing, and the MTD's Argument is itself structured A through E. The memo's closing paragraph says to 'cite specific complaint paragraph numbers throughout the brief.' Separate headings that mirror the motion are also a standard component of an opposition. |

## Blind pass and what changed

I kept O1 (C-011) as problematic and strengthened it. This session I re-read Weiss, which has no hits for 'modif' or 'divisib', and the full Deming fn.21, whose Beit quote is restrictive: severance only of distinct covenants. I also noted that the memo appears to plant the miscitation deliberately. I kept C-009 (now O2) as arguable and added the Beit rule. I kept C-029 (now O3) as arguable, replaced the unverified Restatement cite with a verified one, and added Weiss Part II, where a 'knew or should have known' interference count was reversed; I framed that holding as turning on improper means. I kept C-040 (now O4) as arguable, but noted that the memo directs pulling the emails, so the requirement is not hidden; the pleading problem and the sender conflict remain. I dropped blind O3 (C-032): memo item 7.D expressly directs the CRO-level fiduciary theory, and the criterion's proposition is reasonable, so it is incomplete rather than wrong. I dropped blind O6 (C-017/C-021): complaint ¶54 itself links the hotel-ownership clients to the Platinum Client List and lists exactly the data elements C-017 names, so a brief quoting ¶¶52-54 is fully supported. After reading Sol, I rejected F1 (C-007), F4 (C-038/C-039) and F5 (C-041 to C-046) because the partner memo prescribes each of those requirements, and C-031 (in F3) because its FAIL condition is lenient and the memo supplies the timing argument. I adopted no new criteria from Sol; Sol's F2 and F3 overlap findings I already had.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-011): C-011 offers Deming and Weiss as Connecticut reformation authority, but neither case supports reformation
- **O2** (arguable; C-009): C-009's PASS condition requires the brief to say Connecticut courts 'routinely' reform overbroad covenants, which overstates the law
- **O3** (arguable; C-032): C-032 accepts the MTD's framing that ordinary employees owe no fiduciary duty and ignores that every employee owes a duty of loyalty (Wall Systems)
- **O4** (arguable; C-029): C-029 requires a 'constructive knowledge' theory, even though interference torts generally require actual knowledge
- **O5** (arguable; C-040): C-040 requires citing emails outside the pleadings, and the emails name different senders than the complaint
- **O6** (arguable; C-017, C-021): The complaint defines the Platinum Client List as corporate travel contacts but relies on it as the source of the hotel owners' renewal data

## Coverage and limits

Blind pass: I read all 63 criteria and the instructions. I read these documents in full: the defendants' MTD memorandum, the litigation strategy memo, the restrictive covenant agreement, the client notification emails, and the press release. For the verified complaint, I read ¶¶1-40 by grep and ¶¶34-134 and 143-187 in full. I searched the Meridian forensics report (Exhibit B) for the facts the criteria rely on. On CourtListener I read the primary text of Weiss v. Wiederlight, 208 Conn. 525 (1988); Deming v. Nationwide, 279 Conn. 745 (2006) (including fn. 21); and Wall Systems v. Pompa, 324 Conn. 718 (2017). I did not re-read the text of 18 U.S.C. §§ 1836, 1838 or 1839, or Restatement (Second) of Torts § 766 cmt. i. I checked the statutory criteria (C-024, C-025, C-035) from my own knowledge and found nothing wrong with them. Some record problems do not change how any criterion grades, so I left them out of the findings. (1) The complaint and Exhibit B give different download windows (7:14-11:47 pm vs 7:42-11:18 pm) and different baseline access figures. (2) The MTD and the strategy memo cite complaint paragraphs that do not match the complaint's actual numbering, for example MTD ¶8, ¶58 and ¶79 and memo ¶38. C-041 cannot catch this: it passes a brief that copies those wrong cites. (3) The complaint, the RCA and the MTD each quote § 8.5 differently. None of this changes the result of any criterion.

Reconciliation: I read all 63 criteria, the instructions, and Sol's index entry and report. In this session I re-checked the strategy memo's outline (items 1-8), its knowledge, press-release and reformation sections, and the email housekeeping note. I also checked the MTD's Argument headings and its Ex. C, the full press release, the complaint's paragraphs on the Platinum Client List (¶¶2, 32, 51-55, 87, 119) and on the notifications (¶¶8, 122-124, 181), and the Northridge email. On CourtListener I read the primary text of: Deming fn.21, including the Beit quote at 769-70; Weiss, by keyword searches plus Part II at 534-36; and Wall Systems v. Pompa on the duty of loyalty. Chambers remains unverified. Several record discrepancies do not change how any criterion grades, so I did not make them findings. (1) MTD Ex. C attributes the release quote to 'David Aronov' and puts 'proprietary insights' in the narrative text, while the release attributes it to James Harrington inside his quote. (2) The complaint calls the Platinum Client List 'corporate travel contacts' but ties it to the hotel-owner data (¶54, ¶119). (3) As found in the blind pass, the download windows, the complaint paragraph cites in the MTD and memo, and the wording of § 8.5 differ across documents.
