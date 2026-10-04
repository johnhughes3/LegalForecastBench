<!-- Rendered from preservation-action-memo.docx for reading; the original file is the deliverable. -->

**VANTAGE MEDICAL DEVICES, INC. — OFFICE OF THE GENERAL COUNSEL**

**MEMORANDUM**

| **TO:**   | Priya Chandrasekaran, General Counsel                                                                                                         |
|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| **CC:**   | Natalie R. Prichard, Calloway Prichard Weeks LLP (outside litigation counsel)                                                                 |
| **FROM:** | Legal Department — Litigation Hold Team                                                                                                       |
| **DATE:** | June 2, 2025                                                                                                                                  |
| **RE:**   | Preservation Action Plan — *Kessler et al. v. Vantage Medical Devices, Inc.*, No. 1:25-cv-04387-RLM (S.D. Ind.) — Litigation Hold LH-2025-001 |

# I. Bottom Line

The litigation hold notice (separate document) is ready for issuance today, June 2, 2025. A notice alone will not satisfy our preservation duty: **six scheduled, Company-controlled events will destroy or degrade core KR-3000 evidence within the next seven weeks unless we stop them in writing this week.** Several of these events are not identified in the materials we received, and several of the dates and facts in those materials conflict with one another. This memo sets out (1) the destruction calendar, (2) the action plan by workstream with owners and deadlines, (3) the discrepancies we found and how we have resolved them (in each case by adopting the more protective position), and (4) the decisions we need from you today.

**Key points:**

- **Today (June 2):** issue the hold; sign the written IT and HR directives in Appendix A (VNT-IT-ARCH-001 §10 states IT will not act without written GC authorization); send the Petrosian offboarding suspension to HR; send the device-refresh halt to IT and Sales.

- **Auto-deletion is broader than the June 30 email purge.** Under VNT-POL-007 Teams chat purges **monthly** (1-year retention), voicemail purges on a **rolling 90-day** basis, and Veeva Vault abandoned drafts purge on a **rolling 180-day** basis. All of these are running now. All must be disabled by June 3 (the policy requires IT to do this within 24 hours of a hold).

- **Petrosian imaging must finish by June 13, not June 18.** HR’s offboarding workflow auto-starts around June 13; her standard offboarding would reimage her laptop, wipe her company iPhone, convert and later delete her mailbox, and purge her H: drive 30 days after she leaves. She is also the **only** Veeva QMS administrator.

- **SAP:** preserve legacy KR-3000 data before the June 16 cutover. The July 15 decommissioning date conflicts with VNT-POL-007 §4.2 (minimum 90 days read-only after migration and GC approval) and with the IT Director’s statement that ILM archiving loses fields, audit logs, and change history. Recommend a full forensic snapshot of the ECC 6.0 database plus a verified KR-3000 extraction, and **no decommissioning while the hold is in effect** without written GC sign-off.

- **Threshold risk to address now:** if the VNT-POL-007 Rev. 3 quarterly email purge has been running since 2024 as configured, email from before about April 2022 (including 2017–2019 design-period email) may **already** be gone from M365. The materials assume it still exists. IT must confirm this by June 4, and we must preserve every other copy that might exist (the third-party email archive, annual backup tapes, and PST files).

- **Gaps in the custodian list:** CEO Gerald T. Morrissey is named in the complaint and listed by outside counsel but is **missing from the custodian inventory and the M365 hold list**. Petrosian’s direct reports, the R&D engineers, Sales Operations, and the SAP migration team must also be added. **Physical evidence** (retrieved or explanted devices, metallurgical specimens, retained samples) is not covered anywhere in the inventory and must be preserved.

# II. Background and Trigger of the Duty to Preserve

The complaint was filed May 22, 2025 and served May 28, 2025. Plaintiffs (Hargrove, Steinfeld & Burch LLP) seek to represent a nationwide Rule 23(b)(3) class of about 47,000 KR-3000 recipients (implants from February 3, 2020 onward). They assert strict liability for design defect, negligence, breach of implied warranty, and fraudulent concealment. The fraudulent-concealment count, and its punitive-damages exposure, depends on three allegations: (i) 2017–2019 pre-market wear testing, (ii) a Q3 2022 internal metallurgical analysis of retrieved femoral components, and (iii) “informal” surgeon reports sent to field representatives and Dr. Suresh by text, WhatsApp, VantagePulse, and personal email. The complaint repeatedly tells the Company to preserve these specific categories (¶¶ 42, 61, 69, 120–121). That will make any loss in these categories very hard to defend under Rule 37(e).

**Trigger date.** Service (May 28) is the latest possible trigger. Plaintiffs will likely argue that the duty arose earlier, based on complaint trends and the reported 6.8% three-year revision rate, product-liability accruals and warranty-reserve analyses (Callahan), any earlier demand letters, claims, or patient/attorney record requests, and the Pinnacle Indemnity Group notice (May 29). **Recommendation:** outside counsel should privately assess the earliest reasonably defensible trigger date. We should inventory any KR-3000 claim letters, lawsuits, or records requests received before May 2025. Until that is done, treat all ordinary-course deletions since at least January 1, 2024 (the effective date of VNT-POL-007 Rev. 3) as potentially subject to scrutiny, and document them.

