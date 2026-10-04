# Claude Opus 5.5 (low): Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 49 of 52 criteria; GPT-5.5 passed 49 of 52 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [obligation-extraction-memo.docx](output/obligation-extraction-memo.docx) ([read as Markdown](output/obligation-extraction-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001: Identifies conflicting Relevant Period for financial records | Pass | Pass |
| [C-002](#c-002) | ISSUE_001: Flags financial records date discrepancy as requiring DOJ clarification | Pass | **Fail** |
| [C-003](#c-003) | ISSUE_001: Notes broader date range creates additional preservation burden | Pass | Pass |
| [C-004](#c-004) | ISSUE_002: Identifies contradictory HCP communication scope | **Fail** | Pass |
| [C-005](#c-005) | ISSUE_002: Explains dramatically different scope implications of HCP readings | **Fail** | Pass |
| [C-006](#c-006) | ISSUE_002: Recommends defaulting to broader HCP interpretation | Pass | Pass |
| [C-007](#c-007) | ISSUE_003: Flags January 15, 2025 destruction of approximately 4.2 million records from the 2019–2021 period | Pass | Pass |
| [C-008](#c-008) | ISSUE_003: Notes destruction occurred approximately 7 weeks before Preservation Notice | Pass | Pass |
| [C-009](#c-009) | ISSUE_003: Addresses potential spoliation risk from pre-notice destruction | Pass | Pass |
| [C-010](#c-010) | ISSUE_003: Recommends forensic investigation of destroyed records | Pass | Pass |
| [C-011](#c-011) | ISSUE_004: Identifies email migration data loss affecting approximately 340,000 pre-September 2021 emails | Pass | Pass |
| [C-012](#c-012) | ISSUE_004: Identifies that 8 of 23 named custodians are affected by email migration loss | Pass | Pass |
| [C-013](#c-013) | ISSUE_004: Notes affected emails fall within Relevant Period | Pass | Pass |
| [C-014](#c-014) | ISSUE_004: Recommends preserving decommissioned servers at offsite storage | Pass | Pass |
| [C-015](#c-015) | ISSUE_005: Flags 'related compounds' as potential massive scope expansion | Pass | Pass |
| [C-016](#c-016) | ISSUE_005: Recommends seeking clarification on 'related compounds' | Pass | Pass |
| [C-017](#c-017) | ISSUE_006: Identifies compressed third-party vendor notification deadline | Pass | Pass |
| [C-018](#c-018) | ISSUE_006: Flags need for immediate/parallel action on third-party notices | Pass | Pass |
| [C-019](#c-019) | ISSUE_007: Identifies Exhibit B category count discrepancy (34 vs. 36) | Pass | Pass |
| [C-020](#c-020) | ISSUE_007: Recommends clarification on missing categories | Pass | Pass |
| [C-021](#c-021) | ISSUE_008: Identifies privacy concerns with forensic imaging of personal devices | Pass | Pass |
| [C-022](#c-022) | ISSUE_008: Distinguishes forensic imaging from logical extraction | Pass | Pass |
| [C-023](#c-023) | ISSUE_009: Identifies inconsistent use of 'documents,' 'records,' 'materials' | Pass | Pass |
| [C-024](#c-024) | ISSUE_009: Recommends applying broadest definition uniformly | Pass | Pass |
| [C-025](#c-025) | ISSUE_010: Assesses backup tape preservation burden and proportionality | **Fail** | **Fail** |
| [C-026](#c-026) | ISSUE_010: Notes backup tapes may be sole source due to migration loss | Pass | **Fail** |
| [C-027](#c-027) | ISSUE_011a: Identifies Linden & Pruitt conflict due to prior representation of Dr. Osei | Pass | Pass |
| [C-028](#c-028) | ISSUE_011b: Identifies that privileged Linden & Pruitt communications may be swept into preservation scope | Pass | Pass |
| [C-029](#c-029) | ISSUE_011: Recommends protocol for handling privileged materials | Pass | Pass |
| [C-030](#c-030) | ISSUE_012: Identifies RPAF as separate legal entity with preservation implications | Pass | Pass |
| [C-031](#c-031) | ISSUE_012: Notes RPAF board independence and coordination requirement | Pass | Pass |
| [C-032](#c-032) | Correctly states the 14-day confirmation deadline as March 17, 2025 | Pass | Pass |
| [C-033](#c-033) | Correctly states the 10-day third-party vendor deadline as March 13, 2025 | Pass | Pass |
| [C-034](#c-034) | Correctly states the 21-day mobile device imaging deadline as March 24, 2025 | Pass | Pass |
| [C-035](#c-035) | Identifies the Relevant Period as January 1, 2019 to March 3, 2025 | Pass | Pass |
| [C-036](#c-036) | Identifies ESI preservation requirement including specific platforms | Pass | Pass |
| [C-037](#c-037) | Identifies backup tape rotation suspension obligation | Pass | Pass |
| [C-038](#c-038) | Identifies paper records preservation obligation at Durham headquarters | Pass | Pass |
| [C-039](#c-039) | Identifies paper records preservation obligation at Atlanta field office | Pass | Pass |
| [C-040](#c-040) | Names the three specific third-party vendors requiring preservation notices | Pass | Pass |
| [C-041](#c-041) | Identifies the nine subject-matter areas or 34 document categories | Pass | Pass |
| [C-042](#c-042) | Identifies conflict between retention policy and preservation obligations | Pass | Pass |
| [C-043](#c-043) | Memo includes a prioritized action item list organized by urgency | Pass | Pass |
| [C-044](#c-044) | Action items include correct sequencing of the three deadlines | Pass | Pass |
| [C-045](#c-045) | References Grand Jury No. 24-GJ-0387 | Pass | Pass |
| [C-046](#c-046) | References Anti-Kickback Statute and/or False Claims Act | Pass | Pass |
| [C-047](#c-047) | Identifies AUSA Brendan K. Faulkner as the DOJ contact for confirmation | Pass | Pass |
| [C-048](#c-048) | Cites specific paragraph numbers from the Preservation Notice | Pass | Pass |
| [C-049](#c-049) | Identifies the obligation to preserve files and data for 23 named custodians | Pass | Pass |
| [C-050](#c-050) | Names at least 5 key custodians from the 23 named custodians | Pass | Pass |
| [C-051](#c-051) | Addresses the 5 non-employee HCP consultants in Exhibit D | Pass | Pass |
| [C-052](#c-052) | Identifies Velcara (ridgenostat) as the drug at issue | Pass | Pass |

## Judge reasoning

### C-001

ISSUE_001: Identifies conflicting Relevant Period for financial records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L22))

- **Sonnet 4.6: Pass.** The memo explicitly identifies this conflict in Section IV.C (Time Periods table), noting that the General Relevant Period runs from Jan. 1, 2019 to Mar. 3, 2025 (¶12; Exh. A), while financial records, accounting entries, GL, budgets and payment records for KOL, RPAF and Velcara extend back to Jan. 1, 2017 (¶47). This two-year discrepancy is further discussed in Section VIII.H ('Financial Records Back to January 1, 2017 (¶47)') and in the conflict table in Section VII. The memo clearly identifies the inconsistency between ¶12 and ¶47.
- **GPT-5.5: Pass.** The memo expressly states that the general Relevant Period under ¶12 is Jan. 1, 2019–Mar. 3, 2025, while ¶47 extends financial records, accounting entries, GL, budgets, and payment records back to Jan. 1, 2017. It also discusses applying the 2017 start date to financial records and notes related drafting inconsistencies. This satisfies the criterion.

### C-002

ISSUE_001: Flags financial records date discrepancy as requiring DOJ clarification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L30))

- **Sonnet 4.6: Pass.** The memo addresses the financial records date discrepancy in multiple places. In Section VI (Reconciling the Notice's Category Numbering), it identifies the ¶47 cross-reference issue and recommends: 'Also consider preserving 2017–2018 Velcara pre-launch marketing materials (Area 7 in Exhibit B) until DOJ clarifies in writing.' In Section XI (Points to Clarify With DOJ), item 18 explicitly lists 'The 36 vs. 34 categories, and whether HCP communications (¶¶23–24) are the two unnumbered categories. The ¶47 reference to "Area 7"' as a point to raise with DOJ in writing before March 13. The memo thus recommends seeking written clarification from DOJ regarding the ¶47 numbering discrepancy, which relates to the financial records date range conflict.
- **GPT-5.5: Fail.** The memo identifies the general relevant period as Jan. 1, 2019 and financial records as Jan. 1, 2017, and it recommends preserving the broader financial period. It also recommends asking DOJ to clarify ¶47’s Area 7/category inconsistency, but it does not specifically recommend DOJ clarification of a conflicting Jan. 1, 2017 vs. Jan. 1, 2019 date range for financial records.

### C-003

ISSUE_001: Notes broader date range creates additional preservation burden ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L38))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the extended January 1, 2017 start date for financial records in multiple places. Section II.C (Time Periods) notes the 2017–present period for financial records and flags that it 'Includes archival and backup copies of 2017–2018 financial data. See risk in Part VIII.H.' Section VIII.H ('Financial Records Back to January 1, 2017 (¶47)') directly discusses the additional preservation burden: it notes that 2017 records would have become eligible for destruction during 2024 and early 2025, that earlier destruction cycles (Apr., Jul., Oct. 2024) may have removed 2017 data, and that the CFO and Controller must confirm what 2017–2018 data still exists. The memo also flags the ¶47 cross-reference error (Area 7 vs. Categories 24–27) and recommends applying the 2017 start date to all financial and payment records. The practical impact of the broader date range is thus clearly discussed in connection with both the destruction event and the need to verify surviving data.
- **GPT-5.5: Pass.** The memo expressly discusses the January 1, 2017 extended date range for financial records and its practical preservation impact. It notes that 2017–2018 financial data may be at risk under the 7-year retention schedule, that earlier 2024 destruction cycles may have removed 2017 data, and recommends confirming what data exists in SAP, archives, and backups and suspending disposition. This directly identifies the broader date range as creating additional preservation burdens in light of destruction/retention issues.

### C-004

ISSUE_002: Identifies contradictory HCP communication scope ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L46))

- **Sonnet 4.6: Fail.** The memo does identify both Paragraph 23 (broad HCP communications about Velcara) and Paragraph 24 (Exhibit D HCPs specifically) as separate obligations. In Section V.C, C4 covers '¶23 — all HCP communications about Velcara, with any HCP, in any context' and notes it is 'Very broad: effectively all field and MSL communications. No matching Exhibit B category.' C5 covers '¶24 — communications with the Exhibit D HCPs on every channel.' The memo also notes in VIII.C that '¶23 covers communications with all HCPs about Velcara' affecting potentially 2,092+ employees. However, the criterion specifically asks whether the memo identifies these two paragraphs as *contradictory* — i.e., that ¶23 requires preservation of all HCP communications while ¶24 limits scope to 5 named HCPs. The memo treats them as separate, additive obligations rather than identifying a contradiction between them. It does not frame ¶24 as limiting or contradicting ¶23. The memo notes ¶23 is broad and ¶24 covers the Exhibit D HCPs specifically, but does not characterize this as a contradiction or tension between the two paragraphs. In Part XI, item 22 asks DOJ to clarify 'the practical scope of ¶23' but frames it as an ambiguity about breadth, not a contradiction with ¶24. The criterion requires identification of the contradiction between these two paragraphs, which the memo does not explicitly do.
- **GPT-5.5: Pass.** The memo expressly identifies Paragraph 23 as very broad, requiring preservation of all HCP communications about Velcara with any HCP, and separately identifies Paragraph 24 as covering communications with the Exhibit D HCPs on all channels. It also flags the practical scope of ¶23 for clarification. Although it does not use the word “contradiction” in that exact section, it recognizes the broad-vs-Exhibit-D HCP scope issue required by the criterion.

### C-005

ISSUE_002: Explains dramatically different scope implications of HCP readings ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L54))

- **Sonnet 4.6: Fail.** The memo discusses the broad reading of paragraph 23 (all HCP communications about Velcara by all employees) versus the narrow reading (the 5 named Exhibit D HCPs), and notes in Part VIII.C that 'because ¶23 covers communications with all HCPs about Velcara, the un-migrated mailboxes of the other ~2,092 employees (field sales, MSLs) are also potentially in scope, not only the named custodians' mailboxes.' It also notes in Part XI item 22 that the practical scope of ¶23 covers 'all HCP communications about Velcara, by all employees' and proposes a framework. However, the memo does not explicitly quantify or estimate the dramatically different document volumes between the two interpretations—it does not say something like 'the broader reading could encompass millions of additional documents compared to the narrow reading of just the 5 Exhibit D HCPs.' The criterion specifically requires explaining that the broader reading 'could encompass potentially millions of additional documents compared to the narrow reading.' While the memo acknowledges the breadth and scope difference, it does not discuss the difference in document volume or scope magnitude between the two interpretations in the way the criterion requires.
- **GPT-5.5: Pass.** The memo distinguishes the broad ¶23 reading (all HCP communications about Velcara by field/MSL and other employees, requiring org-wide preservation and implicating ~2,092 additional mailboxes) from the narrower Exhibit D/five-HCP focus. It also ties the broad HCP reading to large data volumes, including millions of emails/call records and destroyed records, making clear the broader interpretation could encompass vastly more documents than the five named HCPs.

### C-006

ISSUE_002: Recommends defaulting to broader HCP interpretation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L62))

- **Sonnet 4.6: Pass.** The memo explicitly recommends defaulting to the broader interpretation of HCP communications. In Section IV.D, it states 'Recommendation: read every paragraph as covering all five defined terms. Do not rely on any narrower reading without written DOJ agreement.' In Section V.C (C4), it notes that ¶23 covers 'all HCP communications about Velcara, with any HCP, in any context' and flags it as 'Very broad: effectively all field and MSL communications.' In Section VIII.C, it notes that '¶23 covers communications with all HCPs about Velcara, the un-migrated mailboxes of the other ~2,092 employees (field sales, MSLs) are also potentially in scope.' In Section X (action plan item 1), it recommends an 'org-wide retention hold' rather than limiting to named custodians, explicitly citing ¶23's breadth. In Section XI (point 22), it proposes clarifying with DOJ the 'practical scope of ¶23 (all HCP communications about Velcara, by all employees)' and suggests 'preserve org-wide in place, collect later by custodian.' The memo also connects this broader interpretation to spoliation risk avoidance through its repeated warnings about §1519 exposure and adverse inference risk from post-Notice losses. The memo clearly recommends the broader HCP interpretation as the default pending DOJ clarification, and connects it to spoliation risk avoidance.
- **GPT-5.5: Pass.** The memo expressly treats ¶23 as covering communications with all HCPs about Velcara, recommends applying the broader reading/preserving org-wide in place while seeking DOJ clarification, and warns that narrowing or delay risks data loss, §1519 exposure, and adverse-inference/spoliation-type consequences.

### C-007

ISSUE_003: Flags January 15, 2025 destruction of approximately 4.2 million records from the 2019–2021 period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L70))

- **Sonnet 4.6: Pass.** The memo extensively flags the January 15, 2025 destruction of approximately 4.2 million records from the 2019–2021 period as a critical issue. It is mentioned in the Executive Summary, the Deadline Calendar, Section VIII.A (dedicated section titled 'The January 15, 2025 Destruction Cycle'), and multiple other places throughout the document. The memo details the breakdown of the ~4.2 million records, identifies which Notice categories they implicate, notes procedural defects, and recommends immediate action including stopping tape rotation and preparing a ¶46 disclosure to DOJ.
- **GPT-5.5: Pass.** The memo repeatedly identifies the January 15, 2025 destruction of approximately 4.2 million records dated 2019–2021 as a serious/critical issue, including in the Executive Summary and a dedicated gap-analysis section.

### C-008

ISSUE_003: Notes destruction occurred approximately 7 weeks before Preservation Notice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L78))

- **Sonnet 4.6: Pass.** The memo explicitly states in the Executive Summary: 'About 4.2 million records were destroyed on January 15, 2025, seven weeks before the Notice.' This directly identifies the timing relationship between the destruction and the preservation notice, satisfying the criterion.
- **GPT-5.5: Pass.** The memo explicitly states that approximately 4.2 million records were destroyed on January 15, 2025, “seven weeks before the Notice,” satisfying the required timing relationship.

### C-009

ISSUE_003: Addresses potential spoliation risk from pre-notice destruction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L86))

- **Sonnet 4.6: Pass.** Section VIII.A explicitly addresses the spoliation risk from pre-notice destruction. It notes that the grand jury number (24-GJ-) indicates a 2024 investigation, and that under Policy §6.1, the duty to preserve arises on 'reasonable notice,' which includes whistleblower or hotline reports, qui tam activity, subpoenas to third parties such as the Exhibit D HCPs, or industry enforcement trends. It further states that destroying records the company's own Policy required it to keep weakens any 'routine, good-faith destruction' defense. The memo also recommends a privileged internal inquiry into 'the earliest date Ridgeline had notice of a potential investigation' and lists open factual question #25 about the earliest date Ridgeline had any notice of a government inquiry. This directly addresses the anticipation-of-litigation / spoliation risk even though no formal litigation hold was in place at the time of the January 15 destruction.
- **GPT-5.5: Pass.** The memo addresses the pre-notice destruction risk by noting the January 15 destruction occurred before the DOJ Notice and was not automatically unlawful on that basis, but that Ridgeline’s preservation duty may have arisen earlier if it had “reasonable notice” of an investigation or litigation, including through hotline reports, subpoenas, qui tam activity, or similar indicators. It also recommends investigating the earliest date Ridgeline had notice and explains that the destruction weakens any routine good-faith destruction defense. This satisfies the anticipation-of-litigation/spoliation-risk criterion, even though the memo does not prominently use the word “spoliation.”

### C-010

ISSUE_003: Recommends forensic investigation of destroyed records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L94))

- **Sonnet 4.6: Pass.** The memo extensively addresses the January 15, 2025 destruction in Section VIII.A and elsewhere. It recommends stopping the tape rotation to potentially recover deleted data, checking whether Salesforce/Veeva source data survives behind the destroyed exports, looking for copies in custodian mailboxes and vendor systems, preserving the destruction record set, and running a privileged internal inquiry into the destruction. It also recommends tape recovery assessment (Action Plan item 11) and explicitly notes that electronic deletions may survive on weekly full backups. These constitute clear recommendations to investigate what was destroyed and attempt recovery.
- **GPT-5.5: Pass.** The memo explicitly analyzes the January 15, 2025 destruction, identifies categories and volumes destroyed, recommends preserving destruction logs/certificates and investigating why records were destroyed, and recommends assessing recovery options including stopping tape rotation, checking backups, Salesforce/Veeva source data, M365/custodian copies, and completing a tape-recovery assessment.

### C-011

ISSUE_004: Identifies email migration data loss affecting approximately 340,000 pre-September 2021 emails ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L102))

- **Sonnet 4.6: Pass.** The memo extensively identifies the Ashford Data Solutions email migration error in Section VIII.C, noting that approximately 340,000 emails from January 2019 to September 2021 exist only on six powered-down legacy Exchange servers at Sentinel. This is flagged as a critical preservation issue throughout the document, including in the Executive Summary and the detailed gap analysis.
- **GPT-5.5: Pass.** The memo expressly identifies the 2021 Ashford Data Solutions migration error, explains that archives/.pst stores were skipped, states that about 340,000 emails from Jan. 2019–Sept. 2021 exist only on decommissioned Exchange servers, and treats this as a key preservation/data-loss risk requiring disclosure and remediation.

### C-012

ISSUE_004: Identifies that 8 of 23 named custodians are affected by email migration loss ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L110))

- **Sonnet 4.6: Pass.** The memo explicitly states in Part VIII.C: 'The IT Memo's count of "8 of 23" affected custodians is unreliable.' and 'correct the "8 of 23" / "47,000--52,000 emails" figures before any statement to DOJ.' The executive summary also references '8 of 23' affected custodians. The memo clearly identifies that 8 of the 23 named custodians are reported as affected by the email migration data loss (while also noting this figure is unreliable).
- **GPT-5.5: Pass.** The memo explicitly references the email migration issue and states the IT Memo's count of "8 of 23" affected custodians, including later discussion that the "8 of 23" figure should be corrected before statements to DOJ. Although it questions the reliability of the count, the required number is identified.

### C-013

ISSUE_004: Notes affected emails fall within Relevant Period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L118))

- **Sonnet 4.6: Pass.** The memo explicitly states in Part VIII.C that 'About 340,000 emails from Jan. 2019--Sept. 2021 exist only on six powered-down Dell PowerEdge servers.' The Relevant Period is defined in Part IV.C as 'Jan. 1, 2019 -- Mar. 3, 2025.' The memo also notes these emails fall within Notice categories (e.g., Part VIII.C references ¶23 covering communications with all HCPs about Velcara, and the broader scope of the 2,092 other employees' mailboxes being 'potentially in scope'). The connection between the 340,000 emails' date range (Jan. 2019–Sept. 2021) and the Relevant Period (Jan. 1, 2019–Mar. 3, 2025) is explicitly made, and the memo notes these are responsive to preservation categories (Cats. 33-34, ¶23, etc.).
- **GPT-5.5: Pass.** The memo identifies the migration gap as approximately 340,000 emails from Jan. 2019 to Sept. 2021, states the Relevant Period is Jan. 1, 2019 to Mar. 3, 2025, and treats the un-migrated emails/mailboxes as potentially in scope and requiring preservation because they may include HCP/Velcara communications covered by the Notice. Although it does not use the exact phrase “fall within the Relevant Period” in the migration-gap section, the required connection is made sufficiently.

### C-014

ISSUE_004: Recommends preserving decommissioned servers at offsite storage ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L126))

- **Sonnet 4.6: Pass.** The memo extensively addresses the decommissioned Exchange servers at Sentinel Records Management. In Section VIII.C, it recommends: (i) sending Sentinel a written hold today (no movement, disposal or environmental change; confirm chain of custody and the account is in good standing); (ii) having Greenwell propose a forensic protocol such as write-blocked imaging of each drive with no boot; and (iii) telling DOJ about the protocol before carrying it out. Section G2 of the obligation matrix also requires preserving decommissioned servers in current physical condition with no disposal without written DOJ authorization. The action plan (items 4 and 15) reiterates sending Sentinel a written hold on SM-2247891 and carrying out the DOJ-agreed legacy Exchange server imaging protocol. These recommendations clearly address immediate preservation and steps to prevent further degradation or disposal of the hardware.
- **GPT-5.5: Pass.** The memo expressly identifies the six decommissioned Dell PowerEdge Exchange servers at Sentinel Records Management, recommends sending Sentinel a written hold immediately, prohibiting movement, disposal, or environmental changes, preserving chain of custody, paying storage invoices, keeping storage contracts, and using a forensic protocol such as write-blocked imaging to avoid degradation or alteration. This satisfies the requirement.

### C-015

ISSUE_005: Flags 'related compounds' as potential massive scope expansion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L134))

- **Sonnet 4.6: Pass.** The memo explicitly addresses this in Section IV.B under 'Related compounds (¶31)': 'the Notice extends to "ridgenostat and all related compounds" to the extent they relate to the investigation, and must be construed broadly. The Org Chart identifies four pipeline oncology compounds. Their R&D, medical affairs and HCP-consulting files should be assessed and, when in doubt, preserved.' This directly identifies the scope expansion risk from Paragraph 31 and connects it to the four additional pipeline compounds identified in the Org Chart.
- **GPT-5.5: Pass.** The memo expressly flags Paragraph 31's reference to “ridgenostat and all related compounds,” notes that the Org Chart identifies four pipeline oncology compounds, and states that their R&D, medical affairs, and HCP-consulting files should be assessed/preserved. It also recommends clarifying the scope of ¶31 with DOJ. This satisfies the criterion by identifying the related-compounds scope expansion into the four additional pipeline compounds.

### C-016

ISSUE_005: Recommends seeking clarification on 'related compounds' ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L142))

- **Sonnet 4.6: Pass.** The memo addresses 'related compounds' in Section IV.B, noting that the Notice extends to 'ridgenostat and all related compounds' and recommends preserving R&D, medical affairs and HCP-consulting files for the four pipeline oncology compounds identified in the Org Chart when in doubt. In Section XI (Points to Clarify With DOJ), item 22 explicitly recommends seeking written clarification from DOJ on 'the practical scope of ¶23 (all HCP communications about Velcara, by all employees) and of ¶31 (related compounds)' and proposes a reasonable framework. The memo thus both recommends a conservative initial hold (preserve when in doubt) and recommends seeking written clarification from DOJ on the scope of 'related compounds.'
- **GPT-5.5: Pass.** The memo expressly recommends preserving broadly for related compounds pending clarity (stating ¶31 must be construed broadly and pipeline compounds should be assessed and preserved when in doubt) and includes a written DOJ clarification point on the practical scope of ¶31 related compounds while proposing preservation in place.

### C-017

ISSUE_006: Identifies compressed third-party vendor notification deadline ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L150))

- **Sonnet 4.6: Pass.** The memo explicitly identifies both the March 13, 2025 deadline for third-party vendor preservation notices and the March 17, 2025 deadline for the overall certification. In the deadline calendar (Part III), the March 13 entry states 'Issue written preservation notices to all third-party vendors...instructing them to suspend deletion; then obtain written confirmation from each.' The March 17 entry covers the written certification. Part V.H (Third-Party Notices) labels the deadline as 'Mar. 13' and Part V.K (the certification matrix) shows March 17. The action plan (Part X) also separates these into 'By March 13' and 'By March 17' steps. The memo thus clearly identifies the compressed 10-day vendor notice deadline (March 13) as distinct from and 4 days earlier than the 14-day certification deadline (March 17).
- **GPT-5.5: Pass.** The memo repeatedly identifies the third-party vendor preservation notice deadline as March 13, 2025, and separately identifies the overall ¶45 compliance certification deadline as March 17, 2025. It also notes vendor notices are due before the certification, thereby capturing the compressed timeline and the specific dates required by the criterion.

### C-018

ISSUE_006: Flags need for immediate/parallel action on third-party notices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L158))

- **Sonnet 4.6: Pass.** The memo explicitly flags the March 13 deadline for third-party vendor notices (Section H, items H1-H3, and the Deadline Calendar) and places this on a parallel track with the general hold implementation. The action plan in Section X separates the immediate 24-48 hour actions (implementing M365 holds, suspending tape rotation, etc.) from the March 13 deadline for third-party notices, making clear these must proceed in parallel. Section IX provides a detailed list of all third-party recipients including Veeva, SAP, Concur, and IntegriCall. The memo notes in the deadline calendar that third-party notices are 'Not started' and must be sent by March 13, while the general hold suspension is flagged as 'CRITICAL' and immediate. The action plan step 9 ('By March 13: Send all third-party and RPAF preservation notices') is explicitly separated from the immediate actions, showing parallel tracking. The memo clearly treats these as concurrent obligations rather than sequential ones.
- **GPT-5.5: Pass.** The memo identifies third-party vendor notices as a separate hard deadline before the general March 17 certification, lists Veeva, SAP/Concur, and IntegriCall specifically, marks the task as “Not started,” and includes a dedicated third-party notice workstream due March 13 with confirmations tracked by March 17. This sufficiently flags that vendor notices must proceed on an accelerated/parallel track rather than waiting for completion of the broader hold implementation.

### C-019

ISSUE_007: Identifies Exhibit B category count discrepancy (34 vs. 36) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L166))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the discrepancy in Section VI ('Reconciling the Notice's Category Numbering'), stating: 'Paragraph 19 refers to "thirty-six (36) categories" in nine areas, but Exhibit B lists only 34.' This is also mentioned in the Executive Summary and in Section VIII.I ('The only numerical inconsistencies found are the 36 vs. 34 categories and the IT Memo custodian list.')
- **GPT-5.5: Pass.** The memo explicitly identifies the discrepancy multiple times, including in the Executive Summary and Section VI, stating that Paragraph 19 refers to “thirty-six (36) categories” while Exhibit B lists only 34.

### C-020

ISSUE_007: Recommends clarification on missing categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L174))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the 36 vs. 34 category discrepancy in multiple places. In Section VI, it notes that '¶19 refers to "thirty-six (36) categories" in nine areas, but Exhibit B lists only 34' and identifies the HCP communications paragraphs (¶¶23-24) as probably the two missing/unnumbered categories. It recommends preserving the broader reading and seeking written DOJ clarification. In Section XI (point 18), it lists as a clarification point to raise with DOJ: 'The 36 vs. 34 categories, and whether HCP communications (¶¶23-24) are the two unnumbered categories.' The memo also states in Section I and Section IV.D to 'read every paragraph as covering all five defined terms' and not rely on narrower readings without written DOJ agreement. This satisfies the criterion of recommending clarification on the missing categories and preserving broadly in the interim.
- **GPT-5.5: Pass.** The memo explicitly identifies the discrepancy that paragraph 19 references 36 categories while Exhibit B lists only 34, states that the HCP communications provisions may be the two missing categories, recommends applying/preserving under the broader reading, and includes a written clarification request to DOJ regarding the 36 vs. 34 categories and related numbering issues.

### C-021

ISSUE_008: Identifies privacy concerns with forensic imaging of personal devices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L182))

- **Sonnet 4.6: Pass.** The memo explicitly addresses privacy concerns with forensic imaging of personal devices in multiple places. In Section VII (Conflicts Between the Notice and Internal Policy/Practice), it notes that Policy §4.5 requires 'consent or a court order' for BYOD imaging. In Section VIII.E (Mobile Device Imaging), it discusses that employee personal devices require written consent under Policy §4.5, that individuals facing criminal exposure 'may need separate counsel and may assert Fifth Amendment rights over personal devices,' and that the GC's and CCO's devices require a filter-team protocol for privileged material. In Section F of the Obligation Extraction Matrix, it notes the Policy §4.5 consent/court order requirement. These collectively address employee privacy concerns, the need for consent or court order, and related legal issues with forensic imaging of personal devices.
- **GPT-5.5: Pass.** The memo expressly flags privacy/legal concerns for forensic imaging of employee BYOD/personal devices, stating that full imaging requires employee consent or a court order, recommending written consent and privacy/filtering protocols, and documenting refusals. This satisfies the criterion.

### C-022

ISSUE_008: Distinguishes forensic imaging from logical extraction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L190))

- **Sonnet 4.6: Pass.** The memo explicitly distinguishes forensic imaging from logical extraction in Section F1 of the Mobile Devices obligations matrix: 'Full physical forensic image (bit-for-bit; deleted data, app data, iMessage, WhatsApp, Signal, Telegram, location, browser) of all personal and company devices of all 23 custodians; logical extraction is not enough.' It also discusses the heightened intrusiveness for personal devices in Section VIII.E, noting that Policy §4.5 requires consent or a court order for BYOD imaging, that individuals may need separate counsel, and that the GC's and CCO's devices require a filter-team protocol. The distinction between full physical (forensic) imaging and logical extraction is clearly made.
- **GPT-5.5: Pass.** The memo expressly distinguishes full physical forensic imaging/bit-for-bit copies from logical extraction, stating that logical extraction is not enough. It also discusses the heightened intrusiveness and legal/privacy issues for personal devices, including BYOD consent or court order requirements, external HCP devices, privacy filtering, and possible refusals.

### C-023

ISSUE_009: Identifies inconsistent use of 'documents,' 'records,' 'materials' ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L198))

- **Sonnet 4.6: Pass.** The memo explicitly addresses this issue in Section IV.D ('Defined Terms — Drafting Traps'). It describes the nested hierarchy of defined terms (Documents ⊂ Records ⊂ Materials, plus Communications and ESI defined separately), and then notes that 'The operative paragraphs use these terms inconsistently. For example: ¶¶21, 22 and 26 cover "Documents, Records, and Communications" but not Materials; ¶¶19, 23, 24, 27 and 28 use undefined lower-case terms; ¶30 uses the undefined term "Documentation"; ¶32 omits Communications and ESI.' It then recommends reading every paragraph as covering all five defined terms and not relying on any narrower reading without written DOJ agreement. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies that Paragraph 3 defines Documents, Records, and Materials with distinct nested scopes, and then states that the operative paragraphs use these terms inconsistently, creating ambiguity and recommending a broad reading. This satisfies the criterion.

### C-024

ISSUE_009: Recommends applying broadest definition uniformly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L206))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the terminological inconsistency in Section IV.D, noting that operative paragraphs use the defined terms inconsistently (e.g., some paragraphs cover 'Documents, Records, and Communications' but not Materials; others use undefined lower-case terms). It then provides a clear recommendation: 'read every paragraph as covering all five defined terms. Do not rely on any narrower reading without written DOJ agreement.' This directly satisfies the criterion of recommending that the broadest definition be applied uniformly across all operative paragraphs to avoid preservation gaps.
- **GPT-5.5: Pass.** The memo explicitly identifies terminological inconsistencies among Documents, Records, Materials, Communications, and ESI, and recommends reading every operative paragraph as covering all five defined terms unless DOJ agrees otherwise in writing. This satisfies the requirement to apply the broadest definition uniformly to avoid preservation gaps.

### C-025

ISSUE_010: Assesses backup tape preservation burden and proportionality ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L214))

- **Sonnet 4.6: Fail.** The memo extensively discusses backup tape preservation obligations (G1, G2, VIII.A, VIII.C, X) and identifies critical risks around the 90-day rotation cycle and legacy tapes. However, it never performs a proportionality analysis of the backup tape preservation burden. It does not discuss whether preserving all backup tapes is proportionate given the accessibility of the same data in primary systems, nor does it reference Zubulake v. UBS Warburg or any analogous principle that backup tape preservation is disfavored when data exists in accessible form. The memo treats the obligation as absolute and focuses on compliance rather than questioning or analyzing the proportionality of the requirement.
- **GPT-5.5: Fail.** The memo identifies the obligation to suspend the 90-day backup tape rotation, preserve tapes, and potentially use tapes to recover January 2025 deletions. It also notes recovery cost estimates. However, it does not provide a proportionality analysis of preserving all backup tapes from January 2019 forward, nor does it reference the general Zubulake-type principle that backup tape preservation is disfavored where the same data exists in accessible sources. The discussion treats tape preservation as mandatory/critical rather than assessing burden versus need.

### C-026

ISSUE_010: Notes backup tapes may be sole source due to migration loss ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L222))

- **Sonnet 4.6: Pass.** The memo explicitly connects the backup tape preservation to the email migration data loss. In the Executive Summary, it states: 'The tape rotation is also the only possible route to recovering electronic records deleted on January 15, 2025.' In Part VIII.A, it states: 'Stop the tape rotation today. Electronic deletions from primary systems may survive on weekly full backups made before January 15.' In Part VIII.C, it discusses the 340,000 un-migrated emails existing only on six decommissioned servers and the legacy backup tapes, and recommends preserving the entire server set. The connection between backup tape preservation and the email migration data loss is clearly and explicitly made throughout the memo.
- **GPT-5.5: Fail.** The memo discusses backup tape preservation extensively and separately identifies the 2021 migration gap involving approximately 340,000 emails. However, it does not make the required connection that backup tapes may be the sole remaining source for certain custodian data lost in the migration. Instead, it states that the migration-gap emails exist only on six decommissioned Exchange servers and treats backup tapes primarily as critical for recovering the January 15 destruction. Thus the specific criterion is not satisfied.

### C-027

ISSUE_011a: Identifies Linden & Pruitt conflict due to prior representation of Dr. Osei ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L230))

