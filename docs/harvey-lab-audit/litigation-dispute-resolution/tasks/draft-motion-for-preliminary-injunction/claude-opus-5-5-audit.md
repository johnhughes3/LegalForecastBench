# Claude Opus 5.5 audit: Draft Memorandum of Law in Support of Motion for Preliminary Injunction — Trade Secret Misappropriation and Non-Compete Enforcement

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 53. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

Most of this rubric is sound: the hard-coded facts match the record, and the MNAA and DTSA propositions it tests are correct. Two criteria are clearly defective. C-051 expressly accepts 'plausibly cited' (fabricated) cases, and the judge never checks citations. C-012 names only the fiduciary-duty route to a 24-month restricted period, leaving out § 24L(b)(iv)'s unlawful-taking prong, which is the prong this record fits best. Four criteria are arguable. C-037 requires a jurisdiction section that a PI memo does not normally include. C-038 requires one timeline inference when stronger evidence of pre-resignation dealings exists. C-045 mislabels § 8.1 as the covenant, following the pleadings. Two client-side record contradictions (Decl. ¶9 on USB authorization and ¶12 on when garden leave was added) muddy the correct answer, but the rubric does not grade them. Sol's C-039 and C-043 concerns do not hold up.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-051](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L421) | C-051 counts 'real or plausibly cited' cases, so invented case law passes | blind |
| [O2](#o2) | problematic | legal_error | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L109) | C-012 names only the fiduciary-duty route to 24 months and leaves out the 'unlawfully taken property' route | revised |
| [O3](#o3) | arguable | unrequested_requirement | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L309) | C-037 requires a subject-matter jurisdiction section, which a PI memo does not normally include, and accepts diversity alone | blind |
| [O4](#o4) | arguable | ambiguous_or_unjudgeable | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L317) | C-038 requires one specific inference from the 38-day gap when the record has stronger evidence of pre-resignation dealings | blind |
| [O5](#o5) | arguable | source_conflict | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L373) | C-045 labels § 8.1 (definitions) as the confidentiality covenant; the operative covenant is § 8.2 | revised |
| [O6](#o6) | arguable | document_defect | [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L125), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L149) | Greenfield Decl. ¶9 says she used an 'authorized research-device exception'; the forensic report says the device was never authorized | blind |
| [O7](#o7) | arguable | document_defect | [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L117), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L213) | Greenfield Decl. ¶12 says garden leave was 'added' in 2022, but the 2019 agreement already contains Section 7.3 | blind |

<a id="o1"></a>
### O1. C-051 counts 'real or plausibly cited' cases, so invented case law passes

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-051](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L421)

C-051 passes a memo that cites at least three cases 'whether real or plausibly cited'. That openly accepts fabricated authority. The judge sees no sources, and no other criterion checks whether citations are accurate. So a memo resting on invented cases can pass C-051 and still achieve all-pass, even though fabricated authority in a filed brief can draw sanctions. The criterion therefore rewards wrong work, and as a bare count it does little to separate competent memos.

Evidence:
- `C-051`: “PASS if the memorandum cites at least three case law authorities (whether real or plausibly cited)”

Suggested fix: Remove 'whether real or plausibly cited'. Require that the cited authorities exist and support the propositions, or drop the criterion if the judge cannot verify citations.

Related GPT-6 Sol findings: F1.

<a id="o2"></a>
### O2. C-012 names only the fiduciary-duty route to 24 months and leaves out the 'unlawfully taken property' route

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L109)

MNAA § 24L(b)(iv) allows up to 2 years if the employee breached a fiduciary duty OR 'unlawfully taken, physically or electronically, property belonging to the employer.' On this record the electronic-taking prong is the most direct fit: 14,200 files copied to an unregistered personal USB drive. C-012 presents the fiduciary-duty exception as the only route. Its FAIL condition catches a memo that 'asserts the 24-month period is enforceable without addressing the fiduciary duty exception or the 12-month alternative.' A memo that correctly relies on the property-taking prong without a 12-month fallback would therefore fail. The 'e.g.' parenthetical may let a lenient judge accept it, but the criterion states the statute in a materially incomplete way.

Evidence:
- `C-012`: “asserts the 24-month period is enforceable without addressing the fiduciary duty exception or the 12-month alternative”
- `forensic-it-report.docx.txt`: “This USB device was **not** registered in Greenfield\'s IT asset management system and was **not** a company-issued device.”

Authorities (✓ = primary text checked in the auditing session):
- Mass. Gen. Laws ch. 149, § 24L(b)(iv) (✓): Restricted period may not exceed 12 months unless the employee breached a fiduciary duty or unlawfully took employer property, physically or electronically, in which case up to 2 years.

Suggested fix: Accept either § 24L(b)(iv) prong: breach of fiduciary duty or unlawful physical or electronic taking of employer property.

Related GPT-6 Sol findings: F2.

<a id="o3"></a>
### O3. C-037 requires a subject-matter jurisdiction section, which a PI memo does not normally include, and accepts diversity alone

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L309)

The verified complaint already pleads jurisdiction at ¶¶10-14, and nothing in the record contests it. A memorandum supporting a PI motion normally argues the four-factor standard. It does not re-establish jurisdiction, so a competent memo that leaves it out would fail. The criterion also passes a memo that relies 'and/or' on diversity alone, which the complaint itself concedes is unavailable.

Evidence:
- `C-037`: “and/or diversity jurisdiction. FAIL if the memorandum does not address subject matter jurisdiction at all.”
- `verified-complaint.docx.txt`: “complete diversity of citizenship does not exist between Plaintiff and all Defendants”

Suggested fix: Delete C-037, or make it conditional: if the memo discusses jurisdiction, it must rest on DTSA federal-question jurisdiction plus § 1367, not diversity.

<a id="o4"></a>
### O4. C-038 requires one specific inference from the 38-day gap when the record has stronger evidence of pre-resignation dealings

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L317)

C-038 passes only if the memo argues that the 38-day gap (Jan 17 to Feb 24) is circumstantial evidence of negotiations while she was still employed. The forensic report gives more direct evidence: 23 visits to Canopy Ridge's site starting Nov 15, and emails forwarded to a personal account on Nov 28. The defense letter also offers a 2021 development chronology. A competent memo could rest the negotiation inference on the forensic evidence and use the timeline only for pipeline acceleration, which C-039 covers. That memo would fail C-038. C-039 itself is sound advocacy.

Evidence:
- `C-038`: “FAIL if this timeline argument is not made.”
- `forensic-it-report.docx.txt`: “Dr. Vasquez visited the Canopy Ridge Therapeutics, LLC website ... on twenty-three separate occasions”

Suggested fix: PASS if the memo argues, from any record evidence (browser history, email forwards, download timing or the 38-day gap), that Vasquez was dealing with Canopy Ridge while still employed.

Related GPT-6 Sol findings: F4.

<a id="o5"></a>
### O5. C-045 labels § 8.1 (definitions) as the confidentiality covenant; the operative covenant is § 8.2

**Status:** arguable · **Category:** source_conflict · **Criteria:** [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L373)

The agreement's § 8.1 is headed 'Confidential Information and Trade Secrets Defined'. The operative non-disclosure obligation is § 8.2, and the First Amendment confirms this ('obligations of non-disclosure as set forth in Section 8.2'). The complaint and the cease-and-desist letter repeat the § 8.1 label, and C-045 follows them. A memo that correctly cites § 8.2 could draw a FAIL from a strict judge, though most judges will read the parenthetical as an identifier. The complaint has other minor errors that the criteria do not rely on: '48 days' for an 85-day span, forum clause cited as '12.3' instead of 10.2, and 'Andean plant source' quoted even though that phrase is not in the press release.

Evidence:
- `C-045`: “breach of confidentiality/trade secret covenant (Section 8.1 of the Employment Agreement)”
- `employment-agreement.docx.txt`: “her obligations of non-disclosure as set forth in Section 8.2 of the Original Agreement extend to all such information indefinitely”

Suggested fix: Refer to 'Section 8 (§§ 8.1-8.2)' or to § 8.2.

Related GPT-6 Sol findings: F3.

<a id="o6"></a>
### O6. Greenfield Decl. ¶9 says she used an 'authorized research-device exception'; the forensic report says the device was never authorized

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-014](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L125), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L149)

