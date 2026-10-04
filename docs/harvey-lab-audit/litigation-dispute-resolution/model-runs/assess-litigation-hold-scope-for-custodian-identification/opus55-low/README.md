# Claude Opus 5.5 (low): Assess Litigation Hold Scope for Custodian Identification — Custodian Recommendation Memorandum

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/assess-litigation-hold-scope-for-custodian-identification/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 47 of 50 criteria; GPT-5.5 passed 49 of 50 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-016](#c-016) | Incomplete email archive migration flagged as risk | **Fail** | Pass |
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
| [C-028](#c-028) | Pinnacle Hartwell engagement scope gap noted (SEC not covered) | Pass | Pass |
| [C-029](#c-029) | Temporal proximity (13 days) between complaint and PIP flagged | Pass | Pass |
| [C-030](#c-030) | Priority preservation of decision-maker communications in July 2–15 window | Pass | Pass |
| [C-031](#c-031) | Duty to preserve trigger date analyzed (pre-demand letter) | Pass | Pass |
| [C-032](#c-032) | Preservation gap between trigger date and vendor engagement assessed | Pass | Pass |
| [C-033](#c-033) | SOX Section 806 whistleblower protections flagged | Pass | Pass |
| [C-034](#c-034) | SOX implications for preservation breadth noted | Pass | Pass |
| [C-035](#c-035) | Data source: Microsoft 365 / Exchange email included | Pass | Pass |
| [C-036](#c-036) | Data source: Microsoft Teams included | Pass | Pass |
| [C-037](#c-037) | Data source: Salesforce CRM included | Pass | Pass |
| [C-038](#c-038) | Data source: SAP S/4HANA ERP included | Pass | Pass |
| [C-039](#c-039) | Data source: NXF-FS01 legacy file server included | Pass | Pass |
| [C-040](#c-040) | Data source: Physical HR/personnel files included | Pass | Pass |
| [C-041](#c-041) | Custodian: Monica Tran-Nguyen identified as custodian | **Fail** | Pass |
| [C-042](#c-042) | Immediate action items distinguished from routine hold steps | Pass | Pass |
| [C-043](#c-043) | Accurate citation of Teams chat retention as 90 days | Pass | Pass |
| [C-044](#c-044) | Accurate citation of Salesforce auto-delete as 18 months for inactive records | Pass | Pass |
| [C-045](#c-045) | Accurate date: NXF-FS01 decommission January 31, 2025 | Pass | Pass |
| [C-046](#c-046) | Accurate date: Email migration on April 1, 2024 | Pass | Pass |
| [C-047](#c-047) | Accurate citation of 15% incomplete mailbox migration rate | **Fail** | **Fail** |
| [C-048](#c-048) | Ridgeway Forensics referenced as engaged e-discovery vendor | Pass | Pass |
| [C-049](#c-049) | Preservation hold on internal investigation work product addressed | Pass | Pass |
| [C-050](#c-050) | Teams channel messages distinguished from chat messages | Pass | Pass |

## Judge reasoning

### C-001

Custodian: Darren Kovach identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L19))

- **Sonnet 4.6: Pass.** Darren T. Kovach is explicitly listed as a Tier 1 custodian in Section IV.A of the memo, identified as 'Former VP Sales, Americas (complainant)' with detailed notes on why he is relevant (author of complaints, Teams messages, emails about practices, PIP/CRM compliance) and what data sources must be preserved (M365 mailbox, OneDrive, NXF-FS01 folders, Salesforce activity, returned Dell laptop, personal iPhone). He is tagged K/S (both matters) and discussed extensively throughout the memo.
- **GPT-5.5: Pass.** The memo expressly lists Darren T. Kovach in Tier 1 as a custodian/former VP Sales, Americas, identifies him as the complainant and author of complaints/August 5 letter, and specifies preservation of his company-controlled data and personal iPhone because his communications are central to both the Kovach and SEC matters.

### C-002

Custodian: Renata Sokolova identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L27))

- **Sonnet 4.6: Pass.** Renata Sokolova is explicitly listed as a Tier 1 custodian in Section IV.A of the memo. She is identified as CFO, noted as having received complaints on June 14 and July 2, described as the 'alleged source of "make the number" pressure,' and flagged as a SOX 302 certifier. Her key sources include mailbox, Teams, OneDrive, mobile device, and weekly pipeline forecasts. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo lists Renata Sokolova in Tier 1 as a custodian, identifies her as CFO, notes she received Kovach's complaints on June 14 and July 2, and describes her alleged role in revenue-related pressure and SOX certifications.

### C-003

Custodian: Graham Ellicott identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L35))

- **Sonnet 4.6: Pass.** Graham Ellicott is explicitly listed as a Tier 1 custodian in Section IV.A of the memo. He is identified as CEO, noted for approving the PIP, carrying out the termination, signing the termination letter, writing Kovach's FY21-23 reviews, being a SOX 302 certifier, and being in the Jul 2-15 window. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo lists Graham Ellicott in Tier 1 custodians as CEO, states he approved the PIP, carried out/signed the termination letter, and was a key SOX certifier/decision-maker in the relevant window.

### C-004

Custodian: Janet Purdy identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L43))

- **Sonnet 4.6: Pass.** Janet Purdy is explicitly identified as a Tier 1 custodian in Section IV.A of the memo. She is listed with her role as 'VP Human Resources' and her relevance is described as: 'Prepared the PIP, ran check-ins, carried out termination, handled severance; in the Jul 2--15 window.' She is also mentioned in Section IV.D as 'Kovach only: Janet Purdy as a custodian of substance (PIP, termination, severance)' and in Section VII.A regarding securing the personnel file. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly lists Janet Purdy as a Tier 1 custodian, identifies her as VP Human Resources, and notes her role in preparing/managing the PIP, running check-ins, carrying out the termination, and handling severance.

### C-005

Custodian: Tomás Herrera identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L51))

- **Sonnet 4.6: Pass.** The memo clearly identifies Tomás Herrera as a Tier 1 custodian in Section IV.A. His entry notes his role as 'Director Sales Ops; interim VP Sales since Sep 13,' that he was a 'Former direct report to Kovach,' that he 'received "prioritize channel" guidance,' and that he 'controls Salesforce "Inactive" flagging and NXF-FS01 Sales folders.' His key sources include 'Mailbox (includes forwarded Kovach mail), Teams, Salesforce, S:\ drive.' This satisfies the criterion of identifying Herrera as a custodian who reported to Kovach, took over the interim VP Sales role, and possesses sales data and channel partner communications.
- **GPT-5.5: Pass.** The memo lists Tomás Herrera as a Tier 1 custodian, identifies him as Director of Sales Ops and interim VP Sales since Sep. 13, notes he was Kovach’s former direct report, and describes relevant sales data sources including Salesforce, Sales folders, mailbox/Teams, and channel-related guidance.

### C-006

Custodian: Li Wei Chen identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L59))

- **Sonnet 4.6: Pass.** The memo explicitly lists Li Wei Chen as a Tier 1 custodian in Section IV.A. His entry states he is the Controller, that he 'Received complaint Jun 28,' and that he 'owns revenue entries and quarter-end close; return reserve analysis.' This satisfies the criterion of identifying Chen as a custodian responsible for revenue recognition entries and noting Kovach's June 28 complaint discussion with him.
- **GPT-5.5: Pass.** The memo lists Li Wei Chen in Tier 1 as a custodian, identifies him as Controller, states he received Kovach’s June 28 complaint, and notes he owns revenue entries/quarter-end close and related revenue recognition materials.

### C-007

Custodian: Marcus Ainsley identified as custodian (ISSUE_009) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L67))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Marcus Ainsley as a Tier 1 custodian in Section IV.A, noting he is the Audit Committee Chair who received the August 5 letter, directed the investigation, and holds Board and Audit Committee materials. Section VI is entirely dedicated to his special protocol. He is also referenced throughout the memo as a key custodian requiring immediate hold action.
- **GPT-5.5: Pass.** The memo explicitly states that Marcus Ainsley must be a custodian, lists him in Tier 1 as Audit Committee Chair, and notes that he received Kovach’s August 5 letter and directed the internal investigation.

### C-008

Ainsley: Board-level privilege/governance concerns flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L75))

- **Sonnet 4.6: Pass.** Section VI of the memo is entirely dedicated to Marcus Ainsley and explicitly addresses governance sensitivities (personal call from GC, informing full Audit Committee and Board chair, explaining the hold implies nothing about him) and privilege concerns (two-track review separating non-privileged from potentially privileged Audit Committee deliberations, engagement separation between investigation and defense files, Garner v. Wolfinbarger fiduciary exception, selective waiver risk). It also recommends a specific collection protocol (Pinnacle Hartwell directing but not performing forensic collection, segregated workspace, document-by-document privilege log). This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly identifies Ainsley as a board/Audit Committee custodian and devotes a special section to governance and privilege issues. It recommends personal GC outreach, identifying board/personal accounts, Pinnacle Hartwell-directed collection, forensic collection rather than counsel collection, segregated workspace, two-track privilege review, engagement separation, Audit Committee privilege ownership, possible separate counsel, and privilege waiver/fiduciary exception considerations.

### C-009

Custodian: Regional sales managers (Collings, Muñoz, Patwardhan) evaluated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L83))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Brett Collings, Diana Muñoz, and Raj Patwardhan as Tier 2 custodians in Section IV.B. Each is listed with their role, relevance to quarter-end sales practices and channel-stuffing allegations (e.g., Collings received per-distributor Q2 targets and gave informal return assurances; Muñoz had Q3 volumes +30% and 'stacking the channel'; Patwardhan provided emails with acceleration directives), and matter tags. All three are recommended as custodians requiring holds.
- **GPT-5.5: Pass.** The memo explicitly recommends all investigation interviewees as custodians and specifically lists Brett Collings, Diana Muñoz, and Raj Patwardhan as Tier 2 custodians. It describes their relevant knowledge of Q2/Q3 targets, return assurances, channel stacking, and acceleration directives tied to the channel-stuffing allegations.

### C-010

Custodian: Frank Jessup evaluated as potential custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L91))

- **Sonnet 4.6: Pass.** Frank Jessup is explicitly identified as a Tier 2 custodian in Section IV.B of the memo. He is listed as 'VP Operations' with relevance noted as 'Extended shifts at Houston/Dallas DCs; "ship-ahead" before SAP POs finalized' under matter tag 'S', and notes indicate 'Logistics and warehouse release records; he is VP level, so check BYOD enrollment.' He is clearly identified as a potential custodian with knowledge relevant to the channel-stuffing/revenue recognition allegations.
- **GPT-5.5: Pass.** The memo expressly identifies Frank Jessup, VP Operations, as a Tier 2 custodian/interviewee, notes his role in extended shifts and “ship-ahead” activity before SAP POs were finalized, and ties him to SEC/channel-stuffing relevance.

### C-011

Internal investigation interviewees linked to custodian rationale ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L99))

- **Sonnet 4.6: Pass.** The memo explicitly addresses the 8 internal investigation interviewees in Section IV.B, titled 'Tier 2 --- Investigation Interviewees (Your November 7 Question).' It states that all eight interviewees should be custodians, explains that five are already in Tier 1, and specifically addresses the other four (Collings, Muñoz, Patwardhan, Jessup) who had no part in the termination. The memo connects them to custodian status because 'they are the best evidence we have on the channel-stuffing merits' and notes this 'matters to the SEC and also to the Kovach case, because whether his belief was reasonable is an element of § 806.' Each of the four is individually described with their relevance to quarter-end sales practices and the SEC inquiry. The memo clearly links the investigation interviewee list to the custodian identification process for both the whistleblower retaliation claim and the SEC inquiry.
- **GPT-5.5: Pass.** The memo explicitly ties the Pinnacle Hartwell internal investigation interviewees to custodian identification, stating that all eight interviewees should be custodians or evaluated as such, because their evidence and communications about channel-stuffing/quarter-end sales practices are relevant to the SEC inquiry and to the Kovach retaliation claim, including the reasonableness of his belief.

### C-012

Teams chat 90-day auto-purge identified as spoliation risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L107))

