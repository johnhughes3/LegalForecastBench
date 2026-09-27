# Claude Opus 5.5 audit: Government Subpoena Issue Identification — Memorandum to Partner on Grand Jury Subpoena for Insider Trading Investigation

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 52. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric tracks the record well, and most of its legal points are sound. The one clear legal error is C-025. It credits the Nixon trial-subpoena test for a grand jury subpoena, which R. Enterprises expressly rejects. Because C-025 is disjunctive, it rewards wrong law rather than failing correct memos. The main all-pass risk is structural. C-044 to C-046 depend on severity tiers the instructions never request, C-043 requires every issue section to carry all three elements, and C-041, C-049 and C-019 are narrower than the legal substance they target. I reject Sol's overbreadth, investor (F2) and Salman (F4) concerns: those criteria take reasonable defense-counsel positions and would not fail competent work.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L209) | C-025 credits Nixon's trial-subpoena test (relevance, admissibility, specificity) as a standard for challenging a grand jury subpoena | revised |
| [O2](#o2) | arguable | legal_error | [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L49) | C-005 lists civil 'proportionality' as a legal basis for narrowing a grand jury subpoena | revised |
| [O3](#o3) | arguable | unrequested_requirement | [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L361), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L369), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L377) | Three criteria depend on explicit risk-severity ratings that the instructions never request | blind |
| [O4](#o4) | arguable | unrequested_requirement | [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L353) | C-043 fails the whole memo if any single issue section lacks a recommendation | blind |
| [O5](#o5) | arguable | legal_error | [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L161) | C-019 requires Braswell or the 'collective entity' label for oral designee testimony, where Curcio and Kordel are the closer authorities | blind |
| [O6](#o6) | arguable | unrequested_requirement | [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L337) | C-041 requires a 'proposed timeline' for USAO negotiations, which the instructions never request | blind |
| [O7](#o7) | arguable | unrequested_requirement | [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L401) | C-049's FAIL trigger requires remarking on the missing privilege-log provision, not only recommending a privilege protocol | blind |
| [O8](#o8) | arguable | document_defect | [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L201), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L337) | AUSA name 'Jonathan Cromdale Consulting' with email jonathan.mercer@usdoj.gov looks like an anonymization artifact, repeated in criteria | blind |

<a id="o1"></a>
### O1. C-025 credits Nixon's trial-subpoena test (relevance, admissibility, specificity) as a standard for challenging a grand jury subpoena

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L209)

C-025 passes a memo that 'mentions United States v. Nixon standards (relevance, admissibility, specificity)' as the legal standard for challenging this grand jury subpoena. R. Enterprises holds that the Nixon standard does not apply to grand jury proceedings. A Rule 17(c) relevance challenge must be denied unless there is 'no reasonable possibility' the materials will produce relevant information, and the government bears no initial burden. The criterion is disjunctive, so a correct memo that cites Rule 17(c) or a motion to quash still passes. The defect is that it rewards a memo whose only stated standard is the wrong law, and such a memo would mislead the partner about how hard it is to quash.

Evidence:
- `C-025`: “or mentions United States v. Nixon standards (relevance, admissibility, specificity)”
- `grand-jury-subpoena.docx.txt`: “Issued Pursuant to Federal Rule of Criminal Procedure 17(c)”

Authorities (✓ = primary text checked in the auditing session):
- United States v. R. Enterprises, Inc., 498 U.S. 292, 299-301 (1991) (✓): 'The Nixon standard does not apply in the context of grand jury proceedings'; a relevance-based motion to quash must be denied unless there is no reasonable possibility the materials will produce information relevant to the general subject of the investigation; placing an initial burden on the Government is error.

Suggested fix: Delete the Nixon clause, or accept Nixon only where the memo distinguishes it. Require Rule 17(c)(2)'s unreasonable-or-oppressive standard as applied in R. Enterprises.

Related GPT-6 Sol findings: F1.

<a id="o2"></a>
### O2. C-005 lists civil 'proportionality' as a legal basis for narrowing a grand jury subpoena

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-005](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L49)

C-005 accepts 'relevance, proportionality, undue burden, or Fed. R. Crim. P. 17(c) standards' as the legal basis for narrowing requests. Proportionality is a civil Rule 26(b)(1) concept with no footing in Rule 17(c) grand jury practice. A memo that invokes only proportionality would pass on a wrong legal basis. The effect is minor because the list is illustrative and most memos will cite Rule 17(c) or burden.

Evidence:
- `C-005`: “referencing concepts such as relevance, proportionality, undue burden, or Fed. R. Crim. P. 17(c) standards”

Authorities (✓ = primary text checked in the auditing session):
- United States v. R. Enterprises, Inc., 498 U.S. 292, 301 (1991) (✓): Grand jury subpoena challenges proceed under Rule 17(c)'s reasonableness limits, not trial or civil discovery standards.

Suggested fix: Drop 'proportionality' or label it a negotiation argument by analogy, not a legal standard.

<a id="o3"></a>
### O3. Three criteria depend on explicit risk-severity ratings that the instructions never request

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L361), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L369), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L377)

The instructions ask only for 'a detailed issues memo to the lead partner.' C-044 requires severity ratings or equivalent prioritization. C-045 and C-046 then require the spoliation and conflict issues to be rated 'critical or high (or equivalent top-tier severity).' A competent memo can treat both issues as urgent in its prose without labeled tiers. That memo falls between the PASS condition (rated critical or high) and the FAIL condition (rated moderate or low). The judge prompt says to apply criteria 'as described' and gives no guidance on equivalents. Partner memos commonly prioritize issues, so this is arguable rather than problematic. Still, labeled tiers are a house format, and three all-pass criteria rest on them.

Evidence:
- `task.json instructions`: “Review the attached grand jury subpoena and related client documents and prepare a detailed issues memo to the lead partner.”
- `C-045`: “FAIL if spoliation is rated as moderate or low risk.”
- `rubric_criterion.txt`: “PASS: The agent's output satisfies the criterion as described”

Suggested fix: Either ask for ratings in the instructions, or pass C-045 and C-046 when the memo treats the issue as among the most urgent or requiring immediate action, labeled or not.

Related GPT-6 Sol findings: F5.

<a id="o4"></a>
### O4. C-043 fails the whole memo if any single issue section lacks a recommendation

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L353)

C-043 fails the memo 'if any issue section lacks' a description, a reference to the subpoena or the facts, and a recommended course of action. Several criteria require analytic sections that do not naturally end in an action item: exposure analysis (C-035 to C-038) and evidentiary assessment. A competent memo often gathers its recommendations in the concluding strategy section that C-040 itself requires. Under a literal judge, one exposure section without a recommendation zeroes the run. The instructions set no per-section template.

Evidence:
- `C-043`: “FAIL if any issue section lacks one or more of these three elements.”
- `C-040`: “PASS if the memorandum includes a concluding section that sets out a recommended overall response strategy”

Suggested fix: Apply the requirement to the principal subpoena-response issues, or accept recommendations placed in a consolidated strategy section.

Related GPT-6 Sol findings: F5.

<a id="o5"></a>
### O5. C-019 requires Braswell or the 'collective entity' label for oral designee testimony, where Curcio and Kordel are the closer authorities

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L161)

