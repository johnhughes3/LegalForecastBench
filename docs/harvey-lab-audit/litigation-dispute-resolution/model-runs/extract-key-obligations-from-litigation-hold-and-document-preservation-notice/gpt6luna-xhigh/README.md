# GPT-6 Luna (xhigh): Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 39 of 52 criteria; GPT-5.5 passed 39 of 52 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [obligation-extraction-memo.docx](output/obligation-extraction-memo.docx) ([read as Markdown](output/obligation-extraction-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001: Identifies conflicting Relevant Period for financial records | Pass | Pass |
| [C-002](#c-002) | ISSUE_001: Flags financial records date discrepancy as requiring DOJ clarification | **Fail** | **Fail** |
| [C-003](#c-003) | ISSUE_001: Notes broader date range creates additional preservation burden | Pass | Pass |
| [C-004](#c-004) | ISSUE_002: Identifies contradictory HCP communication scope | **Fail** | **Fail** |
| [C-005](#c-005) | ISSUE_002: Explains dramatically different scope implications of HCP readings | **Fail** | **Fail** |
| [C-006](#c-006) | ISSUE_002: Recommends defaulting to broader HCP interpretation | **Fail** | **Fail** |
| [C-007](#c-007) | ISSUE_003: Flags January 15, 2025 destruction of approximately 4.2 million records from the 2019–2021 period | Pass | Pass |
| [C-008](#c-008) | ISSUE_003: Notes destruction occurred approximately 7 weeks before Preservation Notice | **Fail** | Pass |
| [C-009](#c-009) | ISSUE_003: Addresses potential spoliation risk from pre-notice destruction | Pass | Pass |
| [C-010](#c-010) | ISSUE_003: Recommends forensic investigation of destroyed records | Pass | Pass |
| [C-011](#c-011) | ISSUE_004: Identifies email migration data loss affecting approximately 340,000 pre-September 2021 emails | Pass | Pass |
| [C-012](#c-012) | ISSUE_004: Identifies that 8 of 23 named custodians are affected by email migration loss | Pass | Pass |
| [C-013](#c-013) | ISSUE_004: Notes affected emails fall within Relevant Period | Pass | Pass |
| [C-014](#c-014) | ISSUE_004: Recommends preserving decommissioned servers at offsite storage | Pass | Pass |
| [C-015](#c-015) | ISSUE_005: Flags 'related compounds' as potential massive scope expansion | **Fail** | **Fail** |
| [C-016](#c-016) | ISSUE_005: Recommends seeking clarification on 'related compounds' | **Fail** | **Fail** |
| [C-017](#c-017) | ISSUE_006: Identifies compressed third-party vendor notification deadline | Pass | Pass |
| [C-018](#c-018) | ISSUE_006: Flags need for immediate/parallel action on third-party notices | Pass | **Fail** |
| [C-019](#c-019) | ISSUE_007: Identifies Exhibit B category count discrepancy (34 vs. 36) | Pass | Pass |
| [C-020](#c-020) | ISSUE_007: Recommends clarification on missing categories | Pass | Pass |
| [C-021](#c-021) | ISSUE_008: Identifies privacy concerns with forensic imaging of personal devices | **Fail** | Pass |
| [C-022](#c-022) | ISSUE_008: Distinguishes forensic imaging from logical extraction | Pass | Pass |
| [C-023](#c-023) | ISSUE_009: Identifies inconsistent use of 'documents,' 'records,' 'materials' | **Fail** | **Fail** |
| [C-024](#c-024) | ISSUE_009: Recommends applying broadest definition uniformly | **Fail** | **Fail** |
| [C-025](#c-025) | ISSUE_010: Assesses backup tape preservation burden and proportionality | **Fail** | **Fail** |
| [C-026](#c-026) | ISSUE_010: Notes backup tapes may be sole source due to migration loss | Pass | **Fail** |
| [C-027](#c-027) | ISSUE_011a: Identifies Linden & Pruitt conflict due to prior representation of Dr. Osei | **Fail** | **Fail** |
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
| [C-046](#c-046) | References Anti-Kickback Statute and/or False Claims Act | **Fail** | **Fail** |
| [C-047](#c-047) | Identifies AUSA Brendan K. Faulkner as the DOJ contact for confirmation | Pass | Pass |
| [C-048](#c-048) | Cites specific paragraph numbers from the Preservation Notice | Pass | Pass |
| [C-049](#c-049) | Identifies the obligation to preserve files and data for 23 named custodians | Pass | Pass |
| [C-050](#c-050) | Names at least 5 key custodians from the 23 named custodians | Pass | Pass |
| [C-051](#c-051) | Addresses the 5 non-employee HCP consultants in Exhibit D | Pass | Pass |
| [C-052](#c-052) | Identifies Velcara (ridgenostat) as the drug at issue | Pass | Pass |

## Judge reasoning

### C-001

ISSUE_001: Identifies conflicting Relevant Period for financial records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L22))

- **Sonnet 4.6: Pass.** Section 3.3 of the memo explicitly identifies both time periods: 'General Relevant Period: January 1, 2019 through March 3, 2025' (citing Notice ¶ 12) and 'Extended financial period: January 1, 2017 to present for KOL, RPAF, and Velcara financial records' (citing Notice ¶ 47). The memo clearly notes this as a separate, extended period and instructs to 'preserve earlier-period archives and backups with the same rigor.' This directly identifies the two-year discrepancy between the general relevant period starting January 1, 2019 and the financial records period starting January 1, 2017.
- **GPT-5.5: Pass.** The memo expressly states that the general Relevant Period is January 1, 2019 through March 3, 2025 under Notice ¶12, and separately identifies an extended financial period beginning January 1, 2017 under ¶47 for KOL, RPAF, Velcara financial/accounting/payment records, including noting that 2017–2018 financial data is independently in scope. This satisfies the requirement to identify the two-year discrepancy/extension for financial records.

### C-002

ISSUE_001: Flags financial records date discrepancy as requiring DOJ clarification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L30))

- **Sonnet 4.6: Fail.** The memo acknowledges the two different time periods (January 1, 2017 for financial records and January 1, 2019 as the general relevant period) in Section 3.3, but it treats them as complementary rather than conflicting, simply stating to 'preserve earlier-period archives and backups with the same rigor.' The memo does not recommend seeking clarification from DOJ about this date discrepancy. It only recommends seeking DOJ clarification for the Exhibit B category count discrepancy (36 vs. 34 categories) and for the deadline receipt date. There is no recommendation to seek DOJ clarification specifically about the conflicting financial records date ranges (2017 vs. 2019).
- **GPT-5.5: Fail.** The memo identifies both the general Jan. 1, 2019 relevant period and an extended Jan. 1, 2017 financial-records period, but it treats the 2017 period as controlling/extended rather than flagging a conflict and recommending DOJ clarification regarding the date discrepancy for financial records.

### C-003

ISSUE_001: Notes broader date range creates additional preservation burden ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L38))

- **Sonnet 4.6: Pass.** Section 3.3 explicitly notes the extended financial period (January 1, 2017 to present) for KOL, RPAF, and Velcara financial records and states to 'preserve earlier-period archives and backups with the same rigor.' The memo also notes that the financial extension 'independently makes relevant 2017–2018 financial data in scope' alongside the backup tape preservation requirement. However, the criterion specifically asks whether the memo connects this broader date range to the additional preservation burdens created by the January 2025 destruction event or the email migration issue. The migration gap covers January 2019–September 2021, so the 2017–2018 extended period is not directly tied to the migration issue. Regarding the January 2025 destruction, Section 5.2 discusses the destruction event and notes that KOL event files and RPAF correspondence were destroyed, and Section 3.3 notes the extended financial period. However, the memo does not explicitly connect the 2017 start date to the destruction event as creating an additional burden—it discusses them somewhat separately. That said, Section 3.3 does note that the financial extension creates a separate preservation obligation for earlier archives/backups, and Section 5.2 discusses the destruction of KOL and RPAF records (which fall under the extended period). The practical impact of the broader date range is discussed (preserve earlier archives with same rigor, financial extension makes 2017-2018 data in scope), even if the explicit connection to the destruction event is not spelled out in a single sentence. The criterion says PASS if the memo notes the extended date range creates additional preservation burdens 'particularly in light of' the destruction or migration issues—the memo does discuss both the extended range and the destruction/migration issues, and notes the extended range creates additional burdens, though the explicit linkage is implicit rather than direct. Given the memo does address the practical impact of the broader date range and discusses both the destruction event and migration gap as separate issues, I'll consider whether this meets the criterion. The criterion requires noting the practical impact of the broader date range in connection with the destruction or migration issues. The memo does this sufficiently by noting the extended period creates additional archive/backup preservation obligations and separately discussing the destruction of KOL/RPAF records that fall within that extended period.
- **GPT-5.5: Pass.** The memo expressly identifies the extended financial period (January 1, 2017 to present) for KOL, RPAF, Velcara financial/accounting/payment records and states that earlier-period archives and backups must be preserved with the same rigor. It also notes that the financial extension independently brings 2017–2018 financial data into scope, creating an added preservation obligation beyond the general 2019 period. Although not heavily tied to the January 2025 destruction event, the practical impact of the broader date range is discussed sufficiently.

### C-004

ISSUE_002: Identifies contradictory HCP communication scope ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L46))

- **Sonnet 4.6: Fail.** The memo mentions HCP communications in section 3.2 under 'HCP communications (¶¶ 23--24; cross-cutting)' and notes that preservation covers 'Communications with any HCP about Velcara efficacy, safety, dosing, administration, formulary, prescribing and reimbursement, in any context---not only listed HCPs or KOL events.' It also references Exhibit D communications. However, the memo does not explicitly identify a contradiction between ¶23 (all HCP communications) and ¶24 (limited to the 5 named Exhibit D HCPs). The memo treats these as complementary rather than contradictory provisions, and does not flag the tension or inconsistency between the broad scope of ¶23 and the narrower scope of ¶24. The criterion specifically requires identification of this contradiction, which the memo fails to do.
- **GPT-5.5: Fail.** The memo recognizes that HCP communications are broad and says they are “not only listed HCPs,” while also discussing the five Exhibit D HCPs. However, it does not identify the specific contradiction required by the criterion: that Paragraph 23 requires preservation of all HCP communications regarding Velcara, whereas Paragraph 24 appears to limit the scope to the five Exhibit D HCPs.

### C-005

ISSUE_002: Explains dramatically different scope implications of HCP readings ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L54))

- **Sonnet 4.6: Fail.** The memo discusses that HCP communications are not limited to the 5 named Exhibit D HCPs but extend to 'any HCP' regarding Velcara topics. However, it does not explain or quantify the dramatically different scope implications in terms of document volume—it never discusses that the broader reading could encompass potentially millions of additional documents compared to the narrow reading of just 5 named HCPs. The memo notes the broader scope but does not contrast the volume/scale difference between the two interpretations.
- **GPT-5.5: Fail.** The memo recognizes a broad reading covering communications with any HCP, not just the five Exhibit D HCPs, but it does not explain the dramatically different volume implications—i.e., that the broad reading could encompass potentially millions of additional documents compared with the narrow five-HCP interpretation.

### C-006

ISSUE_002: Recommends defaulting to broader HCP interpretation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L62))

- **Sonnet 4.6: Fail.** The memo in Section 3.2 under 'HCP communications (¶¶ 23--24; cross-cutting)' states: 'Communications with any HCP about Velcara efficacy, safety, dosing, administration, formulary, prescribing and reimbursement, in any context---not only listed HCPs or KOL events.' This explicitly recommends the broader interpretation (all HCPs regarding Velcara, not just the listed ones). Additionally, Section 2 notes 'do not unilaterally narrow an ambiguous category' and the executive summary states 'Preservation is not limited to the 23 named custodians or the enumerated categories.' However, the memo does not explicitly connect this broader HCP interpretation to spoliation risk avoidance. The memo does discuss spoliation risk in the context of the January 15 destruction event, but does not specifically tie the broader HCP interpretation to avoiding spoliation risk. The criterion requires both: (1) recommending the broader interpretation as default AND (2) connecting it to spoliation risk avoidance. While the broader interpretation is clearly recommended, the explicit connection to spoliation risk for the HCP scope specifically is not made in the memo.
- **GPT-5.5: Fail.** The memo does recommend preserving broadly for HCP communications, expressly stating communications with “any HCP about Velcara” are covered and “not only listed HCPs,” and it advises not to unilaterally narrow ambiguous categories while seeking clarification through counsel/DOJ. However, it does not clearly connect this broader default interpretation to avoiding spoliation risk. The only spoliation discussion is tied to the January 15 destruction issue, not the HCP scope ambiguity. Therefore, it does not fully satisfy the criterion as stated.

### C-007

ISSUE_003: Flags January 15, 2025 destruction of approximately 4.2 million records from the 2019–2021 period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L70))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the January 15, 2025 destruction event in multiple places. Section 1 (Executive Summary) states: 'an internal email reports that approximately 4.2 million records, including KOL event files, Velcara field records, RPAF correspondence, emails, and 47 boxes of paper, were destroyed on January 15, 2025.' Section 5.2 is entirely dedicated to 'January 15, 2025 destruction' and provides detailed analysis of the approximately 4.2 million records destroyed from the 2019–2021 period (with sales tranche through 2022). This is clearly flagged as a critical issue throughout the memo.
- **GPT-5.5: Pass.** The memo explicitly identifies the January 15, 2025 destruction cycle as a significant issue, stating that approximately 4.2 million records dated 2019–2021 were destroyed and discussing related preservation risks and follow-up actions.

### C-008

ISSUE_003: Notes destruction occurred approximately 7 weeks before Preservation Notice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L78))

- **Sonnet 4.6: Fail.** The memo in Section 5.2 states that the January 15 destruction 'predates the notice' and notes the records 'were destroyed before the March 3 notice,' but it does not specifically quantify the timing relationship as 'approximately 7 weeks.' The criterion requires the memo to note that the destruction occurred approximately 7 weeks before the Preservation Notice. While the memo identifies that the destruction predated the notice, it does not characterize the gap as approximately 7 weeks (January 15 to March 3 is indeed about 7 weeks). The specific temporal characterization of '~7 weeks' is absent from the memo.
- **GPT-5.5: Pass.** The memo identifies the January 15, 2025 destruction and states that it predates / occurred before the March 3, 2025 Preservation Notice, giving both dates. Although it does not use the phrase “approximately 7 weeks,” it sufficiently identifies the timing relationship required by the criterion.

### C-009

ISSUE_003: Addresses potential spoliation risk from pre-notice destruction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L86))

- **Sonnet 4.6: Pass.** Section 5.2 of the memo explicitly states: 'investigate any earlier actual or reasonably anticipated preservation trigger' and asks whether 'any earlier actual or reasonably anticipated investigation trigger' existed, referencing knowledge, notices, complaints, internal reviews and hold decisions relevant to timing (Open Item 8). The memo also notes the destruction predates the notice but instructs counsel to investigate any earlier preservation trigger and whether responsive copies remain, and to 'report it promptly to DOJ if counsel concludes it is a circumstance covered by ¶ 46.' While the memo does not use the word 'spoliation' explicitly in connection with the anticipation-of-litigation doctrine, it does address the core concept: that if there was an earlier actual or reasonably anticipated preservation trigger before January 15, 2025, the destruction could be problematic. Section 5.2 also explicitly states 'No finding is made here about intent, knowledge, legal duty at the time' — acknowledging the legal duty question is open. The criterion requires the memo to discuss that if DOJ can establish Ridgeline had reason to anticipate litigation before January 15, 2025, the destruction could be characterized as spoliation. The memo does address the anticipation-of-litigation risk by instructing investigation of 'any earlier actual or reasonably anticipated preservation trigger' and noting the need to establish the 'notice/knowledge timeline.' This satisfies the criterion's requirement to address the anticipation-of-litigation/spoliation risk.
- **GPT-5.5: Pass.** The memo explicitly notes the January 15 destruction predated the DOJ notice and no active hold was found, but directs investigation into any earlier actual or reasonably anticipated preservation trigger and states no conclusion is made about spoliation. This addresses the anticipation-of-investigation/litigation spoliation risk even without an existing hold.

### C-010

ISSUE_003: Recommends forensic investigation of destroyed records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L94))

- **Sonnet 4.6: Pass.** Section 5.2 explicitly recommends investigating the January 15, 2025 destruction event, including obtaining the destruction log, batch-level certificates, and recovery prospects. It states: 'investigate any earlier actual or reasonably anticipated preservation trigger, what versions/copies remain, and whether deleted items, backups, archives, vendor copies, users' devices, exports or paper duplicates are recoverable.' Open item #3 in Section 7 also calls for obtaining full records for the January 15 batch and 'recovery prospects.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly addresses the January 15, 2025 destruction, recommends establishing what was destroyed, obtaining destruction logs and certificates, investigating remaining copies, and determining whether deleted items, backups, archives, vendor copies, devices, exports, or paper duplicates are recoverable.

### C-011

ISSUE_004: Identifies email migration data loss affecting approximately 340,000 pre-September 2021 emails ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L102))

- **Sonnet 4.6: Pass.** Section 5.1 of the memo explicitly identifies the Ashford Data Solutions email migration error, noting that approximately 340,000 pre-September 2021 emails were not migrated to Microsoft 365 due to the tool skipping archive mailboxes and certain PST stores for about 2,100 employees. This is treated as a critical preservation issue throughout the memo.
- **GPT-5.5: Pass.** The memo explicitly identifies the Ashford Data Solutions migration problem: it states that approximately 340,000 pre-September 2021 emails for about 2,100 employees were not migrated to Microsoft 365, may exist only on six decommissioned Exchange servers, and treats this as the highest immediate preservation risk/critical issue.

### C-012

ISSUE_004: Identifies that 8 of 23 named custodians are affected by email migration loss ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L110))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 5.1: 'IT estimates 47,000--52,000 missing emails for eight migration-affected individuals it says match the 23-custodian list: Franklin Osei, Greg Hsu, Amanda Terrell, Richard Blaine, Katerina Novak, Luis Delgado, Jennifer Calloway, and David Yun.' This clearly identifies 8 of the 23 named custodians as affected by the email migration data loss.
- **GPT-5.5: Pass.** The memo expressly states that IT estimated missing emails for eight migration-affected individuals/custodians and ties this to the 23-custodian list, while also noting a roster reconciliation issue for two names.

### C-013

ISSUE_004: Notes affected emails fall within Relevant Period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L118))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 5.1 that the missing data is 'estimated at approximately 340,000 emails from January 2019 through September 2021' and in Section 3.3 establishes the General Relevant Period as 'January 1, 2019 through March 3, 2025.' The memo also notes in Section 3.3 that backup tapes containing data from January 1, 2019–March 3, 2025 must be preserved, and in Section 5.1 discusses these emails as falling within the preservation scope. The connection between the ~340,000 missing emails (Jan 2019–Sept 2021) and the Relevant Period (Jan 1, 2019–March 3, 2025) is clearly made, and the memo treats these emails as potentially responsive preservation items throughout.
- **GPT-5.5: Pass.** The memo identifies the migration gap as approximately 340,000 emails from January 2019 through September 2021, separately states the Relevant Period is January 1, 2019 through March 3, 2025, and treats the gap as a high immediate preservation risk involving custodians and potentially responsive sources. This sufficiently connects the affected emails to the Relevant Period and preservation obligations.

### C-014

ISSUE_004: Recommends preserving decommissioned servers at offsite storage ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L126))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the decommissioned Exchange servers at Sentinel Records Management multiple times. In Section 5.1, it identifies the six powered-down Dell PowerEdge servers at Sentinel (Account SM-2247891) as potentially the only surviving source of ~340,000 missing emails. It recommends preserving the servers in their current physical condition, notifying Sentinel in writing to hold all equipment, avoiding booting or altering the servers before a forensic examiner establishes a protocol, and treating the server disks as potentially the only surviving source. Section 4 (Legacy/decommissioned systems row) states: 'Preserve hardware in current physical condition; no sale, donation, recycling, repurposing, degaussing, destruction or other disposal without DOJ's prior written authorization. Maintain storage contract; notify facility in writing.' The sequenced checklist (Section 6.1) also includes 'notify Sentinel in writing to hold all Account SM-2247891 equipment, backups and paper; preserve the legacy servers in current condition' as a first-24-hours action. These recommendations clearly satisfy the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies the six decommissioned Exchange servers at Sentinel Records Management as a key preservation source, directs immediate written notice to Sentinel to hold the equipment, says to preserve the legacy servers in their current condition, avoid booting or altering them before forensic protocol, maintain storage, and prohibits disposal, recycling, repurposing, degaussing, or destruction without authorization.

### C-015

ISSUE_005: Flags 'related compounds' as potential massive scope expansion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L134))

- **Sonnet 4.6: Fail.** The memo mentions 'ridgenostat and related compounds' in Section 3.2 under 'Related compounds / later-created information (¶¶ 31--32)' but only notes that information about ridgenostat and related compounds must be preserved 'to the extent it also relates to the investigation.' The memo does not identify that this could sweep in Ridgeline's 4 additional oncology pipeline compounds, nor does it flag this as a potentially massive or possibly unintended scope expansion. The criterion specifically requires identification of the scope expansion risk regarding the 4 additional pipeline compounds. This analysis is absent from the memo.
- **GPT-5.5: Fail.** The memo notes that Paragraph 31 covers “ridgenostat and related compounds,” but it does not flag that this language could sweep in Ridgeline’s 4 additional oncology pipeline compounds or characterize it as a potentially massive, possibly unintended scope expansion requiring clarification.

### C-016

ISSUE_005: Recommends seeking clarification on 'related compounds' ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L142))

- **Sonnet 4.6: Fail.** The memo mentions 'related compounds' in Section 3.2 under 'Related compounds / later-created information (¶¶ 31--32)' and notes that information about ridgenostat and related compounds should be preserved 'to the extent it also relates to the investigation.' However, the memo does not explicitly recommend seeking clarification from the DOJ on the meaning of 'related compounds.' The general instruction in Section 2 states 'do not unilaterally narrow an ambiguous category' and to raise 'proposed scope clarifications...promptly through counsel,' but this is a general statement not specifically directed at the 'related compounds' ambiguity. The memo does not specifically flag 'related compounds' as an ambiguous term requiring DOJ clarification, nor does it explicitly recommend a conservative hold pending such clarification for this specific term. The criterion requires both a recommendation to seek clarification on 'related compounds' specifically AND a conservative initial hold covering the broader scope. While the memo implicitly preserves broadly, it fails to specifically recommend seeking DOJ clarification on this particular term.
- **GPT-5.5: Fail.** The memo includes related compounds in the preservation scope and generally advises raising scope clarifications through counsel, but it does not specifically recommend seeking DOJ clarification on the meaning of “related compounds” while preserving broadly pending that clarification.

### C-017

ISSUE_006: Identifies compressed third-party vendor notification deadline ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L150))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the March 13, 2025 deadline (10 calendar days) for third-party vendor preservation notices and the March 17, 2025 deadline (14 calendar days) for the overall certification. In Section 2 (Deadlines and mandatory deliverables), the table clearly lists both dates with their respective day counts, and the executive summary also references both deadlines in sequence, making clear that the vendor notification deadline is 4 days earlier than the certification deadline.
- **GPT-5.5: Pass.** The memo expressly identifies the third-party vendor notice deadline as 10 calendar days / March 13, 2025, and separately identifies the overall written certification deadline as 14 calendar days / March 17, 2025, showing the earlier compressed vendor-notification timeline.

