# GPT-6 Luna (xhigh): Draft Litigation Hold Notice for New Product Liability Class Action (Medical Device)

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-litigation-hold-notice-for-new-product-liability-matter/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 56 of 61 criteria; GPT-5.5 passed 56 of 61 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [litigation-hold-notice.docx](output/litigation-hold-notice.docx) ([read as Markdown](output/litigation-hold-notice.docx.md))
- [preservation-action-memo.docx](output/preservation-action-memo.docx) ([read as Markdown](output/preservation-action-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Litigation hold notice document is produced | Pass | Pass |
| [C-002](#c-002) | Preservation action memo document is produced | Pass | Pass |
| [C-003](#c-003) | Hold notice identifies correct case name | Pass | Pass |
| [C-004](#c-004) | Hold notice identifies correct case number | Pass | Pass |
| [C-005](#c-005) | Hold notice identifies correct court | Pass | Pass |
| [C-006](#c-006) | Hold notice states it is issued by General Counsel Priya Chandrasekaran | Pass | Pass |
| [C-007](#c-007) | Hold notice identifies the ProFlex KR-3000 as the product at issue | Pass | Pass |
| [C-008](#c-008) | Hold notice explains the legal obligation to preserve documents | **Fail** | **Fail** |
| [C-009](#c-009) | Hold notice defines preservation period starting January 1, 2017 | Pass | Pass |
| [C-010](#c-010) | Hold notice defines preservation period extending through the present | Pass | Pass |
| [C-011](#c-011) | Hold notice lists key custodians by name (threshold) | **Fail** | **Fail** |
| [C-012](#c-012) | Hold notice specifies email as a data type to preserve | Pass | Pass |
| [C-013](#c-013) | Hold notice specifies text messages and messaging apps | Pass | Pass |
| [C-014](#c-014) | Hold notice covers Veeva Vault documents | Pass | Pass |
| [C-015](#c-015) | Hold notice covers SAP / ERP data | Pass | Pass |
| [C-016](#c-016) | Hold notice covers Salesforce CRM data | Pass | Pass |
| [C-017](#c-017) | Hold notice covers VantagePulse app data | Pass | Pass |
| [C-018](#c-018) | Hold notice covers R&D files including CAD/engineering data | Pass | Pass |
| [C-019](#c-019) | Hold notice covers paper/hard copy documents | Pass | Pass |
| [C-020](#c-020) | ISSUE_001: SAP migration addressed with halt/carve-out instruction | **Fail** | **Fail** |
| [C-021](#c-021) | ISSUE_001: SAP legacy decommissioning by July 15 flagged | Pass | Pass |
| [C-022](#c-022) | ISSUE_002: Email auto-purge on June 30 addressed with suspension | **Fail** | **Fail** |
| [C-023](#c-023) | ISSUE_002: Retention policy VNT-POL-007 referenced | Pass | Pass |
| [C-024](#c-024) | ISSUE_003: Sandra Petrosian's departure flagged as urgent | Pass | Pass |
| [C-025](#c-025) | ISSUE_003: Forensic imaging of Petrosian's devices before departure | Pass | Pass |
| [C-026](#c-026) | ISSUE_004: Mobile device refresh/wipe halted | Pass | Pass |
| [C-027](#c-027) | ISSUE_004: WhatsApp and third-party app data on mobile devices | Pass | Pass |
| [C-028](#c-028) | ISSUE_005: Ashford Precision Components preservation addressed | Pass | Pass |
| [C-029](#c-029) | ISSUE_005: Legal basis for control over third-party records | Pass | Pass |
| [C-030](#c-030) | ISSUE_006: Privilege considerations for GC's files addressed | Pass | Pass |
| [C-031](#c-031) | ISSUE_006: Preservation without waiver of privilege | Pass | Pass |
| [C-032](#c-032) | ISSUE_007: Proportionality or tiered approach for 85 mobile devices | Pass | Pass |
| [C-033](#c-033) | ISSUE_008: Personal devices / BYOD preservation addressed | Pass | Pass |
| [C-034](#c-034) | ISSUE_008: Dr. Suresh's potential personal device use flagged | Pass | Pass |
| [C-035](#c-035) | ISSUE_009: Backup tapes / disaster recovery archives addressed | Pass | Pass |
| [C-036](#c-036) | ISSUE_009: Reasonable accessibility of backup tapes discussed | Pass | Pass |
| [C-037](#c-037) | ISSUE_010: Acknowledgment requirement included in hold notice | Pass | Pass |
| [C-038](#c-038) | ISSUE_010: Periodic reminders or compliance monitoring mentioned | Pass | Pass |
| [C-039](#c-039) | ISSUE_011: Veeva Vault audit trail and version preservation | Pass | Pass |
| [C-040](#c-040) | ISSUE_011: Veeva document lifecycle suspension instruction | Pass | Pass |
| [C-041](#c-041) | Memo identifies Petrosian imaging before June 20 as critical action | Pass | Pass |
| [C-042](#c-042) | Memo identifies SAP migration halt/preservation before June 16 | Pass | Pass |
| [C-043](#c-043) | Memo identifies mobile device wipe halt before June 23 | Pass | Pass |
| [C-044](#c-044) | Memo identifies email purge suspension before June 30 | Pass | Pass |
| [C-045](#c-045) | Memo correctly sequences urgent actions by deadline | Pass | Pass |
| [C-046](#c-046) | Memo addresses Ashford third-party coordination | Pass | Pass |
| [C-047](#c-047) | Memo addresses coordination with e-discovery vendor Corestone | Pass | Pass |
| [C-048](#c-048) | Memo recommends next steps for hold compliance | Pass | Pass |
| [C-049](#c-049) | Hold notice includes consequences of non-compliance | **Fail** | **Fail** |
| [C-050](#c-050) | Hold notice provides contact information for questions | Pass | Pass |
| [C-051](#c-051) | Hold notice instructs custodians not to delete/destroy documents | Pass | Pass |
| [C-052](#c-052) | Hold notice instructs suspension of routine destruction policies | Pass | Pass |
| [C-053](#c-053) | Correct date of complaint service: May 28, 2025 | Pass | Pass |
| [C-054](#c-054) | Correct product description: CoCrMo femoral component | Pass | Pass |
| [C-055](#c-055) | Hold notice defines subject matter scope covering key categories | Pass | Pass |
| [C-056](#c-056) | Hold notice addresses IT Department / Marcus Tilden's role | Pass | Pass |
| [C-057](#c-057) | Hold notice mentions the 510(k) clearance or FDA regulatory filings | Pass | Pass |
| [C-058](#c-058) | Hold notice addresses CAPA records and MDR reports | Pass | Pass |
| [C-059](#c-059) | Hold notice addresses field sales representative communications | Pass | Pass |
| [C-060](#c-060) | Memo addresses coordination with outside counsel Calloway Prichard Weeks | Pass | Pass |
| [C-061](#c-061) | Hold notice date is approximately June 2, 2025 | Pass | Pass |

## Judge reasoning

### C-001

Litigation hold notice document is produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L20))

- **Sonnet 4.6: Pass.** The agent produced a detailed, clearly labeled litigation hold notice document titled 'LITIGATION HOLD NOTICE' for Kessler et al. v. Vantage Medical Devices, Inc. The document is comprehensive and identifiable as a litigation hold notice.
- **GPT-5.5: Pass.** The agent produced a document clearly titled and labeled as a 'LITIGATION HOLD NOTICE' and 'CONFIDENTIAL — LITIGATION HOLD DIRECTIVE,' including preservation instructions and an acknowledgment section.

### C-002

Preservation action memo document is produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L28))

- **Sonnet 4.6: Pass.** The agent produced a detailed 'PRESERVATION ACTION MEMORANDUM' (preservation-action-memo.docx) addressed to Priya Chandrasekaran, General Counsel, Vantage Medical Devices, Inc., from outside counsel Natalie R. Prichard. This is a standalone document separate from any hold notice, containing executive summary, directives, scope, custodian lists, system-by-system plans, action register, and budget information. It clearly satisfies the criterion of a separate cover memo/preservation action memo addressed to or for the General Counsel.
- **GPT-5.5: Pass.** The agent produced a distinct document titled “INITIAL PRESERVATION PLAN AND IMPLEMENTATION DIRECTIVES / PRESERVATION ACTION MEMORANDUM,” addressed to the General Counsel, with action directives and implementation guidance. It is not merely embedded within a hold notice.

### C-003

Hold notice identifies correct case name ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L36))

- **Sonnet 4.6: Pass.** The litigation hold notice clearly identifies the matter as 'Dorothy M. Kessler and Raymond A. Dufresne, individually and on behalf of all others similarly situated v. Vantage Medical Devices, Inc.' and uses the short form 'Kessler et al. v. Vantage Medical Devices, Inc.' multiple times throughout the document, including in the header, the matter field, and the acknowledgment section.
- **GPT-5.5: Pass.** The litigation hold notice repeatedly identifies the matter as “Kessler et al. v. Vantage Medical Devices, Inc.”, including in the title/header, matter line, and acknowledgment section.

### C-004

Hold notice identifies correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L44))

- **Sonnet 4.6: Pass.** The litigation hold notice clearly identifies Case No. 1:25-cv-04387-RLM in multiple places, including the header table and the acknowledgment section.
- **GPT-5.5: Pass.** The litigation hold notice explicitly identifies the case as Case No. 1:25-cv-04387-RLM in the header, body, and acknowledgment section.

### C-005

Hold notice identifies correct court ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L52))

- **Sonnet 4.6: Pass.** The litigation hold notice clearly identifies the court as 'United States District Court, Southern District of Indiana, Indianapolis Division' in the header table under COURT/CASE. This satisfies the criterion of identifying the correct court as the Southern District of Indiana.
- **GPT-5.5: Pass.** The litigation hold notice identifies the court as the United States District Court, Southern District of Indiana, Indianapolis Division, which satisfies the criterion.

### C-006

Hold notice states it is issued by General Counsel Priya Chandrasekaran ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L60))

- **Sonnet 4.6: Pass.** The notice clearly states in the header table: 'ISSUED BY: Priya Chandrasekaran, General Counsel, on behalf of Vantage Medical Devices, Inc.' This satisfies the criterion that the hold notice is issued by General Counsel Priya Chandrasekaran, identified by name and title.
- **GPT-5.5: Pass.** The notice explicitly lists the issuer as “Priya Chandrasekaran, General Counsel, on behalf of Vantage Medical Devices, Inc.” and also directs questions to her as General Counsel.

### C-007

Hold notice identifies the ProFlex KR-3000 as the product at issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L68))

- **Sonnet 4.6: Pass.** The notice explicitly identifies the 'ProFlex KR-3000 Total Knee Replacement System' as the product at issue in multiple places throughout the document, including in Section 1 ('Vantage was served on May 28, 2025 with a putative class action concerning the ProFlex KR-3000 Total Knee Replacement System') and throughout Sections 2, 3, 4, and 5.
- **GPT-5.5: Pass.** The notice explicitly states that the putative class action concerns the “ProFlex KR-3000 Total Knee Replacement System,” correctly identifying the product at issue.

### C-008

Hold notice explains the legal obligation to preserve documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L76))

- **Sonnet 4.6: Fail.** The notice explains in Section 1 that 'Because litigation is pending, Vantage must preserve potentially relevant evidence.' It also states the duty continues until written release. However, the criterion specifically requires that the notice explain that failure to preserve may result in sanctions or adverse consequences. Reviewing the entire document, I do not find any explicit mention of sanctions, spoliation consequences, adverse inference instructions, or other adverse consequences for failing to comply with the preservation duty. The notice tells employees what to do and not to do, but never warns them of the legal consequences (sanctions, adverse inference, etc.) for non-compliance. This is a key element of the criterion that is missing.
- **GPT-5.5: Fail.** The notice clearly states that litigation is pending and that Vantage and recipients must preserve potentially relevant documents/ESI, but it does not explain that failure to preserve may result in sanctions or other adverse consequences. Because the criterion requires both the preservation duty and consequences for noncompliance, it is incomplete.

### C-009

Hold notice defines preservation period starting January 1, 2017 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L84))

- **Sonnet 4.6: Pass.** The notice explicitly states in Section 2: 'Preserve all documents and information, from January 1, 2017 through the present and on a continuing, forward-looking basis...' The acknowledgment form also confirms this date: 'I understand that I must preserve potentially relevant information from January 1, 2017 through the present and going forward.' The preservation period start date of January 1, 2017 is clearly and correctly specified.
- **GPT-5.5: Pass.** The hold notice expressly states that custodians must preserve relevant documents and information “from January 1, 2017 through the present,” and repeats this in the acknowledgment section.

### C-010

Hold notice defines preservation period extending through the present ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L92))

- **Sonnet 4.6: Pass.** The notice explicitly states in Section 2 that custodians must preserve information 'from January 1, 2017 through the present and on a continuing, forward-looking basis.' Section 9 and the acknowledgment form also confirm the duty continues 'until written release by the General Counsel.' The preservation period is open-ended and ongoing, not fixed to a past date.
- **GPT-5.5: Pass.** The notice specifies preservation of information from January 1, 2017 through the present and on a continuing, forward-looking basis, and states the hold remains until written notice from the General Counsel that it is lifted.

### C-011

Hold notice lists key custodians by name (threshold) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L100))

- **Sonnet 4.6: Fail.** Checking the notice for the 10 named custodians: (1) Dr. Wei-Lin Huang - not mentioned; (2) Sandra K. Petrosian - mentioned in Section 7; (3) Thomas/Tom Braddock - not mentioned; (4) Michelle Torrence - not mentioned; (5) James Kowalski - not mentioned; (6) Dr. Anita Suresh - not mentioned; (7) Brian Callahan - not mentioned; (8) Gerald Morrissey - not mentioned; (9) Priya Chandrasekaran - mentioned as General Counsel; (10) Marcus Tilden - mentioned as Director of IT. Only 3 of the 10 custodians are identified by name (Petrosian, Chandrasekaran, Tilden). The threshold requires at least 8 of 10. This fails the criterion.
- **GPT-5.5: Fail.** The notice identifies only 3 of the listed custodians by name: Sandra K. Petrosian, Priya Chandrasekaran, and Marcus Tilden. It does not identify at least 8 of the 10 required custodians.

### C-012

Hold notice specifies email as a data type to preserve ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L108))

- **Sonnet 4.6: Pass.** The notice explicitly mentions email multiple times as a data type to preserve. In Section 3, it lists 'Microsoft 365: Exchange email and archives, calendars, Teams chats/channels, SharePoint, OneDrive, shared mailboxes, and attachments.' In Section 2, it lists 'email' among communications to preserve. The acknowledgment form also includes a checkbox for 'M365 email / Teams / SharePoint / OneDrive / calendar'. Email is clearly and explicitly covered.
- **GPT-5.5: Pass.** The notice explicitly lists email as a data type to preserve, including “Microsoft 365: Exchange email and archives,” “personal email,” and “M365 email” in the acknowledgment checklist.

### C-013

Hold notice specifies text messages and messaging apps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L116))

- **Sonnet 4.6: Pass.** The notice explicitly mentions text/iMessage/SMS, WhatsApp, Signal, and VantagePulse in multiple sections (Section 2, Section 3, Section 4, Section 5), clearly covering text messages and third-party messaging apps as data to be preserved.
- **GPT-5.5: Pass.** The hold notice explicitly identifies text/iMessage/SMS, WhatsApp, Signal, and other messaging applications as sources to preserve, including specific instructions for field sales representatives and personal devices/accounts.

### C-014

Hold notice covers Veeva Vault documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L124))

- **Sonnet 4.6: Pass.** The notice explicitly mentions Veeva Vault in Section 3 ('Veeva Vault QMS and Submissions: all relevant controlled records, including drafts, prior/superseded versions, audit trails, electronic signatures, relationships, and lifecycle metadata') and also references it in Section 4 regarding auto-purge and Veeva draft purge, and in the acknowledgment checklist ('SAP / Veeva Vault / Salesforce / VantagePulse'). This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The notice explicitly identifies “Veeva Vault QMS and Submissions” as a covered source, including controlled records, drafts, audit trails, electronic signatures, and metadata, and also references Veeva draft purge and Veeva records elsewhere.

### C-015

Hold notice covers SAP / ERP data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L132))

- **Sonnet 4.6: Pass.** The notice explicitly identifies SAP ECC 6.0 and SAP S/4HANA in Section 3 (Sources and formats covered), specifying that KR-3000 manufacturing, quality, supplier, inspection, change-history/audit, financial, and linked records within those systems must be preserved. SAP/ERP data is clearly within scope.
- **GPT-5.5: Pass.** The notice expressly includes SAP ECC 6.0 and SAP S/4HANA within preservation scope, including KR-3000 manufacturing, quality, supplier, inspection, change-history/audit, financial, and linked records. It also separately references batch/device-history records and supplier quality records.

### C-016

Hold notice covers Salesforce CRM data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L140))

- **Sonnet 4.6: Pass.** The notice explicitly mentions Salesforce in Section 3 (Sources and formats covered): 'Salesforce and associated exports/attachments; VantagePulse cloud and on-device data...' and in Section 2 under sales/marketing/training: 'CRM records; complaint escalations; surgeon/hospital interactions.' The acknowledgment form also lists 'SAP / Veeva Vault / Salesforce / VantagePulse' as a checkbox option. Salesforce/CRM data is clearly within scope.
- **GPT-5.5: Pass.** The notice expressly includes sales/field activity with “CRM records” and lists “Salesforce and associated exports/attachments” as covered sources, and the acknowledgment also includes “Salesforce.”

### C-017

Hold notice covers VantagePulse app data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L148))

- **Sonnet 4.6: Pass.** VantagePulse is explicitly mentioned multiple times throughout the notice. It appears in Section 2 (communications), Section 3 (sources and formats covered, with specific mention of 'VantagePulse cloud and on-device data, including locally stored messages, photographs, notes, feedback, and offline activity'), Section 4 (instructions not to uninstall VantagePulse), and Section 5 (field sales representatives section, with specific instructions to preserve VantagePulse content including offline/local data). The acknowledgment form also includes a checkbox for 'SAP / Veeva Vault / Salesforce / VantagePulse'. The notice clearly and comprehensively covers VantagePulse app data.
- **GPT-5.5: Pass.** The notice expressly includes VantagePulse in the scope of preserved communications, covered sources/formats, mobile-device instructions, and the acknowledgment checklist, including on-device/offline locally stored data.

### C-018

Hold notice covers R&D files including CAD/engineering data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L156))

- **Sonnet 4.6: Pass.** The notice explicitly identifies 'CAD/SolidWorks files; FEA models; design reviews and change orders' under product design and development, and also references the R&D shared drive path '\\VNTG-ENG01\RnD\KR3000' and 'SolidWorks PDM' as covered sources. Engineering notebooks are also mentioned. All required R&D engineering file types are clearly within scope.
- **GPT-5.5: Pass.** The notice expressly includes R&D engineering materials such as engineering notebooks, CAD/SolidWorks files, FEA models, design reviews, and the R&D shared drive \\VNTG-ENG01\\RnD\\KR3000 within the preservation scope.

### C-019

Hold notice covers paper/hard copy documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L164))

- **Sonnet 4.6: Pass.** The notice explicitly includes paper documents in multiple places. Section 2 mentions 'paper files/notebooks' and 'paper originals.' Section 3 lists 'paper files/notebooks' under sources covered. Section 4 instructs to 'Keep physical records and notebooks secure.' The acknowledgment form includes a checkbox for 'Paper records, notebooks, notes, photographs, or other physical material.' Paper/hard-copy documents are clearly within scope.
- **GPT-5.5: Pass.** The notice expressly includes paper and hard-copy materials within scope, including 'paper files,' 'engineering notebooks,' 'paper originals,' and 'Paper records, notebooks, notes, photographs, or other physical material' in the acknowledgment.

### C-020

ISSUE_001: SAP migration addressed with halt/carve-out instruction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L172))

- **Sonnet 4.6: Fail.** The notice mentions SAP ECC 6.0 and SAP S/4HANA in Section 3 as systems covered by preservation, and in Section 4 it instructs that 'SAP migration/archive/decommissioning' must not affect covered information. However, the criterion specifically requires that the notice address the SAP ECC 6.0 to S/4HANA migration beginning June 16, 2025, and instruct that relevant legacy data must be fully preserved before migration proceeds or that the migration must be halted/paused. The notice does not mention the specific June 16, 2025 migration date, does not identify it as an imminent risk requiring a halt or carve-out, and does not specifically call out the manufacturing batch records and supplier quality records from 2017-2022 in the context of the SAP migration. The general instruction not to let 'SAP migration/archive/decommissioning' affect covered information is present but lacks the specificity required by the criterion regarding the known upcoming migration event and the need to halt or carve out relevant legacy data before it proceeds.
- **GPT-5.5: Fail.** The notice mentions SAP ECC 6.0/S/4HANA as covered sources and generally says not to permit a SAP migration/archive/decommissioning to affect covered information. However, it does not specifically address the ECC 6.0-to-S/4HANA migration beginning June 16, 2025, nor does it give a targeted halt/carve-out or pre-migration preservation instruction for relevant legacy manufacturing batch records and supplier quality records from 2017-2022.

### C-021

ISSUE_001: SAP legacy decommissioning by July 15 flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L180))

- **Sonnet 4.6: Pass.** The preservation-action-memo.docx explicitly mentions the July 15 deadline in multiple places. In the Executive Summary: 'SAP ECC 6.0 migration begins June 16 with legacy archival/decommissioning planned by July 15.' In the Action Register table: 'Before July 1 / July 15 - Hold KR-3000 paper files out of Iron Mountain transfer pending inventory. No SAP legacy decommissioning July 15 absent verified preservation and written GC approval.' This clearly identifies the July 15 SAP decommissioning as a data risk and action item requiring GC approval before proceeding.
- **GPT-5.5: Pass.** The preservation action memo explicitly notes that SAP ECC legacy archival/decommissioning is planned by July 15 and treats it as a preservation risk/action item, directing that no SAP legacy decommissioning occur by July 15 absent verified preservation and written GC approval.

### C-022

ISSUE_002: Email auto-purge on June 30 addressed with suspension ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L189))

- **Sonnet 4.6: Fail.** The notice does not specifically mention the quarterly email auto-purge scheduled for June 30, 2025, nor does it instruct that this specific auto-purge must be suspended or disabled. While the notice contains general language about suspending auto-purges and routine deletion processes (e.g., 'Do not permit an auto-purge... mailbox or Teams deletion... to affect covered information'), it never specifically identifies the June 30, 2025 quarterly email auto-purge or the specific risk of destroying emails older than 3 years (pre-June 30, 2022). The criterion requires specific mention of this scheduled event and a specific instruction to suspend/disable it.
- **GPT-5.5: Fail.** The notice generally instructs custodians not to permit an auto-purge or mailbox deletion, but it does not specifically mention the quarterly email auto-purge scheduled for June 30, 2025, the destruction of emails older than three years, or expressly direct suspension/disablement of that specific purge.

### C-023

ISSUE_002: Retention policy VNT-POL-007 referenced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L197))

- **Sonnet 4.6: Pass.** The preservation-action-memo.docx references 'Document Retention and Destruction Policy VNT-POL-007, Rev. 3' in the 'Source materials reviewed' section at the end of the document. This satisfies the criterion of referencing the policy by number (VNT-POL-007) in connection with the need to override normal retention schedules, as the memo is explicitly about overriding normal retention/destruction procedures during the litigation hold.
- **GPT-5.5: Pass.** The preservation-action memo expressly lists “Document Retention and Destruction Policy VNT-POL-007, Rev. 3” among the source materials reviewed, and the documents discuss suspending email purges and overriding normal retention schedules. This satisfies the requirement that the policy or its number be referenced in the relevant preservation/retention context.

### C-024

ISSUE_003: Sandra Petrosian's departure flagged as urgent ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L206))

- **Sonnet 4.6: Pass.** Both documents explicitly identify Sandra K. Petrosian's departure (effective June 20, 2025) as an urgent preservation issue. The litigation hold notice has an entire dedicated section (Section 7) titled 'Special instructions for departing custodian Sandra K. Petrosian' that flags her June 20 departure, suspends routine offboarding, and requires forensic imaging by June 13. The preservation action memo lists her as a 'Critical' custodian, notes her departure date, and includes specific deadlines for imaging her devices before she leaves.
- **GPT-5.5: Pass.** The output specifically flags Sandra K. Petrosian as a departing custodian with a June 20, 2025 last day and gives urgent preservation instructions, including suspending offboarding, preserving devices/accounts, and completing forensic imaging by June 13. The preservation memo also identifies her departure as an immediate risk requiring action.

### C-025

ISSUE_003: Forensic imaging of Petrosian's devices before departure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L215))

- **Sonnet 4.6: Pass.** The litigation hold notice (Section 7) explicitly states: 'Forensic imaging must be completed by June 13, 2025, before departure; coordinate with HR, IT, and Legal.' The preservation action memo (Section 4, custodian table) states 'Critical: Veeva QMS; complaints, CAPAs, MDRs, Q3 2022 analysis; M365, laptop, H: drive, QA shares, SAP QM; preserve before departure.' The action register also specifies 'Complete Petrosian laptop/portable-media forensic imaging (preferred one-week buffer); preserve home/QA drives' by June 13. Both documents clearly instruct forensic imaging/preservation of Petrosian's devices before her June 20 departure.
- **GPT-5.5: Pass.** The litigation hold notice specifically instructs that Petrosian’s laptop, iPhone, storage media, H: drive, mailbox, Teams, OneDrive, and Veeva records must not be wiped or purged, and states that forensic imaging must be completed by June 13, 2025, before her June 20 departure. The preservation memo also repeats these preservation/imaging requirements before departure.

### C-026

ISSUE_004: Mobile device refresh/wipe halted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L224))

- **Sonnet 4.6: Pass.** Section 5 of the notice explicitly addresses the scheduled replacement of 30 company-issued iPhones beginning June 23, 2025, and states that 'The June 23 refresh and wipe is suspended for affected devices.' It also instructs all 85 representatives to preserve data and that Legal will coordinate targeted collection, prioritizing the 30 at-risk phones. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The notice explicitly addresses the 30 company-issued iPhones scheduled for replacement beginning June 23, 2025, states that the June 23 refresh and wipe is suspended, and instructs users not to change, transfer, reset, or wipe devices while preserving mobile data.

### C-027

ISSUE_004: WhatsApp and third-party app data on mobile devices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L232))

- **Sonnet 4.6: Pass.** The notice explicitly mentions WhatsApp multiple times in the context of field sales representatives' mobile devices. Section 5 specifically states 'Preserve KR-3000-related text/iMessage/SMS, WhatsApp messages and media, VantagePulse content...' and Section 4 mentions 'Do not uninstall VantagePulse, WhatsApp, or other messaging apps.' WhatsApp and third-party messaging app data on mobile devices are clearly within scope.
- **GPT-5.5: Pass.** The notice expressly includes WhatsApp and other messaging apps within preservation scope, including in the field sales/mobile-device section requiring preservation of KR-3000-related WhatsApp messages and media on company and personal devices.

### C-028

ISSUE_005: Ashford Precision Components preservation addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L240))

- **Sonnet 4.6: Pass.** Both documents explicitly address Ashford Precision Components. The litigation hold notice (Section 2) instructs preservation of 'Ashford Precision Components records and communications' and (Section 4) directs custodians to 'Route questions about Ashford, VantagePulse, vendors, or any outside system to Legal.' The preservation action memo (Section 1, item 5) provides Ashford's full address, contact person, email, and instructs sending a formal preservation demand by June 6 via email and certified mail, invoking Quality Agreement QA-2017-0044, and escalating to subpoena/Rule 45 if noncooperation. Section 4 also includes Ashford in the system-by-system preservation plan. Both documents clearly identify Ashford as a third party requiring preservation and recommend/instruct that a preservation demand be sent.
- **GPT-5.5: Pass.** The preservation action memo specifically identifies Ashford Precision Components, Inc. in Grand Rapids, MI as a third party/contract manufacturer with relevant manufacturing and quality records, and recommends sending a formal preservation demand by email and certified mail. The litigation hold also references preserving Ashford records and communications.

### C-029

ISSUE_005: Legal basis for control over third-party records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L249))

- **Sonnet 4.6: Pass.** The preservation action memo explicitly references Quality Agreement QA-2017-0044 as the contractual basis for Vantage's rights over Ashford's records, stating 'invoke and review Quality Agreement QA-2017-0044 access/retention rights' and 'Exercise Quality Agreement QA-2017-0044 rights; escalate to subpoena/Rule 45 if noncooperation.' This provides both a contractual basis (quality agreement giving Vantage access/retention rights over Ashford records) and a legal basis (Rule 45 subpoena as fallback), which explains why third-party contract manufacturer records must be preserved and how Vantage can exercise control over them. The system-by-system table also notes preserving 'native-format preservation' of Ashford records and confirms written hold. This satisfies the criterion.
- **GPT-5.5: Pass.** The output expressly identifies Ashford as a contract manufacturer/supplier and directs Vantage to send a preservation demand while invoking/reviewing and exercising Quality Agreement QA-2017-0044 access/retention rights. It also frames preservation around Vantage’s possession, custody, or control. This provides a contractual/legal basis for preserving Ashford third-party records.

### C-030

ISSUE_006: Privilege considerations for GC's files addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L258))

- **Sonnet 4.6: Pass.** The preservation action memo explicitly addresses privilege considerations for the General Counsel's files in multiple places. Section 6 states: 'For the General Counsel's own files, apply preservation holds but use an outside-counsel supervised, segregated collection/review environment. Designate a privilege coordinator; screen before substantive review or production; maintain privilege log protocol. Seek a Federal Rule of Evidence 502(d) order/clawback protection at the Rule 26(f) or scheduling conference. Privileged materials must not be disclosed to IT, vendor reviewers, insurers, or opposing counsel beyond need-to-know instructions without Legal review.' Section 3 also flags GC Chandrasekaran as 'Executive/privilege-sensitive' with collection to be 'segregated and privilege screened.' The hold notice itself (Section 8) instructs recipients to preserve privileged communications but not forward or disclose them, and notes Legal will handle privilege-sensitive collection separately. Both documents clearly address privilege considerations for the GC's files.
- **GPT-5.5: Pass.** The output expressly addresses privileged materials in both documents. The hold notice instructs custodians to preserve legal communications/work product and states Legal will handle privilege-sensitive collection separately. The preservation memo specifically identifies the GC as a privilege-sensitive custodian and recommends outside-counsel-supervised segregated collection/review, a privilege coordinator, screening before production, privilege log protocol, and a Rule 502(d) clawback order.

### C-031

ISSUE_006: Preservation without waiver of privilege ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L267))

- **Sonnet 4.6: Pass.** Section 8 of the notice explicitly addresses privilege handling. It instructs custodians to preserve potentially relevant communications with Legal and outside counsel, legal advice, and attorney work product, and not to delete them. It also instructs that these materials should not be forwarded, disclosed, or placed in a general business review or production folder, and that Legal will handle privilege-sensitive collection and review separately. This satisfies the criterion: privileged materials must be preserved (not destroyed) and will be subject to privilege review before any production.
- **GPT-5.5: Pass.** The notice expressly instructs recipients to preserve privileged communications and attorney work product, not delete them, and states that Legal will handle privilege-sensitive collection and review separately and that the hold does not authorize disclosure outside the company. This addresses preservation without waiver of privilege.

### C-032

ISSUE_007: Proportionality or tiered approach for 85 mobile devices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L275))

- **Sonnet 4.6: Pass.** Both documents explicitly address proportionality and tiering for the 85 field sales representative devices. The litigation hold notice (Section 5) distinguishes between the 30 at-risk phones scheduled for wipe on June 23 (which are suspended and prioritized for collection) and the remaining 55 representatives (who must preserve but will be subject to targeted collection based on relevant surgeon, complaint, and territory information). The preservation action memo (Section 4, iPhones row) further specifies prioritizing the 30 imminent-wipe devices first, then targeting 15-20 of the remaining 55 based on Ohio/Florida named-plaintiff surgeon coverage, complaint geography, and CRM interaction volume. The action register also reflects this tiered approach with different deadlines for the 30 vs. the remaining 55. This clearly satisfies the proportionality/tiered approach criterion.
- **GPT-5.5: Pass.** The output expressly addresses proportionality/tiering for the 85 field sales devices. It requires preservation for all 85, suspends the 30 imminent refresh/wipes, prioritizes forensic imaging of those 30, and recommends targeted/tiered collection for the remaining 55 based on surgeon, complaint, territory, geography, and CRM relevance.

### C-033

ISSUE_008: Personal devices / BYOD preservation addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L284))

- **Sonnet 4.6: Pass.** The hold notice explicitly addresses personal devices and BYOD in multiple sections. Section 3 states that personal phones, email, messaging applications, and cloud storage must be preserved 'to the extent used for Vantage business or containing potentially relevant Vantage information,' listing specific apps like Gmail, iCloud, Google Drive, Dropbox, WhatsApp, Signal, and iMessage/SMS. Section 6 is entirely dedicated to 'Personal devices and accounts' and instructs custodians to preserve work-related information on personal devices and identify those devices/accounts in their acknowledgment. The acknowledgment form also includes a checkbox for 'Personal device, personal email, messaging app, or personal cloud used for Vantage business.' This comprehensively satisfies the criterion.
- **GPT-5.5: Pass.** The hold notice explicitly addresses personal devices, personal email, messaging apps, and personal cloud accounts used for Vantage business, instructing custodians to preserve work-related information on those sources and not delete, reset, or overwrite them. It also includes BYOD-related acknowledgment items.

### C-034

ISSUE_008: Dr. Suresh's potential personal device use flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L292))

- **Sonnet 4.6: Pass.** The preservation action memo explicitly flags Dr. Anita Suresh under the custodians section with the note 'immediate targeted BYOD inquiry (personal iPhone/Gmail/messaging use flagged),' directly identifying her potential personal device/account use as a specific concern. This satisfies the criterion.
- **GPT-5.5: Pass.** The preservation action memo specifically identifies Dr. Anita Suresh and flags an immediate targeted BYOD inquiry, noting “personal iPhone/Gmail/messaging use flagged” in connection with KOL/advisory board communications. It also prioritizes Suresh for personal device/account preservation.

### C-035

ISSUE_009: Backup tapes / disaster recovery archives addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L301))