- **Sonnet 4.6: Pass.** The memo extensively identifies the Teams 90-day auto-purge as a critical spoliation risk. It explicitly states in the Bottom Line section that 'Every Teams 1:1 and group chat created before about August 10, 2024 has been permanently purged,' covering the period of Kovach's verbal complaints (June 14, June 28, July 2) and the July 2–15 window. Section V.B.1 provides detailed analysis of the confirmed permanent loss of Teams chats, noting chats from May 7 to August 10 (under Aug 5 trigger) are gone, including complaint periods and Q2 quarter-end chats. The data source inventory labels Teams 1:1/group chat as 'Critical — ongoing loss.' The memo also identifies specific custodians (Sokolova, Ellicott, Purdy, Chen) whose chats in the relevant periods have been lost. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies Microsoft Teams 1:1/group chats as subject to a 90-day auto-purge, labels it a critical ongoing spoliation risk, and states that chats before about August 10, 2024 have likely been permanently purged as of November 8, including June/July complaint-period chats involving Kovach and relevant personnel such as Sokolova, Chen, and others concerning revenue issues.

### C-013

Teams chat: Specific timeline of likely data loss assessed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L115))

- **Sonnet 4.6: Pass.** The memo explicitly states in multiple places that Teams chats created before approximately August 10, 2024 have been permanently purged (90 days back from November 8, 2024). It specifically identifies that this loss encompasses Kovach's June 14, June 28, and July 2 complaint dates, the July 2–15 window, and Q2 quarter-end chats. The memo calculates the specific cutoff date and maps it to the critical complaint period, satisfying the criterion's requirement for a specific timeline assessment rather than a generic risk flag.
- **GPT-5.5: Pass.** The memo specifically calculates the 90-day Teams chat purge as of November 8, 2024, stating that chats before about August 10, 2024 are gone. It explicitly notes this includes the June 14, June 28, and July 2 complaint period and related July 2–15 window.