Attachment B demands oral grand jury testimony from a corporate designee. Braswell concerns a custodian's act of producing documents, and Braswell itself distinguishes Curcio: a custodian cannot be compelled to incriminate himself by oral testimony. For the designee problem, the closer authorities are Curcio and Kordel, under which the entity must designate someone who can testify without self-incrimination. C-019 may fail a memo that relies correctly on Curcio, Kordel or Hale v. Henkel. Its phrase 'custodian/designee acts in a representative capacity' also blurs the line between documents and testimony. C-018 already captures the tension correctly, so this is arguable rather than wrong law.

Evidence:
- `C-019`: “FAIL if neither Braswell nor the collective entity doctrine is mentioned in this context.”
- `grand-jury-subpoena.docx.txt`: “You are hereby commanded to designate and produce a corporate representative or representatives of Grayfield Capital Partners, LLC, designated and prepared to testify on behalf of the entity”

Authorities (✓ = primary text checked in the auditing session):
- Braswell v. United States, 487 U.S. 99, 113-114 (1988) (unverified): Custodian cannot resist production of corporate records on Fifth Amendment grounds; Court distinguishes Curcio, where a custodian could not be compelled to give incriminating oral testimony.
- Curcio v. United States, 354 U.S. 118, 123-125 (1957) (unverified): A custodian may not be compelled to give incriminating oral testimony about records.

Suggested fix: Accept Braswell, Curcio, Kordel, Hale or Bellis, or any accurate statement that the entity has no privilege while the designee keeps a personal privilege against oral testimony.

Related GPT-6 Sol findings: F3.

<a id="o6"></a>
### O6. C-041 requires a 'proposed timeline' for USAO negotiations, which the instructions never request

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L337)

C-041 fails a memo with no 'proposed timeline with concrete steps.' A memo that recommends calling the AUSA promptly, seeking an extension and proposing rolling production has given the substance, which C-024 already tests. A literal judge may still expect dated or sequenced milestones. The criterion duplicates C-024 and adds a format requirement. The intake memo does ask about the extension approach, so next steps are implicit. Whether they must take the form of a 'timeline' is the debatable part.