- **Sonnet 4.6: Pass.** The preservation action memorandum explicitly addresses backup/DR tapes in Section 4 (System-by-system preservation plan) with a dedicated row for 'Backup / DR tapes' instructing to suspend rotation/overwrite/destruction, segregate/label, preserve Commvault catalogs, inventories, dates, locations and logs, and not restore absent a demonstrated source gap. Section 6 also reiterates not restoring backup tapes at this stage but preserving tape media and catalogs as a secondary safeguard. The litigation hold notice itself also references backup-tape overwrite in Section 4 ('do not permit an auto-purge... or backup-tape overwrite to affect covered information'). Both documents clearly address backup tapes and disaster recovery archives as sources that must not be destroyed or overwritten during the hold period.
- **GPT-5.5: Pass.** The preservation action memo explicitly addresses backup/DR tapes, instructing suspension of rotation/overwrite/destruction of potentially relevant tapes, preservation of catalogs/inventories/logs, and identifying point-in-time copies of at-risk sources. It also states not to restore tapes absent a source-data gap. This satisfies the criterion.

### C-036

ISSUE_009: Reasonable accessibility of backup tapes discussed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L310))

- **Sonnet 4.6: Pass.** The preservation action memo explicitly addresses backup tape accessibility and burden considerations. In Section 4 (System-by-system preservation plan), under 'Backup / DR tapes,' it states: 'Do not restore absent a demonstrated source gap; document accessibility/cost.' In Section 6 (Preservation, collection, and privilege safeguards), it states: 'Do not restore backup tapes at this stage. Preserve tape media and catalogs as a secondary safeguard. Assess accessibility and restore only if source-level collection identifies a gap or discovery supports restoration; document the burden and unique data value.' This clearly addresses the concept of deferring restoration decisions and acknowledges accessibility/burden considerations, satisfying the criterion.
- **GPT-5.5: Pass.** The preservation action memo expressly addresses backup/DR tapes, instructing preservation of extant tapes and catalogs while stating not to restore tapes unless a source-data gap is identified. It further says to assess accessibility and document burden/unique data value before any restoration. This satisfies the criterion.