- **Sonnet 4.6: Pass.** Section VIII.F explicitly states that Linden & Pruitt, P.A. is 'conflicted out because it separately represented Dr. Osei personally' and that 'Dr. Osei is a named custodian, was L&P's main business contact, and is affected by the migration gap.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies that Linden & Pruitt, P.A. is conflicted out because it separately represented Dr. Franklin Osei personally, and notes that Dr. Osei is a named custodian and VP Medical Affairs.

### C-028

ISSUE_011b: Identifies that privileged Linden & Pruitt communications may be swept into preservation scope ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L238))

- **Sonnet 4.6: Pass.** Section VIII.F explicitly addresses Linden & Pruitt, noting that Paragraph 29 expressly reaches communications with Linden & Pruitt about Velcara regulatory, FDA labeling and compliance advice, and discusses the privilege complications arising from L&P's conflict (having separately represented Dr. Osei personally). The memo recommends sending L&P a preservation letter, not using L&P for hold or privilege work, setting up a protocol for L&P materials where privilege belongs to Ridgeline, and segregated review. This clearly identifies that privileged L&P communications are swept into preservation scope and discusses the privilege implications.
- **GPT-5.5: Pass.** The memo expressly discusses Linden & Pruitt communications as within the preservation scope, including Velcara regulatory/FDA labeling/compliance advice, and flags privilege complications from L&P's separate representation of Dr. Osei. It recommends preservation letters, segregated privilege review, and separate counsel, satisfying the criterion.

