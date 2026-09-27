# Claude Opus 5.5 audit: Draft First Set of Interrogatories to Defendant Veridian Health Systems in Trade Secret Misappropriation Case

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 50. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric's factual criteria are well grounded. The caption, parties, counsel, trade-secret names, SynapticEdge, Trent's outreach, the resignation and last-day dates, the non-solicit, and the USB serial CX-8827491 are all supported by the record. The one confident defect is C-032. It treats a proper contention interrogatory as defective unless it recites Rule 33(a)(2) deferral, which misreads a rule that expressly permits such interrogatories. It also conflicts with C-031, which requires a contention-style interrogatory on independent development. Secondary risks: C-019's subpart test is looser than the scheduling order's relatedness standard while other criteria require multi-element questions; C-015 requires an optional 'Describe' definition in a specific section; and C-046's 'specifically targets' wording could fail a broad date-range interrogatory. Sol's other concerns (C-007 to C-010 boilerplate, C-026/C-048, C-016) do not survive review.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L267), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L259) | C-032 penalizes proper contention interrogatories and conflicts with C-031, which requires one | blind |
| [O2](#o2) | arguable | ambiguous_or_unjudgeable | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L163), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L171), [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L203), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L227), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L235), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L371) | Subpart-count criterion uses a looser test than the scheduling order while other criteria require multi-element questions | blind |
| [O3](#o3) | arguable | unrequested_requirement | [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L131) | Requires a standalone 'Describe' definition in the Definitions section, which is optional boilerplate | blind |
| [O4](#o4) | arguable | ambiguous_or_unjudgeable | [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L379) | 'Specifically targets pre-resignation communications' may fail a broad date-range interrogatory that covers them | blind |

<a id="o1"></a>
### O1. C-032 penalizes proper contention interrogatories and conflicts with C-031, which requires one

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L267), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L259)

Rule 33(a)(2) says a contention interrogatory 'is not objectionable'. Deferral is something the court may order on objection; the serving party does not plead it. The scheduling order adds no disclaimer requirement. C-032 fails any 'state all facts supporting [defense/contention]' interrogatory unless the drafter cites 33(a)(2), mentions deferral, or satisfies an undefined 'factual framing' exception. Practitioners do not put that text in their own requests. C-031 requires an interrogatory asking Veridian to 'describe or identify all facts, evidence, or bases supporting any claim that SynapticEdge was independently developed'. That is the contention form C-032 targets, and Veridian raised independent development at the TRO hearing. A solver who writes 'State all facts supporting your contention that SynapticEdge was independently developed' clearly passes C-031 and may fail C-032, depending on how each judge reads 'factual framing'. Under all-pass scoring, that split zeroes out a correct answer.

Evidence:
- `C-032`: “FAIL if the document includes one or more interrogatories in the form 'State all facts supporting [affirmative defense/legal contention]' with no reference to FRCP 33(a)(2) deferral and no factual framing.”
- `C-031`: “PASS if at least one interrogatory asks Veridian to describe or identify all facts, evidence, or bases supporting any claim that SynapticEdge was independently developed without use of CMT's trade secrets.”
- `tro-order.docx.txt`: “Veridian's counsel represented at the hearing that SynapticEdge was "in development prior to Mr. Oshiro's hiring,"”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Civ. P. 33(a)(2) (✓): An interrogatory is not objectionable merely because it asks for an opinion or contention relating to fact or application of law to fact; the court may order that it need not be answered until later.

Suggested fix: Delete C-032. Or narrow it to penalize only an omnibus interrogatory demanding all facts for every affirmative defense, and state expressly that a targeted contention interrogatory like the one C-031 requires passes.

Related GPT-6 Sol findings: Definite defect: item 1.

<a id="o2"></a>
### O2. Subpart-count criterion uses a looser test than the scheduling order while other criteria require multi-element questions

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L163), [C-020](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L171), [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L203), [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L227), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L235), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L371)

C-019 asks the judge to count 'discrete subparts' using a 'different categories of information' test. The scheduling order counts a subpart separately only if it is not logically or factually related to the primary question, and the judges never see the order. The rubric also requires about 18 topical interrogatories, several with multi-element 'including' lists: timeline, circumstances and first contact (C-020); start date, milestones, and before or after Oshiro (C-024); hold issuance, scope, and ESI steps (C-027); three named hires (C-028); salary, bonus, equity and benefits (C-045). A compact 18–20 interrogatory set built to satisfy these could be counted above 25 by one judge and at or below 25 by the other. The criteria push toward the very drafting C-019 may penalize, and there is no reference count to anchor the judgment.

