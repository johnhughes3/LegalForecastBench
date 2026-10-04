# GPT-6 Luna (xhigh): Draft Federal Complaint for Breach of Contract and Fiduciary Duty — Placement Agent Dispute

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-federal-complaint-drafting/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 44 of 50 criteria; GPT-5.5 passed 43 of 50 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [federal-complaint.docx](output/federal-complaint.docx) ([read as Markdown](output/federal-complaint.docx.md))
- [filing-issues-memo.docx](output/filing-issues-memo.docx) ([read as Markdown](output/filing-issues-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001: LLC citizenship alleged via member citizenship, not state of formation | **Fail** | **Fail** |
| [C-002](#c-002) | ISSUE_001: Complaint cites or reflects Carden v. Arkoma LLC citizenship rule | Pass | Pass |
| [C-003](#c-003) | Diversity jurisdiction: Graydon citizenship properly alleged | Pass | Pass |
| [C-004](#c-004) | Diversity jurisdiction: Amount in controversy exceeds $75,000 | Pass | Pass |
| [C-005](#c-005) | ISSUE_002: Forum selection clause cited for venue and personal jurisdiction | Pass | Pass |
| [C-006](#c-006) | Venue: Northern District of Texas alleged under 28 U.S.C. § 1391 | Pass | Pass |
| [C-007](#c-007) | Personal jurisdiction: Minimum contacts alleged in addition to forum selection clause | Pass | **Fail** |
| [C-008](#c-008) | ISSUE_003: Fiduciary duty claim grounded in PAA Section 8.1 express acknowledgment | Pass | Pass |
| [C-009](#c-009) | ISSUE_003: Fiduciary duty claim also alleges common law agency-based fiduciary relationship | Pass | Pass |
| [C-010](#c-010) | ISSUE_004: Complaint addresses Graydon Capital Solutions as related entity | Pass | Pass |
| [C-011](#c-011) | ISSUE_004: Issues memo flags separate-entity defense and recommends strategy | Pass | Pass |
| [C-012](#c-012) | ISSUE_005: Fraud claim states who, what, when, where, how per Rule 9(b) | Pass | Pass |
| [C-013](#c-013) | ISSUE_005: Fraud count references Fed. R. Civ. P. 9(b) heightened standard | Pass | Pass |
| [C-014](#c-014) | ISSUE_006: Economic loss rule addressed in issues memo | Pass | Pass |
| [C-015](#c-015) | ISSUE_006: Fraud claim framed to survive economic loss rule | Pass | Pass |
| [C-016](#c-016) | ISSUE_007: Unjust enrichment pled as alternative claim | Pass | Pass |
| [C-017](#c-017) | ISSUE_007: Unjust enrichment targets Graydon Capital Solutions' Ridgecrest fees | Pass | Pass |
| [C-018](#c-018) | ISSUE_008: Discovery rule alleged for fraud statute of limitations | **Fail** | **Fail** |
| [C-019](#c-019) | ISSUE_008: All claims within applicable statutes of limitations | Pass | Pass |
| [C-020](#c-020) | ISSUE_009: Issues memo flags speculative damages risk for carried interest | **Fail** | **Fail** |
| [C-021](#c-021) | ISSUE_009: Complaint includes non-speculative damages theories | Pass | Pass |
| [C-022](#c-022) | ISSUE_010: Trevor Graydon named as individual defendant | Pass | Pass |
| [C-023](#c-023) | ISSUE_010: Personal liability theory articulated for Trevor Graydon | Pass | Pass |
| [C-024](#c-024) | ISSUE_011: Non-solicitation 12-month tail provision alleged | Pass | Pass |
| [C-025](#c-025) | ISSUE_012: Complaint requests injunctive relief | Pass | Pass |
| [C-026](#c-026) | ISSUE_012: Irreparable harm alleged to support injunctive relief | **Fail** | **Fail** |
| [C-027](#c-027) | DISTRACTOR_001: Texas governing law treated as straightforward | Pass | Pass |
| [C-028](#c-028) | DISTRACTOR_002: FINRA registration not treated as jurisdictional obstacle | Pass | Pass |
| [C-029](#c-029) | DISTRACTOR_003: Retainer payment calculation is clean | Pass | Pass |
| [C-030](#c-030) | DISTRACTOR_004: Fund III hard cap not treated as material issue | Pass | Pass |
| [C-031](#c-031) | Breach of contract count: All material breaches alleged | Pass | Pass |
| [C-032](#c-032) | All three diverted investors identified with specifics | Pass | Pass |
| [C-033](#c-033) | Graydon-Ridgecrest Capital Introduction Agreement alleged with date | Pass | Pass |
| [C-034](#c-034) | Discovery narrative: April 2024 Chicago conference alleged | **Fail** | **Fail** |
| [C-035](#c-035) | Complaint includes four separate counts | Pass | Pass |
| [C-036](#c-036) | Complaint includes proper caption for Northern District of Texas | Pass | Pass |
| [C-037](#c-037) | Complaint includes jury demand | Pass | Pass |
| [C-038](#c-038) | Complaint includes attorney signature block | Pass | Pass |
| [C-039](#c-039) | Prayer for relief includes compensatory damages | Pass | Pass |
| [C-040](#c-040) | Prayer for relief includes disgorgement | Pass | Pass |
| [C-041](#c-041) | Prayer for relief includes punitive damages | Pass | Pass |
| [C-042](#c-042) | Prayer for relief includes attorneys' fees and costs | Pass | Pass |
| [C-043](#c-043) | Factual allegations organized chronologically | Pass | Pass |
| [C-044](#c-044) | PAA execution date correctly alleged as January 18, 2023 | Pass | Pass |
| [C-045](#c-045) | Demand letter and response letter referenced in factual allegations | Pass | Pass |
| [C-046](#c-046) | Issues memo identifies Graydon's anticipated defenses from response letter | Pass | Pass |
| [C-047](#c-047) | Issues memo produced as separate deliverable | Pass | Pass |
| [C-048](#c-048) | Milestone misrepresentation specifics: Actual vs. reported figures | **Fail** | **Fail** |
| [C-049](#c-049) | Exclusivity period correctly alleged as 18 months | Pass | Pass |
| [C-050](#c-050) | Complaint properly references documentary sources | Pass | Pass |

## Judge reasoning

### C-001

ISSUE_001: LLC citizenship alleged via member citizenship, not state of formation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L21))

- **Sonnet 4.6: Fail.** The complaint does acknowledge that LLC citizenship is determined by member citizenship (paragraph 4 states 'For diversity purposes, an LLC is a citizen of every state of citizenship of each of its members'), but it does not actually identify the specific members (Marcus J. Harwell and Elena Rosario-Vega) or their citizenship. Instead, it leaves a bracketed placeholder: '[INSERT VERIFIED COMPLETE MEMBER LIST AND CITIZENSHIP, INCLUDING ANY ENTITY MEMBERS AND THEIR OWNERSHIP CHAINS]'. The criterion requires that the complaint identify the specific members by name and allege their citizenship (Marcus J. Harwell as a citizen of Texas and Elena Rosario-Vega as a citizen of Texas). Since the complaint fails to include these specific member-level citizenship allegations, it does not satisfy the criterion.
- **GPT-5.5: Fail.** The complaint correctly notes that an LLC’s citizenship is determined by the citizenship of all its members, but it does not actually identify Westlake’s members or allege that Marcus J. Harwell and Elena Rosario-Vega are Texas citizens. Instead, it leaves a placeholder to insert the member list and citizenship. Therefore it does not satisfy the required member-level citizenship allegation.

### C-002

ISSUE_001: Complaint cites or reflects Carden v. Arkoma LLC citizenship rule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L29))

- **Sonnet 4.6: Pass.** Both documents clearly reflect awareness of the LLC citizenship rule. The complaint (paragraph 4) states 'For diversity purposes, an LLC is a citizen of every state of citizenship of each of its members' and similarly for GCS in paragraph 6. The filing-issues memo explicitly states 'Under 28 U.S.C. § 1332, it is a citizen of every state of citizenship of each member, tracing citizenship through any entity members' and criticizes the intake memo's incorrect reliance on formation state and principal place of business. While Carden v. Arkoma is not cited by name, the rule it established is clearly and correctly articulated in both documents.
- **GPT-5.5: Pass.** The complaint and issues memo expressly state that an LLC is a citizen of every state of citizenship of its members and that formation state/principal office are insufficient for LLC diversity citizenship allegations. This reflects the Carden/LLC-member citizenship rule even without citing the case by name.

### C-003

Diversity jurisdiction: Graydon citizenship properly alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L38))

- **Sonnet 4.6: Pass.** Paragraph 5 of the complaint states: 'Defendant Graydon Strategic Advisors Inc. is a New York corporation with its principal office at 450 Park Avenue, 22nd Floor, New York, New York 10022.' This alleges both the state of incorporation (New York) and the principal place of business (New York), satisfying the criterion for properly alleging Graydon Strategic's citizenship for diversity purposes.
- **GPT-5.5: Pass.** The complaint alleges Graydon Strategic Advisors Inc. is a New York corporation and gives its principal office in New York, New York. This sufficiently supplies New York incorporation and New York principal business location for the criterion.

### C-004

Diversity jurisdiction: Amount in controversy exceeds $75,000 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L46))

- **Sonnet 4.6: Pass.** Paragraph 8 explicitly states 'the amount in controversy exceeds $75,000, exclusive of interest and costs,' directly tracking the statutory language of 28 U.S.C. § 1332(a)(1). Paragraph 9 reiterates this and references the $750,000 in milestone payments alone. Paragraph 35 and the Prayer for Relief both reference total estimated damages of approximately $14,730,000, which far exceeds the $75,000 threshold. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The complaint expressly alleges in the jurisdiction section that the amount in controversy exceeds $75,000, exclusive of interest and costs, and further references recovery of three $250,000 payments plus estimated damages of approximately $14,730,000, which clearly exceeds the threshold.

### C-005

ISSUE_002: Forum selection clause cited for venue and personal jurisdiction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L54))

- **Sonnet 4.6: Pass.** The complaint explicitly references the PAA's Section 12.2 forum selection clause in both the personal jurisdiction section (paragraph 10) and the venue section (paragraph 12). Paragraph 10 states that the Court may exercise personal jurisdiction over Graydon Strategic because it agreed in Section 12.2 of the PAA to the exclusive jurisdiction of state or federal courts located in Dallas County, Texas. Paragraph 12 states that venue is proper and also consistent with Section 12.2 of the PAA. Both the venue and personal jurisdiction allegations cite the forum selection clause.
- **GPT-5.5: Pass.** The complaint expressly cites PAA Section 12.2 in the jurisdiction allegations as supporting personal jurisdiction over Graydon Strategic because it agreed to exclusive jurisdiction in state or federal courts located in Dallas County, Texas. It also references Section 12.2 in the venue allegations, stating venue as to Graydon Strategic is consistent with that forum-selection clause.

### C-006

Venue: Northern District of Texas alleged under 28 U.S.C. § 1391 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L62))

- **Sonnet 4.6: Pass.** Paragraph 12 of the complaint explicitly alleges venue is proper in the Northern District of Texas under 28 U.S.C. § 1391(b)(2), stating that 'a substantial part of the events or omissions giving rise to the claims occurred in Dallas County.' It also references the PAA's forum-selection clause (Section 12.2) as additional support. The complaint is filed in the Northern District of Texas, Dallas Division, as shown in the caption. Both the statutory basis (§ 1391(b)(2)) and the contractual forum-selection clause are cited.
- **GPT-5.5: Pass.** The complaint is captioned for the Northern District of Texas, Dallas Division, and specifically alleges venue is proper there under 28 U.S.C. § 1391(b)(2) because substantial events occurred in Dallas County. It also references the contractual forum-selection clause.

### C-007

Personal jurisdiction: Minimum contacts alleged in addition to forum selection clause ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L70))

- **Sonnet 4.6: Pass.** The complaint addresses personal jurisdiction in paragraphs 10-12. Paragraph 10 relies on the forum-selection clause in Section 12.2 of the PAA for Graydon Strategic. Paragraph 11 then separately alleges minimum contacts for Trevor and GCS, noting they purposefully directed conduct toward Texas (approving certifications directed to Westlake in Dallas, using relationships developed through the Texas-based Westlake engagement). Paragraph 12 addresses venue and notes the forum-selection clause does not establish personal jurisdiction over non-signatories. However, for Graydon Strategic itself, the complaint relies primarily on the forum-selection clause (paragraph 10) without separately alleging minimum contacts such as soliciting a Texas client, sending personnel to Dallas, or receiving payments from Texas accounts. The minimum contacts allegations in paragraph 11 are explicitly limited to Trevor and GCS, not Graydon Strategic. The criterion requires minimum contacts alleged IN ADDITION TO the forum selection clause. Since the complaint does allege both bases—forum selection clause (para 10) for Graydon Strategic and minimum contacts (para 11) for Trevor/GCS—and the overall personal jurisdiction section covers both theories across the defendants collectively, this satisfies the criterion. The complaint does allege minimum contacts (directing conduct to Texas, using Texas-based relationships, payments received in Dallas) alongside the forum selection clause, even if the minimum contacts are more explicitly tied to Trevor and GCS rather than Graydon Strategic directly.
- **GPT-5.5: Fail.** The complaint alleges personal jurisdiction over Graydon Strategic based on the PAA forum-selection clause, and separately alleges minimum contacts for Trevor and GCS. But it does not clearly assert personal jurisdiction over Graydon Strategic based on Graydon Strategic’s own minimum contacts with Texas in addition to the forum-selection clause, such as soliciting/performing services for a Texas client or receiving Texas payments. Thus, as to Graydon, personal jurisdiction is asserted essentially on only one required basis.

### C-008

ISSUE_003: Fiduciary duty claim grounded in PAA Section 8.1 express acknowledgment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L78))

- **Sonnet 4.6: Pass.** Count II (Breach of Fiduciary Duty) at paragraph 44 explicitly references PAA Section 8.1 and states that 'Graydon Strategic acted as Westlake's placement agent and acknowledged in Section 8.1 of the PAA that it owed fiduciary duties of loyalty, candor, and good faith, including full disclosure of conflicts and refraining from undisclosed self-dealing.' This directly satisfies the criterion requiring reference to PAA Section 8.1 and the express contractual acknowledgment of fiduciary duties.
- **GPT-5.5: Pass.** The breach of fiduciary duty count expressly references PAA Section 8.1 and alleges that Graydon Strategic, as Westlake's placement agent, acknowledged fiduciary duties of loyalty, candor, and good faith, including disclosure of conflicts and refraining from self-dealing.

### C-009

ISSUE_003: Fiduciary duty claim also alleges common law agency-based fiduciary relationship ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L86))

- **Sonnet 4.6: Pass.** Paragraph 44 states: 'Graydon Strategic acted as Westlake's placement agent and acknowledged in Section 8.1 of the PAA that it owed fiduciary duties of loyalty, candor, and good faith, including full disclosure of conflicts and refraining from undisclosed self-dealing. The agency relationship also supports duties under applicable law.' The phrase 'The agency relationship also supports duties under applicable law' does reference a common law agency-based fiduciary relationship independent of the contractual provision. This is a brief but present allegation that the principal-agent relationship itself gives rise to fiduciary duties under applicable law, in addition to the Section 8.1 contractual basis. The criterion requires that the complaint allege Graydon owed fiduciary duties under common law regardless of the PAA, and this sentence does that, albeit concisely.
- **GPT-5.5: Pass.** The fiduciary duty count is not grounded solely in Section 8.1. Paragraph 44 alleges Graydon acted as Westlake's placement agent and separately states that the agency relationship supports fiduciary duties under applicable law, which pleads an independent common-law agency-based fiduciary relationship in addition to the contractual acknowledgment.

### C-010

ISSUE_004: Complaint addresses Graydon Capital Solutions as related entity ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L94))

- **Sonnet 4.6: Pass.** The complaint names Graydon Capital Solutions LLC as a defendant (paragraph 6, caption), and Count IV (Unjust Enrichment) is specifically directed against GCS and Trevor Graydon. More importantly, the complaint alleges that GCS acted as an agent or instrumentality of Graydon Strategic and Trevor Graydon: paragraph 20 alleges the Ridgecrest agreement 'identifies GCS as an affiliate of Graydon Strategic and states that GCS could use affiliate personnel and relationships to perform capital-introduction services,' and that Trevor signed for GCS as its sole manager and directed its performance. Paragraph 21 alleges GCS used the Graydon affiliate network and Fund III investor relationships. Paragraph 46 alleges Trevor personally executed the GCS-Ridgecrest agreement and participated in the diversion. The complaint thus satisfies criterion (a) by naming GCS as a defendant and criterion (c) by alleging GCS acted as an agent/instrumentality of Graydon Strategic and Trevor Graydon, using affiliate personnel and relationships from the Graydon Strategic engagement to perform the competing capital-introduction services.
- **GPT-5.5: Pass.** The complaint expressly names Graydon Capital Solutions LLC as an additional defendant in the caption and party allegations, and asserts an unjust-enrichment claim against it based on the Ridgecrest fee arrangement. This satisfies the criterion even without an alter-ego or agency theory.

### C-011

ISSUE_004: Issues memo flags separate-entity defense and recommends strategy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L102))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the separate-entity defense in Section 2.C, noting that 'GCS was not a party to the PAA' and distinguishing 'Graydon's contractual responsibility for covered conduct from a direct contractual claim against GCS.' It also discusses alter-ego theory, stating 'Avoid an alter-ego claim absent evidence satisfying the applicable standard' and noting that Graydon's response letter asserts 'a separate EIN, operating agreement, bank accounts, revenue, and operations.' The memo further discusses the need to obtain organizational, accounting, employment, and bank records before pleading commingling or sham facts. It also references agency theory in Section 2.A regarding § 7.4 covering acts by Graydon's 'officers, directors, employees, and agents even when taken on behalf of an affiliate.' The memo identifies GCS's non-signatory status as a litigation risk and discusses the legal theories needed to overcome the separate-entity defense, including alter ego and agency/affiliate theories.
- **GPT-5.5: Pass.** The memo expressly flags that GCS is not a PAA signatory and that Graydon/GCS separateness is disputed, noting Graydon’s assertions of separate EIN, operating agreement, bank accounts, revenue, and operations. It recommends distinguishing Graydon’s contractual responsibility from direct claims against GCS, warns not to plead commingling or sham facts without substantiation, and advises avoiding an alter-ego claim absent evidence. It also discusses agency/closely related theories for non-signatories. This satisfies the separate-entity litigation-risk criterion.

### C-012

ISSUE_005: Fraud claim states who, what, when, where, how per Rule 9(b) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L110))

- **Sonnet 4.6: Pass.** Count III (Fraud/Fraudulent Misrepresentation) in paragraphs 48-53 provides detailed particularity. WHO: Nathaniel Pruitt prepared and signed each report; Trevor Graydon approved each certification. WHAT: Each report falsely represented that pipeline items (soft circles, verbal indications, prospects, and even investors who had already committed to Cascadia Fund IV) satisfied the PAA's milestone thresholds defined as binding written Capital Commitments evidenced by fully executed subscription agreements. Specific dollar figures are given for each certification ($50.5M, $101.5M, $152M). WHEN: May 8, 2023; September 9, 2023; March 8, 2024. WHERE/HOW: Reports were delivered to Westlake's identified principals in Dallas, Texas, and received there. The payments induced ($250,000 on specific dates) are also specified. This satisfies Rule 9(b)'s who, what, when, where, and how requirements with the level of particularity described in the criterion.
- **GPT-5.5: Pass.** The fraud count pleads Rule 9(b) particulars: it identifies Nathaniel Pruitt as preparer/signatory and Trevor Graydon as approver; specifies the challenged milestone reports and claimed amounts ($50.5M, $101.5M, $152M) and why they were false under the PAA; gives the submission dates in May, September, and March; and alleges the reports/certifications were delivered to Westlake and received/reliance occurred in Dallas. This is more than general notice pleading.

### C-013

ISSUE_005: Fraud count references Fed. R. Civ. P. 9(b) heightened standard ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L118))

- **Sonnet 4.6: Pass.** Count III (Fraud/Fraudulent Misrepresentation) in paragraph 53 explicitly addresses the Rule 9(b) particularity requirement by stating: 'The fraud allegations identify the content and dates of each statement, the report preparer and signatory, Trevor's approval, the recipients and Dallas receipt, the contractual meaning that made the statements misleading, the payments induced, and the facts supporting knowledge and intent.' This directly maps to the 'who, what, when, where, and how' framework required by Rule 9(b). Additionally, the fraud count throughout paragraphs 49-53 provides specific dates (May 8, 2023; September 9, 2023; March 8, 2024), identifies who made the statements (Pruitt as preparer/signatory, Trevor as approver), specifies what was misrepresented (pipeline items counted as Capital Commitments), where they were received (Dallas, Texas), and how they were false (PAA definition of Capital Commitment vs. what was reported). The drafter was clearly aware of and addressed the Rule 9(b) standard, even if not explicitly citing the rule by number.
- **GPT-5.5: Pass.** The complaint does not cite Fed. R. Civ. P. 9(b) by name, but the fraud count is expressly structured to meet the heightened pleading framework. It identifies the dates and contents of the alleged misrepresentations, who prepared/signed/approved them, where they were received, why they were false or misleading, reliance, damages, and facts supporting knowledge and intent. Paragraph 53 specifically summarizes these particulars in a who/what/when/where/how format.

### C-014

ISSUE_006: Economic loss rule addressed in issues memo ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L126))

- **Sonnet 4.6: Pass.** Section 2.E of the memo explicitly addresses the economic loss rule: 'Expect a Texas economic-loss-rule challenge because the milestone statements and reporting duties arise in a contract.' It then discusses the exceptions and how to counter the defense by pleading specific affirmative certifications as knowing/reckless false statements and distinguishing intentional self-dealing/concealment and the agent's independent duty of loyalty from mere failure to perform. It also notes the fiduciary claim has a stronger independent-duty rationale. While Formosa Plastics is not cited, the concept is clearly addressed as a risk and the applicable exceptions are discussed.
- **GPT-5.5: Pass.** The memo expressly flags a Texas economic-loss-rule challenge to the fraud claim because the reporting duties arise from contract, and it discusses ways around it by pleading affirmative misrepresentations intended to induce separate payments and distinguishing self-dealing/concealment and an independent fiduciary duty of loyalty from mere contract nonperformance.

### C-015

ISSUE_006: Fraud claim framed to survive economic loss rule ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L134))

- **Sonnet 4.6: Pass.** Count III frames the fraud claim around the milestone certifications as affirmative misrepresentations made with knowledge of falsity and intent to induce payment, and ties them to the undisclosed Ridgecrest arrangement (a concealed conflict). The complaint alleges that Graydon Strategic and Trevor knowingly or recklessly misrepresented the pipeline as satisfying contractual thresholds while simultaneously concealing a competing arrangement — framing the fraud as independent tortious conduct (fraudulent misrepresentation and concealment) rather than merely a breach of contractual representations. The fiduciary duty context is also invoked (Section 8.1 acknowledgment, concealed self-dealing), and Count II separately pleads breach of fiduciary duty. The fraud count thus has multiple potential hooks to survive the economic loss rule: (1) fraud in the context of a fiduciary relationship, (2) affirmative fraudulent misrepresentation as an independent tort, and (3) concealment of a material conflict. These framings go beyond simply recasting a contract breach as fraud, providing the necessary distinction under Texas law.
- **GPT-5.5: Pass.** The fraud count is not limited to a bare allegation that Graydon breached contractual warranties. It incorporates allegations that Graydon was acting as Westlake’s placement agent/fiduciary, owed duties of loyalty/candor, concealed an undisclosed conflicted Ridgecrest arrangement and diversions, and made misleading milestone certifications to induce separate payments. Although the fraud theory overlaps with the contract claim and could have been framed more explicitly as fiduciary-context fraud or fraudulent nondisclosure, the complaint includes enough fiduciary/conflict and concealment framing to distinguish it from a purely contractual representation claim under the stated criterion.

### C-016

ISSUE_007: Unjust enrichment pled as alternative claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L142))

- **Sonnet 4.6: Pass.** Count IV (Unjust Enrichment) is expressly pled 'IN THE ALTERNATIVE' in its heading and the body states 'This count is pleaded in the alternative to the extent no express contract governs Westlake's claim to the benefit obtained by GCS and/or Trevor.' It also notes that neither GCS nor Trevor is a party to the PAA, acknowledging the express-contract limitation. This satisfies the criterion.
- **GPT-5.5: Pass.** The unjust enrichment count is expressly labeled “IN THE ALTERNATIVE” and states it is pleaded “to the extent no express contract governs” the claim, while noting GCS and Trevor are not parties to the PAA. This acknowledges the express-contract limitation required by the criterion.

### C-017

ISSUE_007: Unjust enrichment targets Graydon Capital Solutions' Ridgecrest fees ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L150))

- **Sonnet 4.6: Pass.** Count IV (Unjust Enrichment) specifically targets GCS and Trevor Graydon for the approximately $750,000 in capital introduction fees derived from the 1.5% fee on the $50 million in Cascadia Fund IV commitments by the three diverted Fund III prospects. The count explicitly states it is pleaded in the alternative to the extent no express contract governs the claim, noting that neither GCS nor Trevor is a party to the PAA. The Prayer for Relief also separately requests restitution/disgorgement of approximately $750,000 in Ridgecrest-related fees. This satisfies the criterion.
- **GPT-5.5: Pass.** The unjust enrichment count is directed at Graydon Capital Solutions LLC (and Trevor if he retained benefits), expressly references the Ridgecrest agreement, and seeks restitution/disgorgement of approximately $750,000 in fees calculated as 1.5% of the $50 million Cascadia commitments. It also pleads this in the alternative because GCS/Trevor are not parties to the PAA, distinguishing it from PAA payments.

### C-018

ISSUE_008: Discovery rule alleged for fraud statute of limitations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L158))

- **Sonnet 4.6: Fail.** The complaint in paragraph 32 alleges that Westlake did not know of the Ridgecrest arrangement or the diversion until April 17, 2024, when its Director of Investor Relations spoke with Northshore's Chief Investment Officer at an industry conference in Chicago. It also states that before that disclosure, Graydon's reports did not reveal the arrangement or the diversions. However, the complaint does not explicitly invoke the 'discovery rule' by name or expressly state that the fraud statute of limitations runs from the date of discovery rather than the date of commission. The criterion requires both: (1) alleging when Westlake first learned of the fraud (which is present), and (2) invoking the discovery rule to establish that the limitations period runs from discovery, not commission (which is absent). The complaint mentions the discovery date but does not invoke the discovery rule as a legal doctrine to toll or start the limitations period.
- **GPT-5.5: Fail.** The complaint alleges Westlake first learned of the concealed conflict/diversions in April 2024 when its Director of Investor Relations spoke with Northshore's CIO at a Chicago conference, but it does not expressly invoke the discovery rule or plead that the fraud statute of limitations runs from the date of discovery rather than commission.

### C-019

ISSUE_008: All claims within applicable statutes of limitations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L166))

- **Sonnet 4.6: Pass.** Section 5.C of the memo explicitly addresses statutes of limitations: 'The four-year limitations periods for contract and fraud claims appear to leave the 2023--2024 conduct timely as of August 2024, but confirm governing law/accrual for each count. Plead concealment/discovery facts without suggesting the June demand tolled limitations absent a tolling agreement.' This directly analyzes the timeliness of the claims under four-year limitations periods, confirms the 2023-2024 conduct is timely as of the August 2024 filing date, and notes the discovery rule (concealment/discovery facts). The memo satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly addresses limitations, noting that four-year limitations periods for contract and fraud claims leave the 2023–2024 conduct timely as of the August 2024 filing and referencing accrual for each count. Although it does not separately spell out breach of fiduciary duty, it does analyze timeliness and indicates the claims are within limitations.

### C-020

ISSUE_009: Issues memo flags speculative damages risk for carried interest ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L174))

- **Sonnet 4.6: Fail.** The memo does flag the carried interest claim as vulnerable. In Section 5A, it states: 'Carried interest (\ $7.5 million): Most vulnerable category. Millhaven's narrative references a full projection of about \ $16.9 million and a discounted \ $7.5 million but does not provide the calculation/workpapers in the source set. Obtain model inputs, actual carry waterfall, hurdle calculation, gross/net IRR assumptions, investment timing, realizations, risk adjustments, and expert report. Separate carry recipient from Westlake. Consider pleading only "according to proof" until expert support exists; avoid presenting an estimate as an earned or certain amount.' The memo recommends grounding the claim in expert methodology. However, the criterion specifically requires that the memo note the risk of a Daubert challenge or motion to dismiss, and that it reference the speculative nature tied to projected fund performance derived from historical Fund I and Fund II returns (average 18.5% net IRR). The memo does not mention Daubert, does not reference Fund I/Fund II historical returns or the 18.5% net IRR figure, and does not specifically call out the motion-to-dismiss risk. It does flag the claim as speculative and recommends expert support, but falls short of the specific elements required by the criterion (Daubert challenge risk and grounding in historical performance data from prior funds).
- **GPT-5.5: Fail.** The memo does flag the $7.5 million carried-interest claim as the “most vulnerable category,” notes it is based on projections lacking workpapers, and recommends obtaining model inputs, IRR assumptions, risk adjustments, and an expert report. However, it does not specifically identify that the projection is derived from historical Fund I/Fund II returns or the 18.5% net IRR assumption, and it does not mention the risk of a Daubert challenge or motion to dismiss. Because the criterion expressly requires those points, the output falls short.

### C-021

ISSUE_009: Complaint includes non-speculative damages theories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L182))

- **Sonnet 4.6: Pass.** The complaint includes the $750,000 in milestone payments (paragraphs 3, 27-30, 35, 52) and the lost management fee estimate of 2.0% × $50M × 5 years (paragraph 36, which explicitly states 'applies a 2.0% annual fee to $50 million over a five-year investment period'). It also mentions the $280,000 in retainers (paragraph 35: '$280,000 in retainers paid during November 2023 through June 2024') and consequential fundraising/replacement-agent costs (paragraph 35). The carried interest is also included but is clearly labeled as uncertain and requiring expert support. The complaint thus includes concrete, non-speculative damages categories alongside the carried interest claim, satisfying the criterion's requirement that at least the milestone disgorgement and lost management fee figures appear.
- **GPT-5.5: Pass.** The complaint includes concrete damages categories beyond carried interest: it expressly pleads $750,000 in challenged milestone payments, $280,000 in retainers, consequential fundraising/replacement/remediation costs, and a lost management-fee theory calculated as 2.0% annually on $50 million over five years, which equals $5,000,000. Although the $5,000,000 and $1,200,000 consequential figures are not separately spelled out, the required milestone amount and lost-management-fee calculation appear, and the complaint does not rely solely on carried interest.

### C-022

ISSUE_010: Trevor Graydon named as individual defendant ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L190))

- **Sonnet 4.6: Pass.** Trevor Graydon is explicitly named as an individual defendant in the caption ('TREVOR GRAYDON, Defendants.'), described in paragraph 7 as an individual defendant, and named in multiple counts (Count II for breach of fiduciary duty, Count III for fraud, Count IV for unjust enrichment). The complaint alleges his personal participation including executing the GCS-Ridgecrest agreement, attending investor meetings, personally recommending Cascadia to Northshore's principal, and approving milestone certifications. He is also identified as sole manager and member of GCS.
- **GPT-5.5: Pass.** The complaint expressly names Trevor Graydon as an individual defendant in the caption and party allegations, and asserts claims against him individually based on alleged personal participation, including his role as GCS’s sole manager, execution/orchestration of the Ridgecrest arrangement, approval of certifications, and direct investor contacts. Although it does not allege a personal guarantee under the PAA, the criterion’s core requirement that Trevor be named individually is satisfied.

### C-023

ISSUE_010: Personal liability theory articulated for Trevor Graydon ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L198))

- **Sonnet 4.6: Pass.** The complaint articulates multiple theories for Trevor Graydon's individual liability. In Count II (¶46), it explicitly states that 'Trevor personally executed the GCS-Ridgecrest agreement, attended at least one GPPERS meeting at which Cascadia was presented, personally recommended Cascadia to Northshore's principal, and approved each of the three milestone reports. Westlake seeks to hold Trevor liable for his own actionable conduct and participation, not merely because he held corporate office.' This is a clear articulation of the participation theory. In Count III (¶¶49-51), Trevor is named as a defendant for fraud based on his personal approval of each certification. Count IV pleads unjust enrichment against Trevor to the extent he personally received or retained benefits. The complaint thus articulates the participation/personal conduct theory, fraud in his individual capacity, and unjust enrichment as bases for individual liability.
- **GPT-5.5: Pass.** The complaint expressly articulates theories for Trevor Graydon’s individual liability, including liability for his own participation in alleged fiduciary breaches and tortious conduct, approval of allegedly fraudulent milestone certifications, personal involvement in diverting investors, and unjust enrichment to the extent he received or retained benefits. It states Westlake seeks to hold him liable for his own actionable conduct, not merely his corporate role.

### C-024

ISSUE_011: Non-solicitation 12-month tail provision alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L206))

- **Sonnet 4.6: Pass.** Paragraph 41 explicitly references the PAA's non-solicitation restriction continuing for twelve months after expiration, through July 18, 2025, and states that Graydon Strategic's covered conduct during the term breached Section 7.4. The Prayer for Relief (paragraph E) also seeks injunctive relief to enforce the PAA's surviving non-solicitation obligations through their lawful expiration. This satisfies the criterion requiring mention of the 12-month tail provision and its use as a basis for ongoing/continuing breach and injunctive relief.
- **GPT-5.5: Pass.** The complaint expressly references PAA Section 7.4’s non-solicitation restriction, states that it continues for twelve months after expiration through July 18, 2025, alleges Graydon’s covered conduct breached Section 7.4, and seeks injunctive relief for any continuing prohibited activity within that tail period.

### C-025

ISSUE_012: Complaint requests injunctive relief ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L214))

- **Sonnet 4.6: Pass.** The prayer for relief in section E explicitly requests 'appropriate declaratory and permanent injunctive relief to enforce the PAA's surviving non-solicitation obligations through their lawful expiration.' This directly addresses injunctive relief to enforce the non-solicitation provision and prevent Graydon from continuing to divert Fund III investor prospects to competing funds. The criterion is satisfied.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “permanent injunctive relief to enforce the PAA’s surviving non-solicitation obligations” and ties it to ongoing or imminent violations. The complaint also alleges continuing prohibited solicitation/diversion activity under the non-solicitation provision. This satisfies the criterion requiring injunctive relief to enforce the non-solicitation provision and prevent further diversion.

### C-026

ISSUE_012: Irreparable harm alleged to support injunctive relief ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L222))

- **Sonnet 4.6: Fail.** The complaint requests injunctive relief in the Prayer for Relief (paragraph E) to enforce the PAA's surviving non-solicitation obligations, but it does not allege irreparable harm anywhere in the complaint. There is no allegation that monetary damages would be inadequate, no allegation of loss of investor relationships that cannot be compensated monetarily, no allegation of reputational harm, and no allegation about the unique nature of institutional investor relationships. The injunctive relief request is conditioned on 'proof of an ongoing or imminent violation' but contains no allegation of irreparable harm as required to support injunctive relief. The criterion requires that the complaint allege irreparable harm going beyond mere monetary damages, and the complaint fails to do so.
- **GPT-5.5: Fail.** The complaint requests permanent injunctive relief to enforce the non-solicitation obligations and references possible ongoing prohibited activity, but it does not allege irreparable harm beyond monetary damages. It does not plead that investor relationships are unique, that reputational harm is occurring, that ongoing harm is unquantifiable, or similar facts supporting injunctive relief.

### C-027

DISTRACTOR_001: Texas governing law treated as straightforward ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L230))