**Scope adopted in the notice:** January 1, 2017 to present and continuing. Subject matter follows outside counsel’s May 30 assessment (§ III.B), expanded to cover physical evidence, 21 CFR Part 806 / recall evaluations, the named plaintiffs’ implant lots and surgeons, ethics-hotline reports, and training records.

# III. Destruction Calendar — Hard Dates

| **Date**              | **Scheduled event (source)**                                                                                             | **Evidence at risk**                                                                                                | **Required action / deadline**                                          |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| Running now (rolling) | Teams chat monthly auto-purge, 1-year retention (VNT-POL-007 §§3.3, 4.1, 5.2)                                            | Teams chats older than 1 year; next purge June 30                                                                   | Disable by **June 3**; place custodians on M365 hold                    |
| Running now (rolling) | Voicemail 90-day auto-purge (VNT-POL-007 §3.3, App. B)                                                                   | Surgeon and field voicemails                                                                                        | Suspend by **June 3** (not addressed in inventory)                      |
| Running now (rolling) | Veeva Vault abandoned-draft 180-day purge (VNT-POL-007 §4.3); 60-day recycle bin (IT-ARCH §4.2)                          | Draft quality/risk assessments, which are critical for knowledge and timing                                         | Disable by **June 3**; recover anything in the recycle bin              |
| Running now (rolling) | Backup tape overwrite: daily 30 days, weekly 90 days, monthly 12 months                                                  | Snapshots, possibly the only copy of already-purged email or data                                                   | Halt all rotation by **June 3**                                         |
| ~June 13              | HR offboarding workflow auto-starts for Petrosian (Waverly email)                                                        | Laptop, iPhone, H: drive, mailbox, Veeva access                                                                     | Written suspension to HR **today**; imaging done by **June 13**         |
| June 16               | SAP ECC 6.0 to S/4HANA cutover; legacy goes read-only; 2017–2022 data “archive-only” to ILM (Tilden email; IT-ARCH §3.2) | Batch records (~47,000 units), inspection, supplier quality, validation, QM, FI/CO; audit logs and change documents | Halt order by **June 4**; preservation done and verified by **June 14** |
| June 20               | Petrosian last day; accounts deactivated within 24 hours                                                                 | As above                                                                                                            | All preservation complete; accounts kept on hold                        |
| June 23               | Device refresh Batch 1: 30 iPhones factory-wiped and recycled via Greenbridge E-Cycling                                  | Texts, WhatsApp, VantagePulse local data (no server copy), call logs                                                | Halt directive **today**; image by **June 20**                          |
| June 30               | Quarterly M365 email auto-purge: all email dated on or before June 30, 2022                                              | 2017–mid-2022 email: design/testing, K192847, launch, early complaints                                              | Disable by **June 4**; verify by **June 27**                            |
| July 1                | Records Archive Room 2-104 moves to Iron Mountain (inventory SRC-009)                                                    | Engineering notebooks, paper batch travelers, signed quality records                                                | Hold KR-3000 boxes; inventory and scan first                            |
| July 15               | Legacy SAP ECC 6.0 decommissioned; servers shut down                                                                     | Native relational SAP data                                                                                          | No decommissioning without written GC sign-off                          |
| July 21               | Device refresh Batch 2 (Tilden email)                                                                                    | Additional rep devices                                                                                              | Covered by refresh halt                                                 |
| Sept 30               | Next quarterly email purge: email through Sept 30, 2022                                                                  | **Q3 2022 metallurgical-analysis email** (July–Sept 2022)                                                           | Covered by purge disablement; purge stays off for duration of hold      |
| Dec 31                | SharePoint/OneDrive annual purge, 5 years from last modification (VNT-POL-007 §4.1)                                      | Files last modified before end-2020 (2017–2020 design and launch files)                                             | Disable; apply M365 hold to sites                                       |

***Correction to the source materials:** the inventory and outside counsel memo say the June 30 purge will destroy the Q3 2022 metallurgical-analysis email. It will not. The June 30 purge deletes email dated on or before June 30, 2022, and the analysis ran July–September 2022. That email is at risk from the **September 30, 2025** purge instead. This does not change what we must do (disable the purge permanently now). But preservation reports and any later court filings must describe the risk accurately.*

# IV. Action Plan by Workstream

## A. Microsoft 365 — Email, Teams, Voicemail, OneDrive/SharePoint

