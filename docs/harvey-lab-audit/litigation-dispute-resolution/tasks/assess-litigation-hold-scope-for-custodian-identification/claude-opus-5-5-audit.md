# Claude Opus 5.5 audit: Assess Litigation Hold Scope for Custodian Identification — Custodian Recommendation Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 50. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is mostly sound and closely grounded in the record. The GC email chain explicitly asks for much of what the criteria test: the unified hold, the timeline of when preservation should have been triggered versus when it was, the evaluation of the interviewees, the Salesforce auto-deletion, and the Kovach device. So most apparent specificity is requested rather than hidden. I found no problematic criterion. Three are arguable: C-009 has a PASS/FAIL gap for answers naming one or two managers; C-028 gates on an engagement-letter scope point that sits outside the hold work; and C-034's alternative prong rewards a loose SOX preservation proposition. There are also minor document inconsistencies that should not affect grading. Sol's two findings match two of mine; I rate C-009 arguable rather than confirmed.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | arguable | ambiguous_or_unjudgeable | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L83) | C-009 PASS needs all three regional managers but FAIL fires only if none is named; one or two named is undefined | blind |
| [O2](#o2) | arguable | unrequested_requirement | [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L235) | C-028 gates on flagging the outside-counsel engagement-letter scope gap, an engagement issue rather than hold scope | blind |
| [O3](#o3) | arguable | legal_error | [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L283) | C-034's alternative prong rewards the claim that SOX 806 creates 'broader or more protective preservation obligations' | blind |
| [O4](#o4) | arguable | document_defect | — | Minor record inconsistencies: Tran-Nguyen's title and GC tenure, and Kovach's BYOD enrollment date and apps | blind |

<a id="o1"></a>
### O1. C-009 PASS needs all three regional managers but FAIL fires only if none is named; one or two named is undefined

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L83)

The PASS condition requires the memo to identify 'at least the three regional sales managers' (Collings, Muñoz, Patwardhan). The FAIL condition triggers only if 'none of these three individuals are identified.' A memo naming one or two, for example the two with documentary evidence while putting Muñoz in a lower tier or leaving her out, fits neither condition, and the two judges could split. Under all-pass scoring, one split zeroes the run. That said, the GC's Nov 7 email explicitly asks the memo to address whether each of the eight interviewees should be a custodian, so competent memos will usually name all three. The misgrade risk is confined to partial answers, which is why this is arguable rather than problematic.

Evidence:
- `C-009`: “PASS if the memo identifies at least the three regional sales managers”
- `C-009`: “FAIL if none of these three individuals are identified as custodians or potential custodians.”
- `brashear-tran-nguyen-emails.eml.txt`: “remind me in the memo whether any of the internal investigation interviewees — the eight people Nathan Cross interviewed — should be custodians”

Suggested fix: Make PASS and FAIL complements: 'FAIL if any of the three is omitted', or an explicit at-least-N rule.

Related GPT-6 Sol findings: confirmed_defects/0.

<a id="o2"></a>
### O2. C-028 gates on flagging the outside-counsel engagement-letter scope gap, an engagement issue rather than hold scope

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-028](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L235)

The instructions ask for custodians, data sources, spoliation risks and preservation coordination. The GC emails ask for a unified hold covering both matters, and nowhere mention the Pinnacle Hartwell engagement terms. The engagement letter does exclude any matter other than the Kovach claims, so the observation is grounded in the record. But the company's preservation duty and the unified hold stand whatever outside counsel's engagement covers, and the engagement letter itself says the company bears ultimate responsibility for the hold. A competent memo can recommend one consolidated hold covering both matters, with outside-counsel coordination, without discussing the engagement letter, and it would fail here. Only the 'hold ... may need to be updated' branch ties the criterion to the requested work.

Evidence:
- `task.json instructions`: “prepare a litigation hold memo covering custodian identification, data sources, spoliation risks, and preservation coordination”
- `pinnacle-hartwell-engagement.docx.txt`: “This engagement does not include the provision of tax advice, regulatory compliance advice, or representation in any matter other than the defense of the Kovach claims described above”
- `C-028`: “FAIL if this engagement scope gap is not mentioned.”

Suggested fix: Make it non-gating, or also pass memos that address who handles the SEC response or coordinate the unified hold with SEC-matter counsel.

<a id="o3"></a>
### O3. C-034's alternative prong rewards the claim that SOX 806 creates 'broader or more protective preservation obligations'

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L283)