Evidence:
- `C-019`: “counting discrete subparts as separate interrogatories where they ask for different categories of information (consistent with FRCP 33(a)(1)), does not exceed 25”
- `scheduling-order.docx.txt`: “A subpart is logically or factually related to the primary interrogatory only if it seeks information on the same subject matter and could reasonably be considered a natural component of a single, unified inquiry.”
- `C-024`: “including when development began, key milestones, and whether development commenced before or after Oshiro joined Veridian”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Civ. P. 33(a)(1) (✓): A party may serve no more than 25 written interrogatories, including all discrete subparts, unless stipulated or ordered otherwise.

Suggested fix: Give the judge the scheduling order's related-subpart test and state that subparts elaborating a single subject count as one interrogatory. Or replace C-019 with 'no more than 25 numbered interrogatories and no obviously unrelated compound questions.'

Related GPT-6 Sol findings: Arguable/format concerns: item 2.

<a id="o3"></a>
### O3. Requires a standalone 'Describe' definition in the Definitions section, which is optional boilerplate

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L131)

The instructions ask only for a first set of interrogatories. Definitions of Identify, Document, Communication, and You (C-007 to C-010) are near-universal and implicit in the document type, so they are not defects. A separate 'Describe' definition is common but optional. Many competent sets instead spell out the required detail inside each interrogatory or in the Instructions. C-015 fails such a set, even when every interrogatory demands a detailed narrative, solely because the word is not defined in a particular section.

Evidence:
- `C-015`: “FAIL if 'Describe' is not defined in the Definitions section.”
- `task.json instructions`: “Draft first set of interrogatories from plaintiff to defendant based on the attached case files.”

Suggested fix: PASS if 'Describe' is defined anywhere, or if the interrogatories or instructions otherwise require a detailed factual narrative.

Related GPT-6 Sol findings: Arguable/format concerns: item 1.

<a id="o4"></a>
### O4. 'Specifically targets pre-resignation communications' may fail a broad date-range interrogatory that covers them

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L379)

