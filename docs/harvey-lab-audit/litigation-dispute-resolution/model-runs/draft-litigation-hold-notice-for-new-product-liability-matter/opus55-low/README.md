# Claude Opus 5.5 (low): Draft Litigation Hold Notice for New Product Liability Class Action (Medical Device)

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-litigation-hold-notice-for-new-product-liability-matter/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 60 of 61 criteria; GPT-5.5 passed 60 of 61 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-008](#c-008) | Hold notice explains the legal obligation to preserve documents | Pass | Pass |
| [C-009](#c-009) | Hold notice defines preservation period starting January 1, 2017 | Pass | Pass |
| [C-010](#c-010) | Hold notice defines preservation period extending through the present | Pass | Pass |
| [C-011](#c-011) | Hold notice lists key custodians by name (threshold) | Pass | Pass |
| [C-012](#c-012) | Hold notice specifies email as a data type to preserve | Pass | Pass |
| [C-013](#c-013) | Hold notice specifies text messages and messaging apps | Pass | Pass |
| [C-014](#c-014) | Hold notice covers Veeva Vault documents | Pass | Pass |
| [C-015](#c-015) | Hold notice covers SAP / ERP data | Pass | Pass |
| [C-016](#c-016) | Hold notice covers Salesforce CRM data | Pass | Pass |
| [C-017](#c-017) | Hold notice covers VantagePulse app data | Pass | Pass |
| [C-018](#c-018) | Hold notice covers R&D files including CAD/engineering data | Pass | Pass |
| [C-019](#c-019) | Hold notice covers paper/hard copy documents | Pass | Pass |
| [C-020](#c-020) | ISSUE_001: SAP migration addressed with halt/carve-out instruction | Pass | Pass |
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
| [C-049](#c-049) | Hold notice includes consequences of non-compliance | Pass | Pass |
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

- **Sonnet 4.6: Pass.** The agent produced a comprehensive document clearly titled 'LITIGATION HOLD NOTICE' with the subtitle 'Mandatory Preservation of Documents, Data, and Physical Items'. It is explicitly labeled as a litigation hold notice and contains all the typical elements of such a document.
- **GPT-5.5: Pass.** The agent produced a document explicitly titled and labeled “LITIGATION HOLD NOTICE,” with preservation instructions, recipients, attachments, and related hold details.

### C-002

Preservation action memo document is produced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L28))

- **Sonnet 4.6: Pass.** The agent produced a separate preservation action memo (preservation-action-memo.docx) addressed to the General Counsel (Priya Chandrasekaran) from the Legal Department. It is clearly a standalone document distinct from the hold notice itself, containing a full action plan, destruction calendar, discrepancy analysis, and decisions needed from the GC. This satisfies the criterion of producing a separate cover memo/preservation action memo addressed to or for the General Counsel.
- **GPT-5.5: Pass.** The output is explicitly a separate document titled 'preservation-action-memo.docx' and formatted as a memorandum from the Legal Department to the General Counsel, with a preservation action plan and decisions needed. It is not merely embedded within a hold notice.

### C-003

Hold notice identifies correct case name ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L36))

- **Sonnet 4.6: Pass.** The litigation hold notice clearly identifies the matter as 'Kessler et al. v. Vantage Medical Devices, Inc.' in multiple places, including the header table, Section 1, Attachment 1, and throughout the document. This matches the required case name exactly.
- **GPT-5.5: Pass.** The litigation hold notice identifies the matter as “Kessler et al. v. Vantage Medical Devices, Inc.” in the header and attachments, matching the required case name.

### C-004

Hold notice identifies correct case number ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L44))

- **Sonnet 4.6: Pass.** The litigation hold notice clearly identifies Case No. 1:25-cv-04387-RLM in the header table under 'MATTER' and again in Attachment 1. The case number matches exactly what the criterion requires.
- **GPT-5.5: Pass.** The litigation hold notice expressly identifies the matter as Case No. 1:25-cv-04387-RLM in the header and attachments.

### C-005

Hold notice identifies correct court ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L52))

- **Sonnet 4.6: Pass.** The litigation hold notice clearly identifies the court as 'U.S. District Court, Southern District of Indiana' in the matter header (Case No. 1:25-cv-04387-RLM (U.S. District Court, Southern District of Indiana)), and this is repeated in Attachment 1 as '(S.D. Ind.)'
- **GPT-5.5: Pass.** The hold notice identifies the matter as pending in the U.S. District Court for the Southern District of Indiana, including references to “S.D. Ind.” in attachments.

### C-006

Hold notice states it is issued by General Counsel Priya Chandrasekaran ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L60))

- **Sonnet 4.6: Pass.** The notice clearly states 'FROM: Priya Chandrasekaran, General Counsel' in the header, and is signed at the bottom by 'Priya Chandrasekaran, General Counsel, Vantage Medical Devices, Inc.' She is identified by name as General Counsel and as the issuer of the notice throughout the document.
- **GPT-5.5: Pass.** The notice identifies the sender as Priya Chandrasekaran, General Counsel, in the header and is signed by her as General Counsel.

### C-007

Hold notice identifies the ProFlex KR-3000 as the product at issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L68))

- **Sonnet 4.6: Pass.** The notice repeatedly and explicitly identifies the 'ProFlex KR-3000 Total Knee Replacement System' as the product at issue, starting from the header/matter line and throughout the document.
- **GPT-5.5: Pass.** The notice explicitly identifies the matter as involving the “ProFlex KR-3000 Total Knee Replacement System” and repeatedly refers to the KR-3000 as the product at issue.

### C-008

Hold notice explains the legal obligation to preserve documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L76))

- **Sonnet 4.6: Pass.** The notice clearly explains the legal obligation to preserve documents in multiple places. Section 1 states 'the Company and its employees are legally required to preserve all information that may be relevant to the claims or defenses in the case.' Section 12 states 'Failure to comply can expose the Company to serious court sanctions and may result in disciplinary action up to and including termination.' The summary box at the top also emphasizes immediate action requirements. Both the duty to preserve and the consequences of failure (court sanctions, disciplinary action) are explicitly addressed.
- **GPT-5.5: Pass.** The notice explicitly states that the Company and employees are legally required to preserve all relevant information, including documents and ESI, and that the hold overrides normal retention/destruction practices. It also warns that failure to comply can expose the Company to court sanctions and may result in disciplinary action.

### C-009

Hold notice defines preservation period starting January 1, 2017 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L84))