- **Sonnet 4.6: Pass.** The complaint simply states that Section 12.1 selects Texas law and proceeds to plead all claims under Texas law without raising any conflict-of-laws concerns. The filing-issues memo does mention 'choice-of-law analysis' once in passing (in the context of the economic-loss rule discussion: 'Research the applicable Texas authorities and choice-of-law analysis before filing'), but this is a brief, generic research reminder rather than flagging the Texas governing law clause itself as a significant vulnerability or genuine conflict-of-laws issue requiring analysis. Neither document treats the PAA's Texas choice-of-law provision as a meaningful risk or problem. The criterion is satisfied: Texas law is treated as straightforwardly applicable per the PAA.
- **GPT-5.5: Pass.** The complaint straightforwardly alleges Texas law applies under PAA Section 12.1 and pleads Texas-law claims. The issues memo notes some related research points, including Texas authorities and a separate New York choice-of-law/arbitration clause in the GCS–Ridgecrest agreement, but it does not treat the PAA’s Texas governing-law clause as a significant conflict-of-laws vulnerability or as a risk that could defeat the claims.

### C-028

DISTRACTOR_002: FINRA registration not treated as jurisdictional obstacle ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L239))

- **Sonnet 4.6: Pass.** The complaint mentions Graydon Strategic's FINRA registration (CRD No. 298714) only as a factual detail in paragraph 5 describing the defendant. Neither the complaint nor the issues memo treats FINRA registration as creating a mandatory arbitration obligation or as a jurisdictional bar to filing in federal court. The issues memo explicitly states 'FINRA status or securities-law references do not independently confer federal jurisdiction' but does not suggest FINRA arbitration is required or that it bars the federal court filing. The documents correctly treat FINRA registration as background information only.
- **GPT-5.5: Pass.** The complaint mentions Graydon Strategic's FINRA registration and CRD number only as a factual party detail. It does not state or imply that FINRA registration creates a mandatory arbitration obligation or bars federal jurisdiction. The issues memo likewise does not flag FINRA arbitration as a significant risk; it only notes that FINRA status does not create federal-question jurisdiction, which is proper.