### C-029

ISSUE_011: Recommends protocol for handling privileged materials ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L246))

- **Sonnet 4.6: Pass.** Section VIII.F explicitly addresses the Linden & Pruitt situation and recommends a privilege protocol: 'set up a protocol for L&P materials in which privilege belongs to Ridgeline, not Dr. Osei, with segregated review.' It also recommends sending L&P a preservation letter, not using L&P for hold or privilege work, and advising Dr. Osei to retain separate counsel. This directly addresses the adverse former counsel relationship and establishes a privilege review protocol for L&P materials.
- **GPT-5.5: Pass.** The memo expressly identifies Linden & Pruitt privilege complications and recommends setting up a protocol for L&P materials, including segregated review, clarifying privilege ownership, avoiding use of L&P for privilege work, and advising Dr. Osei to retain separate counsel.

### C-030

ISSUE_012: Identifies RPAF as separate legal entity with preservation implications ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L254))

- **Sonnet 4.6: Pass.** Section VIII.D explicitly addresses RPAF as a 'legally separate North Carolina 501(c)(3) organization' with its own executive director, bank accounts, records, and retention policy. The memo discusses that Ridgeline does not control RPAF's day-to-day operations, that board action may be needed to adopt a hold, and that the Notice's attempt to bind RPAF (¶4) raises questions about whether Ridgeline can compel RPAF's preservation. It recommends sending a separate preservation notice to RPAF's executive director and board, suggesting RPAF retain its own counsel, and asking DOJ whether it will serve RPAF directly. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly discusses RPAF as a legally separate North Carolina 501(c)(3) with its own governance, records, and retention policy, notes that Ridgeline does not control its day-to-day operations, and explains that board action or separate notice may be needed because the DOJ Notice may not directly bind RPAF despite purporting to include it.