### C-018

ISSUE_006: Flags need for immediate/parallel action on third-party notices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L158))

- **Sonnet 4.6: Pass.** The memo explicitly addresses third-party vendor notices in multiple places. In Section 2 (Deadlines), it lists the March 13 deadline for vendor notices and names Veeva Systems, SAP SE, Concur Technologies, and IntegriCall Services. In Section 6.1 (Sequenced Checklist), under 'Now / first 24 hours,' it instructs to 'notify Sentinel in writing to hold all Account SM-2247891 equipment, backups and paper' immediately, and under 'By March 13' it lists sending written hold notices to all relevant vendors including Veeva, SAP, Concur, IntegriCall, Microsoft, Salesforce, Slack, Sentinel, Ashford, and others. The checklist structure itself shows that vendor notices are on a parallel track with the general hold implementation (both starting immediately/within 24 hours), not sequential. The memo also notes in Section 4 that vendor notices must be sent by March 13 and written confirmation obtained. The urgency of parallel/accelerated action on third-party vendor notices is clearly flagged throughout the document, satisfying the criterion.
- **GPT-5.5: Fail.** The memo identifies the March 13 deadline for third-party preservation notices and names Veeva, Concur, and IntegriCall, and it assigns responsibility for obtaining confirmations. However, it does not specifically flag that these vendor notices must be handled immediately or on a parallel/accelerated track rather than waiting for the general hold implementation. The urgency contemplated by the criterion is therefore not clearly stated.