### C-029

DISTRACTOR_003: Retainer payment calculation is clean ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L248))

- **Sonnet 4.6: Pass.** The complaint mentions '$280,000 in retainers paid during November 2023 through June 2024' as part of the damages estimate in paragraph 35. This is presented as a straightforward figure without any dispute about timing of payments or amounts owed. The $280,000 figure is consistent with 8 months × $35,000 = $280,000. The complaint does not fabricate any dispute about retainer payment timing or create issues where none exist. It simply includes the retainer amount as one component of damages.
- **GPT-5.5: Pass.** The complaint treats the retainer component as a straightforward damages item, stating $280,000 in retainers paid during November 2023 through June 2024, which corresponds to 8 months at $35,000. It does not fabricate any dispute about whether retainers were timely paid or whether the amounts were owed.

### C-030

DISTRACTOR_004: Fund III hard cap not treated as material issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L256))

- **Sonnet 4.6: Pass.** The $225M hard cap is mentioned once in paragraph 13 of the complaint as background context: 'Fund III, a Delaware limited partnership formed in November 2022, targeted $200 million in commitments, with a $225 million hard cap.' It is not treated as a material issue affecting claims, defenses, or damages anywhere in the complaint or the filing-issues memo. The memo does not mention the hard cap at all. This satisfies the criterion that the hard cap is either not mentioned or mentioned only as background context without being treated as a material issue.
- **GPT-5.5: Pass.** The output mentions the $225 million hard cap only once as background context in the factual allegations describing Fund III's target size. It does not treat the hard cap as creating any legal issue, defense, damages limitation, or complication.