### C-031

ISSUE_012: Notes RPAF board independence and coordination requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L262))

- **Sonnet 4.6: Pass.** Section VIII.D explicitly addresses RPAF's independent governance structure, noting it has its own executive director, bank accounts, records, and five directors (two of whom are independent per OIG guidance). The memo states that 'board action may be needed to adopt a hold' and recommends sending a written preservation notice directly to RPAF's executive director and full board, asking for written confirmation and a board resolution. It also suggests RPAF retain its own counsel and notes that Ridgeline should describe accurately what it can and cannot control, asking DOJ whether it will serve RPAF directly. This clearly addresses the need for separate coordination with RPAF's independent governance rather than simply directing RPAF to comply.
- **GPT-5.5: Pass.** The memo expressly addresses RPAF’s separate governance: it states RPAF is a legally separate 501(c)(3), has five directors including two independent directors, and that board action may be needed to adopt a hold. It recommends sending a preservation notice to RPAF’s executive director and full board, requesting written confirmation and a board resolution, and suggests RPAF retain separate counsel rather than Ridgeline simply directing compliance.

### C-032

Correctly states the 14-day confirmation deadline as March 17, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L270))

- **Sonnet 4.6: Pass.** The memo explicitly states 'Mar. 17, 2025 (Mon.) — Written certification to Faulkner and Gutierrez covering items (a)--(f) of ¶45' in the deadline calendar (Part III), and this date is referenced multiple times throughout the document as the deadline for the written compliance certification/confirmation. The memo correctly identifies March 17, 2025 as the 14-day deadline from the March 3, 2025 notice date.
- **GPT-5.5: Pass.** The memo repeatedly identifies the March 17, 2025 deadline for the written certification/confirmation required by paragraph 45, including in the Deadline Calendar and certification section.

