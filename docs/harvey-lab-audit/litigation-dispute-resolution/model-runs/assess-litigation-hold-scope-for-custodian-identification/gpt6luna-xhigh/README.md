# GPT-6 Luna (xhigh): Assess Litigation Hold Scope for Custodian Identification — Custodian Recommendation Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/assess-litigation-hold-scope-for-custodian-identification/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 47 of 50 criteria; GPT-5.5 passed 48 of 50 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [litigation-hold-memo.docx](output/litigation-hold-memo.docx) ([read as Markdown](output/litigation-hold-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Custodian: Darren Kovach identified as custodian | Pass | Pass |
| [C-002](#c-002) | Custodian: Renata Sokolova identified as custodian | Pass | Pass |
| [C-003](#c-003) | Custodian: Graham Ellicott identified as custodian | Pass | Pass |
| [C-004](#c-004) | Custodian: Janet Purdy identified as custodian | Pass | Pass |
| [C-005](#c-005) | Custodian: Tomás Herrera identified as custodian | Pass | Pass |
| [C-006](#c-006) | Custodian: Li Wei Chen identified as custodian | Pass | Pass |
| [C-007](#c-007) | Custodian: Marcus Ainsley identified as custodian (ISSUE_009) | Pass | Pass |
| [C-008](#c-008) | Ainsley: Board-level privilege/governance concerns flagged | Pass | Pass |
| [C-009](#c-009) | Custodian: Regional sales managers (Collings, Muñoz, Patwardhan) evaluated | Pass | Pass |
| [C-010](#c-010) | Custodian: Frank Jessup evaluated as potential custodian | Pass | Pass |
| [C-011](#c-011) | Internal investigation interviewees linked to custodian rationale | Pass | Pass |
| [C-012](#c-012) | Teams chat 90-day auto-purge identified as spoliation risk | Pass | Pass |
| [C-013](#c-013) | Teams chat: Specific timeline of likely data loss assessed | Pass | Pass |
| [C-014](#c-014) | Teams: Immediate suspension of retention policy recommended | Pass | Pass |
| [C-015](#c-015) | Teams: Forensic recovery investigation recommended | Pass | Pass |
| [C-016](#c-016) | Incomplete email archive migration flagged as risk | Pass | Pass |
| [C-017](#c-017) | Veritas Enterprise Vault identified as separate hold target | Pass | Pass |
| [C-018](#c-018) | Recommendation to verify if key custodians' mailboxes were in the affected 15% | Pass | Pass |
| [C-019](#c-019) | NXF-FS01 file server decommissioning flagged as imminent risk | Pass | Pass |
| [C-020](#c-020) | NXF-FS01: Preservation action recommended before decommissioning | Pass | Pass |
| [C-021](#c-021) | Kovach personal iPhone / BYOD preservation issue identified | Pass | Pass |
| [C-022](#c-022) | Recommendation to send preservation demand to Kovach's counsel re personal device | Pass | Pass |
| [C-023](#c-023) | Kovach device may hold unique surviving copies of communications | Pass | Pass |
| [C-024](#c-024) | Salesforce auto-deletion of inactive records flagged | Pass | Pass |
| [C-025](#c-025) | Salesforce: Recommendation to suspend auto-deletion or export data | Pass | Pass |
| [C-026](#c-026) | SEC inquiry overlap recognized — coordinated hold recommended | Pass | Pass |
| [C-027](#c-027) | SEC inquiry may require broader custodian set | Pass | Pass |
| [C-028](#c-028) | Pinnacle Hartwell engagement scope gap noted (SEC not covered) | **Fail** | **Fail** |
| [C-029](#c-029) | Temporal proximity (13 days) between complaint and PIP flagged | Pass | Pass |
| [C-030](#c-030) | Priority preservation of decision-maker communications in July 2–15 window | Pass | Pass |
| [C-031](#c-031) | Duty to preserve trigger date analyzed (pre-demand letter) | Pass | Pass |
| [C-032](#c-032) | Preservation gap between trigger date and vendor engagement assessed | Pass | Pass |
| [C-033](#c-033) | SOX Section 806 whistleblower protections flagged | Pass | Pass |
| [C-034](#c-034) | SOX implications for preservation breadth noted | **Fail** | Pass |
| [C-035](#c-035) | Data source: Microsoft 365 / Exchange email included | Pass | Pass |
| [C-036](#c-036) | Data source: Microsoft Teams included | Pass | Pass |
| [C-037](#c-037) | Data source: Salesforce CRM included | Pass | Pass |
| [C-038](#c-038) | Data source: SAP S/4HANA ERP included | Pass | Pass |
| [C-039](#c-039) | Data source: NXF-FS01 legacy file server included | Pass | Pass |
| [C-040](#c-040) | Data source: Physical HR/personnel files included | Pass | Pass |
| [C-041](#c-041) | Custodian: Monica Tran-Nguyen identified as custodian | **Fail** | **Fail** |
| [C-042](#c-042) | Immediate action items distinguished from routine hold steps | Pass | Pass |
| [C-043](#c-043) | Accurate citation of Teams chat retention as 90 days | Pass | Pass |
| [C-044](#c-044) | Accurate citation of Salesforce auto-delete as 18 months for inactive records | Pass | Pass |
| [C-045](#c-045) | Accurate date: NXF-FS01 decommission January 31, 2025 | Pass | Pass |
| [C-046](#c-046) | Accurate date: Email migration on April 1, 2024 | Pass | Pass |
| [C-047](#c-047) | Accurate citation of 15% incomplete mailbox migration rate | Pass | Pass |
| [C-048](#c-048) | Ridgeway Forensics referenced as engaged e-discovery vendor | Pass | Pass |
| [C-049](#c-049) | Preservation hold on internal investigation work product addressed | Pass | Pass |
| [C-050](#c-050) | Teams channel messages distinguished from chat messages | Pass | Pass |

## Judge reasoning

### C-001

Custodian: Darren Kovach identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L19))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Darren T. Kovach as a custodian in Section 3, listing him as 'Former VP, Sales Americas' and noting he is the 'primary complainant and custodian of alleged complaint communications, sales directives, texts, and supporting records.' The memo covers both his Nexfield-controlled data and his personal iPhone, and discusses preservation of his communications about revenue concerns and termination throughout the document.
- **GPT-5.5: Pass.** The memo explicitly identifies Darren T. Kovach, former VP, Sales Americas, in the custodian table as a custodian for both matters, describing him as the primary complainant and custodian of complaint communications, sales directives, texts, and supporting records, and directs preservation of his mailbox, files, laptop, and personal iPhone work data.

### C-002

Custodian: Renata Sokolova identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L27))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Renata Sokolova (CFO) as a custodian in Section 3, noting she is the 'alleged recipient of June 14/July 2 complaints' and covers 'financial reporting, forecasts, revenue decisions.' This satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly lists Renata Sokolova as a custodian in the Custodian Identification table, identifies her as CFO, notes she was the alleged recipient of Kovach's June 14 and July 2 complaints, and describes her role in financial reporting, forecasts, and revenue decisions.

### C-003

Custodian: Graham Ellicott identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L35))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Graham Ellicott (CEO) as a custodian in Section 3, noting he 'approved PIP and made termination decision; executive sales/revenue communications' and directing preservation of 'all communications and records, especially July 2--15 decision period, PIP/termination drafts, communications with Sokolova/Purdy, Audit Committee, and sales leadership.' This satisfies the criterion.
- **GPT-5.5: Pass.** The memo lists Graham Ellicott — CEO in the Custodian Identification table, notes he approved the PIP and made the termination decision, and directs preservation of PIP/termination drafts and communications with key decision-makers. This satisfies the criterion that he be identified as a custodian and key termination decision-maker.

### C-004

Custodian: Janet Purdy identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L43))

- **Sonnet 4.6: Pass.** Janet Purdy is explicitly listed as a custodian in Section 3 of the memo: 'Janet Purdy --- VP, HR' with the basis 'KOV-EMP; PIP, check-ins, termination, personnel-file custodian.' The memo notes her role in the PIP process, check-ins, termination, and as personnel-file custodian, which satisfies the criterion requiring identification of her role in managing the PIP process and coordinating the termination decision.
- **GPT-5.5: Pass.** The memo lists Janet Purdy as “VP, HR” in the custodian identification table and ties her to the PIP, check-ins, termination, personnel file, PIP drafts, termination/release records, and communications with decision-makers.

### C-005

Custodian: Tomás Herrera identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L51))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Tomás Herrera as a custodian in Section 3, describing him as 'Sales Operations Director / interim VP Sales' and noting he was a 'direct report to Kovach, successor, Salesforce and sales-operations access.' The preservation direction includes Salesforce records/reports, territory and pipeline data, sales directives, forecast files, channel communications, and transferred/forwarded Kovach emails. This satisfies the criterion of identifying Herrera as a custodian who reported to Kovach, took over the interim VP Sales role, and possesses sales data and channel partner communications.
- **GPT-5.5: Pass.** The memo explicitly lists “Tomás Herrera — Sales Operations Director / interim VP Sales” as a custodian, states he was a direct report to Kovach and successor/interim VP Sales, and directs preservation of Salesforce records/reports, channel communications, sales directives, and related sales data.

### C-006

Custodian: Li Wei Chen identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L59))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Li Wei Chen (Controller) as a custodian in Section 3, noting he is an 'alleged June 28 complaint recipient' and responsible for 'close, revenue entries, reserves, and Q3 return-rate analysis.' This satisfies the criterion requiring Chen to be listed as a custodian with reference to revenue recognition entries and the June 28 discussion with Kovach.
- **GPT-5.5: Pass.** The memo expressly lists Li Wei Chen as a custodian, identifies him as Controller, notes he was the alleged June 28 complaint recipient, and ties him to revenue entries/revenue recognition-related records.

### C-007

Custodian: Marcus Ainsley identified as custodian (ISSUE_009) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L67))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Marcus Ainsley as a custodian in Section 3 (Custodian Identification), noting he is the 'Audit Committee Chair' who 'received Aug. 5 complaint and directed investigation.' Section 7 further elaborates that 'Marcus Ainsley must be included as a custodian' and references his receipt of Kovach's August 5 letter and direction of the Audit Committee investigation. All required elements are present.
- **GPT-5.5: Pass.** The memo explicitly lists Marcus Ainsley as “Audit Committee Chair” in the custodian table, stating that he received the August 5 complaint and directed the investigation, and further emphasizes that he must be included as a custodian.

### C-008

Ainsley: Board-level privilege/governance concerns flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L75))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Ainsley's governance and privilege sensitivities in multiple places. Section 7 ('Special Coordination: Audit Committee, Privilege, and SEC Response') is dedicated to this issue, stating that Ainsley must be included as a custodian but that his records may contain privileged material, and recommending a separate collection protocol with restricted repository, a factual/non-privileged review track, and a separate potential-privilege/work-product track. The custodian table also notes 'Apply privilege protocol; do not broadly collect unrelated personal materials' for Ainsley. The memo clearly flags governance sensitivities and recommends a specific protocol to protect privileged board communications during collection.
- **GPT-5.5: Pass.** The memo specifically includes Marcus Ainsley as a custodian while flagging Audit Committee, privilege, and governance sensitivities. It recommends a controlled Ainsley collection protocol, restricted repositories, separate privilege/work-product review tracks, preservation of board/committee materials, and counsel-led review before access or production.

### C-009

Custodian: Regional sales managers (Collings, Muñoz, Patwardhan) evaluated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L83))

- **Sonnet 4.6: Pass.** The memo explicitly identifies all three regional sales managers as custodians in Section 3: Brett Collings (Regional Sales Manager, Gulf Coast), Diana Muñoz (Regional Sales Manager, Southwest), and Raj Patwardhan (Regional Sales Manager, Northeast). Each is listed with their matter basis (SEC-RR and relevant KOV-EMP) and specific preservation directions noting their knowledge of quarter-end shipment practices, channel-loading concerns, and sales directives relevant to the channel-stuffing allegations.
- **GPT-5.5: Pass.** The memo expressly identifies Brett Collings, Diana Muñoz, and Raj Patwardhan as custodians in the custodian table, tying each to SEC-RR/channel sales issues such as shipment targets, Q3 shipments, channel-loading concerns, and acceleration/milestone emails relevant to quarter-end sales practices.

### C-010

Custodian: Frank Jessup evaluated as potential custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L91))

- **Sonnet 4.6: Pass.** Frank Jessup is explicitly listed as a custodian in Section 3 of the memo. He is identified as 'VP, Operations' under 'SEC-RR' with the basis noting 'shipping capacity, extended shifts, ship-ahead arrangements and logistics communications.' The preservation direction includes 'Houston/Dallas shipping records, warehouse releases, dispatch/PO timing, shift records, communications with Sales, and operational notes.' This clearly identifies him as a recommended custodian with knowledge relevant to channel-stuffing/revenue recognition allegations (specifically the operational side of quarter-end shipment acceleration). The criterion requires only that he be identified as a potential or recommended custodian with relevant knowledge, which is satisfied.
- **GPT-5.5: Pass.** The memo expressly lists “Frank Jessup — VP, Operations” in the custodian identification table as an SEC-RR custodian, citing his knowledge of shipping capacity, extended shifts, ship-ahead arrangements, and logistics communications relevant to the revenue/channel-stuffing issues. It also states that the internal-investigation interviewees are relevant candidates.

### C-011

Internal investigation interviewees linked to custodian rationale ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L99))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 3: 'The eight interviewees identified in the internal-investigation summary are all relevant candidates; being interviewed is not a reason to exclude an individual.' This directly connects the internal investigation interviewee list to the custodian identification process. The memo also explains throughout that the Pinnacle Hartwell investigation (August–October 2024) is relevant to both the employment/whistleblower claims and the SEC revenue recognition inquiry, and that custodians who hold evidence of revenue practices should be included even if they had no role in Kovach's employment decision. This satisfies the criterion of linking the 8 internal investigation interviewees to the custodian rationale for both matters.
- **GPT-5.5: Pass.** The memo expressly ties the internal investigation interviewees to custodian identification, stating that the eight interviewees in the internal-investigation summary are relevant candidates and should not be excluded merely because they were interviewed. It further explains that custodians with evidence of revenue/channel sales practices should be included even if they were not involved in Kovach’s employment decision, and identifies several sales personnel with quarter-end shipment/return communications relevant to both the Kovach employment matter and SEC revenue-recognition inquiry.

### C-012

Teams chat 90-day auto-purge identified as spoliation risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L107))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the Teams 90-day auto-purge as a high-priority spoliation risk. In Section 4 (Data Sources), it states the 90-day chat purge remains active and that 'as of Nov. 6, messages older than about Aug. 8 likely purged. June/July complaint communications may be gone if sent by chat.' In Section 5 (Spoliation and Data-Loss Assessment), it lists 'Teams chat --- confirmed active purge; likely past loss' as HIGH/immediate priority, noting that 'if complaints or quarter-end directives were sent by Teams in June/July, the content is likely unavailable in the tenant.' This directly addresses the criterion's requirement that the memo identify the 90-day auto-purge and the spoliation risk from likely-purged June–August 2024 chats between Kovach and others regarding revenue concerns.
- **GPT-5.5: Pass.** The memo explicitly states that Teams chats are subject to a 90-day purge, that the purge remained active as of early November, and that messages older than about August 8—including possible June/July complaint or revenue-concern chats involving Kovach and others—were likely purged, identifying this as a high/immediate spoliation/data-loss risk.

### C-013

Teams chat: Specific timeline of likely data loss assessed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L115))

- **Sonnet 4.6: Pass.** The memo explicitly states in the Teams section of the Data Sources table: 'As of Nov. 6, messages older than about Aug. 8 likely purged. June/July complaint communications may be gone if sent by chat.' This directly calculates the 90-day window from the current date and identifies that the June 14, June 28, and July 2 complaint dates fall outside that window and are likely already purged. The spoliation section reinforces this: 'As of Nov. 6, 90-day policy likely purged server-side chats older than about Aug. 8. If complaints or quarter-end directives were sent by Teams in June/July, the content is likely unavailable in the tenant.' This satisfies the criterion of specifically assessing the timeline of likely data loss rather than flagging the risk generically.
- **GPT-5.5: Pass.** The memo specifically calculates the 90-day Teams purge window, noting that as of Nov. 6 messages older than about Aug. 8 were likely purged, and it expressly states that June/July complaint communications may be gone if sent via Teams. This covers the critical June 14, June 28, and July 2 dates as outside the window and likely already purged.

### C-014

Teams: Immediate suspension of retention policy recommended ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L123))

- **Sonnet 4.6: Pass.** The memo explicitly recommends immediately suspending the 90-day Teams chat deletion policy in multiple places. In Section 4 (Data Sources), under Microsoft Teams, the immediate preservation action states: 'Immediately suspend 90-day chat deletion tenant-wide or use a validated equivalent that covers all known/possible custodians.' In Section 6, it instructs IT to 'suspend Teams chat purge.' In the Immediate Milestones section, 'suspend Teams and Salesforce deletion' is listed as a same-day action. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo repeatedly recommends immediate suspension of the Teams 90-day chat purge/retention policy, including in the executive summary, data sources table, workplan, and milestones, to prevent further data loss.

### C-015

Teams: Forensic recovery investigation recommended ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L131))

- **Sonnet 4.6: Pass.** In Section 5 (Spoliation and Data-Loss Assessment), under the Teams chat risk area, the memo explicitly states in the Mitigation/Investigation column: 'Stop purge; preserve surviving chats and logs; search Kovach iPhone through counsel; interview custodians about platform/channel and dates; assess permitted recovery from Microsoft/substrate or other copies.' This directly recommends investigating whether purged Teams chats can be recovered through Microsoft/substrate or other copies, satisfying the criterion.
- **GPT-5.5: Pass.** The memo identifies the active Teams purge and expressly recommends recovery investigation steps, including preserving surviving chats/logs, checking Kovach’s iPhone and other copies, and assessing permitted recovery from Microsoft/substrate with Ridgeway/Microsoft, while also preserving backups/logs. This satisfies the requirement to investigate recoverability of purged Teams chats.

### C-016

Incomplete email archive migration flagged as risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L139))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the Enterprise Vault migration issue in multiple places. In Section 4 (Data Sources), it states: 'Migration validation found 421 of ~2,800 mailboxes with incomplete ingestion; relevant custodians not yet checked. Exchange source servers/storage decommissioned May 15, 2024; original source data unavailable.' It also flags this in Section 5 (Spoliation Risk) as HIGH priority: '421 mailboxes had incomplete ingestion. It is unknown whether Kovach, Sokolova, Chen, or other key custodians are affected.' The 421 out of ~2,800 mailboxes represents approximately 15% of mailboxes with incomplete archive ingestion, and the memo clearly identifies this as creating potential gaps in pre-April 2024 email history for key custodians. The criterion is satisfied.
- **GPT-5.5: Pass.** The memo flags the Enterprise Vault/Exchange-to-M365 migration issue, noting that pre-April 1, 2024 email archive history may have gaps because 421 of approximately 2,800 mailboxes had incomplete ingestion, and it specifically calls for cross-referencing key custodians against the affected-mailbox list.

### C-017

Veritas Enterprise Vault identified as separate hold target ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L147))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Veritas Enterprise Vault (NXF-EV01) as a separate data source requiring preservation. In Section 4, it lists 'Veritas Enterprise Vault, NXF-EV01' as a distinct row in the data sources table, noting it holds pre-April 1, 2024 email archives with indefinite retention, identifies the known risk of 421 mailboxes with incomplete ingestion, and directs immediate preservation actions including holding and preserving the archive, configuration, indexes, migration/validation logs, and remediation log. It also appears in the spoliation risk table in Section 5 as a HIGH priority item. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo explicitly identifies Veritas Enterprise Vault (NXF-EV01) as a separate data source for pre-April 2024 email archives, notes the incomplete migration affecting 421 mailboxes, and directs that the archive, configuration, indexes, migration logs, and remediation logs be held and preserved.

### C-018

Recommendation to verify if key custodians' mailboxes were in the affected 15% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L155))

- **Sonnet 4.6: Pass.** The memo explicitly states in Section 4 under Enterprise Vault: 'Cross-reference all custodians against affected-mailbox list immediately; determine date ranges and missing counts; expedite recovery/remediation for affected people.' It also states in Section 5 under the spoliation risk for Enterprise Vault: 'It is unknown whether Kovach, Sokolova, Chen, or other key custodians are affected' and recommends to 'Cross-reference remediation log; quantify gaps by custodian and date.' This directly addresses the criterion of recommending verification of whether key custodians (specifically naming Kovach, Sokolova, Chen) were among the affected mailboxes with incomplete archive ingestion.
- **GPT-5.5: Pass.** The memo explicitly recommends cross-referencing all custodians against the Enterprise Vault affected-mailbox/remediation list and specifically notes that it is unknown whether Kovach, Sokolova, Chen, or other key custodians are affected by the incomplete ingestion.

### C-019

NXF-FS01 file server decommissioning flagged as imminent risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L163))

- **Sonnet 4.6: Pass.** The memo explicitly identifies NXF-FS01 as a high-priority risk in multiple sections. In Section 4 (Data Sources), it notes the server contains Sales/Sales Operations shared folders with 4.2 TB total data, that decommissioning is planned for January 31, 2025, migration is only 35% complete, and ~40% of Sales files labeled stale are planned for deletion. In Section 5 (Spoliation Assessment), it rates NXF-FS01 as HIGH priority with a January 31, 2025 deadline. The memo directs an immediate freeze on deletion and decommissioning, authorizes a forensic image before January 31, and lists this as an immediate milestone. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The memo explicitly identifies NXF-FS01 as containing Sales/Sales Operations shared folders, notes the January 31, 2025 decommission date and planned stale-file deletion, characterizes it as a high/imminent preservation risk, and recommends freezing deletion/decommissioning and forensic imaging before that date.

### C-020

NXF-FS01: Preservation action recommended before decommissioning ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L171))

- **Sonnet 4.6: Pass.** The memo explicitly addresses NXF-FS01 in multiple places. In Section 4 (Data Sources), it states: 'Freeze deletion and decommissioning for relevant data. Authorize forensic image of server or at minimum all Sales/Sales Ops shares before Jan. 31; preferred full image given stale-file risk and 8–10-hour estimate.' In Section 5 (Spoliation), it lists NXF-FS01 as HIGH priority with a January 31, 2025 deadline and directs a 'written stop instruction now; make forensic image (preferred) or preserve all relevant shares with metadata.' The immediate milestones section also references freezing NXF-FS01 cleanup on November 8 and completing forensic image before January 31, 2025. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo specifically addresses NXF-FS01 multiple times, recommending freezing deletion and decommissioning, authorizing a forensic image or preservation of relevant Sales/Sales Ops shares before the January 31, 2025 decommissioning date, and preserving metadata/migration logs until Legal sign-off.

### C-021

Kovach personal iPhone / BYOD preservation issue identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L179))

- **Sonnet 4.6: Pass.** The memo explicitly identifies that Kovach used a personal iPhone for work (Outlook, Teams, Salesforce) under BYOD, and states 'Company has no MDM' meaning no remote access/image/wipe capability. This is flagged multiple times in the custodian table, the data sources section, and the spoliation risk section.
- **GPT-5.5: Pass.** The memo explicitly identifies Kovach’s personal iPhone/BYOD issue, noting it was used for work-related Outlook/email, Teams/cache, and Salesforce data, and states the company has no MDM or remote access/image/wipe capability, so preservation must be sought through counsel.

### C-022

Recommendation to send preservation demand to Kovach's counsel re personal device ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L187))

- **Sonnet 4.6: Pass.** The memo explicitly recommends that Pinnacle Hartwell (outside defense counsel) send a preservation demand to Stadler Raines/Kovach covering his personal iPhone. This appears in multiple sections: the Executive Summary states 'have Pinnacle Hartwell promptly send the agreed preservation demand to Kovach's counsel concerning his personal iPhone'; the custodian table entry for Kovach states 'Through Stadler Raines, request immediate preservation of personal iPhone work data'; Section 6 states 'Pinnacle Hartwell to send the agreed notice to Stadler Raines promptly. Request preservation of Kovach's iPhone'; and the immediate milestones include 'send Kovach device preservation demand through counsel.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly recommends that Pinnacle Hartwell/outside counsel send a prompt preservation demand to Kovach’s counsel at Stadler Raines covering Kovach’s personal iPhone and work-related data, including Outlook, Teams/cache, Salesforce, SMS/texts, photos/notes, and preventing deletion/reset.

### C-023

Kovach device may hold unique surviving copies of communications ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L195))

- **Sonnet 4.6: Pass.** The memo explicitly states in the Spoliation and Data-Loss Assessment section under 'Kovach personal iPhone / cached data': 'No MDM, no preservation request at termination, no known reset/deletion status. Local emails/chat cache may be unique surviving copies; device belongs to former employee represented by counsel.' This directly connects the personal device to the possibility that it holds unique/irreplaceable data, particularly in the context of Teams chats having been purged from Nexfield's systems. The memo also references this connection in the custodian table and in the BYOD data sources section, noting the Teams purge risk alongside the need to 'search Kovach iPhone through counsel' as a mitigation step for lost Teams chat content.
- **GPT-5.5: Pass.** The memo explicitly links Kovach’s personal iPhone to potentially unique surviving evidence, stating that local email/Teams cache may survive and that local emails/chat cache may be “unique surviving copies,” particularly in the context of likely Teams purge from Nexfield systems.

### C-024

Salesforce auto-deletion of inactive records flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L203))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Salesforce's nightly batch deletion of records inactive for 18 months in Section 4 (Data Sources): 'Nightly 2:00 a.m. CT deletion of records inactive for 18 months, including child records; job remains active. ~2,200 FY2023 records marked inactive; unknown subset may have been deleted.' It also flags this as a HIGH priority risk in Section 5 (Spoliation Assessment): 'Salesforce inactive records --- possible prior permanent deletion: 18-month nightly job active; some FY2023 inactive records may have crossed threshold during 2024; unknown subset deleted.' This directly addresses the criterion requiring identification of the 18-month auto-deletion policy and the risk to FY2023 (early-to-mid 2023) channel/sales records.
- **GPT-5.5: Pass.** The memo expressly flags Salesforce as running a nightly deletion job for records inactive for 18 months, including child records, notes the job remains active, and identifies FY2023 channel/sales records as potentially already deleted or at risk, with instructions to suspend the job and preserve/export relevant channel distributor data.

### C-025

Salesforce: Recommendation to suspend auto-deletion or export data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L211))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the Salesforce auto-deletion risk in multiple places. In Section 4 (Data Sources), it states: 'Suspend batch deletion immediately pending scope; preserve current snapshot, deletion/recycle-bin/audit logs and backups; export channel distributor accounts/opportunities and associated child records, historical field values, Q1--Q4 activity, inactive FY2023 records, and PIP audit reports.' In Section 5 (Spoliation), it lists Salesforce as HIGH priority and directs: 'Disable job; capture deletion/recycle-bin/audit logs and snapshots; identify deleted account/opportunity IDs and dates; seek vendor/backups/exports and custodian copies.' In Section 6, it directs IT to 'suspend Salesforce inactive-record batch deletion immediately' and to 'export and snapshot Salesforce before relevant deletion.' The memo clearly recommends both suspending the auto-deletion policy and performing targeted exports of channel distributor records.
- **GPT-5.5: Pass.** The memo repeatedly identifies the Salesforce inactive-record deletion risk and recommends immediate suspension of the nightly batch deletion, preservation of snapshots/logs/backups, and targeted exports of channel distributor accounts/opportunities and related records for the relevant period.

### C-026

SEC inquiry overlap recognized — coordinated hold recommended ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L219))

- **Sonnet 4.6: Pass.** The memo explicitly recognizes the SEC informal inquiry received October 28, 2024, covering Q1–Q3 channel sales and revenue recognition, and notes substantial factual overlap with the Kovach matter. It recommends a single coordinated preservation hold with a common 'Kovach / SEC Revenue Recognition' umbrella and two matter tags (KOV-EMP and SEC-RR) to cover both matters efficiently while maintaining separate tracking for scope, access, privilege review, and production decisions. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly states that Nexfield should issue one coordinated preservation hold covering both Kovach’s employment claims and the SEC October 28 informal inquiry, notes substantial factual overlap in revenue-recognition/channel sales evidence, and separately tracks SEC-RR scope for Q1–Q3 channel distribution and revenue recognition materials.

### C-027

SEC inquiry may require broader custodian set ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L227))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the need for additional custodians beyond those involved in the Kovach termination for the SEC inquiry. Section 3 includes separate custodian categories for 'Finance / accounting / revenue and returns personnel' (primarily SEC-RR), 'Other regional sales managers and Sales Operations staff' (SEC-RR), 'Audit Committee members, Corporate Secretary, governance record custodians' (primarily SEC-RR), and outside auditor contacts. The memo states these should include 'employees who prepared/reviewed revenue recognition, Q1–Q3 close, channel sales, return reserves, rebates/credits, or distributor inventory analyses' and directs the Controller and CFO to identify preparers, approvers, and sales-finance analysts. The memo also uses a two-matter tagging system (KOV-EMP and SEC-RR) specifically to distinguish custodians needed for the SEC matter beyond those in the employment dispute. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly states that custodians who hold evidence of revenue practices should be included even if they had no role in Kovach's employment decision, and it identifies additional sales, sales operations, finance/accounting/revenue/returns personnel, Audit Committee/governance custodians, IT admins, and auditor-related sources for the SEC revenue-recognition inquiry. This directly addresses that the SEC matter may require custodians beyond the Kovach termination list.