Section 806 (18 U.S.C. § 1514A) is an anti-retaliation provision. It widens the relevant subject matter (protected activity, employer knowledge, contributing-factor causation), but it imposes no distinct or 'more protective' preservation duty of its own. The duty to preserve comes from reasonable anticipation of litigation and from the SEC inquiry. The provision that actually bears on record destruction is SOX 802 (18 U.S.C. § 1519), which the retention policy cites. Because the criterion reads 'and/or', a correct memo passes on the relevance prong. The defect is that the criterion also rewards a loose or incorrect legal statement.

Evidence:
- `C-034`: “and/or that SOX claims may create broader or more protective preservation obligations”
- `nexfield-retention-policy.docx.txt`: “including but not limited to penalties under SOX Section 802 (18 U.S.C. §§ 1519, 1520)”

Authorities (✓ = primary text checked in the auditing session):
- 18 U.S.C. § 1514A (unverified): SOX 806 is a whistleblower anti-retaliation provision and contains no document-preservation mandate
- 18 U.S.C. § 1519 (unverified): Criminalizes destroying or altering records with intent to obstruct a federal investigation; relevant to the SEC inquiry

Suggested fix: Replace the second prong with: the SOX theory widens relevant subject matter, and the SEC inquiry brings obstruction exposure under § 1519.

Related GPT-6 Sol findings: arguable/0.

<a id="o4"></a>
### O4. Minor record inconsistencies: Tran-Nguyen's title and GC tenure, and Kovach's BYOD enrollment date and apps

**Status:** arguable · **Category:** document_defect · **Criteria:** none

First inconsistency: the IT memo attributes the February 2023 Teams purge configuration to 'the prior General Counsel's office.' Yet the retention policy shows Tran-Nguyen approving v1.0 (2021) and v2.0 (Feb 2023) as General Counsel, and her email signature reads 'Deputy General Counsel' while every other document calls her General Counsel. Second: the IT memo dates Kovach's BYOD enrollment to April 3, 2020 with Outlook and Teams, while HR dates it to about January 2021 and adds the Salesforce app. Neither conflict is likely to misgrade a criterion (C-041 and C-021 are robust to them), but a careful memo may spend effort reconciling them, and the app list bears on the scope of the device preservation demand.

Evidence:
- `it-infrastructure-memo.docx.txt`: “configured by the IT department in coordination with the prior General Counsel's office in February 2023”
- `nexfield-retention-policy.docx.txt`: “Monica Tran-Nguyen, General Counsel; Graham Ellicott, CEO”
- `brashear-tran-nguyen-emails.eml.txt`: “Monica Tran-Nguyen Deputy General Counsel”
- `kovach-personnel-file-summary.docx.txt`: “Enrollment Date: Approximately January 2021, concurrent with Kovach's promotion to Vice President.”