### C-014

Teams: Immediate suspension of retention policy recommended ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L123))

- **Sonnet 4.6: Pass.** The memo explicitly recommends suspending the Teams chat and channel retention policies. In Section V.A, it lists Teams 1:1/group chat as 'Critical --- ongoing loss' and requires 'Tenant-wide suspension of the chat purge policy.' In Section VIII, Action Item #1 states 'Suspend the Teams chat and channel retention policies tenant-wide' with a deadline of 'Today, Nov 8.' The Bottom Line section also warns that Q3 chats 'will start purging around December 16, 2024' and urges immediate action. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly recommends immediate suspension of the Teams 90-day chat purge/retention policy, including tenant-wide suspension and eDiscovery holds today to prevent ongoing data loss.

### C-015

Teams: Forensic recovery investigation recommended ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L131))

- **Sonnet 4.6: Pass.** The memo explicitly recommends multiple forensic recovery efforts for purged Teams chats. In Section V.B.1, it identifies 'Partial substitutes' including: (a) M365 unified audit log metadata export for purged chats with urgency noted; (b) chats cached on Kovach's iPhone and custodians' phones/desktops (Teams client cache); (c) emails or files referencing the chats; (d) screenshots Kovach may have kept. It also states 'Ridgeway should assess client-side caches on custodians' company laptops before any device refresh.' Action item #9 in Section VIII directs Ridgeway to 'Export M365 unified audit log (Teams metadata) for all custodians, Jan 1, 2024 onward' by Nov 12. The memo clearly recommends investigating recoverability through multiple channels including forensic analysis, audit logs, and client-side caches.
- **GPT-5.5: Pass.** The memo identifies the Teams purge and recommends recovery-related forensic steps, including exporting M365 unified audit log metadata, looking for cached Teams chats on Kovach’s iPhone and custodians’ phones/desktops, and having Ridgeway assess Teams client-side caches before device refreshes. It also directs eDiscovery holds going forward. This satisfies the requirement to investigate recoverability or alternative forensic sources for purged Teams chats.

### C-016

Incomplete email archive migration flagged as risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L139))

- **Sonnet 4.6: Fail.** The memo does mention the M365 migration and incomplete ingestion, but it states '421 mailboxes with incomplete ingestion' rather than characterizing this as approximately 15% of mailboxes. The criterion specifically requires the memo to identify the issue as 'approximately 15% of mailboxes with incomplete archive ingestion.' The memo references '421 mailboxes' as an absolute number without providing the percentage context (15%) that the criterion requires. However, the memo does flag the incomplete migration as a risk for pre-April 2024 email history for key custodians, noting it 'may affect Q1 2024 (SEC period) and FY2023 baseline email' and that custodians like Kovach, Sokolova, Chen may be affected. The criterion says PASS if the memo identifies that the migration had 'approximately 15% of mailboxes with incomplete archive ingestion.' The memo identifies 421 mailboxes but not the ~15% figure. This is a meaningful distinction since the criterion specifically calls out the percentage. The memo fails to characterize the 421 mailboxes as approximately 15% of the total mailbox population.
- **GPT-5.5: Pass.** The memo flags the April 2024 M365 migration issue, noting a validation report with 421 mailboxes with incomplete ingestion and explaining that this creates a potential pre-April 2024 email gap affecting Q1/FY2023 materials and possibly key custodians such as Kovach, Sokolova, and Chen. Although it does not state the 15% figure explicitly, the incomplete migration risk is clearly identified.

### C-017

Veritas Enterprise Vault identified as separate hold target ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L147))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Veritas Enterprise Vault (NXF-EV01) as a separate data source in the Data Source Inventory table (Section V.A). It notes 'Indefinite, no purge; 421 mailboxes with incomplete ingestion' and specifies the required action as 'Separate written hold. Cross-reference the remediation log against the custodian list today. Ridgeway forensic image before any Q1 2025 remediation touches the archive.' This clearly satisfies the criterion of identifying the Enterprise Vault as a data source requiring separate preservation given the incomplete migration.
- **GPT-5.5: Pass.** The memo explicitly identifies “Veritas Enterprise Vault (NXF-EV01)” as a data source, notes the incomplete ingestion/migration issue, and recommends a “Separate written hold” plus preservation/imaging steps.

### C-018

Recommendation to verify if key custodians' mailboxes were in the affected 15% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L155))

