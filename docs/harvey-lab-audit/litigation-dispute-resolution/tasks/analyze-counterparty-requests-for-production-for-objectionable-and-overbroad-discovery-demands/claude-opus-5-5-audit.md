# Claude Opus 5.5 audit: Analyze Counterparty Requests for Production for Objectionable and Overbroad Discovery Demands — Issue Identification Memorandum

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](../../README.md).

[Task landing page](README.md) · [GPT-6 Sol report](gpt-6-sol-audit.md) · [Pinned rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json) · Harvey commit `1dd81403b2fb`

**Model:** Claude Opus 5.5 (claude-opus-5-5), reasoning effort `high`. **Rubric criteria:** 47. **Workflow run:** `wf_0aa16214-381`.

Method: a blind pass that saw only the task instructions, rubric, and supplied documents, followed by a reconciliation pass that checked every GPT-6 Sol finding against the record and law. The findings below are the final position.

## Overall assessment

The rubric is mostly sound and closely tied to the record. The strategy email supplies the structure (RFP numbers, nature of the problem, citations, recommendations, high/medium/low priority) and most of the substance: RFP 31, 19, 33, 15/40, 36, and 9, the 2009 start dates, the 11 product lines, and the 950K-document volume. The protective order's express disclaimer of privilege coverage supports the 502(d) criteria. The one clearly defective criterion is C-030. It requires using the non-compete end date to narrow 'to the present' requests, but fact discovery falls entirely inside the covenant window and royalties begin after it. Smaller risks come from C-018/C-019, which lock in a contention/prematurity theory for RFP 41; C-024/C-025, which treat an optional form-of-production omission as a defect; C-002's fixed start date, which ignores the independent-development defense; the literal clash between C-032 and C-044; and the peripheral wind-down requirement in C-047. Under all-pass scoring, any one of these could zero out an otherwise excellent memo.

## Findings