### C-037

ISSUE_010: Acknowledgment requirement included in hold notice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L319))

- **Sonnet 4.6: Pass.** The hold notice includes a detailed 'LITIGATION HOLD ACKNOWLEDGMENT' section at the end with signature lines, checkboxes confirming receipt and understanding, fields for name/title/department/date, and explicit instructions to return the signed form to the General Counsel's Office by June 9, 2025. This clearly satisfies the requirement for a formal acknowledgment mechanism.
- **GPT-5.5: Pass.** The hold notice explicitly requires recipients to return a signed acknowledgment by June 9, 2025 and includes a detailed Litigation Hold Acknowledgment form with checkboxes, signature line, and return instructions confirming receipt, understanding, and compliance obligations.

### C-038

ISSUE_010: Periodic reminders or compliance monitoring mentioned ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L327))

- **Sonnet 4.6: Pass.** The litigation hold notice explicitly states 'Vantage Legal will issue periodic reminders and may conduct compliance checks' in Section 9. The preservation action memo also references 'Aug. 1; quarterly thereafter - First reminder and compliance audit; quarterly reminders, questionnaire updates, interviews and hold log maintenance' in the action register. Both documents clearly address periodic reminders and ongoing compliance monitoring.
- **GPT-5.5: Pass.** The litigation hold notice expressly states that Legal will issue periodic reminders and may conduct compliance checks, and the preservation memo includes quarterly reminders, compliance audits, follow-up for nonresponders, and verification/monitoring steps.