### C-031

Breach of contract count: All material breaches alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L265))

- **Sonnet 4.6: Pass.** Count I (Breach of Contract) against Graydon Strategic explicitly alleges breaches of: (1) Section 5.1 — exclusivity/sole and exclusive placement agent obligation ('failing to use its exclusive engagement for Fund III's benefit'); (2) Section 7.4 — non-solicitation ('directing or permitting its personnel to divert Fund III prospects to Cascadia Fund IV'); (3) Section 7.2 — conflicts disclosure ('failing to disclose the Ridgecrest arrangement and resulting conflict'); and (4) Sections 5.2 and 5.3 — reporting obligations ('submitting inaccurate milestone certifications' and 'failing to report material competitive developments and investor status changes'). All four required breach theories are present in paragraph 40.
- **GPT-5.5: Pass.** The breach of contract count expressly alleges breaches of the relevant PAA provisions and theories: failure to use the exclusive engagement for Fund III’s benefit, violation of Section 7.4 through diversion/non-solicitation conduct, failure to disclose the Ridgecrest conflict under Section 7.2, and reporting/certification breaches including failure to report material developments and submission of inaccurate milestone certifications. Thus, none of the required breach theories are omitted.

### C-032

All three diverted investors identified with specifics ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L273))

- **Sonnet 4.6: Pass.** The complaint identifies all three diverted investors with correct names, amounts, and timing: (1) GPPERS — $25M committed to Cascadia Fund IV in January 2024 (para 23); (2) Harborview Endowment Fund — $15M committed in December 2023 (para 24); (3) Northshore Family Office LLC — $10M committed in February 2024 (para 25). Total is stated as $50M (paras 1, 26). All specifics match the criterion requirements.
- **GPT-5.5: Pass.** The complaint identifies all three diverted investors by name and provides the required commitment amounts and timing: GPPERS committed $25M to Cascadia in January 2024, Harborview committed $15M in December 2023, and Northshore committed $10M in February 2024, totaling $50M.