### C-019

ISSUE_007: Identifies Exhibit B category count discrepancy (34 vs. 36) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L166))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 3.2: 'Paragraph 19 calls Exhibit B "thirty-six (36)" categories, but Exhibit B as supplied actually enumerates Categories 1--34. This discrepancy does not narrow the express general duty; counsel should seek written clarification while preserving broadly.' This directly identifies the 36 vs. 34 category count discrepancy.
- **GPT-5.5: Pass.** The memo explicitly states that Paragraph 19 refers to “thirty-six (36)” categories while Exhibit B as supplied enumerates only Categories 1–34, identifying the required numerical discrepancy.

### C-020

ISSUE_007: Recommends clarification on missing categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L174))

- **Sonnet 4.6: Pass.** The memo does address the Exhibit B discrepancy in Section 3.2: 'Paragraph 19 calls Exhibit B "thirty-six (36)" categories, but Exhibit B as supplied actually enumerates Categories 1--34. This discrepancy does not narrow the express general duty; counsel should seek written clarification while preserving broadly.' This satisfies the criterion: it notes the 2-category discrepancy (36 stated vs. 34 enumerated), recommends seeking written clarification, and recommends preserving broadly in the interim.
- **GPT-5.5: Pass.** The memo expressly identifies the discrepancy that Paragraph 19 refers to 36 categories while Exhibit B enumerates only Categories 1–34, and states that counsel should seek written clarification while preserving broadly in the interim.