- **Disable, do not just “pause,”** the quarterly email purge, the monthly Teams purge, the voicemail 90-day purge, and the annual SharePoint/OneDrive purge. Preferred approach: apply org-wide preservation (or at least cover all KR-3000-touching departments). Outside counsel recommends company-wide suspension so that custodians not yet identified are also protected. **Deadline: June 3–4.** IT must confirm in writing with screenshots and timestamps within 24 hours (VNT-POL-007 §§4.1, 5.2).

- Apply M365 eDiscovery/Litigation Hold to all named custodians’ mailboxes (including Archive and Recoverable Items), OneDrive, Teams, and relevant SharePoint sites (R&D, QA, Regulatory, Sales & Marketing, Finance, Legal). Include shared mailboxes Quality@ and RegulatoryAffairs@. **Include Morrissey**, who is missing from the inventory hold list. Confirm E3/E5 licensing covers this.

- **Third-party email archive** (IT-ARCH §2.2): identify the vendor, suspend its deletion rules, and place it on hold. It may be the only surviving copy of older email.

- **Threshold investigation (by June 4):** IT must produce the purge execution logs for every quarterly purge since January 1, 2024. We need to know the earliest email date that still exists in each Tier 1 custodian’s mailbox and in the archive. Also check for pre-2024 purge settings under Rev. 2 and for PST or local email caches on laptops. If 2017–2021 email has already been purged, notify outside counsel immediately. That will require a strategy for preserving and restoring from annual backup tapes, and possibly for disclosure.

- Teams chats: because retention is 1 year, chats from before about June 2024 are probably gone. Document this as part of the ordinary-course history.

- **Verification:** Corestone Analytics should independently spot-check pre-2022 items and hold status by **June 27**. Tilden is both the person carrying out these steps and a custodian whose own retention decisions are relevant, so an independent check strengthens defensibility.

## B. SAP ECC 6.0 / S/4HANA Migration

- **June 4 (Tilden’s requested deadline is June 6; we recommend acting sooner):** GC written directive stating that no archival, ILM move, deletion, or decommissioning of any KR-3000 data may occur without written GC approval.

- **Recommended approach (inventory options 2 + 3):** (a) Corestone performs a full forensic snapshot of the ECC 6.0 production database and application layer (hash-verified, chain of custody). (b) Corestone also extracts KR-3000 data in native/structured form: material masters, production orders, batch/DHR records, QM lots and notifications, incoming inspection, supplier quality (including Ashford CoCs), BOMs and routings, change documents (audit trail), linked DMS attachments, and FI/CO warranty/accrual postings. Kowalski and Callahan validate completeness. **Complete by June 14.** The go-live can then proceed, which avoids the estimated ~\$500K cost of halting the migration.

- **Decommissioning:** keep ECC 6.0 in read-only, accessible form for the duration of the hold. At minimum, do not decommission on July 15. VNT-POL-007 §4.2 requires at least 90 days read-only after migration and GC approval. §7.5 requires a GC-approved written data preservation plan before any legacy system is taken offline. July 14: written GC sign-off gate, based on hash-verified images and a completeness certification.

- Preserve the migration project records: the project plan and Gantt chart, data-mapping and “archive-only” classification decisions, the implementation-partner SOW, and cutover logs. Send a preservation notice to the SAP implementation partner.

- Budget: \$15,000–\$40,000 (Corestone).

## C. Departing Custodian — Sandra K. Petrosian (last day June 20)

- **Today:** written directive to HR (Waverly) and IT to suspend HR-PROC-012 for Petrosian. No laptop reimage. No iPhone wipe. No mailbox conversion or deletion. No 30-day H: drive purge. No account deletion (accounts may be disabled for security after June 20 only if placed on hold and kept, not deleted). Access logs for her accounts must also be preserved.

- **Forensic imaging by June 13** (outside counsel’s date; the inventory’s June 18 date falls after the HR workflow starts and leaves no buffer): laptop, **company-issued iPhone** (missing from the inventory and from the 30-device count), H: drive, QA shared drives, and any USB/external media. Hash values and chain of custody required. Schedule with Daniel Okafor (Corestone, 312-555-0194) **by June 4**. Budget \$5,000–\$8,000.

- **Veeva:** she is the sole QMS Vault Admin. Before June 12: designate Braddock as interim QMS admin (Veeva Professional Services if validation is required under 21 CFR Part 11), hold a knowledge-transfer session, and have her suspend KR-3000 workflows and certify in writing that no KR-3000 records have been obsoleted, archived, or deleted since May 28.

- **Exit/preservation interview** with outside counsel present, via HR’s offered exit interview: record locations (Room 2-104, SAP QM, Veeva), personal devices and accounts, and a signed departure certification (VNT-POL-007 §7.5(e)).

- **Sensitivity:** outside counsel believes the complaint’s specificity suggests an insider source. Petrosian resigned the day the complaint was served and is joining another company. **She must not be treated or described as a suspect.** Any leak investigation should be run separately by outside counsel under privilege. All communications with her should be limited to preservation, include the protected-reporting language, and avoid anything that could be seen as retaliation or as discouraging communications with regulators. This protects the Company from a retaliation claim and protects the integrity of the preservation record.