### C-033

Correctly states the 10-day third-party vendor deadline as March 13, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L278))

- **Sonnet 4.6: Pass.** The memo explicitly identifies March 13, 2025 as the deadline for issuing written preservation notices to third-party vendors. This appears in the Deadline Calendar (Part III) stating 'Issue written preservation notices to all third-party vendors (at least Veeva, SAP, Concur, IntegriCall)' with deadline 'Mar. 13, 2025 (Thu.)'. It is also referenced in Part V.H (Obligation H1) and Part X action item #9, and Part XI item #9. The named vendors Veeva, Concur, and IntegriCall are all specifically mentioned in connection with this March 13 deadline.
- **GPT-5.5: Pass.** The memo repeatedly identifies March 13, 2025 as the deadline to issue written preservation notices to third-party vendors, including Veeva, SAP/Concur, and IntegriCall.

### C-034

Correctly states the 21-day mobile device imaging deadline as March 24, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L286))

- **Sonnet 4.6: Pass.** The memo explicitly states the March 24, 2025 deadline for forensic imaging of mobile devices in multiple places: the deadline calendar table (Section III) lists 'Mar. 24, 2025 (Mon.)' for 'Complete forensic (full physical, not logical) imaging of all personal and company mobile devices of all 23 named custodians, with a chain-of-custody log'; Section V.F (Mobile Devices) lists 'Mar. 24' as the deadline for F1 and F2; and Section X (Action Plan) references 'By March 24' for completing forensic imaging. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo expressly identifies March 24, 2025 as the deadline to complete forensic imaging of all personal and company mobile devices of all 23 named custodians, including in the deadline calendar and mobile devices section.