- **Sonnet 4.6: Pass.** The memo mentions the 421-mailbox ingestion gap (approximately 15% of mailboxes) and notes it 'may affect Q1 2024 (SEC period) and FY2023 baseline email.' It also states 'Until the remediation log is cross-checked we do not know if Kovach, Sokolova, Chen, or other custodians are affected. This is the day-one task for Halverson.' This directly recommends that IT (Halverson) cross-reference the remediation log against the custodian list to verify whether key custodians like Kovach, Sokolova, and Chen were among those affected by the incomplete ingestion. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly recommends cross-referencing the Enterprise Vault remediation/ingestion-gap log against the custodian list and states that until this is done, it is unknown whether Kovach, Sokolova, Chen, or other custodians are affected. It assigns this as a day-one task and includes it in the immediate action plan.

### C-019

NXF-FS01 file server decommissioning flagged as imminent risk ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L163))

- **Sonnet 4.6: Pass.** The memo explicitly identifies NXF-FS01 as a high-risk data source scheduled for decommissioning on January 31, 2025, with approximately 40% of Sales files marked as 'stale' and slated for deletion. It appears in the Bottom Line section, the Data Source Inventory table (marked as 'High (scheduled)' risk), and Section V.B.6, and Section IX. The memo calls for immediate action including a written direction prohibiting destruction without Legal's written release and scheduling a Ridgeway forensic image before further migration. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo repeatedly flags NXF-FS01 as a preservation concern: it states the server is scheduled for decommissioning on January 31, 2025 with deletion of stale files, identifies Sales folders and Kovach/Herrera Sales Ops folders as relevant, rates the risk as high/scheduled, and recommends no destruction plus forensic imaging before migration/decommissioning.

### C-020

NXF-FS01: Preservation action recommended before decommissioning ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L171))

- **Sonnet 4.6: Pass.** The memo explicitly recommends multiple preservation actions for NXF-FS01: (1) a written direction under Policy § 3.6 that no destruction occur without Legal's written release, (2) a Ridgeway full forensic image (4.2 TB, 8–10 hrs) to be done before more migration, prioritizing Kovach's and Herrera's folders, and (3) scheduling the image by Nov 22 in the immediate action plan (item 8). These actions directly address preservation before the January 31, 2025 decommissioning date.
- **GPT-5.5: Pass.** The memo specifically identifies NXF-FS01 as scheduled for decommissioning on January 31, 2025 and recommends preservation actions before then, including written direction that there be no destruction without Legal release, a Ridgeway full forensic image of the 4.2 TB server before further migration, and an action item to schedule the image by Nov. 22.

### C-021

Kovach personal iPhone / BYOD preservation issue identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L179))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Kovach's personal iPhone as a critical data source with no MDM control. In Section V.A (Data Source Inventory), it lists 'Kovach personal iPhone' with risk level 'Critical' and notes 'No MDM; not in our control; no preservation notice given at termination.' The memo also states in the custodian mobile devices row that 'No MDM on BYOD; about 45 enrolled.' Section VII.B further details the preservation demand to Stadler Raines specifically covering the personal iPhone, noting Kovach's BYOD acknowledgment. The Bottom Line section also flags this as a critical issue. All required elements are present: personal iPhone, BYOD policy, no MDM, and inability to remotely access/preserve data.
- **GPT-5.5: Pass.** The memo expressly flags Kovach’s personal iPhone as a non-company/BYOD source, states there is no MDM and it is not in Nexfield’s control, and recommends a preservation demand covering Outlook/work email, Teams app data/caches, and related mobile data because Nexfield cannot preserve it remotely.

### C-022

Recommendation to send preservation demand to Kovach's counsel re personal device ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L187))

- **Sonnet 4.6: Pass.** The memo explicitly recommends in Section VII.B that outside counsel (Sarah Drummond at Pinnacle Hartwell) send a preservation demand to Stadler Raines (Kovach's counsel) regarding his personal Apple iPhone. It details specific items to cover including the device itself, cached Teams chats, Outlook mail, Salesforce mobile data, SMS/iMessage, photos/screenshots, and cloud backups. Action item #4 in Section VIII also lists 'Send preservation demand to Stadler Raines (iPhone)' with a deadline of today. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly recommends that outside counsel Sarah Drummond send a preservation demand to Stadler Raines regarding Kovach’s personal iPhone, including instructions not to wipe, reset, replace, or delete relevant app data/caches, and lists this as an immediate action item.

### C-023

Kovach device may hold unique surviving copies of communications ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L195))

- **Sonnet 4.6: Pass.** The memo explicitly connects Kovach's personal iPhone to the potential for unique surviving copies of communications. In Section V.B.1, under 'Partial substitutes' for lost Teams chats, the memo lists 'Chats cached on Kovach's iPhone and on custodians' own phones and desktops (the Teams client cache)' as a recovery avenue precisely because the server-side chats have been purged. In Section VII.B, the preservation demand letter to Stadler Raines specifically requests preservation of 'Cached Teams chats and Outlook mail, Salesforce mobile data' on the iPhone. The memo also notes in Section V.B.5 that 'Kovach has had eight weeks to delete, reset, or replace the device' — implying urgency because the device may hold irreplaceable data. The connection between the purged Teams chats and the iPhone as a potential sole surviving source is clearly made.
- **GPT-5.5: Pass.** The memo explicitly connects Kovach’s personal iPhone to potentially unique surviving evidence: it states Teams chats from the relevant period were purged server-side, identifies Kovach’s iPhone/app caches as partial substitutes for purged chats, calls the iPhone a critical source, and recommends a preservation demand covering Teams/Outlook/Salesforce app caches and backups. This implies the device may contain irreplaceable copies of communications no longer available in Nexfield systems.

### C-024

Salesforce auto-deletion of inactive records flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L203))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Salesforce's 18-month inactive-record auto-deletion policy as a critical preservation concern. In Section V.A (Data Source Inventory), it states: 'Inactive records auto-deleted at 18 months; nightly 2:00 a.m. batch; 15-day recycle bin' and rates the risk as 'Critical --- ongoing loss.' In Section V.B, it further elaborates that 'Records flagged between about Feb 5 and May 8, 2023 were deleted during the Aug 5 -- Nov 8 gap' and notes that records deleted in the last 15 days are still in the recycle bin. This directly addresses channel partner/distributor records from early-to-mid 2023 being at risk. The memo also flags this in the Bottom Line section as one of four automated processes destroying data.
- **GPT-5.5: Pass.** The memo explicitly identifies Salesforce's 18-month auto-deletion of records marked Inactive, notes the nightly batch and recycle bin, recommends suspending it, and explains that records flagged in early-to-mid 2023 could have been deleted during the preservation gap and may include distributor/channel partner records relevant to baseline comparisons.