Suggested fix: Align Tran-Nguyen's title and GC tenure across documents; reconcile the BYOD enrollment date and app list.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| confirmed_defects/0 | confirmed | [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L83) | arguable | The PASS and FAIL conditions really do leave a gap: PASS needs all three managers, FAIL fires only if none is named, and a memo naming one or two fits neither. But Tran-Nguyen's Nov 7 email expressly asks whether each of the eight interviewees should be a custodian, and the investigation summary gives Collings, Muñoz and Patwardhan clear channel-stuffing knowledge. So competent memos will almost always name all three. The gap bites only partial answers, and I am not confident it misgrades competent work. That makes it arguable, not confirmed. |
| arguable/0 | arguable | [C-034](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L283) | arguable | I agree. The first prong is sound: the hold should cover communications about Kovach's Audit Committee reports and any later adverse actions. The alternative prong, 'SOX claims may create broader or more protective preservation obligations', is loose law. SOX 806 (18 U.S.C. § 1514A) is an anti-retaliation provision with no preservation mandate of its own; record-destruction exposure comes from SOX 802 (§ 1519), which the retention policy cites. Because the criterion reads 'and/or', a correct memo still passes. The defect is that it rewards an imprecise proposition, not that it fails correct work. |

## Blind pass and what changed

I dropped blind O2 (C-015). On re-reading, the IT memo itself says locally cached Teams chat history may still be on Kovach's iPhone, and Brashear's Nov 6 email stresses the same point. C-015 also accepts 'forensic analysis' as a recovery avenue. So a competent memo that recommends forensic preservation and imaging of the device for cached Teams data would satisfy it even if it adopts IT's view that server-side purged content is unrecoverable. The misgrade risk is too low to flag. Sol's note that C-015 asks for investigation, not a promise of recovery, is consistent with this. C-009 and C-034 stay arguable. Sol's C-034 reasoning matches mine. I do not adopt Sol's 'confirmed' status for C-009, because the Nov 7 email's instruction to evaluate all eight interviewees makes a one- or two-manager answer unlikely for competent work. Blind O3 (C-028) and O5 (document inconsistencies) are kept and renumbered O2 and O4. Sol flagged neither.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (arguable; C-009): C-009 PASS needs all three regional managers but FAIL fires only if none is named; one or two named is undefined
- **O2** (arguable; C-015): C-015 requires a recoverability investigation that the IT memo says is futile for purged Teams chat content
- **O3** (arguable; C-028): C-028 requires flagging the outside-counsel engagement-letter scope gap, which is an engagement issue rather than a hold-scope issue
- **O4** (arguable; C-034): C-034's alternative prong rewards the claim that SOX 806 creates 'broader or more protective preservation obligations'
- **O5** (arguable; no criterion): Minor record inconsistencies: Tran-Nguyen's title and GC tenure, and Kovach's BYOD enrollment date and apps

## Coverage and limits

Blind pass: I read all 50 criteria and the instructions. I read seven documents in full: the IT infrastructure memo, the internal investigation summary, the Kovach personnel file summary, the Stadler Raines demand letter, the Pinnacle Hartwell engagement letter, the SEC inquiry letter, and the Brashear/Tran-Nguyen email chain. I did not read the Nexfield retention policy end to end. I searched it with grep and then read the sections that matter here: the header, §§3.1–3.2, §3.6, §§4.1–4.4, and the Appendix A schedule. I also read the judge prompt and the solver system prompt. External legal verification failed: WebFetch returned a spend-limit error, and CourtListener uses the same account. So every statutory point below comes from my own knowledge and from the record's own citations, and none of it is verified against primary text in this session. I checked record facts (dates, retention periods, the 15% figure, names and roles, the eight interviewees, the July 2–15 window) against the documents. They are consistent with the criteria except where noted.

Reconciliation: I read all 50 criteria and the instructions in the blind pass, and re-checked C-009, C-015, C-021, C-028, C-034 and C-041 in this pass. Blind pass: seven documents read in full, and the retention policy read in its relevant sections. This pass: I re-read the full Brashear/Tran-Nguyen email chain, the relevant IT memo passages on Teams, backups and the device cache, the engagement letter's scope section, and the investigation interview summaries for the three regional managers, and I grepped every document for Tran-Nguyen's title. I read Sol's index entry and audit report in full. I did not verify the statutes against primary text in this session, so every authority is marked verified=false.