### C-035

Identifies the Relevant Period as January 1, 2019 to March 3, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L294))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section IV.C (Time Periods) that the General Relevant Period is 'Jan. 1, 2019 -- Mar. 3, 2025' with source '¶12; Exh. A', which matches the criterion exactly.
- **GPT-5.5: Pass.** The memo expressly identifies the General Relevant Period as January 1, 2019 through March 3, 2025 in the Time Periods section, citing Paragraph 12.

### C-036

Identifies ESI preservation requirement including specific platforms ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L302))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the ESI preservation requirement in native format with metadata intact (Section D, ref D1: 'Preserve all ESI natively with metadata intact. No printing, PDF, CSV export or screenshots as a substitute.'). It also specifically mentions well more than four of the listed platforms: Slack (E1), Microsoft Teams (E1), email including deleted items/archives (D2, ref to Exchange and M365, Recoverable Items, archive and journal mailboxes), SharePoint (E3), OneDrive (E3), Salesforce CRM (E2, C1, VIII.A), Veeva Vault (E2, C1), and SAP ERP (C8, H1, Part IX). All eight listed platforms are mentioned.
- **GPT-5.5: Pass.** The memo expressly states the obligation to preserve ESI natively with metadata intact and no substitute formats. It also specifically mentions numerous qualifying platforms, including Slack, Microsoft Teams, email with deleted/archive items, SharePoint, OneDrive, Salesforce CRM, Veeva Vault/CRM, and SAP ERP.