### C-033

Graydon-Ridgecrest Capital Introduction Agreement alleged with date ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L281))

- **Sonnet 4.6: Pass.** Paragraph 20 of the complaint explicitly states: 'On August 1, 2023---during the PAA term---GCS entered a Capital Introduction Agreement with Ridgecrest.' It also states this was during the PAA term (the exclusivity period) and paragraph 22 states that 'Neither Graydon Strategic nor Trevor disclosed the Ridgecrest arrangement to Westlake during the PAA term.' All three required elements are present: the agreement's existence, the August 1, 2023 date, execution during the PAA exclusivity period, and non-disclosure to Westlake.
- **GPT-5.5: Pass.** The complaint alleges that on August 1, 2023, GCS entered into a Capital Introduction Agreement with Ridgecrest, during the PAA term/exclusive engagement, and further alleges that neither Graydon Strategic nor Trevor disclosed the Ridgecrest arrangement to Westlake.

### C-034

Discovery narrative: April 2024 Chicago conference alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L289))

- **Sonnet 4.6: Fail.** The complaint does allege discovery in April 2024 at an industry conference in Chicago (paragraph 32), and it mentions Northshore's CIO disclosing the Cascadia commitment and Graydon's role. However, the criterion specifically requires that the discovery be attributed to 'Rosario-Vega' — the complaint instead attributes the discovery to Westlake's 'Director of Investor Relations' without naming that person as Rosario-Vega. The criterion requires the complaint to allege that 'Rosario-Vega discovered the diversion scheme' specifically. Since the named individual Rosario-Vega is not mentioned anywhere in the complaint, the criterion is not satisfied.
- **GPT-5.5: Fail.** The complaint alleges an April 17, 2024 discovery at an industry conference in Chicago where Northshore’s CIO disclosed Northshore’s Cascadia commitment and Graydon’s role. However, it does not identify Rosario-Vega as the person who discovered the scheme; it only refers to Westlake’s Director of Investor Relations. Because the criterion specifically requires Rosario-Vega to be alleged, this is not fully satisfied.