### C-025

Salesforce: Recommendation to suspend auto-deletion or export data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L211))

- **Sonnet 4.6: Pass.** The memo explicitly recommends suspending the Salesforce inactive-record batch job, restoring the 15-day recycle bin, revoking Inactive flagging, and performing a Data Loader export of channel accounts/opportunities plus field history. This appears in both the Data Source Inventory table (Section V.A) and the Immediate Action Plan (Section VIII, item 2). These recommendations directly address the Salesforce auto-deletion risk.
- **GPT-5.5: Pass.** The memo explicitly identifies Salesforce inactive-record auto-deletion as a critical ongoing risk and recommends suspending the nightly batch job, restoring recently deleted records from the recycle bin, freezing inactive flagging, preserving job logs, and performing a Data Loader export of channel accounts/opportunities and related history.

### C-026

SEC inquiry overlap recognized — coordinated hold recommended ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L219))

- **Sonnet 4.6: Pass.** The memo extensively recognizes the SEC informal inquiry overlap with the Kovach matter. Section I explicitly states 'We have two overlapping preservation obligations: the Kovach SOX § 806 / Sabine Pilot claims and the SEC Division of Enforcement informal inquiry.' Section III recommends a consolidated hold structure with one notice covering both matters, with custodians and data sources tagged K (Kovach), S (SEC), or K/S (both). The memo references the SEC inquiry throughout, including its October 28 receipt date, the Q1-Q3 2024 revenue recognition scope, and the November 27 production deadline. The coordination recommendation is central to the entire memo's structure.
- **GPT-5.5: Pass.** The memo explicitly identifies overlapping preservation obligations for the Kovach matter and the SEC informal inquiry, describes the SEC inquiry as covering Q1–Q3 2024 revenue recognition/channel issues, and repeatedly recommends a unified/consolidated litigation hold with shared custodian and data-source lists tagged by matter.

### C-027

SEC inquiry may require broader custodian set ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L227))

- **Sonnet 4.6: Pass.** The memo extensively addresses the need for additional custodians beyond those involved in the Kovach termination for the SEC inquiry. Section IV.C (Tier 3) explicitly lists expanded custodians driven 'largely by the SEC inquiry,' including remaining 11 Regional Sales Managers, revenue accounting/AR/credit-memo staff reporting to Chen, FP&A, Houston and Dallas distribution center managers, IR/SEC reporting/Internal Audit staff, and others. Section IV.D explicitly distinguishes 'SEC primarily' custodians from 'Kovach only' custodians. The memo clearly notes that the SEC inquiry requires a broader custodian set including finance, accounting, and sales personnel involved in revenue recognition.
- **GPT-5.5: Pass.** The memo explicitly recognizes that the SEC inquiry requires a broader custodian set beyond Kovach termination participants. It identifies Tier 3 as 'largely SEC-driven' and includes additional sales personnel, revenue accounting/AR/credit-memo staff, FP&A, logistics, Audit Committee, investor relations, SEC reporting, SOX compliance, Internal Audit, and third parties/auditors tied to revenue recognition.

### C-028

Pinnacle Hartwell engagement scope gap noted (SEC not covered) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L235))

- **Sonnet 4.6: Pass.** In Section VII.A (Roles and Responsibilities), the memo explicitly states under Pinnacle Hartwell's responsibilities: 'SEC counsel role (confirm: current engagement is limited to Kovach defense and expressly excludes regulatory matters, so SEC representation needs a separate engagement or other counsel before Nov 27).' This directly notes that the Pinnacle Hartwell engagement covers only the Kovach employment claims and does not cover the SEC inquiry, and flags that a separate engagement or other counsel is needed for the SEC matter before the November 27 production deadline. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly states that Pinnacle Hartwell’s current engagement is limited to the Kovach defense and expressly excludes regulatory matters, and notes that SEC representation needs a separate engagement or other counsel before the SEC production deadline. It also includes an action item to confirm the SEC counsel engagement.

### C-029

Temporal proximity (13 days) between complaint and PIP flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L243))

- **Sonnet 4.6: Pass.** The memo explicitly states in the Tier 1 custodian table under Graham Ellicott's entry: 'Approved PIP; carried out termination; signed termination letter; wrote Kovach's FY21--23 reviews; SOX 302 certifier; in the Jul 2--15 window' and in the trigger timeline table under the July 15, 2024 entry: 'Adverse action 13 days after protected activity.' This directly identifies the temporal proximity between Kovach's July 2 complaint and the July 15 PIP as approximately 13 days, and characterizes it as an adverse action following protected activity, which bears on the retaliation causation question.
- **GPT-5.5: Pass.** The memo expressly notes the July 2 complaint and the July 15 PIP, stating that the PIP was an “Adverse action 13 days after protected activity,” and repeatedly highlights the July 2–15 window. This satisfies the requirement to flag the temporal proximity as relevant to retaliation causation.

### C-030

Priority preservation of decision-maker communications in July 2–15 window ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L251))

- **Sonnet 4.6: Pass.** The memo repeatedly and specifically calls out the July 2–15 window as a priority preservation concern. In Section I (Bottom Line), it states that the July 2–15 window 'between his second complaint and the PIP (which Stadler Raines specifically demanded we preserve)' is among the content lost. In the trigger timeline table, Sokolova, Ellicott, and Purdy are identified as 'three people in the demanded Jul 2–15 window.' In the Tier 1 custodian table, Sokolova, Ellicott, and Purdy are each individually noted as being 'in the Jul 2--15 window.' Section V.B.1 on Teams chat loss specifically identifies 'any Sokolova / Ellicott / Purdy chats in the July 2–15 window' as content lost during the gap. The memo also notes Stadler Raines has already said it will seek 'the strongest possible inference' for any loss in that window. This clearly satisfies the criterion of specifically calling out this timeframe for priority preservation among the termination decision-makers.
- **GPT-5.5: Pass.** The memo specifically identifies Sokolova, Ellicott, and Purdy as Tier 1 custodians for immediate hold, repeatedly calls out the July 2–15 window between Kovach’s complaint and the PIP, and notes that their communications in that window are demanded and central to preservation/spoliation risk. This satisfies the requirement to prioritize/target preservation of decision-maker communications for that timeframe.