- **Sonnet 4.6: Pass.** Section 2 of the notice explicitly states: 'Preserve covered information created, sent, received, or modified from January 1, 2017 through the present, and going forward for as long as this hold is in effect.' The start date of January 1, 2017 is clearly specified. Additionally, Attachment 2 (Questionnaire) question B.16 also references 'since January 1, 2017' for mobile devices. The criterion is satisfied.
- **GPT-5.5: Pass.** The notice expressly states in Section 2 that covered information must be preserved from “January 1, 2017 through the present, and going forward,” satisfying the required preservation period start date.

### C-010

Hold notice defines preservation period extending through the present ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L92))

- **Sonnet 4.6: Pass.** Section 2 explicitly states: 'Preserve covered information created, sent, received, or modified from January 1, 2017 through the present, and going forward for as long as this hold is in effect.' Section 12 also states: 'This hold remains in effect until lifted in writing by the General Counsel.' The preservation period clearly extends through the present and is ongoing, not ending at a fixed past date.
- **GPT-5.5: Pass.** The notice expressly states the preservation period runs from January 1, 2017 “through the present, and going forward” and remains in effect until lifted in writing, so it is ongoing rather than ending on a fixed past date.

### C-011

Hold notice lists key custodians by name (threshold) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L100))

- **Sonnet 4.6: Pass.** All 10 custodians are identified by name in the document: (1) Dr. Wei-Lin Huang, (2) Sandra K. Petrosian, (3) Thomas J. Braddock, (4) Michelle R. Torrence, (5) James D. Kowalski, (6) Dr. Anita Suresh, (7) Brian P. Callahan, (8) Gerald T. Morrissey, (9) Priya Chandrasekaran, and (10) Marcus Tilden. This exceeds the threshold of 8 out of 10.
- **GPT-5.5: Pass.** The notice identifies all 10 listed custodians by name in Schedule A and elsewhere, exceeding the threshold of at least 8.

### C-012

Hold notice specifies email as a data type to preserve ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L108))

- **Sonnet 4.6: Pass.** The notice explicitly lists email as a data type to preserve. In Section 4 (Types of Information and Where It May Be), under 'Email & collaboration,' it specifically mentions 'Microsoft 365 email (including Archive, Deleted Items, Sent Items), Teams chats and channel posts, calendar items, OneDrive, SharePoint sites, shared mailboxes (e.g., Quality@, RegulatoryAffairs@).' Email is clearly and explicitly called out as a category of data to be preserved.
- **GPT-5.5: Pass.** The notice explicitly identifies email as covered data to preserve, including references to “email,” “Microsoft 365 email,” archive/deleted/sent items, personal email, and shared mailboxes.

### C-013

Hold notice specifies text messages and messaging apps ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L116))

- **Sonnet 4.6: Pass.** The notice explicitly mentions text messages (SMS/iMessage), WhatsApp, Signal, Telegram, and other messaging apps in multiple sections including Section 4 (Types of Information), Section 5 (Personal Devices), Section 6 (specific instructions for mobile devices and messaging apps), and Attachment 3 (field sales supplement). These are clearly and repeatedly listed as data to be preserved.
- **GPT-5.5: Pass.** The hold notice explicitly requires preservation of text messages (SMS/iMessage) and third-party messaging apps including WhatsApp, Signal, Telegram, and LinkedIn, and gives specific instructions to disable disappearing messages.

### C-014

Hold notice covers Veeva Vault documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L124))

- **Sonnet 4.6: Pass.** Veeva Vault is explicitly mentioned multiple times throughout the notice, including in the business systems table (Section 4), in custodian-specific instructions for Sandra Petrosian, Thomas Braddock, and others, and in Section 7's prohibition on modifying Veeva Vault documents. It is clearly identified as a source of data to be preserved.
- **GPT-5.5: Pass.** The notice explicitly identifies Veeva Vault QMS and Submissions as business systems/data sources to preserve and includes specific instructions about Veeva Vault documents, audit trails, workflows, and exports.

### C-015

Hold notice covers SAP / ERP data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L132))

- **Sonnet 4.6: Pass.** The notice explicitly mentions SAP multiple times. In Section 4 (Types of Information), SAP (ECC 6.0 and S/4HANA) is listed under Business Systems. In the custodian-specific instructions for James D. Kowalski, it directs him to 'Work with IT and Corestone to identify all KR-3000 SAP data (material numbers, production orders, batches, QM lots, change documents) for preservation before June 16, 2025.' The IT department distribution list also includes 'SAP Basis/migration team.' Manufacturing batch records, supplier records, and inspection data are all covered within the SAP preservation scope.
- **GPT-5.5: Pass.** The hold notice expressly includes SAP (ECC 6.0 and S/4HANA) as a covered business system and identifies manufacturing batch/device history records, supplier quality records, inspection data, production orders, QM lots, and related SAP data for preservation.

### C-016

Hold notice covers Salesforce CRM data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L140))

- **Sonnet 4.6: Pass.** The notice explicitly mentions Salesforce multiple times. In Section 3 (Subject Matter Covered), it lists 'Salesforce records' under Sales, marketing, and field communications. In Section 4 (Types of Information), Salesforce CRM is listed as a business system. In Attachment 3 (Field Sales), it instructs representatives not to delete Salesforce activity records. In Attachment 4, Michelle Torrence is instructed to cease Salesforce data clean-up. Salesforce CRM data is clearly within scope.
- **GPT-5.5: Pass.** The hold notice explicitly includes Salesforce/CRM data multiple times, including 'Salesforce records' under sales/marketing, 'Salesforce CRM' in business systems, Salesforce administrators in the distribution list, and instructions not to delete/edit Salesforce activity records.

### C-017

Hold notice covers VantagePulse app data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L148))

- **Sonnet 4.6: Pass.** VantagePulse is explicitly mentioned multiple times throughout the notice: in Section 4's table of business systems, in Section 6's specific mobile device instructions (do not uninstall VantagePulse or log out in a way that clears local data), in Attachment 3's field sales representative instructions (item 29, specifically addressing VantagePulse notes, messages, photos, feedback forms, and offline logs), and in the custodian-specific instructions for Michelle R. Torrence. The notice clearly identifies VantagePulse as within scope of the litigation hold.
- **GPT-5.5: Pass.** The notice expressly identifies VantagePulse as covered, including VantagePulse records in the subject matter/systems sections and specific instructions not to uninstall or clear VantagePulse app data, notes, messages, photos, feedback forms, or offline logs.

### C-018

Hold notice covers R&D files including CAD/engineering data ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L156))