### C-028

Pinnacle Hartwell engagement scope gap noted (SEC not covered) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L235))

- **Sonnet 4.6: Fail.** The memo mentions the Pinnacle Hartwell defense engagement dated October 18, 2024, and separately notes the SEC informal inquiry arrived October 28, 2024. However, the memo does not explicitly note or imply that the October 18 Pinnacle Hartwell engagement letter covers only the Kovach employment claims and therefore does not address the SEC inquiry, nor does it flag that the engagement scope may need to be updated to cover the SEC matter. The memo treats Pinnacle Hartwell as defense counsel for both matters throughout (e.g., directing them to coordinate SEC response strategy, send preservation demands, etc.) without flagging the gap that the original engagement predated the SEC inquiry and may not cover it. The criterion specifically requires the memo to note or imply this engagement scope gap.
- **GPT-5.5: Fail.** The memo identifies Pinnacle Hartwell's October 18 defense engagement and the later October 28 SEC inquiry, and it recommends separate tracking of the matters. However, it does not state or clearly imply that the October 18 engagement letter covered only Kovach employment claims and omitted the SEC inquiry, nor does it recommend updating the engagement scope to cover the SEC matter.

### C-029

Temporal proximity (13 days) between complaint and PIP flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L243))

- **Sonnet 4.6: Pass.** The memo explicitly states in the trigger timeline table: 'PIP issued thirteen days after the second reported Sokolova complaint.' This directly identifies the temporal proximity (13 days) between Kovach's July 2 complaint to Sokolova and the July 15 PIP initiation as a key fact bearing on the retaliation causation question.
- **GPT-5.5: Pass.** The memo expressly notes that the July 15, 2024 PIP was issued “thirteen days after the second reported Sokolova complaint,” i.e., Kovach’s July 2 complaint, and places this fact in the preservation timeline for the retaliation/employment dispute.