### C-037

Identifies backup tape rotation suspension obligation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L310))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the obligation to suspend the 90-day backup tape rotation in multiple places. In the Executive Summary, it states 'The April 15, 2025 destruction cycle and the 90-day backup tape rotation are still running' and that 'Paragraphs 5, 33 and 41 of the Notice required suspension immediately on receipt.' In the Deadline Calendar, the March 3 immediate obligation includes 'Suspend all auto-deletion, destruction schedules, backup tape recycling, email purges and vault clean-up.' In Section G (Backup Tapes, Legacy Hardware, Paper), obligation G1 explicitly states 'Suspend the 90-day backup rotation in its entirety; no tape recycled, overwritten or degaussed; covers tapes offsite at Sentinel and any DR vendor; notify those vendors' with source ¶41 and deadline 'Immediate.' The memo also notes this is 'CRITICAL' and that the tapes may hold the only copies of data deleted January 15, 2025. The Action Plan item 2 says 'Pull all backup tapes from rotation (current environment and any legacy tapes).' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo repeatedly identifies the obligation to immediately suspend backup tape recycling/rotation, including the 90-day tape rotation, and states that no tapes should be recycled, overwritten, or degaussed. It ties this to the relevant period beginning January 1, 2019 and broadly directs preservation of tapes/backups, which satisfies the criterion.

### C-038

Identifies paper records preservation obligation at Durham headquarters ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L318))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the obligation to secure paper records at Durham headquarters. In Section V.G (Backup Tapes, Legacy Hardware, Paper), obligation G3 states: 'Paper: secure and restrict access to custodian offices and central files at Durham and Atlanta; no removal (except safeguarded business use), shredding or discard; inventory off-site paper storage and instruct operators.' This directly addresses the obligation to physically secure paper files in custodian offices and central filing rooms at the Durham headquarters.
- **GPT-5.5: Pass.** The memo expressly identifies the paper preservation obligation, including securing and restricting access to paper records in custodian offices and central files at the Durham headquarters, and reiterates this in the action plan.

### C-039

Identifies paper records preservation obligation at Atlanta field office ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L326))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the obligation to secure paper records at the Atlanta field office. In Section G (Backup Tapes, Legacy Hardware, Paper), obligation G3 states: 'Paper: secure and restrict access to custodian offices and central files at Durham and Atlanta; no removal (except safeguarded business use), shredding or discard; inventory off-site paper storage and instruct operators.' The Atlanta field office is also referenced in Section IV.A as a specific covered facility. The action plan in Section X also mentions 'Secure paper at Durham and Atlanta (lock files, suspend shred-bin pickups).'
- **GPT-5.5: Pass.** The memo expressly identifies the paper preservation obligation for Atlanta, including securing and restricting access to custodian offices and central files at Durham and Atlanta, prohibiting removal/shredding/discard, and an action item to secure paper at Durham and Atlanta.

### C-040

Names the three specific third-party vendors requiring preservation notices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L334))

- **Sonnet 4.6: Pass.** The memo explicitly identifies all three required vendors: Veeva CRM (listed as 'Veeva Systems' with '¶43(a) (named)' and description of Veeva CRM and Vault), Concur expense system (listed as 'Concur Technologies (SAP Concur)' with '¶43(c) (named)'), and IntegriCall Services (listed as 'IntegriCall Services' with '¶43(d) (named)'). All three appear in the Third-Party Preservation Notice List in Part IX, and are also referenced in the obligation extraction matrix under H1.
- **GPT-5.5: Pass.** The memo identifies all three required third-party vendors/platforms for preservation notices: Veeva CRM (Veeva Systems), Concur expense system (Concur Technologies/SAP Concur), and IntegriCall Services for hotline/compliance records.

### C-041

Identifies the nine subject-matter areas or 34 document categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L342))

- **Sonnet 4.6: Pass.** The memo explicitly catalogs all nine subject-matter areas from Exhibit B in Section V.C (Obligation Extraction Matrix) and in the reconciliation table in Section VI. The areas covered include: (1) KOL/Speaker Program administration (Cats. 1-6), (2) Compensation/FMV (Cats. 7-10), (3) HCP selection/due diligence (Cats. 11-14), (4) Patient assistance/RPAF (Cats. 15-19), (5) Compliance/audit (Cats. 20-23), (6) Financial records (Cats. 24-27), (7) Marketing/promotional (Cats. 28-30), (8) Government inquiry communications (Cats. 31-32), and (9) IT/data systems (Cats. 33-34). All nine areas are identified with their corresponding category numbers, well exceeding the threshold of five required for a PASS.
- **GPT-5.5: Pass.** The memo catalogs the Exhibit B categories organized by subject matter and explicitly identifies all nine areas, including speaker program administration, compensation/FMV, HCP selection, RPAF, compliance, financial records, marketing, government inquiry communications, and IT/data systems. It also references the 34 categories and discusses numbering inconsistencies.

### C-042

Identifies conflict between retention policy and preservation obligations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L350))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the conflict between Policy RDG-LGL-007's retention schedules and the Notice's preservation obligations. In Section VII (Conflicts Between the Notice and Internal Policy/Practice), the memo lists '§4.1 30-day Recoverable Items purge; Cat. E 3-year email retention' conflicting with the Notice's requirement to preserve email without purging Recoverable Items. In Section VIII.A, the memo details that routine business correspondence (emails) was destroyed on a 3-year schedule 'per §4.2' and sales call records on a 2-year schedule 'per §4.5' (actually Cat. F), both of which fall within the Notice's January 1, 2019 forward preservation period. The memo also notes these destructions hit Notice categories directly. The specific conflicts between the 3-year email retention, 2-year CRM/call record retention, and the Notice's preservation obligations are clearly identified throughout the document.
- **GPT-5.5: Pass.** The memo specifically identifies the relevant retention schedules: routine business correspondence/emails destroyed under a 3-year retention period and sales call records/field activity reports under a 2-year retention period. It also ties those categories to records dating from 2019 forward, notes they were destroyed despite falling within Notice categories, and repeatedly states that the Preservation Notice requires preservation from January 1, 2019 onward and overrides/suspends the policy schedules.

### C-043

Memo includes a prioritized action item list organized by urgency ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L358))

- **Sonnet 4.6: Pass.** Section X ('Recommended Action Plan') contains a clearly labeled, prioritized list of action items grouped into four urgency tiers with specific deadline dates: 'Within 24–48 hours (by March 6–7)', 'By March 13', 'By March 17', and 'By March 24 and ongoing'. Each tier contains numbered action items. This satisfies the criterion of an identifiable section with action items grouped/ordered by deadline or urgency tier.
- **GPT-5.5: Pass.** The memo contains an identifiable 'Recommended Action Plan' section with action items grouped by urgency/deadline tiers: within 24–48 hours, by March 13, by March 17, and by March 24/ongoing. This satisfies the requirement for a prioritized action item list organized by urgency.

### C-044

Action items include correct sequencing of the three deadlines ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L366))

- **Sonnet 4.6: Pass.** The action plan in Section X clearly sequences the three deadlines in chronological order: (1) By March 13 — send all third-party and RPAF preservation notices (items 9-11); (2) By March 17 — serve the written ¶46 disclosure and the ¶45 certification (items 12-13); (3) By March 24 and ongoing — complete forensic imaging with chain-of-custody logs (item 14). All three deadlines are present and correctly sequenced.
- **GPT-5.5: Pass.** The action plan and deadline calendar list the three key deadlines in the correct chronological order: March 13 for third-party/vendor preservation notices, March 17 for the written certification/confirmation of litigation hold compliance, and March 24 for completion of forensic mobile device imaging.