| ID | Status | Category | Criteria | Finding | Origin |
|---|---|---|---|---|---|
| [O1](#o1) | problematic | source_conflict | [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L251) | C-030 treats the non-compete end date as a way to narrow 'to the present' requests, but discovery falls inside the covenant | blind |
| [O2](#o2) | arguable | legal_error | [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L155), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L163) | RFP 41 must be called a contention interrogatory and objected to as premature, though Rule 33(a)(2) governs interrogatories | blind |
| [O3](#o3) | arguable | unrequested_requirement | [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L203), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L211) | The RFPs' silence on ESI form must be flagged as a defect, but Rule 34 makes specifying form optional | blind |
| [O4](#o4) | arguable | ambiguous_or_unjudgeable | [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L27) | C-002's fixed 2017/2018 start date ignores Greenleaf's need for pre-JV records for its independent-development defense | blind |
| [O5](#o5) | arguable | internal_inconsistency | [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L267), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L363) | C-032 requires RFP numbers for 'each issue', while C-044 requires cross-cutting issues that have none | blind |
| [O6](#o6) | arguable | unrequested_requirement | [C-047](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L387) | The July–September 2023 wind-down must be mentioned even though no objectionable request turns on it | blind |

<a id="o1"></a>
### O1. C-030 treats the non-compete end date as a way to narrow 'to the present' requests, but discovery falls inside the covenant

**Status:** problematic · **Category:** source_conflict · **Criteria:** [C-030](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L251)

C-030 fails any memo that does not use the §9.1 period (June 30, 2023 to June 30, 2025) to narrow requests that run 'to the present'. On this record that narrowing does almost nothing. Responses are due September 11, 2024, and fact discovery closes February 28, 2025, both inside the covenant window. The only request cut short would be Rule 26(e) supplementation between July and October 2025. Conduct after the period also stays relevant: Exhibit B royalties start July 1, 2025, and the trade-secret claims do not depend on the covenant's term. The strategy email never suggests the non-compete as a scoping tool. A competent memo that leaves it out, or says correctly that the covenant makes post-dissolution documents relevant, is failed on a point that changes no recommended objection. C-046 already rewards citing §9.1.

Evidence:
- `C-030`: “notes that this period may be relevant to narrowing the scope of forward-looking document requests that seek documents 'to the present' or beyond the non-compete period”
- `case-management-order.docx.txt`: “Fact discovery shall close on February 28, 2025.”
- `dissolution-agreement-executed.docx.txt`: “royalty obligations shall commence on July 1, 2025”
- `dissolution-agreement-executed.docx.txt`: “from June 30, 2023, through and including June 30, 2025”

Suggested fix: Delete C-030 or fold it into C-046. If it stays, reward identifying the §9.1 period as the window of alleged breach, without requiring it to be used as a narrowing cutoff.

<a id="o2"></a>
### O2. RFP 41 must be called a contention interrogatory and objected to as premature, though Rule 33(a)(2) governs interrogatories

**Status:** arguable · **Category:** legal_error · **Criteria:** [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L155), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L163)

Rule 33(a)(2) lets a court defer answers to contention interrogatories. It does not govern Rule 34 requests for existing documents. Many courts allow requests for documents supporting pleaded defenses, and Rule 26(a)(1)(A)(ii) already requires parties to disclose documents they may use. The email is silent on RFP 41. The stronger objections are overbreadth (the 'relate to' and 'contradict' language) and work product in counsel's selection of documents, and the usual fix is to agree to produce the documents Greenleaf relies on. A memo that takes that approach fails C-018, which requires the contention-interrogatory label, and C-019, which requires prematurity. Because contention-style prematurity objections are common in practice and C-019 accepts a general prematurity argument, many memos would still pass, so this is arguable rather than confirmed.

Evidence:
- `C-018`: “effectively a contention interrogatory masquerading as a document request, requiring Greenleaf to marshal its entire case theory prematurely”
- `C-019`: “FAIL if no legal basis related to the prematurity of contention discovery is cited.”
- `plaintiffs-first-rfps.docx.txt`: “Produce all Documents that support, contradict, or relate to each of Greenleaf\'s affirmative defenses and counterclaims”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Civ. P. 33(a)(2) (unverified): Contention interrogatories are not objectionable merely for asking for opinions or contentions; the court may order that they need not be answered until designated discovery is complete. The provision addresses interrogatories.
- Fed. R. Civ. P. 26(a)(1)(A)(ii) (unverified): Initial disclosures must describe or produce documents the party may use to support its claims or defenses

Suggested fix: C-018: pass if RFP 41 is flagged as improper on any reasonable ground (contention-style, overbreadth, work product in counsel's selection, duplicative of initial disclosures). C-019: accept any supportable legal basis or response strategy, including an offer to produce relied-upon documents with Rule 26(e) supplementation.

Related GPT-6 Sol findings: Confirmed grading defect / required questionable advocacy: item 1.

<a id="o3"></a>
### O3. The RFPs' silence on ESI form must be flagged as a defect, but Rule 34 makes specifying form optional

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L203), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L211)

It is true that the instructions set no ESI form and only RFP 36 demands native format. But Rule 34(b)(1)(C) says a requester 'may' specify form. If it does not, (b)(2)(D)-(E) let the responding party state its form and produce in a reasonably usable form. The omission is therefore not objectionable, it benefits Greenleaf, and the strategy email does not raise it. A memo that treats form as Greenleaf's choice, or deals with it only through an ESI protocol (rewarded by C-026), fails C-024 for not calling the silence an 'ambiguity'. It then fails C-025, which ties the Rule 34(b) citation to that same issue.

Evidence:
- `C-024`: “identifies that the Requests for Production generally fail to specify the form of production for ESI ... creating ambiguity”
- `plaintiffs-first-rfps.docx.txt`: “Production of Documents in response to these Requests shall include all electronically stored information as defined in Rule 34(a)(1)(A)”
- `task.json instructions`: “prepare an internal memo flagging objectionable requests with recommended responses”

Authorities (✓ = primary text checked in the auditing session):
- Fed. R. Civ. P. 34(b)(1)(C), (b)(2)(D)-(E) (unverified): A request may specify form; if none is specified, the responder states its intended form and produces in a form ordinarily maintained or reasonably usable

Suggested fix: Merge C-024 and C-025 into C-026: pass if the memo addresses form of production or an ESI protocol, with or without a Rule 34(b) citation, without requiring that the omission be called a defect.

Related GPT-6 Sol findings: Arguable concerns: item 1.

<a id="o4"></a>
### O4. C-002's fixed 2017/2018 start date ignores Greenleaf's need for pre-JV records for its independent-development defense

**Status:** arguable · **Category:** ambiguous_or_unjudgeable · **Criteria:** [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L27)

The email supports a start date around 2017. But JV §11.2(b) requires independent development to be proven 'by contemporaneous written records', Background IP is measured as of January 15, 2019, and the hold memo preserves Background IP material for that defense. A careful memo might narrow RFPs 3, 7, 14, and 22 while carving out pre-2017 Background IP development records, or warn about sword/shield problems. Such a memo proposes narrowing, yet its start date is earlier than 'no earlier than 2017'. That leaves it between C-002's PASS and FAIL conditions.

Evidence:
- `C-002`: “recommends narrowing the temporal scope to a period starting no earlier than 2017 or 2018”
- `litigation-hold-memo.docx.txt`: “All documents related to Greenleaf's background intellectual property in filtration technology, to the extent it may bear on the independent-development defense.”
- `kerrigan-discovery-strategy.eml.txt`: “even pre-JV negotiations don't go back before 2017 at the earliest”

Suggested fix: Pass any narrowing proposal that removes most of the 2009–2017 period, including one with a Background IP carve-out. Fail only if no temporal narrowing is proposed.

Related GPT-6 Sol findings: Arguable concerns: item 2.

<a id="o5"></a>
### O5. C-032 requires RFP numbers for 'each issue', while C-044 requires cross-cutting issues that have none

**Status:** arguable · **Category:** internal_inconsistency · **Criteria:** [C-032](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L267), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L363)

C-044 requires a separate treatment of issues that affect the whole production, such as the ESI protocol, the FRE 502(d) order, and general meet-and-confer topics. Those issues have no specific RFP numbers. C-032 passes only if 'for each issue discussed' the affected RFP numbers are identified. A literal judge could fail C-032 because of the very section C-044 demands.

Evidence:
- `C-032`: “PASS if, for each issue discussed in the memorandum, the specific RFP number(s) affected are identified.”
- `C-044`: “as distinct from issues with individual RFPs”

Suggested fix: Limit C-032 to RFP-specific issues and exempt the cross-cutting issues rewarded by C-044.

<a id="o6"></a>
### O6. The July–September 2023 wind-down must be mentioned even though no objectionable request turns on it

**Status:** arguable · **Category:** unrequested_requirement · **Criteria:** [C-047](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L387)

The wind-down is the endpoint of RFPs 10, 17, and 23. Those requests are reasonably scoped and are not among the objectionable requests the memo is asked to catalogue. The email mentions the wind-down only as one category of privileged communications. A complete objections memo can analyze temporal overbreadth and every other issue without mentioning it, and still fail this gating criterion.

Evidence:
- `C-047`: “FAIL if the wind-down period is not mentioned.”
- `kerrigan-discovery-strategy.eml.txt`: “the wind-down period (July 1 through September 30, 2023)”

Suggested fix: Drop C-047, or make it a non-gating quality consideration.

## Verdicts on GPT-6 Sol's findings

| GPT-6 Sol finding | Sol status | Criteria | Opus verdict | Reason |
|---|---|---|---|---|
| Confirmed grading defect / required questionable advocacy: item 1 | confirmed | [C-018](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L155), [C-019](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L163) | arguable | RFP 41 asks for documents that 'support, contradict, or relate to' each defense and counterclaim. Calling it contention-style is a natural reading, and prematurity is a common objection that C-019's 'otherwise articulates' clause accepts. But the strategy email never mentions RFP 41, and Rule 33(a)(2) governs interrogatories. A competent memo that objects on overbreadth or work-product grounds and offers to produce the documents Greenleaf relies on fails both criteria. That misgrades some competent answers, not most, so the right label is arguable rather than confirmed. |
| Arguable concerns: item 1 | arguable | [C-024](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L203), [C-025](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L211) | arguable | The record supports the factual premise. Instruction 5 and the other instructions set no ESI form, and only RFP 36 demands native format. But under Rule 34(b)(1)(C) a requester 'may' specify form, and (b)(2)(D)-(E) then leave the choice to the responding party. So the omission is not an objection, and the email does not raise it. A memo that handles form only through an ESI protocol (C-026) fails C-024, and C-025 then fails with it. |
| Arguable concerns: item 2 | arguable | [C-002](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L27) | arguable | The email supports a start date around 2017 ('pre-JV negotiations don't go back before 2017'). But JV §11.2(b) requires independent development to be shown by 'contemporaneous written records', and the hold memo preserves Background IP for that defense. A memo that carves pre-2017 Background IP records out of RFP 3 or RFP 14 falls between C-002's PASS and FAIL conditions. The risk is low to moderate. |
| Arguable concerns: item 3 | arguable | [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L67), [C-016](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L139), [C-023](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L195), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/task.json#L259) | not_a_defect | The record supports each of these, and each is worded with hedges. The email says the financing information has 'little to no bearing' (C-007) and personnel compensation, benefits, and medical data have 'no apparent relevance' (C-016). The hold memo preserves Helix communications as 'relevant to Greenleaf's counterclaim' (C-023). RFPs 15 and 40 contain the 'agents, representatives, consultants' language, and the email ties it to Ridgepoint and Sterling Ark, with 'may have no legal right' as the criterion's hedge (C-031). None of them requires a categorical conclusion or a section number. |

## Blind pass and what changed

No findings were added or dropped. I checked Sol's 'confirmed' label on C-018/C-019 and kept them arguable. RFP 41's wording makes the contention-style label natural, and C-019's 'otherwise articulates' clause accepts the common prematurity objection, so the criteria misgrade only some competent memos. I rejected Sol's arguable cluster on C-007, C-016, C-023, and C-031. The strategy email and hold memo support each of them, and each is worded with hedges ('much of', 'any category', 'may be relevant', 'may have no legal right'). I also rechecked C-030 against the trial and supplementation dates. Rule 26(e) supplementation running from July to October 2025 is the only request the non-compete end date could narrow, and post-period royalties and the trade-secret claims keep that material relevant. So I kept C-030 as problematic. I could not verify any authority in this session because WebFetch hit its spend limit, so every authority stays verified=false.

Blind-pass findings (before reading GPT-6 Sol):

- **O1** (problematic; C-030): Non-compete end date cannot narrow any 'to the present' request during discovery; the record shows post-period conduct matters
- **O2** (arguable; C-018, C-019): RFP 41 must be labeled a contention interrogatory and objected to as premature; Rule 33(a)(2) governs interrogatories, not RFPs
- **O3** (arguable; C-024, C-025): The RFPs' silence on ESI form is required to be flagged as a defect, but Rule 34 makes form optional
- **O4** (arguable; C-002): Uniform post-2017 cutoff ignores Greenleaf's need for pre-JV records to prove independent development
- **O5** (arguable; C-032, C-044): C-032 requires RFP numbers for 'each issue', while C-044 requires cross-cutting issues that have no RFP numbers
- **O6** (arguable; C-047): Memo must mention the July–September 2023 wind-down period even though no objectionable request turns on it

## Coverage and limits

Blind pass: Read in full: task.json (instructions and all 47 criteria), plaintiffs-first-rfps (all 46 RFPs, definitions, instructions), kerrigan-discovery-strategy.eml, case-management-order, litigation-hold-memo, stipulated-protective-order. JV Agreement: read the recitals, definitions, Arts. VI–IX, and Arts. XI–XII, and searched the rest. Dissolution Agreement: searched for dates, wind-down, non-compete survival (§6.1), Exhibit B royalty start, Background IP, and competitor names, but did not read it in full. The Sterling Ark credit agreement and the Ridgepoint engagement letter mentioned in the email are not in the record. Legal propositions were checked against my own knowledge of FRCP 26/33/34 and FRE 502. Two CourtListener searches on contention-style RFPs found nothing useful, so no case law was verified. The generic system prompt and judge prompt were not opened.

Reconciliation: Reread all 47 criteria and the instructions. Reread the strategy email in full and the RFP instructions and definitions, and grepped the record for RFPs 15, 19, 28, 36, 40, and 41. Checked the facts behind each Sol and blind finding: Helix and the counterclaim in the hold memo, form of production, ESI and 502 provisions in the CMO and protective order, non-compete and royalty dates, and trial and fact-discovery dates. The first pass had read the RFPs, email, CMO, hold memo, and protective order in full, with targeted reading of the JV and Dissolution Agreements. WebFetch of the FRCP text failed on a spend limit, so no authority is verified. The Sterling Ark credit agreement and the Ridgepoint engagement letter are not in the record.