## D. Mobile Devices and VantagePulse

- **Today:** GC written directive overriding VNT-IT-SOP-023. Suspend the refresh of **all** company-issued devices (all 85 field devices, the 10 executive devices, and Petrosian’s). Issue no MDM remote-wipe or reset commands. Instruct Greenbridge E-Cycling and the device logistics vendor to hold any Vantage devices in their possession. IT must report by June 4 **whether any devices have been wiped or recycled since May 28, 2025**, and list prior-cycle devices that may still be in inventory.

- **Preserve the MDM console** (VMware Workspace ONE): device inventory, serials/IMEIs, assignment history, and wipe logs.

- **Tier 1 (by June 20):** Corestone images the 30 at-risk devices (Cellebrite/full file system; extract VantagePulse SQLite data). Centralized ship-in to Chicago, in batches of 10, at about 2–3 business days per batch, means devices must ship **by June 11**. \$9,000–\$15,000.

- **Tier 2 (begin by June 30, finish in about 30 days):** prioritized subset of the remaining 55 devices. **Add the territories covering Riverside Methodist Hospital (Columbus, OH) and the Tampa, FL implanting facility.** The inventory’s priority list (IN, OH, MI, IL, KY) leaves out Florida, where Dufresne was implanted. Also prioritize reps with the highest KR-3000 complaint activity in Salesforce. Outside counsel estimates 15–20 devices; the inventory estimates 20–25. Document the proportionality analysis.

- **Tier 3:** all remaining devices stay under the hold and the refresh halt, with settings changed to keep messages permanently (Attachment 3 of the notice). Re-assess quarterly.

- **Executive devices:** image Suresh, Torrence, Morrissey, Huang, Braddock, and Kowalski devices in Tier 1 or 2, based on questionnaire results.

- **VantagePulse:** the sources conflict on who hosts it (see Part V). By June 4, confirm the developer and host. Send a preservation demand to VantagePulse, Inc. and/or the cloud hosting provider to suspend the 2-year rolling analytics purge and the 30-day backup rotation, and to preserve all Vantage account data. Consider pushing a managed-app configuration that triggers a sync **without** deleting local data (test first with Corestone).

## E. Veeva Vault (QMS and Submissions)

- By June 3–6: suspend obsolescence, archival, and abandoned-draft purge workflows for KR-3000 records (about 3,500–4,000 of the ~12,000 documents), following 21 CFR Part 11 change control. Review the 60-day recycle bin and restore any KR-3000 items deleted since April 2025.

- Full-fidelity preservation: keep the vault intact. Corestone and Veeva Professional Services perform a Vault API / Vault Loader export with version history, audit trails, e-signatures, and document relationships (complaint → CAPA → MDR). **PDF renditions alone are not acceptable.** \$15,000–\$25,000.

- Braddock and Petrosian certify in writing that no KR-3000 records have changed lifecycle state since May 28 (outside counsel § V.B).

## F. Backup Tapes (Commvault / LTO-8)

- By June 3: halt all rotation, overwrite, recycling, and degaussing. Segregate and label existing daily, weekly, monthly, and **annual** tapes. Preserve the Commvault catalog. Retrieve the tape inventory from the Indianapolis off-site facility. Do not restore tapes for now (Rule 26(b)(2)(B)); restoration is a later decision.

- **The sources conflict on which tapes exist** (see Part V). IT-ARCH says annual tapes from January 2019 onward exist with 7-year retention. The policy says annual tapes are kept 3 years. Tilden’s email says the oldest tape is from about March 2025. If the January 2019–2022 annual tapes exist, they may be the **only** surviving copy of purged design-period email and of SAP and file-server states. A physical inventory is required by **June 6**.

- Also preserve the 90-day rolling weekly Salesforce exports stored on the Fort Wayne file server (IT-ARCH §5.2).

## G. R&D Shared Drive, SolidWorks PDM, Other File Shares

- Forensic image of \\VNTG-ENG01\RnD\KR3000 (~850 GB) with SHA-256 hashes by June 13. After imaging, preserve file-system metadata and set a read-only snapshot. Dr. Huang may keep working on a copy.

- SolidWorks PDM: full vault database (SQL) and archive backup; verify integrity; preserve ECO history. Confirm that the SAP BOM integration is not disrupted by the migration.

- Also preserve \\VNTG-MFG01\Production, \\VNTG-FS02 departmental shares, \\VNTG-LEGAL01\Litigation, and \\VNTG-HR01\Personnel (KR-3000-relevant folders).

## H. Salesforce CRM

- Hold notice to Sales Operations today. Disable mass delete for relevant objects. Perform a full Data Export Service export by June 13. Check whether Field Audit Trail / Shield is enabled for Account, Contact, Case, and Activity. The ~340,000 interaction records may include field complaint reports that never reached the formal complaint system. That is a sensitive category for both MDR and fraudulent-concealment purposes, so preserve it intact and do not remediate it before counsel review.