### C-039

ISSUE_011: Veeva Vault audit trail and version preservation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L336))

- **Sonnet 4.6: Pass.** Both documents address Veeva Vault preservation with specificity beyond generic 'preserve Veeva documents' language. The litigation hold notice (Section 3) explicitly states to preserve 'all relevant controlled records, including drafts, prior/superseded versions, audit trails, electronic signatures, relationships, and lifecycle metadata.' The preservation action memo (Section 4) instructs to 'Suspend KR-3000 obsolescence, archival, and 180-day abandoned-draft purge under validated change control. Preserve all versions, audit trails, e-signatures, relationships and user permissions using Vault API/Loader or Veeva Professional Services---not PDFs alone.' These instructions clearly address audit trails, version history, metadata, and document lifecycle workflows (obsolescence, archival, draft purge suspension), satisfying the criterion.
- **GPT-5.5: Pass.** The output specifically instructs preservation of Veeva Vault QMS/Submissions drafts, prior/superseded versions, audit trails, electronic signatures, relationships, and lifecycle metadata, and the action memo further directs suspension of Veeva obsolescence, archival, and abandoned-draft purge workflows. This exceeds a generic Veeva preservation reference.

### C-040

ISSUE_011: Veeva document lifecycle suspension instruction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L345))

- **Sonnet 4.6: Pass.** The preservation-action-memo.docx explicitly instructs to 'Suspend KR-3000 obsolescence, archival, and 180-day abandoned-draft purge under validated change control' in the Veeva Vault QMS/Submissions row of the system-by-system preservation plan (Section 4). Additionally, Section 1 directive 2 states to 'suspend Teams chat/monthly purge, voicemail auto-deletion where relevant, and Veeva abandoned-draft purge.' The litigation hold notice also references preserving Veeva Vault records. These instructions clearly direct QA/Regulatory teams to suspend document lifecycle workflows within Veeva Vault for KR-3000-related records.
- **GPT-5.5: Pass.** The preservation action memo expressly instructs relevant Veeva owners to “Suspend KR-3000 obsolescence, archival, and 180-day abandoned-draft purge” for Veeva Vault QMS/Submissions, and the hold notice also references halting Veeva draft purge. This satisfies the requirement to halt Veeva document lifecycle workflows for KR-3000-related records.