### C-030

Priority preservation of decision-maker communications in July 2–15 window ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L251))

- **Sonnet 4.6: Pass.** The memo explicitly calls out the July 2–15 window in the Graham Ellicott custodian entry: 'Preserve all communications and records, especially July 2–15 decision period, PIP/termination drafts, communications with Sokolova/Purdy, Audit Committee, and sales leadership.' It also notes in the trigger table that the PIP was 'issued thirteen days after the second reported Sokolova complaint' and directs preservation of 'decision-making, drafts, CRM audits, check-in notes, and communications among Sokolova, CEO Graham Ellicott, and HR VP Janet Purdy.' This specifically targets the July 2–15 window and the key decision-makers (Sokolova, Ellicott, Purdy) for priority preservation, directly addressing the retaliation causation issue.
- **GPT-5.5: Pass.** The memo expressly calls out the July 2–15 decision period for preservation, including PIP/termination drafts and communications among Sokolova, Ellicott, and Purdy. It also notes the July 15 PIP followed shortly after Kovach’s July 2 complaint and directs preservation of related decision-making communications.

### C-031

Duty to preserve trigger date analyzed (pre-demand letter) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L259))

- **Sonnet 4.6: Pass.** The memo explicitly analyzes the duty to preserve trigger date and concludes it arose well before the October 3, 2024 demand letter. It identifies August 5, 2024 (Kovach's written whistleblower letter to Audit Committee Chair Marcus Ainsley) as the 'prudent conservative trigger date' and notes the September 12, 2024 termination as a point at which 'claims were reasonably foreseeable at the latest.' The memo also references the June verbal complaints and the August 20 investigation as additional relevant facts. It explicitly states the 95-day gap between August 5 and November 8, and notes the October 3 demand letter made threatened litigation 'explicit' — implying the duty arose earlier. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly analyzes the preservation trigger date and concludes preservation likely became necessary no later than August 5, 2024, when Kovach sent a written accounting-misconduct complaint to the Audit Committee Chair. It also notes the September 12 termination reinforced foreseeability and that the October 3 demand letter merely made threatened litigation explicit. Thus it satisfies the pre-demand trigger analysis criterion.

### C-032

Preservation gap between trigger date and vendor engagement assessed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L267))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the preservation gap in multiple places. In the Executive Summary, it states: 'The August 5-to-November 8 interval is 95 days. During this interval, at least some relevant Teams chats may have been automatically purged; Salesforce records may have been permanently deleted; and archive completeness for key custodians remains unknown.' It also notes that 'The record reviewed does not establish that a formal hold notice or effective technical preservation controls were implemented before November 4' and that 'IT affirmatively reported that no eDiscovery hold had been placed on Kovach's mailbox or Teams data.' Section 5 (Spoliation and Data-Loss Assessment) provides a detailed risk-by-risk analysis of what may have been lost during the gap, including Teams chats (likely purged before Aug. 8), Salesforce inactive records (possibly permanently deleted), and Enterprise Vault migration gaps. The memo also notes that Ridgeway's engagement on November 1 did not itself implement holds. This comprehensively addresses the gap between the August 5 trigger date and the November 1 vendor engagement and actual preservation actions.
- **GPT-5.5: Pass.** The memo explicitly identifies August 5, 2024 as the likely preservation trigger, notes Ridgeway's November 1 engagement and lack of effective holds by November 4, calculates a 95-day gap to November 8, and assesses potential data loss during that interval including Teams purge, Salesforce deletions, Enterprise Vault gaps, and other risks. It also recommends investigation and mitigation of any lost data. This directly satisfies the criterion.