## I. Paper Records and Physical Evidence

- **Iron Mountain:** stop the July 1 transfer of KR-3000 boxes (about 12 bankers boxes). Inventory, scan, and keep originals (signatures and annotations).

- Legal takes custody of Dr. Huang’s ~14 engineering notebooks (2017–2023), with a chain-of-custody log and working copies provided to R&D.

- **Physical evidence (not in the inventory):** retrieved/explanted KR-3000 components, including those used in the Q3 2022 metallurgical analysis; any returned device associated with Kessler (revision January 8, 2025) or Dufresne; metallurgical mounts and specimens; bench-test samples from 2017–2019; retained production samples by lot (Fort Wayne and Ashford). **Suspend all destructive testing and disposal** without Legal approval. Record storage conditions and custody. Any future testing should follow a protocol agreed with plaintiffs, so that we are not accused of spoliation by destructive testing.

- Identify the lot and serial numbers of the named plaintiffs’ implants and preserve the related DHRs, complaint files, and MDRs as a priority set.

## J. Third-Party Preservation Demands

| **Third party**                                                                                                        | **Basis / scope**                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | **Owner**                             | **Send by**                         |
|------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------|-------------------------------------|
| Ashford Precision Components, Inc., 1580 Commerce Ave SE, Grand Rapids, MI 49503 (Robert M. Hensley, Quality Director) | Quality Agreement QA-2017-0044 §8.3 (notice before destruction) and §8.5 (electronic records on request); constructive control under Rule 34(a). **All** KR-3000 components (the complaint says femoral; the inventory says tibial tray; the data-source tab says both); **January 1, 2017** to present (pre-market validation), not 2019. Epicor/MasterControl data, CoCs, validation, surface-finish data, CAPAs, and correspondence. Written confirmation required within 5 business days. | Prichard (drafts); Kowalski (liaison) | **June 6** (email + certified mail) |
| VantagePulse, Inc. and/or cloud host                                                                                   | Suspend the server-side 2-year purge and 30-day backup rotation; preserve all Vantage data, logs, and backups                                                                                                                                                                                                                                                                                                                                                                                 | Prichard / Torrence                   | June 6                              |
| Greenbridge E-Cycling; device logistics vendor                                                                         | Hold and do not wipe or recycle any Vantage devices received                                                                                                                                                                                                                                                                                                                                                                                                                                  | Tilden                                | June 3                              |
| Iron Mountain                                                                                                          | Hold KR-3000 boxes; no destruction (Iron Mountain Destruction Services)                                                                                                                                                                                                                                                                                                                                                                                                                       | Legal                                 | June 6                              |
| SAP implementation partner                                                                                             | Preserve migration work product and data extracts                                                                                                                                                                                                                                                                                                                                                                                                                                             | Tilden                                | June 6                              |
| Veeva Systems                                                                                                          | Engage Professional Services; confirm no purge from Veeva backups                                                                                                                                                                                                                                                                                                                                                                                                                             | Braddock / Tilden                     | June 6                              |
| Third-party email archive vendor                                                                                       | Suspend deletion and apply hold                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Tilden                                | June 4                              |
| Corestone Analytics (Daniel Okafor)                                                                                    | Engagement / SOW under outside counsel (to support work-product protection)                                                                                                                                                                                                                                                                                                                                                                                                                   | Prichard                              | June 3                              |

## K. Personal Devices and Accounts (BYOD)

- The questionnaire is included with the notice (Attachment 2), due June 9. Priority follow-up: **Dr. Suresh**, who reportedly uses a personal iPhone and Gmail for KOL and advisory-board communications. The complaint specifically alleges this (¶¶ 59, 121). Outside counsel should meet with her by June 6 to agree a consent-based, targeted collection of work-related content only. Follow up with Petrosian before June 20, and with Torrence, Morrissey, Huang, Braddock, and Chandrasekaran.

- Review BYOD Policy VNT-IT-POL-012 and employment agreements for access rights. Compliance with that policy has been inconsistent.

## L. Privilege, and the General Counsel as Custodian

- The complaint names the General Counsel as a participant in the alleged post-Q3 2022 decision (¶¶ 68, 74). Plaintiffs are likely to raise crime-fraud and “at-issue” arguments. **Recommendation:** outside counsel formally co-owns hold administration. A Calloway Prichard Weeks senior associate is designated privilege coordinator. The GC does **not** self-collect or pre-screen her own files. Collect them into a segregated review environment.

- Seek a FRE 502(d) order at the Rule 26(f) conference (expected within about 90 days). Set up a privilege-log protocol early. Assess separately whether Pinnacle Indemnity Group correspondence and board materials are privileged.

- This memo and the IT/HR directives are privileged. The hold notice itself should be drafted on the assumption that it may be disclosed if preservation is challenged, which is why it is written in neutral, non-argumentative terms.