The client's CEO declaration contradicts the client's forensic report and complaint on a point that goes to improper means (C-014) and reasonable secrecy measures (C-017). A competent drafter would avoid ¶9 or reconcile it. The judge never sees the record, so the rubric neither rewards noticing the conflict nor penalizes relying on it. The criteria themselves are not wrong, but the correct answer is muddied.

Evidence:
- `greenfield-declaration.docx.txt`: “by exploiting an authorized research-device exception that permits the transfer of data to approved laboratory instruments via USB connection”
- `forensic-it-report.docx.txt`: “This USB device was **not** registered in Greenfield\'s IT asset management system and was **not** a company-issued device.”

Suggested fix: Conform ¶9 to the forensic report.

<a id="o7"></a>
### O7. Greenfield Decl. ¶12 says garden leave was 'added' in 2022, but the 2019 agreement already contains Section 7.3

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L117), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L213)

The March 2019 agreement already contains § 7.3 (Garden Leave), and the 2022 First Amendment only reaffirms it. Decl. ¶12 says the amendment 'added' garden leave. Under the MNAA the difference matters. If garden leave arrived only in 2022, the 2019 noncompete lacked (b)(vii) consideration, and the amendment would be governed by the mid-employment rules in (b)(ii). C-013 and C-025 take the controlling agreement's version, which is correct, so the risk of misgrading is low. Still, the record gives a drafter conflicting inputs.