### C-033

SOX Section 806 whistleblower protections flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L275))

- **Sonnet 4.6: Pass.** The memo explicitly mentions 'a SOX Section 806 claim' in Section 1 (Matter, Trigger, and Preservation Gap): 'The Kovach matter concerns alleged retaliation for internal complaints about accelerated channel shipments and revenue recognition, including a SOX Section 806 claim and Texas-law claims.' This directly identifies that Kovach's claims implicate Sarbanes-Oxley Section 806 whistleblower retaliation protections, which broadens the hold scope beyond simple state-law wrongful termination.
- **GPT-5.5: Pass.** The memo expressly states that the Kovach matter includes “a SOX Section 806 claim” and frames the dispute as whistleblower retaliation involving accounting/revenue-recognition complaints, thereby flagging the Sarbanes-Oxley whistleblower-protection issue and broadening the preservation scope beyond state-law wrongful termination.

### C-034

SOX implications for preservation breadth noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L283))

- **Sonnet 4.6: Fail.** The memo mentions SOX Section 806 claim in Section 1 ('The Kovach matter concerns alleged retaliation for internal complaints about accelerated channel shipments and revenue recognition, including a SOX Section 806 claim and Texas-law claims'). However, the criterion requires that the memo draw a connection between the SOX retaliation theory and the scope or breadth of the litigation hold—specifically that the hold should encompass all communications regarding Kovach's reports to the Audit Committee and any subsequent retaliatory actions, and/or that SOX claims create broader or more protective preservation obligations. The memo does preserve communications related to Kovach's Audit Committee reports and retaliatory actions (PIP, termination), but it does not explicitly connect the SOX Section 806 claim to a broader or more protective preservation obligation. The SOX reference is merely descriptive of the legal theory, not used to justify or expand the hold scope. The criterion specifically requires that the connection between SOX and preservation breadth be drawn explicitly.
- **GPT-5.5: Pass.** The memo identifies the Kovach matter as including a SOX Section 806 retaliation claim and ties the employment hold scope to preservation of complaint/reporting communications, Audit Committee materials, investigation files, PIP/termination decision-making, and alleged retaliatory actions. This connects the SOX retaliation theory to the breadth of the litigation hold rather than merely mentioning SOX in passing.