## M. Hold Administration and Defensibility

- Issue June 2 by email with read receipt, plus hard copy to named custodians. Field reps receive the notice with Attachment 3 through DocuSign, distributed via Torrence and supported by HR. Acknowledgments are due **June 9** (5 business days, per VNT-POL-007 §7.4). Send a reminder on June 6 to anyone who has not responded. Phone or in-person follow-up and escalation to the supervisor after June 11.

- Hold log: custodian, date sent, acknowledgment date, questionnaire results, devices, systems on hold, collection status.

- Reminders: August 1, 2025 (outside counsel’s 60-day recommendation), then quarterly (VNT-POL-007 minimum). Re-issue whenever scope changes (for example, new custodians from questionnaires, amended complaint, or related filings).

- Board of Directors: send a separate hold through the Corporate Secretary covering Diligent Boards and directors’ personal email, if used.

- New hires or replacements in QA (Petrosian successor) and any new KR-3000 personnel receive the notice at onboarding.

- Keep all written directives, IT confirmations, screenshots, hash reports, and chain-of-custody forms in the hold file.

# V. Discrepancies Identified in the Source Materials

*In each case below we adopted the more protective position. Each item needs to be confirmed.*

| **\#** | **Issue**                           | **Conflicting sources**                                                                                                                                                                     | **Resolution / action**                                                          |
|--------|-------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| 1      | Petrosian imaging deadline          | Outside counsel: June 13. Inventory ACT-007: June 18. HR workflow auto-starts about June 13.                                                                                                | June 13. HR suspension issued today.                                             |
| 2      | Petrosian company iPhone            | HR: iPhone wiped on last day. Not in the inventory or the 30-device count.                                                                                                                  | Add to imaging scope.                                                            |
| 3      | Petrosian mailbox and H: drive      | HR: mailbox converted, then deleted under the retention schedule; H: drive purged 30 days after departure.                                                                                  | Suspend; M365 hold; image H: drive.                                              |
| 4      | CEO Morrissey                       | Named in the complaint; outside counsel Tier 2 custodian. Missing from inventory and M365 hold list.                                                                                        | Added to notice, M365 hold, and BYOD follow-up.                                  |
| 5      | Q3 2022 email and the June 30 purge | Inventory and outside counsel: June 30 purge destroys Q3 2022 email. The purge cutoff is June 30, 2022.                                                                                     | The Q3 2022 risk is the Sept 30 purge. Disable all purges now.                   |
| 6      | Whether earlier purges already ran  | Policy Rev. 3 has run quarterly purges since January 2024. The sources nonetheless assume 2017–2019 email still exists.                                                                     | IT to produce purge logs and the earliest surviving email dates by June 4.       |
| 7      | Teams retention                     | Policy and inventory: 1 year, monthly purge. IT-ARCH: 3 years, quarterly.                                                                                                                   | Disable both. Determine the actual configuration.                                |
| 8      | SharePoint/OneDrive purge           | Policy: 5 years from last modification, annual Dec 31 purge. IT-ARCH and inventory: no auto-purge.                                                                                          | Disable any retention deletion. Apply hold.                                      |
| 9      | Voicemail and Veeva draft purges    | In the policy; absent from the inventory action plan.                                                                                                                                       | Added (June 3).                                                                  |
| 10     | Backup tape retention               | IT-ARCH: annual tapes kept 7 years, from January 2019. Policy: annual tapes kept 3 years. Tilden email: 90-day rotation, oldest about March 2025. Inventory: oldest monthly tape June 2024. | Halt everything. Physical inventory by June 6.                                   |
| 11     | SAP decommissioning                 | July 15 plan vs. VNT-POL-007 §4.2 (90 days read-only plus GC approval) and §7.5. IT-ARCH go-live July 1 vs. the email’s June 16 go-live.                                                    | No decommissioning without a GC sign-off gate. Confirm the timeline with Tilden. |
| 12     | Ashford components and period       | Complaint: femoral components. Inventory: tibial tray. Data-source tab: both. Inventory: data from 2019. Complaint and QA-2017-0044: 2017 pre-market validation.                            | Demand covers all KR-3000 components from January 1, 2017.                       |
| 13     | Ashford records inside Vantage      | Inventory: Ashford records NOT in Vantage systems. IT-ARCH §8: Ashford CoCs and batch records copied into SAP QM.                                                                           | Both apply. Include SAP QM copies in the SAP preservation.                       |
| 14     | Ashford demand date                 | Outside counsel: June 6. Inventory: June 9.                                                                                                                                                 | June 6.                                                                          |
| 15     | VantagePulse ownership and hosting  | Inventory: third-party developer VantagePulse, Inc., 2-year server purge. IT-ARCH: built in-house, third-party cloud host, 30-day backups.                                                  | Confirm by June 4. Send demands to whichever entities hold data.                 |
| 16     | Refresh scope                       | Inventory: remaining 55 on staggered schedule through Q4. Tilden: Batch 2 of 25 on July 21.                                                                                                 | Halt all refreshes.                                                              |
| 17     | Tier 2 territories                  | Inventory priority list: IN/OH/MI/IL/KY. Dufresne was implanted in Tampa, FL.                                                                                                               | Add FL (Tampa) and Columbus territories.                                         |
| 18     | Titles                              | Braddock: VP vs. Senior Director. Suresh: CMO vs. VP Clinical Affairs. Callahan: VP Finance vs. CFO. Waverly: VP vs. Director HR. Kowalski: reported to “VP of Manufacturing.”              | HR to confirm before hold log and court filings.                                 |
| 19     | Email domains                       | Emails use @vantagemeddevices.com; IT-ARCH uses @vantagemed.com; inventory uses @vantagemeddev.com.                                                                                         | IT to confirm all domains and aliases so M365 holds and searches cover each.     |
| 20     | Reminder cadence                    | Outside counsel: 60 days. Policy: quarterly.                                                                                                                                                | August 1, then quarterly.                                                        |