### C-031

Duty to preserve trigger date analyzed (pre-demand letter) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L259))

- **Sonnet 4.6: Pass.** The memo extensively analyzes the duty to preserve trigger date in Section II, explicitly identifying multiple pre-demand letter trigger dates including June 14, 2024 (first verbal complaint), August 5, 2024 (Kovach's written letter to Audit Committee), August 20, 2024 (Audit Committee retaining outside counsel), August 29, 2024 (Kovach's statement about Teams use), and September 12, 2024 (termination). The memo concludes that the trigger likely attached on August 5 or August 20, and explicitly states 'We should plan and budget for an August 5 trigger.' It clearly analyzes that the duty arose well before the October 3, 2024 demand letter.
- **GPT-5.5: Pass.** The memo extensively analyzes preservation trigger dates before the October 3 demand letter, identifying June complaints as arguable, August 5 written Audit Committee letter as the strongest early trigger, August 20 investigation retention as an independent trigger, and September 12 termination as the latest defensible trigger. It expressly concludes a court or SEC is more likely to find the trigger on August 5 or August 20 than September 12 and recommends planning for an August 5 trigger.

### C-032

Preservation gap between trigger date and vendor engagement assessed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L267))

- **Sonnet 4.6: Pass.** The memo extensively addresses the gap between the preservation trigger dates and actual preservation actions. Section II provides a detailed timeline showing triggers as early as June 14, 2024 (verbal complaint) and August 5, 2024 (written letter to Audit Committee), with Ridgeway not engaged until November 1, 2024. Section V.B explicitly analyzes what data was lost during this gap, including confirmed permanent loss of Teams chats before August 10, probable Salesforce record losses, and backup overwriting. The memo quantifies the gap (95 days from Aug 5, 57 days from Sep 12, 36 days from Oct 3) and assesses spoliation risk under FRCP 37(e). This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly analyzes the preservation trigger dates in August–October 2024, notes Ridgeway was engaged on November 1, and repeatedly states that no hold or suspension of deletion occurred during the intervening period. It assesses likely data loss during that gap, especially permanent Teams chat loss, probable Salesforce deletions, backup overwrites, and other risks, and characterizes the delay as a serious preservation failure.

### C-033

SOX Section 806 whistleblower protections flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L275))

- **Sonnet 4.6: Pass.** The memo explicitly references 'Kovach SOX § 806 / Sabine Pilot claims' in the very first section (Bottom Line), and later references 'Kovach's OSHA SOX § 806 filing window: 180 days from Sep 12, 2024' in Section X. It also mentions SOX § 802 (18 U.S.C. § 1519) in the trigger timeline. The memo clearly identifies that Kovach's claims implicate SOX Section 806 whistleblower retaliation protections and notes this broadens the hold scope (e.g., the § 806 'reasonable belief' element affects which custodians are relevant).
- **GPT-5.5: Pass.** The memo expressly identifies the matter as involving “Kovach SOX § 806 / Sabine Pilot claims,” discusses SOX § 806 elements such as reasonable belief, and treats this as part of the preservation/hold scope beyond state-law termination issues.

### C-034

SOX implications for preservation breadth noted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L283))

- **Sonnet 4.6: Pass.** The memo explicitly connects SOX to preservation scope in multiple places. It identifies Kovach's SOX § 806 / Sabine Pilot claims as a core preservation obligation, notes that the August 5 letter to Audit Committee Chair Ainsley is a key trigger, and includes in the subject-matter scope '(a) Kovach's complaints, performance, PIP, termination, severance, and BYOD' and '(e) Board and Audit Committee materials.' The memo also references SOX § 802 (18 U.S.C. § 1519) in the context of the SEC inquiry, and the July 2–15 window (between the second complaint and the PIP) is specifically called out as a period that must be preserved because of the retaliation theory. Ainsley's custodian designation is directly tied to his receipt of the August 5 whistleblower letter. The memo also notes that the hold scope covers communications about Kovach's complaints and the subsequent adverse actions (PIP, termination), and that the SOX retaliation theory affects which custodians and date ranges must be preserved. This satisfies the criterion that SOX implications be connected to the scope and breadth of the hold.
- **GPT-5.5: Pass.** The memo expressly frames the Kovach matter as a SOX § 806 retaliation claim and ties that theory to preservation scope: it recommends preserving Kovach’s complaints/reports, Audit Committee communications/materials including Ainsley’s receipt of the August 5 letter, and subsequent PIP/termination/severance materials. It also expands custodians to merits witnesses because the reasonableness of Kovach’s belief is an element of § 806, showing SOX affects hold breadth.

### C-035

Data source: Microsoft 365 / Exchange email included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L291))

- **Sonnet 4.6: Pass.** The memo explicitly identifies M365 Exchange Online as a data source in Section V.A (Data Source Inventory), listing it with a 7-year retention policy and requiring eDiscovery case holds on all Tier 1-2 mailboxes. It also references Kovach's M365 mailbox specifically as a separate high-risk source. M365/Exchange email is clearly included as a data source subject to the litigation hold.
- **GPT-5.5: Pass.** The memo explicitly lists “M365 Exchange Online” in the Data Source Inventory with required action to place eDiscovery holds on mailboxes, and also references Kovach’s M365 mailbox/shared mailbox as a source. This satisfies the requirement to identify Microsoft 365/Exchange email as a data source subject to the hold.

### C-036

Data source: Microsoft Teams included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L299))