### C-041

Memo identifies Petrosian imaging before June 20 as critical action ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L354))

- **Sonnet 4.6: Pass.** The memo explicitly identifies Sandra K. Petrosian as a 'Critical' custodian with a note to 'preserve before departure.' It includes a specific action item: 'Complete Petrosian laptop/portable-media forensic imaging (preferred one-week buffer); preserve home/QA drives' with a deadline of 'By June 13.' Additionally, Section 1 Directive 4 states: 'Suspend Petrosian's ordinary offboarding... Complete forensic imaging of her laptop and portable media by June 13.' This clearly identifies forensic imaging of Petrosian's data before her June 20 departure as a critical time-sensitive action.
- **GPT-5.5: Pass.** The memo explicitly identifies Sandra Petrosian as a critical custodian departing June 20 and directs forensic imaging of her laptop/portable media by June 13, along with preservation of her mailbox, drives, Veeva content, and related data before departure.

### C-042

Memo identifies SAP migration halt/preservation before June 16 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L362))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the SAP ECC 6.0 migration beginning June 16 as a critical time-sensitive risk. In Section 1 (Directive 3), it states: 'Freeze KR-3000 SAP changes before the migration touches relevant data' and sets a target of 'June 14 at latest' for completing a validated export or forensic snapshot. The action register also lists 'By June 14; before relevant migration activity' as a deadline to 'Complete and validate KR-3000 SAP ECC image/export.' The executive summary also flags the SAP migration as one of the most immediate risks. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo repeatedly identifies the SAP ECC to S/4HANA migration beginning June 16 as an immediate preservation risk and directs a legal freeze/carve-out, validated export or forensic snapshot of KR-3000-related legacy SAP data by June 14/before migration activity, with no decommissioning absent GC approval.