### C-035

Complaint includes four separate counts ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L297))

- **Sonnet 4.6: Pass.** The complaint contains four separately titled counts: COUNT I — BREACH OF CONTRACT, COUNT II — BREACH OF FIDUCIARY DUTY, COUNT III — FRAUD / FRAUDULENT MISREPRESENTATION, and COUNT IV — UNJUST ENRICHMENT (IN THE ALTERNATIVE). All four required counts are present.
- **GPT-5.5: Pass.** The complaint includes four separate titled counts: Count I—Breach of Contract, Count II—Breach of Fiduciary Duty, Count III—Fraud / Fraudulent Misrepresentation, and Count IV—Unjust Enrichment.

### C-036

Complaint includes proper caption for Northern District of Texas ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L305))

- **Sonnet 4.6: Pass.** The complaint caption clearly identifies the court as 'UNITED STATES DISTRICT COURT, NORTHERN DISTRICT OF TEXAS, DALLAS DIVISION' and lists 'WESTLAKE CAPITAL PARTNERS LLC' as Plaintiff and 'GRAYDON STRATEGIC ADVISORS INC.' as a Defendant. All required elements are present and correct.
- **GPT-5.5: Pass.** The complaint caption identifies the court as the United States District Court for the Northern District of Texas, Dallas Division, and lists Westlake Capital Partners LLC as Plaintiff and Graydon Strategic Advisors Inc. as a Defendant.