- **Sonnet 4.6: Pass.** The memo extensively identifies Microsoft Teams as a data source subject to the litigation hold. It specifically addresses Teams 1:1/group chats (90-day auto-purge) and Teams channel messages (1-year auto-purge) in the data source inventory table, marks them as 'Critical' risk, and requires immediate action to suspend retention policies. Teams is discussed throughout the memo as a key data source with ongoing spoliation risk.
- **GPT-5.5: Pass.** The memo explicitly identifies Microsoft Teams as a data source, including separate entries for Teams 1:1/group chats and Teams channel messages, and recommends preservation/hold actions for both.

### C-037

Data source: Salesforce CRM included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L307))

- **Sonnet 4.6: Pass.** The memo extensively identifies Salesforce as a data source subject to the litigation hold. It appears in the Data Source Inventory table with detailed notes about the 18-month inactive-record auto-deletion risk, required actions (suspend batch job, restore recycle bin, revoke Inactive flagging, run Data Loader export), and is tagged as Critical with ongoing loss risk. Salesforce is also mentioned multiple times throughout the memo in the context of custodian data sources, spoliation risk, and immediate action items.
- **GPT-5.5: Pass.** The memo explicitly identifies Salesforce as a relevant data source, including Salesforce activity for custodians, a Salesforce entry in the data source inventory, and required hold actions such as suspending inactive-record deletion and exporting relevant records.

### C-038

Data source: SAP S/4HANA ERP included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L315))

- **Sonnet 4.6: Pass.** The memo explicitly identifies SAP S/4HANA as a data source in Section V.A (Data Source Inventory), noting it has '7 yr / permanent GL; no auto-delete' retention, tags it as 'S (K/S)' for matter relevance, and specifies required actions including a written hold to Controller and SAP Basis, and Ridgeway-supervised extraction of Q1-Q3 2024 orders, deliveries, invoices, credit memos, RMAs, and change documents/audit logs.
- **GPT-5.5: Pass.** The memo expressly lists “SAP S/4HANA” in the Data Source Inventory, describes it as containing GL/revenue-related data including orders, deliveries, invoices, credit memos, RMAs, and audit logs, and recommends a written hold and supervised extraction. It also references SAP journal entries for the Controller custodian.

### C-039

Data source: NXF-FS01 legacy file server included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L323))

- **Sonnet 4.6: Pass.** The memo explicitly identifies NXF-FS01 as a data source in multiple places, including the data source inventory table where it is listed as 'NXF-FS01 file server' with details about its decommission date, stale files, and required actions (forensic imaging by Ridgeway). It is also mentioned in the Bottom Line section, the spoliation risk assessment, and the immediate action plan (item 8).
- **GPT-5.5: Pass.** The memo explicitly identifies NXF-FS01 as a relevant data source multiple times, including in the custodian notes for Kovach/Herrera, the data source inventory as 'NXF-FS01 file server' with sales files and required hold/imaging actions, and the immediate action plan directing no destruction and forensic imaging.

### C-040

Data source: Physical HR/personnel files included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L331))

- **Sonnet 4.6: Pass.** The memo explicitly mentions the physical HR personnel file in multiple places. In Section IV.A (Tier 1 custodians), under Janet Purdy's entry, it lists 'Physical personnel file (6th floor locked cabinet)' as a key source. In Section V.A (Data Source Inventory), there is a dedicated row for 'HR paper file (6th floor)' described as 'Locked cabinet; 15 items inventoried' with required action to 'Label "DO NOT DESTROY --- LEGAL HOLD" (Policy § 5); keep originals in place; Legal takes a certified copy.' The memo also references Kovach's personnel file and severance materials in Section IV.D. These references clearly identify Kovach's paper personnel files maintained by Purdy in HR as subject to the hold.
- **GPT-5.5: Pass.** The memo expressly identifies Kovach’s physical personnel file maintained in HR as subject to preservation, including references to the 6th floor locked cabinet, Purdy’s HR role, PIP/termination/severance materials, performance reviews, and instructions to label the HR paper file “DO NOT DESTROY — LEGAL HOLD.”

### C-041

Custodian: Monica Tran-Nguyen identified as custodian ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L339))

- **Sonnet 4.6: Fail.** The memo lists Monica Tran-Nguyen as the recipient (TO:) and references her in various places, but does not identify her as a custodian in any of the custodian tiers (Tier 1, Tier 2, or Tier 3). The Legal Department section in Tier 3 mentions 'you and me' (referring to Tran-Nguyen and Brashear) as needing preservation, but this is not a formal custodian designation. The criterion requires that Tran-Nguyen be identified as a custodian noting her role in receiving the demand letter, handling the SEC response, and/or overseeing the legal department's response. She is not listed as a custodian in the memo.
- **GPT-5.5: Pass.** The memo includes a Tier 3 custodian group for the “Legal Department (you and me),” which in context includes Monica Tran-Nguyen as the addressee, and identifies relevant preserved materials such as Aug. 5 consultation, demand response, and hold history. It also assigns Tran-Nguyen responsibilities for SEC/demand response coordination. Thus, she is identified as a custodian or part of a custodian group.

### C-042

Immediate action items distinguished from routine hold steps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L347))

- **Sonnet 4.6: Pass.** The memo explicitly differentiates immediate/urgent actions from routine steps in multiple ways. Section I (Bottom Line) contains an 'Immediate asks' subsection that calls out the most urgent action (authorizing Teams preservation today). Section VIII is titled 'Immediate Action Plan' and includes a 72-hour timeframe reference in Section I. Within the action table, items are labeled 'Today, Nov 8' for the most urgent actions (items 1-5), while others have later deadlines (Nov 11, Nov 12, Nov 15, Nov 22), clearly separating urgent from routine steps. The memo also uses language like 'most urgent' to highlight specific actions. This clearly satisfies the criterion of explicitly labeling or grouping at least two action items as immediate/urgent and separating them from standard procedures.
- **GPT-5.5: Pass.** The memo explicitly distinguishes urgent/immediate tasks from routine hold procedures, including a Bottom Line bullet titled “Immediate asks,” identifying the “most urgent” action, and Section VIII titled “Immediate Action Plan” with multiple time-sensitive actions due today or within days.

### C-043

Accurate citation of Teams chat retention as 90 days ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L355))