### C-043

Memo identifies mobile device wipe halt before June 23 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L370))

- **Sonnet 4.6: Pass.** The memo explicitly identifies halting mobile device wipes before June 23 as a critical action. In Section 1 (Decisions and directives for immediate action), it states: 'Halt all 30 scheduled phone refresh/wipes; target imaging before June 20 (preferably June 18) and in all events before any wipe.' The action register also includes a June 16-18 target (no later than June 20) for imaging the 30 at-risk iPhones, and a June 23 entry stating 'Keep refresh suspended for any device not fully imaged and verified; no factory reset or recycler transfer without written Legal authorization.' This clearly identifies halting mobile device wipes before the June 23 scheduled refresh.
- **GPT-5.5: Pass.** The memo explicitly identifies the June 23 iPhone refresh/wipe risk and directs halting all 30 scheduled phone refresh/wipes, preserving all 85 phones, and imaging the at-risk devices before June 20 / before any wipe.

### C-044

Memo identifies email purge suspension before June 30 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L378))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the June 30 M365 email auto-purge as a critical risk in the Executive Summary ('M365 email auto-purge runs June 30') and includes multiple directives to suspend it: in Section 1 ('disable the M365 three-year email purge'), in the Action Register ('Ensure June 30 purge cannot run'), and in Section 6. The memo clearly identifies suspending the June 30 email auto-purge as a critical action.
- **GPT-5.5: Pass.** The memo explicitly identifies the June 30 M365 email auto-purge as an immediate risk and directs suspension/disablement of the email purge before June 30, including verification that the June 30 purge cannot run.