# VI. Master Action Tracker

| **\#** | **Action**                                                                                           | **Owner (Legal / Business)**              | **Deadline** |
|--------|------------------------------------------------------------------------------------------------------|-------------------------------------------|--------------|
| 1      | Issue hold notice, Schedule A distribution, and Attachments 1–4                                      | Chandrasekaran / Torrence (reps), Waverly | **June 2**   |
| 2      | Sign and send IT directive (Appendix A-1) and HR directive (A-2)                                     | Chandrasekaran                            | **June 2**   |
| 3      | Halt all device refresh and wipes; MDM wipe lock; notify Greenbridge                                 | Tilden / Torrence                         | **June 2–3** |
| 4      | Disable Teams, voicemail, Veeva-draft, and SharePoint/OneDrive purges; halt tape rotation            | Tilden / Braddock, Petrosian              | **June 3**   |
| 5      | Engage Corestone under outside counsel; schedule Petrosian and Tier 1 imaging                        | Prichard / Okafor                         | **June 3–4** |
| 6      | Preservation coordination meeting (GC, Tilden, Kowalski, Prichard, Corestone)                        | Chandrasekaran                            | **June 3**   |
| 7      | Disable quarterly email purge; M365 holds on all custodians and shared mailboxes; email archive hold | Tilden                                    | **June 4**   |
| 8      | Purge-history report, earliest surviving email dates, devices wiped since May 28                     | Tilden                                    | **June 4**   |
| 9      | SAP halt / no-archival directive; KR-3000 data scoping                                               | Chandrasekaran / Tilden, Kowalski         | **June 4**   |
| 10     | Confirm VantagePulse developer and host                                                              | Torrence / Tilden                         | June 4       |
| 11     | Ashford, VantagePulse, and vendor preservation demands                                               | Prichard / Kowalski                       | **June 6**   |
| 12     | Physical backup tape inventory (including annual tapes)                                              | Tilden                                    | June 6       |
| 13     | Suresh BYOD meeting with outside counsel                                                             | Prichard / Suresh                         | June 6       |
| 14     | Take custody of engineering notebooks; hold Iron Mountain transfer; physical evidence hold           | Legal / Huang, Kowalski                   | June 6       |
| 15     | Acknowledgments and questionnaires returned; reminder on June 6                                      | Legal / Waverly                           | **June 9**   |
| 16     | Tier 1 devices shipped to Corestone                                                                  | Tilden / Torrence                         | June 11      |
| 17     | Veeva admin transfer to Braddock; Petrosian knowledge transfer                                       | Tilden / Petrosian, Braddock              | June 12      |
| 18     | Petrosian forensic imaging complete (laptop, iPhone, H: drive, Veeva export)                         | Corestone / Tilden                        | **June 13**  |
| 19     | R&D drive image; Salesforce full export; PDM backup                                                  | Tilden / Huang, Torrence                  | June 13      |
| 20     | SAP forensic snapshot and verified KR-3000 extraction                                                | Corestone / Tilden, Kowalski              | **June 14**  |
| 21     | Petrosian exit interview and departure certification                                                 | Prichard / Waverly                        | June 18      |
| 22     | Tier 1 (30 devices) imaging complete                                                                 | Corestone                                 | **June 20**  |
| 23     | Independent verification of M365 purge disablement and holds                                         | Corestone / Tilden                        | June 27      |
| 24     | Tier 2 device selection memo and start of collection                                                 | Prichard / Torrence                       | June 30      |
| 25     | Veeva full-fidelity export                                                                           | Corestone / Veeva PS                      | July 11      |
| 26     | SAP decommissioning sign-off gate (default: not approved)                                            | Chandrasekaran                            | July 14      |
| 27     | First reminder notice and compliance audit                                                           | Legal                                     | August 1     |

# VII. Decisions Needed From the General Counsel Today

1.  Approve issuance of the hold notice and sign the Appendix A directives.