- **Sonnet 4.6: Pass.** The notice explicitly identifies CAD (SolidWorks) files, finite element analysis (FEA), engineering change orders, and engineering notebooks as covered items in Section 3. It also references the R&D shared drive (\\VNTG-ENG01\RnD\KR3000) and SolidWorks PDM in Section 4, and Attachment 4 (Dr. Wei-Lin Huang's custodian-specific instructions) specifically addresses the engineering notebooks and the R&D network drive. All required R&D engineering file types are clearly within scope.
- **GPT-5.5: Pass.** The notice expressly includes R&D engineering data within scope, including CAD/SolidWorks files, FEA, engineering change orders, engineering notebooks, SolidWorks PDM, and the R&D shared drive \\VNTG-ENG01\RnD\KR3000.

### C-019

Hold notice covers paper/hard copy documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L164))

- **Sonnet 4.6: Pass.** The notice explicitly includes paper and hard-copy documents in multiple places. Section 4 lists 'Paper & physical items' as a category, with examples including 'Engineering notebooks, lab notebooks, paper batch travelers, signed quality records, meeting notes, desk files, printouts with handwritten notes.' Attachment 2 (Question 15) asks about 'paper files, notebooks, or physical items.' Attachment 4 references engineering notebooks and paper batch travelers. The scope clearly covers paper/hard-copy documents.
- **GPT-5.5: Pass.** The notice expressly includes paper and hard-copy materials within the hold, including engineering notebooks, lab notebooks, paper batch travelers, signed quality records, meeting notes, desk files, printouts with handwritten notes, paper files, and hard-copy distribution instructions.

### C-020

ISSUE_001: SAP migration addressed with halt/carve-out instruction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L172))

- **Sonnet 4.6: Pass.** The notice explicitly mentions the SAP ECC 6.0 to S/4HANA migration in the custodian-specific instructions for James D. Kowalski (VP Manufacturing Operations): 'Work with IT and Corestone to identify all KR-3000 SAP data (material numbers, production orders, batches, QM lots, change documents) for preservation before June 16, 2025. No archival, ILM move, or decommissioning of KR-3000 data may occur without the General Counsel's written sign-off.' The June 16, 2025 deadline aligns with the migration date referenced in the criterion. The notice also references SAP (ECC 6.0 and S/4HANA) in the data sources table and instructs IT separately. This satisfies the criterion by specifically addressing the SAP migration and requiring that relevant legacy data be preserved before any migration or decommissioning proceeds.
- **GPT-5.5: Pass.** The notice identifies SAP ECC 6.0/S/4HANA, includes the SAP Basis/migration team, and gives a custodian-specific instruction to identify and preserve KR-3000 SAP data—including production orders, batches, QM lots, and change documents—before June 16, 2025, with no archival, ILM move, or decommissioning without General Counsel sign-off. This sufficiently addresses the SAP migration/decommissioning risk and requires relevant legacy data preservation before the June 16 migration activity proceeds.

### C-021

ISSUE_001: SAP legacy decommissioning by July 15 flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L180))

- **Sonnet 4.6: Pass.** The preservation-action-memo.docx explicitly mentions the July 15 decommissioning date multiple times. In Section III (Destruction Calendar), it lists 'July 15: Legacy SAP ECC 6.0 decommissioned; servers shut down' as a scheduled event with 'Native relational SAP data' at risk, requiring 'No decommissioning without written GC sign-off.' In Section IV.B, it states 'do not decommission on July 15' and sets a 'July 14: written GC sign-off gate.' The Master Action Tracker (item 26) also lists 'SAP decommissioning sign-off gate (default: not approved)' with a July 14 deadline. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The preservation-action memo explicitly lists July 15 as the date legacy SAP ECC 6.0 would be decommissioned and servers shut down, identifies native SAP data as at risk, and sets action items requiring no decommissioning without GC sign-off and preservation steps before then.

### C-022

ISSUE_002: Email auto-purge on June 30 addressed with suspension ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L189))

- **Sonnet 4.6: Fail.** The litigation hold notice does not specifically mention the quarterly email auto-purge scheduled for June 30, 2025, nor does it instruct that this specific auto-purge must be suspended or disabled. While the notice generally instructs recipients to preserve all information and override normal retention/auto-delete settings, it does not address the specific June 30, 2025 email auto-purge event that would destroy emails older than 3 years (pre-June 30, 2022). The criterion requires specific mention of this scheduled purge and explicit instruction to suspend/disable it.
- **GPT-5.5: Fail.** The notice contains broad instructions to override normal retention periods and auto-delete settings, but it does not specifically mention the quarterly email auto-purge scheduled for June 30, 2025 or the risk of deleting emails older than three years, nor does it specifically instruct that this email purge be suspended or disabled.

### C-023

ISSUE_002: Retention policy VNT-POL-007 referenced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L197))

- **Sonnet 4.6: Pass.** Both documents reference VNT-POL-007 by name and number multiple times. The litigation hold notice explicitly states it is 'issued under Section 7 of the Company's Document Retention and Destruction Policy, VNT-POL-007, Rev. 3' and that it 'overrides every normal retention period, auto-delete setting, destruction schedule...' The preservation action memo references VNT-POL-007 extensively in connection with email purges, Teams purges, and the need to override normal retention schedules (e.g., 'Under VNT-POL-007 Teams chat purges monthly,' 'VNT-POL-007 §§4.1, 5.2,' etc.)
- **GPT-5.5: Pass.** The litigation hold notice explicitly states it is issued under Section 7 of the Company's Document Retention and Destruction Policy, VNT-POL-007, Rev. 3 and that it overrides normal retention periods, auto-delete settings, destruction schedules, and related practices. The preservation memo also references VNT-POL-007 in connection with email and other auto-purges.

### C-024

ISSUE_003: Sandra Petrosian's departure flagged as urgent ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L206))

- **Sonnet 4.6: Pass.** Both documents extensively flag Sandra K. Petrosian's departure as an urgent preservation issue. The litigation hold notice (Schedule A) explicitly notes she is 'departing June 20, 2025' and Attachment 4 provides custodian-specific instructions for her, including forensic imaging by June 13, suspension of standard offboarding, and a departure certification. The preservation action memo dedicates an entire section (Section IV.C) to her departure, identifies the June 13 HR offboarding workflow auto-start as a hard deadline, lists her in the destruction calendar, and includes a written HR directive (Appendix A-2) specifically suspending her offboarding procedures. The memo also notes she is the sole Veeva QMS administrator, adding urgency.
- **GPT-5.5: Pass.** The output specifically flags Sandra K. Petrosian as departing on June 20, 2025 and treats it as an urgent preservation issue, including immediate suspension of offboarding, preservation of her laptop/iPhone/mailbox/H: drive/Veeva access, forensic imaging by June 13, and HR/IT directives.

### C-025

ISSUE_003: Forensic imaging of Petrosian's devices before departure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L215))