### C-035

Data source: Microsoft 365 / Exchange email included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L291))

- **Sonnet 4.6: Pass.** The memo explicitly identifies 'Microsoft 365 / Exchange Online' as a data source in Section 4, describing it as containing 'Email, attachments, calendar; Kovach mailbox converted to shared and intact for Apr. 1, 2024 onward.' It also provides detailed preservation actions for this source.
- **GPT-5.5: Pass.** The memo expressly lists “Microsoft 365 / Exchange Online” as a data source and discusses email, attachments, calendar, mailbox holds, and preservation actions for that system.

### C-036

Data source: Microsoft Teams included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L299))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Microsoft Teams as a data source in Section 4 (Data Sources and Required Preservation Controls), noting '1:1/group chat, channels, files, meeting records; extensive Sales use and Kovach activity Q1--Q3. Chats purge after 90 days; channel posts after one year; files in SharePoint/OneDrive.' It also addresses Teams in the spoliation section and directs immediate suspension of the 90-day chat deletion policy, preservation of channels, meeting artifacts, audit logs, and chat content. Both chats and channel messages are covered.
- **GPT-5.5: Pass.** The memo explicitly lists Microsoft Teams as a data source, including “1:1/group chat” and “channels/channel posts,” and directs preservation of Teams chats, channels, meeting artifacts, and related content under the hold.