2.  Approve **company-wide** (not custodian-only) suspension of M365 auto-purges for the duration of the hold (recommended).

3.  Approve the SAP approach: forensic snapshot plus verified extraction before June 16; go-live proceeds; **no** July 15 decommissioning.

4.  Authorize Corestone engagement through outside counsel and the initial budget (see Part VIII).

5.  Approve outside counsel as co-administrator of the hold and privilege coordinator for GC-custodian materials.

6.  Direct outside counsel to assess the trigger date and the historical-purge exposure.

# VIII. Budget

Outside counsel estimates initial preservation costs of **\$175,000–\$250,000**, within the \$5M self-insured retention under Pinnacle Policy No. PLG-2025-VNT-0041. Main items: SAP extraction and imaging \$15K–\$40K; Petrosian imaging \$5K–\$8K; Tier 1 devices \$9K–\$15K; Tier 2 devices \$16.5K–\$27.5K (lower with the proportional approach); Veeva export \$15K–\$25K; Ashford demand \$3K–\$5K; plus processing (\$35/GB), hosting (\$18/GB/month), and attorney oversight. Track all preservation spend separately for SIR erosion and insurer reporting. **Cost must not drive preservation scope** for any at-risk source.

# Appendix A-1 — Written Preservation Directive to IT (for GC signature)

**To:** Marcus Tilden, Director of IT **From:** Priya Chandrasekaran, General Counsel **Date:** June 2, 2025 **Re:** Litigation Hold LH-2025-001 — Mandatory System Preservation Actions (Privileged & Confidential)

Under VNT-POL-007 §§ 2.2, 5.2, and 7.2, and effective immediately, you are directed to:

7.  Disable, company-wide and until further written notice, the M365 quarterly email purge, the monthly Teams purge, the annual SharePoint/OneDrive purge, and the voicemail 90-day purge. Suspend deletion rules in the third-party email archive. Confirm in writing with screenshots within 24 hours.

8.  Apply M365 Litigation/eDiscovery Holds to the Schedule A custodians (including G. Morrissey) and to shared mailboxes Quality@ and RegulatoryAffairs@, covering mailboxes, archives, Recoverable Items, OneDrive, Teams, and the listed SharePoint sites.

9.  Suspend VNT-IT-SOP-023 device refresh for all company-issued devices. Issue no MDM wipe or reset commands. Instruct Greenbridge and the logistics vendor to hold all Vantage devices. Preserve the Workspace ONE console data.

10. Halt all Commvault/LTO rotation, overwrite, and destruction. Segregate and label all tapes. Preserve the catalog. Provide a physical inventory by June 6.

11. Take no action that archives to ILM, deletes, converts, or decommissions SAP ECC 6.0 KR-3000 data, and do not decommission the ECC 6.0 system, without my written approval. Coordinate the forensic snapshot and extraction with Corestone for completion by June 14.

12. Do not deactivate-and-delete, reimage, wipe, convert, or purge any account, device, or drive of S. Petrosian. Coordinate forensic imaging with Corestone for completion by June 13.

13. Coordinate with T. Braddock to disable the Veeva abandoned-draft purge and KR-3000 obsolescence workflows under change control, and restore recycle-bin items.

14. By June 4, report in writing: (a) execution logs for all email and Teams purges since January 1, 2024; (b) the earliest surviving email date for each Tier 1 custodian; (c) any devices wiped or recycled since May 28, 2025; (d) all email domains and aliases; (e) the VantagePulse developer and hosting provider.

15. Preserve your own and the IT Department’s records on retention settings, purges, the SAP migration, device refresh, and offboarding.

Signed: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Priya Chandrasekaran, General Counsel

# Appendix A-2 — Written Directive to Human Resources (for GC signature)

**To:** Colleen M. Waverly, Human Resources **Cc:** Marcus Tilden **Date:** June 2, 2025 **Re:** Suspension of HR-PROC-012 — S. Petrosian and all hold custodians (Privileged & Confidential)

16. Suspend the standard Employee Separation Checklist (HR-PROC-012) for Sandra K. Petrosian before it auto-initiates (about June 13). No laptop reimage or redeployment, no iPhone wipe, no mailbox conversion or deletion, no H: drive review or purge, and no deletion of M365, SAP, or Veeva accounts. Accounts may be disabled after June 20 only as coordinated with Legal and IT.

17. Schedule Ms. Petrosian’s exit interview for about June 16–18 with Legal and outside counsel participating, and a departure certification under VNT-POL-007 §7.5(e).

18. Going forward, notify Legal the same day any Schedule A custodian or field representative gives notice. No offboarding for such persons proceeds without Legal clearance.

19. Preserve personnel files, training records, BYOD agreements, ethics-hotline records relating to the KR-3000, and HR communications about Ms. Petrosian’s resignation. Support acknowledgment tracking for field representatives.

Signed: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ Priya Chandrasekaran, General Counsel