- **Sonnet 4.6: Pass.** Both documents explicitly address forensic imaging of Petrosian's devices before her June 20 departure. The litigation hold notice (Attachment 4) states that Corestone Analytics will forensically image her laptop, company iPhone, and H: drive, and export Veeva Vault data, on a date scheduled no later than June 13, 2025. The preservation action memo (Section III.C and the action tracker) reiterates that forensic imaging must be completed by June 13, well before her June 20 last day, covering laptop, company iPhone, H: drive, and Veeva Vault export. Appendix A-2 also directs HR to suspend standard offboarding procedures for Petrosian.
- **GPT-5.5: Pass.** The output expressly instructs that Sandra Petrosian’s standard offboarding be suspended and that Corestone forensically image her laptop, company iPhone, H: drive/network data, and export Veeva Vault data no later than June 13, 2025, before her June 20 departure.

### C-026

ISSUE_004: Mobile device refresh/wipe halted ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L224))

- **Sonnet 4.6: Pass.** The notice explicitly addresses the scheduled device refresh in Attachment 3 (Supplemental Hold Notice to Field Sales Representatives), item 26: 'The scheduled device refresh (including the replacement cycle that was to begin June 23, 2025) is suspended. Do not return, reset, wipe, or trade in your device unless you receive written shipping instructions from the Legal Department or its forensic vendor, Corestone Analytics, for preservation imaging.' This directly addresses the June 23, 2025 replacement cycle and instructs that it must be halted until data is preserved. The general notice also states in Section 6 that 'Company device refresh is suspended' and that no company-issued device will be wiped or replaced until forensically preserved.
- **GPT-5.5: Pass.** The notice explicitly states that company device refresh is suspended and that no covered company-issued device may be wiped or replaced until forensically preserved. Attachment 3 specifically references the scheduled device refresh/replacement cycle beginning June 23, 2025 and instructs field representatives not to return, reset, wipe, or trade in devices except for preservation imaging. Although it does not mention '30' iPhones, it clearly addresses the scheduled refresh/wipe and halts it or requires preservation first.

### C-027

ISSUE_004: WhatsApp and third-party app data on mobile devices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L232))

- **Sonnet 4.6: Pass.** The notice explicitly mentions WhatsApp multiple times in the context of field sales representatives' mobile devices. In Attachment 3 (Supplemental Hold Notice to Field Sales Representatives), item 27 states 'Do not delete texts, iMessages, WhatsApp chats, call logs, voicemails, or photos' and item 28 instructs 'turn off WhatsApp "Disappearing messages" and any default message timer.' Additionally, Section 6 of the main notice provides specific instructions for WhatsApp/Signal/other apps. The notice clearly identifies WhatsApp and third-party messaging app data on mobile devices as within scope of preservation for field sales representatives.
- **GPT-5.5: Pass.** The notice specifically addresses field sales representatives and instructs them not to delete WhatsApp chats and other mobile messaging data, to turn off WhatsApp disappearing messages, and to preserve personal phone/app communications relating to KR-3000.

### C-028

ISSUE_005: Ashford Precision Components preservation addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L240))

- **Sonnet 4.6: Pass.** Both documents extensively address Ashford Precision Components, Inc. The litigation hold notice (Section 3) explicitly covers manufacturing records at 'Ashford Precision Components, Inc. (Grand Rapids, Michigan)' including batch/device history records, process validation, incoming material inspection, supplier audits, and the Quality Agreement QA-2017-0044. The preservation action memo (Section IV.J) includes Ashford in the third-party preservation demands table, specifying the address, contact person, legal basis, scope, owner, and a deadline of June 6 to send the demand via email and certified mail. The memo also addresses Ashford records within Vantage's own SAP QM system. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The output identifies Ashford Precision Components, Inc. in Grand Rapids as a relevant third-party manufacturer/supplier whose KR-3000 manufacturing and quality records must be preserved. It also expressly recommends/schedules a preservation demand to Ashford in the action memo and references a preservation demand being sent in the hold notice custodian-specific instructions.

### C-029

ISSUE_005: Legal basis for control over third-party records ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L249))

- **Sonnet 4.6: Pass.** The preservation-action-memo.docx explicitly references both the contractual basis (Quality Agreement QA-2017-0044 §8.3 and §8.5) and the legal basis under FRCP Rule 34(a) ('constructive control under Rule 34(a)') for why Vantage must preserve Ashford's records. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The preservation-action memo expressly states that Ashford records are subject to preservation based on Quality Agreement QA-2017-0044 and Vantage’s constructive control under Rule 34(a), and it directs a third-party preservation demand to Ashford. This satisfies the criterion.

### C-030

ISSUE_006: Privilege considerations for GC's files addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L258))

- **Sonnet 4.6: Pass.** Both documents address privilege considerations for the General Counsel's files. The litigation hold notice (Section 9) states that privileged materials will be collected and reviewed under separate procedures supervised by the Legal Department and outside counsel and will not be disclosed without appropriate privilege review. The preservation action memo (Section IV.L) specifically addresses the GC as a custodian, noting the complaint names her as a participant, recommending outside counsel formally co-own hold administration, designating a privilege coordinator, stating the GC should not self-collect or pre-screen her own files, and recommending they be collected into a segregated review environment. It also recommends seeking a FRE 502(d) order and setting up a privilege-log protocol. Schedule A also notes 'privilege protocol applies' for Chandrasekaran. These provisions clearly satisfy the criterion.
- **GPT-5.5: Pass.** The output expressly addresses privileged materials and the General Counsel as a custodian. The hold notice instructs custodians to preserve attorney-client/work-product materials and states they will be collected/reviewed under separate Legal/outside counsel procedures. It also notes Priya Chandrasekaran is a custodian subject to a privilege protocol. The preservation memo further recommends outside counsel co-administer the hold, designates a privilege coordinator, prohibits the GC from self-collecting or pre-screening her own files, calls for a segregated review environment, and recommends a FRE 502(d) order.

### C-031

ISSUE_006: Preservation without waiver of privilege ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L267))

- **Sonnet 4.6: Pass.** Section 9 of the notice explicitly addresses privileged materials: it states that the hold applies to communications with lawyers (in-house or outside counsel), legal memoranda, and other privileged or work-product materials, instructs custodians to preserve them like everything else, and clarifies that preservation does not mean production — privileged materials will be collected and reviewed under separate procedures supervised by the Legal Department and outside counsel and will not be disclosed without appropriate privilege review. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The notice expressly states in Section 9 that communications with lawyers, legal memoranda, and other privileged or work-product materials must be preserved like all other materials, and clarifies that preservation does not mean production because such materials will be collected and reviewed under separate Legal/outside counsel procedures and not disclosed without privilege review.

### C-032

ISSUE_007: Proportionality or tiered approach for 85 mobile devices ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L275))