### C-037

Data source: Salesforce CRM included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L307))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Salesforce Enterprise (U.S. org) as a data source in Section 4, describing it as containing 'Accounts, opportunities, contacts, activity, calls/emails logged, tasks, agreements/attachments, pipeline, territory and deal data.' It also details known risks (nightly deletion of inactive records) and immediate preservation actions required. Salesforce is also referenced multiple times throughout the memo in the context of custodian preservation directions and spoliation risk assessment.
- **GPT-5.5: Pass.** The memo expressly identifies Salesforce Enterprise (U.S. org) as a data source, describes relevant CRM records such as accounts, opportunities, activity, agreements/attachments, pipeline, territory and deal data, and directs preservation actions including suspending deletion and exporting records.

### C-038

Data source: SAP S/4HANA ERP included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L315))

- **Sonnet 4.6: Pass.** The memo explicitly identifies SAP S/4HANA as a data source in Section 4 (Data Sources and Required Preservation Controls), listing it as containing 'Orders, shipments, invoices, AR, credits, returns, GL/journals and revenue recognition; relevant Q1–Q3 data.' It also provides specific preservation instructions for SAP data.
- **GPT-5.5: Pass.** The memo explicitly lists “SAP S/4HANA” in the Data Sources section, describing it as containing orders, shipments, invoices, AR, credits, returns, GL/journals and revenue recognition, and directs preservation/controlled extracts for relevant Q1–Q3 data. This satisfies the criterion.