### C-045

Memo correctly sequences urgent actions by deadline ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L386))

- **Sonnet 4.6: Pass.** The memo's action register (Section 5) lists deadlines in chronological order: June 2 (hold notice), June 3 (M365/Teams purges), June 6 (Ashford demand, SAP freeze), June 9 (acknowledgments), June 13 (Petrosian imaging), June 14 (SAP ECC export before June 16 migration), June 16-18/20 (iPhone imaging before June 20 Petrosian departure), June 20 (Petrosian departure), June 23+ (device refresh suspension), June 27-30 (M365 purge verification), June 30 (remaining phones), July 1/15 (paper records/SAP decommissioning), August 1 (quarterly reminders). The SAP migration deadline (June 14-16) and Petrosian departure (June 20) are both listed before the mobile device wipe (June 23) and email purge (June 30). The sequencing is logically chronological and reflects the actual urgency of each deadline.
- **GPT-5.5: Pass.** The memo presents a chronological action register and executive summary that place the SAP migration-related preservation before June 16 and Petrosian departure actions by June 20, followed by device wipe suspension around June 23 and M365/email purge verification before June 30. This reflects the required deadline order.

### C-046

Memo addresses Ashford third-party coordination ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L394))

- **Sonnet 4.6: Pass.** The memo extensively addresses Ashford Precision Components as a third-party coordination issue. In Section 1 (Directive 5), it explicitly states to send Ashford Precision Components, Inc. a formal preservation demand no later than June 6, provides their address and contact information, references the Quality Agreement QA-2017-0044, and requests written confirmation. Ashford is also mentioned in the scope section, the custodian section (James Kowalski's focus includes Ashford relationship), the system-by-system preservation plan (with a dedicated row for Ashford), and the action register with a June 6 deadline for the preservation demand.
- **GPT-5.5: Pass.** The memo explicitly identifies Ashford Precision Components as a third-party/contract manufacturer coordination issue and recommends sending a formal preservation demand by email and certified mail, with follow-up confirmation and preservation of native-format records.

### C-047

Memo addresses coordination with e-discovery vendor Corestone ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L402))

- **Sonnet 4.6: Pass.** The memo explicitly mentions Corestone Analytics multiple times throughout the document, including in the action register (June 6 entry: 'Book Corestone'), in the system-by-system preservation plan (referencing Corestone as owner for SAP, R&D share, and iPhone collection), in Section 7 (budget section recommending 'authorizing Corestone Analytics to scope and schedule immediate work'), and in Section 8 (directing to convene a preservation meeting with 'Corestone Analytics'). The criterion requires mention of Corestone Analytics for forensic collection, imaging, or processing, which is clearly satisfied.
- **GPT-5.5: Pass.** The memo repeatedly mentions coordinating with Corestone Analytics for SAP preservation, forensic imaging of devices/laptops, phone collection, and immediate scoping/scheduling of preservation work.

### C-048

Memo recommends next steps for hold compliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L410))

- **Sonnet 4.6: Pass.** The memo includes multiple specific next steps for ongoing hold compliance. Section 5 (Action Register) includes 'Aug. 1; quarterly thereafter: First reminder and compliance audit; quarterly reminders, questionnaire updates, interviews and hold log maintenance.' Section 6 states 'Require all recipients to acknowledge receipt...Keep an auditable log of notices, reminders, system holds, migrations, exports, chain of custody, exceptions, and remedial steps. Conduct interviews and verification rather than treating a notice as sufficient by itself.' Section 1 also mentions requiring acknowledgment by June 9 and preserving returned forms. These clearly satisfy the criterion.
- **GPT-5.5: Pass.** The memo recommends multiple specific next steps for ongoing hold compliance, including tracking acknowledgments, following up with nonresponders, conducting custodian interviews/questionnaires, maintaining hold logs, sending quarterly reminders, and performing compliance audits.

### C-049

Hold notice includes consequences of non-compliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L418))

- **Sonnet 4.6: Fail.** I reviewed the entire litigation hold notice carefully, looking for any mention of consequences for non-compliance, such as sanctions, adverse inference instructions, disciplinary action, or other penalties. The notice is comprehensive and covers many aspects of preservation obligations, but it does not include any language about what happens if a custodian fails to comply. There is no mention of court-imposed sanctions, adverse inference jury instructions, spoliation consequences, or internal disciplinary measures (termination, HR action, etc.). The notice only states obligations and instructions, not consequences for failing to follow them.
- **GPT-5.5: Fail.** The notice gives detailed preservation instructions and mentions compliance checks, but it does not state any consequences for failure to comply, such as court sanctions, adverse inference instructions, disciplinary action, or other internal/court-imposed consequences.

### C-050

Hold notice provides contact information for questions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L426))

- **Sonnet 4.6: Pass.** The notice explicitly provides contact information in Section 9: Priya Chandrasekaran, General Counsel, reachable by replying to the notice email or at extension 4200, and Marcus Tilden, Director of IT, at 260-555-0184. The acknowledgment return section also lists 260-555-4200. Multiple contact persons and methods are clearly provided.
- **GPT-5.5: Pass.** The notice provides clear contact information for questions, including Priya Chandrasekaran, General Counsel, with instructions to reply to the transmitting email or contact the Legal Department at extension 4200, as well as Marcus Tilden with a phone number for technical coordination.

### C-051

Hold notice instructs custodians not to delete/destroy documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L434))

- **Sonnet 4.6: Pass.** The notice contains extensive and explicit instructions prohibiting custodians from deleting, destroying, altering, or overwriting documents. Section 4 is titled 'Immediate instructions --- do not delete, alter, or destroy' and contains multiple specific prohibitions including stopping 'manual deletion, editing, overwriting, shredding, disposal, or alteration of covered information,' not deleting messages, not emptying trash/recycle folders, not purging drafts, etc. Section 5 also instructs field sales reps not to delete conversations. The acknowledgment form also includes a checkbox confirming the custodian has stopped 'routine or manual deletion, alteration, disposal, wipe, or retention process that could affect covered information.' The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The notice clearly instructs custodians to stop deletion, editing, overwriting, shredding, disposal, alteration, wiping, resetting, purging, and destruction of potentially relevant documents and data, including routine retention processes and device wipes.

### C-052

Hold notice instructs suspension of routine destruction policies ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L442))

- **Sonnet 4.6: Pass.** The notice explicitly states in multiple places that routine retention schedules and destruction policies are suspended. Section 4 states 'Do not use normal retention or offboarding procedures to delete or archive covered information.' The notice also contains a highlighted box stating 'This hold remains in effect unless and until you receive written notice from the General Counsel that it has been lifted. Normal retention schedules do not apply to covered material while the hold is active.' Additionally, the acknowledgment form includes a checkbox confirming the recipient has stopped 'any routine or manual deletion, alteration, disposal, wipe, or retention process that could affect covered information.' These provisions clearly satisfy the criterion.
- **GPT-5.5: Pass.** The notice explicitly instructs recipients to suspend routine deletion, disposal, device wiping, data migration, auto-purges, offboarding deletion, and states that normal retention schedules do not apply to covered material while the hold is active.