- **Sonnet 4.6: Pass.** The preservation action memo (Section IV.D) explicitly addresses proportionality and tiering for the 85 field devices. It divides them into three tiers: Tier 1 (30 at-risk devices to be imaged by June 20, shipped by June 11), Tier 2 (a prioritized subset of the remaining 55 devices, with specific territory prioritization including FL/Tampa and highest complaint activity, estimated 15-25 devices, beginning by June 30), and Tier 3 (remaining devices under hold with settings changes, reassessed quarterly). The memo also notes to 'document the proportionality analysis.' This clearly satisfies the criterion of addressing proportionality and tiering rather than treating all 85 devices identically.
- **GPT-5.5: Pass.** The preservation-action memo expressly uses a tiered, proportional approach for the 85 field sales devices: halt all refreshes, image the 30 devices at imminent wipe risk as Tier 1, then collect a prioritized subset of the remaining 55 based on territories and complaint activity as Tier 2, while keeping the rest under hold as Tier 3 and documenting proportionality.

### C-033

ISSUE_008: Personal devices / BYOD preservation addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L284))

- **Sonnet 4.6: Pass.** The hold notice extensively addresses personal devices and BYOD preservation. Section 5 is entirely dedicated to 'Personal Devices and Personal Accounts,' instructing custodians to preserve work-related data on personal phones, personal email accounts, personal messaging apps, and personal cloud storage. Section 6 provides specific technical instructions for mobile devices. The questionnaire (Attachment 2, Section C) asks about personal accounts and messaging apps. Attachment 3 addresses field reps' personal phones. Attachment 4 specifically calls out Dr. Suresh's personal iPhone and Gmail account. This criterion is clearly satisfied.
- **GPT-5.5: Pass.** The hold notice expressly addresses BYOD/personal accounts in multiple places, including a dedicated Section 5 on personal devices and personal accounts. It instructs custodians to preserve work-related messages, emails, files, cloud backups, and devices, and not to delete, reset, replace, or discard personal devices containing relevant work-related information without contacting Legal.

### C-034

ISSUE_008: Dr. Suresh's potential personal device use flagged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L292))

- **Sonnet 4.6: Pass.** Dr. Anita Suresh's personal device use is explicitly flagged in multiple places. In the litigation hold notice (Attachment 4), her custodian-specific instructions state: 'Preliminary information indicates you may have used a personal iPhone and a personal Gmail account for some surgeon advisory board / KOL communications. Preserve all such messages, emails, attachments, and backups immediately.' The preservation action memo (Section IV.K) also specifically calls out Dr. Suresh as a priority for BYOD follow-up, noting the complaint specifically alleges this at paragraphs 59 and 121, and recommends outside counsel meet with her by June 6 for a consent-based targeted collection.
- **GPT-5.5: Pass.** The litigation hold notice specifically includes a custodian-specific instruction for Dr. Anita Suresh stating that she may have used a personal iPhone and personal Gmail account for surgeon advisory board/KOL communications and directing preservation. The action memo also flags the same BYOD concern and calls for outside counsel follow-up.

### C-035

ISSUE_009: Backup tapes / disaster recovery archives addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L301))

- **Sonnet 4.6: Pass.** The preservation-action-memo.docx explicitly addresses backup tapes in Section IV.F ('Backup Tapes (Commvault / LTO-8)'), directing that all rotation, overwrite, recycling, and degaussing be halted by June 3, and that existing daily, weekly, monthly, and annual tapes be segregated and labeled. The IT directive in Appendix A-1 item 4 also explicitly orders halting all Commvault/LTO rotation, overwrite, and destruction. The destruction calendar table also lists 'Backup tape overwrite: daily 30 days, weekly 90 days, monthly 12 months' as a running risk requiring action by June 3. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The preservation-action memo expressly addresses backup tapes/archives, including Commvault/LTO rotation, overwrite, recycling, degaussing, catalog preservation, off-site tape inventory, and annual tapes, and directs that rotation/overwrite be halted during the hold.

### C-036

ISSUE_009: Reasonable accessibility of backup tapes discussed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L310))

- **Sonnet 4.6: Pass.** The preservation-action-memo.docx explicitly references Rule 26(b)(2)(B) in Section IV.F regarding backup tapes: 'Do not restore tapes for now (Rule 26(b)(2)(B)); restoration is a later decision.' This directly addresses the concept of not reasonably accessible ESI sources and defers restoration decisions, satisfying the criterion.
- **GPT-5.5: Pass.** The preservation-action memo expressly addresses backup tapes, directs preservation/halting rotation, and states: “Do not restore tapes for now (Rule 26(b)(2)(B)); restoration is a later decision,” which references burden/accessibility considerations and defers restoration decisions.

### C-037

ISSUE_010: Acknowledgment requirement included in hold notice ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L319))

- **Sonnet 4.6: Pass.** The hold notice includes a prominent acknowledgment requirement in the header box ('Sign and return the Acknowledgment (Attachment 1) and Questionnaire (Attachment 2) by 5:00 p.m. ET, Monday, June 9, 2025'), and Attachment 1 is a full 'Litigation Hold Acknowledgment and Certification (Form VNT-FRM-045)' with a signature line, certification statements, and return instructions. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The hold notice repeatedly instructs custodians to sign and return an acknowledgment by a specified deadline, and Attachment 1 provides a formal Litigation Hold Acknowledgment and Certification with signature line and certifications of receipt, reading, understanding, and compliance.

### C-038

ISSUE_010: Periodic reminders or compliance monitoring mentioned ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L327))

- **Sonnet 4.6: Pass.** The litigation hold notice explicitly mentions periodic reminders in Section 12: 'You will receive periodic reminders (the first on or about August 1, 2025, and at least quarterly thereafter) and may be asked to confirm continued compliance or to participate in an interview or data collection.' The preservation action memo also references reminders in Section IV.M: 'Reminders: August 1, 2025 (outside counsel's 60-day recommendation), then quarterly (VNT-POL-007 minimum).' The master action tracker also includes item 27: 'First reminder notice and compliance audit' due August 1. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The litigation hold notice expressly states that custodians will receive periodic reminders, first around August 1, 2025 and at least quarterly thereafter, and may be asked to confirm continued compliance. The preservation memo also includes acknowledgment tracking, reminder notices, compliance audits, and verification steps.

### C-039

ISSUE_011: Veeva Vault audit trail and version preservation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L336))