### C-039

Data source: NXF-FS01 legacy file server included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L323))

- **Sonnet 4.6: Pass.** The memo explicitly identifies NXF-FS01 as a data source in Section 4, describing it as a file server containing Sales/Sales Operations shared folders with 4.2 TB total data (~1.8 TB Sales/Sales Ops), noting the decommission planned for January 31, 2025, and directing immediate preservation actions including freezing deletion and authorizing a forensic image. It is also referenced in the spoliation assessment (Section 5) and the immediate milestones.
- **GPT-5.5: Pass.** The memo explicitly identifies “NXF-FS01 (file server)” as a data source containing Sales/Sales Operations shared folders and directs preservation actions, including freezing deletion/decommissioning and imaging relevant shares.

### C-040

Data source: Physical HR/personnel files included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L331))

- **Sonnet 4.6: Pass.** The memo explicitly identifies physical HR/personnel files as a data source subject to the hold. In Section 4 (Data Sources and Required Preservation Controls), there is a row for 'HR physical file / HRIS (SAP SuccessFactors)' that specifically mentions 'Personnel file, agreements, performance reviews, PIP with Kovach marginal note, check-ins, termination/release, payroll/benefit/offboarding records' and notes 'Paper originals in locked HR cabinet.' The preservation action directs 'Janet Purdy to label and segregate originals "DO NOT DESTROY---LEGAL HOLD"' and to scan for review without replacing originals. This clearly satisfies the criterion of identifying Kovach's paper personnel files maintained by Purdy in HR, including PIP documentation, termination letter, and performance reviews, as subject to the hold.
- **GPT-5.5: Pass.** The memo expressly identifies Janet Purdy/HR as custodian of Kovach personnel-file materials, directs preservation of paper originals, and separately lists the HR physical file/HRIS as containing the personnel file, performance reviews, PIP documentation, and termination/release records subject to hold.

### C-041

Custodian: Monica Tran-Nguyen identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L339))

- **Sonnet 4.6: Fail.** Monica Tran-Nguyen is listed as the recipient (General Counsel) and as an owner/responsible party in Section 8, but she is not identified as a custodian in the custodian table in Section 3. The criterion requires that she be identified as a custodian noting her role in receiving the demand letter, handling the SEC response, and/or overseeing the legal department's response. The memo lists her only in administrative/oversight roles, not as a custodian who should receive a hold notice and preserve her own records.
- **GPT-5.5: Fail.** The memo names Monica Tran-Nguyen as General Counsel and assigns her legal oversight responsibilities, but it does not list or identify her as a custodian in the custodian identification section or otherwise direct preservation of her records as a custodian.

### C-042

Immediate action items distinguished from routine hold steps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L347))