### C-021

ISSUE_008: Identifies privacy concerns with forensic imaging of personal devices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L182))

- **Sonnet 4.6: Fail.** The memo mentions personal devices and BYOD in several places, but it does not identify employee privacy concerns, Fourth Amendment issues, state privacy law issues, or the need for employee consent or a court order regarding forensic imaging of personal devices. The closest reference is in Section 7, item 7: 'Coordinate lawful/consensual acquisition for personal devices and document limitations without substituting logical extraction for the stated imaging requirement.' While 'lawful/consensual acquisition' hints at consent, it does not explicitly identify privacy concerns, Fourth Amendment issues, state privacy law issues, or the legal framework around compelling employees to submit personal devices. The memo fails to raise these privacy or legal concerns in any substantive way.
- **GPT-5.5: Pass.** The memo flags that imaging personal devices requires careful coordination and specifically instructs the team to coordinate “lawful/consensual acquisition for personal devices” and document limitations. Although it does not expressly mention the Fourth Amendment or state privacy statutes, it identifies the need for lawful consent-based access to personal devices, which satisfies the criterion.

### C-022

ISSUE_008: Distinguishes forensic imaging from logical extraction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L190))

- **Sonnet 4.6: Pass.** The memo explicitly distinguishes forensic imaging from logical extraction in multiple places. In Section 2 (Deadlines), it states 'Complete forensic imaging---not merely logical extraction---of all personal and company-issued mobile devices.' In Section 4 (Technology table), the Mobile devices row states 'complete bit-for-bit image, including deleted and application data...logical extraction alone is insufficient.' In Section 6.1 (Checklist), it again references 'bit-for-bit forensic imaging.' In Open Item 7, it states 'document limitations without substituting logical extraction for the stated imaging requirement.' The memo also acknowledges the heightened intrusiveness for personal devices by noting that 'individual device access requires careful coordination' and discussing 'lawful/consensual acquisition for personal devices.'
- **GPT-5.5: Pass.** The memo repeatedly distinguishes forensic imaging from logical extraction, stating that mobile devices require a complete bit-for-bit forensic image and that logical extraction alone is insufficient. It also notes the scope includes personal devices and sensitive/deleted/app/location/browser data, with careful coordination and lawful/consensual acquisition, acknowledging the heightened intrusiveness of imaging personal devices.