- **Sonnet 4.6: Pass.** The agent's output addresses Veeva Vault preservation in multiple specific ways beyond generic mentions. In the litigation hold notice (Section 7), it instructs custodians not to 'modify, obsolete, retire, or archive Veeva Vault documents, or allow drafts to lapse.' In the preservation action memo (Section IV.E), it explicitly states: 'Full-fidelity preservation: keep the vault intact. Corestone and Veeva Professional Services perform a Vault API / Vault Loader export with version history, audit trails, e-signatures, and document relationships (complaint → CAPA → MDR). PDF renditions alone are not acceptable.' It also instructs suspension of 'obsolescence, archival, and abandoned-draft purge workflows for KR-3000 records' and recovery of items from the 60-day recycle bin. The custodian-specific instructions for Braddock and Petrosian also address suspending KR-3000 Veeva workflows. This clearly satisfies the criterion requiring reference to audit trails, version history, and document lifecycle workflows.
- **GPT-5.5: Pass.** The documents expressly address Veeva Vault preservation beyond generic document retention. The hold notice refers to preserving Veeva Vault versions, drafts, and audit trails, instructs custodians not to modify, obsolete, retire, or archive KR-3000 Veeva records without Legal authorization, and includes custodian-specific instructions to suspend obsolescence, archival, and draft-purge workflows. The preservation memo likewise calls for suspending Veeva lifecycle workflows and performing full-fidelity exports with version history, audit trails, e-signatures, and document relationships.

### C-040

ISSUE_011: Veeva document lifecycle suspension instruction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L345))

- **Sonnet 4.6: Pass.** The agent's output explicitly instructs suspension of Veeva Vault document lifecycle workflows in multiple places. In the hold notice (Section 7), it states 'Do not modify, obsolete, retire, or archive Veeva Vault documents, or allow drafts to lapse, relating to the KR-3000 without Legal Department authorization.' In the preservation action memo (Section IV.E), it directs: 'suspend obsolescence, archival, and abandoned-draft purge workflows for KR-3000 records.' In Attachment 4 (Petrosian-specific instructions), it states 'Do not change the lifecycle state of any KR-3000 Veeva Vault record.' In Appendix A-1 (IT directive), item 13 directs IT to 'coordinate with T. Braddock to disable the Veeva abandoned-draft purge and KR-3000 obsolescence workflows under change control.' The Braddock custodian-specific instructions also state: 'Suspend obsolescence, archival, and draft-purge workflows for KR-3000 records in Veeva Vault Submissions.' These instructions clearly satisfy the criterion.
- **GPT-5.5: Pass.** The output expressly instructs relevant custodians/teams to halt Veeva Vault lifecycle activity for KR-3000 records, including directions not to obsolete/retire/archive Veeva documents and specific instructions to Regulatory/QA leadership to suspend obsolescence, archival, and draft-purge workflows in Veeva Vault QMS/Submissions.

### C-041

Memo identifies Petrosian imaging before June 20 as critical action ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L354))

- **Sonnet 4.6: Pass.** The memo extensively identifies forensic imaging of Sandra Petrosian's data before her June 20 departure as a critical time-sensitive action. Section C is entirely dedicated to this, specifying that imaging must be completed by June 13 (before the HR offboarding workflow auto-starts), covering her laptop, company iPhone, H: drive, and Veeva access. The destruction calendar table also lists this as a hard deadline. The master action tracker (item 18) lists 'Petrosian forensic imaging complete' with a June 13 deadline. The IT directive (Appendix A-1, item 6) explicitly directs no wiping or reimaging of Petrosian's devices and coordinates forensic imaging by June 13.
- **GPT-5.5: Pass.** The memo repeatedly identifies Sandra Petrosian’s forensic imaging as a critical time-sensitive action, stating it must be completed by June 13 before her June 20 departure and before HR offboarding workflows could wipe or alter her data.

### C-042

Memo identifies SAP migration halt/preservation before June 16 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L362))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the SAP ECC 6.0 to S/4HANA migration on June 16 as a critical time-sensitive action. It appears in the Destruction Calendar table with a June 16 date, describes the evidence at risk (batch records for ~47,000 units, inspection, supplier quality, validation, QM, FI/CO, audit logs), and requires a halt order by June 4 with preservation completed and verified by June 14. Section IV.B (SAP workstream) further details the forensic snapshot and extraction approach, the decommissioning restrictions, and the budget. The Master Action Tracker includes items #9 (SAP halt directive by June 4) and #20 (SAP forensic snapshot by June 14). This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies the June 16 SAP ECC 6.0 to S/4HANA cutover as a critical destruction-calendar event and directs preservation of legacy KR-3000 SAP data before that date, including a halt/no-archival directive by June 4 and forensic snapshot/extraction by June 14.

### C-043

Memo identifies mobile device wipe halt before June 23 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L370))

- **Sonnet 4.6: Pass.** The memo explicitly identifies halting the mobile device refresh before June 23 as a critical action. In the Destruction Calendar table, it lists 'June 23: Device refresh Batch 1: 30 iPhones factory-wiped and recycled via Greenbridge E-Cycling' and states the required action is 'Halt directive today; image by June 20.' Section D (Mobile Devices and VantagePulse) also states 'Today: GC written directive overriding VNT-IT-SOP-023. Suspend the refresh of all company-issued devices' and notes Tier 1 devices must ship by June 11 and imaging must be complete by June 20, well before the June 23 date. Appendix A-1 directive item 9 also instructs IT to suspend VNT-IT-SOP-023 device refresh for all company-issued devices immediately.
- **GPT-5.5: Pass.** The memo explicitly identifies the June 23 device refresh as a scheduled event that would factory-wipe and recycle 30 iPhones, directs a halt to the device refresh today, and includes multiple action items to suspend all company-issued device refreshes and MDM wipes before June 23.

### C-044

Memo identifies email purge suspension before June 30 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L378))

- **Sonnet 4.6: Pass.** The memo explicitly identifies the June 30 quarterly M365 email auto-purge as a critical event in the Destruction Calendar table, noting it will destroy '2017--mid-2022 email: design/testing, K192847, launch, early complaints' and requires disabling by June 4 with verification by June 27. It is also addressed in Section IV.A and in Appendix A-1 directive item 1. The memo clearly identifies suspending this purge before June 30 as a critical action.
- **GPT-5.5: Pass.** The memo explicitly identifies the June 30, 2025 quarterly M365 email auto-purge as a scheduled destruction event and directs disabling/suspending the email purge before that date, with deadlines and verification steps.

### C-045

Memo correctly sequences urgent actions by deadline ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L386))