Evidence:
- `C-041`: “FAIL if no proposed timeline with concrete steps is included.”
- `intake-memo-tsao.docx.txt`: “What is the best approach for requesting an extension of the July 8 return date from AUSA Cromdale Consulting?”

Suggested fix: Pass when the memo sets out concrete, sequenced next steps with the USAO; dates not required.

<a id="o7"></a>
### O7. C-049's FAIL trigger requires remarking on the missing privilege-log provision, not only recommending a privilege protocol

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L401)

The observation is accurate: the subpoena has no privilege-log provision and mentions privilege only in 'non-privileged Documents' within the certification instruction. A competent memo can deal with privilege fully, covering Clearwater under Request 14, attorney-held documents swept in by the definition of 'You', and a clawback or non-waiver agreement, without framing any of it as the absence of a log provision. The FAIL condition is tied to that one framing.

Evidence:
- `C-049`: “FAIL if the absence of a privilege log provision is not mentioned.”
- `grand-jury-subpoena.docx.txt`: “all responsive, non-privileged Documents have bee”

Suggested fix: Pass if the memo recommends a privilege-handling protocol (log, clawback or non-waiver) with the USAO.

<a id="o8"></a>
### O8. AUSA name 'Jonathan Cromdale Consulting' with email jonathan.mercer@usdoj.gov looks like an anonymization artifact, repeated in criteria

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L201), [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L337)

The subpoena names the AUSA 'Jonathan Cromdale Consulting' but gives the email jonathan.mercer@usdoj.gov, which looks like a find-and-replace error. C-024 and C-041 repeat 'AUSA Cromdale Consulting.' A careful solver may use 'Mercer' or flag the inconsistency. The grading impact is minimal because C-024 accepts 'the USAO' and C-041 gives the name only as an example.

Evidence:
- `grand-jury-subpoena.docx.txt`: “Jonathan Cromdale Consulting Assistant United States Attorney”
- `grand-jury-subpoena.docx.txt`: “Email: jonathan.mercer@usdoj.gov”
- `C-024`: “negotiating a rolling production schedule with AUSA Cromdale Consulting/the USAO”

Suggested fix: Make the AUSA's name and email consistent across the subpoena, the intake memo and the criteria.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| F1 | confirmed | [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L209) | problematic | I agree. C-025 passes a memo that 'mentions United States v. Nixon standards (relevance, admissibility, specificity)'. R. Enterprises, 498 U.S. at 299-300 (read this session), holds that 'the Nixon standard does not apply in the context of grand jury proceedings.' The criterion is disjunctive, so it will not fail a correct memo. It does reward a memo whose only stated standard is the wrong law. |
| F2 | arguable | [C-001](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L17), [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L25), [C-003](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L33), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L257), [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L265) | not_a_defect | The criteria ask defense counsel to flag overbreadth and resist investor disclosure. That is the mainstream negotiation posture. The record supports it: the intake memo says Fund III and Credit Partners 'had no involvement in Veridian-related trading whatsoever'. None of these criteria requires claiming that a court would quash. R. Enterprises puts no initial burden on the government, which makes C-032's 'absent a government showing' loose as law. It is still a reasonable position to take with the AUSA, so this is ordinary disagreement about judgment. |
| F3 | arguable | [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L153) (not_a_defect), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L161) (arguable) | mixed | C-018 states the tension correctly: the entity has no privilege, but the designee keeps a personal one. It fails nobody who is right. C-019 requires Braswell or the collective-entity label, and it frames the issue as a custodian acting in a representative capacity. Attachment B demands oral testimony, where the closer authorities are Curcio and Kordel. A memo that relies correctly on Curcio, Kordel or Hale may fail C-019. |
| F4 | arguable | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L305) | not_a_defect | C-037 fails a memo only if 'the tipper-tippee theory and the Ashford-Grayfield family relationship are not connected'. A careful memo that treats the relationship as supporting a Salman gift-to-relative benefit, with the tip itself still to be proven, passes. Within a tipping theory, the phrase 'family relationship ... providing the personal benefit' is standard shorthand, and nothing requires the memo to overstate it. The record supports the brother-in-law relationship, Ashford's SAB access and the March 12 call. |
| F5 | arguable | [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L193) (not_a_defect), [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L329) (not_a_defect), [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L353) (arguable), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L361) (arguable), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L369) (arguable), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L377) (arguable), [C-047](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L385) (not_a_defect), [C-048](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/identify-government-subpoena-issues/task.json#L393) (not_a_defect) | mixed | C-023 fails only if the return-date issue is 'not flagged'. The facts check out: June 5 to July 8 is 33 days, with 18 requests and 11 topics, and the intake memo itself asks how to get an extension. C-040, C-047 and C-048 describe things any detailed subpoena memo will contain. The real risks are the labeled severity tiers in C-044 to C-046, which the instructions never request, and C-043's rule that every section must have all three elements. |

## Blind pass and what changed

I split blind O1. C-025 stays problematic (O1). The C-005 proportionality point is now a separate arguable finding (O2), so each finding carries one status. This session I re-verified R. Enterprises in CourtListener, including the passage 'the Nixon standard does not apply in the context of grand jury proceedings' and the no-initial-burden holding. I marked Braswell and Curcio unverified because I did not reread them this session. I did not adopt Sol F2 (C-001 to C-003, C-031, C-032) or Sol F4 (C-037): the positions in those criteria are reasonable, and their FAIL conditions do not fail correct work. From Sol F5, I added nothing beyond blind O2 and O3. I reviewed C-023, C-040, C-047 and C-048 and found no defects. All other blind findings (O2 to O7) are retained and renumbered O3 to O8.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-025, C-005): C-025 treats the Nixon trial-subpoena test (relevance, admissibility, specificity) as a standard for challenging a grand jury subpoena
- **O2** (arguable; C-044, C-045, C-046): Three criteria depend on explicit risk-severity ratings that the instructions never request
- **O3** (arguable; C-043): C-043 fails the whole memo if any single issue section lacks a recommendation
- **O4** (arguable; C-019): C-019 requires Braswell or the 'collective entity' label for an oral-testimony issue governed more directly by Curcio/Kordel
- **O5** (arguable; C-041): C-041 requires a 'proposed timeline' for USAO negotiations, which the instructions never request
- **O6** (arguable; C-049): C-049 requires noting the subpoena's lack of a privilege-log provision, a narrow checklist item
- **O7** (arguable; C-024, C-041): AUSA's name is an apparent anonymization artifact ('Jonathan Cromdale Consulting', email jonathan.mercer@usdoj.gov) and is repeated in the criteria