- **Sonnet 4.6: Pass.** The memo explicitly differentiates immediate/urgent actions from routine hold steps throughout. The Executive Summary lists five 'most urgent steps' with explicit 'immediately' language. Section 6 has a subsection 'Issue notice now' and 'Stop automatic deletion before collection.' Section 8 has an 'Immediate milestones' subsection with time-stamped priorities (Today, 24-48 hours, before Jan 31, by Nov 27). The spoliation table labels multiple risks as 'HIGH / immediate' or 'HIGH / urgent.' These clearly separate urgent actions from standard/routine hold procedures.
- **GPT-5.5: Pass.** The memo clearly distinguishes urgent/immediate items from routine steps. It lists “most urgent steps” in the executive summary, labels risk areas as “HIGH / immediate” or “urgent,” includes a “Today” immediate milestones list, and separately discusses routine hold administration such as periodic reminders and monitoring.

### C-043

Accurate citation of Teams chat retention as 90 days ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L355))

- **Sonnet 4.6: Pass.** The memo explicitly states '90-day Teams chat deletion policy' in the Executive Summary and '90-day chat purge' and 'Chats purge after 90 days' in the Data Sources section, correctly citing the Teams chat retention as 90 days per IT policy.
- **GPT-5.5: Pass.** The memo repeatedly and correctly states that Microsoft Teams chats are subject to a 90-day deletion/purge policy, including noting that the 90-day Teams chat deletion policy remained active and that chats purge after 90 days.

### C-044

Accurate citation of Salesforce auto-delete as 18 months for inactive records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L363))

- **Sonnet 4.6: Pass.** The memo explicitly states in the Salesforce row of the Data Sources table: 'Nightly 2:00 a.m. CT deletion of records inactive for 18 months, including child records; job remains active.' This correctly identifies the 18-month inactive record threshold for the Salesforce auto-delete policy.
- **GPT-5.5: Pass.** The memo correctly states that Salesforce has a nightly deletion job for records inactive for 18 months, including child records, and refers to the active 18-month inactive-record deletion policy.

### C-045

Accurate date: NXF-FS01 decommission January 31, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L371))

- **Sonnet 4.6: Pass.** The memo explicitly states 'Decommission planned Jan. 31, 2025' in the NXF-FS01 row of the data sources table, and also references 'before January 31, 2025' in the milestones section and 'forensic image of server or at minimum all Sales/Sales Ops shares before Jan. 31' elsewhere. This correctly identifies January 31, 2025 as the decommission date.
- **GPT-5.5: Pass.** The memo correctly states multiple times that NXF-FS01 is planned/scheduled for decommissioning by January 31, 2025.

### C-046

Accurate date: Email migration on April 1, 2024 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L379))

- **Sonnet 4.6: Pass.** The memo states 'Kovach mailbox converted to shared and intact for Apr. 1, 2024 onward' in the M365/Exchange Online row, and also references 'Pre-Apr. 1, 2024 email archive' for Enterprise Vault. This correctly identifies April 1, 2024 as the migration date from on-premises Exchange to Microsoft 365.
- **GPT-5.5: Pass.** The memo correctly references the migration timing by describing Microsoft 365/Exchange Online as containing Kovach mailbox data 'for Apr. 1, 2024 onward' and Enterprise Vault as the 'Pre-Apr. 1, 2024 email archive,' consistent with an email migration occurring on or around April 1, 2024.

### C-047

Accurate citation of 15% incomplete mailbox migration rate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L387))

- **Sonnet 4.6: Pass.** The memo states '421 of ~2,800 mailboxes with incomplete ingestion.' Dividing 421 by 2800 gives approximately 15%, which correctly reflects the 15% incomplete mailbox migration rate referenced in the criterion.
- **GPT-5.5: Pass.** The memo states that 421 of approximately 2,800 mailboxes had incomplete ingestion, which is about 15%, and it does not state an incorrect percentage.

### C-048

Ridgeway Forensics referenced as engaged e-discovery vendor ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L395))

- **Sonnet 4.6: Pass.** Ridgeway Forensics Group is mentioned multiple times throughout the memo, including in the trigger assessment section, the data sources table, the hold administration section, and the roles/milestones table. It is clearly identified as the engaged forensic/e-discovery vendor responsible for preservation, collection, imaging, and gap assessment tasks.
- **GPT-5.5: Pass.** The memo explicitly references Ridgeway Forensics multiple times, including noting Ridgeway Forensics was engaged on November 1, has preliminary M365 access, and assigning Ridgeway Forensics Group responsibilities for defensible collections/images and preservation support.

### C-049

Preservation hold on internal investigation work product addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L403))

- **Sonnet 4.6: Pass.** The memo explicitly addresses preservation of internal investigation materials in multiple places. In Section 3 (Custodian Identification), it lists 'Pinnacle Hartwell / investigation and defense files' as a custodian group and directs: 'Ask each engagement team to preserve its complete file, including source documents, interview notes, communications and collection logs.' In Section 1, it references the 'Audit Committee-directed preliminary investigation' and directs preservation of 'underlying documents, interview materials, collection records, notes, and counsel files under a controlled privileged protocol.' Section 7 explicitly addresses the Audit Committee investigation engagement, noting it is distinct from the defense engagement, directing separate file preservation, and flagging privilege considerations. The memo clearly notes the privileged status of these materials while still requiring their preservation.
- **GPT-5.5: Pass.** The memo expressly includes the Audit Committee/Pinnacle Hartwell internal investigation materials as preservation targets, including interview materials, interview notes, counsel files, source documents, collection logs, and investigation files. It also repeatedly notes the need for controlled privileged protocols, separate repositories, and privilege/work-product review.

### C-050

Teams channel messages distinguished from chat messages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L411))

- **Sonnet 4.6: Pass.** In Section 4 (Data Sources and Required Preservation Controls), under the Microsoft Teams row, the memo states: 'Chats purge after 90 days; channel posts after one year; files in SharePoint/OneDrive.' This explicitly distinguishes between Teams chat messages (90-day retention) and Teams channel posts (1-year retention), satisfying the criterion.
- **GPT-5.5: Pass.** The memo explicitly distinguishes Microsoft Teams 1:1/group chats from channel posts and states different retention periods: chats purge after 90 days while channel posts are retained for one year.