- **Sonnet 4.6: Pass.** The memo presents a detailed destruction calendar table (Section III) that lists events in chronological order: rolling purges (now), Petrosian HR workflow (~June 13), SAP cutover (June 16), Petrosian last day (June 20), device refresh Batch 1 (June 23), email purge (June 30), Iron Mountain move (July 1), SAP decommissioning (July 15), device refresh Batch 2 (July 21), and later purges (Sept 30, Dec 31). The Master Action Tracker (Section VI) also sequences actions chronologically from June 2 through August 1. SAP migration (June 14-16) and Petrosian departure (June 13-20) are both listed before mobile device wipe (June 20-23) and email purge (June 30). The sequencing is logically ordered by deadline throughout the document.
- **GPT-5.5: Pass.** The memo includes a destruction calendar ordered chronologically: SAP migration/cutover on June 16 and Petrosian departure on June 20 are listed before the June 23 mobile device refresh/wipe and the June 30 email purge. The action tracker also generally sequences work by deadline.

### C-046

Memo addresses Ashford third-party coordination ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L394))

- **Sonnet 4.6: Pass.** The memo extensively addresses Ashford Precision Components in the third-party coordination section (Section J), including a detailed entry in the third-party preservation demands table specifying the address, contact person, legal basis (Quality Agreement QA-2017-0044), scope of records to preserve, and a deadline of June 6 for sending the demand. Ashford is also discussed in the discrepancy section (items 12 and 13) and in the SAP workstream. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The memo includes a dedicated third-party preservation demands section that identifies Ashford Precision Components, Inc. as a third party, describes the scope and contractual basis, and recommends sending a preservation demand by June 6.

### C-047

Memo addresses coordination with e-discovery vendor Corestone ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L402))

- **Sonnet 4.6: Pass.** The memo extensively mentions Corestone Analytics and Daniel Okafor throughout. For example, in Section IV.A it references 'Corestone Analytics should independently spot-check pre-2022 items'; Section IV.B mentions 'Corestone performs a full forensic snapshot'; Section IV.C references 'Schedule with Daniel Okafor (Corestone, 312-555-0194)'; Section IV.D mentions 'Corestone images the 30 at-risk devices'; and the Master Action Tracker lists Corestone as an owner/participant in multiple actions. The e-discovery vendor is clearly and repeatedly mentioned for forensic collection, imaging, and processing tasks.
- **GPT-5.5: Pass.** The memo repeatedly mentions coordinating with Corestone Analytics and Daniel Okafor for forensic imaging, SAP snapshots/extractions, device imaging, Veeva exports, and engagement under outside counsel.

### C-048

Memo recommends next steps for hold compliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L410))

- **Sonnet 4.6: Pass.** The memo contains multiple specific recommended next steps for ongoing hold compliance. Section M (Hold Administration and Defensibility) explicitly addresses tracking acknowledgments (due June 9), sending reminders (August 1, 2025 and quarterly thereafter), and conducting compliance audits. The Master Action Tracker (Section VI) includes items such as acknowledgment tracking (#15), independent verification of M365 purge disablement (#23), and a first reminder notice and compliance audit (#27). These clearly satisfy the criterion.
- **GPT-5.5: Pass.** The memo recommends multiple specific next steps for ongoing hold compliance, including tracking acknowledgments and questionnaires in a hold log, sending reminders on June 6 and then August 1/quarterly, conducting custodian/exit interviews, escalating nonresponses, and performing a compliance audit.

### C-049

Hold notice includes consequences of non-compliance ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L418))

- **Sonnet 4.6: Pass.** Section 12 of the notice explicitly states: 'Compliance with this notice is mandatory. Failure to comply can expose the Company to serious court sanctions and may result in disciplinary action up to and including termination, consistent with VNT-POL-007, Section 8.' This clearly addresses both court-imposed consequences (sanctions) and internal consequences (disciplinary action up to termination), satisfying the criterion.
- **GPT-5.5: Pass.** The notice expressly states that failure to comply can expose the Company to serious court sanctions and may result in disciplinary action up to and including termination.

### C-050

Hold notice provides contact information for questions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L426))

- **Sonnet 4.6: Pass.** Section 13 of the notice provides a dedicated contacts table with three contacts: Priya Chandrasekaran (General Counsel) with email and extension, Natalie R. Prichard (outside counsel) with email and phone number, and Marcus Tilden (IT Director) with email and phone number. This clearly satisfies the criterion of providing a contact person with contact method for custodians to direct questions.
- **GPT-5.5: Pass.** The notice includes a dedicated 'Questions and Contacts' section listing contact persons (including the General Counsel, outside counsel, and IT contact) with email addresses and phone/extensions for scope, legal, and technical questions.

### C-051

Hold notice instructs custodians not to delete/destroy documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L434))

- **Sonnet 4.6: Pass.** The notice repeatedly and explicitly instructs custodians not to delete, destroy, alter, discard, or overwrite relevant documents. The very first action item states 'Do not delete, discard, alter, overwrite, or "clean up" any document, email, message, file, or physical item that relates in any way to the ProFlex KR-3000.' Section 7 reiterates 'Do not delete, shred, or discard documents, even duplicates or drafts, and do not empty "Deleted Items," recycle bins, or trash folders.' These prohibitions are stated clearly and prominently throughout the document.
- **GPT-5.5: Pass.** The hold notice repeatedly instructs custodians not to delete, discard, alter, overwrite, shred, wipe, reset, or otherwise destroy potentially relevant documents, ESI, devices, and physical items.

### C-052

Hold notice instructs suspension of routine destruction policies ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L442))

- **Sonnet 4.6: Pass.** Section 1 of the notice explicitly states: 'It overrides every normal retention period, auto-delete setting, destruction schedule, clean-up practice, device refresh, system migration, and offboarding procedure that would otherwise apply to covered information.' This clearly instructs the suspension of routine document retention and destruction policies for materials within the scope of the hold. Additionally, Section 7 and other sections reinforce this with specific prohibitions on deletion, shredding, running disk clean-up software, etc.
- **GPT-5.5: Pass.** The notice expressly states that it overrides normal retention periods, auto-delete settings, destruction schedules, clean-up practices, device refresh, system migration, and offboarding procedures for covered information, and includes multiple specific instructions suspending routine deletion/destruction.

### C-053

Correct date of complaint service: May 28, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L450))

- **Sonnet 4.6: Pass.** Section 1 of the notice explicitly states: 'On May 28, 2025, Vantage Medical Devices, Inc. (
- **GPT-5.5: Pass.** The notice explicitly states that Vantage was served with the complaint on May 28, 2025.

### C-054

Correct product description: CoCrMo femoral component ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L458))