## Coverage and limits

Blind pass: Read all 52 criteria and the one-line instructions. Read in full: grand-jury-subpoena, intake-memo-tsao, mehta-tsao-phone-email, grayfield-zheng-email-chain, preservation-notice, clearwater-audit-report. Read partially: ic-memo-veridian (through the approval block, not the appendix of sources); code-of-ethics (Sections VI-X in full, the rest by grep); trading-blotter-extract (metadata, purchase rows and the sales-sheet header, plus greps). Also read the judge prompt (rubric_criterion.txt), which tells judges to apply each criterion "as described" and gives no guidance on equivalents, and the solver system prompt. Legal checks: read United States v. R. Enterprises, 498 U.S. 292 (1991), in CourtListener (the Nixon test does not apply to grand jury subpoenas; the "no reasonable possibility" relevance standard under Rule 17(c)). Read Braswell v. United States, 487 U.S. 99 (1988), including its discussion distinguishing Curcio. Did not read Curcio, Kordel, Nixon, Salman, Stringer or Steinhardt directly. Record inconsistencies that do not affect any criterion: iPhone 13 Pro (intake memo) vs iPhone 14 Pro (Mehta email); 605 vs 599 Lexington Avenue; the IC memo gives average daily volume of 120-150K shares while the emails give 1.8-2.2M; the blotter's fund trade GOF-240305-001 (15,000 sh at $41.90 on March 5) matches Marcus Grayfield's personal trade exactly in size, price and date, although the blotter says personal trades are excluded; the intake memo says the confidential 89% ORR came from "publicly available proxy materials". C-023's "spanning January 2023 to present" is slightly off, because Requests 15-16 reach back to 2022; this is trivial. Checked C-026/C-028 against the record: Code of Ethics Section VIII (BYOD) exists and VIII.A(d) gives the firm consent to access Firm-related data on personal devices, so those criteria are fair. I did not look at any other audit of Harvey LAB.

Reconciliation: In the blind pass I read all 52 criteria and the instructions, and read the key documents in full (subpoena, intake memo, emails, preservation notice, Clearwater report). In this pass I re-checked the criteria Sol raised (C-001 to C-003, C-018, C-019, C-023, C-025, C-031, C-032, C-037, C-040, C-043 to C-048) plus C-005, C-020, C-024, C-035, C-038, C-041 and C-049 against the subpoena and intake memo text. I verified that R. Enterprises holds Nixon inapplicable, sets the no-reasonable-possibility standard and places no initial burden on the government (CourtListener opinion 112523). I read Sol's audit markdown and index entry. I did not re-read Braswell, Curcio or Salman this session.