### C-045

References Grand Jury No. 24-GJ-0387 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L374))

- **Sonnet 4.6: Pass.** The memo explicitly references Grand Jury Investigation No. 24-GJ-0387 in the RE line of the memorandum header: 'RE: Obligation Extraction --- DOJ Litigation Hold and Document Preservation Notice, Grand Jury Investigation No. 24-GJ-0387 (issued March 3, 2025)'. It is also referenced in Part VIII.A where the grand jury number prefix '24-GJ-' is noted as indicating a 2024 investigation.
- **GPT-5.5: Pass.** The memo explicitly references “Grand Jury Investigation No. 24-GJ-0387” in the RE line.

### C-046

References Anti-Kickback Statute and/or False Claims Act ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L382))

- **Sonnet 4.6: Pass.** The memo explicitly references both the Anti-Kickback Statute (42 U.S.C. §1320a-7b(b)) and the False Claims Act (31 U.S.C. §§3729–3733) in Section IV.B under 'Subject Matter,' noting these as the statutes underlying the investigation.
- **GPT-5.5: Pass.** The memo expressly identifies the Anti-Kickback Statute and the False Claims Act as statutes underlying the investigation in Section IV.B, and elsewhere references AKS/FCA-related scope.

### C-047

Identifies AUSA Brendan K. Faulkner as the DOJ contact for confirmation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L390))

- **Sonnet 4.6: Pass.** The memo explicitly identifies AUSA Brendan K. Faulkner multiple times in connection with the confirmation/certification obligation. In Section III (Deadline Calendar), the March 17 deadline states 'Written certification to Faulkner and Gutierrez covering items (a)--(f) of ¶45.' In Section I2 of the Obligation Matrix, it states 'Direct all communications about the Notice exclusively to AUSA Faulkner ((704) 338-3170) and TA Gutierrez.' In Section X (Action Plan), item 10 states 'HTM contacts AUSA Faulkner and TA Gutierrez to raise clarification points.' Faulkner is clearly identified as the DOJ contact for the written confirmation/certification obligation.
- **GPT-5.5: Pass.** The memo identifies AUSA Brendan K. Faulkner as a DOJ contact and specifically states that the March 17 written certification/confirmation should be sent to Faulkner and Gutierrez.

### C-048

Cites specific paragraph numbers from the Preservation Notice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L398))

- **Sonnet 4.6: Pass.** The memo extensively cites specific paragraph numbers from the DOJ Preservation Notice throughout. Examples include: ¶¶1, 5, 33, 41, 52 (deadline calendar), ¶4 (RPAF), ¶10 (statutes), ¶12 (time period), ¶13 (custodians), ¶16 (functional-title custodians), ¶17 (mobile devices), ¶18 (DOJ supplement), ¶19 (categories), ¶¶20-30 (subject matter areas), ¶31 (related compounds), ¶32 (continuing duty), ¶33 (no destruction), ¶34 (obstruction), ¶35 (ESI format), ¶36 (email), ¶37 (messaging), ¶38 (enterprise apps), ¶39 (SharePoint), ¶40 (mobile imaging), ¶41 (backup tapes), ¶42 (legacy hardware), ¶43 (third-party notices), ¶44 (paper), ¶45 (certification), ¶46 (disclosure), ¶47 (financial records period), ¶48 (privilege), ¶49 (obstruction threat), ¶50 (cooperation), ¶51 (scope questions), ¶52 (effective date). This far exceeds the minimum of 4 distinct paragraph references required.
- **GPT-5.5: Pass.** The memo repeatedly cites specific Preservation Notice paragraph numbers throughout, including ¶¶1, 3, 5, 12, 19, 23, 24, 31, 33, 41, 43, 45, 46, 47, 51, and 52, among many others, when discussing obligations and inconsistencies. This exceeds the minimum requirement of 4 distinct paragraph references.

### C-049

Identifies the obligation to preserve files and data for 23 named custodians ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L406))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the obligation to preserve files and data for 23 named custodians in multiple places. Section IV.E is titled 'Named Custodians (23)' and lists all 23 custodians with their roles. Section B of the Obligation Extraction Matrix (Part V.B) obligation B1 states 'Preserve all data of all 23 custodians on corporate systems, personal devices, personal webmail, personal cloud...' The deadline calendar also references the 23 custodians. The memo thoroughly addresses this obligation.
- **GPT-5.5: Pass.** The memo expressly identifies 23 named custodians, lists them in a custodian table, and states the obligation to preserve all data/files for all 23 custodians across corporate systems, personal devices, personal webmail, personal cloud, and home computers.

### C-050

Names at least 5 key custodians from the 23 named custodians ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L414))

- **Sonnet 4.6: Pass.** The memo explicitly names all 9 key custodians from the list: Dr. Priya Venkataraman (CEO, #1), Marcus Ellsworth (GC, #2), Diane Cho-Rosen (CCO, #3), Dr. Franklin Osei (VP Medical Affairs, #4), Gregory Hsu (VP Commercial Operations, #5), Amanda Terrell (Sr. Dir., Speaker Programs, #6), Richard Blaine (Dir., Patient Assistance Programs, #7), Dr. Katerina Novak (MSL, Southeast, #8), and Luis Delgado (National Sales Director, #9). This far exceeds the minimum of 5 required.
- **GPT-5.5: Pass.** The memo specifically names all 9 listed key custodians, including Dr. Priya Venkataraman, Marcus Ellsworth, Diane Cho-Rosen, Dr. Franklin Osei, Gregory Hsu, Amanda Terrell, Richard Blaine, Dr. Katerina Novak, and Luis Delgado. This exceeds the requirement of at least 5.

### C-051

Addresses the 5 non-employee HCP consultants in Exhibit D ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L422))

- **Sonnet 4.6: Pass.** The memo extensively addresses the 5 non-employee HCP consultants in Exhibit D. It identifies all five by name (Dr. Raymond T. Whitford, Dr. Ingrid M. Svensson, Dr. Oscar L. Famuyide, Dr. Hannah J. Prescott, Dr. Samuel K. Anand) with their institutions and payment amounts in the custodian table. It notes they are external/non-employee HCPs. It requires preservation of all communications with them (B4, C5, ¶24). It also specifically addresses the challenge of imaging their personal devices (VIII.E), noting Ridgeline cannot compel them to hand over devices and recommending clarification with DOJ. The memo clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies five Exhibit D HCPs as external/non-employee custodians and repeatedly states that communications with the Exhibit D HCPs must be preserved, including all contracts, payments, expenses, travel records, and communications across channels.

### C-052

Identifies Velcara (ridgenostat) as the drug at issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L430))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Velcara (ridgenostat) multiple times throughout the document, including in the executive summary, scope parameters, subject matter section, and various obligation matrices. For example, Section IV.B states 'marketing, promotion and sale of Velcara (ridgenostat)' and the drug is referenced extensively throughout the memo.
- **GPT-5.5: Pass.** The memo explicitly identifies Velcara (ridgenostat) multiple times as the drug at issue, including in the subject-matter section: “marketing, promotion and sale of Velcara (ridgenostat)” and in preservation categories referencing Velcara.