- **Sonnet 4.6: Pass.** The notice references 'Metallurgical, failure, retrieval, or surface-characterization analyses of KR-3000 components, including the analysis of retrieved femoral components referenced in the complaint as having occurred in or around July–September 2022.' It also references 'surface finish and polishing specifications' in design/development, 'surface finish measurements' in manufacturing, and lists 'CoCrMo' as a material in incoming material inspection. The manufacturing section references 'CoCrMo, UHMWPE, titanium alloy' materials. The notice also references 'SEM/profilometry samples' and 'SEM/EDS/profilometry data' in the context of retrieved components. These references are consistent with allegations of articular surface finish issues and premature wear of CoCrMo femoral components. The product defect allegations are not materially misstated.
- **GPT-5.5: Pass.** The notice references KR-3000 design/testing issues in a manner consistent with alleged defects, including wear testing, accelerated wear simulation, surface finish and polishing specifications, surface-characterization analyses, retrieved femoral components, and CoCrMo materials. It does not materially misstate the product defect allegations.

### C-055

Hold notice defines subject matter scope covering key categories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L466))

- **Sonnet 4.6: Pass.** Section 3 of the notice explicitly covers all 6 categories: (1) Design and development - 'Design and development of the KR-3000'; (2) Testing - 'Testing, including bench, wear, cyclical-loading...'; (3) Manufacturing - 'Manufacturing at Fort Wayne and at Ashford Precision Components'; (4) Marketing/Sales - 'Sales, marketing, and field communications'; (5) Complaint handling/adverse events - 'Quality system records: complaints, complaint trending...CAPAs...health hazard evaluations'; (6) Regulatory submissions/FDA - 'Regulatory matters, including the 510(k) submission K192847...FDA correspondence and meetings, Medical Device Reports (MDRs)'. All 6 categories are clearly present, far exceeding the minimum threshold of 4.
- **GPT-5.5: Pass.** The hold notice's subject matter scope expressly includes design and development, testing, manufacturing, sales/marketing, complaint handling/adverse events/post-market surveillance, and regulatory matters including FDA submissions and communications. This covers all 6 listed categories, exceeding the requirement of at least 4.

### C-056

Hold notice addresses IT Department / Marcus Tilden's role ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L474))

- **Sonnet 4.6: Pass.** The notice extensively addresses Marcus Tilden and the IT Department's role. Marcus Tilden is listed in the contacts table as 'Director of IT' for 'Technical questions only (device settings, system access). IT will act on preservation only as directed in writing by Legal.' He appears in Schedule A as custodian #10 'Director of Information Technology (custodian and IT preservation liaison).' The IT Department is listed as custodian #19 with specific roles: 'SAP Basis/migration team, M365 administrators, MDM/endpoint team, backup (Commvault/LTO) operators, Salesforce and Veeva administrators.' Attachment 4 includes a specific section for Marcus Tilden and HR noting 'Separate written preservation directives are being issued to IT and HR today' and that their own records 'are themselves subject to this hold.' The notice also references IT directing voicemail deletion suspension, device refresh suspension, forensic imaging coordination, and working with Corestone Analytics.
- **GPT-5.5: Pass.** The notice expressly identifies Marcus Tilden as Director of IT and IT preservation liaison, includes the IT Department in the distribution list with M365, endpoint, backup, Salesforce/Veeva, and SAP roles, and references IT actions such as suspending voicemail deletion, halting device refresh/offboarding wipes, forensic preservation, SAP migration/data preservation, and separate IT preservation directives.

### C-057

Hold notice mentions the 510(k) clearance or FDA regulatory filings ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L482))

- **Sonnet 4.6: Pass.** The notice explicitly identifies '510(k) submission K192847 and its preparation, predicate-device comparisons, FDA correspondence and meetings, Medical Device Reports (MDRs), corrections and removals (21 CFR Part 806) evaluations, inspections, and labeling / Instructions for Use' as within the scope of preservation in Section 3 under 'Regulatory matters.'
- **GPT-5.5: Pass.** The hold notice expressly includes regulatory matters within the preservation scope, including 'the 510(k) submission K192847,' predicate-device comparisons, FDA correspondence and meetings, MDRs, and labeling/Instructions for Use.

### C-058

Hold notice addresses CAPA records and MDR reports ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L490))

- **Sonnet 4.6: Pass.** The notice explicitly mentions both CAPA records and MDR reports in Section 3 under 'Quality system records': 'complaints, complaint trending, revision-rate analyses, CAPAs (opened, considered, or declined), nonconformances, deviations, health hazard evaluations, risk management files, field action or recall evaluations, and post-market surveillance.' MDRs are also mentioned under 'Regulatory matters': 'Medical Device Reports (MDRs), corrections and removals (21 CFR Part 806) evaluations.' Both are clearly within scope of preservation.
- **GPT-5.5: Pass.** The hold notice expressly includes both Medical Device Reports (MDRs) under regulatory matters and CAPAs under quality system records within the scope of preservation.

### C-059

Hold notice addresses field sales representative communications ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L498))

- **Sonnet 4.6: Pass.** The notice explicitly addresses field sales representatives in multiple places. Schedule A lists '17 Field Sales Representatives (85) All field representatives in 22 territories --- with Attachment 3.' Attachment 3 is an entire supplemental notice dedicated to field sales representatives, covering preservation of texts, iMessages, WhatsApp, call logs, voicemails, photos, VantagePulse, Salesforce records, personal phones, and communications with surgeons about the KR-3000. The custodian-specific instructions for Michelle R. Torrence also direct her to distribute Attachment 3 to all 85 field representatives.
- **GPT-5.5: Pass.** The notice expressly includes all 85 field sales representatives in the distribution list and provides a supplemental hold notice specifically for them. It directs preservation of their communications with surgeons, hospitals, OR staff, and colleagues about the KR-3000, including texts, WhatsApp, call logs, voicemails, photos, VantagePulse, and Salesforce records.

### C-060

Memo addresses coordination with outside counsel Calloway Prichard Weeks ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L506))

- **Sonnet 4.6: Pass.** The memo extensively mentions Natalie R. Prichard and Calloway Prichard Weeks LLP throughout, including in the CC line, references to 'outside counsel's May 30 assessment,' 'outside counsel recommends company-wide suspension,' coordination on Petrosian imaging, Suresh BYOD meeting, privilege coordination, and the action tracker assigning multiple items to Prichard. Outside counsel coordination is clearly and repeatedly addressed.
- **GPT-5.5: Pass.** The memo repeatedly mentions coordination with outside counsel, including CC'ing Natalie R. Prichard of Calloway Prichard Weeks LLP, engaging Corestone through outside counsel, designating outside counsel as co-administrator/privilege coordinator, and assigning preservation tasks to Prichard/Calloway Prichard Weeks.

### C-061

Hold notice date is approximately June 2, 2025 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-litigation-hold-notice-for-new-product-liability-matter/task.json#L514))

- **Sonnet 4.6: Pass.** The notice is clearly dated June 2, 2025, which exactly matches the criterion.
- **GPT-5.5: Pass.** The litigation hold notice is explicitly dated June 2, 2025 in the main header and repeated in attachments, satisfying the criterion.