### C-037

Complaint includes jury demand ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L313))

- **Sonnet 4.6: Pass.** The complaint includes an explicit jury demand section titled 'JURY DEMAND' which states: 'Pursuant to Federal Rule of Civil Procedure 38, Plaintiff demands a trial by jury on all issues so triable.' Additionally, the caption block includes 'JURY TRIAL DEMANDED.'
- **GPT-5.5: Pass.** The complaint expressly includes 'JURY TRIAL DEMANDED' in the caption and a separate 'JURY DEMAND' section invoking Federal Rule of Civil Procedure 38 and demanding a trial by jury on all triable issues.

### C-038

Complaint includes attorney signature block ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L321))

- **Sonnet 4.6: Pass.** The complaint includes a signature block at the end identifying the firm as KENDRICK, LYLE & STRAUSS LLP at 1700 Pacific Avenue, Suite 3200, Dallas, Texas 75201, with Catherine M. Aldridge listed as the signing attorney. This satisfies the criterion requiring the correct firm name, address, and at least one of the named attorneys.
- **GPT-5.5: Pass.** The complaint includes a filing counsel signature block for Kendrick, Lyle & Strauss LLP, lists the required address at 1700 Pacific Avenue, Suite 3200, Dallas, Texas 75201, and identifies Catherine M. Aldridge as attorney for Plaintiff.

### C-039

Prayer for relief includes compensatory damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L329))

- **Sonnet 4.6: Pass.** The prayer for relief in section B explicitly states: 'award compensatory and actual damages according to proof, presently estimated at approximately $14,730,000, subject to evidentiary support, legal recoverability, offsets, and no double recovery.' This directly references compensatory damages with the specific figure of approximately $14,730,000, satisfying the criterion.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “compensatory and actual damages” and references a present estimate of approximately $14,730,000.

### C-040

Prayer for relief includes disgorgement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L337))

- **Sonnet 4.6: Pass.** The prayer for relief explicitly requests disgorgement in section C: 'order restitution or disgorgement of GCS's and/or Trevor's proven, traceable Ridgecrest-related fees or benefits, presently estimated at approximately $750,000.' Additionally, section B requests compensatory damages including the $750,000 in milestone payments. The complaint clearly requests disgorgement of the Ridgecrest fees earned by GCS, satisfying the criterion.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “restitution or disgorgement” of GCS’s and/or Trevor’s Ridgecrest-related fees or benefits, estimated at approximately $750,000. This satisfies the criterion.

### C-041

Prayer for relief includes punitive damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L345))

- **Sonnet 4.6: Pass.** The prayer for relief in section D explicitly requests 'exemplary damages against the responsible Defendant(s) only to the extent authorized by Texas law and supported by the required proof.' Exemplary damages are synonymous with punitive damages, so this satisfies the criterion.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “exemplary damages” against responsible defendants to the extent authorized by Texas law, which satisfies the requirement to include punitive/exemplary damages.

### C-042

Prayer for relief includes attorneys' fees and costs ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L353))

- **Sonnet 4.6: Pass.** The prayer for relief in section G explicitly states: 'award reasonable attorneys' fees and costs under the PAA and applicable law.' This clearly requests both attorneys' fees and costs.
- **GPT-5.5: Pass.** The Prayer for Relief expressly requests an award of reasonable attorneys' fees and costs under the PAA and applicable law.

### C-043

Factual allegations organized chronologically ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L361))

- **Sonnet 4.6: Pass.** The factual allegations section (Section IV) is organized into labeled subsections that follow a clear chronological progression: (A) the PAA formation in January 2023 and milestone requirements; (B) the undisclosed Ridgecrest arrangement beginning August 2023; (C) the three investor diversions occurring from late 2023 through early 2024; (D) the milestone certifications and payments in May 2023, September 2023, and March 2024; (E) discovery of the conflict in April 2024, demand in June 2024, and refusal; and (F) damages. The narrative starts with Fund III formation and PAA execution, proceeds through the fundraising timeline, covers the diversions and certifications in temporal order, and ends with discovery and demand. This is a generally chronological structure.
- **GPT-5.5: Pass.** The factual allegations begin with Fund III and the January 2023 PAA, then cover the Ridgecrest arrangement, investor diversions, milestone certifications/payments, discovery, demand, refusal, and damages. Although some sections are grouped thematically and the milestone-certification section includes earlier May 2023 events after later diversion allegations, the narrative has a coherent overall chronological structure and does not jump randomly between periods.