### C-023

ISSUE_009: Identifies inconsistent use of 'documents,' 'records,' 'materials' ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L198))

- **Sonnet 4.6: Fail.** The agent's memo does not identify or discuss the terminological inconsistency between 'documents,' 'records,' and 'materials' as used interchangeably in operative paragraphs versus their distinct definitions in the Definitions section (Paragraph 3) of the Preservation Notice. The memo is thorough in many respects but never flags this specific ambiguity.
- **GPT-5.5: Fail.** The memo does not identify that the Preservation Notice uses “documents,” “records,” and “materials” interchangeably in operative provisions while defining them with distinct scopes in Paragraph 3, nor does it flag the resulting ambiguity. It identifies other ambiguities/discrepancies, but not this terminological inconsistency.

### C-024

ISSUE_009: Recommends applying broadest definition uniformly ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L206))

- **Sonnet 4.6: Fail.** The criterion requires the memo to recommend applying the broadest definition uniformly across all operative paragraphs to handle terminological inconsistency, in order to avoid preservation gaps. Reviewing the memo, it does address the Exhibit B category count discrepancy (notice says 36 categories but Exhibit B enumerates only 34) and states 'This discrepancy does not narrow the express general duty; counsel should seek written clarification while preserving broadly.' It also notes that the listed categories are not exhaustive and that the duty is broader than specific examples. However, the memo does not explicitly recommend applying the 'broadest definition uniformly across all operative paragraphs' as a general principle for handling terminological inconsistencies throughout the document. The guidance is piecemeal rather than a systematic recommendation to apply the broadest definition uniformly. There is no explicit statement recommending that wherever there is terminological inconsistency, the broadest definition should be applied uniformly across all operative paragraphs. The memo's approach is to preserve broadly and seek clarification, but it does not frame this as a uniform definitional approach across all operative paragraphs.
- **GPT-5.5: Fail.** The memo repeatedly advises preserving broadly and not narrowing ambiguous categories, but it does not specifically address a terminological inconsistency or recommend applying the broadest definition uniformly across all operative paragraphs to avoid preservation gaps.

### C-025

ISSUE_010: Assesses backup tape preservation burden and proportionality ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L214))

- **Sonnet 4.6: Fail.** The memo addresses backup tape preservation in several places (Section 4, Section 5.1, Section 3.3) but only instructs preservation of backup tapes and suspension of the 90-day rotation cycle. It does not discuss proportionality of the backup tape preservation obligation, does not analyze whether the same data exists in more accessible form rendering tape preservation burdensome, and does not reference Zubulake v. UBS Warburg or any analogous principle that preservation of backup tapes is disfavored when accessible copies exist. The criterion specifically requires a proportionality analysis of the backup tape obligation, which is entirely absent from the memo.
- **GPT-5.5: Fail.** The memo identifies the obligation to preserve backup tapes/images/archives and suspend the 90-day recycling/rotation, and it discusses investigating legacy tape availability. However, it does not analyze burden or proportionality of preserving all backup tapes from January 2019 forward, nor does it reference the general Zubulake-type principle that preserving backup tapes is often disfavored where the same data exists in accessible form. Therefore it does not satisfy ISSUE_010.

### C-026

ISSUE_010: Notes backup tapes may be sole source due to migration loss ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L222))

- **Sonnet 4.6: Pass.** Section 5.1 explicitly states: 'Treat server disks as potentially the only surviving source unless proved otherwise.' It also notes that the missing ~340,000 emails 'exists only on six decommissioned Dell PowerEdge servers at Sentinel Records Management' and that 'IT is uncertain whether pre-December 2021 legacy backup tapes survived or were recycled.' The memo connects the email migration data loss to the criticality of preserving the legacy servers/backup tapes as potentially the sole remaining source for custodian data, satisfying the criterion.
- **GPT-5.5: Fail.** The memo clearly connects the migration loss to preservation of legacy sources and says to investigate and preserve any surviving legacy backup tapes, but it frames the six decommissioned Exchange servers—not backup tapes—as the potentially only surviving source. It does not expressly note that backup tapes themselves may be the sole remaining source for certain custodian emails due to the migration loss or emphasize that this makes backup tape preservation critical despite proportionality concerns.

### C-027

ISSUE_011a: Identifies Linden & Pruitt conflict due to prior representation of Dr. Osei ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L230))

- **Sonnet 4.6: Fail.** The memo in Section 5.4 states: 'Linden & Pruitt, P.A. as former regulatory counsel (approximately 2020--mid-2024) now conflicted out, with Dr. Osei as primary business contact.' This identifies Linden & Pruitt as conflicted out and connects them to Dr. Osei. However, the criterion specifically requires identifying that the conflict is 'due to prior representation of Dr. Franklin Osei.' The memo describes Dr. Osei as the 'primary business contact' for Linden & Pruitt, not as someone they represented. The memo does not explicitly state that Linden & Pruitt is conflicted out because they previously represented Dr. Osei — it merely notes Dr. Osei was the primary business contact. The conflict reason (prior representation of Dr. Osei) is not clearly stated. That said, the memo does link the conflict to Dr. Osei's role as primary business contact with the firm, which implies a prior representation relationship. The criterion asks whether the memo identifies that Linden & Pruitt is conflicted out 'due to prior representation of Dr. Franklin Osei.' The memo says they are 'conflicted out' and identifies Dr. Osei as the primary business contact, but does not explicitly state the conflict arises from prior representation of Dr. Osei as a client. This is ambiguous but leans toward not fully satisfying the criterion as described.
- **GPT-5.5: Fail.** The memo notes that Linden & Pruitt, P.A. is “former regulatory counsel” and “now conflicted out,” and mentions Dr. Osei as the primary business contact, but it does not identify the conflict as being due to prior representation of Dr. Franklin Osei personally.

### C-028

ISSUE_011b: Identifies that privileged Linden & Pruitt communications may be swept into preservation scope ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L238))

