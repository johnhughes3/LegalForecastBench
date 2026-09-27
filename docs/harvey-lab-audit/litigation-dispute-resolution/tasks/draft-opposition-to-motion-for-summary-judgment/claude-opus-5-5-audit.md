# Claude Opus 5.5 audit: Draft Opposition to Motion for Summary Judgment in BSA/AML Whistleblower Retaliation Case

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 59. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

Most of the rubric is well grounded in the record: the knowledge, timeline, pretext and comparator facts all check out. The clear defect is Count I. The rubric treats a BSA whistleblower claim under 31 U.S.C. § 5328 as viable. That statute was repealed before the 2023 events, and both it and its successor, § 5323(g), exclude employers subject to 12 U.S.C. § 1831j, which covers national banks like Ridgeline. So C-037's BSA prima facie case, with internal reports treated as protected, is wrong law under either version, and C-051 carries the stale label. Secondary issues: C-046 and C-017 require a McDonnell Douglas pretext framework and never credit SOX's AIR21 contributing-factor / clear-and-convincing standard; C-027 omits the consolidation condition for subsidiary coverage; the audit and PIP loan identifiers do not match (C-013); and C-040's PASS and FAIL counting tests differ. Under the all-pass metric, C-037 is the criterion most likely to penalize a legally careful answer.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | legal_error | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L310) | C-037 rewards a BSA prima facie case under repealed §5328 that is also unavailable against an insured bank under either version | revised |
| [O2](#o2) | arguable | legal_error | [C-051](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L422) | C-051 frames the BSA claim as live 'under 31 U.S.C. § 5328' | revised |
| [O3](#o3) | arguable | legal_error | [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L382), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L150) | Rubric requires a McDonnell Douglas pretext structure, but SOX uses the AIR21 contributing-factor / clear-and-convincing framework | blind |
| [O4](#o4) | arguable | legal_error | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L230) | SOX subsidiary criterion omits the consolidated-financial-statements condition | revised |
| [O5](#o5) | arguable | document_defect | [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L118) | Audit report's account names and loan numbers do not match the PIP's three files | blind |
| [O6](#o6) | arguable | ambiguous_or_unjudgeable | [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L334) | C-040's PASS and FAIL tests measure different things (10 distinct documents vs. 10 citations) | blind |

<a id="o1"></a>
### O1. C-037 rewards a BSA prima facie case under repealed §5328 that is also unavailable against an insured bank under either version

**Status:** problematic · **Category:** legal_error · **Criteria:** [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L310)

C-037's title anchors the claim to 31 U.S.C. §5328, which the AML Act of 2020 repealed effective Jan. 1, 2021, before any of the 2023 events. Its PASS text also treats internal reports as BSA-protected. The claim fails on a second, independent ground. Old §5328(e) and its successor §5323(g)(6) both exclude any employer subject to FDIA §33 (12 U.S.C. §1831j), and Ridgeline is a 'nationally chartered commercial bank', which is insured by operation of law. Such an employee's federal banking whistleblower remedy is §1831j, which protects reports to federal banking agencies or the AG, not internal reports. Old §5328(a) also never protected internal reports. The criterion therefore rewards stating as viable law a claim that fails under both the repealed and the current statute. A careful brief that flags the defect and pivots to §1831j or SOX, instead of building the §5328 elements with internal reporting as protected activity, risks failing it.

Evidence:
- `C-037`: “Prima facie case for BSA retaliation (31 U.S.C. § 5328) constructed”
- `C-037`: “reporting suspected BSA/AML violations internally and to FinCEN”
- `defendants-msj-brief.docx.txt`: “It is a nationally chartered commercial bank --- a wholly owned subsidiary of Ridgeline Financial Group, Inc.”
- `defendants-sumf.docx.txt`: “retaliation in violation of the anti-retaliation provisions of the Bank Secrecy Act, 31 U.S.C. § 5328”

Authorities (✓ = primary text checked in the auditing session):
- 31 U.S.C. § 5328 (repealed by Pub. L. 116-283, § 6314(b), effective Jan. 1, 2021) (✓): The BSA whistleblower provision relied on was repealed before the 2023 events.
- 31 U.S.C. § 5328(e) (pre-2021) (✓): The section did not apply to financial institutions subject to FDIA § 33.
- 31 U.S.C. § 5323(g)(6) (✓): 'This subsection shall not apply with respect to any employer that is subject to section 33 of the Federal Deposit Insurance Act (12 U.S.C. 1831j)'.
- 12 U.S.C. § 1831j(a)(1), (b) (✓): Insured depository institutions may not retaliate against employees who provide information to a federal banking agency or the AG. Enforcement is by a district-court action within 2 years.
- 12 U.S.C. §§ 222, 1814(b) (unverified): National banks are Federal Reserve members and FDIC-insured.

Suggested fix: Rebuild Count I around a claim that is actually available, such as §1831j (given the OCC inquiry). Alternatively, credit a brief that addresses Count I while flagging the §5328 repeal and bank carve-out. Remove 'internally' from the BSA protected-activity element.

Related GPT-6 Sol findings: confirmed_defects/0.

<a id="o2"></a>
### O2. C-051 frames the BSA claim as live 'under 31 U.S.C. § 5328'

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-051](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L422)

C-051 describes the claim as pleaded (SUMF ¶44). Any brief that responds to Count I will almost certainly pass, including one that flags the repeal or re-anchors the claim to §5323(g) or §1831j. Its only real defect is that it adopts the stale statutory label and treats the claim as live, so it could misgrade only under a hyper-literal reading.

Evidence:
- `C-051`: “PASS if the memorandum addresses Plaintiff's BSA whistleblower retaliation claim under 31 U.S.C. § 5328.”

Authorities (✓ = primary text checked in the auditing session):
- 31 U.S.C. § 5328 (repealed eff. Jan. 1, 2021) (✓): The provision was repealed.

Suggested fix: Change the wording to 'addresses Count I (BSA whistleblower retaliation, as pleaded)'. Accept briefs that note the repeal or the carve-out.

Related GPT-6 Sol findings: confirmed_defects/0.

<a id="o3"></a>
### O3. Rubric requires a McDonnell Douglas pretext structure, but SOX uses the AIR21 contributing-factor / clear-and-convincing framework

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L382), [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L150)

C-046 requires three steps: prima facie case, legitimate reason, pretext. C-017 requires framing the PIP defects as pretext. SOX incorporates 49 U.S.C. §42121(b): the plaintiff shows protected activity was a contributing factor, and the employer then must prove by clear and convincing evidence that it would have taken the same action. There is no pretext step and no retaliatory-intent element. The strongest opposition would argue that AIR21 governs the SOX claim and engage pretext only in the alternative, or under the Colorado claim. Such a brief can still pass through 'analogous framework' or the state claim, but neither criterion ever credits the correct federal standard. C-038 correctly uses 'contributing factor', so the rubric is internally mixed.

Evidence:
- `C-046`: “identifying the steps: (1) plaintiff's prima facie case, (2) defendant's legitimate reason, and (3) plaintiff's showing of pretext”
- `C-038`: “(protected activity, employer knowledge, adverse action, and contributing factor/causal connection)”

Authorities (✓ = primary text checked in the auditing session):
- Lockheed Martin Corp. v. Admin. Review Bd., 717 F.3d 1121 (10th Cir. 2013) (✓): SOX uses the contributing-factor standard. Temporal proximity may suffice.
- 18 U.S.C. § 1514A(b)(2) (✓): SOX actions are governed by the burdens of proof in 49 U.S.C. § 42121(b).
- Murray v. UBS Securities, LLC, 601 U.S. 23 (2024) (unverified): A SOX whistleblower need not prove retaliatory intent.

Suggested fix: In C-046, accept either McDonnell Douglas or AIR21 contributing-factor plus same-decision burden-shifting. In C-017, accept 'pretext or failure to carry the clear-and-convincing same-decision burden'.

Related GPT-6 Sol findings: arguable/1.

<a id="o4"></a>
### O4. SOX subsidiary criterion omits the consolidated-financial-statements condition

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L230)

C-027 says SOX 'extend[s] to employees of subsidiaries of publicly traded companies.' Section 1514A(a) covers only a subsidiary 'whose financial information is included in the consolidated financial statements' of the public parent. The record shows wholly owned status, which is a strong inference of consolidation, but no direct evidence of it. Correct briefs pass. The defect is that the criterion states the rule without the element Defendant would attack, so it would also pass a brief that states subsidiary coverage as unconditional.

Evidence:
- `C-027`: “because SOX protections extend to employees of subsidiaries of publicly traded companies”

Authorities (✓ = primary text checked in the auditing session):
- 18 U.S.C. § 1514A(a) (✓): Coverage includes 'any subsidiary or affiliate whose financial information is included in the consolidated financial statements of such company'.

Suggested fix: Add the consolidation condition to C-027, for example 'a wholly owned subsidiary whose financials are consolidated into RDFG's'.

Related GPT-6 Sol findings: arguable/2.

<a id="o5"></a>
### O5. Audit report's account names and loan numbers do not match the PIP's three files

**Status:** arguable · **Category:** document_defect · **Criteria:** [C-013](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L118)

The PIP and the Q1 audit identify different entities and loan numbers. PIP: Westlake Properties Inc. CL-2020-05832, Meridian Commercial Partners LLC CL-2021-07291. Audit: Westlake Commercial Properties LLC CL-2020-05537, Meridian Infrastructure Partners, Inc. CL-2021-06190. The Thornburg numbers also differ, and the MSJ uses a third set of names. Caldwell's concession at deposition p. 52 that the audit rated all three accounts Satisfactory largely rescues the point. Still, a careful brief that hedges because of the mismatch could fail a strict reading of 'rated all three files Satisfactory.'

Evidence:
- `vasquez-pip.docx.txt`: “**Westlake Properties Inc.** (Account No. CL-2020-05832)”
- `internal-audit-q1-2023.docx.txt`: “**4.2 Westlake Commercial Properties LLC (Loan No. CL-2020-05537)**”
- `caldwell-deposition-excerpts.docx.txt`: “Q. All three? A. Yes.”

Suggested fix: Make the identifiers match across the documents, or have C-013 accept briefs that rely on Caldwell's concession and note the discrepancy.

<a id="o6"></a>
### O6. C-040's PASS and FAIL tests measure different things (10 distinct documents vs. 10 citations)

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-040](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L334)

PASS requires 'at least 10 distinct document citations', meaning ten different documents. FAIL is triggered by 'fewer than 10 record citations', which counts citations. A brief with many citations to only 8 documents meets neither condition, so the judges may split. The threshold of ten is also never stated in the instructions. This is minor because 15 documents are available.

Evidence:
- `C-040`: “with at least 10 distinct document citations across the brief. FAIL if the memorandum contains fewer than 10 record citations to specific documents.”

Suggested fix: Use one test in both branches, or replace the count with 'factual assertions supported by pinpoint record citations throughout'.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| confirmed_defects/0 | confirmed | [C-037](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L310) (problematic), [C-051](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L422) (arguable) | mixed | §5328 was repealed effective Jan. 1, 2021. Sol's carve-out point also holds, and it reaches the repealed statute too: old §5328(e) and current §5323(g)(6) both exclude employers subject to 12 U.S.C. §1831j, which covers insured depository institutions, and the record calls Ridgeline a 'nationally chartered commercial bank'. C-037 rewards a BSA prima facie case, with internal reports as protected activity, that fails under either version. C-051 only asks the brief to address the claim as pleaded, so the misgrade risk there is low. |
| arguable/0 | arguable | [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L246), [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L254), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L326) | not_a_defect | The MSJ § E expressly argues field and conflict preemption, so a rebuttal is required. The propositions the criteria reward are correct: neither statute expressly preempts state law, and §1514A(d) and §5323(g)(5) preserve state remedies. Colorado's adequate-statutory-remedy doctrine is a separate argument that none of these criteria forbids. A brief that also answers the Crawford/Martin Marietta point still passes. The criteria are incomplete, but they do not misgrade. |
| arguable/1 | arguable | [C-017](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L150) (arguable), [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L318) (not_a_defect), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L382) (arguable) | mixed | SOX incorporates the AIR21 burdens in 49 U.S.C. §42121(b): contributing factor, then the employer's clear-and-convincing same-action defense. There is no pretext step. The Tenth Circuit applies this in Lockheed Martin, and Murray v. UBS confirms no retaliatory-intent element. C-046 and C-017 require a pretext structure and never credit the AIR21 standard, but the Colorado claim or 'analogous framework' language can satisfy them, so they are arguable. C-038 correctly says 'contributing factor'. |
| arguable/2 | arguable | [C-027](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L230) (arguable), [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L238) (not_a_defect), [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L318) (not_a_defect), [C-049](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L406) (not_a_defect) | mixed | C-027 leaves out §1514A(a)'s condition that the subsidiary's financials be consolidated into the parent's statements, though wholly owned status makes consolidation a strong inference. C-028 accepts the statutory text, and citing Lawson's description of the Dodd-Frank amendment is common practice. C-038 and C-049 accept SOX protected activity. Arguing that an AML report is reasonably believed to involve wire or bank fraud is reasonable advocacy, not a rubric error. |
| unverified/0 | unverified | [C-048](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-for-summary-judgment/task.json#L398) | not_a_defect | A web search did not find FinCEN advisory FIN-2023-A001, so the advisory the Redmond report relies on may be fictional. C-048 does not depend on the advisory's identity. It rewards citing Redmond's 7-of-9 conclusion, or the 'no reasonable compliance officer' conclusion, both of which appear verbatim in the report. A brief can cite either without vouching for the advisory. |

## Blind pass and what changed

I made four changes after reading Sol. (1) I adopted and verified Sol's carve-out point: current §5323(g)(6) and repealed §5328(e) both exclude employers subject to 12 U.S.C. §1831j, and the record calls Ridgeline a nationally chartered bank. The BSA claim therefore fails under either version, and C-037 rewards treating internal reports as BSA-protected, which was wrong even under old §5328(a). That makes C-037 the primary problematic criterion. (2) I downgraded C-051 to arguable, because it only asks the brief to address the claim as pleaded. (3) I dropped C-028, because it accepts the statutory text and citing Lawson's description of the amendment is common practice; C-027 stays arguable. (4) I dropped blind O6, the DOL-exhaustion filing date, because Defendant did not raise it, it does not change what a correct opposition says, and no criterion misgrades on it. I rejected Sol's Colorado preemption cluster (C-029, C-030, C-039) and its C-048 advisory point as rubric defects.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-051, C-037): BSA claim is framed under 31 U.S.C. § 5328, which was repealed effective Jan. 1, 2021, before any of the 2023 events
- **O2** (arguable; C-046, C-017): Rubric requires a McDonnell Douglas pretext framework, but SOX (and § 5323(g)) use the AIR21 contributing-factor standard
- **O3** (arguable; C-027, C-028): SOX subsidiary criterion omits the consolidated-financial-statements condition and treats Lawson as subsidiary authority
- **O4** (arguable; C-013): Audit report's account names and loan numbers do not match the PIP's three files
- **O5** (arguable; C-040): C-040's PASS and FAIL tests measure different things (10 distinct documents vs. 10 citations)
- **O6** (arguable; C-052, C-038, C-027, C-051): Record's filing date makes both federal whistleblower claims facially premature under DOL exhaustion rules

## Coverage and limits

Blind pass: I read all 59 criteria and the instructions. I read these documents in full: the defendant's MSJ brief and SUMF, both Hargrove-Caldwell emails, the Prescott April 18 email, the Thornburg declaration, the termination letter, Handbook § 7.4, the PIP, the 2023 business plan, the 2022 review, the Caldwell deposition excerpts, the Prescott deposition excerpts, and the Medina declaration. I read the internal audit report through § 6. I searched the Redmond expert report for the opinions the criteria rely on (7 of 9 red flags, "facially inadequate," "no reasonable compliance officer," the 14-day investigation, and the SAR violation). I also searched the record for consolidation, FDIC, and DOL-exhaustion facts. I checked every date calculation against the record (13, 32, 99, 22 and 23 days) and all are correct. I verified from primary text in this session: the repeal of 31 U.S.C. § 5328 (uscode.house.gov and LII); § 1514A(a), including the subsidiary/consolidated-statements language, and § 1514A(d) (LII); Lockheed Martin v. ARB, 717 F.3d 1121 (10th Cir. 2013), which applies the contributing-factor framework to SOX (CourtListener); and Lawson v. FMR, 571 U.S. 429 (CourtListener), which is a contractor holding and mentions subsidiary coverage only in describing the Dodd-Frank amendment. For § 5323(g), I saw the (g)(5) rights-retained clause and part of the (g)(1) prohibition quoted verbatim; the enforcement/180-day and 42121(b) provisions came back as a fetch summary, not verbatim text. I did not read Martin Marietta v. Lorenz, Crawford Rehab v. Weissman, or any Colorado case on the statutory-remedy bar to the public-policy tort. I also did not check Judge Jackson's practice standards on the format of summary-judgment responses. I noted but did not flag minor record inconsistencies that do not change what a correct answer is. These include the Thornburg declaration being executed April 22, 2024 yet shown as an exhibit at the March 8, 2024 deposition, the email timestamps and wording differing between Exhibit 5 and Caldwell's reading of it, "Amanda" versus "Diane" Prescott, and mismatched employee IDs.

Reconciliation: I reviewed all 59 criteria and the instructions, relying on my blind-pass reading of all 15 documents. This pass I also read Sol's audit (markdown and index) and re-checked the record for Sol's points: bank charter, FinCEN/OCC facts, MSJ § E's preemption and Colorado adequate-remedy arguments, and the Redmond report's use of FIN-2023-A001. I read these primary texts this session: 31 U.S.C. § 5323(g)(1) and (g)(6) (LII); former 31 U.S.C. § 5328, including (e) (govinfo, 2011 edition); and 12 U.S.C. § 1831j(a)(1) and (b) (LII). A web search did not find FIN-2023-A001. I did not verify 12 U.S.C. §§ 222 or 1814(b) (national banks are insured) or Murray v. UBS from primary text, and I did not read Colorado cases on the adequate-statutory-remedy bar.