### C-053

Correct date of complaint service: May 28, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L450))

- **Sonnet 4.6: Pass.** The notice explicitly states in Section 1: 'Vantage was served on May 28, 2025 with a putative class action concerning the ProFlex KR-3000 Total Knee Replacement System.' This matches the criterion exactly.
- **GPT-5.5: Pass.** The notice explicitly states: “Vantage was served on May 28, 2025 with a putative class action...,” which matches the required complaint service date.

### C-054

Correct product description: CoCrMo femoral component ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L458))

- **Sonnet 4.6: Pass.** The notice references 'premature wear and metal debris' in Section 1, and in Section 2 explicitly mentions 'metallurgical, materials-science, retrieval, and failure analyses,' 'CoCrMo, UHMWPE, and titanium materials,' 'surface-finish measurements,' 'metal-ion data,' and 'the Q3 2022 metallurgical analysis.' These references are consistent with design defect allegations involving premature wear, elevated cobalt/chromium ion levels, and articular surface finish issues. The product defect allegations are not materially misstated.
- **GPT-5.5: Pass.** The notice accurately references the alleged defect theory, including premature wear, metal debris, surface finish/roughening and metallurgical analyses, CoCrMo materials, and metal-ion data. It does not materially misstate the product defect allegations.

### C-055

Hold notice defines subject matter scope covering key categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L466))

- **Sonnet 4.6: Pass.** The notice clearly covers all 6 categories: (1) design and development - 'Product design and development; design history files; engineering notebooks; CAD/SolidWorks files...'; (2) testing - 'Pre-market and post-market testing, including bench and wear testing; cyclical loading...'; (3) manufacturing - 'Manufacturing and quality: batch/device-history records; production orders...'; (4) marketing/sales - 'Sales, marketing, training, and field activity: promotional claims and presentations; surgeon training; sales-force communications...'; (5) complaint handling or adverse events - 'complaints; complaint trending; CAPAs; MDRs; adverse-event assessments...'; (6) regulatory submissions or FDA communications - '510(k) submission K192847...FDA submissions and correspondence...' All 6 of the 6 required categories are present, well exceeding the threshold of 4.
- **GPT-5.5: Pass.** The notice’s subject matter scope expressly covers design and development, testing, manufacturing/quality, sales/marketing/training, complaint handling/adverse events/CAPAs/MDRs, and regulatory/FDA submissions and correspondence. This includes at least 4 of the 6 required categories.

### C-056

Hold notice addresses IT Department / Marcus Tilden's role ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L474))

- **Sonnet 4.6: Pass.** The notice explicitly identifies Marcus Tilden, Director of IT, by name and phone number (260-555-0184) as the technical coordination contact. Additionally, the notice addresses IT's implementation role in multiple places: Section 5 mentions 'Legal will coordinate targeted collection, prioritizing the 30 at-risk phones' with IT involvement; Section 7 states 'IT, HR, and Legal will coordinate collection and account continuity' and 'Forensic imaging must be completed by June 13, 2025'; Section 9 directs recipients to 'contact Marcus Tilden, Director of IT, at 260-555-0184' for technical coordination. The notice also addresses IT-relevant actions like suspending device refreshes/wipes, halting migrations, and preserving backup systems throughout the document.
- **GPT-5.5: Pass.** The notice identifies IT administrators as recipients, names Marcus Tilden as Director of IT for technical coordination, and assigns IT/Legal roles in preservation actions such as device handling, collection, and forensic imaging, while also directing suspension of auto-purge, migrations, wipes, and other IT-controlled processes.

### C-057

Hold notice mentions the 510(k) clearance or FDA regulatory filings ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L482))

- **Sonnet 4.6: Pass.** The notice explicitly mentions '510(k) submission K192847 and ProFlex KR-2500 predicate materials; FDA submissions and correspondence' under the regulatory and quality-system records section, clearly identifying FDA regulatory filings as within the scope of preservation.
- **GPT-5.5: Pass.** The notice expressly includes “Regulatory and quality-system records: 510(k) submission K192847 and ProFlex KR-2500 predicate materials; FDA submissions and correspondence,” within the scope of preservation.

### C-058

Hold notice addresses CAPA records and MDR reports ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L490))

- **Sonnet 4.6: Pass.** Section 2 of the notice explicitly mentions both 'CAPAs' and 'MDRs' under the regulatory and quality-system records bullet: 'complaints; complaint trending; CAPAs; MDRs; adverse-event assessments; audits; field safety, recall, correction/removal, or other corrective-action evaluations.' Both CAPA records and MDR reports are clearly identified as within scope of preservation.
- **GPT-5.5: Pass.** The notice expressly includes “CAPAs” and “MDRs” within the scope of regulatory and quality-system records to be preserved.

### C-059

Hold notice addresses field sales representative communications ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L498))

- **Sonnet 4.6: Pass.** Section 5 is explicitly dedicated to 'Additional instructions for field sales representatives and mobile-device users,' addressing all 85 field sales representatives. It covers preservation of KR-3000-related communications including text/iMessage/SMS, WhatsApp, VantagePulse content, call logs, voicemail, photographs/videos, notes, and 'surgeon or hospital communications on company and personal devices/accounts.' The notice also suspends the June 23 device refresh for affected representatives and outlines coordination for collection. Section 2 also references sales-force communications, CRM records, complaint escalations, and surgeon/hospital interactions. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The notice expressly includes the 85 field sales representatives as recipients and contains a dedicated section requiring them to preserve KR-3000-related communications, including surgeon or hospital communications, texts, WhatsApp, VantagePulse, call logs, voicemails, and related mobile data.

### C-060

Memo addresses coordination with outside counsel Calloway Prichard Weeks ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L506))

- **Sonnet 4.6: Pass.** The memo explicitly mentions Natalie R. Prichard, Partner, Calloway Prichard Weeks LLP as the author (FROM field), and references coordination with outside counsel multiple times throughout the document, including in Section 5 (Action Register) where 'Prichard / Legal' is listed as accountable for multiple actions, and in Section 8 where it states to convene a preservation meeting with 'outside counsel' and lists 'Prichard' as a participant in the June 3-4 meeting.
- **GPT-5.5: Pass.** The memo identifies Natalie R. Prichard of Calloway Prichard Weeks LLP as outside counsel and repeatedly includes outside counsel/Prichard in preservation next steps, including issuing demands, preservation meetings, oversight, and coordination with vendors.

### C-061

Hold notice date is approximately June 2, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L514))

- **Sonnet 4.6: Pass.** The notice header shows 'DATE: May 30, 2025 (prepared for distribution June 2, 2025)'. The distribution date is June 2, 2025, which exactly matches the criterion. The document was prepared May 30 but explicitly states it is for distribution June 2, 2025, which is the operative date for the hold notice.
- **GPT-5.5: Pass.** The notice includes a DATE line of May 30, 2025, but expressly states it was prepared for distribution June 2, 2025 and uses June 2 as the planned distribution date. This is effectively dated very close to/at June 2 for notice purposes.