- **Sonnet 4.6: Pass.** Section 5.4 of the memo explicitly addresses Linden & Pruitt, P.A. as former regulatory counsel (approximately 2020–mid-2024) now conflicted out, and states that all potentially privileged files and metadata must be preserved, with a segregated access and independent counsel-led privilege protocol. It also notes that conflicted former counsel should not conduct the privilege review. Section 7, item 9 reiterates implementing a segregated privilege review for communications with Linden & Pruitt. The memo thus identifies that Linden & Pruitt communications may be swept into preservation scope and creates privilege complications, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly discusses privileged/former-counsel records, identifies Linden & Pruitt as former regulatory counsel now conflicted out, notes that preservation applies regardless of privilege, and recommends preserving potentially privileged files while using a segregated privilege protocol. It also lists outside/regulatory counsel communications, including Linden & Pruitt and Velcara-related matters, within the preservation scope.

### C-029

ISSUE_011: Recommends protocol for handling privileged materials ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L246))

- **Sonnet 4.6: Pass.** Section 5.4 of the memo explicitly addresses privileged and former-counsel records, noting that Linden & Pruitt, P.A. is former regulatory counsel that is now conflicted out. The memo recommends implementing 'an independent counsel-led privilege protocol,' segregating access, and specifically states 'Do not ask conflicted former counsel to conduct the privilege review.' Item 9 in Section 7 further reinforces this by calling for 'segregated privilege review for communications with HTM and Linden & Pruitt.' This satisfies the criterion of recommending a protocol for handling potentially privileged materials involving the now-adverse former counsel relationship with Linden & Pruitt.
- **GPT-5.5: Pass.** The memo expressly addresses Linden & Pruitt as former regulatory counsel now conflicted out and recommends preserving privileged materials, segregating access, using an independent counsel-led privilege protocol, and not asking conflicted former counsel to conduct the review. It also lists an open item to implement segregated privilege review for Linden & Pruitt materials.

### C-030

ISSUE_012: Identifies RPAF as separate legal entity with preservation implications ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L254))

- **Sonnet 4.6: Pass.** Section 5.3 of the memo explicitly identifies RPAF as a separate 501(c)(3) with an independent board, separate systems/records and retention practices. It notes that three of five directors are Ridgeline officers or designees and two are independent, and that Richard Blaine has no authority over RPAF records. The memo states that 'board approval may be needed for a direct RPAF preservation directive,' and instructs counsel to 'promptly assess control and arrange a separate written hold directed to RPAF's board/executive director if appropriate.' This clearly addresses RPAF's separate legal entity status and its implications for preservation obligations, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly discusses RPAF as a separate 501(c)(3) with an independent board, separate systems/records and retention practices, and notes that board approval may be needed for a preservation directive. It also frames preservation obligations in terms of Ridgeline’s possession, custody, or control and advises assessing control/governance before directing RPAF, satisfying the criterion.

### C-031

ISSUE_012: Notes RPAF board independence and coordination requirement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L262))

- **Sonnet 4.6: Pass.** Section 5.3 explicitly notes that RPAF has an independent board with three Ridgeline-affiliated directors and two independent directors, that Richard Blaine has no authority over RPAF records, and that 'board approval may be needed for a direct RPAF preservation directive.' It then instructs that Ridgeline should preserve its own copies immediately and 'through counsel, promptly assess control and arrange a separate written hold directed to RPAF's board/executive director if appropriate.' This directly addresses the need for separate coordination with RPAF governance rather than simply directing RPAF to comply.
- **GPT-5.5: Pass.** The memo expressly states that RPAF is a separate 501(c)(3) with an independent board, including two independent directors, and explains that board approval may be needed for a direct preservation directive. It recommends preserving Ridgeline-held records immediately while coordinating through counsel with RPAF’s board/executive director for a separate hold as appropriate.

### C-032

Correctly states the 14-day confirmation deadline as March 17, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L270))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 2 (Deadlines and mandatory deliverables) that the March 17, 2025 deadline is '14 calendar days' from the cover letter and Notice ¶ 45, requiring written certification to AUSA Faulkner and Trial Attorney Gutierrez. This is also referenced in the executive summary and the sequenced checklist. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo expressly identifies the 14-day written certification/confirmation deadline as March 17, 2025 in the executive summary, deadlines table, and checklist.

### C-033

Correctly states the 10-day third-party vendor deadline as March 13, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L278))

- **Sonnet 4.6: Pass.** The memo clearly states in Section 2 (Deadlines and mandatory deliverables) that the March 13, 2025 deadline (10 calendar days) requires issuing written preservation notices to all third parties, explicitly naming Veeva Systems, SAP SE, Concur Technologies, and IntegriCall Services. This is also referenced in the sequenced checklist in Section 6.1. The date and the 10-calendar-day timing are both correctly stated.
- **GPT-5.5: Pass.** The memo explicitly identifies the third-party vendor preservation notice deadline as March 13, 2025, described as 10 calendar days, and lists vendors including Veeva, Concur, and IntegriCall Services.

### C-034

Correctly states the 21-day mobile device imaging deadline as March 24, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L286))

- **Sonnet 4.6: Pass.** The memo explicitly states the March 24, 2025 deadline for forensic imaging of mobile devices in multiple places: in the Executive Summary ('forensic imaging of all 23 named custodians' qualifying mobile devices by March 24, 2025'), in the Deadlines table ('March 24, 2025 / 21 calendar days; cover letter and Notice ¶¶ 17, 40 / Complete forensic imaging---not merely logical extraction---of all personal and company-issued mobile devices of the 23 named custodians'), and in the sequenced checklist ('By March 24 / Complete bit-for-bit forensic imaging...'). The criterion is fully satisfied.
- **GPT-5.5: Pass.** The memo expressly identifies March 24, 2025 as the 21-day deadline to complete forensic imaging of all 23 named custodians' qualifying mobile devices.

### C-035

Identifies the Relevant Period as January 1, 2019 to March 3, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L294))

- **Sonnet 4.6: Pass.** Section 3.3 of the memo explicitly states: 'General Relevant Period: January 1, 2019 through March 3, 2025, and continuing thereafter for newly created/received responsive information. (Notice ¶ 12, Exhibit A, ¶ 32.)' This correctly identifies the Relevant Period as January 1, 2019 to March 3, 2025, citing Notice ¶ 12 as required.
- **GPT-5.5: Pass.** The memo expressly states in Section 3.3 that the General Relevant Period is January 1, 2019 through March 3, 2025, citing Notice ¶ 12.

### C-036

Identifies ESI preservation requirement including specific platforms ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L302))

- **Sonnet 4.6: Pass.** The memo explicitly identifies ESI preservation in native format with metadata intact (Section 4, 'Native files / metadata' row). It specifically mentions: Slack (¶37, Section 4), Microsoft Teams (¶37, Section 4), email including deleted items and archive folders (¶36, Section 4), SharePoint (¶39, Section 4), OneDrive (¶39, Section 4), Salesforce CRM (¶38, Section 4), Veeva Vault/Veeva CRM (¶38, Section 4), and SAP ERP (¶38, Section 4). That is eight of the listed platforms, well exceeding the threshold of four.
- **GPT-5.5: Pass.** The memo expressly requires preserving ESI in native format with metadata intact and identifies numerous specific platforms, including Slack, Microsoft Teams, email with deleted/archived folders, SharePoint, OneDrive, Salesforce CRM, Veeva Vault/CRM, and SAP ERP.