Evidence:
- `greenfield-declaration.docx.txt`: “a garden leave provision was added as new Section 7.3.”
- `employment-agreement.docx.txt`: “**7.3 Garden Leave Provision.** In consideration for the Employee\'s compliance with the non-competition obligations set forth in Section 7.1 above”

Authorities (✓ = primary text checked in the auditing session):
- Mass. Gen. Laws ch. 149, § 24L(b)(vii) (✓): Noncompete must be supported by garden leave (at least 50% of highest base salary in the prior 2 years) or other mutually agreed consideration specified in the agreement.

Suggested fix: Correct Decl. ¶12 to match the agreement.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| F1 | confirmed | [C-051](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L421) | problematic | The text says 'at least three case law authorities (whether real or plausibly cited)'. The judge never sees any sources, and no other criterion checks whether citations are real. So a memo built on fabricated cases passes this criterion and can still reach all-pass. Fabricated authority in a filed brief is a sanctionable defect, so the criterion rewards wrong work. |
| F2 | confirmed | [C-012](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L109) | problematic | § 24L(b)(iv) allows up to two years for breach of fiduciary duty OR where the employee 'has unlawfully taken, physically or electronically, property belonging to the employer'. The forensic report shows 14,200 files copied to an unregistered personal USB drive, which fits that second prong squarely. C-012 treats the fiduciary-duty route as the only one. Its FAIL text would literally fail a memo that relies on the unlawful-taking prong with no 12-month fallback. The 'e.g.' parenthetical softens this only partly. |
| F3 | confirmed | [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L373) | arguable | In the agreement, § 8.1 only defines 'Confidential Information and Trade Secrets'. The operative non-disclosure covenant is § 8.2, and the First Amendment confirms this. However, the complaint (¶¶90-94) and the cease-and-desist letter both call § 8.1 the confidentiality covenant, so the criterion simply follows the client's pleadings. A judge will probably pass a memo that argues the covenant breach and cites § 8.2, because the parenthetical works as an identifier. The criterion is factually off, but the risk of misgrading is modest. |
| F4 | arguable | [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L317) (arguable), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L325) (not_a_defect) | mixed | C-038 requires one specific inference: that the 38-day gap shows negotiations while she was still employed. The forensic report has stronger direct evidence (23 visits to Canopy Ridge's site from Nov 15 and emails forwarded Nov 28), and a competent memo relying on that would fail. C-039 is different. The press release 'simultaneously' announces the hire and an 'accelerated' pipeline, and ¶¶22-25 of the declaration support tying the acceleration to misappropriation. That is ordinary plaintiff advocacy, and the defense's 2021 chronology does not make it unreasonable. |
| F5 | arguable | [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-motion-for-preliminary-injunction/task.json#L357) | not_a_defect | C-043 offers inevitable disclosure as only one of several acceptable rebuttals, alongside downloads, similarity and timeline. It never requires it. Here the evidence of actual acquisition means competent memos will lead with that evidence. Invoking inevitable disclosure as a supporting point is not wrong law in D. Mass. The § 1836(b)(3)(A)(i)(I) limits on DTSA employment restraints would not cause competent work to fail. At most they let a thin rebuttal pass, and that is not a material misgrade. |

## Blind pass and what changed

I raised C-012 (O2) from arguable to problematic. The criterion's FAIL text treats the fiduciary-duty route as the only way to 24 months, which is a materially incomplete statement of § 24L(b)(iv), and the unlawful-electronic-taking prong is the stronger fit on this record. Sol's F2 reached the same result independently. I made C-045 (the § 8.1 vs § 8.2 point) its own finding, O5, kept it arguable, and folded the minor complaint errors into it; I rejected Sol's 'confirmed' because the pleadings use the same label and the judge will probably read it as an identifier. I considered Sol's F4 on C-039 and rejected it: tying the 'accelerated' pipeline to misappropriation is supported plaintiff advocacy. I rejected Sol's F5 on C-043 because inevitable disclosure is only one of several acceptable options there. I removed C-010 from the garden-leave document defect because that criterion concerns only the agreement date. I dropped no blind findings.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-051): C-051 counts 'real or plausibly cited' cases, so invented case law passes
- **O2** (arguable; C-012): C-012 recognizes only the fiduciary-duty route to 24 months and omits the 'unlawfully taken property' route
- **O3** (arguable; C-037): C-037 requires a subject-matter jurisdiction section, which a PI memo does not normally include, and rewards a failed diversity theory
- **O4** (arguable; C-038): C-038 requires one specific inference from the 38-day post-departure gap when the record has stronger evidence of pre-resignation dealings
- **O5** (arguable; C-014, C-017): Greenfield Declaration ¶9 says she used an 'authorized research-device exception'; the forensic report says no authorization existed
- **O6** (arguable; C-010, C-013, C-025): Greenfield Decl. ¶12 says garden leave was added in 2022, but the 2019 agreement already contains Section 7.3
- **O7** (arguable; C-045): Minor record errors, including C-045 calling Section 8.1 the confidentiality covenant

## Coverage and limits

Blind pass: I read all 9 supplied documents in full: the employment agreement with its First Amendment, the verified complaint, the Greenfield and Chow declarations, the forensic IT report, the Linden valuation report, the press release, the cease-and-desist letter, and the defense counsel letter. I also read the task instructions, all 53 criteria, the solver system prompt and the judge prompt. I checked every fact hard-coded in the criteria against the record: case number, dates, $47.3M, $85M/$52M, $95M, $220M, $13,541.67, the 38-day gap, Feb 1 and Feb 5, Feb 20, the 40% premium, Dec 1-12, 14,200 files and 3.8 GB. Primary statutory text was fetched verbatim for Mass. Gen. Laws ch. 149, § 24L(b)(iv) and (b)(vii), 18 U.S.C. § 1833(b)(3) and 18 U.S.C. § 1836(b)(3)(A). § 24L(b)(i)-(viii), (c) and (d) came back only as a paraphrase, so the reformation power in (d) is paraphrase-only. I did not research case law and did not use CourtListener, so I did not independently verify the First Circuit/D. Mass. positions on presumed irreparable harm or inevitable disclosure. Important structural point: the judge sees only the one-sentence instructions, the deliverable and one criterion. It never sees the documents, so it cannot check citation accuracy or record fidelity.

Reconciliation: In the blind pass I reviewed all 53 criteria and all 9 documents in full, and fetched the text of § 24L(b)(iv) and (b)(vii) and 18 U.S.C. §§ 1833(b)(3) and 1836(b)(3)(A). In this pass I read Sol's index and audit.md, then re-checked the record for each Sol finding: § 8.1 vs § 8.2 across the agreement, complaint and cease-and-desist letter; the acceleration chronology in the press release, declaration and defense letter; and where the garden-leave provision first appears. I did no case-law research. My view that inevitable disclosure is acceptable in D. Mass. comes from general knowledge, not a primary source I read in this session.