- **Sonnet 4.6: Pass.** The memo consistently and correctly states that the Microsoft Teams chat retention policy is set to 90 days. This is mentioned multiple times throughout the document: in Section I ('the Teams chat 90-day purge'), in the trigger timeline table ('Teams chat 90-day and channel 1-year retention configured'), in Section V.A ('90-day auto-purge, running'), and in Section V.B ('chats created before about August 10, 2024 are gone' consistent with a 90-day lookback from November 8). The memo also correctly distinguishes between the 90-day chat purge and the separate 1-year channel purge policy.
- **GPT-5.5: Pass.** The memo repeatedly and correctly states that Teams 1:1/group chat retention is subject to a 90-day auto-purge, including in the Bottom Line, timeline, data source inventory, and spoliation analysis.

### C-044

Accurate citation of Salesforce auto-delete as 18 months for inactive records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L363))

- **Sonnet 4.6: Pass.** The memo explicitly states in the Data Source Inventory table: 'Salesforce (U.S. org) - Inactive records auto-deleted at 18 months; nightly 2:00 a.m. batch; 15-day recycle bin.' This correctly identifies the 18-month retention period for inactive Salesforce records. The same figure is referenced consistently elsewhere in the memo (e.g., 'The batch deletes records 18 months after they were marked Inactive' in Section V.B.2, and 'the Salesforce 18-month inactive-record deletion' in Section I).
- **GPT-5.5: Pass.** The memo correctly states multiple times that Salesforce inactive records are auto-deleted after 18 months, including in the Bottom Line and Data Source Inventory.

### C-045

Accurate date: NXF-FS01 decommission January 31, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L371))

- **Sonnet 4.6: Pass.** The memo explicitly states 'A fifth event, the NXF-FS01 decommissioning with deletion of "stale" files, is scheduled for January 31, 2025' in the Bottom Line section, and this date is repeated consistently throughout the document (e.g., 'Decommission Jan 31, 2025' in the data source inventory, 'Written direction: no NXF-FS01 destruction without Legal release' with the Jan 31 date referenced in Section X deadlines).
- **GPT-5.5: Pass.** The memo correctly states multiple times that NXF-FS01 is scheduled for decommissioning on January 31, 2025, including in the Bottom Line and data source inventory.

### C-046

Accurate date: Email migration on April 1, 2024 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L379))

- **Sonnet 4.6: Pass.** The memo states 'Apr 1 / Apr 18 / May 15, 2024 M365 migration; validation report finds 421 mailboxes with incomplete ingestion; on-premises Exchange storage deallocated' in the trigger timeline table. This correctly references the email migration as occurring on or around April 1, 2024.
- **GPT-5.5: Pass.** The memo correctly references the M365/email migration as occurring on April 1, 2024, including the timeline entry “Apr 1 / Apr 18 / May 15, 2024” and related references to mailboxes being intact from Apr. 1, 2024.

### C-047

Accurate citation of 15% incomplete mailbox migration rate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L387))

- **Sonnet 4.6: Fail.** The memo states '421 mailboxes with incomplete ingestion' but does not express this as a percentage. The criterion requires the memo to correctly reference approximately 15% of mailboxes experiencing incomplete archive ingestion. The memo only gives the raw number (421) without any percentage figure, so it does not satisfy the criterion of citing the 15% rate.
- **GPT-5.5: Fail.** The memo references “421 mailboxes with incomplete ingestion” but does not state that this represented approximately 15% of mailboxes. Because it does not correctly cite the required 15% incomplete migration rate, it fails the criterion.

### C-048

Ridgeway Forensics referenced as engaged e-discovery vendor ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L395))

- **Sonnet 4.6: Pass.** Ridgeway Forensics Group is mentioned extensively throughout the memo. It is explicitly identified as the engaged forensic vendor (engaged November 1) in Section VII.A, and is referenced in connection with numerous preservation and collection tasks including forensic imaging of NXF-FS01, collection of mobile devices, export of Teams audit logs, Salesforce extracts, and more.
- **GPT-5.5: Pass.** The memo explicitly references Ridgeway Forensics Group multiple times, including noting it was engaged Nov. 1 and assigning it preservation, forensic collection, imaging, chain-of-custody, and recovery tasks.

### C-049

Preservation hold on internal investigation work product addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L403))

- **Sonnet 4.6: Pass.** The memo explicitly addresses preservation of the internal investigation materials in multiple places. In Section IV.B (Tier 2), it lists 'Nathan Cross / Sarah Drummond (Pinnacle Hartwell)' and states: 'Not hold recipients. Send a written request to Pinnacle Hartwell to preserve the investigation file intact and kept separate from the defense file (engagement letter § 6).' In Section III (Consolidated Hold Recommendation), the subject-matter scope includes '(g) the internal investigation and its file, kept separately privileged.' In Section V.A (Data Source Inventory), 'Pinnacle Hartwell investigation file' is listed as a data source with the action 'Written preservation request; keep separate from defense file.' Section VI also discusses the two-track review and engagement separation, noting that investigation files must not be commingled. The memo clearly addresses preservation of investigation materials while noting their privileged status throughout.
- **GPT-5.5: Pass.** The memo explicitly identifies the internal investigation file, interview notes, and collected documents held by Pinnacle Hartwell as materials to preserve, directs a written preservation request, and repeatedly notes that these materials should be kept separate and treated as privileged/work product with appropriate privilege review/logging.

### C-050

Teams channel messages distinguished from chat messages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/task.json#L411))

- **Sonnet 4.6: Pass.** The memo explicitly distinguishes between Teams 1:1/group chat messages (90-day auto-purge) and Teams channel messages (1-year auto-purge) in multiple places. In Section I, it lists both as separate automated deletion processes: 'the Teams chat 90-day purge' and 'the Teams channel 1-year purge.' In Section V.A, the data source inventory has separate rows for 'Teams 1:1 / group chat' (90-day auto-purge) and 'Teams channel messages' (1-year auto-purge) with different risk assessments. The memo also notes in Section X that 'Teams channel posts from Q1 2024 begin purging: Jan 1, 2025' as a separate deadline from the chat purge deadline of December 16, 2024.
- **GPT-5.5: Pass.** The memo repeatedly distinguishes Teams 1:1/group chat messages subject to a 90-day purge from Teams channel messages subject to a 1-year purge, including separate risk assessments and action items for each.