### C-037

Identifies backup tape rotation suspension obligation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L310))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the obligation to suspend backup tape rotation in multiple places. In Section 3.3, it states: 'all backup tapes/images/archives containing data from January 1, 2019–March 3, 2025, and the currently described 90-day rotation, must be preserved.' In Section 4 (the technology table), under 'Backups': 'Preserve backup tapes, images and archives for the stated period; immediately stop 90-day recycling, overwrite, degaussing or other disposal, including media at Sentinel or another vendor. (¶ 41.)' The checklist in Section 6.1 also references freezing all scheduled deletion and backup rotation immediately. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly states that all backup tapes/images/archives containing data from January 1, 2019 through March 3, 2025 and the 90-day rotation must be preserved, and instructs the company to immediately stop 90-day recycling/overwrite/degaussing or other disposal.

### C-038

Identifies paper records preservation obligation at Durham headquarters ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L318))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Durham headquarters as a paper records location in Section 3.1: 'Paper locations specifically identified: named custodians' work areas, central filing/records rooms, Durham headquarters, Atlanta field office, and any offsite paper storage.' It also references this in Section 4 under the Paper records row: 'Physically secure and restrict access at custodian work areas, Durham and Atlanta locations, central filing, and offsite storage.' This satisfies the criterion of identifying the obligation to physically secure paper files at Durham headquarters.
- **GPT-5.5: Pass.** The memo expressly identifies paper records obligations, including named custodians' work areas, central filing/records rooms, and the Durham headquarters, and states they should be physically secured and access restricted.

### C-039

Identifies paper records preservation obligation at Atlanta field office ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L326))

- **Sonnet 4.6: Pass.** The memo explicitly mentions the Atlanta field office in Section 3.1 under paper locations: 'Paper locations specifically identified: named custodians' work areas, central filing/records rooms, Durham headquarters, Atlanta field office, and any offsite paper storage. Secure access, inventory offsite holdings, and instruct storage operators to hold them (¶ 44).' This clearly identifies the obligation to physically secure paper files at the Atlanta field office.
- **GPT-5.5: Pass.** The memo expressly identifies paper records at the Atlanta field office as within scope and instructs the company to physically secure/restrict access to paper records at Atlanta locations.

### C-040

Names the three specific third-party vendors requiring preservation notices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L334))

- **Sonnet 4.6: Pass.** The criterion requires identification of three specific vendors: Veeva CRM, Concur expense system, and IntegriCall Services. The memo mentions all three: Veeva Systems (in the March 13 deadline row), Concur Technologies (same row), and IntegriCall Services (same row). Additionally, IntegriCall is mentioned in the subject matter table under Compliance and audits. All three are present in the output.
- **GPT-5.5: Pass.** The memo identifies all three required third-party vendors/platforms: Veeva/Veeva CRM, Concur/Concur expense reports, and IntegriCall Services/hotline records, including in the vendor notice sections.

### C-041

Identifies the nine subject-matter areas or 34 document categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L342))

- **Sonnet 4.6: Pass.** The memo's Section 3.2 contains a table that catalogs document categories organized by subject matter. It clearly identifies: (1) KOL program administration (Speaker Program administration), (2) Speaker pay/FMV (Speaker compensation/FMV analyses), (3) HCP selection/due diligence, (4) RPAF operations (Patient Assistance Fund operations), (5) Compliance and audits (Compliance monitoring/audits), (6) Financial/accounting (Financial records/accounting), (7) Marketing/promotion (Marketing/promotional materials for Velcara), (8) Government inquiry/counsel (Internal communications regarding government inquiry), and (9) Systems and infrastructure (Data systems/IT infrastructure). All nine subject-matter areas are identified, well exceeding the threshold of five required for a PASS.
- **GPT-5.5: Pass.** The memo includes a subject-matter table cataloging the Exhibit B categories and identifies all nine required areas: KOL/Speaker Program administration, speaker compensation/FMV, HCP selection/due diligence, RPAF operations, compliance/audits, financial/accounting, marketing/promotional materials, government inquiry/counsel communications, and systems/IT infrastructure.

### C-042

Identifies conflict between retention policy and preservation obligations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L350))

- **Sonnet 4.6: Pass.** The memo in Section 5.2 explicitly references RDG-LGL-007 and identifies specific retention schedule conflicts. It states that the policy sets speaker program records (Category L) and patient assistance records (Category M) at six years, compliance records (K) at six years, general correspondence (E) at three years, and sales field records (F) at two years. It notes that the destruction email assigned KOL event files a three-year period and RPAF routine correspondence a three-year period, and flags that these categories may not have been eligible for destruction under the provided policy. The memo also notes the preservation notice requires preservation from January 1, 2019 forward (and January 1, 2017 for financial records), which conflicts with the shorter 2-year and 3-year retention schedules in RDG-LGL-007. The criterion asks specifically whether the memo identifies that general correspondence has a 3-year retention and sales call records have a 2-year retention, and that these conflict with the preservation notice's requirement to preserve from January 1, 2019 forward. The memo does identify both the 3-year general correspondence period (Category E) and the 2-year sales field records period (Category F) from RDG-LGL-007, and the preservation notice's January 1, 2019 start date is clearly stated in Section 3.3. The conflict between these schedules and the preservation obligations is explicitly identified.
- **GPT-5.5: Pass.** The memo expressly states that the Preservation Notice overrides RDG-LGL-007 and routine destruction practices, identifies the Preservation Notice’s general relevant period as January 1, 2019 through March 3, 2025 and continuing, and specifically notes RDG-LGL-007’s retention periods for general correspondence at three years and sales field records at two years. This identifies the relevant retention-policy schedules and their conflict with the preservation obligation to preserve materials from January 1, 2019 forward.

### C-043

Memo includes a prioritized action item list organized by urgency ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L358))

- **Sonnet 4.6: Pass.** Section 6.1 'Sequenced checklist' contains a clearly labeled table with action items grouped by timing tiers: 'Now / first 24 hours', 'Next 24--48 hours', 'By March 13', 'By March 17', 'By March 24', and 'Continuing / before any release'. This is an identifiable section with a heading that organizes action items by deadline/urgency tier, satisfying the criterion.
- **GPT-5.5: Pass.** The memo includes an identifiable prioritized action section, “6.1 Sequenced checklist,” with action items organized by urgency and specific timing tiers such as “Now / first 24 hours,” “Next 24–48 hours,” “By March 13,” “By March 17,” “By March 24,” and “Continuing.” It also includes a deadlines table organized by due date.

### C-044

Action items include correct sequencing of the three deadlines ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L366))