A standard, competent interrogatory asks for all Veridian–Oshiro communications from November 1, 2023 (the litigation hold letter's start date) to the present. That fully covers the pre-resignation period. A literal judge could still find it does not 'specifically target' communications before Feb. 14 or Mar. 1, 2024, and fail it, while the other judge passes it. The misgrading risk is moderate.

Evidence:
- `C-046`: “FAIL if no interrogatory specifically targets pre-resignation communications between Veridian and Oshiro.”
- `litigation-hold-letter.docx.txt`: “between any Veridian officer, director, employee, or agent and Ryan Oshiro, from November 1, 2023 to the present.”

Suggested fix: PASS if any interrogatory seeks Veridian–Oshiro communications for a period that includes the time before Feb. 14, 2024 or Mar. 1, 2024.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Definite defect: item 1 | confirmed | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L267) | problematic | Rule 33(a)(2) says contention interrogatories are 'not objectionable'. Deferral is a remedy the court may grant; the serving party does not recite it. The scheduling order (B.1–B.3) imposes no disclaimer. C-032 fails a targeted 'state all facts supporting your contention' interrogatory unless it cites 33(a)(2) or uses undefined 'factual framing'. C-031 requires exactly that form for independent development, so the two conflict and a correct answer can fail. |
| Arguable/format concerns: item 1 | arguable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L67) (not_a_defect), [C-008](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L75) (not_a_defect), [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L83) (not_a_defect), [C-010](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L91) (not_a_defect), [C-015](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L131) (arguable) | mixed | Definitions of Identify (name, position, employer, contact), Document (including ESI), Communication, and You/Your are standard components of a federal interrogatory set. They are implicit in the requested work product, not hidden requirements. A standalone 'Describe' definition is common but optional, and C-015 fails a set that puts narrative requirements elsewhere. So only C-015 is arguable. |
| Arguable/format concerns: item 2 | arguable | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L163) | arguable | The scheduling order counts a subpart separately only if it is not 'logically or factually related'. C-019's 'different categories of information' gloss is looser, and the judges do not see the order. Other criteria (C-020, C-024, C-027, C-045) require multi-element 'including' questions, so the same compact 20-question set could be counted above 25 by one judge and at or below 25 by the other. |
| Arguable/format concerns: item 3 | arguable | [C-026](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L219), [C-048](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L395) | not_a_defect | The two criteria do not conflict. C-026 tests topic coverage; C-048 tests precision, and one interrogatory can meet both. Serial CX-8827491 appears consistently in the complaint, TRO, hold letter, Ashcroft report and Yilmaz report. Using the record identifier to prevent evasive answers is ordinary good drafting. The criterion is demanding but reasonable. |
| Arguable/format concerns: item 4 | arguable | [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-interrogatories/task.json#L139) | not_a_defect | C-016 passes any instruction that 'references or describes the... continuing duty to supplement responses under FRCP 26(e)'. An accurate, qualified Rule 26(e) instruction therefore passes. The broader 'if additional information becomes available' wording is an extra way to pass, not a requirement, so the criterion cannot fail a correct answer. A supplementation instruction is standard in the document type. |

## Blind pass and what changed

I dropped blind O5 (C-037, conflicting counsel for Oshiro). The August 30 scheduling order postdates the August 1 TRO and says Stephen Osei of Drummond & Wakefield represents both defendants. C-037 passes any certificate that names Osei or Drummond & Wakefield, whether or not Dominguez is added, so the conflict cannot misgrade an answer. After reading Sol, I kept C-015 as arguable. I rejected Sol's extension of that concern to C-007 through C-010, because those definitions are standard, implicit parts of an interrogatory set. I rejected Sol's C-026/C-048 tension: coverage and precision are compatible, and the serial number is consistent across five record documents. I rejected Sol's C-016 concern because an accurate Rule 26(e) instruction satisfies the criterion's first pass condition. Sol's C-032 and C-019 findings match my blind O1 and O2, which are unchanged.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-032, C-031): C-032 penalizes proper contention interrogatories and conflicts with C-031, which requires one
- **O2** (arguable; C-019, C-020, C-024, C-027, C-028, C-045): Subpart-count criterion has no counting method and conflicts with many multi-element topic mandates
- **O3** (arguable; C-015): Requires a standalone 'Describe' definition, which is optional boilerplate
- **O4** (arguable; C-046): 'Specifically targets pre-resignation communications' may fail a broad date-range interrogatory that covers them
- **O5** (arguable; C-037): Record conflicts on who represents Oshiro, which affects the correct certificate of service

## Coverage and limits

Blind pass: Read in full: task.json (instructions and all 50 criteria), first-amended-complaint, scheduling-order, tro-order, litigation-hold-letter, cmt-internal-emails, veridian-press-release, and the judge prompt. Searched with grep only (not read in full): oshiro-nda-agreement (non-solicitation §3.1 is 18 months post-employment; non-disclosure §2.3 is 24 months; governed by Texas law), ashcroft-forensics-report (serial CX-8827491 is consistent), yilmaz-preliminary-report. Checked the record facts every criterion relies on: court and division, case number, party names, NeuralPath/PrecisionDrive/PathPlanner, SynapticEdge, Trent's LinkedIn message of Dec. 3, 2023, the Feb. 14 and Mar. 1, 2024 dates, the 18-month non-solicit, the USB serial, and counsel names. All are supported. Verified from primary text: FRCP 33(a)(1) and 33(a)(2) (Cornell LII). No case law was verified. Record noise that no criterion depends on, so not flagged: the TRO gives Furukawa, Briggs and Moreno different job titles than the complaint and emails; the TRO puts Oshiro's residence in Alexandria while the complaint says Reston; the litigation hold letter says Moreno was 'expected to join'; and the emails show approaches to the three engineers while Oshiro was still employed, before the post-employment non-solicit window.

Reconciliation: Reviewed all 50 criteria and the instructions. Read the Sol index entry and Sol's full audit report. In the blind pass, read the complaint, scheduling order, TRO, hold letter, emails and press release in full. In this pass, re-checked by grep: the scheduling order's subpart-counting, deadline and proportionality provisions (no contention-interrogatory disclaimer); counsel of record across the scheduling order, TRO and complaint; and the USB device identification across the complaint, TRO, hold letter, Ashcroft report and Yilmaz report (one device, consistent serial). Rule 33(a)(1) and (a)(2) were verified from primary text in the blind pass. Rule 26(e) was not re-read this session; C-016 is judged on its own pass conditions. No case law was relied on.