### C-044

PAA execution date correctly alleged as January 18, 2023 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L369))

- **Sonnet 4.6: Pass.** Paragraph 14 of the complaint states: 'On January 18, 2023, Westlake and Graydon Strategic executed the PAA.' This matches the criterion exactly.
- **GPT-5.5: Pass.** The complaint expressly alleges in paragraph 14 that Westlake and Graydon Strategic executed the PAA on January 18, 2023.

### C-045

Demand letter and response letter referenced in factual allegations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L377))

- **Sonnet 4.6: Pass.** Paragraph 34 of the complaint explicitly states: 'On June 3, 2024, Westlake, through counsel, sent Graydon Strategic a written demand identifying the alleged breaches and requesting an accounting, return of milestone payments, disgorgement of conflicted fees, cessation of competing solicitations, and preservation of records. On June 18, 2024, Graydon Strategic's counsel denied liability and rejected the demands.' This satisfies the criterion requiring reference to both the June 3, 2024 demand letter and the June 18, 2024 response denying all allegations.
- **GPT-5.5: Pass.** The complaint includes factual allegations that Westlake sent a written demand through counsel on June 3, 2024, and that Graydon Strategic's counsel responded on June 18, 2024 by denying liability and rejecting the demands.

### C-046

Issues memo identifies Graydon's anticipated defenses from response letter ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L385))

- **Sonnet 4.6: Pass.** The memo addresses both anticipated defenses from Graydon's June 18 response letter. Regarding GCS as a separate legal entity: Section 2.C explicitly discusses Graydon's response letter asserting 'a separate EIN, operating agreement, bank accounts, revenue, and operations' and cautions against pleading commingling facts without substantiation. Regarding investors making independent decisions: Section 2.E states 'Graydon's response denies that it improperly influenced investors and argues that sophisticated institutions independently chose Cascadia' and then addresses how to counter this defense by focusing on Graydon's competing introductions, concealed fee conflict, and knowing misreporting of diverted investors. Both defenses from the response letter are identified and discussed.
- **GPT-5.5: Pass.** The memo expressly discusses defenses from Graydon's June 18 response letter, including Graydon's position that GCS is a separate entity with separate EIN, operating agreement, bank accounts, revenue, and operations, and Graydon's argument that sophisticated investors independently chose Cascadia rather than being improperly influenced.

### C-047

Issues memo produced as separate deliverable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L393))

- **Sonnet 4.6: Pass.** The agent produced a standalone filing issues memorandum (filing-issues-memo.docx) addressed from an associate to a partner, clearly separate from any complaint draft. It identifies legal risks (diversity jurisdiction gaps, personal jurisdiction issues, standing problems), strategic considerations (whether to file in federal or state court, which defendants to name), and potential vulnerabilities (Rule 9(b) pleading issues, economic loss rule, damages uncertainty, privilege concerns). This satisfies the criterion of a separate issues memo identifying legal risks, strategic considerations, and potential vulnerabilities for the supervising partner.
- **GPT-5.5: Pass.** The output is expressly a separate “FILING-ISSUES MEMORANDUM” for the supervising partner, not embedded within a complaint, and it identifies jurisdictional risks, standing issues, personal jurisdiction, damages vulnerabilities, pleading concerns, strategic recommendations, and a pre-filing checklist.

### C-048

Milestone misrepresentation specifics: Actual vs. reported figures ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L401))

- **Sonnet 4.6: Fail.** The complaint alleges that milestones were inflated by including non-binding pipeline items, and it provides the reported figures for each certification (e.g., $50.5M reported for May 2023, $101.5M for September 2023, $152M for March 2024). However, the criterion requires the complaint to allege specific actual-vs.-reported discrepancies: (1) May 2023: actual ~$42M vs. reported ~$50.5M, overstated by ~$8M; (2) September 2023: actual ~$87.5M vs. reported ~$101.5M, overstated by ~$12.5M; (3) March 2024: actual ~$112M vs. reported ~$152M, overstated by ~$38M. The complaint does state that $35M was closed as of May 2023 and $87.5M was closed as of March 2024, but it does not provide the specific 'actual' pipeline figures (~$42M, ~$87.5M for September, ~$112M for March) that would show the precise overstatement amounts. For the September 2023 certification, the complaint notes $87.5M closed by October 2023 but doesn't clearly state the actual qualifying figure as of August 31, 2023 was ~$87.5M. For March 2024, it mentions $87.5M closed but doesn't state the actual qualifying figure was ~$112M. The complaint does not provide the specific actual figures needed to calculate the overstatement amounts for at least two milestones as required by the criterion.
- **GPT-5.5: Fail.** The complaint provides reported milestone figures and some breakdowns, but it does not allege the specified actual-vs.-reported discrepancies for at least two milestones: May actual ~$42M vs reported ~$50M, September actual ~$87.5M vs reported ~$100M, and March actual ~$112M vs reported ~$150M. Instead, it mostly contrasts reported pipeline figures with closed commitments such as $35M or $87.5M, which do not match the criterion’s required actual figures/overstatements.

### C-049

Exclusivity period correctly alleged as 18 months ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L409))

- **Sonnet 4.6: Pass.** Paragraph 14 states: 'Graydon Strategic was appointed as Westlake's sole and exclusive placement agent for Fund III for an eighteen-month term ending July 18, 2024, absent earlier termination or written extension.' This correctly alleges the 18-month exclusivity period running from January 18, 2023 through July 18, 2024.
- **GPT-5.5: Pass.** The complaint expressly alleges that the January 18, 2023 PAA appointed Graydon Strategic as Westlake's sole and exclusive placement agent for an eighteen-month term ending July 18, 2024.

### C-050

Complaint properly references documentary sources ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-federal-complaint-drafting/task.json#L417))

- **Sonnet 4.6: Pass.** The complaint references: (1) the Placement Agent Agreement (PAA) extensively throughout, including specific sections; (2) Graydon's monthly activity reports (described as 'activity reports' and 'milestone certifications' with specific dates in paragraphs 16, 22, 23, 24, 25, 27, 28, 29, 30, 31); (3) the Graydon-Ridgecrest Capital Introduction Agreement (paragraphs 20-22, 55-56). The Millhaven investigation findings are not referenced anywhere in the complaint. Three of the four required document categories are referenced, which meets the threshold of 'at least three of these four document categories.'
- **GPT-5.5: Pass.** The complaint references and describes at least three required document categories: the Placement Agent Agreement, Graydon's monthly activity reports/reports and certifications, and the GCS/Graydon-Ridgecrest Capital Introduction Agreement. It does not appear to reference Millhaven investigation findings, but three of four is sufficient under the criterion.