- **Sonnet 4.6: Pass.** The agent's output includes a sequenced checklist in section 6.1 that correctly lists: (1) By March 13 — written hold notices to all relevant vendors; (2) By March 17 — written certification; (3) By March 24 — forensic imaging of mobile devices. This matches the required chronological order. The deadlines are also correctly sequenced in section 2 (the deadlines table) and in the executive summary. All three deadlines are present and in the correct order.
- **GPT-5.5: Pass.** The output includes an action-oriented deadline sequence and checklist that correctly lists the three key deadlines in chronological order: March 13, 2025 for third-party vendor notices, March 17, 2025 for written certification/confirmation of the litigation hold, and March 24, 2025 for forensic imaging of mobile devices.

### C-045

References Grand Jury No. 24-GJ-0387 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L374))

- **Sonnet 4.6: Pass.** The memo explicitly references Grand Jury No. 24-GJ-0387 in the header ('DOJ Litigation Hold and Document Preservation Notice --- Grand Jury No. 24-GJ-0387') and again in Section 8 ('Grand Jury Investigation No. 24-GJ-0387').
- **GPT-5.5: Pass.** The memo explicitly references “Grand Jury No. 24-GJ-0387” in the title and source references.

### C-046

References Anti-Kickback Statute and/or False Claims Act ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L382))

- **Sonnet 4.6: Fail.** The memo does not mention the Anti-Kickback Statute or the False Claims Act anywhere in its text. It references healthcare fraud generally and describes KOL programs, HCP payments, and RPAF operations, but never names either statute as the basis for the investigation.
- **GPT-5.5: Fail.** The memo does not mention the Anti-Kickback Statute or the False Claims Act. It only refers generally to healthcare fraud and related preservation categories, which does not satisfy the criterion.

### C-047

Identifies AUSA Brendan K. Faulkner as the DOJ contact for confirmation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L390))

- **Sonnet 4.6: Pass.** The memo explicitly identifies AUSA Brendan K. Faulkner in connection with the written certification/confirmation obligation. In Section 2 (Deadlines and mandatory deliverables), the March 17, 2025 row states: 'Written certification to Brendan K. Faulkner and Sonia R. Gutierrez confirming items (a)--(f)...' This directly connects Faulkner to the confirmation obligation.
- **GPT-5.5: Pass.** The memo explicitly states that the March 17 written certification/confirmation must be sent to Brendan K. Faulkner and Sonia R. Gutierrez, and elsewhere identifies communications as directed to AUSA Brendan K. Faulkner.

### C-048

Cites specific paragraph numbers from the Preservation Notice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L398))

- **Sonnet 4.6: Pass.** The memo contains numerous specific paragraph number citations from the DOJ Preservation Notice throughout the document. Examples include: ¶¶ 5, 32--33, 52 (deadline table); ¶ 43 (vendor notices); ¶ 45 (certification); ¶¶ 17, 40 (mobile devices); ¶ 46 (impairment notice); ¶¶ 18, 32, 46, 51 (ongoing obligations); ¶¶ 1, 4 (entity reach); ¶ 16, ¶ 13, ¶ 18 (custodians); ¶¶ 23--24 (HCP communications); ¶ 25 (RPAF); ¶ 26 (compliance); ¶ 27 (financial); ¶ 28 (marketing); ¶ 29 (government inquiry); ¶ 30 (systems); ¶¶ 31--32 (related compounds); ¶ 12 (time period); ¶ 47 (extended financial period); ¶¶ 41, 47 (backups); ¶ 35 (native files); ¶ 36 (email); ¶ 37 (messaging); ¶ 38 (enterprise apps); ¶ 39 (cloud); ¶¶ 17, 40 (mobile); ¶ 41 (backups); ¶ 42 (legacy systems); ¶ 44 (paper); ¶ 43 (vendors); ¶ 19 (subject matter); ¶ 4 (RPAF). There are well over 4 distinct paragraph number references, easily satisfying the criterion.
- **GPT-5.5: Pass.** The memo cites numerous specific Preservation Notice paragraph numbers when describing obligations and issues, including ¶¶ 5, 12, 17, 19, 23, 24, 31, 32, 40, 43, 45, 46, 47, 51, and others. This exceeds the requirement of at least 4 distinct paragraph references.

### C-049

Identifies the obligation to preserve files and data for 23 named custodians ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L406))

- **Sonnet 4.6: Pass.** The memo clearly identifies the obligation to preserve files and data for 23 named custodians in multiple sections. Section 1 states '23 named custodians' and breaks down the composition (9 senior employees, 7 Exhibit C sales managers, 2 role-based employees, 5 external HCPs). Section 3.1 details all 23 custodians by name and category. Section 4 includes a row specifically about mobile devices for 'all 23 named custodians.' The deadline table in Section 2 references forensic imaging of all 23 named custodians' devices. The checklist in Section 6.1 also references the '23-custodian roster.'
- **GPT-5.5: Pass.** The memo explicitly identifies a 23-custodian preservation obligation, describes the 23 total custodians, lists categories of custodians, and repeatedly states that files/data such as email, mobile devices, cloud repositories, and other repositories must be preserved for all 23 named custodians.

### C-050

Names at least 5 key custodians from the 23 named custodians ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L414))

- **Sonnet 4.6: Pass.** The memo explicitly names all 9 senior custodians: Dr. Priya Venkataraman, Marcus Ellsworth, Diane Cho-Rosen, Dr. Franklin Osei, Gregory 'Greg' Hsu, Amanda Terrell, Richard Blaine, Dr. Katerina Novak, and Luis Delgado. This far exceeds the minimum of 5 required by the criterion.
- **GPT-5.5: Pass.** The memo specifically names all 9 listed key custodians, including Dr. Priya Venkataraman, Marcus Ellsworth, Diane Cho-Rosen, Dr. Franklin Osei, Gregory Hsu, Amanda Terrell, Richard Blaine, Dr. Katerina Novak, and Luis Delgado, exceeding the requirement of at least 5.

### C-051

Addresses the 5 non-employee HCP consultants in Exhibit D ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L422))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the 5 external HCP consultants in Exhibit D by name (Dr. Raymond T. Whitford, Dr. Ingrid M. Svensson, Dr. Oscar L. Famuyide, Dr. Hannah J. Prescott, Dr. Samuel K. Anand) and states that Ridgeline-held communications and engagement, contract, payment, 1099, expense, and travel records must be preserved. It also notes the notice calls for affirmative identification/collection of communications with these HCPs and hold instructions to Ridgeline employees who had the most frequent contact.
- **GPT-5.5: Pass.** The memo explicitly identifies the 5 external HCP consultants/speakers in Exhibit D by name and states that Ridgeline-held communications and related records with these individuals must be preserved.

### C-052

Identifies Velcara (ridgenostat) as the drug at issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/task.json#L430))

- **Sonnet 4.6: Pass.** The memo explicitly mentions Velcara multiple times throughout the document, including in the subject matter table ('Velcara efficacy, safety, dosing...'), financial/accounting section ('Velcara revenue recognition, sales, prescriptions'), marketing/promotion section, and other places. It also mentions ridgenostat as a related compound in the subject matter table under 'Related compounds / later-created information.' Both drug names are clearly identified in the memo.
- **GPT-5.5: Pass.** The memo repeatedly mentions Velcara and also references ridgenostat/related compounds in the preservation scope, identifying the drug at issue in the investigation and obligations.
